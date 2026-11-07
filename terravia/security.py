from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

PBKDF2_ROUNDS = 390_000
SESSION_HOURS = 8

def now() -> datetime:
    return datetime.now(timezone.utc)

def iso(value: datetime | None = None) -> str:
    return (value or now()).isoformat(timespec="seconds")

def identifier() -> str:
    return secrets.token_hex(16)

def secret_token() -> str:
    return secrets.token_urlsafe(32)

def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    result = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${result.hex()}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def expiry(hours: int = SESSION_HOURS) -> str:
    return iso(now() + timedelta(hours=hours))

def safe_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())
