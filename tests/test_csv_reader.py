import io
import csv
import tempfile
from csv_reader import read_customers, validate_iban


def test_validate_iban_valid():
    assert validate_iban("NL91ABNA0417164300")


def test_validate_iban_invalid():
    assert not validate_iban("INVALIDIBAN123")


def test_read_customers(tmp_path):
    p = tmp_path / "test.csv"
    data = [
        ["email","given_name","family_name","iban","mandate_reference","mandate_signature_date","amount"],
        ["a@example.com","A","B","NL91ABNA0417164300","ref1","2024-01-01","12.50"],
        ["bad@example.com","C","D","INVALIDIBAN","ref2","2024-01-01","10.00"],
    ]
    with open(p, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(data)

    rows = list(read_customers(str(p)))
    assert len(rows) == 1
    assert rows[0]["email"] == "a@example.com"
    assert rows[0]["amount"] == 12.5
    assert str(rows[0]["mandate_signature_date"]) == "2024-01-01"

