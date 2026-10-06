from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from .workspaces import current_membership
from .extensions import db
from .models import Budget, Category, Expense, sum_minor, to_major
from .validation import fail, parse_int, parse_month

bp = Blueprint("reports", __name__, url_prefix="/api/reports")
WARN_AT = 0.8  # flag a budget once 80% is spent


def budget_status(spent, limit):
    ratio = spent / limit if limit else 0
    state = "over" if spent > limit else "warning" if ratio >= WARN_AT else "ok"
    return {"limit": to_major(limit), "spent": to_major(spent),
            "remaining": to_major(limit - spent), "used_pct": round(ratio * 100, 1), "status": state}


@bp.get("/monthly")
@jwt_required()
def monthly_summary():
    ws = current_membership().workspace
    wid = ws.id
    start, end = parse_month(request.args.get("month"))
    in_month = (Expense.workspace_id == wid, Expense.spent_on >= start, Expense.spent_on < end)

    total, count = db.session.query(
        sum_minor(Expense.amount_minor), db.func.count(Expense.id)
    ).filter(*in_month).one()

    by_cat_rows = (
        db.session.query(Category, sum_minor(Expense.amount_minor), db.func.count(Expense.id))
        .join(Expense, Expense.category_id == Category.id)
        .filter(*in_month).group_by(Category.id)
        .order_by(sum_minor(Expense.amount_minor).desc(), Category.name).all()
    )
    spent_by_cat = {c.id: s for c, s, _ in by_cat_rows}

    daily_rows = (
        db.session.query(Expense.spent_on, sum_minor(Expense.amount_minor))
        .filter(*in_month).group_by(Expense.spent_on).order_by(Expense.spent_on).all()
    )

    # Zero-filled: one entry per day of the month so the chart has no gaps.
    by_day = dict(daily_rows)
    daily = []
    d = start
    while d < end:
        daily.append({"date": d.isoformat(), "total": to_major(by_day.get(d, 0))})
        d += timedelta(days=1)

    budgets = []
    for b in Budget.query.filter_by(workspace_id=wid).all():
        spent = total if b.category_id is None else spent_by_cat.get(b.category_id, 0)
        budgets.append({"id": b.id, "category": b.category.to_dict() if b.category else None,
                        **budget_status(spent, b.amount_minor)})
    budgets.sort(key=lambda x: (x["category"] is not None, -x["used_pct"]))

    overall = next((b for b in budgets if b["category"] is None), None)
    return jsonify(
        workspace=ws.to_dict(),
        month=start.strftime("%Y-%m"),
        currency=ws.currency,
        total=to_major(total),
        overall_budget=overall,
        expense_count=count,
        by_category=[{"category": c.to_dict(), "total": to_major(s), "count": n,
                      "share_pct": round(s / total * 100, 1) if total else 0}
                     for c, s, n in by_cat_rows],
        daily=daily,
        budgets=budgets,
    )


@bp.get("/trend")
@jwt_required()
def monthly_trend():
    """Totals for the last N months (including the current one), zero-filled."""
    wid = current_membership().workspace_id
    months = parse_int(request.args.get("months"), "months") or 6
    if not 1 <= months <= 24:
        fail("months must be between 1 and 24")
    today = date.today()
    keys = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    keys.reverse()
    first = date(int(keys[0][:4]), int(keys[0][5:]), 1)

    # extract() is portable (SQLite, Postgres, MySQL); strftime would lock us to SQLite.
    yr, mo = db.extract("year", Expense.spent_on), db.extract("month", Expense.spent_on)
    rows = {
        f"{int(y):04d}-{int(m):02d}": s
        for y, m, s in db.session.query(yr, mo, sum_minor(Expense.amount_minor))
        .filter(Expense.workspace_id == wid, Expense.spent_on >= first).group_by(yr, mo).all()
    }
    overall = Budget.query.filter_by(workspace_id=wid, category_id=None).first()
    return jsonify(
        months=[{"month": k, "total": to_major(rows.get(k, 0))} for k in keys],
        overall_budget=to_major(overall.amount_minor) if overall else None,
    )
