from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app import create_app
from app.extensions import db
from app.services.catalogue import CatalogueValidationError, import_catalogue


def main():
    app = create_app()
    configured_path = app.config.get("PRODUCTS_JSON_PATH") or BACKEND / "data" / "products.json"
    path = Path(configured_path)
    if not path.is_absolute():
        path = ROOT / path
    creator_id = app.config.get("CATALOGUE_CREATOR_ID")
    if not creator_id:
        print("Set CATALOGUE_CREATOR_ID to an existing creator profile ID before importing.", file=sys.stderr)
        return 2
    with app.app_context():
        try:
            created, updated = import_catalogue(db.session, path, creator_id)
        except (CatalogueValidationError, Exception) as exc:
            print(f"Catalogue import failed: {exc}", file=sys.stderr)
            return 1
    print(f"Catalogue import complete: {created} created, {updated} updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
