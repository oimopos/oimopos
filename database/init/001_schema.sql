BEGIN;

CREATE TABLE branches (
  id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  city TEXT NOT NULL DEFAULT 'Бишкек',
  address TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE categories (
  id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  sort_order SMALLINT NOT NULL DEFAULT 0
);

CREATE TABLE products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category_id SMALLINT NOT NULL REFERENCES categories(id),
  unit TEXT NOT NULL,
  price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
  barcode TEXT UNIQUE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ingredients (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL,
  unit TEXT NOT NULL,
  stock NUMERIC(14, 3) NOT NULL DEFAULT 0 CHECK (stock >= 0),
  average_cost NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (average_cost >= 0),
  stock_limit NUMERIC(14, 3) NOT NULL DEFAULT 0 CHECK (stock_limit >= 0),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE recipes (
  product_id INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
  yield_grams NUMERIC(10, 3) NOT NULL CHECK (yield_grams > 0),
  station TEXT NOT NULL DEFAULT 'Кухня',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE recipe_items (
  product_id INTEGER NOT NULL REFERENCES recipes(product_id) ON DELETE CASCADE,
  ingredient_id TEXT NOT NULL REFERENCES ingredients(id),
  gross_amount NUMERIC(10, 3) NOT NULL CHECK (gross_amount >= 0),
  net_amount NUMERIC(10, 3) NOT NULL CHECK (net_amount >= 0),
  measure TEXT NOT NULL DEFAULT 'г',
  PRIMARY KEY (product_id, ingredient_id)
);

CREATE TABLE sales (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  receipt_number INTEGER NOT NULL CHECK (receipt_number > 0),
  branch_id SMALLINT NOT NULL REFERENCES branches(id),
  cashier_name TEXT NOT NULL,
  payment_method TEXT NOT NULL CHECK (payment_method IN ('cash', 'card', 'qr')),
  total NUMERIC(12, 2) NOT NULL CHECK (total >= 0),
  received NUMERIC(12, 2) NOT NULL CHECK (received >= total),
  change_amount NUMERIC(12, 2) GENERATED ALWAYS AS (received - total) STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (branch_id, receipt_number)
);

CREATE TABLE sale_items (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_id BIGINT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  product_id INTEGER REFERENCES products(id),
  product_name TEXT NOT NULL,
  unit TEXT NOT NULL,
  quantity NUMERIC(10, 3) NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
  line_total NUMERIC(12, 2) GENERATED ALWAYS AS (quantity * unit_price) STORED
);

CREATE TABLE stock_documents (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  number TEXT NOT NULL UNIQUE,
  document_type TEXT NOT NULL CHECK (document_type IN ('supply', 'writeoff', 'production', 'inventory', 'transfer')),
  branch_id SMALLINT NOT NULL REFERENCES branches(id),
  status TEXT NOT NULL DEFAULT 'posted' CHECK (status IN ('draft', 'posted', 'cancelled')),
  supplier TEXT,
  reason TEXT,
  total NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (total >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stock_document_items (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_id BIGINT NOT NULL REFERENCES stock_documents(id) ON DELETE CASCADE,
  ingredient_id TEXT REFERENCES ingredients(id),
  product_id INTEGER REFERENCES products(id),
  quantity NUMERIC(14, 3) NOT NULL,
  unit_cost NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
  CHECK ((ingredient_id IS NOT NULL)::INTEGER + (product_id IS NOT NULL)::INTEGER = 1)
);

CREATE INDEX sales_created_at_idx ON sales (created_at DESC);
CREATE INDEX sales_branch_created_at_idx ON sales (branch_id, created_at DESC);
CREATE INDEX sale_items_sale_id_idx ON sale_items (sale_id);
CREATE INDEX stock_documents_created_at_idx ON stock_documents (created_at DESC);

COMMIT;

