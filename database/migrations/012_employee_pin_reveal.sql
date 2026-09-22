BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS pin_encrypted bytea;
INSERT INTO schema_migrations(version) VALUES ('012_employee_pin_reveal') ON CONFLICT DO NOTHING;
COMMIT;
