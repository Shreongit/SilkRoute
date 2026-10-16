# API v1

Base URL: `http://127.0.0.1:5000/api/v1`. JSON uses `{ "data": ..., "error": null }` for success and `{ "data": null, "error": { "code", "message", "details?" } }` for errors.

| Method and path | Access | Behavior |
|---|---|---|
| `GET /health` | Public | Checks the configured database connection |
| `POST /auth/register` | Public | Creates a user and creator profile; returns an 8-hour bearer token |
| `POST /auth/login` | Public | Verifies password hash and returns a bearer token |
| `GET /auth/me` | Bearer | Returns the verified user's creator identity |
| `POST /auth/logout` | Bearer | Revokes the presented token |
| `GET /products` | Public | Published catalogue, search `q`, category, `price=free|paid`, `sort=newest|price-low|price-high`, `page`, `per_page` (max 48) |
| `GET /products/<id-or-slug>` | Public | Published product only; private resource paths and Canva edit links are excluded |
| `GET /creators` | Public | Creators with published work |
| `GET /creators/<handle>` | Public | Creator profile and published products |
| `GET /creator/products` | Bearer | Current creator's own drafts and listings |
| `POST /creator/products` | Bearer | Create a draft; creator identity comes from the token |
| `GET/PATCH/DELETE /creator/products/<id>` | Bearer | Read or modify/delete an owned product |
| `POST /creator/products/<id>/publish` | Bearer | Validates metadata, preview and product resource before publishing |
| `POST /creator/products/<id>/unpublish` | Bearer | Returns an owned listing to draft state |
| `POST /creator/products/<id>/previews` | Bearer | Upload a PNG/JPG/JPEG/WEBP preview (max 8 MB) |
| `POST /creator/products/<id>/resources` | Bearer | Upload private category-allowed source file, or register a Canva URL |
| `GET /media/<filename>` | Public | Serves only an uploaded preview by generated filename |

Authentication uses `Authorization: Bearer <access_token>`. Errors use 400 for validation, 401 for authentication, 404 for inaccessible/missing owned products, 409 for duplicate account identity, and 413 for oversized uploads. Public product serializers never include private filesystem keys or source download URLs. Payment and source delivery endpoints are not implemented.
