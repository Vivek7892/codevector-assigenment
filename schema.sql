-- Run this once in Supabase SQL Editor (or psql)
CREATE TABLE IF NOT EXISTS products (
    id         BIGSERIAL PRIMARY KEY,
    name       VARCHAR(255)   NOT NULL,
    category   VARCHAR(100)   NOT NULL,
    price      NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- Composite index for keyset pagination (newest-first) + category filter
CREATE INDEX IF NOT EXISTS idx_products_keyset
    ON products (created_at DESC, id DESC, category);
