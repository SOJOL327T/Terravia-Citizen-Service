# TerraVia Citizen Service — Security Model V1

## Security goals
Confidentiality, integrity, availability, provenance, non-repudiation where appropriate, least privilege and citizen visibility.

## Controls
- MFA for sensitive operations.
- Device/session management and revocation.
- RBAC + ABAC.
- Purpose binding.
- Minimum disclosure.
- Encryption in transit and at rest.
- Key rotation and managed secrets.
- Secure backups.
- Rate limiting and abuse prevention.
- CSRF/XSS/SQLi/SSRF defenses.
- Dependency and supply-chain scanning.
- Security headers and secure cookies.
- Secure file scanning and content-type validation.

## High-risk controls
Break-glass access requires reason, scope, time limit, elevated authorization, immutable audit and post-event review.

## STOP ALL AUTOMATION
A global kill switch blocks automated actions and external transfers. Read-only inspection and safety operations remain available according to policy.

## Account recovery
Recovery must use strong multi-factor proof. Recovery must not silently change authoritative identity attributes. Device loss triggers session/token revocation.

## Privacy
Private by default. Family relationship does not imply visibility. Data requests expose only minimum required fields.

## Audit
Audit security-sensitive reads, writes, exports, sharing, policy decisions, consent changes, role changes, break-glass events and recovery events.
