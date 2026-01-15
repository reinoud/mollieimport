import pytest
from mollie_api import MollieAPI


def test_mollie_api_dry_run():
    api = MollieAPI("test_key", test=True)
    cust = {"email": "x@y.com", "given_name": "X", "family_name": "Y"}
    resp = api.create_customer(cust)
    assert resp.get("_test") is True
    assert "/customers" in resp.get("url")

    # import mandate
    mandate = {"iban":"NL91ABNA0417164300","given_name":"X","family_name":"Y","mandate_reference":"mref","mandate_signature_date":__import__('datetime').date(2024,1,1)}
    resp2 = api.import_mandate("cst_test", mandate)
    assert resp2.get("_test") is True

    plan = {"amount": 10.0, "currency": "EUR", "interval": "1 year"}
    resp3 = api.create_subscription("cst_test", plan)
    assert resp3.get("_test") is True

