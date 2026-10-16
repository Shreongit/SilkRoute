# Data model and persistence

The SQLAlchemy schema is migrated through Alembic revisions in `backend/migrations/`; those migration files are authoritative. `database/schema.sql` is a human-readable reference only.

## Implemented tables

| Model/table | Purpose and relationships |
|---|---|
| `User` / `users` | Unique email and password hash; one creator profile. No plaintext password is stored. |
| `CreatorProfile` / `creator_profiles` | Unique public handle, display name and biography; owns products. |
| `ProductCategory` / `product_categories` | Controlled category names, seeded by migration with the four allowed product types. Product rows reference this table. |
| `Product` / `products` | Slug, title, description, category, creator, non-negative USD price, tags, JSON category metadata and draft/published status. |
| `ProductPreview` / `product_previews` | Public preview route, alt text and display order; generated names map to image-only routes. |
| `ProductResource` / `product_resources` | Either a private local file key or a Canva template URL. Neither private keys nor Canva edit links are included in public product responses. |
| `RevokedToken` / `revoked_tokens` | JWT token IDs invalidated by logout. Expired records may be cleaned up in later maintenance work. |

SQLAlchemy JSON columns work with SQLite for tests/development and PostgreSQL in shared environments. Constraints enforce allowed category references, product status, non-negative prices and resource location/type. The server validates category metadata and permitted upload extensions before publishing.

## Planned, not implemented

Orders, order items, payment records, download entitlements, audit/usage records, creator payouts, refunds and tax accounting are not modeled in Stage 2. Payments and private file delivery are explicitly out of scope. Before enabling delivery, persist an immutable licence snapshot per purchase, verify ownership and paid/free entitlements for every download, keep source objects private, issue short-lived signed URLs, apply rate limits, and audit access. No source file should be served from the public preview route.

## Database setup

For PostgreSQL, configure `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME`, then run `flask --app run:app db upgrade` from `backend/`. Docker Compose starts a local PostgreSQL instance and applies the committed migrations before starting Flask. SQLite can be selected with `DATABASE_URL=sqlite:///silk_route_dev.db`. Never point migration commands at a production database without reviewing the migration first.
