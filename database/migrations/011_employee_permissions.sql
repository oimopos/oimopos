\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE auth_users
  ADD COLUMN IF NOT EXISTS access_permissions JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE auth_users
SET access_permissions = CASE staff_role
  WHEN 'branch_manager' THEN '{"posAccess":true,"posRefunds":true,"posCash":true,"posSupply":true,"reports":true,"menu":true,"inventory":true,"production":true,"finance":true,"employees":true,"registers":true,"settings":true}'::jsonb
  WHEN 'hall_admin' THEN '{"posAccess":true,"posRefunds":true,"posCash":true,"posSupply":false,"reports":false,"menu":false,"inventory":false,"production":false,"finance":false,"employees":false,"registers":false,"settings":false}'::jsonb
  WHEN 'waiter' THEN '{"posAccess":true,"posRefunds":false,"posCash":false,"posSupply":false,"reports":false,"menu":false,"inventory":false,"production":false,"finance":false,"employees":false,"registers":false,"settings":false}'::jsonb
  WHEN 'cashier' THEN '{"posAccess":true,"posRefunds":false,"posCash":true,"posSupply":false,"reports":false,"menu":false,"inventory":false,"production":false,"finance":false,"employees":false,"registers":false,"settings":false}'::jsonb
  WHEN 'storekeeper' THEN '{"posAccess":false,"posRefunds":false,"posCash":false,"posSupply":false,"reports":false,"menu":false,"inventory":true,"production":false,"finance":false,"employees":false,"registers":false,"settings":false}'::jsonb
  WHEN 'production' THEN '{"posAccess":false,"posRefunds":false,"posCash":false,"posSupply":false,"reports":false,"menu":false,"inventory":false,"production":true,"finance":false,"employees":false,"registers":false,"settings":false}'::jsonb
  WHEN 'marketer' THEN '{"posAccess":false,"posRefunds":false,"posCash":false,"posSupply":false,"reports":true,"menu":true,"inventory":false,"production":false,"finance":false,"employees":false,"registers":false,"settings":false}'::jsonb
  ELSE access_permissions
END
WHERE role = 'branch' AND staff_role <> 'pos_terminal' AND access_permissions = '{}'::jsonb;

INSERT INTO schema_migrations (version)
VALUES ('011_employee_permissions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
