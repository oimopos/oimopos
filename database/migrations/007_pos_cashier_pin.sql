\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE auth_users
  ADD COLUMN IF NOT EXISTS pin_hash TEXT,
  ADD COLUMN IF NOT EXISTS pin_failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK (pin_failed_attempts >= 0),
  ADD COLUMN IF NOT EXISTS pin_locked_until TIMESTAMPTZ;

ALTER TABLE auth_users DROP CONSTRAINT IF EXISTS auth_users_staff_role_check;
UPDATE auth_users
SET staff_role = 'pos_terminal', display_name = 'Терминал точки'
WHERE role = 'branch' AND staff_role = 'branch_manager';
ALTER TABLE auth_users
  ADD CONSTRAINT auth_users_staff_role_check CHECK (
    (role = 'platform_owner' AND staff_role = 'platform_owner')
    OR (role = 'owner' AND staff_role = 'company_admin')
    OR (role = 'branch' AND staff_role IN ('pos_terminal', 'branch_manager', 'storekeeper', 'production', 'cashier'))
  );

DROP INDEX IF EXISTS auth_users_active_branch_manager_uq;
CREATE UNIQUE INDEX auth_users_active_pos_terminal_uq
  ON auth_users (tenant_id, branch_id)
  WHERE role = 'branch' AND staff_role = 'pos_terminal' AND is_active;
CREATE UNIQUE INDEX auth_users_active_branch_manager_uq
  ON auth_users (tenant_id, branch_id)
  WHERE role = 'branch' AND staff_role = 'branch_manager' AND is_active;

CREATE TABLE IF NOT EXISTS pos_operator_sessions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  token_hash CHAR(64) NOT NULL UNIQUE,
  terminal_session_id BIGINT NOT NULL REFERENCES auth_sessions(id) ON DELETE CASCADE,
  employee_user_id BIGINT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
  branch_id TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS pos_operator_sessions_terminal_idx
  ON pos_operator_sessions (terminal_session_id, expires_at DESC);
CREATE INDEX IF NOT EXISTS pos_operator_sessions_employee_idx
  ON pos_operator_sessions (employee_user_id, expires_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('007_pos_cashier_pin')
ON CONFLICT (version) DO NOTHING;

COMMIT;
