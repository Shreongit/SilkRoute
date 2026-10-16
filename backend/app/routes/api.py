from decimal import Decimal
from pathlib import Path
import re
from uuid import uuid4
from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from sqlalchemy import or_
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import CreatorProfile, Product, ProductPreview, ProductResource, RevokedToken, User, utcnow
from app.services.storage import LocalStorage
from app.services.validation import make_slug, validate_product_payload

api = Blueprint("api", __name__, url_prefix="/api/v1")


def success(data, status=200, **extra):
    return jsonify({"data": data, "error": None, **extra}), status


def failure(code, message, status=400, details=None):
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return jsonify({"data": None, "error": error}), status


def json_body():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def creator_for_user(user_id):
    return CreatorProfile.query.filter_by(user_id=user_id).first()


def serialize_product(product, include_creator=False):
    metadata = dict(product.product_metadata or {})
    image = product.previews[0].public_path if product.previews else metadata.get("image_url", "")
    label = metadata.get("product_label") or {"Wallpapers": "wallpaper", "Mobile Icon Packs": "icon", "Digital Art & Illustrations": "art", "Canva Designs": "canva"}.get(product.category, "")
    if not include_creator:
        metadata.pop("template_url", None)
    result = {
        "id": product.id,
        "digital_product_id": product.digital_product_id,
        "s_no": product.s_no,
        "slug": product.slug,
        "title": product.title,
        "description": product.description,
        "category": product.category,
        "product_label": label,
        "creator_id": product.creator_id,
        "creator": product.creator.display_name if product.creator else "Independent creator",
        "creator_handle": product.creator.handle if product.creator else "",
        "price": float(product.price),
        "currency": product.currency,
        "tags": product.tags or [],
        "status": product.status,
        "metadata": metadata,
        "image": image,
        "images": [preview.public_path for preview in product.previews] or ([image] if image else []),
        "created_at": product.created_at.isoformat() if product.created_at else None,
    }
    if include_creator:
        result["resources"] = [{"id": item.id, "resource_type": item.resource_type, "display_name": item.display_name, "file_format": item.file_format} for item in product.resources]
    return result


def product_query():
    return Product.query.join(CreatorProfile).filter(Product.status == "published")


@api.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db.session.rollback()
        return failure("database_unavailable", "The configured database is not reachable.", 503)
    return success({"status": "ok", "service": "silk-route-api", "database": "connected"})


@api.post("/auth/register")
def register():
    data = json_body()
    raw_email = data.get("email", "")
    password = data.get("password", "")
    raw_name = data.get("display_name", "")
    raw_handle = data.get("handle", "")
    errors = {}
    email = raw_email.strip().lower() if isinstance(raw_email, str) else ""
    name = raw_name.strip() if isinstance(raw_name, str) else ""
    handle = raw_handle.strip().lower() if isinstance(raw_handle, str) else ""
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        errors["email"] = "Enter a valid email address."
    if not isinstance(password, str) or len(password) < 10 or len(password) > 128:
        errors["password"] = "Password must contain 10–128 characters."
    if not name or len(name) > 100:
        errors["display_name"] = "Display name must contain 1–100 characters."
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9_-]{0,38}[a-z0-9])?", handle):
        errors["handle"] = "Handle must be 1–40 characters, start and end with a letter or number, and use only letters, numbers, hyphens, or underscores."
    if errors:
        return failure("validation_error", "Please correct the fields and try again.", details=errors)
    if User.query.filter_by(email=email).first() or CreatorProfile.query.filter_by(handle=handle).first():
        return failure("account_exists", "That email or creator handle is already registered.", 409)
    user = User(email=email)
    user.set_password(password)
    user.profile = CreatorProfile(handle=handle, display_name=name)
    try:
        db.session.add(user)
        db.session.flush()
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("account_exists", "That email or creator handle is already registered.", 409)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.error("Creator registration failed while saving the account.")
        return failure("registration_failed", "The account could not be created. Please try again.", 500)
    token = create_access_token(identity=user.id)
    return success({"access_token": token, "user": {"id": user.id, "email": user.email, "creator": {"id": user.profile.id, "handle": handle, "display_name": name}}}, 201)


@api.post("/auth/login")
def login():
    data = json_body()
    user = User.query.filter_by(email=str(data.get("email", "")).strip().lower()).first()
    if not user or not user.check_password(str(data.get("password", ""))):
        return failure("invalid_credentials", "Email or password is incorrect.", 401)
    token = create_access_token(identity=user.id)
    return success({"access_token": token, "user": {"id": user.id, "email": user.email, "creator": {"id": user.profile.id, "handle": user.profile.handle, "display_name": user.profile.display_name}}})


@api.get("/auth/me")
@jwt_required()
def me():
    user = db.session.get(User, get_jwt_identity())
    if not user or not user.profile:
        return failure("account_not_found", "Creator account was not found.", 404)
    return success({"id": user.id, "email": user.email, "creator": {"id": user.profile.id, "handle": user.profile.handle, "display_name": user.profile.display_name, "bio": user.profile.bio}})


@api.post("/auth/logout")
@jwt_required()
def logout():
    db.session.add(RevokedToken(jti=get_jwt()["jti"]))
    db.session.commit()
    return success({"logged_out": True})


@api.get("/products")
def products():
    query = product_query()
    search = request.args.get("q", "").strip()[:120]
    category = request.args.get("category")
    price = request.args.get("price")
    sort = request.args.get("sort", "newest")
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(48, max(1, int(request.args.get("per_page", 12))))
    except ValueError:
        return failure("invalid_pagination", "Page and per_page must be integers.")
    label_categories = {"wallpaper": "Wallpapers", "icon": "Mobile Icon Packs", "art": "Digital Art & Illustrations", "canva": "Canva Designs"}
    if category:
        query = query.filter(Product.category == label_categories.get(category, category))
    if category and category not in {"Wallpapers", "Digital Art & Illustrations", "Canva Designs", "Mobile Icon Packs", *label_categories}:
        return failure("invalid_category", "Choose one of the four supported product categories.")
    if price == "free":
        query = query.filter(Product.price == 0)
    elif price == "paid":
        query = query.filter(Product.price > 0)
    elif price:
        return failure("invalid_price", "Price must be 'free' or 'paid'.")
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Product.title.ilike(pattern), Product.description.ilike(pattern), Product.tags.cast(db.String).ilike(pattern), CreatorProfile.display_name.ilike(pattern)))
    if sort == "price-low":
        query = query.order_by(Product.price.asc())
    elif sort == "price-high":
        query = query.order_by(Product.price.desc())
    elif sort == "newest":
        query = query.order_by(Product.s_no.is_(None).asc(), Product.s_no.asc(), Product.created_at.desc())
    else:
        return failure("invalid_sort", "Sort must be newest, price-low, or price-high.")
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return success([serialize_product(item) for item in pagination.items], meta={"count": pagination.total, "page": page, "per_page": per_page, "pages": pagination.pages})


@api.get("/products/<product_id>")
def product(product_id):
    item = product_query().filter(Product.id == product_id).first()
    if not item:
        item = product_query().filter(Product.digital_product_id == product_id).first()
    if not item:
        item = product_query().filter(Product.slug == product_id).first()
    if not item:
        return failure("not_found", "Product not found.", 404)
    return success(serialize_product(item))


@api.get("/creators/<handle>")
def creator(handle):
    profile = CreatorProfile.query.filter_by(handle=handle).first()
    if not profile:
        return failure("not_found", "Creator not found.", 404)
    return success({"id": profile.id, "handle": profile.handle, "display_name": profile.display_name, "bio": profile.bio, "products": [serialize_product(p) for p in profile.products if p.status == "published"]})


@api.get("/creators")
def creators():
    profiles = CreatorProfile.query.join(Product).filter(Product.status == "published").distinct().order_by(CreatorProfile.display_name.asc()).all()
    return success([{"id": profile.id, "handle": profile.handle, "display_name": profile.display_name, "bio": profile.bio, "products_count": sum(1 for item in profile.products if item.status == "published")} for profile in profiles])


@api.route("/creator/products", methods=["GET", "POST"])
@jwt_required()
def creator_products():
    profile = creator_for_user(get_jwt_identity())
    if not profile:
        return failure("creator_profile_required", "Creator profile not found.", 404)
    if request.method == "GET":
        return success([serialize_product(item, include_creator=True) for item in Product.query.filter_by(creator_id=profile.id).order_by(Product.updated_at.desc()).all()])
    data = request.get_json(silent=True)
    errors = validate_product_payload(data)
    if errors:
        return failure("validation_error", "Please correct the product fields.", details=errors)
    slug_base = make_slug(data["title"])
    slug = f"{slug_base}-{uuid4().hex[:8]}"
    item = Product(slug=slug, title=data["title"].strip(), description=data["description"].strip(), category=data["category"], creator_id=profile.id, price=Decimal(str(data.get("price", 0))), currency=data.get("currency", "USD"), tags=data.get("tags", []), product_metadata=data.get("metadata", {}), status="draft")
    db.session.add(item)
    db.session.commit()
    return success(serialize_product(item, include_creator=True), 201)


@api.route("/creator/products/<product_id>", methods=["GET", "PATCH", "DELETE"])
@jwt_required()
def creator_product(product_id):
    profile = creator_for_user(get_jwt_identity())
    item = Product.query.filter_by(id=product_id, creator_id=profile.id if profile else None).first()
    if not item:
        return failure("not_found", "Product not found.", 404)
    if request.method == "GET":
        return success(serialize_product(item, include_creator=True))
    if request.method == "DELETE":
        stored_keys = [resource.private_storage_key for resource in item.resources if resource.private_storage_key]
        stored_keys.extend(preview.public_path.rsplit("/", 1)[-1] for preview in item.previews)
        db.session.delete(item)
        db.session.commit()
        storage = LocalStorage()
        for key in stored_keys:
            storage.delete(key if "/" in key else f"previews/{key}")
        return success({"deleted": True})
    data = request.get_json(silent=True)
    errors = validate_product_payload(data, partial=True)
    if errors:
        return failure("validation_error", "Please correct the product fields.", details=errors)
    for key, attr in (("title", "title"), ("description", "description"), ("category", "category"), ("price", "price"), ("currency", "currency"), ("tags", "tags"), ("metadata", "product_metadata")):
        if key in data:
            setattr(item, attr, Decimal(str(data[key])) if key == "price" else data[key].strip() if key in {"title", "description"} else data[key])
    item.updated_at = utcnow()
    db.session.commit()
    return success(serialize_product(item, include_creator=True))


@api.post("/creator/products/<product_id>/publish")
@jwt_required()
def publish_product(product_id):
    profile = creator_for_user(get_jwt_identity())
    item = Product.query.filter_by(id=product_id, creator_id=profile.id if profile else None).first()
    if not item:
        return failure("not_found", "Product not found.", 404)
    errors = validate_product_payload({"title": item.title, "description": item.description, "category": item.category, "metadata": item.product_metadata}, publishing=True)
    if errors:
        return failure("validation_error", "Complete the product details before publishing.", details=errors)
    if not item.previews:
        return failure("validation_error", "Add at least one preview image before publishing.", details={"previews": "At least one preview image is required."})
    if not item.resources:
        return failure("validation_error", "Register at least one source resource before publishing.", details={"resources": "At least one downloadable file or Canva template is required."})
    if item.category == "Canva Designs":
        if not any(resource.resource_type == "canva_url" for resource in item.resources):
            return failure("validation_error", "Register the Canva template resource before publishing.", details={"resources": "A Canva template link is required."})
    else:
        allowed_formats = {"Wallpapers": {"JPG", "JPEG", "PNG", "WEBP", "ZIP"}, "Digital Art & Illustrations": {"AI", "SVG", "EPS", "PNG", "PSD", "ZIP"}, "Mobile Icon Packs": {"PNG", "SVG", "WEBP", "ZIP"}}.get(item.category, set())
        if not any(resource.resource_type == "file" and resource.file_format in allowed_formats for resource in item.resources):
            return failure("validation_error", "Register a file supported by this product category.", details={"resources": "A compatible file is required."})
    item.status = "published"
    item.updated_at = utcnow()
    db.session.commit()
    return success(serialize_product(item, include_creator=True))


@api.post("/creator/products/<product_id>/unpublish")
@jwt_required()
def unpublish_product(product_id):
    profile = creator_for_user(get_jwt_identity())
    item = Product.query.filter_by(id=product_id, creator_id=profile.id if profile else None).first()
    if not item:
        return failure("not_found", "Product not found.", 404)
    item.status = "draft"
    db.session.commit()
    return success(serialize_product(item, include_creator=True))


@api.post("/creator/products/<product_id>/previews")
@jwt_required()
def upload_preview(product_id):
    profile = creator_for_user(get_jwt_identity())
    item = Product.query.filter_by(id=product_id, creator_id=profile.id if profile else None).first()
    if not item:
        return failure("not_found", "Product not found.", 404)
    file = request.files.get("file")
    if not file or not file.filename:
        return failure("invalid_upload", "Choose an image file.")
    header = file.stream.read(12)
    file.stream.seek(0)
    valid_signatures = {"png": header.startswith(b"\x89PNG\r\n\x1a\n"), "jpg": header.startswith(b"\xff\xd8\xff"), "jpeg": header.startswith(b"\xff\xd8\xff"), "webp": len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"}
    extension = secure_filename(file.filename).rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if not valid_signatures.get(extension, False):
        return failure("invalid_upload", "File content must be a PNG, JPG, JPEG, or WEBP image.")
    try:
        key, _ = LocalStorage().save_preview(file)
    except ValueError as error:
        return failure("invalid_upload", str(error))
    preview = ProductPreview(product_id=item.id, public_path=f"/api/v1/media/{Path(key).name}", alt_text=(request.form.get("alt_text") or item.title)[:200], position=len(item.previews))
    db.session.add(preview)
    db.session.commit()
    return success({"id": preview.id, "url": preview.public_path, "alt_text": preview.alt_text}, 201)


@api.get("/media/<filename>")
def public_preview(filename):
    if Path(filename).name != filename:
        return failure("not_found", "Preview not found.", 404)
    storage = LocalStorage()
    path = storage.root / "previews" / filename
    if not path.is_file():
        return failure("not_found", "Preview not found.", 404)
    return send_file(path, conditional=True, max_age=3600)


@api.post("/creator/products/<product_id>/resources")
@jwt_required()
def register_resource(product_id):
    profile = creator_for_user(get_jwt_identity())
    item = Product.query.filter_by(id=product_id, creator_id=profile.id if profile else None).first()
    if not item:
        return failure("not_found", "Product not found.", 404)
    data = json_body()
    if item.category == "Canva Designs":
        template_url = data.get("template_url")
        parsed = urlparse(template_url) if isinstance(template_url, str) else None
        if not parsed or parsed.scheme != "https" or parsed.hostname not in {"canva.com", "www.canva.com"}:
            return failure("validation_error", "Provide a valid HTTPS Canva template URL.", details={"template_url": "Use a Canva template URL."})
        item.product_metadata = {**item.product_metadata, "template_url": template_url}
        resource = ProductResource.query.filter_by(product_id=item.id, resource_type="canva_url").first()
        if resource:
            resource.external_url = template_url
        else:
            resource = ProductResource(product_id=item.id, resource_type="canva_url", display_name="Canva template", external_url=template_url)
    else:
        uploaded = request.files.get("file") if request.files else None
        if not uploaded or not uploaded.filename:
            return failure("invalid_upload", "Choose a product resource file.")
        allowed = {"Wallpapers": {"JPG", "JPEG", "PNG", "WEBP"}, "Digital Art & Illustrations": {"AI", "SVG", "EPS", "PNG", "PSD"}, "Mobile Icon Packs": {"PNG", "SVG", "WEBP"}}
        metadata_key = {"Wallpapers": "formats", "Digital Art & Illustrations": "source_formats", "Mobile Icon Packs": "formats"}.get(item.category)
        selected_formats = item.product_metadata.get(metadata_key, []) if metadata_key else []
        if selected_formats:
            accepted = {value.upper() for value in selected_formats}
            if "JPG" in accepted:
                accepted.add("JPEG")
            allowed[item.category] = allowed[item.category].intersection(accepted)
        try:
            key, fmt, size = LocalStorage().save_private_resource(uploaded, allowed.get(item.category, set()))
        except ValueError as error:
            return failure("invalid_upload", str(error))
        resource = ProductResource(product_id=item.id, resource_type="file", display_name=secure_filename(uploaded.filename), private_storage_key=key, file_format=fmt, file_size=size)
    db.session.add(resource)
    db.session.commit()
    return success({"id": resource.id, "resource_type": resource.resource_type, "display_name": resource.display_name, "file_format": resource.file_format}, 201)
