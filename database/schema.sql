-- Reference only. Apply backend/migrations/ with Flask-Migrate for real databases.
CREATE TABLE users (
  id VARCHAR(36) PRIMARY KEY,
  email VARCHAR(254) UNIQUE NOT NULL,
  password_hash VARCHAR(256) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE creator_profiles (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  handle VARCHAR(40) UNIQUE NOT NULL,
  display_name VARCHAR(100) NOT NULL,
  bio VARCHAR(500) NOT NULL DEFAULT ''
);
CREATE TABLE product_categories (
  name VARCHAR(50) PRIMARY KEY,
  slug VARCHAR(60) UNIQUE NOT NULL
);
-- Seeded by the first migration: Wallpapers, Digital Art & Illustrations,
-- Canva Designs, and Mobile Icon Packs.
CREATE TABLE products (
  id VARCHAR(36) PRIMARY KEY,
  slug VARCHAR(150) UNIQUE NOT NULL,
  title VARCHAR(120) NOT NULL,
  description VARCHAR(5000) NOT NULL,
  category VARCHAR(50) NOT NULL REFERENCES product_categories(name),
  creator_id VARCHAR(36) NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
  price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
  currency CHAR(3) NOT NULL DEFAULT 'USD',
  tags JSON NOT NULL,
  status VARCHAR(16) NOT NULL CHECK (status IN ('draft','published')),
  product_metadata JSON NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE product_previews (
  id VARCHAR(36) PRIMARY KEY,
  product_id VARCHAR(36) NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  public_path VARCHAR(255) NOT NULL,
  alt_text VARCHAR(200) NOT NULL,
  position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE product_resources (
  id VARCHAR(36) PRIMARY KEY,
  product_id VARCHAR(36) NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  resource_type VARCHAR(20) NOT NULL CHECK (resource_type IN ('file','canva_url')),
  display_name VARCHAR(200) NOT NULL,
  private_storage_key VARCHAR(255),
  external_url VARCHAR(2048),
  file_format VARCHAR(20),
  file_size INTEGER,
  CHECK ((resource_type='file' AND private_storage_key IS NOT NULL) OR (resource_type='canva_url' AND external_url IS NOT NULL))
);
CREATE TABLE revoked_tokens (jti VARCHAR(36) PRIMARY KEY, revoked_at TIMESTAMPTZ NOT NULL);
