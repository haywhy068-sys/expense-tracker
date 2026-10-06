# Spend-wise API contract

Base URL (dev): `http://127.0.0.1:5000/api`. Health check: `GET /health` (no auth; `200` healthy, `503` if the database is down). Frontend origin allowed by default: `http://localhost:5173`
(change with the `CORS_ORIGINS` env var, comma-separated).

**Every request except register, login and health** sends:

```
Authorization: Bearer <access_token>
X-Workspace-Id: <id>      // optional; omitted = the user's Personal workspace
Content-Type: application/json
```

Money is always a **decimal string** (`"57600.00"`), never a float. Dates are `YYYY-MM-DD`, months `YYYY-MM`.
Errors are `{"error": "message"}` with: 400 bad input shape, 401 not signed in / signed out, 403 not allowed,
404 not found (including workspaces you aren't a member of), 409 conflict, 422 validation.

## Screen → endpoint map

| Screen element | Call |
|---|---|
| Sign in | `POST /auth/login` `{email, password}` |
| Create an account | `POST /auth/register` `{name?, email, password}` (password ≥ 8 chars) |
| Sidebar user card (`U`, name, email) | `GET /auth/me` → `{user: {id, name, email, initials}}` |
| Sign out | `POST /auth/logout`, then delete the token in the browser |
| Workspace dropdown ("Personal") | `GET /workspaces` → `[{id, name, kind, role, member_count, currency}]`, personal first |
| + Create a team | `POST /workspaces` `{name}` |
| Breadcrumb / "NGN ledger" | `workspace.name`, `workspace.currency` from `GET /workspaces/<id>` |
| Month picker + all Overview cards | `GET /reports/monthly?month=2026-10` (one call, see below) |
| Total spent / "6 expenses in 2026-10" | `total`, `expense_count` |
| Monthly budget / "Not set" | `overall_budget` (`null` → show "Not set") |
| Set a monthly budget | `PUT /budgets` `{limit: "600000"}` |
| Budget remaining | `overall_budget.remaining`, `overall_budget.used_pct`, `overall_budget.status` (`ok`/`warning`/`over`) |
| Daily spending chart | `daily` — one entry per day of the month, zero-filled |
| By category chart / "5 categories" | `by_category` (sorted, with `share_pct`), `by_category.length` |
| Export CSV | `GET /expenses/export?<same filters as list>` → file. Read the name from `Content-Disposition` |
| Add expense | `POST /expenses` `{category_id, amount, spent_on?, description?}` |
| Expenses page | `GET /expenses?page&per_page&start_date&end_date&category_id&min_amount&max_amount&q&sort&created_by` |
| Edit / delete expense | `PATCH /expenses/<id>`, `DELETE /expenses/<id>` |
| Budgets page | `GET /budgets`, `PUT /budgets` `{category_id?, limit}`, `DELETE /budgets/<id>`; live status in `GET /reports/monthly` → `budgets[]` |
| Analytics page | `GET /reports/trend?months=6` + `GET /reports/monthly` |
| Category picker | `GET /categories`; manage with `POST`/`PATCH`/`DELETE /categories/<id>` |

## Response shapes

`POST /auth/login` and `POST /auth/register`
```json
{"user": {"id": 1, "name": "Demo User", "email": "demo@example.com", "initials": "DU"},
 "access_token": "eyJ...", "default_workspace_id": 1}
```

`GET /reports/monthly?month=2026-10`
```json
{"workspace": {"id": 1, "name": "Personal", "kind": "personal", "currency": "NGN"},
 "month": "2026-10", "currency": "NGN", "total": "57600.00", "expense_count": 6,
 "overall_budget": {"id": 3, "category": null, "limit": "600000.00", "spent": "57600.00",
                    "remaining": "542400.00", "used_pct": 9.6, "status": "ok"},
 "by_category": [{"category": {"id": 1, "name": "Food", "color": "#2a78d6"}, "total": "22000.00", "count": 2, "share_pct": 38.2}],
 "daily": [{"date": "2026-10-01", "total": "0.00"}, {"date": "2026-10-02", "total": "22000.00"}],
 "budgets": [ /* overall first, then per-category, same shape as overall_budget */ ]}
```

`GET /expenses`
```json
{"expenses": [{"id": 7, "amount": "1500.50", "description": "Lunch", "spent_on": "2026-10-05",
               "category": {"id": 1, "name": "Food", "color": "#2a78d6"},
               "created_by": {"id": 1, "name": "Demo User"}}],
 "page": 1, "per_page": 25, "total_items": 6, "total_pages": 1, "total_amount": "57600.00"}
```

## Teams

| Call | Who |
|---|---|
| `GET /workspaces/<id>/members` | any member |
| `POST /workspaces/<id>/members` `{email}` | owner. The person must already have an account (no email invites) |
| `DELETE /workspaces/<id>/members/<user_id>` | owner removes others; a member can remove themselves (leave) |
| `PATCH /workspaces/<id>` `{name}`, `DELETE /workspaces/<id>` | owner. The Personal workspace can't be deleted |

In a team, any member can add expenses, categories and budgets, but **members can only edit or delete
their own expenses**. The owner can edit or delete any.

<!-- ## Frontend wiring (React/Vite)

```js
// api.js
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000/api";

export async function api(path, { workspaceId, ...opts } = {}) {
  const token = sessionStorage.getItem("token");
  const res = await fetch(BASE + path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
      ...(workspaceId && { "X-Workspace-Id": String(workspaceId) }),
      ...opts.headers,
    },
  });
  if (res.status === 401) { sessionStorage.removeItem("token"); window.location.assign("/login"); }
  if (res.status === 204) return null;
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : res;
  if (!res.ok) throw new Error(body.error ?? res.statusText);
  return body;
}
``` -->
