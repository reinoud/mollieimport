import csv
from typing import Dict, Generator, List, Optional
from datetime import datetime

from stdnum import iban as iban_module


# Dutch column names from export.csv
REQUIRED_COLUMNS = ["Email", "Voor naam", "Naam", "IBAN", "MachtigingsID", "Datum Ondertekening", "Bedrag"]


def validate_iban(iban_value: str) -> bool:
    """Validate IBAN using python-stdnum.

    Returns True if valid, False otherwise.
    """
    try:
        iban_module.validate(iban_value)
        return True
    except Exception:
        return False


def _detect_delimiter(sample: str) -> str:
    """Attempt to detect delimiter (comma or semicolon) from a sample string."""
    # Prefer semicolon if present, otherwise rely on csv.Sniffer
    if ";" in sample and "," not in sample:
        return ";"
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        return dialect.delimiter
    except Exception:
        return ","


def _parse_date(date_str: str):
    """Try parsing date in multiple common formats (ISO and Dutch D-M-Y). Returns date object or raises."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"):  # try ISO then Dutch
        try:
            return datetime.strptime(date_str, fmt).date()
        except Exception:
            continue
    raise ValueError(f"Unrecognized date format: {date_str}")


def read_customers(path: str, validate_iban_flag: bool = True, logger: Optional[object] = None) -> Generator[Dict[str, object], None, None]:
    """Yield validated customer rows from a CSV file using Dutch headers.

    Performs validation on required columns, optional IBAN checksum, date parsing for Datum Ondertekening,
    and numeric parsing for Bedrag. Invalid rows are skipped (but can be logged by caller).

    Args:
        path: path to the CSV file.
        validate_iban_flag: if False, skip IBAN checksum validation.
        logger: optional logger to emit warnings (e.g., when IBAN is invalid).

    Yields:
        Dict with cleaned row data. Keys follow the Dutch header names from the export file.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        delimiter = _detect_delimiter(sample)
        reader = csv.DictReader(fh, delimiter=delimiter)
        headers = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in headers]
        if missing:
            raise KeyError(f"CSV missing required columns: {missing}")

        for i, row in enumerate(reader, start=1):
            # Trim whitespace
            row = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}

            # Basic non-empty check
            if not row.get("Email") or not row.get("IBAN"):
                if logger:
                    logger.warning("Row %s skipped: missing Email or IBAN", i)
                continue

            # IBAN validation (optional)
            if validate_iban_flag:
                try:
                    ok = validate_iban(row.get("IBAN"))
                except Exception:
                    ok = False
                if not ok:
                    if logger:
                        logger.warning("Row %s - invalid IBAN for %s: %s", i, row.get("Email"), row.get("IBAN"))
                    continue

            # Parse date (Datum Ondertekening)
            try:
                row["Datum Ondertekening"] = _parse_date(row["Datum Ondertekening"]) if row.get("Datum Ondertekening") else None
            except Exception:
                if logger:
                    logger.warning("Row %s skipped: invalid Datum Ondertekening for %s: %s", i, row.get("Email"), row.get("Datum Ondertekening"))
                continue

            # Ensure amount is present and numeric
            try:
                # Some exports use comma as decimal separator, normalize
                amt_raw = row.get("Bedrag", "").replace(" ", "")
                amt_raw = amt_raw.replace(",", ".")
                row["Bedrag"] = float(amt_raw)
            except Exception:
                if logger:
                    logger.warning("Row %s skipped: invalid Bedrag for %s: %s", i, row.get("Email"), row.get("Bedrag"))
                continue

            yield row


def sample_headers() -> List[str]:
    """Return a sample header layout for the CSV expected by the importer (Dutch headers)."""
    return [
        "Email",
        "Voor naam",
        "Naam",
        "IBAN",
        "MachtigingsID",
        "Datum Ondertekening",  # DD-MM-YYYY
        "Bedrag",  # decimal, e.g. 12.50
        "currency",
    ]
