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
        ["Email","Voor naam","Naam","IBAN","MachtigingsID","Datum Ondertekening","Bedrag"],
        ["a@example.com","A","B","NL91ABNA0417164300","ref1","01-01-2024","25,00"],
        ["bad@example.com","C","D","INVALIDIBAN","ref2","01-01-2024","10,00"],
    ]
    # write with semicolon delimiter to mimic test_export.csv
    with open(p, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=';')
        writer.writerows(data)

    rows = list(read_customers(str(p)))
    assert len(rows) == 1
    assert rows[0]["Email"] == "a@example.com"
    assert rows[0]["Bedrag"] == 25.0
    assert str(rows[0]["Datum Ondertekening"]) == "2024-01-01"
