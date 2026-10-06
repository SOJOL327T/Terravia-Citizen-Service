# TerraVia Citizen Service — Audit Model V1

## Audit every
Authentication/security events; identity changes; credential verification; evidence changes; conflict decisions; consent presentation/grant/revoke; policy decisions; data requests; transfers; application submissions; role changes; family governance actions; legacy releases; break-glass use; recovery operations.

## Audit event
`audit_id, timestamp, actor, actor_type, action, object_type, object_id, purpose, policy_decision_id, result, source, correlation_id, device/session_ref, before_hash, after_hash`

## Requirements
- Append-only design.
- Tamper evidence.
- Clock synchronization.
- Restricted audit access.
- Export for authorized investigations.
- Retention according to legal/product policy.

## User transparency
Citizen-facing activity history should explain what happened in human-readable form while privileged audit retains required technical detail.
