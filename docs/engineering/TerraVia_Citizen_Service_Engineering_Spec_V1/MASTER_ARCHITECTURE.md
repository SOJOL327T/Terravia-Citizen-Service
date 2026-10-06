# TerraVia Citizen Service — Master Architecture V1

## 1. Purpose
TerraVia Citizen Service is a citizen-controlled identity, interoperability and life-management platform. It orchestrates verified credentials, evidence, consent, policy-controlled data exchange, service readiness, life events, family heritage and legacy while external authorities retain ownership of authoritative records.

## 2. Non-negotiable boundaries
- TerraVia Person ID is not NID or another government identifier.
- External authorities remain source of truth for authoritative records.
- Person, Credential, Evidence, Relationship, Family, Organization, Application, Consent and Audit are separate domains.
- Family/Bongsho Dhara is a human-controlled heritage domain, not official identity truth.
- AI cannot create authoritative facts by inference.
- No automatic identity merge, citizenship determination, death inference or autonomous high-impact submission.
- STOP ALL AUTOMATION is a platform emergency control.

## 3. Logical architecture
```text
Clients / Mobile / Web / Partner Services
                |
        API & Session Gateway
                |
      Identity & Access Control
                |
       Policy / Consent Engine
                |
   +------------+-------------+
   |            |             |
Identity     Evidence      Credentials
   |            |             |
   +------------+-------------+
                |
      Interoperability Core
                |
       Service Adapter Layer
                |
 Government / Education / Employers / Professional Bodies / Businesses

Parallel controlled domains:
Family/Bongsho -> Calendar -> Archive -> Living Memory -> Legacy
Applications -> Readiness -> Transfer -> Receipt -> Audit
Life Events -> Evidence -> Impact Analysis -> Policy -> Action
AI -> Explain/Prepare/Recommend -> Policy -> Authorized Action

Cross-cutting: Security, Privacy, Audit, Disaster Recovery, Observability
```

## 4. Architectural style
Modular domain-oriented service architecture with a canonical internal model, explicit policy decisions, append-oriented audit events, replaceable external adapters and fail-closed security controls. Initial deployment may be a modular monolith; domain boundaries must be preserved so services can later be separated without redesigning the domain model.

## 5. Trust model
Every important datum has provenance, assurance and lifecycle state. TerraVia stores references to authoritative sources rather than pretending to become the authority. Conflicts are cases, not silent overwrites.

## 6. Transaction pattern
Request -> authenticate -> identify requester -> purpose/legal basis -> policy -> consent where required -> retrieve/verify source -> minimum-data package -> user/authority confirmation -> transfer -> receipt -> audit.

## 7. Automation model
AUTO, MANUAL, ASSISTANCE_ONLY and STOPPED. High-impact actions default to MANUAL or ASSISTANCE_ONLY. STOPPED blocks automation globally.

## 8. Deployment principles
- API-first.
- Encryption in transit and at rest.
- MFA and device/session controls.
- Tenant/organization isolation.
- Fine-grained authorization.
- Immutable/append-only audit design.
- Backups and disaster recovery.
- Data portability/export.
- Versioned schemas and adapters.
- Idempotent external operations.
- Explicit retention/deletion policy.

## 9. Build order
P0: Person, Credential, Evidence, Consent, Policy, Transfer, Audit, Security.
P1: Application, Service Readiness, Adapter Framework, AI Assistant, Identity Conflict.
P2: Bongsho Dhara, Calendar, Archive, Living Memory.
P3: Organization Identity and trusted-service integrations.
P4: Legacy, Succession and Civic Network.
