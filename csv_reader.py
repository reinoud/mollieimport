import csv
from typing import Dict, Generator, List
from datetime import datetime

from stdnum import iban as iban_module


REQUIRED_COLUMNS = ["email", "given_name", "family_name", "iban", "mandate_reference", "mandate_signature_date", "amount"]


def validate_iban(iban_value: str) -> bool:
    """Validate IBAN using python-stdnum.

    Returns True if valid, False otherwise.
    """
    try:
        # stdnum.iban will raise an exception for invalid IBANs
        iban_module.validate(iban_value)
        return True
    except Exception:
        return False


def read_customers(path: str) -> Generator[Dict[str, object], None, None]:
    """Yield validated customer rows from a CSV file.

    Performs validation on required columns, IBAN checksum, date parsing for mandate_signature_date,
    and numeric parsing for amount. Invalid rows are skipped (but counted/logged by caller).

    Args:
        path: path to the CSV file.

    Yields:
        Dict with cleaned row data. Keys: same as CSV headers; "mandate_signature_date" becomes datetime.date and "amount" becomes float.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in headers]
        if missing:
            raise KeyError(f"CSV missing required columns: {missing}")

        for i, row in enumerate(reader, start=1):
            # Trim whitespace
            row = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}

            # Basic non-empty check
            if not row.get("email") or not row.get("iban"):
                continue

            # IBAN validation
            if not validate_iban(row.get("iban")):
                continue

            # Parse date
            try:
                row["mandate_signature_date"] = datetime.strptime(row["mandate_signature_date"], "%Y-%m-%d").date()
            except Exception:
                continue

            # Ensure amount is present and numeric
            try:
                row["amount"] = float(row["amount"])
            except Exception:
                continue

            yield row


def sample_headers() -> List[str]:
    """Return a sample header layout for the CSV expected by the importer."""
    return [
        "email",
        "given_name",
        "family_name",
        "iban",
        "mandate_reference",
        "mandate_signature_date",  # YYYY-MM-DD
        "amount",  # decimal, e.g. 12.50
        "currency",  # optional (defaults to EUR)
        "street",
        "city",
        "postal_code",
        "country",
    ]
