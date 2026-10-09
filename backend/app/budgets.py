from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from . import validation as v
from .auth import current_user_id
from .extensions import db
from .models import Budget, money

bp = Blueprint("budgets", __name__, url_prefix="/api/budgets")


@bp.get("")
@jwt_required()
def get_budget():
    month = v.month(request.args.get("month"))
    b = Budget.query.filter_by(user_id=current_user_id(), month=month).first()
    return jsonify(month=month, limit=money(b.limit) if b else None)  # null when not set


@bp.put("")
@jwt_required()
def set_budget():
    data = v.json_body()
    month = v.month(data.get("month"))
    limit = v.money(data.get("limit"), "limit")
    uid = current_user_id()
    b = Budget.query.filter_by(user_id=uid, month=month).first()
    if b:
        b.limit = limit
    else:
        db.session.add(Budget(user_id=uid, month=month, limit=limit))
    db.session.commit()
    return jsonify(month=month, limit=money(limit))
