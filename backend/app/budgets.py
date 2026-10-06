from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from .workspaces import current_workspace_id
from .categories import get_owned_category
from .extensions import db
from .models import Budget
from .validation import fail, parse_amount, parse_int, require_json

bp = Blueprint("budgets", __name__, url_prefix="/api/budgets")


@bp.get("")
@jwt_required()
def list_budgets():
    budgets = Budget.query.filter_by(workspace_id=current_workspace_id()).all()
    return jsonify(budgets=[b.to_dict() for b in budgets])


@bp.put("")
@jwt_required()
def upsert_budget():
    """Set the monthly limit for a category, or the overall limit if category_id is null/omitted.
    PUT because it's idempotent: one budget per (user, category)."""
    wid = current_workspace_id()
    data = require_json(request)
    category_id = parse_int(data.get("category_id"), "category_id")
    if category_id is not None:
        get_owned_category(category_id, wid)
    amount = parse_amount(data.get("limit"), "limit")
    budget = Budget.query.filter_by(workspace_id=wid, category_id=category_id).first()
    status = 200
    if not budget:
        budget = Budget(workspace_id=wid, category_id=category_id, amount_minor=amount)
        db.session.add(budget)
        status = 201
    budget.amount_minor = amount
    db.session.commit()
    return jsonify(budget=budget.to_dict()), status


@bp.delete("/<int:budget_id>")
@jwt_required()
def delete_budget(budget_id):
    budget = Budget.query.filter_by(id=budget_id, workspace_id=current_workspace_id()).first()
    if not budget:
        fail("Budget not found", 404)
    db.session.delete(budget)
    db.session.commit()
    return "", 204
