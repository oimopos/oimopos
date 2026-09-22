\set ON_ERROR_STOP on

BEGIN;

DROP INDEX IF EXISTS auth_users_active_branch_manager_uq;

ALTER TABLE auth_users DROP CONSTRAINT IF EXISTS auth_users_staff_role_check;
ALTER TABLE auth_users
  ADD CONSTRAINT auth_users_staff_role_check CHECK (
    (role = 'platform_owner' AND staff_role = 'platform_owner')
    OR (role = 'owner' AND staff_role = 'company_admin')
    OR (role = 'branch' AND staff_role IN (
      'branch_manager', 'hall_admin', 'waiter', 'storekeeper',
      'production', 'marketer', 'cashier', 'pos_terminal'
    ))
  );

CREATE INDEX IF NOT EXISTS auth_users_tenant_staff_role_idx
  ON auth_users (tenant_id, staff_role, is_active);

INSERT INTO schema_migrations (version)
VALUES ('010_poster_access_model')
ON CONFLICT (version) DO NOTHING;

COMMIT;
