from datetime import date
from decimal import Decimal, InvalidOperation

from flask import abort, jsonify, make_response

MAX_AMOUNT_MINOR = 10**13  # 100 billion in major units; a sanity cap, not a business rule


def fail(message, status=422, **extra):
    abort(make_response(jsonify({"error": message, **extra}), status))


def require_json(request):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        fail("Request body must be a JSON object", 400)
    return data


def parse_amount(value, field="amount"):
    """Accepts '1500', '1500.5', 1500.50 -> integer minor units. Rejects >2 decimals and <= 0."""
    if isinstance(value, bool) or value is None:
        fail(f"{field} is required")
    try:
        dec = Decimal(str(value))
    except InvalidOperation:
        fail(f"{field} must be a number")
    if not dec.is_finite():
        fail(f"{field} must be a number")
    if dec <= 0:
        fail(f"{field} must be greater than 0")
    if dec != dec.quantize(Decimal("0.01")):
        fail(f"{field} can have at most 2 decimal places")
    minor = int(dec * 100)
    if minor > MAX_AMOUNT_MINOR:
        fail(f"{field} is too large")
    return minor


def parse_date(value, field="date", required=True):
    if value in (None, ""):
        if required:
            fail(f"{field} is required")
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        fail(f"{field} must be YYYY-MM-DD")


def parse_month(value):
    """'2026-10' -> (first_day, first_day_of_next_month). Defaults to current month."""
    if not value:
        today = date.today()
        y, m = today.year, today.month
    else:
        try:
            y, m = (int(p) for p in str(value).split("-"))
            date(y, m, 1)
        except (ValueError, TypeError):
            fail("month must be YYYY-MM")
    start = date(y, m, 1)
    end = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return start, end


def parse_int(value, field, required=False):
    if value in (None, ""):
        if required:
            fail(f"{field} is required")
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        fail(f"{field} must be an integer")
