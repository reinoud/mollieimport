# Mollie SEPA Importer

Dit project bevat een Python-script om klanten uit een CSV-import (`export.csv`) in te lezen en jaarlijks terugkerende incasso's (SEPA-mandaten + abonnementen) aan te maken in de Mollie API.

Belangrijkste acties die het script uitvoert
- Aanmaken van Mollie customers via `POST /v2/customers`
- Importeren van SEPA-mandates via `POST /v2/customers/{customerId}/mandates` (zonder hertekenen)
- Aanmaken van yearly subscriptions via `POST /v2/customers/{customerId}/subscriptions`
- Bijhouden van resultaten in een output-CSV (`imported_<basename>.csv`) en logging naar `import.log`
- Deterministische idempotency-keys gebruiken zodat her-runs geen duplicaten maken

Bestanden
- `main.py` – CLI + orchestrator
- `mollie_api.py` – minimale Mollie-wrapper (create_customer, import_mandate, create_subscription)
- `csv_reader.py` – CSV-lezer en validatie (incl. IBAN-check)
- `config_loader.py` – leest `config.ini`
- `logger_setup.py` – logging setup (rotating file handler)
- `requirements.txt` – benodigde dependencies
- `imported_<basename>.csv` – wordt gegenereerd door het script met resultaatregels per invoer
- `import.log` – logging bestand

Voorwaarden / prerequisites
- Python 3.8+ (project gebruikt virtualenv `.venv` in deze repo)
- Een Mollie API key in `config.ini` (zie voorbeeld)
- Internettoegang voor productie runs (niet nodig in `--test` dry-run)

Voorbeeld `config.ini`
```ini
[mollie]
APIkey=<MOLLIE_API_KEY>
ProfileID=<MOLLIE_PROFILE_ID> 
```

CSV-format (verplichte kolommen)
- Verplichte kolommen (exacte header-naam):
  - `email`
  - `given_name`
  - `family_name`
  - `iban` (IBAN wordt gevalideerd met `python-stdnum`)
  - `mandate_reference`
  - `mandate_signature_date` (YYYY-MM-DD)
  - `amount` (bijv. 12.50)

- Optionele kolommen: `currency` (standaard EUR), `interval` (standaard `1 year`), `description`, adresvelden

Voorbeeld CSV (first row = headers):
```csv
email,given_name,family_name,iban,mandate_reference,mandate_signature_date,amount,currency
a@example.com,A,B,NL91ABNA0417164300,ref1,2024-01-01,12.50,EUR
```

Gebruik
- Dry-run (testmodus, geen echte POSTs naar Mollie):

```bash
# met venv (aanbevolen):
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --test --export export.csv

# of zonder venv (zorg dat deps geïnstalleerd zijn):
python3 main.py --test --export export.csv
```

- Productierun (let op: echte API-calls, zorg dat `config.ini` correcte APIkey bevat):

```bash
.venv/bin/python main.py --export export.csv
```

Output & logging
- `imported_<basename>.csv` (staat in dezelfde map als het inputbestand) met kolommen:
  - `email`, `customer_id`, `customer_idempotency`, `mandate_id`, `mandate_idempotency`, `subscription_id`, `subscription_idempotency`, `status`, `error`
  - `status` is `ok` of `failed`; `error` bevat eventuele foutmeldingen
- `import.log`: draaitijd/log entries. Console toont WARNING+.

Deterministische idempotency
- Idempotency-keys worden deterministisch gegenereerd per actie met SHA-256 over betekenisvolle velden:
  - Customer: `customer|{email}`
  - Mandate: `mandate|{customer_id}|{mandate_reference}`
  - Subscription: `subscription|{customer_id}|{amount:.2f}|{interval}`
- Deze key wordt meegestuurd in `Idempotency-Key` header en ook opgenomen in de output-CSV (`*_idempotency` kolommen). Dit voorkomt dubbele aanmaak bij her-runs.

Fouten & retry
- Transient server errors (5xx) en 429 worden herhaald met exponentiële backoff (max 5 pogingen).
- Andere 4xx errors worden als permanente fouten behandeld en in `imported_*.csv` opgenomen als `failed` met fouttekst.

Tests
- De repo bevat unit- en integratietests met `pytest` in `tests/`.
- Test-run (gebruik de project venv):

```bash
# installeer test dependencies
.venv/bin/python -m pip install -r requirements.txt
# draai alle tests
.venv/bin/python -m pytest -q
# of draai single test
.venv/bin/python -m pytest tests/test_integration_dryrun.py::test_end_to_end_dryrun -q
```

Veiligheid / waarschuwing
- Productieruns sturen echte API-calls naar Mollie. Zorg dat je API-key correct is en dat je wilt dat er incasso's/mandates/subscriptions aangemaakt worden.
- Gebruik `--test` om dry-runs te doen voordat je in productie gaat.
