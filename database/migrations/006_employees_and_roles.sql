\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE auth_users
  ADD COLUMN IF NOT EXISTS staff_role TEXT,
  ADD COLUMN IF NOT EXISTS phone TEXT NOT NULL DEFAULT '';

UPDATE auth_users
SET staff_role = CASE role
  WHEN 'platform_owner' THEN 'platform_owner'
  WHEN 'owner' THEN 'company_admin'
  ELSE 'branch_manager'
END
WHERE staff_role IS NULL;

ALTER TABLE auth_users ALTER COLUMN staff_role SET NOT NULL;
ALTER TABLE auth_users DROP CONSTRAINT IF EXISTS auth_users_staff_role_check;
ALTER TABLE auth_users
  ADD CONSTRAINT auth_users_staff_role_check CHECK (
    (role = 'platform_owner' AND staff_role = 'platform_owner')
    OR (role = 'owner' AND staff_role = 'company_admin')
    OR (role = 'branch' AND staff_role IN ('branch_manager', 'storekeeper', 'production', 'cashier'))
  );

DROP INDEX IF EXISTS auth_users_active_branch_uq;
CREATE UNIQUE INDEX auth_users_active_branch_manager_uq
  ON auth_users (tenant_id, branch_id)
  WHERE role = 'branch' AND staff_role = 'branch_manager' AND is_active;
CREATE INDEX IF NOT EXISTS auth_users_tenant_branch_idx
  ON auth_users (tenant_id, branch_id, is_active);

INSERT INTO schema_migrations (version)
VALUES ('006_employees_and_roles')
ON CONFLICT (version) DO NOTHING;

COMMIT;
