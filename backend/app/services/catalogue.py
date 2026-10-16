import json
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import CreatorProfile, Product, ProductPreview
from app.services.validation import make_slug

LABEL_CATEGORIES = {
    "wallpaper": "Wallpapers",
    "icon": "Mobile Icon Packs",
    "art": "Digital Art & Illustrations",
    "canva": "Canva Designs",
}
REQUIRED = {"s_no", "image_url", "digital_product_id", "digital_product_name", "product_description", "product_label"}


class CatalogueValidationError(ValueError):
    pass


def load_catalogue(path):
    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise CatalogueValidationError(f"Cannot read catalogue file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogueValidationError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    if not isinstance(document, dict) or set(document) != {"products"} or not isinstance(document.get("products"), list):
        raise CatalogueValidationError("Document must be an object containing only a 'products' array.")
    seen = set()
    clean = []
    for index, item in enumerate(document["products"], 1):
        where = f"products[{index}]"
        if not isinstance(item, dict):
            raise CatalogueValidationError(f"{where} must be an object.")
        missing = REQUIRED - item.keys()
        if missing:
            raise CatalogueValidationError(f"{where} is missing required field(s): {', '.join(sorted(missing))}.")
        if set(item) != REQUIRED:
            extra = set(item) - REQUIRED
            raise CatalogueValidationError(f"{where} has unsupported field(s): {', '.join(sorted(extra))}.")
        if type(item["s_no"]) is not int or item["s_no"] <= 0:
            raise CatalogueValidationError(f"{where}.s_no must be a positive integer.")
        for key in ("digital_product_id", "digital_product_name", "product_description", "product_label", "image_url"):
            if not isinstance(item[key], str) or not item[key].strip():
                raise CatalogueValidationError(f"{where}.{key} must be a non-empty string.")
        identifier = item["digital_product_id"].strip()
        if len(identifier) > 120:
            raise CatalogueValidationError(f"{where}.digital_product_id must be at most 120 characters.")
        if len(item["digital_product_name"].strip()) > 120:
            raise CatalogueValidationError(f"{where}.digital_product_name must be at most 120 characters.")
        if len(item["product_description"].strip()) > 5000:
            raise CatalogueValidationError(f"{where}.product_description must be at most 5000 characters.")
        if identifier in seen:
            raise CatalogueValidationError(f"{where}.digital_product_id '{identifier}' is duplicated in this file.")
        seen.add(identifier)
        parsed = urlparse(item["image_url"].strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or any(char.isspace() for char in item["image_url"]) or len(item["image_url"].strip()) > 2048:
            raise CatalogueValidationError(f"{where}.image_url must be a valid HTTP or HTTPS URL.")
        label = item["product_label"].strip()
        if label not in LABEL_CATEGORIES:
            raise CatalogueValidationError(f"{where}.product_label must be one of: {', '.join(LABEL_CATEGORIES)}.")
        clean.append({**item, "digital_product_id": identifier, "digital_product_name": item["digital_product_name"].strip(), "product_description": item["product_description"].strip(), "product_label": label, "image_url": item["image_url"].strip()})
    return clean


def import_catalogue(session: Session, path, creator_id):
    products = load_catalogue(path)
    creator = session.get(CreatorProfile, creator_id)
    if not creator:
        raise CatalogueValidationError("CATALOGUE_CREATOR_ID must identify an existing creator profile; import does not create or grant ownership.")
    created = updated = 0
    try:
        for entry in products:
            item = Product.query.filter_by(digital_product_id=entry["digital_product_id"]).with_for_update().first()
            new_item = item is None
            if new_item:
                item = Product(
                    slug=f"{make_slug(entry['digital_product_name'])}-{uuid4().hex[:8]}",
                    creator_id=creator.id,
                    price=0,
                    currency="USD",
                    tags=[],
                    status="published",
                )
                session.add(item)
            item.s_no = entry["s_no"]
            item.title = entry["digital_product_name"]
            item.description = entry["product_description"]
            item.category = LABEL_CATEGORIES[entry["product_label"]]
            item.digital_product_id = entry["digital_product_id"]
            item.product_metadata = {"product_label": entry["product_label"], "image_url": entry["image_url"]}
            item.updated_at = __import__("app.models", fromlist=["utcnow"]).utcnow()
            if item.previews:
                item.previews[0].public_path = entry["image_url"]
                item.previews[0].alt_text = item.title
                item.previews[0].position = 0
                for old_preview in list(item.previews[1:]):
                    session.delete(old_preview)
            else:
                item.previews.append(ProductPreview(public_path=entry["image_url"], alt_text=item.title, position=0))
            if new_item:
                created += 1
            else:
                updated += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    return created, updated
