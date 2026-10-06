# TerraVia Citizen Service — API Specification V1

## API principles
REST/JSON for broad interoperability, versioned endpoints, idempotency keys for writes, correlation IDs, pagination, optimistic concurrency and structured errors. Support standards-based credential exchange where applicable.

## Core resources
`/v1/persons`
`/v1/credentials`
`/v1/evidence`
`/v1/conflicts`
`/v1/organizations`
`/v1/services`
`/v1/applications`
`/v1/requirements`
`/v1/data-requests`
`/v1/consents`
`/v1/authorizations`
`/v1/data-packages`
`/v1/transfers`
`/v1/life-events`
`/v1/family`
`/v1/archive`
`/v1/living-memory`
`/v1/legacy`
`/v1/audit`
`/v1/notifications`

## Example transaction
POST `/v1/data-requests`
-> requester, subject, purpose, legal_basis, requested_fields, service_contract_id, expiry.

POST `/v1/data-requests/{id}/decision`
-> ALLOW | REVIEW | DENY with policy decision reference.

POST `/v1/consents`
-> scoped consent.

POST `/v1/transfers`
-> approved request + consent/authorization + package reference + idempotency key.

GET `/v1/transfers/{id}/receipt`
-> recipient, fields, purpose, time, source references, policy decision.

## Error model
`code, message, category, retryable, field_errors, correlation_id, policy_reference`.

Categories: VALIDATION, AUTHENTICATION, AUTHORIZATION, CONSENT_REQUIRED, POLICY_DENIED, SOURCE_UNAVAILABLE, CONFLICT, RATE_LIMITED, INTERNAL.

## Security
OAuth2/OIDC or equivalent strong authentication, MFA for sensitive actions, scoped access tokens, sender/recipient authorization, signed requests where required, replay protection and audit correlation.
