import csv
import io
from datetime import date

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import jwt_required

from .auth import current_user_id
from .workspaces import current_membership, current_workspace_id
from .categories import get_owned_category
from .extensions import db
from .models import Category, Expense, sum_minor, to_major
from .validation import fail, parse_amount, parse_date, parse_int, require_json

bp = Blueprint("expenses", __name__, url_prefix="/api/expenses")

SORTS = {
    "date": Expense.spent_on, "-date": Expense.spent_on.desc(),
    "amount": Expense.amount_minor, "-amount": Expense.amount_minor.desc(),
}


def filtered_query(workspace_id, args):
    """Shared by list and CSV export so both always apply identical filters."""
    q = Expense.query.filter(Expense.workspace_id == workspace_id)
    start = parse_date(args.get("start_date"), "start_date", required=False)
    end = parse_date(args.get("end_date"), "end_date", required=False)
    if start and end and start > end:
        fail("start_date must be on or before end_date")
    if start:
        q = q.filter(Expense.spent_on >= start)
    if end:
        q = q.filter(Expense.spent_on <= end)
    category_ids = [parse_int(c, "category_id") for c in args.getlist("category_id") if c]
    if category_ids:
        q = q.filter(Expense.category_id.in_(category_ids))
    if args.get("min_amount"):
        q = q.filter(Expense.amount_minor >= parse_amount(args["min_amount"], "min_amount"))
    if args.get("max_amount"):
        q = q.filter(Expense.amount_minor <= parse_amount(args["max_amount"], "max_amount"))
    if args.get("q"):
        q = q.filter(Expense.description.ilike(f"%{args['q']}%"))
    if args.get("created_by"):
        q = q.filter(Expense.created_by == parse_int(args["created_by"], "created_by"))
    sort = args.get("sort", "-date")
    if sort not in SORTS:
        fail(f"sort must be one of {', '.join(SORTS)}")
    return q.order_by(SORTS[sort], Expense.id.desc())


def get_owned_expense(expense_id, workspace_id):
    exp = Expense.query.filter_by(id=expense_id, workspace_id=workspace_id).first()
    if not exp:
        fail("Expense not found", 404)
    return exp


def require_can_modify(exp):
    """In a team, members change only their own expenses; the owner can change any."""
    m = current_membership()
    if m.role != "owner" and exp.created_by != m.user_id:
        fail("You can only change expenses you added", 403)


@bp.get("")
@jwt_required()
def list_expenses():
    q = filtered_query(current_workspace_id(), request.args)
    page = max(parse_int(request.args.get("page"), "page") or 1, 1)
    per_page = min(max(parse_int(request.args.get("per_page"), "per_page") or 25, 1), 100)
    total_minor = q.with_entities(sum_minor(Expense.amount_minor)).order_by(None).scalar()
    p = q.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(
        expenses=[e.to_dict() for e in p.items],
        page=p.page, per_page=p.per_page, total_items=p.total, total_pages=p.pages,
        total_amount=to_major(total_minor),
    )


@bp.post("")
@jwt_required()
def create_expense():
    wid = current_workspace_id()
    data = require_json(request)
    cat = get_owned_category(parse_int(data.get("category_id"), "category_id", required=True), wid)
    spent_on = parse_date(data.get("spent_on") or date.today().isoformat(), "spent_on")
    if spent_on > date.today():
        fail("spent_on cannot be in the future")
    exp = Expense(
        workspace_id=wid, created_by=current_user_id(), category_id=cat.id, amount_minor=parse_amount(data.get("amount")),
        description=str(data.get("description", "")).strip()[:255], spent_on=spent_on,
    )
    db.session.add(exp)
    db.session.commit()
    return jsonify(expense=exp.to_dict()), 201


@bp.get("/<int:expense_id>")
@jwt_required()
def get_expense(expense_id):
    return jsonify(expense=get_owned_expense(expense_id, current_workspace_id()).to_dict())


@bp.patch("/<int:expense_id>")
@jwt_required()
def update_expense(expense_id):
    wid = current_workspace_id()
    exp = get_owned_expense(expense_id, wid)
    require_can_modify(exp)
    data = require_json(request)
    if "amount" in data:
        exp.amount_minor = parse_amount(data["amount"])
    if "category_id" in data:
        exp.category_id = get_owned_category(parse_int(data["category_id"], "category_id", True), wid).id
    if "spent_on" in data:
        d = parse_date(data["spent_on"], "spent_on")
        if d > date.today():
            fail("spent_on cannot be in the future")
        exp.spent_on = d
    if "description" in data:
        exp.description = str(data["description"]).strip()[:255]
    db.session.commit()
    return jsonify(expense=exp.to_dict())


@bp.delete("/<int:expense_id>")
@jwt_required()
def delete_expense(expense_id):
    exp = get_owned_expense(expense_id, current_workspace_id())
    require_can_modify(exp)
    db.session.delete(exp)
    db.session.commit()
    return "", 204


def _csv_safe(value: str) -> str:
    """Block CSV/formula injection: Excel executes cells starting with = + - @ tab or CR."""
    return "'" + value if value and value[0] in ("=", "+", "-", "@", "\t", "\r") else value


@bp.get("/export")
@jwt_required()
def export_csv():
    rows = filtered_query(current_workspace_id(), request.args).join(Category).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "date", "category", "description", "amount", "added_by"])
    for e in rows:
        writer.writerow([e.id, e.spent_on.isoformat(), _csv_safe(e.category.name),
                         _csv_safe(e.description), to_major(e.amount_minor), _csv_safe(e.author.name)])
    filename = f"expenses_{date.today().isoformat()}.csv"
    return Response(
        "﻿" + buf.getvalue(),  # BOM so Excel opens UTF-8 (e.g. ₦) correctly
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )