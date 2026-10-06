# TerraVia Citizen Service — System Boundaries V1

## TerraVia owns
- Person identity orchestration
- Credential references and verification state
- Evidence graph
- Identity conflict workflow
- Consent and authorization
- Policy decisions
- Service readiness
- Application preparation
- Adapter orchestration
- Transfer receipts
- Audit and security events
- Family heritage data supplied/controlled by users
- AI assistance under policy

## External authorities own
- Birth/death registry records
- NID records
- Passport authority records
- University authoritative records
- Professional licensing records
- Employer authoritative employment records
- Other legal/regulatory source records

## TerraVia must not
- Replace authoritative registries
- Decide legal citizenship independently
- silently merge people
- infer death
- become a universal document wallet competitor
- operate a generic social network
- create citizen scores
- continuously track location
- autonomously submit high-impact applications

## Integration boundary
External systems communicate through adapters. Adapters translate external schemas into canonical TerraVia contracts and never directly mutate domain state without validation, policy and audit.

## Family boundary
Official identity and Family/Bongsho are separate worlds connected through controlled references.
