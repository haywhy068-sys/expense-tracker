import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required

from .extensions import db, jwt
from .models import RevokedToken, User
from .validation import fail, require_json

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def current_user_id() -> int:
    return int(get_jwt_identity())


@jwt.token_in_blocklist_loader
def _is_revoked(_header, payload):
    return db.session.get(RevokedToken, payload["jti"]) is not None


def _session(user):
    from .models import Membership, Workspace
    personal = (Membership.query.filter_by(user_id=user.id).join(Workspace)
                .filter(Workspace.kind == "personal").first())
    return {"user": user.to_dict(), "access_token": create_access_token(identity=str(user.id)),
            "default_workspace_id": personal.workspace_id if personal else None}


def _valid_password(pw, field="password"):
    if len(pw) < 8:
        fail(f"{field} must be at least 8 characters")
    return pw


@bp.post("/register")
def register():
    from .workspaces import create_workspace  # local import avoids a circular import
    data = require_json(request)
    email = str(data.get("email", "")).strip().lower()
    password = _valid_password(str(data.get("password", "")))
    if not EMAIL_RE.match(email):
        fail("A valid email is required")
    name = str(data.get("name") or email.split("@")[0]).strip()[:80]
    if User.query.filter_by(email=email).first():
        fail("An account with this email already exists", 409)

    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    create_workspace(user.id, "Personal", "personal")
    db.session.commit()
    return jsonify(_session(user)), 201


@bp.post("/login")
def login():
    data = require_json(request)
    user = User.query.filter_by(email=str(data.get("email", "")).strip().lower()).first()
    # Same message for unknown email and wrong password: don't leak which accounts exist.
    if not user or not user.check_password(str(data.get("password", ""))):
        fail("Invalid email or password", 401)
    return jsonify(_session(user))


@bp.post("/logout")
@jwt_required()
def logout():
    db.session.add(RevokedToken(jti=get_jwt()["jti"]))
    db.session.commit()
    return "", 204


def _me():
    user = db.session.get(User, current_user_id())
    if not user:
        fail("User not found", 404)
    return user


@bp.get("/me")
@jwt_required()
def me():
    return jsonify(user=_me().to_dict())


@bp.patch("/me")
@jwt_required()
def update_me():
    user = _me()
    name = str(require_json(request).get("name", "")).strip()
    if not 1 <= len(name) <= 80:
        fail("name must be 1-80 characters")
    user.name = name
    db.session.commit()
    return jsonify(user=user.to_dict())


@bp.post("/password")
@jwt_required()
def change_password():
    user = _me()
    data = require_json(request)
    if not user.check_password(str(data.get("current_password", ""))):
        fail("Current password is incorrect", 401)
    user.set_password(_valid_password(str(data.get("new_password", "")), "new_password"))
    db.session.commit()
    return "", 204
