import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load <project>/.env if present. Real environment variables always win over the file.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _normalise(url):
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _database_url():
    """DATABASE_URL, with the common host-provided 'postgres://' prefix normalised.
    SQLAlchemy 2 rejects 'postgres://', and a bare 'postgresql://' would look for psycopg2."""
    url = os.environ.get("DATABASE_URL", "").strip()
    return _normalise(url) if url else None


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development").lower()
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")          # validated in create_app()
    SECRET_KEY = os.environ.get("SECRET_KEY") or JWT_SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.environ.get("JWT_EXPIRES_HOURS", "8")))
    DATABASE_URL_SET = _database_url() is not None
    # Fallback: SQLite file. Flask-SQLAlchemy puts a relative SQLite path in the instance/ folder.
    SQLALCHEMY_DATABASE_URI = _database_url() or "sqlite:///expenses.db"
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}  # survive dropped Postgres connections
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "NGN")
    # Comma-separated. Vite dev server by default; add your deployed frontend URL here.
    CORS_ORIGINS = [o.strip() for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]


class TestConfig(Config):
    TESTING = True
    APP_ENV = "test"
    # Set TEST_DATABASE_URL to run the suite against Postgres. Use a throwaway database: tables are dropped.
    SQLALCHEMY_DATABASE_URI = _normalise(os.environ.get("TEST_DATABASE_URL", "")) or "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    JWT_SECRET_KEY = "test-secret-key-that-is-long-enough-32b"
    SECRET_KEY = JWT_SECRET_KEY
