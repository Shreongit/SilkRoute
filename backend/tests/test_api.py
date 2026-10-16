import io
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import CreatorProfile, Product, ProductCategory, ProductPreview, ProductResource, User

CATEGORIES = {
    "Wallpapers": {"device_type": "Desktop", "resolution": "3840x2160", "aspect_ratio": "16:9", "formats": ["JPG"]},
    "Digital Art & Illustrations": {"artwork_type": "Vector illustration", "source_formats": ["SVG"], "editable_source": True},
    "Canva Designs": {"template_type": "Social graphics", "template_url": "https://www.canva.com/design/abc/view", "access_instructions": "Open the template link."},
    "Mobile Icon Packs": {"platforms": ["Android", "iOS"], "icon_count": 40, "formats": ["PNG", "SVG"]},
}


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = "test-key-that-is-at-least-32-bytes"
            JWT_SECRET_KEY = "test-jwt-key-that-is-at-least-32-bytes"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
            MAX_CONTENT_LENGTH = 1024 * 1024

        self.app = create_app(TestConfig)
        self.storage = Path(tempfile.mkdtemp(prefix=".silk-route-test-", dir=Path(__file__).parent))
        self.app.config["LOCAL_MEDIA_DIR"] = str(self.storage)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all(ProductCategory(name=name, slug=name.lower().replace(" & ", "-").replace(" ", "-")) for name in CATEGORIES)
        db.session.commit()
        self.client = self.app.test_client()
        self.token = self.register("first@example.test", "first-maker")

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()
        shutil.rmtree(self.storage, ignore_errors=True)

    def register(self, email, handle):
        response = self.client.post("/api/v1/auth/register", json={"email": email, "password": "safe-passphrase-123", "display_name": handle.title(), "handle": handle})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["data"]["access_token"]

    def auth(self, token=None):
        return {"Authorization": f"Bearer {token or self.token}"}

    def test_registration_creates_linked_user_and_profile_and_signs_in(self):
        response = self.client.post("/api/v1/auth/register", json={"email": "new@example.test", "password": "secure-passphrase-456", "display_name": "New Maker", "handle": "new-maker"})
        self.assertEqual(response.status_code, 201, response.get_json())
        data = response.get_json()["data"]
        user = User.query.filter_by(email="new@example.test").one()
        profile = CreatorProfile.query.filter_by(user_id=user.id).one()
        uuid.UUID(user.id)
        uuid.UUID(profile.id)
        self.assertNotEqual(user.password_hash, "secure-passphrase-456")
        self.assertTrue(user.check_password("secure-passphrase-456"))
        self.assertEqual(data["user"]["creator"]["id"], profile.id)
        self.assertEqual(data["user"]["creator"]["handle"], "new-maker")
        self.assertEqual(self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}).status_code, 200)

    def test_registration_rejects_duplicate_email_and_handle(self):
        duplicate_email = self.client.post("/api/v1/auth/register", json={"email": "FIRST@example.test", "password": "secure-passphrase-456", "display_name": "Another Maker", "handle": "another-maker"})
        duplicate_handle = self.client.post("/api/v1/auth/register", json={"email": "another@example.test", "password": "secure-passphrase-456", "display_name": "Another Maker", "handle": "first-maker"})
        self.assertEqual(duplicate_email.status_code, 409)
        self.assertEqual(duplicate_handle.status_code, 409)
        self.assertEqual(User.query.count(), 1)
        self.assertEqual(CreatorProfile.query.count(), 1)

    def test_registration_reports_field_validation_errors(self):
        response = self.client.post("/api/v1/auth/register", json={"email": "bad-email", "password": "short", "display_name": " ", "handle": "not a handle"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.get_json()["error"]["details"]), {"email", "password", "display_name", "handle"})
        self.assertEqual(User.query.count(), 1)
        self.assertEqual(CreatorProfile.query.count(), 1)

    def test_localhost_alias_is_allowed_for_browser_registration(self):
        response = self.client.options("/api/v1/auth/register", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://127.0.0.1:5173")

    def test_registration_rolls_back_user_when_profile_insert_fails(self):
        from sqlalchemy import event
        from sqlalchemy.exc import SQLAlchemyError
        def reject_profile(_mapper, _connection, _profile):
            raise SQLAlchemyError("simulated persistence failure")
        event.listen(CreatorProfile, "before_insert", reject_profile)
        try:
            response = self.client.post("/api/v1/auth/register", json={"email": "rollback@example.test", "password": "secure-passphrase-456", "display_name": "Rollback Maker", "handle": "rollback-maker"})
        finally:
            event.remove(CreatorProfile, "before_insert", reject_profile)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["error"]["code"], "registration_failed")
        self.assertIsNone(User.query.filter_by(email="rollback@example.test").first())
        self.assertIsNone(CreatorProfile.query.filter_by(handle="rollback-maker").first())

    def create_product(self, category="Wallpapers", token=None, metadata=None):
        return self.client.post("/api/v1/creator/products", headers=self.auth(token), json={"title": f"Sample {category}", "description": "A considered digital design product.", "category": category, "price": 5, "tags": ["design"], "metadata": metadata if metadata is not None else CATEGORIES[category]})

    def attach_preview(self, product_id, token=None):
        product = Product.query.filter_by(id=product_id).first()
        db.session.add(ProductPreview(product_id=product.id, public_path="/preview/test.png", alt_text="Preview", position=0))
        if product.category == "Canva Designs":
            url = product.product_metadata["template_url"]
            db.session.add(ProductResource(product_id=product.id, resource_type="canva_url", display_name="Canva template", external_url=url))
        else:
            metadata_key = "source_formats" if product.category == "Digital Art & Illustrations" else "formats"
            fmt = product.product_metadata[metadata_key][0]
            db.session.add(ProductResource(product_id=product.id, resource_type="file", display_name=f"source.{fmt.lower()}", private_storage_key=f"resources/private.{fmt.lower()}", file_format=fmt))
        db.session.commit()

    def test_health_and_public_only_catalogue(self):
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/products").get_json()["meta"]["count"], 0)

    def test_register_login_logout_and_password_hashing(self):
        user = User.query.filter_by(email="first@example.test").first()
        self.assertNotIn("safe-passphrase-123", user.password_hash)
        self.assertTrue(user.check_password("safe-passphrase-123"))
        login = self.client.post("/api/v1/auth/login", json={"email": "first@example.test", "password": "safe-passphrase-123"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/logout", headers=self.auth()).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self.auth()).status_code, 401)

    def test_database_rejects_negative_product_price(self):
        draft = self.create_product().get_json()["data"]
        product = db.session.get(Product, draft["id"])
        product.price = -1
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_only_four_categories_are_accepted_and_valid_metadata_is_category_specific(self):
        for category, metadata in CATEGORIES.items():
            response = self.create_product(category, metadata=metadata)
            self.assertEqual(response.status_code, 201, response.get_json())
            self.assertEqual(response.get_json()["data"]["status"], "draft")
        unsupported = self.client.post("/api/v1/creator/products", headers=self.auth(), json={"title": "Course", "description": "No", "category": "Courses"})
        self.assertEqual(unsupported.status_code, 400)
        invalid = self.create_product("Canva Designs", metadata={**CATEGORIES["Canva Designs"], "template_url": "https://example.com/template"})
        self.assertEqual(invalid.status_code, 400)

    def test_every_allowed_category_can_publish_and_private_canva_link_is_not_public(self):
        for category, metadata in CATEGORIES.items():
            product = self.create_product(category, metadata=metadata).get_json()["data"]
            self.attach_preview(product["id"])
            response = self.client.post(f"/api/v1/creator/products/{product['id']}/publish", headers=self.auth())
            self.assertEqual(response.status_code, 200, response.get_json())
            public = self.client.get(f"/api/v1/products/{product['id']}").get_json()["data"]
            self.assertEqual(public["status"], "published")
            if category == "Canva Designs":
                self.assertNotIn("template_url", public["metadata"])

    def test_draft_publish_unpublish_and_public_listing(self):
        draft = self.create_product()
        product_id = draft.get_json()["data"]["id"]
        self.assertEqual(self.client.get(f"/api/v1/products/{product_id}").status_code, 404)
        missing_details = self.client.post(f"/api/v1/creator/products/{product_id}/publish", headers=self.auth())
        self.assertEqual(missing_details.status_code, 400)
        self.attach_preview(product_id)
        published = self.client.post(f"/api/v1/creator/products/{product_id}/publish", headers=self.auth())
        self.assertEqual(published.status_code, 200)
        self.assertEqual(published.get_json()["data"]["status"], "published")
        listing = self.client.get("/api/v1/products?q=Sample&category=Wallpapers&page=1&per_page=1")
        self.assertEqual(listing.get_json()["meta"]["count"], 1)
        self.assertEqual(listing.get_json()["meta"]["per_page"], 1)
        self.assertEqual(self.client.post(f"/api/v1/creator/products/{product_id}/unpublish", headers=self.auth()).status_code, 200)

    def test_owner_only_edit_publish_and_delete(self):
        product = self.create_product().get_json()["data"]
        other = self.register("other@example.test", "other-maker")
        for method, path in (("patch", ""), ("delete", ""), ("post", "/publish")):
            response = getattr(self.client, method)(f"/api/v1/creator/products/{product['id']}{path}", headers=self.auth(other), json={"title": "Taken over"} if method == "patch" else None)
            self.assertEqual(response.status_code, 404)
        no_token = self.client.patch(f"/api/v1/creator/products/{product['id']}", json={"title": "No token"})
        self.assertEqual(no_token.status_code, 401)
        changed = self.client.patch(f"/api/v1/creator/products/{product['id']}", headers=self.auth(), json={"title": "My updated design"})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.get_json()["data"]["title"], "My updated design")

    def test_invalid_preview_and_resource_uploads_are_rejected(self):
        product = self.create_product().get_json()["data"]
        bad_preview = self.client.post(f"/api/v1/creator/products/{product['id']}/previews", headers=self.auth(), data={"file": (io.BytesIO(b"not an image"), "bad.png")}, content_type="multipart/form-data")
        self.assertEqual(bad_preview.status_code, 400)
        bad_resource = self.client.post(f"/api/v1/creator/products/{product['id']}/resources", headers=self.auth(), data={"file": (io.BytesIO(b"MZ"), "installer.exe")}, content_type="multipart/form-data")
        self.assertEqual(bad_resource.status_code, 400)

    def test_malformed_json_shapes_and_http_errors_are_json(self):
        bad_registration = self.client.post("/api/v1/auth/register", json=[])
        self.assertEqual(bad_registration.status_code, 400)
        bad_product = self.client.post("/api/v1/creator/products", headers=self.auth(), json=[])
        self.assertEqual(bad_product.status_code, 400)
        method_error = self.client.post("/api/v1/health")
        self.assertEqual(method_error.status_code, 405)
        self.assertIsNotNone(method_error.get_json()["error"])
        missing = self.client.get("/api/v1/no-such-route")
        self.assertEqual(missing.status_code, 404)
        self.assertIsNotNone(missing.get_json()["error"])

    def test_valid_uploads_are_stored_and_private_keys_are_not_returned(self):
        product = self.create_product().get_json()["data"]
        preview = self.client.post(f"/api/v1/creator/products/{product['id']}/previews", headers=self.auth(), data={"file": (io.BytesIO(b"\x89PNG\r\n\x1a\npreview bytes"), "preview.png")}, content_type="multipart/form-data")
        self.assertEqual(preview.status_code, 201, preview.get_json())
        resource = self.client.post(f"/api/v1/creator/products/{product['id']}/resources", headers=self.auth(), data={"file": (io.BytesIO(b"\xff\xd8\xffsource bytes"), "wallpaper.jpg")}, content_type="multipart/form-data")
        self.assertEqual(resource.status_code, 201, resource.get_json())
        owned = self.client.get("/api/v1/creator/products", headers=self.auth()).get_json()["data"][0]
        self.assertNotIn("private_storage_key", str(owned))
        self.assertNotIn("private-media", str(owned))
        public_image = self.client.get(preview.get_json()["data"]["url"])
        self.assertEqual(public_image.status_code, 200)
        public_image.close()
        self.assertTrue((self.storage / "resources").is_dir())

    def test_canva_resource_registration_is_validated_and_idempotent(self):
        product = self.create_product("Canva Designs").get_json()["data"]
        invalid = self.client.post(f"/api/v1/creator/products/{product['id']}/resources", headers=self.auth(), json={"template_url": "https://example.com/design"})
        self.assertEqual(invalid.status_code, 400)
        first = self.client.post(f"/api/v1/creator/products/{product['id']}/resources", headers=self.auth(), json={"template_url": "https://www.canva.com/design/first/view"})
        second = self.client.post(f"/api/v1/creator/products/{product['id']}/resources", headers=self.auth(), json={"template_url": "https://canva.com/design/second/view"})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.get_json()["data"]["id"], second.get_json()["data"]["id"])
        self.assertEqual(ProductResource.query.filter_by(product_id=product["id"], resource_type="canva_url").count(), 1)


if __name__ == "__main__":
    unittest.main()

class CatalogueImportTestCase(unittest.TestCase):
    def setUp(self):
        from app.models import CreatorProfile
        from app.services.catalogue import import_catalogue
        self.import_catalogue = import_catalogue
        class TestConfig:
            TESTING = True
            SECRET_KEY = "catalogue-test-key"
            JWT_SECRET_KEY = "catalogue-test-jwt-key"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            FRONTEND_ORIGINS = ["http://localhost:5173"]
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all(ProductCategory(name=name, slug=name.lower().replace(" & ", "-").replace(" ", "-")) for name in CATEGORIES)
        user = User(email="catalogue@example.test")
        user.set_password("safe-passphrase-123")
        user.profile = CreatorProfile(handle="catalogue-maker", display_name="Catalogue Maker")
        db.session.add(user)
        db.session.commit()
        self.creator_id = user.profile.id
        self.temp = Path(tempfile.mkdtemp(prefix="catalogue-import-", dir=Path(__file__).parent))
        self.path = self.temp / "products.json"
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()
        shutil.rmtree(self.temp, ignore_errors=True)

    def write(self, products):
        import json
        self.path.write_text(json.dumps({"products": products}), encoding="utf-8")

    @staticmethod
    def entry(n, label):
        return {"s_no": n, "image_url": f"https://example.test/{n}.jpg", "digital_product_id": f"SR-{n}", "digital_product_name": f"Product {n}", "product_description": f"Description {n}", "product_label": label}

    def test_import_validation_upsert_rollback_and_public_api(self):
        from app.services.catalogue import CatalogueValidationError, load_catalogue
        products = [self.entry(i, label) for i, label in enumerate(("wallpaper", "icon", "art", "canva"), 1)]
        self.write(products)
        self.assertEqual(load_catalogue(self.path), products)
        self.assertEqual(self.import_catalogue(db.session, self.path, self.creator_id), (4, 0))
        self.assertEqual(self.import_catalogue(db.session, self.path, self.creator_id), (0, 4))
        self.assertEqual(Product.query.count(), 4)
        public = self.client.get("/api/v1/products?per_page=48").get_json()["data"]
        self.assertEqual([item["product_label"] for item in public], ["wallpaper", "icon", "art", "canva"])
        self.assertEqual(public[0]["image"], "https://example.test/1.jpg")
        self.assertEqual(self.client.get("/api/v1/products/SR-1").status_code, 200)
        products[0]["digital_product_name"] = "Updated product"
        self.write(products)
        self.assertEqual(self.import_catalogue(db.session, self.path, self.creator_id), (0, 4))
        self.assertEqual(Product.query.filter_by(digital_product_id="SR-1").one().title, "Updated product")
        broken = self.entry(5, "wallpaper")
        broken["image_url"] = "file:///private/image.png"
        self.write([self.entry(6, "icon"), broken])
        with self.assertRaises(CatalogueValidationError):
            self.import_catalogue(db.session, self.path, self.creator_id)
        self.assertIsNone(Product.query.filter_by(digital_product_id="SR-6").first())
        for invalid in ([{"s_no": 1}], [self.entry(1, "course")], [self.entry(1, "art"), self.entry(2, "icon") | {"digital_product_id": "SR-1"} ]):
            self.write(invalid)
            with self.assertRaises(CatalogueValidationError):
                load_catalogue(self.path)
        self.path.write_text("{ invalid", encoding="utf-8")
        with self.assertRaises(CatalogueValidationError):
            load_catalogue(self.path)

    def test_database_failure_rolls_back_the_whole_import(self):
        from sqlalchemy import event
        entries = [self.entry(1, "wallpaper"), self.entry(2, "art")]
        self.write(entries)
        def reject_second(_mapper, _connection, product):
            if product.digital_product_id == "SR-2":
                raise RuntimeError("simulated database failure")
        event.listen(Product, "before_insert", reject_second)
        try:
            with self.assertRaises(RuntimeError):
                self.import_catalogue(db.session, self.path, self.creator_id)
        finally:
            event.remove(Product, "before_insert", reject_second)
        self.assertEqual(Product.query.count(), 0)
