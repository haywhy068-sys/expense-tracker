import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load <project>/.env if present. Real environment variables always win over the file.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


def postgres_url(raw: str) -> str:
    """Normalise a Postgres URL (e.g. Supabase's 'postgresql://...') to the psycopg 3 driver.
    Returns '' for anything that isn't Postgres, so callers can reject it."""
    url = (raw or "").strip()
    for prefix in ("postgresql+psycopg://", "postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return ""


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development").lower()
    # Supabase Session pooler URI (port 5432). Validated in create_app().
    SQLALCHEMY_DATABASE_URI = postgres_url(os.environ.get("DATABASE_URL", ""))
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # drop dead pooled connections instead of erroring
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "5")),
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    SECRET_KEY = JWT_SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.environ.get("JWT_EXPIRES_HOURS", "8")))
    CORS_ORIGINS = [o.strip() for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]


class TestConfig(Config):
    """Tests need their own throwaway Postgres database: every table is dropped after each test."""
    TESTING = True
    APP_ENV = "test"
    SQLALCHEMY_DATABASE_URI = postgres_url(os.environ.get("TEST_DATABASE_URL", ""))
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    JWT_SECRET_KEY = SECRET_KEY = "test-secret-key-that-is-long-enough-32b"
