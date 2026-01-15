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

from typing import Optional
import argparse
import sys
import csv
import os

from logger_setup import setup_logging
from config_loader import load_config
from csv_reader import read_customers
from mollie_api import MollieAPI


def parse_args(argv: Optional[list] = None):
    """Parse command-line arguments.

    Returns:
        argparse.Namespace with attributes: test (bool), config (str), export (str)
    """
    parser = argparse.ArgumentParser(description="Import customers, mandates and subscriptions into Mollie")
    parser.add_argument("-t", "--test", action="store_true", help="Dry run; don't POST to Mollie")
    parser.add_argument("-c", "--config", default="config.ini", help="Path to config file")
    parser.add_argument("-e", "--export", default="export.csv", help="Path to CSV export file")
    return parser.parse_args(argv)


def process_customer(api: MollieAPI, row: dict, logger) -> dict:
    """Process a single customer row: create customer, import mandate, create subscription.

    Args:
        api: MollieAPI instance
        row: dict with customer data
        logger: logger instance

    Returns:
        dict with keys: customer, mandate, subscription containing Mollie responses or error info.
    """
    result = {"customer": None, "mandate": None, "subscription": None, "errors": []}

    try:
        cust_resp = api.create_customer(row)
        result["customer"] = cust_resp
        logger.info("Created customer for %s: %s", row.get("email"), cust_resp.get("id", cust_resp))
    except Exception as exc:
        logger.error("Failed to create customer for %s: %s", row.get("email"), exc)
        result["errors"].append(str(exc))
        return result

    customer_id = None
    if isinstance(cust_resp, dict):
        customer_id = cust_resp.get("id") or cust_resp.get("resource")

    if not customer_id:
        # In test mode or unexpected shape, try to continue using a placeholder id
        customer_id = cust_resp.get("id") if isinstance(cust_resp, dict) else None

    if not customer_id:
        logger.warning("No customer id returned for %s; proceeding in test mode or skipping mandate/subscription", row.get("email"))
        return result

    # Import mandate
    try:
        mandate_resp = api.import_mandate(customer_id, row)
        result["mandate"] = mandate_resp
        logger.info("Imported mandate for %s: %s", row.get("email"), mandate_resp.get("id", mandate_resp))
    except Exception as exc:
        logger.error("Failed to import mandate for %s: %s", row.get("email"), exc)
        result["errors"].append(str(exc))
        return result

    # Create subscription
    try:
        plan = {"amount": row.get("amount"), "currency": row.get("currency", "EUR"), "interval": row.get("interval", "1 year"), "description": row.get("description", "Yearly subscription")}
        sub_resp = api.create_subscription(customer_id, plan)
        result["subscription"] = sub_resp
        logger.info("Created subscription for %s: %s", row.get("email"), sub_resp.get("id", sub_resp))
    except Exception as exc:
        logger.error("Failed to create subscription for %s: %s", row.get("email"), exc)
        result["errors"].append(str(exc))

    return result


def write_imported_csv(out_path: str, rows: list):
    """Write the import results into a CSV file.

    Each row in `rows` should be a dict containing: email, customer_id, mandate_id, subscription_id, status, error
    and optional idempotency columns.
    """
    fieldnames = ["email", "customer_id", "customer_idempotency", "mandate_id", "mandate_idempotency", "subscription_id", "subscription_idempotency", "status", "error"]
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
        for row in read_customers(args.export):
            email = row.get("email")
            logger.info("Processing %s", email)
            res = process_customer(api, row, logger)

            out = {"email": email, "customer_id": "", "customer_idempotency": "", "mandate_id": "", "mandate_idempotency": "", "subscription_id": "", "subscription_idempotency": "", "status": "", "error": ""}
            if res.get("customer") and isinstance(res.get("customer"), dict):
                out["customer_id"] = res["customer"].get("id") or ""
                out["customer_idempotency"] = res["customer"].get("idempotency") or ""
            if res.get("mandate") and isinstance(res.get("mandate"), dict):
                out["mandate_id"] = res["mandate"].get("id") or ""
                out["mandate_idempotency"] = res["mandate"].get("idempotency") or ""
            if res.get("subscription") and isinstance(res.get("subscription"), dict):
                out["subscription_id"] = res["subscription"].get("id") or ""
                out["subscription_idempotency"] = res["subscription"].get("idempotency") or ""

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
