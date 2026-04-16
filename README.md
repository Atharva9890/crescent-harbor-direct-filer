# Crescent Harbor Direct Filer

Production-shaped implementation of the Crescent Harbor customs manifest filer case study. The repo builds manifests from scenario fixtures, validates them against the provided schema and business rules, signs submissions with HMAC-SHA256, transmits them to the mock Authority endpoint, polls for acknowledgments, and writes a grader-compatible `results.json`.

## What’s Included

- `direct_filer/` — manifest builder, schema validator, rules engine, Authority client, and scenario runner
- `run.sh` — one-command entrypoint for single-scenario or full-suite runs
- `results.json` — most recent run output in the required Format B
- `RUNNING.md` — exact commands to start the mock and run the filer
- `ARCHITECTURE.md` — design choices, ambiguity decisions, and next-step scaling plan
- `THREAT_MODEL.md` — security and audit posture for the implementation
- `CASE_STUDY_BRIEF.md` — the original assignment brief preserved for reference

## Quick Start

1. Start the mock Authority in one terminal:

```bash
cd mock-customs
python3 -m pip install -r requirements.txt
CUSTOMS_SCHEMA_PATH=../schema/manifest.schema.json \
CUSTOMS_SECRETS_PATH=./secrets.json \
python3 server.py
```

2. Run the full scenario suite from the repo root in another terminal:

```bash
./run.sh
```

3. Inspect `results.json`.

Expected outcome profile:

- `01-aurora-borealis` through `06-northern-lights`: `accepted`
- `07-tempest`: `rejected_by_rules`
- `08-polaris`: `rejected_by_schema`

## Implementation Summary

The pipeline has four explicit stages:

1. Manifest construction
2. JSON Schema validation
3. Business-rule evaluation
4. HMAC-signed submission plus acknowledgment polling

The rules layer is data-driven off `rules/rules.json`, with custom evaluators only for cross-field checks that cannot be expressed through the generic rule types.

## Project Structure

```text
.
├── direct_filer/
├── mock-customs/
├── rules/
├── scenarios/
├── schema/
├── spec/
├── ARCHITECTURE.md
├── CASE_STUDY_BRIEF.md
├── RUNNING.md
├── THREAT_MODEL.md
├── results.json
└── run.sh
```

## Notes

- The mock Authority intentionally enforces schema only; business-rule rejections are handled client-side in this repo per the packet requirements.
- `manifestId` values are generated deterministically from the scenario ID and computed ETA, so reruns stay within the required format while avoiding filename hardcoding for failure cases.
- Hazmat presence surfaces warnings without blocking submission, matching the specification.
