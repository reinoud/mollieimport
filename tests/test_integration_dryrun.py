import os
import csv
from main import main


def test_end_to_end_dryrun(tmp_path, monkeypatch):
    # create a simple csv
    p = tmp_path / "export.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["email","given_name","family_name","iban","mandate_reference","mandate_signature_date","amount"])
        writer.writerow(["a@example.com","A","B","NL91ABNA0417164300","ref1","2024-01-01","12.50"])

    # run main in test mode
    main(["--test", "--export", str(p)])

    # check imported csv exists
    out = tmp_path / "imported_export.csv"
    assert out.exists()
    with open(out, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["status"] == "ok"

