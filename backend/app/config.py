import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load <project>/.env if present. Real environment variables always win over the file.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


def postgres_url(raw: str) -> str:
    """Normalise a Postgres URL to the psycopg 3 driver; '' for anything that isn't Postgres."""
    url = (raw or "").strip()
    for prefix in ("postgresql+psycopg://", "postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return ""


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development").lower()
    SQLALCHEMY_DATABASE_URI = postgres_url(os.environ.get("DATABASE_URL", ""))
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    SECRET_KEY = JWT_SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)  # contract: token lifetime 24 hours


class TestConfig(Config):
    """Tests need their own throwaway Postgres database: every table is dropped after each test."""
    TESTING = True
    APP_ENV = "test"
    SQLALCHEMY_DATABASE_URI = postgres_url(os.environ.get("TEST_DATABASE_URL", ""))
    JWT_SECRET_KEY = SECRET_KEY = "test-secret-key-that-is-long-enough-32b"
