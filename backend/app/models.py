from datetime import datetime, timezone

from .extensions import db

# Contract: fixed, read-only category list.
CATEGORIES = ["Food", "Transport", "Shopping", "Utilities", "Health", "Entertainment", "Education", "Other"]


def utcnow():
    return datetime.now(timezone.utc)


def money(value):
    """NUMERIC(12,2) -> JSON number (contract: money is a number in major units, never a string)."""
    return None if value is None else float(value)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)  # stored lower-cased => case-insensitive
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, server_default=db.func.now())

    def to_dict(self):
        return {"id": self.id, "email": self.email}


class Expense(db.Model):
    __tablename__ = "expenses"
    __table_args__ = (db.Index("ix_expenses_user_date", "user_id", "date"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(140), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, server_default=db.func.now())

    def to_dict(self):
        return {"id": self.id, "date": self.date.isoformat(), "category": self.category,
                "description": self.description, "amount": money(self.amount)}


class Budget(db.Model):
    __tablename__ = "budgets"
    __table_args__ = (db.UniqueConstraint("user_id", "month", name="uq_budgets_user_month"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    # "limit" is an SQL reserved word; SQLAlchemy quotes it. Hand-written SQL must write "limit".
    limit = db.Column("limit", db.Numeric(12, 2), nullable=False)
