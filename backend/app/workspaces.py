from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import jwt_required

from .auth import current_user_id
from .extensions import db
from .models import DEFAULT_CATEGORIES, PALETTE, Budget, Category, Expense, Membership, User, Workspace
from .validation import fail, require_json

bp = Blueprint("workspaces", __name__, url_prefix="/api/workspaces")
WORKSPACE_HEADER = "X-Workspace-Id"


def create_workspace(owner_id, name, kind):
    ws = Workspace(name=name, kind=kind)
    db.session.add(ws)
    db.session.flush()
    db.session.add(Membership(workspace_id=ws.id, user_id=owner_id, role="owner"))
    for i, cat in enumerate(DEFAULT_CATEGORIES):
        db.session.add(Category(workspace_id=ws.id, name=cat, color=PALETTE[i % len(PALETTE)]))
    return ws


def current_membership() -> Membership:
    """Which workspace a request acts on: the X-Workspace-Id header (or ?workspace_id= for plain
    download links), else the caller's personal workspace. A workspace you're not in is a 404."""
    if "membership" in g:
        return g.membership
    uid = current_user_id()
    raw = request.headers.get(WORKSPACE_HEADER) or request.args.get("workspace_id")
    q = Membership.query.filter_by(user_id=uid)
    if raw:
        try:
            m = q.filter_by(workspace_id=int(raw)).first()
        except ValueError:
            fail(f"{WORKSPACE_HEADER} must be an integer", 400)
    else:
        m = q.join(Workspace).filter(Workspace.kind == "personal").first()
    if not m:
        fail("Workspace not found", 404)
    g.membership = m
    return m


def current_workspace_id() -> int:
    return current_membership().workspace_id


def _membership_for(workspace_id):
    m = Membership.query.filter_by(workspace_id=workspace_id, user_id=current_user_id()).first()
    if not m:
        fail("Workspace not found", 404)
    return m


def _require_owner(m):
    if m.role != "owner":
        fail("Only the workspace owner can do this", 403)


def _clean_name(data):
    name = str(data.get("name", "")).strip()
    if not 1 <= len(name) <= 80:
        fail("name must be 1-80 characters")
    return name


@bp.get("")
@jwt_required()
def list_workspaces():
    uid = current_user_id()
    counts = dict(db.session.query(Membership.workspace_id, db.func.count(Membership.id))
                  .group_by(Membership.workspace_id).all())
    rows = (Membership.query.filter_by(user_id=uid).join(Workspace)
            .order_by(Workspace.kind.desc(), Workspace.name).all())  # personal first
    return jsonify(workspaces=[m.workspace.to_dict(m.role, counts.get(m.workspace_id, 1)) for m in rows])


@bp.post("")
@jwt_required()
def create_team():
    data = require_json(request)
    ws = create_workspace(current_user_id(), _clean_name(data), "team")
    db.session.commit()
    return jsonify(workspace=ws.to_dict("owner", 1)), 201


@bp.get("/<int:workspace_id>")
@jwt_required()
def get_workspace(workspace_id):
    m = _membership_for(workspace_id)
    count = Membership.query.filter_by(workspace_id=workspace_id).count()
    return jsonify(workspace=m.workspace.to_dict(m.role, count))


@bp.patch("/<int:workspace_id>")
@jwt_required()
def rename_workspace(workspace_id):
    m = _membership_for(workspace_id)
    _require_owner(m)
    m.workspace.name = _clean_name(require_json(request))
    db.session.commit()
    return jsonify(workspace=m.workspace.to_dict(m.role))


@bp.delete("/<int:workspace_id>")
@jwt_required()
def delete_workspace(workspace_id):
    m = _membership_for(workspace_id)
    _require_owner(m)
    if m.workspace.kind == "personal":
        fail("Your personal workspace can't be deleted", 409)
    # Explicit order so it works whether or not the database enforces ON DELETE CASCADE.
    for model in (Budget, Expense, Category, Membership):
        model.query.filter_by(workspace_id=workspace_id).delete()
    db.session.delete(m.workspace)
    db.session.commit()
    return "", 204


# ---------- members ----------
@bp.get("/<int:workspace_id>/members")
@jwt_required()
def list_members(workspace_id):
    _membership_for(workspace_id)
    rows = Membership.query.filter_by(workspace_id=workspace_id).join(User).order_by(Membership.joined_at).all()
    return jsonify(members=[{**r.user.to_dict(), "role": r.role} for r in rows])


@bp.post("/<int:workspace_id>/members")
@jwt_required()
def add_member(workspace_id):
    """Adds an existing account by email. There's no email-invite flow: the person must sign up first."""
    m = _membership_for(workspace_id)
    _require_owner(m)
    if m.workspace.kind == "personal":
        fail("You can't add members to a personal workspace. Create a team instead.", 409)
    email = str(require_json(request).get("email", "")).strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        fail("No account with that email. Ask them to sign up first.", 404)
    if Membership.query.filter_by(workspace_id=workspace_id, user_id=user.id).first():
        fail("Already a member", 409)
    db.session.add(Membership(workspace_id=workspace_id, user_id=user.id, role="member"))
    db.session.commit()
    return jsonify(member={**user.to_dict(), "role": "member"}), 201


@bp.delete("/<int:workspace_id>/members/<int:user_id>")
@jwt_required()
def remove_member(workspace_id, user_id):
    """Owner removes anyone else; a member can remove themselves (leave). The owner can't leave."""
    me = _membership_for(workspace_id)
    target = Membership.query.filter_by(workspace_id=workspace_id, user_id=user_id).first()
    if not target:
        fail("Member not found", 404)
    if target.role == "owner":
        fail("The owner can't be removed. Delete the workspace instead.", 409)
    if me.user_id != user_id:
        _require_owner(me)
    db.session.delete(target)
    db.session.commit()
    return "", 204
