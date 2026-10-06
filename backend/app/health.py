"""Health checks for uptime monitors, load balancers and Kubernetes probes. No auth, no CORS.

GET /health        Full check (database included). 200 if healthy, 503 if not.
                   Use for uptime monitoring and readiness probes.
GET /health/live   Process is running; never touches the database. Always 200.
                   Use for liveness probes, so a database outage doesn't restart healthy containers.
GET /api/health    Alias of /health (kept for existing clients and the Postman collection).
"""
import logging
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify
from sqlalchemy import text

from .extensions import db

bp = Blueprint("health", __name__)
log = logging.getLogger("expense_api")
STARTED_AT = time.monotonic()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _uptime():
    return int(time.monotonic() - STARTED_AT)


@bp.get("/health/live")
def live():
    return jsonify(status="ok", uptime_seconds=_uptime(), timestamp=_now())


@bp.get("/health")
@bp.get("/api/health")
def health():
    started = time.perf_counter()
    try:
        db.session.execute(text("SELECT 1"))
        database = {"status": "ok", "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
        healthy = True
    except Exception:
        # Full error goes to the server log only; never expose connection details publicly.
        log.exception("Health check: database unreachable")
        db.session.rollback()
        database = {"status": "unreachable"}
        healthy = False
    body = {"status": "ok" if healthy else "degraded", "checks": {"database": database},
            "uptime_seconds": _uptime(), "timestamp": _now()}
    resp = jsonify(body)
    resp.status_code = 200 if healthy else 503
    resp.headers["Cache-Control"] = "no-store"  # a cached "ok" would hide an outage
    return resp
