# TerraVia Citizen Service — Test Strategy V1

## Test layers
Unit -> domain -> policy -> API contract -> integration -> security -> privacy -> UI workflow -> end-to-end -> disaster recovery.

## Mandatory invariant tests
- External ID != internal person ID.
- No automatic merge.
- No automatic death inference.
- No unauthorized transfer.
- Consent expiry blocks future use.
- Revocation blocks future use where applicable.
- Relationship does not grant private access.
- Family claims do not overwrite official claims.
- AI suggestions cannot become authoritative without workflow.
- STOP ALL AUTOMATION blocks automated actions.

## Property tests
Test idempotency, concurrency, replay protection, schema compatibility, policy monotonicity and data minimization.

## Security tests
Authorization matrix, privilege escalation, session fixation, token replay, injection, file upload, API abuse, rate limits, audit integrity and recovery.

## Integration tests
Each adapter must run contract, positive, negative, timeout, retry, duplicate and source-conflict scenarios.

## Disaster tests
Backup restore, key recovery, partial outage, adapter outage, database corruption, audit recovery and legacy-release interruption.
