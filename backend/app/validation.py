"""Input parsing for the contract's rules. Every failure raises a JSON error response."""
import json
import re
from datetime import date
from decimal import Decimal

from flask import abort, jsonify, make_response, request

from .models import CATEGORIES

MAX_MONEY = Decimal("9999999999.99")  # NUMERIC(12,2)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def fail(message, status=422):
    abort(make_response(jsonify(error=message), status))


def json_body() -> dict:
    """Parse the body with decimals kept exact (120.1 stays 120.1, never a float). 400 if malformed."""
    try:
        data = json.loads(request.get_data(as_text=True) or "null", parse_float=Decimal)
    except (ValueError, UnicodeDecodeError):
        fail("Malformed JSON", 400)
    if not isinstance(data, dict):
        fail("Request body must be a JSON object", 400)
    return data


def money(value, field):
    """A JSON number > 0 with at most 2 decimals, max 9999999999.99. Strings and booleans are rejected."""
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        fail(f"{field} must be a number")
    dec = Decimal(value)
    if not dec.is_finite() or dec <= 0:
        fail(f"{field} must be greater than 0")
    if dec != dec.quantize(Decimal("0.01")):
        fail(f"{field} can have at most 2 decimal places")
    if dec > MAX_MONEY:
        fail(f"{field} must be at most 9999999999.99")
    return dec.quantize(Decimal("0.01"))


def iso_date(value, field, required=True):
    if value in (None, ""):
        if required:
            fail(f"{field} is required")
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        fail(f"{field} must be a valid date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(value)
    except ValueError:
        fail(f"{field} must be a valid date (YYYY-MM-DD)")


def month(value):
    if not isinstance(value, str) or not MONTH_RE.match(value):
        fail("month must be YYYY-MM")
    return value


def category(value):
    if value not in CATEGORIES:
        fail("category must be one of: " + ", ".join(CATEGORIES))
    return value


def description(value):
    if not isinstance(value, str) or not value.strip():
        fail("description is required")
    value = value.strip()
    if len(value) > 140:
        fail("description must be at most 140 characters")
    return value


def email(value):
    value = value.strip().lower() if isinstance(value, str) else ""
    if not value or len(value) > 254 or not EMAIL_RE.match(value):
        fail("A valid email is required (max 254 characters)")
    return value


def password(value):
    if not isinstance(value, str) or not 8 <= len(value) <= 128:
        fail("password must be 8 to 128 characters")
    return value
