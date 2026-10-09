from datetime import date, timedelta


def add(client, auth, cat_id, amount, spent_on=None, description="x"):
    r = client.post("/api/expenses", headers=auth, json={
        "category_id": cat_id, "amount": amount, "description": description,
        "spent_on": spent_on or date.today().isoformat()})
    assert r.status_code == 201, r.json
    return r.json["expense"]


# ---------- auth ----------
def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"email": "A@Example.com", "password": "password123"})
    assert r.status_code == 201
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json['access_token']}"})
    assert me.json["user"]["email"] == "a@example.com"


def test_register_rejects_duplicate_weak_and_bad_email(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "password": "password123"})
    assert client.post("/api/auth/register", json={"email": "a@b.com", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/register", json={"email": "c@d.com", "password": "short"}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "nope", "password": "password123"}).status_code == 422


def test_login_same_error_for_unknown_user_and_bad_password(client, auth):
    a = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrongpass1"})
    b = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "wrongpass1"})
    assert a.status_code == b.status_code == 401 and a.json == b.json


def test_endpoints_require_token(client):
    for path in ["/api/expenses", "/api/categories", "/api/budgets", "/api/reports/monthly"]:
        assert client.get(path).status_code == 401


def test_new_user_gets_default_categories(cats):
    assert {"Food", "Transport", "Other"} <= set(cats)


# ---------- expenses CRUD ----------
def test_expense_crud(client, auth, cats):
    e = add(client, auth, cats["Food"], "1500.50", description="Lunch")
    assert e["amount"] == "1500.50" and e["category"]["name"] == "Food"
    r = client.patch(f"/api/expenses/{e['id']}", headers=auth, json={"amount": 2000, "category_id": cats["Transport"]})
    assert r.json["expense"]["amount"] == "2000.00" and r.json["expense"]["category"]["name"] == "Transport"
    assert client.delete(f"/api/expenses/{e['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/expenses/{e['id']}", headers=auth).status_code == 404


def test_money_has_no_float_drift(client, auth, cats):
    add(client, auth, cats["Food"], "0.10")
    add(client, auth, cats["Food"], "0.20")
    assert client.get("/api/expenses", headers=auth).json["total_amount"] == "0.30"


def test_amount_validation(client, auth, cats):
    for bad in ["-5", "0", "abc", "1.005", None, True, "NaN"]:
        r = client.post("/api/expenses", headers=auth, json={"category_id": cats["Food"], "amount": bad})
        assert r.status_code == 422, bad
    assert add(client, auth, cats["Food"], "1.500")["amount"] == "1.50"  # trailing zeros are fine


def test_future_date_and_bad_category_rejected(client, auth, cats, other_auth):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = client.post("/api/expenses", headers=auth, json={"category_id": cats["Food"], "amount": 5, "spent_on": tomorrow})
    assert r.status_code == 422
    bob_cat = client.get("/api/categories", headers=other_auth).json["categories"][0]["id"]
    r = client.post("/api/expenses", headers=auth, json={"category_id": bob_cat, "amount": 5})
    assert r.status_code == 404  # can't file an expense under someone else's category


def test_users_cannot_touch_each_others_expenses(client, auth, other_auth, cats):
    e = add(client, auth, cats["Food"], 100)
    assert client.get(f"/api/expenses/{e['id']}", headers=other_auth).status_code == 404
    assert client.patch(f"/api/expenses/{e['id']}", headers=other_auth, json={"amount": 1}).status_code == 404
    assert client.delete(f"/api/expenses/{e['id']}", headers=other_auth).status_code == 404
    assert client.get("/api/expenses", headers=other_auth).json["total_items"] == 0


# ---------- filters ----------
def test_filter_by_date_category_amount_and_search(client, auth, cats):
    today = date.today()
    old = (today - timedelta(days=40)).isoformat()
    add(client, auth, cats["Food"], 100, old, "old groceries")
    add(client, auth, cats["Food"], 300, description="dinner")
    add(client, auth, cats["Transport"], 50, description="bus")

    def items(qs):
        return client.get(f"/api/expenses?{qs}", headers=auth).json

    assert items(f"start_date={(today - timedelta(days=7)).isoformat()}")["total_items"] == 2
    assert items(f"category_id={cats['Food']}")["total_amount"] == "400.00"
    assert items(f"category_id={cats['Food']}&category_id={cats['Transport']}")["total_items"] == 3
    assert items("min_amount=100&max_amount=300")["total_items"] == 2
    assert items("q=DINNER")["expenses"][0]["description"] == "dinner"
    assert items("sort=amount")["expenses"][0]["amount"] == "50.00"
    assert client.get("/api/expenses?start_date=2026-02-30", headers=auth).status_code == 422
    assert client.get("/api/expenses?start_date=2026-05-01&end_date=2026-04-01", headers=auth).status_code == 422


def test_pagination(client, auth, cats):
    for i in range(30):
        add(client, auth, cats["Food"], i + 1)
    r = client.get("/api/expenses?per_page=10&page=3", headers=auth).json
    assert len(r["expenses"]) == 10 and r["total_pages"] == 3 and r["total_items"] == 30


# ---------- categories ----------
def test_category_crud_and_uniqueness(client, auth):
    r = client.post("/api/categories", headers=auth, json={"name": "Pets"})
    assert r.status_code == 201
    assert client.post("/api/categories", headers=auth, json={"name": "pets"}).status_code == 409
    assert client.post("/api/categories", headers=auth, json={"name": "X", "color": "red"}).status_code == 422
    cid = r.json["category"]["id"]
    assert client.patch(f"/api/categories/{cid}", headers=auth, json={"name": "Dog"}).json["category"]["name"] == "Dog"


def test_category_delete_in_use_requires_reassign(client, auth, cats):
    add(client, auth, cats["Food"], 100)
    assert client.delete(f"/api/categories/{cats['Food']}", headers=auth).status_code == 409
    r = client.delete(f"/api/categories/{cats['Food']}?reassign_to={cats['Other']}", headers=auth)
    assert r.status_code == 204
    assert client.get("/api/expenses", headers=auth).json["expenses"][0]["category"]["name"] == "Other"


def test_deleting_category_removes_its_budget_not_turns_it_into_overall(client, auth, cats):
    client.put("/api/budgets", headers=auth, json={"category_id": cats["Health"], "limit": 500})
    client.delete(f"/api/categories/{cats['Health']}", headers=auth)
    assert client.get("/api/budgets", headers=auth).json["budgets"] == []


# ---------- budgets & reports ----------
def test_budget_upsert_and_status(client, auth, cats):
    assert client.put("/api/budgets", headers=auth, json={"limit": 1000}).status_code == 201
    assert client.put("/api/budgets", headers=auth, json={"limit": 2000}).status_code == 200  # update, not duplicate
    client.put("/api/budgets", headers=auth, json={"category_id": cats["Food"], "limit": 500})
    client.put("/api/budgets", headers=auth, json={"category_id": cats["Transport"], "limit": 100})
    assert len(client.get("/api/budgets", headers=auth).json["budgets"]) == 3

    add(client, auth, cats["Food"], 600)
    add(client, auth, cats["Transport"], 85)
    s = client.get("/api/reports/monthly", headers=auth).json
    status = {(b["category"] or {}).get("name", "overall"): b for b in s["budgets"]}
    assert status["Food"]["status"] == "over" and status["Food"]["remaining"] == "-100.00"
    assert status["Transport"]["status"] == "warning"
    assert status["overall"]["status"] == "ok" and status["overall"]["spent"] == "685.00"


def test_monthly_summary(client, auth, cats):
    today = date.today()
    add(client, auth, cats["Food"], 300)
    add(client, auth, cats["Food"], 100)
    add(client, auth, cats["Transport"], 100)
    last_month = (today.replace(day=1) - timedelta(days=1)).isoformat()
    add(client, auth, cats["Food"], 9999, last_month)
    s = client.get(f"/api/reports/monthly?month={today:%Y-%m}", headers=auth).json
    assert s["total"] == "500.00" and s["expense_count"] == 3
    assert s["by_category"][0]["category"]["name"] == "Food" and s["by_category"][0]["share_pct"] == 80.0
    assert client.get("/api/reports/monthly?month=2026-13", headers=auth).status_code == 422


def test_trend_is_zero_filled(client, auth, cats):
    add(client, auth, cats["Food"], 250)
    t = client.get("/api/reports/trend?months=6", headers=auth).json
    assert len(t["months"]) == 6 and t["months"][-1]["total"] == "250.00" and t["months"][0]["total"] == "0.00"


# ---------- CSV ----------
def test_csv_export_respects_filters_and_blocks_formula_injection(client, auth, cats):
    add(client, auth, cats["Food"], 100, description="=HYPERLINK(\"http://evil\")")
    add(client, auth, cats["Transport"], 50, description="bus")
    r = client.get(f"/api/expenses/export?category_id={cats['Food']}", headers=auth)
    assert r.status_code == 200 and r.mimetype == "text/csv"
    assert "attachment" in r.headers["Content-Disposition"]
    body = r.data.decode("utf-8-sig")
    lines = body.strip().splitlines()
    assert lines[0] == "id,date,category,description,amount,added_by" and len(lines) == 2
    assert "'=HYPERLINK" in body and "bus" not in body
