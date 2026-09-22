\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalog_items (
  id TEXT PRIMARY KEY,
  item_type TEXT NOT NULL CHECK (item_type IN ('ingredient', 'preparation', 'product')),
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  unit TEXT NOT NULL CHECK (length(btrim(unit)) > 0),
  purchase_cost NUMERIC(14, 4) NOT NULL DEFAULT 0 CHECK (purchase_cost >= 0),
  sale_price NUMERIC(14, 2) CHECK (sale_price IS NULL OR sale_price >= 0),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS catalog_items_name_type_uq
  ON catalog_items (lower(name), item_type)
  WHERE is_active;

CREATE TABLE IF NOT EXISTS technical_cards (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  output_item_id TEXT NOT NULL UNIQUE REFERENCES catalog_items(id),
  yield_quantity NUMERIC(14, 4) NOT NULL CHECK (yield_quantity > 0),
  yield_weight_grams NUMERIC(14, 3) CHECK (yield_weight_grams IS NULL OR yield_weight_grams > 0),
  station TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE technical_cards
  ADD COLUMN IF NOT EXISTS yield_weight_grams NUMERIC(14, 3)
  CHECK (yield_weight_grams IS NULL OR yield_weight_grams > 0);

CREATE TABLE IF NOT EXISTS technical_card_components (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  technical_card_id BIGINT NOT NULL REFERENCES technical_cards(id) ON DELETE CASCADE,
  component_item_id TEXT NOT NULL REFERENCES catalog_items(id),
  gross_quantity NUMERIC(14, 4) NOT NULL CHECK (gross_quantity > 0),
  net_quantity NUMERIC(14, 4) NOT NULL CHECK (net_quantity > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (technical_card_id, component_item_id),
  CHECK (net_quantity <= gross_quantity)
);

CREATE INDEX IF NOT EXISTS technical_card_components_item_idx
  ON technical_card_components (component_item_id);

CREATE TABLE IF NOT EXISTS audit_events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  before_state JSONB,
  after_state JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS audit_events_entity_idx
  ON audit_events (entity_type, entity_id, created_at DESC);

CREATE OR REPLACE FUNCTION reject_technical_card_cycle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  output_item TEXT;
  cycle_exists BOOLEAN;
BEGIN
  SELECT output_item_id INTO output_item
  FROM technical_cards
  WHERE id = NEW.technical_card_id;

  IF output_item IS NULL THEN
    RAISE EXCEPTION 'Technical card % does not exist', NEW.technical_card_id
      USING ERRCODE = '23503';
  END IF;

  WITH RECURSIVE dependencies(item_id) AS (
    SELECT NEW.component_item_id
    UNION
    SELECT child.component_item_id
    FROM dependencies parent
    JOIN technical_cards nested_card ON nested_card.output_item_id = parent.item_id
    JOIN technical_card_components child ON child.technical_card_id = nested_card.id
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

DROP TRIGGER IF EXISTS technical_card_cycle_guard ON technical_card_components;
CREATE CONSTRAINT TRIGGER technical_card_cycle_guard
AFTER INSERT OR UPDATE OF technical_card_id, component_item_id
ON technical_card_components
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION reject_technical_card_cycle();

INSERT INTO catalog_items (id, item_type, name, category, unit, purchase_cost, sale_price)
SELECT id, 'ingredient', name, category, unit, average_cost, NULL
FROM ingredients
ON CONFLICT (id) DO NOTHING;

INSERT INTO catalog_items (id, item_type, name, category, unit, purchase_cost, sale_price)
SELECT p.id::TEXT, 'product', p.name, c.name, p.unit, 0, p.price
FROM products p
JOIN categories c ON c.id = p.category_id
ON CONFLICT (id) DO NOTHING;

INSERT INTO catalog_items (id, item_type, name, category, unit, purchase_cost, sale_price) VALUES
  ('water', 'ingredient', 'Вода технологическая', 'Бакалея', 'л', 2, NULL),
  ('pf-1', 'preparation', 'Тесто для лагмана', 'Заготовки кухни', 'кг', 0, NULL),
  ('pf-2', 'preparation', 'Бульон говяжий', 'Заготовки кухни', 'л', 0, NULL),
  ('pf-3', 'preparation', 'Заправка для салата', 'Холодный цех', 'л', 0, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO technical_cards (output_item_id, yield_quantity, yield_weight_grams, station)
SELECT product_id::TEXT, 1, yield_grams, station
FROM recipes
ON CONFLICT (output_item_id) DO NOTHING;

UPDATE technical_cards tc
SET yield_weight_grams = tc.yield_quantity * 1000,
    yield_quantity = 1
FROM catalog_items item
WHERE item.id = tc.output_item_id
  AND item.item_type = 'product'
  AND tc.yield_weight_grams IS NULL;

INSERT INTO technical_card_components (
  technical_card_id,
  component_item_id,
  gross_quantity,
  net_quantity
)
SELECT
  tc.id,
  ri.ingredient_id,
  ri.gross_amount / 1000.0,
  ri.net_amount / 1000.0
FROM recipe_items ri
JOIN technical_cards tc ON tc.output_item_id = ri.product_id::TEXT
ON CONFLICT (technical_card_id, component_item_id) DO NOTHING;

INSERT INTO technical_cards (output_item_id, yield_quantity, station) VALUES
  ('pf-1', 1, 'Кухня'),
  ('pf-2', 5, 'Кухня'),
  ('pf-3', 0.8, 'Холодный цех')
ON CONFLICT (output_item_id) DO NOTHING;

INSERT INTO technical_card_components (technical_card_id, component_item_id, gross_quantity, net_quantity)
SELECT tc.id, seed.component_item_id, seed.gross_quantity, seed.net_quantity
FROM (VALUES
  ('pf-1', 'flour', 0.95::NUMERIC, 0.95::NUMERIC),
  ('pf-1', 'water', 0.25::NUMERIC, 0.25::NUMERIC),
  ('pf-1', 'salt', 0.02::NUMERIC, 0.02::NUMERIC),
  ('pf-1', 'oil', 0.05::NUMERIC, 0.05::NUMERIC),
  ('pf-2', 'beef', 0.50::NUMERIC, 0.50::NUMERIC),
  ('pf-2', 'water', 5.00::NUMERIC, 5.00::NUMERIC),
  ('pf-2', 'onion', 0.20::NUMERIC, 0.18::NUMERIC),
  ('pf-2', 'carrot', 0.20::NUMERIC, 0.18::NUMERIC),
  ('pf-2', 'spices', 0.01::NUMERIC, 0.01::NUMERIC),
  ('pf-3', 'oil', 0.70::NUMERIC, 0.70::NUMERIC),
  ('pf-3', 'water', 0.10::NUMERIC, 0.10::NUMERIC),
  ('pf-3', 'salt', 0.02::NUMERIC, 0.02::NUMERIC),
  ('pf-3', 'spices', 0.03::NUMERIC, 0.03::NUMERIC)
) AS seed(output_item_id, component_item_id, gross_quantity, net_quantity)
JOIN technical_cards tc ON tc.output_item_id = seed.output_item_id
JOIN catalog_items ingredient ON ingredient.id = seed.component_item_id
ON CONFLICT (technical_card_id, component_item_id) DO NOTHING;

-- Лагман использует произведённое тесто, а не списывает муку напрямую.
DELETE FROM technical_card_components
WHERE technical_card_id = (SELECT id FROM technical_cards WHERE output_item_id = '203')
  AND component_item_id = 'flour';

INSERT INTO technical_card_components (technical_card_id, component_item_id, gross_quantity, net_quantity)
SELECT id, 'pf-1', 0.15, 0.15
FROM technical_cards
WHERE output_item_id = '203'
ON CONFLICT (technical_card_id, component_item_id) DO NOTHING;

INSERT INTO schema_migrations (version)
VALUES ('003_catalog_and_technical_cards')
ON CONFLICT (version) DO NOTHING;

COMMIT;
