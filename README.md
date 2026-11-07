# TerraVia Citizen Service

TerraVia is a citizen-controlled identity and service-readiness application. It keeps TerraVia Person IDs separate from external identifiers, preserves claims with provenance, routes conflicting claims to review, and requires scoped consent before a clearly labeled mock adapter can transfer data.

## Repository baseline

The implementation branch started at `6ae242b` (`chore: add Citizen Service engineering specification`). The repository initially contained the implementation prompt, the 22 V1 engineering specification documents and this README, with no application source, dependency manifest or tests. The existing test-suite baseline was therefore **not available**. Implementation is being built as a Python/FastAPI modular monolith with SQLite, following the accepted modular-monolith decision in `DECISION_REGISTER.md`.

The approved engineering specifications remain under `docs/engineering/TerraVia_Citizen_Service_Engineering_Spec_V1/`.

## Run locally

Requirements: Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
$env:TERRAVIA_DATABASE = "$PWD\var\terravia.sqlite3"
$env:TERRAVIA_CONTROL_KEY = (python -c "import secrets; print(secrets.token_urlsafe(48))")
$env:TERRAVIA_COOKIE_SECURE = "false" # local HTTP only; set true behind HTTPS
python -m uvicorn terravia.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The first citizen account is created through the registration flow. There is no seeded citizen identity or default password. The platform control key is needed to resume outbound transfers; STOP ALL AUTOMATION is active on first startup. Keep the key outside source control.

The API is versioned at `/v1`. FastAPI's interactive schema is available at `/docs` for local development. Runtime data defaults to `var/terravia.sqlite3`, excluded from Git. Versioned SQL files under `terravia/migrations/` are applied once and recorded in `schema_migrations`.

## Implemented workflows

- Citizen account registration and sign-in with salted PBKDF2 password hashes, opaque server-side sessions, HttpOnly session cookies, same-site cookies and double-submit CSRF checks.
- TerraVia Person ID creation distinct from NID and other external IDs.
- Separate claims, credentials and evidence. Citizen entered values remain `UNVERIFIED`; credentials are references and do not replace issuer records.
- Conflicting values create an explicit conflict case. Review does not merge claims or select an authoritative value.
- A seeded reference service catalog and readiness calculation.
- Data requests bound to the service's registered organization and minimum field contract. Policy can deny or require citizen review.
- Field-scoped, purpose-bound, time-limited consent with revocation. Transfer requires active consent, a valid request, an idempotency key and a resumed global control.
- A mock adapter only. Receipts state `MOCK`; no live government or organization integration is configured.
- Append-only, hash-chained audit events and private activity history.
- Private family networks, provenance/evidence labels, relationship notes, events, archive items and living-memory records. Family relationships do not grant access.
- Proposed life events and impact recommendations without automatic changes to other domains.
- Private legacy vault entries with explicit trigger metadata. No release mechanism is exposed, and inactivity is never a trigger.
- Optional Ollama explanation endpoint. It sends only coarse workflow counts, is unavailable unless a model is configured, and cannot call mutation endpoints.

## Tests

Run the automated tests with:

```powershell
python -m pytest
```

Tests use temporary SQLite databases. They exercise identity conflict handling, consent minimization, the stop control, mock transfer receipts and idempotency, revocation, family privacy, life-event non-cascade behavior, legacy safeguards and audit append-only enforcement.

## Current security and readiness limits

This is a development implementation, not a production citizen-data system. SQLite is not encrypted at rest. MFA, device/session management, independent reviewer roles, verified credential-source adapters, organization onboarding and key rotation are not implemented. Login rate limiting is process-local. Backup/restore and disaster recovery are not implemented. The mock transfer records the package locally; it does not transmit to an external organization. Legacy releases are deliberately unavailable pending a two-party authorization workflow. Do not enter real sensitive citizen information or expose this service to the public internet.

These limits are explicit so a development build is not mistaken for a verified production integration. Before any real data or production deployment, add managed encryption/key handling, MFA and recovery, durable distributed rate limits, reviewer authorization, independent security review, backup/restore, and certified adapters. Update the relevant architecture decisions before changing domain meaning.
