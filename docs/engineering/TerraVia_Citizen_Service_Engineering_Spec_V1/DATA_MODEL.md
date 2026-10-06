# TerraVia Citizen Service — Data Model V1

## Identifier rules
Use opaque UUID/ULID-style internal identifiers. External IDs are namespaced by issuer and credential type. Never expose internal IDs as public identity numbers when avoidable.

## Common record metadata
Every mutable domain object should support:
`id, schema_version, created_at, created_by, updated_at, updated_by, status, version, provenance_ref`.

## Provenance
Claims and evidence require source, capture method, timestamp, assurance level and verification status. Store original artifact hashes where permitted.

## Data classification
L0 Public; L1 General; L2 Personal; L3 Sensitive; L4 Highly Sensitive.
Classification must propagate through packages, logs and downstream processing.

## Suggested relational boundaries
- identity_person
- identity_identifier
- credential
- claim
- evidence
- identity_conflict
- organization
- organization_role
- service
- service_contract
- application
- application_requirement
- consent
- authorization
- data_request
- data_package
- transfer
- transfer_receipt
- life_event
- relationship
- family_network
- family_branch
- family_group
- family_event
- archive_item
- living_memory
- family_research_case
- legacy_vault
- legacy_item
- custodian
- succession_rule
- community
- community_membership
- civic_issue
- audit_event
- security_event
- policy_decision
- notification

## Storage rule
Do not place all data into one citizen table. Keep domain ownership explicit and use references/foreign keys or stable event references between domains.

## Event history
Use domain events for important state transitions. Preserve prior state where audit/regulatory requirements apply.
