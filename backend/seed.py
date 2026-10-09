"""Creates demo@example.com / password123 with ~6 months of sample expenses and budgets."""
import random
from datetime import date, timedelta

from app import create_app
from app.extensions import db
from app.models import Budget, Category, Expense, Membership, User, Workspace
from app.workspaces import create_workspace

app = create_app()
with app.app_context():
    old = User.query.filter_by(email="demo@example.com").first()
    if old:
        for m in Membership.query.filter_by(user_id=old.id, role="owner").all():
            for model in (Budget, Expense, Category, Membership):
                model.query.filter_by(workspace_id=m.workspace_id).delete()
            Workspace.query.filter_by(id=m.workspace_id).delete()
        Membership.query.filter_by(user_id=old.id).delete()
        db.session.delete(old)
        db.session.commit()
    user = User(email="demo@example.com", name="Demo User")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    ws = create_workspace(user.id, "Personal", "personal")
    db.session.flush()
    cats = {c.name: c for c in Category.query.filter_by(workspace_id=ws.id)}

    random.seed(7)
    typical = {"Food": (2000, 15000, 25), "Transport": (1000, 8000, 18), "Housing": (150000, 150000, 1),
               "Utilities": (8000, 25000, 3), "Health": (3000, 20000, 2), "Entertainment": (2500, 18000, 4),
               "Shopping": (5000, 40000, 3), "Other": (1000, 10000, 3)}
    today = date.today()
    for day in range(180):
        d = today - timedelta(days=day)
        for name, (lo, hi, per_month) in typical.items():
            if random.random() < per_month / 30:
                db.session.add(Expense(workspace_id=ws.id, created_by=user.id, category_id=cats[name].id, spent_on=d,
                                       amount_minor=random.randint(lo, hi) * 100, description=f"{name} purchase"))
    db.session.add(Budget(workspace_id=ws.id, category_id=None, amount_minor=600000 * 100))
    db.session.add(Budget(workspace_id=ws.id, category_id=cats["Food"].id, amount_minor=180000 * 100))
    db.session.add(Budget(workspace_id=ws.id, category_id=cats["Transport"].id, amount_minor=60000 * 100))
    db.session.add(Budget(workspace_id=ws.id, category_id=cats["Entertainment"].id, amount_minor=30000 * 100))
    db.session.commit()
    print("Seeded demo@example.com / password123")
