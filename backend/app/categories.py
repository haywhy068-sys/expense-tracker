from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from .models import CATEGORIES

bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@bp.get("")
@jwt_required()
def list_categories():
    return jsonify(CATEGORIES)
