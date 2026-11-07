CREATE TABLE IF NOT EXISTS family_invitations (
  id TEXT PRIMARY KEY,
  network_id TEXT NOT NULL REFERENCES family_networks(id),
  inviter_account_id TEXT NOT NULL REFERENCES accounts(id),
  invitee_email TEXT NOT NULL COLLATE NOCASE,
  token_hash TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('PENDING','ACCEPTED','REVOKED','EXPIRED')),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  accepted_by_person_id TEXT REFERENCES persons(id)
);
