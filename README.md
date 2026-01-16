# Mollie SEPA Importer

Dit project importeert ledengegevens uit een CSV-export en maakt via de Mollie API:
- Mollie customers (via `POST /v2/customers`)
- SEPA-machtigingsrecords (mandates) via `POST /v2/customers/{customerId}/mandates` (import zonder hertekenen)
- Jaarlijkse subscriptions via `POST /v2/customers/{customerId}/subscriptions`

Belangrijke kenmerken
- Leest Nederlandse exportbestanden (semicolon-delimited) met Nederlandse kolomnamen.
- Valideert IBANs met `python-stdnum`.
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
- `IBAN` (IBAN, wordt gevalideerd)
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

Gedetailleerd gedrag
- IBAN: gevalideerd met `python-stdnum`; rijen met ongeldige IBAN worden overgeslagen.
- Datum: ondersteunt `DD-MM-YYYY`, `DD-MM-YY` en `YYYY-MM-DD` voor `Datum Ondertekening`.
- Bedrag: ondersteunt komma als decimaal scheidingsteken en wordt genormaliseerd naar een float.
- Idempotency: keys zijn SHA-256 hashes over logische velden:
  - Customer: `customer|{email}`
  - Mandate: `mandate|{customer_id}|{MachtigingsID}`
  - Subscription: `subscription|{customer_id}|{amount:.2f}|{interval}`

Foutafhandeling en retry
- Transient serverfouten (5xx) en 429 worden herhaald met exponentiële backoff (max 5 pogingen).
- Permanente 4xx fouten worden gelogd en gemarkeerd in het resultaatbestand als `failed`.

Tests
- De repo bevat pytest tests in de map `tests/`. Tests gebruiken dry-run mode en controleren CSV parsing en output.

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

Contact
Als je wilt dat ik veldmappingen verander (bijv. als jouw export andere Nederlandse header-namen gebruikt), geef de exacte headers en ik pas de mapper in `main.py` en `csv_reader.py` aan.

---
README bijgewerkt om overeen te komen met de Nederlandse export-velden en de huidige implementatie.
