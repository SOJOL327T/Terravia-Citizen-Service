from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "var" / "terravia.sqlite3"

def database_path() -> str:
    return os.environ.get("TERRAVIA_DATABASE", str(DEFAULT_DB))

def connect() -> sqlite3.Connection:
    path = database_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    return conn

@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize() -> None:
    conn = connect()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        migration_dir = Path(__file__).parent / "migrations"
        for migration in sorted(migration_dir.glob("[0-9][0-9][0-9]_*.sql")):
            version = int(migration.name.split("_", 1)[0])
            if conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,)).fetchone():
                continue
            sql = migration.read_text(encoding="utf-8")
            try:
                conn.executescript("BEGIN IMMEDIATE;\n" + sql + f"\nINSERT INTO schema_migrations(version,applied_at) VALUES({version},datetime('now'));\nCOMMIT;")
            except Exception:
                conn.rollback()
                raise
    finally:
        conn.close()

def rowdict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None
