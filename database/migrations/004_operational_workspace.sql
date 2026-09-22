\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS auth_users (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  login TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('owner', 'branch')),
  branch_id TEXT,
  display_name TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  account_version INTEGER NOT NULL DEFAULT 1 CHECK (account_version > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK ((role = 'owner' AND branch_id IS NULL) OR (role = 'branch' AND branch_id IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS auth_users_login_uq
  ON auth_users (lower(login));

CREATE UNIQUE INDEX IF NOT EXISTS auth_users_active_branch_uq
  ON auth_users (branch_id)
  WHERE role = 'branch' AND is_active;

CREATE TABLE IF NOT EXISTS auth_sessions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
  token_hash CHAR(64) NOT NULL UNIQUE,
  account_version INTEGER NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS auth_sessions_user_idx
  ON auth_sessions (user_id, expires_at DESC);

CREATE TABLE IF NOT EXISTS operational_state (
  id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0),
  payload JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operational_events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  state_version BIGINT NOT NULL,
  actor_user_id BIGINT REFERENCES auth_users(id),
  actor_login TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  branch_id TEXT,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  payload JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS operational_events_created_idx
  ON operational_events (created_at DESC);

CREATE INDEX IF NOT EXISTS operational_events_branch_idx
  ON operational_events (branch_id, created_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('004_operational_workspace')
ON CONFLICT (version) DO NOTHING;

COMMIT;
