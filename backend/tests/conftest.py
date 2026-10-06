import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _register(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 201, r.json
    return {"Authorization": f"Bearer {r.json['access_token']}"}


@pytest.fixture
def auth(client):
    return _register(client, "alice@example.com")


@pytest.fixture
def other_auth(client):
    return _register(client, "bob@example.com")


@pytest.fixture
def cats(client, auth):
    return {c["name"]: c["id"] for c in client.get("/api/categories", headers=auth).json["categories"]}
