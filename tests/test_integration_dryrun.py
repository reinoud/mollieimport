import csv
from main import main


def test_end_to_end_dryrun(tmp_path, monkeypatch):
    # create a simple csv with Dutch headers and semicolon delimiter
    p = tmp_path / "export.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=';')
        writer.writerow(["Email","Voor naam","Naam","IBAN","MachtigingsID","Datum Ondertekening","Bedrag"])
        writer.writerow(["a@example.com","A","B","NL91ABNA0417164300","ref1","01-01-2024","12,50"])

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
        # ensure idempotency columns are present
        assert "customer_idempotency" in rows[0]
        assert rows[0]["customer_idempotency"] != ""
