# Architecture

## What I built

The repository contains a small Python 3.12 CLI with four explicit stages: manifest construction, JSON Schema validation, business-rule evaluation, and signed transport to the Authority. The implementation stays close to the specification artifacts in this packet rather than inventing a large internal framework.

`direct_filer/builder.py` enriches each scenario with filer-owned fields: `manifestId`, `filer`, `arrival.eta`, and `filerSignature`. It treats scenario files as source-of-truth for cargo, crew, and declared totals, so bad source data is preserved and rejected at the right layer instead of being silently normalized away.

`direct_filer/schema_validation.py` compiles the provided Draft 2020-12 schema once and returns structured validation issues with JSON-pointer-like paths and mapped rejection codes. `direct_filer/rules_engine.py` loads `rules/rules.json` and evaluates the 25 rules through a small rule dispatcher instead of baking them into one procedural function. Simple rule types (`regex`, `minValue`, `maxValue`, `minItems`, `notEquals`) are generic; cross-field checks are implemented as named custom checks keyed off the machine-readable rule definitions.

`direct_filer/client.py` implements the Authority protocol exactly as specified: canonical body hashing, HMAC-SHA256 signing, `POST /v3/manifests`, and polling `GET /v3/acks/{receiptId}` until a terminal acknowledgment arrives or the timeout is exceeded. `direct_filer/runner.py` coordinates the full pipeline and writes `results.json` in the grader-compatible Format B.

## Ambiguity decisions

For R-005 vessel name normalization, I followed the language in §4.1 that says lowercase vessel names “shall be uppercased by the filer prior to submission.” The builder therefore uppercases the vessel name before validation and transmission. I did not treat lowercase source input as a reject on its own because the spec gives the filer an explicit normalization action.

For R-014 hazmat gross weight proportion, I used best-effort enforcement and normalized `grossWeightKg` into tons before comparing it to vessel gross register tons. The schema does not require `grossWeightKg` for `HAZ` containers, so rejecting manifests when that field is absent would introduce a hidden mandatory field not present in the schema or base container definition. The engine therefore enforces the 25% cap only when every hazmat container carries a weight. With a real upstream system, I would make the unit contract explicit with the regulator instead of inferring it.

For R-023 filing clock authority, I treat the client transmit time as the effective filing time. That is the only clock available before transmission, which matters because this filer is required to block too-early and too-late submissions before they reach the Authority. In a production integration I would record both the client send timestamp and the Authority receipt timestamp for audit and dispute handling.

For amendment rules R-024 and R-025, this case-study implementation assumes no persistence layer and therefore no authoritative history of prior accepted manifests. The runner rejects any manifest carrying `amendmentSequence` with an explicit message explaining that original-manifest state is unavailable. With persistence, amendments would be validated against stored originals and prior sequences.

## What I cut and what I would build next

I did not add a database, retry queue, CLI subcommands for every operation, or a richer observability stack because they are unnecessary to satisfy the packet and would mostly add scaffolding. I also kept the HTTP client on the Python standard library instead of adding a heavier dependency for two endpoints and a simple signing scheme.

To scale from one filer to multiple document types across regulators, I would separate “document assembly,” “policy/rule packs,” and “transport adapters” into first-class modules. Each regulator would get its own schema set, rule pack, signing strategy, and endpoint adapter, while sharing common concerns like scenario ingestion, audit logging, retries, and secrets access. I would also store outbound payloads, receipts, acknowledgments, and rule decisions in an append-only filing ledger so amendments, replay protection, and operational analytics have a durable source of truth.

With more time, I would add unit tests around each ambiguous rule, contract tests for the HMAC canonical string, integration tests that boot the mock automatically, and a persistent manifest repository for duplicate and amendment handling. I would also formalize the rule DSL further so more cross-field validations can be expressed declaratively instead of through named Python functions.
