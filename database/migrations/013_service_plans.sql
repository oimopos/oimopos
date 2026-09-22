BEGIN;
CREATE TABLE platform_plans (
 code TEXT PRIMARY KEY CHECK (code IN ('canteen', 'restaurant')),
 name TEXT NOT NULL,
 monthly_price NUMERIC(12,2) NOT NULL CHECK (monthly_price >= 0),
 currency TEXT NOT NULL DEFAULT 'KGS' CHECK (currency = 'KGS'),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO platform_plans(code,name,monthly_price) VALUES ('canteen','Столовая',2000),('restaurant','Ресторан',3500);
INSERT INTO schema_migrations(version) VALUES ('013_service_plans');
COMMIT;
