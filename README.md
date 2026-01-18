# Mollie SEPA Importer

Dit project importeert ledengegevens uit een CSV-export en maakt via de Mollie API:
- Mollie customers (via `POST /v2/customers`)
- SEPA-machtigingsrecords (mandates) via `POST /v2/customers/{customerId}/mandates` (import zonder hertekenen)
- Jaarlijkse subscriptions via `POST /v2/customers/{customerId}/subscriptions`

Belangrijke kenmerken
- Leest Nederlandse exportbestanden (semicolon-delimited) met Nederlandse kolomnamen.
- Valideert IBANs met `python-stdnum` (kan met een CLI-vlag uitgeschakeld worden).
- Gebruikt deterministische Idempotency-keys (SHA-256) zodat her-runs geen duplicaten aanmaken.
- Schrijft een resultaatbestand `imported_<basename>.csv` met per-regel status en idempotency-waarden.
- Logging naar `import.log` (rotating file handler).

Inhoud van de repository
- `main.py` – CLI orchestrator
- `mollie_api.py` – Mollie API wrapper (create_customer, import_mandate, create_subscription)
- `csv_reader.py` – CSV-lezer en validatie (ondersteunt Nederlandse headers en datumformaten)
- `config_loader.py` – config loader voor `config.ini`
- `logger_setup.py` – logging setup
- `requirements.txt` – benodigde Python packages
- `tests/` – pytest tests

CSV formaat / verwachte kolommen
Het script verwacht dat de export CSV Nederlandse header-namen gebruikt en meestal een semicolon (;) als delimiter. Vereiste kolommen (exacte headernaam):

- `Email` (e-mail adres)
- `Voor naam` (voornamen)
- `Naam` (achternaam)
- `IBAN` (IBAN, wordt gevalideerd tenzij uitgeschakeld)
- `MachtigingsID` (mandate reference / ID)
- `Datum Ondertekening` (datum handtekening machtiging, verwacht DD-MM-YYYY of YYYY-MM-DD)
- `Bedrag` (bedrag per incasso; kan komma gebruiken als decimale scheidingsteken)

Voorbeeld (1e regel = header, ; delimiter):

```csv
Email;Voor naam;Naam;IBAN;MachtigingsID;Datum Ondertekening;Bedrag
test@example.com;Jan;Jansen;NL91ABNA0417164300;ref-123;06-01-2021;12,50
```

Output bestand
- `imported_<basename>.csv` (zelfde map als inputbestand) met kolommen:
  - `email`
  - `customer_id`
  - `customer_idempotency`
  - `mandate_id`
  - `mandate_idempotency`
  - `subscription_id`
  - `subscription_idempotency`
  - `status` (`ok` of `failed`)
  - `error` (foutmelding indien aanwezig)

De idempotency-kolommen bevatten de deterministische Idempotency-keys die gebruikt werden bij de POST-requests — handig voor auditing en debugging.

Configuratie
Plaats je Mollie API key in `config.ini` in de repo root, sectie `[mollie]`:

```ini
[mollie]
APIkey=YOUR_MOLLIE_KEY
ProfileID=pfl_...
```

Gebruik (kort)
- Dry-run (geen echte POSTs):

```bash
# installeer afhankelijkheden (eenmalig)
.venv/bin/python -m pip install -r requirements.txt

# voer dry-run uit (geen echte Mollie-calls)
.venv/bin/python main.py --test --export export.csv
```

- Productierun (echte Mollie-calls; zorg voor correcte APIkey):

```bash
.venv/bin/python main.py --export export.csv
```

CLI opties
- `--test`, `-t`: dry-run mode; geen POSTs naar Mollie.
- `--config`, `-c`: pad naar config bestand (default `config.ini`).
- `--export`, `-e`: pad naar CSV exportbestand (default `export.csv`).
- `--skip-iban-validation`, `-s`: sla IBAN-check over (valideren kan fouten in exportbestand veroorzaken; logs zullen dan waarschuwen).

Subscription start-datum
- De script zet een abonnement (subscription) zo dat het begint op dezelfde dag-in-het-jaar als de originele machtiging (`Datum Ondertekening`).
  - Bijvoorbeeld: als `Datum Ondertekening` 06-01-2021 is en vandaag is 2026-01-19 dan de nieuwe subscription start op 2026-01-06 (of op 2027-01-06 als de datum dit jaar al gepasseerd was).
  - Voor Feb 29 als originele datum wordt in niet-schrikkeljaren 1 maart gebruikt als fallback.

Idempotency details
- Deterministische idempotency-keys (SHA-256) worden gegenereerd uit logische velden, zodat her-runs niet leiden tot duplicaten:
  - Customer: `customer|{email}`
  - Mandate: `mandate|{customer_id}|{MachtigingsID}`
  - Subscription: `subscription|{customer_id}|{amount:.2f}|{interval}|{startDate}` (opmerking: `startDate` is toegevoegd aan de key zodat subscriptions met verschillende startdata verschillend worden behandeld)

Foutafhandeling en retry
- Transient serverfouten (5xx) en 429 worden herhaald met exponentiële backoff (max 5 pogingen).
- Permanente 4xx fouten worden gelogd en gemarkeerd in het resultaatbestand als `failed`.

Tests
- De repo bevat pytest tests in de map `tests/`. Tests gebruiken dry-run mode en controleren CSV parsing, date logic en API wrapper behavior.

Test-run:

```bash
# vanuit projectroot, met de project venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

Debug en logging
- Logfile: `import.log` (RotatingFileHandler). Console-output toont WARNING en ERROR berichten.
- Voor debugging kun je `--test` gebruiken en `import.log` inspecteren voor details over payloads en idempotency-keys.

Aanpassingen/uitbreidingen
- Duplicate-detectie: momenteel wordt er een nieuwe customer aangemaakt op basis van idempotency; als je wilt dat we eerst op `customer_reference` of `Email` zoeken en hergebruiken, kan ik die pre-check toevoegen.
- Output: ipv een apart `imported_*.csv` kan ik de originele CSV uitbreiden met extra kolommen; laat weten wat je voorkeur heeft.

