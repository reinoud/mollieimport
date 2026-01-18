import requests
import time
import hashlib
from typing import Dict, Optional


class MollieAPI:
    """Minimal Mollie API wrapper with create customer, import mandate, and create subscription.

    This wrapper supports a dry-run mode (test=True) where no POST requests are performed.
    It performs simple retry logic for transient errors.
    Deterministic idempotency keys are generated so repeated runs do not create duplicates.
    """

    BASE = "https://api.mollie.com/v2"

    def __init__(self, api_key: str, test: bool = False, logger=None):
        self.api_key = api_key
        self.test = test
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        self.logger = logger

    def _deterministic_key(self, *parts: str) -> str:
        """Create a deterministic idempotency key from given parts.

        The key is a SHA-256 hex digest of the joined parts. This ensures the same logical
        action produces the same idempotency key across runs.
        """
        joined = "|".join([p or "" for p in parts])
        h = hashlib.sha256(joined.encode("utf-8")).hexdigest()
        # Mollie accepts reasonably long idempotency keys; keep full hash for safety
        return h

    def _post(self, path: str, payload: Dict, idempotency_key: Optional[str] = None) -> Dict:
        url = f"{self.BASE}{path}"
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        if self.test:
            if self.logger:
                self.logger.info("[TEST MODE] POST %s payload=%s idempotency=%s", url, payload, idempotency_key)
            # Create a deterministic fake id for customers/mandates/subscriptions so the
            # rest of the pipeline can continue in dry-run mode.
            fake = {"_test": True, "url": url, "payload": payload, "idempotency": idempotency_key}
            # derive stable short id
            key_source = idempotency_key or hashlib.sha256(repr((path, payload)).encode("utf-8")).hexdigest()
            short = key_source[:12]
            if "/customers" in path and path.rstrip("/").endswith("/customers"):
                fake_id = f"cst_{short}"
                fake["id"] = fake_id
            elif "/mandates" in path:
                fake_id = f"mdt_{short}"
                fake["id"] = fake_id
            elif "/subscriptions" in path:
                fake_id = f"sub_{short}"
                fake["id"] = fake_id
            return fake

        # Simple retry logic
        attempts = 0
        max_attempts = 5
        backoff = 1.0
        while attempts < max_attempts:
            attempts += 1
            try:
                resp = self.session.post(url, json=payload, headers=headers, timeout=10)
            except requests.RequestException as exc:
                if self.logger:
                    self.logger.warning("Request exception on %s: %s (attempt %s)", url, exc, attempts)
                time.sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code in (200, 201):
                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"status_code": resp.status_code, "text": resp.text}
                # Attach idempotency key for tracing
                if idempotency_key:
                    resp_json["idempotency"] = idempotency_key
                return resp_json

            # Retry on server errors and rate limits
            if resp.status_code >= 500 or resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else backoff
                if self.logger:
                    self.logger.warning("Server returned %s for %s. Retrying in %s seconds (attempt %s)", resp.status_code, url, wait, attempts)
                time.sleep(wait)
                backoff *= 2
                continue

            # Other status codes are treated as permanent errors
            try:
                err = resp.json()
            except Exception:
                err = {"status_code": resp.status_code, "text": resp.text}
            raise RuntimeError(f"Mollie API error: {err}")

        raise RuntimeError(f"Failed to POST {url} after {max_attempts} attempts")

    def create_customer(self, customer: Dict) -> Dict:
        """Create a mollie customer.

        Expects a dict containing at least: email, given_name, family_name.
        Uses a deterministic idempotency key based on the email to avoid duplicate customers on re-run.
        Returns the Mollie response as dict.
        """
        payload = {
            "email": customer.get("email"),
            "name": f"{customer.get('given_name','')} {customer.get('family_name','')}".strip(),
        }
        if customer.get("customer_reference"):
            payload["metadata"] = {"customer_reference": customer.get("customer_reference")}

        key = self._deterministic_key("customer", customer.get("email", ""))
        return self._post("/customers", payload, idempotency_key=key)

    def import_mandate(self, customer_id: str, mandate: Dict) -> Dict:
        """Import a SEPA mandate for an existing customer.

        Args:
            customer_id: Mollie customer id (e.g., cst_...)
            mandate: dict with keys: "iban", "mandate_reference", "mandate_signature_date"

        The idempotency key is based on the customer_id and the mandate_reference so repeated
        imports for the same mandate won't create duplicates.
        """
        payload = {
            "method": "directdebit",
            "consumerName": f"{mandate.get('given_name','')} {mandate.get('family_name','')}",
            "consumerAccount": mandate.get("iban"),
            "mandateReference": mandate.get("mandate_reference"),
            "signatureDate": mandate.get("mandate_signature_date").isoformat(),
        }
        key = self._deterministic_key("mandate", customer_id, mandate.get("mandate_reference", ""))
        return self._post(f"/customers/{customer_id}/mandates", payload, idempotency_key=key)

    def create_subscription(self, customer_id: str, plan: Dict) -> Dict:
        """Create a subscription for a customer.

        Args:
            customer_id: Mollie customer id
            plan: dict with keys: amount (float), currency (str), interval (e.g., '1 year')
                  optional key: start_date (datetime.date) - if present the subscription will be
                  scheduled to start on that date (ISO format is used for the Mollie payload).

        The idempotency key is based on the customer_id, amount, interval and start_date (if any)
        to ensure a repeated subscription creation attempt for the same plan doesn't duplicate.
        """
        payload = {
            "amount": {"value": f"{plan.get('amount'):.2f}", "currency": plan.get("currency", "EUR")},
            "interval": plan.get("interval", "1 year"),
            "description": plan.get("description", "Yearly membership"),
        }
        # Include startDate if provided (expecting a date object or ISO string)
        start = plan.get("start_date") or plan.get("startDate")
        if start is not None:
            # accept date object or string
            if hasattr(start, "isoformat"):
                payload["startDate"] = start.isoformat()
                start_str = start.isoformat()
            else:
                payload["startDate"] = str(start)
                start_str = str(start)
        else:
            start_str = ""

        # Normalize amount and interval into the key
        amount_str = f"{plan.get('amount'):.2f}" if plan.get('amount') is not None else ""
        key = self._deterministic_key("subscription", customer_id, amount_str, plan.get("interval", ""), start_str)
        return self._post(f"/customers/{customer_id}/subscriptions", payload, idempotency_key=key)
