import logging
import secrets

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db, jwt

log = logging.getLogger("expense_api")


def _check_config(app):
    """Fail fast with a readable message instead of a 100-line traceback or an unsafe default."""
    cfg = app.config
    if not cfg.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL is missing or not a Postgres URL. Set it to your Supabase "
                           "Session pooler URI: postgresql://postgres.<ref>:<password>@<host>:5432/postgres?sslmode=require")
    secret = cfg.get("JWT_SECRET_KEY")
    if cfg["APP_ENV"] == "production":
        if not secret or len(secret) < 32:
            raise RuntimeError("JWT_SECRET_KEY must be set and at least 32 characters in production.")
    elif not secret:
        # Random per run, never a value written in the code (a known key lets anyone forge tokens).
        cfg["JWT_SECRET_KEY"] = cfg["SECRET_KEY"] = secrets.token_urlsafe(48)
        log.warning("JWT_SECRET_KEY is not set: using a random key for this run. Everyone is signed out on restart.")


def _prepare_database(app):
    """Create missing tables, then enable Row Level Security on each one.
    Supabase exposes the public schema through its Data API; RLS with no policies blocks that API
    entirely. This app connects as the table owner (`postgres`), which bypasses RLS, so it is unaffected."""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    try:
        db.create_all()
        with db.engine.begin() as conn:
            for table in db.metadata.sorted_tables:
                conn.execute(text(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY'))
    except OperationalError as e:
        reason = str(e.orig).splitlines()[0] if e.orig else str(e)
        raise RuntimeError(f"Could not connect to the database: {reason}. Check DATABASE_URL "
                           "(Session pooler URI, database password, ?sslmode=require).") from None


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

    from . import auth, budgets, categories, expenses, health, reports, workspaces
    for module in (health, auth, workspaces, categories, expenses, budgets, reports):
        app.register_blueprint(module.bp)

    @app.errorhandler(HTTPException)
    def http_error(e):
        if e.response is not None:  # already a JSON response from validation.fail()
            return e.response
        return jsonify(error=e.description), e.code

    @app.errorhandler(Exception)
    def unexpected_error(e):
        log.exception("Unhandled error")  # full detail in the server log, never sent to the client
        return jsonify(error="Internal server error"), 500

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
        _prepare_database(app)
        shown = db.engine.url.render_as_string(hide_password=True)
    if app.config["APP_ENV"] != "test":
        log.warning("Database: %s", shown)
    return app
