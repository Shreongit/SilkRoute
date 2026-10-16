from datetime import datetime, timezone
from uuid import uuid4

from werkzeug.security import check_password_hash, generate_password_hash

from sqlalchemy import CheckConstraint

from app.extensions import db


ALLOWED_CATEGORIES = {"Wallpapers", "Digital Art & Illustrations", "Canva Designs", "Mobile Icon Packs"}


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    profile = db.relationship("CreatorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class RevokedToken(db.Model):
    __tablename__ = "revoked_tokens"
    jti = db.Column(db.String(36), primary_key=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class CreatorProfile(db.Model):
    __tablename__ = "creator_profiles"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    handle = db.Column(db.String(40), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.String(500), nullable=False, default="")
    user = db.relationship("User", back_populates="profile")
    products = db.relationship("Product", back_populates="creator", cascade="all, delete-orphan")


class ProductCategory(db.Model):
    __tablename__ = "product_categories"
    name = db.Column(db.String(50), primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    products = db.relationship("Product", back_populates="category_record")


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published')", name="ck_products_status"),
        CheckConstraint("price >= 0", name="ck_products_price_nonnegative"),
    )
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    digital_product_id = db.Column(db.String(120), unique=True, nullable=True, index=True)
    s_no = db.Column(db.Integer, nullable=True, index=True)
    slug = db.Column(db.String(150), unique=True, nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(5000), nullable=False)
    category = db.Column(db.String(50), db.ForeignKey("product_categories.name"), nullable=False, index=True)
    creator_id = db.Column(db.String(36), db.ForeignKey("creator_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    currency = db.Column(db.String(3), nullable=False, default="USD")
    tags = db.Column(db.JSON, nullable=False, default=list)
    status = db.Column(db.String(16), nullable=False, default="draft", index=True)
    product_metadata = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    creator = db.relationship("CreatorProfile", back_populates="products")
    category_record = db.relationship("ProductCategory", back_populates="products")
    previews = db.relationship("ProductPreview", back_populates="product", cascade="all, delete-orphan", order_by="ProductPreview.position")
    resources = db.relationship("ProductResource", back_populates="product", cascade="all, delete-orphan")


class ProductPreview(db.Model):
    __tablename__ = "product_previews"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    product_id = db.Column(db.String(36), db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    public_path = db.Column(db.String(255), nullable=False)
    alt_text = db.Column(db.String(200), nullable=False, default="Product preview")
    position = db.Column(db.Integer, nullable=False, default=0)
    product = db.relationship("Product", back_populates="previews")


class ProductResource(db.Model):
    __tablename__ = "product_resources"
    __table_args__ = (
        CheckConstraint("resource_type IN ('file', 'canva_url')", name="ck_product_resources_type"),
        CheckConstraint("(resource_type = 'file' AND private_storage_key IS NOT NULL) OR (resource_type = 'canva_url' AND external_url IS NOT NULL)", name="ck_product_resources_location"),
    )
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    product_id = db.Column(db.String(36), db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    resource_type = db.Column(db.String(20), nullable=False)  # file or canva_url
    display_name = db.Column(db.String(200), nullable=False)
    private_storage_key = db.Column(db.String(255))
    external_url = db.Column(db.String(2048))
    file_format = db.Column(db.String(20))
    file_size = db.Column(db.Integer)
    product = db.relationship("Product", back_populates="resources")
