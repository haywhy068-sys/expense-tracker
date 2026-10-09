import logging
import secrets

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db, jwt

log = logging.getLogger("spendwise")


def _check_config(app):
    cfg = app.config
    if not cfg.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL is missing or not a Postgres URL, "
                           "e.g. postgresql://user:password@db:5432/spendwise")
    secret = cfg.get("JWT_SECRET_KEY")
    if cfg["APP_ENV"] == "production":
        if not secret or len(secret) < 32:
            raise RuntimeError("JWT_SECRET_KEY must be set and at least 32 characters in production.")
    elif not secret:
        # Random per run, never a value written in the code (a known key lets anyone forge tokens).
        cfg["JWT_SECRET_KEY"] = cfg["SECRET_KEY"] = secrets.token_urlsafe(48)
        log.warning("JWT_SECRET_KEY is not set: using a random key for this run. Everyone is signed out on restart.")


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    _check_config(app)
    db.init_app(app)
    jwt.init_app(app)

    from . import auth, budgets, categories, expenses, health
    for module in (health, auth, expenses, categories, budgets):
        app.register_blueprint(module.bp)

    # Contract: every error is {"error": "..."}.
    @app.errorhandler(HTTPException)
    def http_error(e):
        if e.response is not None:  # already JSON, from validation.fail()
            return e.response
        messages = {404: "Not found", 405: "Method not allowed", 400: "Malformed JSON"}
        return jsonify(error=messages.get(e.code, e.description)), e.code

    @app.errorhandler(Exception)
    def unexpected(e):
        log.exception("Unhandled error")
        return jsonify(error="Internal server error"), 500

    @jwt.unauthorized_loader
    @jwt.invalid_token_loader
    def _no_token(_reason):
        return jsonify(error="Not signed in"), 401

    @jwt.expired_token_loader
    def _expired(_header, _payload):
        return jsonify(error="Session expired, please sign in again"), 401

    with app.app_context():
        from sqlalchemy.exc import OperationalError
        try:
            db.create_all()
        except OperationalError as e:
            reason = str(e.orig).splitlines()[0] if e.orig else str(e)
            raise RuntimeError(f"Could not connect to the database: {reason}. Check DATABASE_URL.") from None
        shown = db.engine.url.render_as_string(hide_password=True)
    if app.config["APP_ENV"] != "test":
        log.warning("Database: %s", shown)
    return app
