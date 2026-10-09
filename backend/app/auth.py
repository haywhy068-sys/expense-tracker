
import base64
import hashlib

import bcrypt
from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity

from . import validation as v
from .extensions import db
from .models import User

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _prehash(password: str) -> bytes:
    # bcrypt only reads the first 72 bytes, but the contract allows 128 characters (up to 512 bytes in UTF-8).
    # SHA-256 first, so every character counts; base64 so there are no NUL bytes for bcrypt to stop at.
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), hashed.encode())
    except ValueError:
        return False


def current_user_id() -> int:
    return int(get_jwt_identity())


def _session(user, status):
    return jsonify(token=create_access_token(identity=str(user.id)), user=user.to_dict()), status


@bp.post("/register")
def register():
    data = v.json_body()
    email = v.email(data.get("email"))
    password = v.password(data.get("password"))
    if User.query.filter_by(email=email).first():
        v.fail("Email already registered", 409)
    user = User(email=email, password_hash=hash_password(password))
    db.session.add(user)
    db.session.commit()
    return _session(user, 201)


@bp.post("/login")
def login():
    data = v.json_body()
    email = data.get("email")
    password = data.get("password")
    user = User.query.filter_by(email=email.strip().lower()).first() if isinstance(email, str) else None
    # One message for unknown email and wrong password, so accounts can't be probed.
    if not user or not isinstance(password, str) or not check_password(password, user.password_hash):
        v.fail("Invalid email or password", 401)
    return _session(user, 200)
