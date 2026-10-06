# TerraVia Citizen Service — Threat Model V1

## Primary threats
1. Account takeover
2. Identity theft / credential theft
3. Unauthorized data transfer
4. Consent abuse
5. Insider misuse
6. Adapter compromise
7. Malicious organization requester
8. AI prompt/data manipulation
9. Identity collision/false merge
10. Family privacy abuse
11. Legacy vault premature release
12. Data corruption/loss
13. Ransomware
14. Supply-chain compromise
15. Availability attack
16. Audit tampering

## Security responses
MFA, device trust, least privilege, purpose-bound access, signed/verified source responses, adapter isolation, policy engine, immutable audit, anomaly detection, rate limits, encrypted backups, key separation, approval workflows and STOP ALL AUTOMATION.

## Abuse cases
- Fake employer requests passport data -> policy/contract mismatch -> deny.
- Family member tries to access unrelated person's private data -> relationship alone insufficient -> deny.
- AI suggests merging two people -> candidate only -> human/evidence workflow.
- Stolen phone -> revoke sessions/device -> re-authentication.
- Malicious adapter response -> schema validation, source verification, quarantine.
- Death incorrectly reported -> evidence review; no legacy release until verified.

## Security testing
Threat modeling at design review, SAST, DAST, dependency scanning, API fuzzing, authorization matrix tests, privacy tests, red-team exercises and recovery drills.
