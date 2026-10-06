# TerraVia Citizen Service — Consent Specification V1

## Consent object
Subject, requester, purpose, data scope, legal basis, granted_at, expires_at, status, revocation state, presentation text/version, policy decision reference.

## Consent states
DRAFT -> PRESENTED -> GRANTED -> ACTIVE -> EXPIRED / REVOKED / SUPERSEDED / DENIED.

## UX requirements
Before approval show:
1. Who is asking?
2. Why?
3. Exactly what data?
4. For how long?
5. What happens next?
6. Can it be revoked?

## Rules
- No bundled unrelated purposes.
- Use field-level scope for high-sensitivity fields.
- Default expiry should be conservative.
- Recurring access requires explicit recurring authorization.
- Consent is not a substitute for legal basis where law permits/requires another basis.
- Withdrawal stops future processing where technically and legally feasible; it cannot retroactively erase lawful prior transfers.

## Audit
Record presentation version, user decision, timestamp, authentication context, requested scope, granted scope, policy outcome and revocation.
