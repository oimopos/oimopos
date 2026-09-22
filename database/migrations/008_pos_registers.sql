\set ON_ERROR_STOP on

BEGIN;

DROP INDEX IF EXISTS auth_users_active_pos_terminal_uq;

UPDATE auth_users
SET display_name = 'Основная касса', updated_at = CURRENT_TIMESTAMP
WHERE role = 'branch' AND staff_role = 'pos_terminal';

CREATE UNIQUE INDEX auth_users_active_pos_register_name_uq
  ON auth_users (tenant_id, branch_id, lower(display_name))
  WHERE role = 'branch' AND staff_role = 'pos_terminal' AND is_active;

ALTER TABLE auth_sessions
  ADD COLUMN IF NOT EXISTS user_agent TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS remote_address TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS pos_shifts (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  register_user_id BIGINT NOT NULL REFERENCES auth_users(id),
  branch_id TEXT NOT NULL,
  opened_by_user_id BIGINT NOT NULL REFERENCES auth_users(id),
  opening_cash NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (opening_cash >= 0),
  opened_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  closed_by_user_id BIGINT REFERENCES auth_users(id),
  closing_cash NUMERIC(14, 2),
  expected_cash NUMERIC(14, 2),
  variance NUMERIC(14, 2),
  closed_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS pos_shifts_active_register_uq
  ON pos_shifts (register_user_id)
  WHERE closed_at IS NULL;
CREATE INDEX IF NOT EXISTS pos_shifts_tenant_branch_idx
  ON pos_shifts (tenant_id, branch_id, opened_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('008_pos_registers')
ON CONFLICT (version) DO NOTHING;

COMMIT;
