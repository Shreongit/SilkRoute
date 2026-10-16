# Architecture

`frontend/` is a standalone Vite/React/TypeScript application. React Router retains Home, Explore, Product, Creator and 404 pages and adds `/studio` for registration, sign-in and creator publishing. Public catalogue screens call the Flask API by default. Set `VITE_USE_MOCK_CATALOGUE=true` to explicitly use the Stage 1 local demonstration catalogue. API request and token handling lives in `src/services/api.ts`.

`backend/` is an application-factory Flask service. SQLAlchemy models are connected to Flask-Migrate and the committed migrations in `backend/migrations/`. PostgreSQL is the configured shared development database through Docker Compose; SQLite remains useful for local setup and isolated tests. Product catalogue responses use PostgreSQL/SQLite persisted data rather than the old in-memory fixture service.

Creator requests are authenticated with short-lived JWT bearer tokens. The user ID is taken from the verified token for every creator action; browser-supplied owner IDs are ignored. Passwords use Werkzeug's PBKDF2 hash. Logout revokes a token in the database. CORS permits only configured frontend origins.

Uploads use a `LocalStorage` adapter. Preview images are public through a generated-name API route; product source files are stored under a private directory and their storage keys are never serialized into product API responses. The storage adapter can be replaced with an object-storage provider later. There is no paid download delivery, payments, creator payouts, or account recovery yet.
