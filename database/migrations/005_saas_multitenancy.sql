\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'archived')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS tenants_slug_uq ON tenants (lower(slug));

INSERT INTO tenants (id, slug, name, status)
VALUES ('tenant-ashkana', 'ashkana', 'Ашкана', 'active')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS tenant_subscriptions (
  tenant_id TEXT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
  plan_code TEXT NOT NULL DEFAULT 'starter',
  status TEXT NOT NULL DEFAULT 'trialing' CHECK (status IN ('trialing', 'active', 'past_due', 'canceled')),
  max_branches INTEGER NOT NULL DEFAULT 3 CHECK (max_branches > 0),
  trial_ends_at TIMESTAMPTZ,
  current_period_ends_at TIMESTAMPTZ,
  external_customer_id TEXT,
  external_subscription_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tenant_subscriptions (tenant_id, plan_code, status, max_branches)
VALUES ('tenant-ashkana', 'business', 'active', 50)
ON CONFLICT (tenant_id) DO NOTHING;

ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id);
UPDATE auth_users
SET tenant_id = 'tenant-ashkana'
WHERE tenant_id IS NULL AND role IN ('owner', 'branch');
ALTER TABLE auth_users DROP CONSTRAINT IF EXISTS auth_users_role_check;
ALTER TABLE auth_users DROP CONSTRAINT IF EXISTS auth_users_check;
ALTER TABLE auth_users
  ADD CONSTRAINT auth_users_role_check CHECK (role IN ('platform_owner', 'owner', 'branch')),
  ADD CONSTRAINT auth_users_scope_check CHECK (
    (role = 'platform_owner' AND tenant_id IS NULL AND branch_id IS NULL)
    OR (role = 'owner' AND tenant_id IS NOT NULL AND branch_id IS NULL)
    OR (role = 'branch' AND tenant_id IS NOT NULL AND branch_id IS NOT NULL)
  );

DROP INDEX IF EXISTS auth_users_active_branch_uq;
CREATE UNIQUE INDEX auth_users_active_branch_uq
  ON auth_users (tenant_id, branch_id)
  WHERE role = 'branch' AND is_active;
CREATE INDEX IF NOT EXISTS auth_users_tenant_idx ON auth_users (tenant_id, role, is_active);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'operational_state' AND column_name = 'id'
  ) THEN
    CREATE TABLE operational_state_saas (
      tenant_id TEXT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
      version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0),
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    INSERT INTO operational_state_saas (tenant_id, version, payload, updated_at)
    SELECT 'tenant-ashkana', version, payload, updated_at
    FROM operational_state
    ON CONFLICT (tenant_id) DO NOTHING;

    DROP TABLE operational_state;
    ALTER TABLE operational_state_saas RENAME TO operational_state;
  END IF;
END
$$;

ALTER TABLE operational_events ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id);
UPDATE operational_events SET tenant_id = 'tenant-ashkana' WHERE tenant_id IS NULL;
ALTER TABLE operational_events ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS operational_events_tenant_created_idx
  ON operational_events (tenant_id, created_at DESC);

ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id);
UPDATE catalog_items SET tenant_id = 'tenant-ashkana' WHERE tenant_id IS NULL;
ALTER TABLE catalog_items ALTER COLUMN tenant_id SET NOT NULL;
DROP INDEX IF EXISTS catalog_items_name_type_uq;
CREATE UNIQUE INDEX catalog_items_tenant_name_type_uq
  ON catalog_items (tenant_id, lower(name), item_type)
  WHERE is_active;
CREATE INDEX IF NOT EXISTS catalog_items_tenant_idx ON catalog_items (tenant_id, item_type, is_active);

ALTER TABLE technical_cards ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id);
UPDATE technical_cards SET tenant_id = 'tenant-ashkana' WHERE tenant_id IS NULL;
ALTER TABLE technical_cards ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE technical_cards DROP CONSTRAINT IF EXISTS technical_cards_output_item_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS technical_cards_tenant_output_uq
  ON technical_cards (tenant_id, output_item_id);
CREATE INDEX IF NOT EXISTS technical_cards_tenant_idx ON technical_cards (tenant_id, id);

ALTER TABLE technical_card_components ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id);
UPDATE technical_card_components component
SET tenant_id = card.tenant_id
FROM technical_cards card
WHERE component.technical_card_id = card.id AND component.tenant_id IS NULL;
ALTER TABLE technical_card_components ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS technical_card_components_tenant_idx
  ON technical_card_components (tenant_id, technical_card_id);

ALTER TABLE technical_card_components DROP CONSTRAINT IF EXISTS technical_card_components_technical_card_id_fkey;
ALTER TABLE technical_card_components DROP CONSTRAINT IF EXISTS technical_card_components_component_item_id_fkey;
ALTER TABLE technical_card_components DROP CONSTRAINT IF EXISTS technical_card_components_tenant_card_fkey;
ALTER TABLE technical_card_components DROP CONSTRAINT IF EXISTS technical_card_components_tenant_item_fkey;
ALTER TABLE technical_cards DROP CONSTRAINT IF EXISTS technical_cards_output_item_id_fkey;
ALTER TABLE technical_cards DROP CONSTRAINT IF EXISTS technical_cards_tenant_output_fkey;
ALTER TABLE technical_cards DROP CONSTRAINT IF EXISTS technical_cards_tenant_id_id_key;
ALTER TABLE catalog_items DROP CONSTRAINT IF EXISTS catalog_items_pkey CASCADE;
ALTER TABLE catalog_items ADD CONSTRAINT catalog_items_pkey PRIMARY KEY (tenant_id, id);
ALTER TABLE technical_cards ADD CONSTRAINT technical_cards_tenant_id_id_key UNIQUE (tenant_id, id);
ALTER TABLE technical_cards
  ADD CONSTRAINT technical_cards_tenant_output_fkey
  FOREIGN KEY (tenant_id, output_item_id) REFERENCES catalog_items(tenant_id, id);
ALTER TABLE technical_card_components
  ADD CONSTRAINT technical_card_components_tenant_card_fkey
  FOREIGN KEY (tenant_id, technical_card_id) REFERENCES technical_cards(tenant_id, id) ON DELETE CASCADE;
ALTER TABLE technical_card_components
  ADD CONSTRAINT technical_card_components_tenant_item_fkey
  FOREIGN KEY (tenant_id, component_item_id) REFERENCES catalog_items(tenant_id, id);

CREATE OR REPLACE FUNCTION reject_technical_card_cycle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  output_item TEXT;
  card_tenant TEXT;
  cycle_exists BOOLEAN;
BEGIN
  SELECT output_item_id, tenant_id INTO output_item, card_tenant
  FROM technical_cards
  WHERE id = NEW.technical_card_id AND tenant_id = NEW.tenant_id;

  IF output_item IS NULL THEN
    RAISE EXCEPTION 'Technical card % does not exist for tenant %', NEW.technical_card_id, NEW.tenant_id
      USING ERRCODE = '23503';
  END IF;

  WITH RECURSIVE dependencies(item_id) AS (
    SELECT NEW.component_item_id
    UNION
    SELECT child.component_item_id
    FROM dependencies parent
    JOIN technical_cards nested_card
      ON nested_card.output_item_id = parent.item_id AND nested_card.tenant_id = card_tenant
    JOIN technical_card_components child
      ON child.technical_card_id = nested_card.id AND child.tenant_id = card_tenant
    WHERE child.id <> COALESCE(NEW.id, -1)
  )
  SELECT EXISTS (SELECT 1 FROM dependencies WHERE item_id = output_item)
  INTO cycle_exists;

  IF cycle_exists THEN
    RAISE EXCEPTION 'Technical card cycle detected for item %', output_item
      USING ERRCODE = '23514';
  END IF;

  RETURN NEW;
END;
$$;

ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id);
UPDATE audit_events SET tenant_id = 'tenant-ashkana' WHERE tenant_id IS NULL;
ALTER TABLE audit_events ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS audit_events_tenant_created_idx
  ON audit_events (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS platform_events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  actor_user_id BIGINT REFERENCES auth_users(id),
  actor_login TEXT NOT NULL,
  action TEXT NOT NULL,
  tenant_id TEXT REFERENCES tenants(id),
  payload JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS platform_events_created_idx ON platform_events (created_at DESC);
CREATE INDEX IF NOT EXISTS platform_events_tenant_idx ON platform_events (tenant_id, created_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('005_saas_multitenancy')
ON CONFLICT (version) DO NOTHING;

COMMIT;
