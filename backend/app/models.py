from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


def sum_minor(column):
    """SUM of a money column as a whole number on every database.
    Postgres returns SUM(bigint) as NUMERIC (Python Decimal); SQLite returns int. Cast so both give int."""
    return db.cast(db.func.coalesce(db.func.sum(column), 0), db.BigInteger)


def to_major(minor: int) -> str:
    """Integer minor units (kobo/cents) -> '1234.50'. Never use floats for money."""
    minor = int(minor)  # defensive: never format a Decimal/float as money
    sign = "-" if minor < 0 else ""
    minor = abs(minor)
    return f"{sign}{minor // 100}.{minor % 100:02d}"


# Fixed categorical order (CVD-validated palette). Colour follows the category,
# assigned once at creation, never re-cycled by rank.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
DEFAULT_CATEGORIES = ["Food", "Transport", "Housing", "Utilities", "Health", "Entertainment", "Shopping", "Other"]


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, default="")
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        initials = "".join(p[0] for p in self.name.split()[:2]).upper() or self.email[0].upper()
        return {"id": self.id, "name": self.name, "email": self.email, "initials": initials}


class Workspace(db.Model):
    """Everything financial (categories, expenses, budgets) belongs to a workspace.
    Every user gets one 'personal' workspace; 'team' workspaces are shared."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    kind = db.Column(db.String(10), nullable=False, default="personal")  # personal | team
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def to_dict(self, role=None, member_count=None):
        d = {"id": self.id, "name": self.name, "kind": self.kind, "currency": self.currency}
        if role:
            d["role"] = role
        if member_count is not None:
            d["member_count"] = member_count
        return d


class Membership(db.Model):
    __table_args__ = (db.UniqueConstraint("workspace_id", "user_id", name="uq_membership"),)
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(10), nullable=False, default="member")  # owner | member
    joined_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    workspace = db.relationship("Workspace")
    user = db.relationship("User")


class Category(db.Model):
    __table_args__ = (db.UniqueConstraint("workspace_id", "name", name="uq_category_ws_name"),)
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), nullable=False)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "color": self.color}


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False, index=True)
    amount_minor = db.Column(db.BigInteger, nullable=False)
    description = db.Column(db.String(255), nullable=False, default="")
    spent_on = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    category = db.relationship("Category")
    author = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "amount": to_major(self.amount_minor),
            "description": self.description,
            "spent_on": self.spent_on.isoformat(),
            "category": self.category.to_dict(),
            "created_by": {"id": self.author.id, "name": self.author.name},
        }


class Budget(db.Model):
    """A recurring monthly limit. category_id NULL = overall monthly budget."""
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id", ondelete="CASCADE"), nullable=True)
    amount_minor = db.Column(db.BigInteger, nullable=False)

    category = db.relationship("Category")

    def to_dict(self):
        return {"id": self.id, "category": self.category.to_dict() if self.category else None,
                "limit": to_major(self.amount_minor)}


class RevokedToken(db.Model):
    """Signed-out tokens. JWTs are stateless, so without this 'Sign out' only deletes the browser copy."""
    jti = db.Column(db.String(36), primary_key=True)
    revoked_at = db.Column(db.DateTime(timezone=True), default=utcnow)
