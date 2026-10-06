from datetime import date

H = "X-Workspace-Id"


def ws_headers(auth, wid):
    return {**auth, H: str(wid)}


def make_team(client, auth, name="Flatmates"):
    r = client.post("/api/workspaces", headers=auth, json={"name": name})
    assert r.status_code == 201, r.json
    return r.json["workspace"]["id"]


def first_cat(client, headers):
    return client.get("/api/categories", headers=headers).json["categories"][0]["id"]


def add(client, headers, amount, desc="x"):
    r = client.post("/api/expenses", headers=headers, json={
        "category_id": first_cat(client, headers), "amount": amount, "description": desc,
        "spent_on": date.today().isoformat()})
    assert r.status_code == 201, r.json
    return r.json["expense"]


def test_register_returns_name_and_personal_workspace(client):
    r = client.post("/api/auth/register", json={"name": "Bolade A", "email": "b@x.com", "password": "password123"})
    assert r.json["user"]["name"] == "Bolade A" and r.json["user"]["initials"] == "BA"
    auth = {"Authorization": f"Bearer {r.json['access_token']}"}
    ws = client.get("/api/workspaces", headers=auth).json["workspaces"]
    assert len(ws) == 1 and ws[0]["kind"] == "personal" and ws[0]["role"] == "owner"
    assert ws[0]["id"] == r.json["default_workspace_id"]


def test_team_data_is_separate_from_personal(client, auth):
    tid = make_team(client, auth)
    add(client, auth, 100, "personal")                # no header -> personal
    add(client, ws_headers(auth, tid), 999, "team")
    personal = client.get("/api/expenses", headers=auth).json
    team = client.get("/api/expenses", headers=ws_headers(auth, tid)).json
    assert personal["total_amount"] == "100.00" and team["total_amount"] == "999.00"
    assert client.get("/api/reports/monthly", headers=ws_headers(auth, tid)).json["total"] == "999.00"


def test_members_share_a_team_but_not_personal_data(client, auth, other_auth):
    tid = make_team(client, auth)
    add(client, auth, 5000, "alice personal")
    r = client.post(f"/api/workspaces/{tid}/members", headers=auth, json={"email": "bob@example.com"})
    assert r.status_code == 201
    bob_team = ws_headers(other_auth, tid)
    add(client, bob_team, 300, "bob team")
    assert client.get("/api/expenses", headers=ws_headers(auth, tid)).json["total_items"] == 1
    assert client.get("/api/expenses", headers=other_auth).json["total_items"] == 0  # bob's personal
    names = [m["email"] for m in client.get(f"/api/workspaces/{tid}/members", headers=other_auth).json["members"]]
    assert names == ["alice@example.com", "bob@example.com"]


def test_non_member_cannot_reach_a_workspace(client, auth, other_auth):
    tid = make_team(client, auth)
    assert client.get("/api/expenses", headers=ws_headers(other_auth, tid)).status_code == 404
    assert client.get(f"/api/workspaces/{tid}", headers=other_auth).status_code == 404
    assert client.get("/api/expenses", headers={**auth, H: "abc"}).status_code == 400


def test_member_can_only_edit_own_expenses_owner_can_edit_all(client, auth, other_auth):
    tid = make_team(client, auth)
    client.post(f"/api/workspaces/{tid}/members", headers=auth, json={"email": "bob@example.com"})
    alice_exp = add(client, ws_headers(auth, tid), 100)
    bob_exp = add(client, ws_headers(other_auth, tid), 200)
    bob = ws_headers(other_auth, tid)
    assert client.patch(f"/api/expenses/{alice_exp['id']}", headers=bob, json={"amount": 1}).status_code == 403
    assert client.delete(f"/api/expenses/{alice_exp['id']}", headers=bob).status_code == 403
    assert client.patch(f"/api/expenses/{bob_exp['id']}", headers=bob, json={"amount": 250}).status_code == 200
    assert client.delete(f"/api/expenses/{bob_exp['id']}", headers=ws_headers(auth, tid)).status_code == 204
    assert alice_exp["created_by"]["name"] == "alice"


def test_member_management_rules(client, auth, other_auth):
    tid = make_team(client, auth)
    me = client.get("/api/auth/me", headers=other_auth).json["user"]
    assert client.post(f"/api/workspaces/{tid}/members", headers=auth, json={"email": "ghost@x.com"}).status_code == 404
    client.post(f"/api/workspaces/{tid}/members", headers=auth, json={"email": "bob@example.com"})
    assert client.post(f"/api/workspaces/{tid}/members", headers=auth, json={"email": "bob@example.com"}).status_code == 409
    assert client.patch(f"/api/workspaces/{tid}", headers=other_auth, json={"name": "Hijack"}).status_code == 403
    alice_id = client.get("/api/auth/me", headers=auth).json["user"]["id"]
    assert client.delete(f"/api/workspaces/{tid}/members/{alice_id}", headers=auth).status_code == 409  # owner can't leave
    assert client.delete(f"/api/workspaces/{tid}/members/{me['id']}", headers=other_auth).status_code == 204  # bob leaves
    assert client.get("/api/expenses", headers=ws_headers(other_auth, tid)).status_code == 404


def test_personal_workspace_rules_and_team_delete(client, auth):
    personal = client.get("/api/workspaces", headers=auth).json["workspaces"][0]["id"]
    assert client.delete(f"/api/workspaces/{personal}", headers=auth).status_code == 409
    assert client.post(f"/api/workspaces/{personal}/members", headers=auth, json={"email": "a@b.com"}).status_code == 409
    tid = make_team(client, auth)
    add(client, ws_headers(auth, tid), 100)
    client.put("/api/budgets", headers=ws_headers(auth, tid), json={"limit": 500})
    assert client.delete(f"/api/workspaces/{tid}", headers=auth).status_code == 204
    assert [w["id"] for w in client.get("/api/workspaces", headers=auth).json["workspaces"]] == [personal]


def test_logout_revokes_token(client, auth):
    assert client.post("/api/auth/logout", headers=auth).status_code == 204
    r = client.get("/api/auth/me", headers=auth)
    assert r.status_code == 401 and "signed out" in r.json["error"]


def test_profile_and_password_change(client, auth):
    assert client.patch("/api/auth/me", headers=auth, json={"name": "Alice Smith"}).json["user"]["initials"] == "AS"
    assert client.post("/api/auth/password", headers=auth, json={"current_password": "nope", "new_password": "newpassword1"}).status_code == 401
    assert client.post("/api/auth/password", headers=auth, json={"current_password": "password123", "new_password": "newpassword1"}).status_code == 204
    assert client.post("/api/auth/login", json={"email": "alice@example.com", "password": "newpassword1"}).status_code == 200


def test_daily_is_zero_filled_and_overall_budget_exposed(client, auth):
    client.put("/api/budgets", headers=auth, json={"limit": 1000})
    add(client, auth, 250)
    s = client.get("/api/reports/monthly", headers=auth).json
    today = date.today()
    assert s["daily"][0]["date"].endswith("-01") and len(s["daily"]) >= 28
    assert next(d for d in s["daily"] if d["date"] == today.isoformat())["total"] == "250.00"
    assert s["overall_budget"]["remaining"] == "750.00" and s["currency"] == "NGN"


def test_cors_allows_vite_dev_server_only(client):
    ok = client.options("/api/expenses", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
                                                    "Access-Control-Request-Headers": "authorization,x-workspace-id"})
    assert ok.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    assert "x-workspace-id" in ok.headers.get("Access-Control-Allow-Headers", "").lower()
    bad = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "Access-Control-Allow-Origin" not in bad.headers
