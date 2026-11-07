ALTER TABLE sessions ADD COLUMN session_id TEXT;
UPDATE sessions SET session_id=substr(token_hash,1,32) WHERE session_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_sessions_session_id ON sessions(session_id);
