import logging
import secrets

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db, jwt


@event.listens_for(Engine, "connect")
def _sqlite_fk_on(dbapi_conn, _record):
    """SQLite ignores foreign keys unless asked; turn enforcement on."""
    if dbapi_conn.__class__.__module__.startswith("sqlite3"):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


log = logging.getLogger("expense_app")
DEV_FALLBACK_NOTE = "JWT_SECRET_KEY is not set: using a random key for this run. Everyone is signed out on restart."


def _check_config(app):
    """Fail fast on unsafe production config instead of silently using defaults."""
    cfg, env = app.config, app.config["APP_ENV"]
    secret = cfg.get("JWT_SECRET_KEY")
    if env == "production":
        problems = []
        if not secret:
            problems.append("JWT_SECRET_KEY is not set")
        elif len(secret) < 32:
            problems.append("JWT_SECRET_KEY must be at least 32 characters")
        if not cfg.get("DATABASE_URL_SET"):
            problems.append("DATABASE_URL is not set (refusing to fall back to a local SQLite file)")
        if problems:
            raise RuntimeError("Unsafe production config: " + "; ".join(problems))
    elif not secret:
        # Random per run, never a value written in the code (a known key lets anyone forge tokens).
        cfg["JWT_SECRET_KEY"] = cfg["SECRET_KEY"] = secrets.token_urlsafe(48)
        log.warning(DEV_FALLBACK_NOTE)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    _check_config(app)
    db.init_app(app)
    jwt.init_app(app)

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
         allow_headers=["Authorization", "Content-Type", "X-Workspace-Id"],
         expose_headers=["Content-Disposition"],  # lets the frontend read the CSV filename
         methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])

    from . import auth, budgets, categories, expenses, reports, workspaces
    for module in (auth, workspaces, categories, expenses, budgets, reports):
        app.register_blueprint(module.bp)

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    @app.get("/")
    def dashboard():
        return render_template("index.html")

    @app.errorhandler(HTTPException)
    def http_error(e):
        if e.response is not None:  # already a JSON response from validation.fail()
            return e.response
        return jsonify(error=e.description), e.code

    @jwt.unauthorized_loader
    @jwt.invalid_token_loader
    def _bad_token(reason):
        return jsonify(error=f"Authentication required: {reason}"), 401

    @jwt.revoked_token_loader
    def _revoked(_header, _payload):
        return jsonify(error="You've signed out. Please sign in again."), 401

    @jwt.expired_token_loader
    def _expired(_header, _payload):
        return jsonify(error="Token expired, please log in again"), 401

    with app.app_context():
        db.create_all()
        app.config["DATABASE_DISPLAY"] = db.engine.url.render_as_string(hide_password=True)
    if app.config["APP_ENV"] != "test":
        log.warning("Database: %s", app.config["DATABASE_DISPLAY"])
    return app
