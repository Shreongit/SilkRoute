import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from app.models import ALLOWED_CATEGORIES


def validate_product_payload(payload, partial=False, publishing=False):
    errors = {}
    if not isinstance(payload, dict):
        return {"body": "Expected a JSON object."}
    required = {"title", "description", "category"}
    if not partial:
        for key in required:
            if not payload.get(key):
                errors[key] = "This field is required."
    title = payload.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip() or len(title.strip()) > 120):
        errors["title"] = "Title must contain 1–120 characters."
    description = payload.get("description")
    if description is not None and (not isinstance(description, str) or not description.strip() or len(description.strip()) > 5000):
        errors["description"] = "Description must contain 1–5000 characters."
    category = payload.get("category")
    if category is not None and (not isinstance(category, str) or category not in ALLOWED_CATEGORIES):
        errors["category"] = "Choose one of the four supported product categories."
    if "price" in payload:
        try:
            price = Decimal(str(payload["price"]))
            if not price.is_finite() or price < 0 or price > 99999999:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            errors["price"] = "Price must be a non-negative amount."
    if "currency" in payload and (not isinstance(payload["currency"], str) or not re.fullmatch(r"[A-Z]{3}", payload["currency"])):
        errors["currency"] = "Currency must be a three-letter uppercase code."
    if "tags" in payload and (not isinstance(payload["tags"], list) or len(payload["tags"]) > 12 or any(not isinstance(tag, str) or len(tag) > 30 for tag in payload["tags"])):
        errors["tags"] = "Provide up to 12 tags, each no longer than 30 characters."
    if "metadata" in payload and not isinstance(payload["metadata"], dict):
        errors["metadata"] = "Metadata must be an object."
    if isinstance(category, str) and category and "metadata" in payload and isinstance(payload["metadata"], dict):
        metadata = payload["metadata"]
        fields = {
            "Wallpapers": {"device_type": str, "resolution": str, "aspect_ratio": str, "formats": list},
            "Digital Art & Illustrations": {"artwork_type": str, "source_formats": list, "editable_source": bool},
            "Canva Designs": {"template_type": str, "template_url": str, "access_instructions": str},
            "Mobile Icon Packs": {"platforms": list, "icon_count": int, "formats": list},
        }.get(category, {})
        for key, expected in fields.items():
            if key not in metadata:
                if publishing:
                    errors[f"metadata.{key}"] = "This field is required and must have the correct type."
                continue
            if not isinstance(metadata[key], expected) or (publishing and expected in (str, list) and not metadata[key]):
                errors[f"metadata.{key}"] = "This field is required and must have the correct type."
        if category == "Canva Designs" and metadata.get("template_url"):
            parsed = urlparse(str(metadata["template_url"]))
            if parsed.scheme != "https" or parsed.hostname not in {"canva.com", "www.canva.com"}:
                errors["metadata.template_url"] = "Use a valid HTTPS Canva template URL."
        if category == "Wallpapers" and isinstance(metadata.get("formats"), list) and (publishing or metadata["formats"]):
            allowed = {"JPG", "JPEG", "PNG", "WEBP"}
            if not metadata["formats"] or any(not isinstance(value, str) or value not in allowed for value in metadata["formats"]):
                errors["metadata.formats"] = "Formats must be JPG/JPEG, PNG, or WEBP."
        if category == "Wallpapers" and metadata.get("device_type") and (not isinstance(metadata["device_type"], str) or metadata["device_type"] not in {"Desktop", "Mobile", "Ultrawide"}):
            errors["metadata.device_type"] = "Choose Desktop, Mobile, or Ultrawide."
        if category == "Wallpapers" and metadata.get("resolution") and (not isinstance(metadata["resolution"], str) or not re.fullmatch(r"\d{2,5}\s*[x×]\s*\d{2,5}", metadata["resolution"])):
            errors["metadata.resolution"] = "Resolution should look like 3840 × 2160."
        if category == "Wallpapers" and metadata.get("aspect_ratio") and (not isinstance(metadata["aspect_ratio"], str) or not re.fullmatch(r"\d{1,2}:\d{1,2}", metadata["aspect_ratio"])):
            errors["metadata.aspect_ratio"] = "Aspect ratio should look like 16:9."
        if category == "Digital Art & Illustrations" and isinstance(metadata.get("source_formats"), list) and metadata["source_formats"]:
            allowed = {"AI", "SVG", "EPS", "PNG", "PSD"}
            if any(not isinstance(value, str) or value not in allowed for value in metadata["source_formats"]):
                errors["metadata.source_formats"] = "Unsupported artwork source format."
        if category == "Mobile Icon Packs":
            if isinstance(metadata.get("platforms"), list) and ((publishing and not metadata["platforms"]) or any(not isinstance(x, str) or x not in {"Android", "iOS"} for x in metadata["platforms"])):
                errors["metadata.platforms"] = "Select Android, iOS, or both."
            if "icon_count" in metadata and ((publishing or metadata["icon_count"] != 0) and (type(metadata["icon_count"]) is not int or metadata["icon_count"] < 1 or metadata["icon_count"] > 10000)):
                errors["metadata.icon_count"] = "Icon count must be between 1 and 10,000."
            if isinstance(metadata.get("formats"), list) and ((publishing and not metadata["formats"]) or any(not isinstance(x, str) or x not in {"PNG", "SVG", "WEBP"} for x in metadata["formats"])):
                errors["metadata.formats"] = "Formats must be PNG, SVG, or WEBP."
    return errors


def make_slug(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:120]
    return slug or "product"
