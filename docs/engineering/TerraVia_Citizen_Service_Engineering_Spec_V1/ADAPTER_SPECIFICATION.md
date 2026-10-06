# TerraVia Citizen Service — Adapter Specification V1

## Adapter contract
Each adapter defines identity, authentication, capabilities, input/output schemas, field mapping, purpose, error model, version, security requirements and audit requirements.

## Supported integration modes
1. Official API
2. Standards-based credential exchange
3. QR/session handoff
4. Browser assistance as fallback only
5. Document package/manual route

## Adapter lifecycle
DRAFT -> TESTING -> CERTIFIED -> ACTIVE -> DEPRECATED -> RETIRED.

## Mandatory tests
- Contract test
- Authentication test
- Authorization test
- Schema mapping test
- Failure/retry test
- Idempotency test
- Security test
- Audit test
- Data-minimization test

## Failure handling
External failure must not create false verification. Distinguish unavailable, rejected, invalid, expired, conflicting and unknown.

## Versioning
Adapters and external schemas are independently versioned. A source schema change must fail safely and enter compatibility review rather than silently changing mappings.
