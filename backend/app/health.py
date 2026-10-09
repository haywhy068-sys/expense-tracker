import logging

from flask import Blueprint, jsonify
from sqlalchemy import text

from .extensions import db

bp = Blueprint("health", __name__)
log = logging.getLogger("spendwise")


@bp.get("/health")
def health():
    """Contract: 200 {"status":"ok","database":"ok"} or 503 {"status":"error","database":"down"}."""
    try:
        db.session.execute(text("SELECT 1"))
        body, status = {"status": "ok", "database": "ok"}, 200
    except Exception:
        log.exception("Health check: database unreachable")  # detail in the server log only
        db.session.rollback()
        body, status = {"status": "error", "database": "down"}, 503
    resp = jsonify(body)
    resp.status_code = status
    resp.headers["Cache-Control"] = "no-store"
    return resp
