#!/usr/bin/env python3
"""Import customers, mandates and subscriptions into Mollie from a CSV export.

Usage:
    python main.py [--test] [--config CONFIG] [--export EXPORT]

Options:
    --test, -t    Dry-run mode: do not perform POST requests to Mollie.
    --config, -c  Path to config.ini (default: config.ini).
    --export, -e  Path to export CSV (default: export.csv).

The script reads Mollie API credentials from the [mollie] section of the config file.
"""

from typing import Optional, Dict
import argparse
import sys
import csv
import os
from datetime import date as _date, datetime

from logger_setup import setup_logging
from config_loader import load_config
from csv_reader import read_customers
from mollie_api import MollieAPI


def parse_args(argv: Optional[list] = None):
    """Parse command-line arguments.

    Returns:
        argparse.Namespace with attributes: test (bool), config (str), export (str), skip_iban_validation (bool)
    """
    parser = argparse.ArgumentParser(description="Import customers, mandates and subscriptions into Mollie")
    parser.add_argument("-t", "--test", action="store_true", help="Dry run; don't POST to Mollie")
    parser.add_argument("-c", "--config", default="config.ini", help="Path to config file")
    parser.add_argument("-e", "--export", default="export.csv", help="Path to CSV export file")
    parser.add_argument("-s", "--skip-iban-validation", action="store_true", help="Skip IBAN checksum validation")
    return parser.parse_args(argv)


def next_same_day_in_year(orig_date: _date, from_date: Optional[_date] = None) -> _date:
    """Return the next date (including this year) that has the same month/day as orig_date.

    If the month/day this year is on or after `from_date` (default today), return that date in the
    current year; otherwise return the same month/day in the next year. Keeps the original year
    only for constructing the month/day and does not depend on orig_date.year.

    Args:
        orig_date: date object with original month/day information
        from_date: date to consider as "today"; defaults to today
    Returns:
        datetime.date representing the next occurrence of orig_date's month/day
    """
    if from_date is None:
        from_date = _date.today()
    try:
        candidate = _date(from_date.year, orig_date.month, orig_date.day)
    except ValueError:
        # Handle Feb 29 on non-leap years: choose Mar 1 as Mollie-friendly alternative
        if orig_date.month == 2 and orig_date.day == 29:
            candidate = _date(from_date.year, 3, 1)
        else:
            raise
    if candidate < from_date:
        # Next year
        try:
            candidate = _date(from_date.year + 1, orig_date.month, orig_date.day)
        except ValueError:
            # Feb 29 -> Mar 1 fallback
            if orig_date.month == 2 and orig_date.day == 29:
                candidate = _date(from_date.year + 1, 3, 1)
            else:
                raise
    return candidate


def process_customer(api: MollieAPI, row: Dict[str, object], logger) -> Dict[str, object]:
    """Process a single customer row: create customer, import mandate, create subscription.

    The input `row` uses Dutch CSV headers. Map them to Mollie fields here.
    The subscription start date will be set to the same month/day as the original
    `Datum Ondertekening` (mandate signature date), in the next occurrence on or after today.
    """
    result = {"customer": None, "mandate": None, "subscription": None, "errors": []}

    # Map Dutch headers to fields expected by MollieAPI
    customer_payload = {
        "email": row.get("Email"),
        "given_name": row.get("Voor naam"),
        "family_name": row.get("Naam"),
        "customer_reference": str(row.get("LidNr") or ""),
    }

    try:
        cust_resp = api.create_customer(customer_payload)
        result["customer"] = cust_resp
        logger.info("Created customer for %s: %s", customer_payload.get("email"), str(cust_resp.get("id") or cust_resp))
    except Exception as exc:
        logger.error("Failed to create customer for %s: %s", customer_payload.get("email"), exc)
        result["errors"].append(str(exc))
        return result

    customer_id = None
    if isinstance(cust_resp, dict):
        customer_id = cust_resp.get("id") or cust_resp.get("resource")

    if not customer_id:
        customer_id = cust_resp.get("id") if isinstance(cust_resp, dict) else None

    if not customer_id:
        logger.warning("No customer id returned for %s; proceeding in test mode or skipping mandate/subscription", customer_payload.get("email"))
        return result

    # Mandate payload mapping
    mandate_payload = {
        "iban": row.get("IBAN"),
        "mandate_reference": str(row.get("MachtigingsID") or ""),
        "mandate_signature_date": row.get("Datum Ondertekening"),
        "given_name": row.get("Voor naam"),
        "family_name": row.get("Naam"),
    }

    try:
        mandate_resp = api.import_mandate(customer_id, mandate_payload)
        result["mandate"] = mandate_resp
        logger.info("Imported mandate for %s: %s", customer_payload.get("email"), str(mandate_resp.get("id") or mandate_resp))
    except Exception as exc:
        logger.error("Failed to import mandate for %s: %s", customer_payload.get("email"), exc)
        result["errors"].append(str(exc))
        return result

    # Subscription plan mapping - keep amount as float from csv_reader
    # Determine subscription start date to match original mandate signature day/month
    start_date = None
    if row.get("Datum Ondertekening"):
        try:
            orig = row.get("Datum Ondertekening")
            if hasattr(orig, "day"):
                start_date = next_same_day_in_year(orig)
        except Exception as exc:
            logger.warning("Could not compute subscription start date for %s: %s", customer_payload.get("email"), exc)

    plan = {"amount": row.get("Bedrag"), "currency": row.get("currency", "EUR"), "interval": row.get("interval", "1 year"), "description": row.get("description", "Yearly subscription")}
    if start_date:
        plan["start_date"] = start_date

    try:
        sub_resp = api.create_subscription(customer_id, plan)
        result["subscription"] = sub_resp
        logger.info("Created subscription for %s: %s", customer_payload.get("email"), str(sub_resp.get("id") or sub_resp))
    except Exception as exc:
        logger.error("Failed to create subscription for %s: %s", customer_payload.get("email"), exc)
        result["errors"].append(str(exc))

    # Record the chosen subscription start date (ISO string) so we can write it to the output CSV
    if start_date:
        result["subscription_startDate"] = start_date.isoformat()
    else:
        result["subscription_startDate"] = ""

    return result


def write_imported_csv(out_path: str, rows: list):
    """Write the import results into a CSV file.

    Each row in `rows` should be a dict containing: email, customer_id, mandate_id, subscription_id, status, error
    and optional idempotency columns.
    """
    fieldnames = ["email", "customer_id", "customer_idempotency", "mandate_id", "mandate_idempotency", "subscription_id", "subscription_idempotency", "subscription_startDate", "status", "error"]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main(argv: Optional[list] = None):
    args = parse_args(argv)
    logger = setup_logging()
    logger.info("Starting import; test=%s, config=%s, export=%s", args.test, args.config, args.export)

    try:
        cfg = load_config(args.config)
    except Exception as exc:
        logger.error("Failed to load config: %s", exc)
        sys.exit(1)

    api = MollieAPI(cfg.get("APIkey"), test=args.test, logger=logger)

    success_count = 0
    fail_count = 0
    out_rows = []

    try:
        for row in read_customers(args.export, validate_iban_flag=not args.skip_iban_validation, logger=logger):
            email = row.get("Email")
            logger.info("Processing %s", email)
            res = process_customer(api, row, logger)

            out = {"email": email, "customer_id": "", "customer_idempotency": "", "mandate_id": "", "mandate_idempotency": "", "subscription_id": "", "subscription_idempotency": "", "status": "", "error": ""}
            # include subscription_startDate column
            out["subscription_startDate"] = ""
            if res.get("customer") and isinstance(res.get("customer"), dict):
                out["customer_id"] = res["customer"].get("id") or ""
                out["customer_idempotency"] = res["customer"].get("idempotency") or ""
            if res.get("mandate") and isinstance(res.get("mandate"), dict):
                out["mandate_id"] = res["mandate"].get("id") or ""
                out["mandate_idempotency"] = res["mandate"].get("idempotency") or ""
            if res.get("subscription") and isinstance(res.get("subscription"), dict):
                out["subscription_id"] = res["subscription"].get("id") or ""
                out["subscription_idempotency"] = res["subscription"].get("idempotency") or ""
            # subscription_startDate may be present in the result
            out["subscription_startDate"] = res.get("subscription_startDate") or ""

            if res.get("errors"):
                out["status"] = "failed"
                out["error"] = "; ".join(res.get("errors"))
                fail_count += 1
            else:
                out["status"] = "ok"
                success_count += 1

            out_rows.append(out)
    except Exception as exc:
        logger.exception("Fatal error while processing CSV: %s", exc)
        sys.exit(1)

    # Write results CSV next to the input export file
    base = os.path.splitext(os.path.basename(args.export))[0]
    out_dir = os.path.dirname(args.export) or os.getcwd()
    out_name = os.path.join(out_dir, f"imported_{base}.csv")
    write_imported_csv(out_name, out_rows)
    logger.info("Wrote results to %s", out_name)

    logger.info("Import finished. Success: %s, Failed: %s", success_count, fail_count)


if __name__ == "__main__":
    main()
