import csv
import io
from datetime import date

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import jwt_required

from . import validation as v
from .auth import current_user_id
from .extensions import db
from .models import Expense

bp = Blueprint("expenses", __name__, url_prefix="/api/expenses")


def _filtered(user_id):
    """Shared by the list and the CSV export, so both always apply the same filters and order."""
    q = Expense.query.filter(Expense.user_id == user_id)
    cat = request.args.get("category", "")
    if cat not in ("", "All"):          # contract: "All" or empty = no category filter
        q = q.filter(Expense.category == v.category(cat))
    start = v.iso_date(request.args.get("start_date"), "start_date", required=False)
    end = v.iso_date(request.args.get("end_date"), "end_date", required=False)
    if start and end and start > end:
        v.fail("start_date must be on or before end_date")
    if start:
        q = q.filter(Expense.date >= start)
    if end:
        q = q.filter(Expense.date <= end)
    return q.order_by(Expense.date.desc(), Expense.id.desc())  # contract: newest date, then newest id


def _fields(data):
    """The four required fields (POST and PUT both send all four: PUT is a full replace)."""
    return {"date": v.iso_date(data.get("date"), "date"), "category": v.category(data.get("category")),
            "description": v.description(data.get("description")), "amount": v.money(data.get("amount"), "amount")}


def _owned(expense_id):
    exp = db.session.get(Expense, expense_id)
    if not exp or exp.user_id != current_user_id():
        v.fail("Expense not found", 404)  # contract: another user's expense is 404, never 403
    return exp


@bp.get("")
@jwt_required()
def list_expenses():
    return jsonify([e.to_dict() for e in _filtered(current_user_id()).all()])


@bp.post("")
@jwt_required()
def create_expense():
    exp = Expense(user_id=current_user_id(), **_fields(v.json_body()))
    db.session.add(exp)
    db.session.commit()
    return jsonify(exp.to_dict()), 201


@bp.put("/<int:expense_id>")
@jwt_required()
def replace_expense(expense_id):
    exp = _owned(expense_id)
    for key, value in _fields(v.json_body()).items():
        setattr(exp, key, value)
    db.session.commit()
    return jsonify(exp.to_dict())


@bp.delete("/<int:expense_id>")
@jwt_required()
def delete_expense(expense_id):
    db.session.delete(_owned(expense_id))
    db.session.commit()
    return "", 204


def _csv_safe(text):
    # Spreadsheets run cells starting with = + - @ as formulas; prefix ' so a description can't execute.
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@bp.get("/export")
@jwt_required()
def export_csv():
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["date", "category", "description", "amount"])
    for e in _filtered(current_user_id()).all():
        writer.writerow([e.date.isoformat(), e.category, _csv_safe(e.description), f"{e.amount:.2f}"])
    return Response(buf.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": f'attachment; filename="expenses_{date.today().isoformat()}.csv"'})
