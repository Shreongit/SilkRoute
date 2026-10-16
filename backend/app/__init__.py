from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager

load_dotenv()

from app.config import Config
from app.extensions import db, jwt, migrate
from app.routes.api import api
from app import models  # noqa: F401 -- register model metadata for migrations
from app.models import RevokedToken


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGINS"]}})
    app.register_blueprint(api)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"data": None, "error": {"code": "not_found", "message": "Resource not found."}}), 404

    @app.errorhandler(500)
    def server_error(_error):
        return jsonify({"data": None, "error": {"code": "internal_error", "message": "An unexpected error occurred."}}), 500

    @app.errorhandler(413)
    def upload_too_large(_error):
        return jsonify({"data": None, "error": {"code": "upload_too_large", "message": "Uploads must be 8 MB or smaller."}}), 413

    @app.errorhandler(HTTPException)
    def http_error(error):
        code = (error.name or "http_error").lower().replace(" ", "_")
        return jsonify({"data": None, "error": {"code": code, "message": error.description}}), error.code

    @jwt.unauthorized_loader
    def missing_token(_reason):
        return jsonify({"data": None, "error": {"code": "authentication_required", "message": "Sign in to continue."}}), 401

    @jwt.invalid_token_loader
    def invalid_token(_reason):
        return jsonify({"data": None, "error": {"code": "invalid_token", "message": "Sign in again to continue."}}), 401

    @jwt.token_in_blocklist_loader
    def token_is_revoked(_header, payload):
        return db.session.get(RevokedToken, payload["jti"]) is not None

    return app
