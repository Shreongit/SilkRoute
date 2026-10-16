import os
from pathlib import Path
import re
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
RESOURCE_BUNDLE = {"ZIP"}


class LocalStorage:
    """Development-only private store. Keys are never returned by public serializers."""

    def __init__(self):
        configured = current_app.config.get("LOCAL_MEDIA_DIR")
        self.root = Path(configured) if configured else Path(current_app.instance_path) / "private-media"

    def save_preview(self, file_storage):
        original = secure_filename(file_storage.filename or "")
        suffix = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError("Preview images must be PNG, JPG, JPEG, or WEBP.")
        if not self._valid_content(file_storage, suffix.upper()):
            raise ValueError("The image contents do not match the selected file type.")
        self.root.mkdir(parents=True, exist_ok=True)
        key = f"previews/{uuid4().hex}.{suffix}"
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_storage.save(destination)
        return key, f"/media/{Path(key).name}"

    def save_private_resource(self, file_storage, allowed_formats):
        original = secure_filename(file_storage.filename or "")
        suffix = original.rsplit(".", 1)[-1].upper() if "." in original else ""
        if suffix not in allowed_formats and suffix not in RESOURCE_BUNDLE:
            raise ValueError("This file format is not permitted for the selected product category.")
        if not self._valid_content(file_storage, suffix):
            raise ValueError("The file contents do not match the selected file format.")
        self.root.mkdir(parents=True, exist_ok=True)
        key = f"resources/{uuid4().hex}.{suffix.lower()}"
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_storage.save(destination)
        return key, suffix, destination.stat().st_size

    @staticmethod
    def _valid_content(file_storage, suffix):
        head = file_storage.stream.read(4096)
        file_storage.stream.seek(0)
        if suffix == "PNG":
            return head.startswith(b"\x89PNG\r\n\x1a\n")
        if suffix in {"JPG", "JPEG"}:
            return head.startswith(b"\xff\xd8\xff")
        if suffix == "WEBP":
            return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
        if suffix == "PSD":
            return head.startswith(b"8BPS")
        if suffix == "ZIP":
            return head.startswith(b"PK\x03\x04")
        if suffix in {"AI", "EPS"}:
            return head.startswith((b"%!PS", b"%PDF-"))
        if suffix == "SVG":
            return bool(re.search(rb"<svg(?:\s|>)", head, re.IGNORECASE))
        return False

    def delete(self, key):
        root = self.root.resolve()
        destination = (root / key).resolve()
        if root not in destination.parents:
            return
        if destination.is_file():
            destination.unlink()
