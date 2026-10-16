import os
import secrets
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parents[1]
    PRODUCTS_JSON_PATH = os.getenv("PRODUCTS_JSON_PATH", str(BASE_DIR / "data" / "products.json"))
    CATALOGUE_CREATOR_ID = os.getenv("CATALOGUE_CREATOR_ID", "")
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 8
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///silk_route_dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    LOCAL_MEDIA_DIR = os.getenv("LOCAL_MEDIA_DIR", "")
    FRONTEND_ORIGINS = [origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
