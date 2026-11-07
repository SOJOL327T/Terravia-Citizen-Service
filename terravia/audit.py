from __future__ import annotations

import hashlib
import json
from .security import identifier, iso

def record(conn, *, actor: str, action: str, object_type: str, object_id: str | None = None,
           purpose: str | None = None, policy_decision_id: str | None = None,
           result: str = "SUCCESS", correlation_id: str = "", before: object = None,
           after: object = None) -> str:
    previous = conn.execute("SELECT event_hash FROM audit_events ORDER BY rowid DESC LIMIT 1").fetchone()
    previous_hash = previous["event_hash"] if previous else "0" * 64
    event_id, timestamp = identifier(), iso()
    before_hash = hashlib.sha256(json.dumps(before, sort_keys=True, default=str).encode()).hexdigest() if before is not None else None
    after_hash = hashlib.sha256(json.dumps(after, sort_keys=True, default=str).encode()).hexdigest() if after is not None else None
    payload = {"id": event_id, "timestamp": timestamp, "actor": actor, "action": action,
        "object_type": object_type, "object_id": object_id, "purpose": purpose,
        "policy_decision_id": policy_decision_id, "result": result, "correlation_id": correlation_id,
        "before_hash": before_hash, "after_hash": after_hash, "previous_hash": previous_hash}
    event_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    conn.execute("""INSERT INTO audit_events(id,timestamp,actor,action,object_type,object_id,purpose,
        policy_decision_id,result,correlation_id,before_hash,after_hash,previous_hash,event_hash)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (*payload.values(), event_hash))
    return event_id
