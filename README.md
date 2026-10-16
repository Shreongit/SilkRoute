# Silk Route

Silk Route is a considered marketplace for independent makers of four kinds of digital goods: Wallpapers, Digital Art & Illustrations, Canva Designs, and Mobile Icon Packs. Stage 2 adds PostgreSQL-ready persistence, creator accounts, and a private publishing workflow while keeping the Stage 1 storefront design and routes.

## Project layout

- `frontend/` — React, TypeScript, Vite and React Router storefront and creator studio.
- `backend/` — Flask API, SQLAlchemy models, Flask-Migrate migrations, bearer-token authentication and local development storage adapter.
- `database/` — schema reference; Alembic migrations in `backend/migrations/` are authoritative.
- `docs/` — API, architecture, data handling and roadmap.

## Requirements

- Node.js 20.19+ (or 22.12+) and npm for the Vite 8 frontend.
- Python 3.10+ for Flask; install dependencies from `backend/requirements.txt`.
- PostgreSQL 14+ for persistent creator/catalogue data, or SQLite for local development and tests.

## Configure and run the backend

From `backend/`, create and activate a virtual environment, install dependencies, and copy `.env.example` to `.env`:

```sh
python -m venv .venv
# Activate .venv for your shell
python -m pip install -r requirements.txt
```

Set these variables in `backend/.env`:

- `DATABASE_URL`: `sqlite:///silk_route_dev.db` for local SQLite, or `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME` for PostgreSQL.
- `SECRET_KEY` and `JWT_SECRET_KEY`: set stable, randomly generated values of at least 32 bytes for a persistent environment. Empty values use a random process-local key, which invalidates tokens after restart.
- `FRONTEND_ORIGINS`: comma-separated allowed frontend origins, normally `http://localhost:5173`.
- `LOCAL_MEDIA_DIR`: optional private local directory for preview and source uploads; defaults to `backend/instance/private-media/`.

Initialize or upgrade the database, then start Flask:

```sh
flask --app run:app db upgrade
python run.py
```

The API listens on `http://127.0.0.1:5000`. To create a new migration after model changes, use `flask --app run:app db migrate -m "describe the change"`, inspect the generated migration, then run `flask --app run:app db upgrade`.

### PostgreSQL with Docker Compose

From the project root, `docker compose up --build` starts PostgreSQL and the Flask API, applies committed migrations, and stores private local-development assets in a named volume. The Compose database credentials are development-only values; replace them and provide stable secret environment variables for any shared environment. The frontend is still run separately.

### Creator publishing flow

Open `/studio`, create an account, and sign in. Create a product, choose one of the four supported categories, and fill the matching metadata. Save as a draft while preparing the listing. To publish, add at least one preview and a private source file (or a Canva template URL), complete category metadata, then use **Save & publish**. Drafts, edits and publish/unpublish actions are private to the authenticated creator who owns the product.

The local storage adapter accepts preview images up to 8 MB and keeps product source files private. Category-compatible individual files and ZIP bundles are accepted; Canva designs register HTTPS Canva template URLs. The API returns public preview routes only; private source keys and file paths are never serialized to the browser. Download entitlements and source delivery are intentionally not implemented.

## Run the frontend

From `frontend/`:

```sh
npm install
npm run dev
```

The Vite app opens at `http://localhost:5173`. Copy `.env.example` to `.env` to configure `VITE_API_BASE_URL` (normally `http://localhost:5000/api/v1`). The default is API-backed; set `VITE_USE_MOCK_CATALOGUE=true` only to explicitly use the Stage 1 local demonstration catalogue. That catalogue is not presented as persisted creator content. Build with `npm run build`.

## Tests

From `backend/`, run `python -m unittest discover -s tests`. Tests use an isolated SQLite database and cover authentication, token revocation, all four categories, validation, draft/publish state, ownership, uploads, search and pagination.

## Current boundaries

There is no payment processing, creator payout, subscription, commission, refund, paid-download delivery, production object storage, account recovery, moderation workflow, or production deployment hardening. Local uploaded assets use a development-only filesystem adapter. Stage 2 does not create fake downloadable files or claim a payment has occurred.

## File-driven catalogue

The editable catalogue lives at `backend/data/products.json`. It contains one top-level `products` array. Every record must contain exactly `s_no` (positive integer), `image_url` (HTTP/HTTPS URL), `digital_product_id` (unique stable string, maximum 120 characters), `digital_product_name` (non-empty string), `product_description` (non-empty string), and `product_label`. Labels are exactly `wallpaper`, `icon`, `art`, or `canva`. Four clearly identified examples are in the file.

Copy the ID of an existing creator profile from the database and set `CATALOGUE_CREATOR_ID` in `backend/.env`. The importer never creates a user or profile. The explicit import command treats new file entries as published, zero-price USD catalogue listings owned by that configured creator; the command is the operator's publishing action. Updating a matching `digital_product_id` changes its order, title, description, category, and public preview while preserving its current owner and publication status. Unlisted products are never deleted. No source file or download URL is created by this catalogue format.

From the project root, with the backend virtual environment active, run:

```sh
python -m backend.scripts.import_products
```

`PRODUCTS_JSON_PATH` can point to another JSON file (absolute path or relative to the project root); otherwise the importer uses `backend/data/products.json`. Re-run the command after edits. It reports create/update counts and fails without applying any entries if the file has validation errors. The importer uses a database transaction and the marketplace reads the imported records from SQLAlchemy like other products. To verify, open Explore or request `http://localhost:5000/api/v1/products`; catalogue labels also work as category filters, for example `/api/v1/products?category=wallpaper`. Product details resolve by the database ID, slug, or `digital_product_id`.

Common fixes: ensure JSON uses double quotes and valid commas; check that every record has all six fields and no extras; use a positive integer for `s_no`; use a reachable-looking `http://` or `https://` preview URL; choose one of the four exact lowercase labels; remove duplicate IDs; and set `CATALOGUE_CREATOR_ID` to an existing creator profile ID. A failed/broken preview URL displays the local Silk Route placeholder in the frontend.

Read [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/API.md](docs/API.md), and [docs/DATABASE.md](docs/DATABASE.md) for details.
