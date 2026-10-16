-- The first Flask-Migrate revision seeds these four supported categories.
-- This idempotent reference seed can be used when rebuilding a database manually.
INSERT INTO product_categories (name, slug) VALUES
  ('Wallpapers', 'wallpapers'),
  ('Digital Art & Illustrations', 'digital-art-illustrations'),
  ('Canva Designs', 'canva-designs'),
  ('Mobile Icon Packs', 'mobile-icon-packs')
ON CONFLICT (name) DO NOTHING;
