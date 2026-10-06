import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from .workspaces import current_workspace_id
from .extensions import db
from .models import PALETTE, Budget, Category, Expense
from .validation import fail, require_json

bp = Blueprint("categories", __name__, url_prefix="/api/categories")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def get_owned_category(category_id, workspace_id):
    cat = Category.query.filter_by(id=category_id, workspace_id=workspace_id).first()
    if not cat:
        fail("Category not found", 404)
    return cat


def _clean_name(data):
    name = str(data.get("name", "")).strip()
    if not 1 <= len(name) <= 50:
        fail("name must be 1-50 characters")
    return name


def _clean_color(data, default):    #check what this code does"!
    color = data.get("color", default)
    if not HEX_RE.match(str(color)):
        fail("color must be a hex value like #2a78d6")
    return color


def _ensure_unique(workspace_id, name, exclude_id=None):
    q = Category.query.filter(Category.workspace_id == workspace_id, db.func.lower(Category.name) == name.lower())
    if exclude_id:
        q = q.filter(Category.id != exclude_id)
    if q.first():
        fail("A category with this name already exists", 409)


@bp.get("")
@jwt_required()
def list_categories():
    cats = Category.query.filter_by(workspace_id=current_workspace_id()).order_by(Category.name).all()
    return jsonify(categories=[c.to_dict() for c in cats])


@bp.post("")
@jwt_required()
def create_category():
    wid = current_workspace_id()
    data = require_json(request)
    name = _clean_name(data)
    _ensure_unique(wid, name)
    count = Category.query.filter_by(workspace_id=wid).count()
    cat = Category(workspace_id=wid, name=name, color=_clean_color(data, PALETTE[count % len(PALETTE)]))
    db.session.add(cat)
    db.session.commit()
    return jsonify(category=cat.to_dict()), 201


@bp.patch("/<int:category_id>")
@jwt_required()
def update_category(category_id):
    wid = current_workspace_id()
    cat = get_owned_category(category_id, wid)
    data = require_json(request)
    if "name" in data:
        name = _clean_name(data)
        _ensure_unique(wid, name, exclude_id=cat.id)
        cat.name = name
    if "color" in data:
        cat.color = _clean_color(data, cat.color)
    db.session.commit()
    return jsonify(category=cat.to_dict())


@bp.delete("/<int:category_id>")
@jwt_required()
def delete_category(category_id):
    """Refuses to delete a category in use unless ?reassign_to=<id> moves its expenses first."""
    wid = current_workspace_id()
    cat = get_owned_category(category_id, wid)
    in_use = Expense.query.filter_by(category_id=cat.id).count()
    if in_use:
        target_id = request.args.get("reassign_to", type=int)
        if not target_id:
            fail(f"Category has {in_use} expense(s). Pass ?reassign_to=<category_id> to move them.", 409)
        target = get_owned_category(target_id, wid)
        if target.id == cat.id:
            fail("Cannot reassign to the same category")
        Expense.query.filter_by(category_id=cat.id).update({"category_id": target.id})
    # Delete explicitly: an orphaned budget (category_id -> NULL) would silently become the overall budget.
    Budget.query.filter_by(workspace_id=wid, category_id=cat.id).delete()
    db.session.delete(cat)
    db.session.commit()
    return "", 204
