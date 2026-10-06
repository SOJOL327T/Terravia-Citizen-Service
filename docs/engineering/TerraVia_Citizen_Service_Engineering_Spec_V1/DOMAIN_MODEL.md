# TerraVia Citizen Service — Domain Model V1

## Core aggregates
### Person
`person_id, status, names, birth_information, contacts, addresses, created_at, updated_at, version`

### Credential
`credential_id, holder_person_id, type, issuer_org_id, external_identifier_ref, issued_at, expires_at, status, verification_status, source_reference`

### Claim
`claim_id, subject_type, subject_id, attribute, value_ref, valid_from, valid_to, status`

### Evidence
`evidence_id, claim_id, source_type, source_reference, captured_at, verification_method, assurance_level, evidence_status, hash`

### IdentityConflict
`conflict_id, person_id, attribute, conflicting_claims, state, opened_at, reviewer, resolution_reference`

### Consent
`consent_id, subject, requester, purpose, data_scope, legal_basis, granted_at, expires_at, status, revocation`

### DataRequest / Authorization / DataPackage / Transfer / TransferReceipt
These form the controlled data-exchange transaction.

### Organization
`organization_id, legal_name, registration_refs, status, verification_status, contact_points`

### Representative / OrganizationRole / Service / ServiceContract
Define who may request what from whom and under which purpose/terms.

### Application
`application_id, applicant, service_id, requirements, readiness_state, status, submission_reference`

### LifeEvent
`event_id, type, subject, evidence, state, occurred_at, impact_set, policy_result, actions`

## Family domain
FamilyNetwork, FamilyBranch, FamilyGroup, Relationship, RelationshipEvidence, FamilyEvent, FamilyCalendar, ArchiveItem, LivingMemory, FamilyResearchCase.

Relationship states: VERIFIED, MUTUALLY_CONFIRMED, FAMILY_REPORTED, HISTORICAL_UNCERTAIN, UNCONFIRMED, DISPUTED, PROPOSED, REVOKED/HISTORICAL.

## Legacy domain
LegacyVault, LegacyItem, Custodian, SuccessionRule, ReleaseTrigger, AccessPolicy.

## Community domain
Community, CommunityMembership, CivicIssue, VolunteerProfile.

## Cross-cutting
AuditEvent, SecurityEvent, PolicyDecision, Notification.

## Domain invariants
1. External identifier never becomes internal identity key.
2. A credential can be invalid/expired without deleting the person.
3. Evidence can support, contradict or leave a claim unresolved.
4. Relationships never grant access by themselves.
5. Consent is scoped and time-bound.
6. Every sensitive transfer has an auditable decision.
7. AI inference is never authoritative without an approved evidence workflow.
8. Family claims cannot silently overwrite official claims.
9. Historical states are preserved; destructive updates are prohibited for regulated records.
10. Death is never inferred from inactivity.
