# Running

## 1. Start the mock Authority endpoint

Docker:

```bash
cd mock-customs
docker compose up --build
```

Without Docker:

```bash
python3 -m pip install -r requirements.txt
CUSTOMS_SCHEMA_PATH=../schema/manifest.schema.json \
CUSTOMS_SECRETS_PATH=./secrets.json \
python3 server.py
```

The mock listens on `http://localhost:8080`.

## 2. Run a single scenario for debugging

From the repository root:

```bash
./run.sh --scenario scenarios/01-aurora-borealis.json --output single-result.json
```

## 3. Run all 8 scenarios and produce the report

From the repository root:

```bash
./run.sh
```

This writes `results.json` in the repo root.

## Configuration

Optional environment variables:

- `CRESCENT_AUTHORITY_BASE_URL` overrides the Authority base URL.
- `CRESCENT_SECRET_PATH` overrides the path to `secrets.json`.
- `CRESCENT_FILER_ID` overrides the filer ID.
- `CRESCENT_SIGNER_NAME`, `CRESCENT_SIGNER_TITLE`, `CRESCENT_LEGAL_NAME`, and `CRESCENT_CONTACT_EMAIL` override filer metadata.
