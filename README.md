# expense-tracker
# Spend-wise API

Flask REST API for the Spend-wise expense app. JSON only, no frontend. Database: Supabase (PostgreSQL).

- **API contract for frontend developers:** [API.md](API.md), which maps each screen to its endpoint, with response shapes.
- **Try every endpoint:** import `Expense_Tracker_API.postman_collection.json` into Postman.

## Run it locally (about 5 minutes)

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
```

Fill in `.env` (ask the backend owner for the Supabase values):

| Variable | Required | What it is |
|---|---|---|
| `DATABASE_URL` | Yes | Supabase > **Connect** > **Direct** > **Session pooler** > URI, port 5432. Use the *database password*, not an API key. Add `?sslmode=require`. |
| `JWT_SECRET_KEY` | Yes in production | Signs login tokens. Generate: `python -c 'import secrets; print(secrets.token_urlsafe(48))'`. If unset in development, a random key is used and everyone is signed out on restart. |
| `CORS_ORIGINS` | No | Frontend URLs allowed to call the API. Default `http://localhost:5173,http://127.0.0.1:5173` (Vite). |
| `APP_ENV` | No | `development` (default) or `production`. |
| `JWT_EXPIRES_HOURS`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `PORT` | No | Defaults: 8, 5, 5, 5000. |

```bash
python run.py                        # http://127.0.0.1:5000
python seed.py                       # optional: demo@example.com / password123 with 6 months of data
```

**On a Mac**, if requests to port 5000 return `403` or `AirTunes`, macOS AirPlay Receiver is using that port. Either set
`PORT=5001` in `.env` (and point the frontend at 5001) or turn off System Settings > General > AirDrop & Handoff > AirPlay Receiver.

On start, the log prints `Database: postgresql+psycopg://...` with the password hidden. Tables are created automatically on
the first run. Check it's up: `GET http://127.0.0.1:5000/health`.

## Health checks

No authentication needed. Responses are never cached.

| Endpoint | Checks | Returns | Use for |
|---|---|---|---|
| `GET /health` | API **and** database (`SELECT 1`) | `200` healthy, `503` database unreachable | Uptime monitors, load balancers, Kubernetes **readiness** probe |
| `GET /health/live` | API process only | Always `200` while running | Kubernetes **liveness** probe |
| `GET /api/health` | Same as `/health` | Same | Older clients |

```json
{"status": "ok", "checks": {"database": {"status": "ok", "latency_ms": 2.2}},
 "uptime_seconds": 3600, "timestamp": "2026-10-06T20:01:16+00:00"}
```

When the database is down, `/health` returns `503` with `"status": "degraded"` and `"database": {"status": "unreachable"}`.
The error details go to the server log only. Don't point a liveness probe at `/health`: a Supabase outage would then make
Kubernetes restart healthy containers in a loop.

```yaml
# Kubernetes probes
livenessProbe:  { httpGet: { path: /health/live, port: 5000 }, periodSeconds: 15 }
readinessProbe: { httpGet: { path: /health,      port: 5000 }, periodSeconds: 10, failureThreshold: 3 }
```

## For the frontend

- Base URL: `http://127.0.0.1:5000/api`
- Sign in with `POST /api/auth/login`, then send `Authorization: Bearer <access_token>` on every request.
- Optional `X-Workspace-Id: <id>` header picks a team workspace. Without it, the user's Personal workspace is used.
- Money is always a decimal **string** (`"1500.50"`). Errors are always `{"error": "message"}`.
- Full details, a ready-made `fetch` helper, and the screen-to-endpoint map: [API.md](API.md).

## Deploy

```bash
APP_ENV=production gunicorn -w 2 -b 0.0.0.0:${PORT:-5000} run:app
```

Set `DATABASE_URL`, `JWT_SECRET_KEY` (32+ chars) and `CORS_ORIGINS` (your deployed frontend URL) as environment variables
on the host. In production the app refuses to start if the database URL is missing or the secret is weak.

## Security notes

- **Row Level Security is switched on automatically** for every table at startup. Supabase publishes the `public` schema
  through its Data API; RLS with no policies blocks that API, so the tables are reachable only through this Flask API.
  The app connects as `postgres`, which bypasses RLS.
- Never commit `.env`. It's already in `.gitignore`.
- Not built yet: login rate limiting, password reset and email invites. Add rate limiting before a public launch.

## Tests

The tests need their **own empty Postgres database**, because they drop every table after each test. They refuse to run
against the database in `DATABASE_URL`.

```bash
pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/expenses_test pytest -q    # 43 tests
```

A quick local Postgres for this: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=expenses_test postgres:16`.

## Project layout

```
app/
  __init__.py     app factory, CORS, error handlers, DB startup (tables + RLS)
  health.py       /health, /health/live
  config.py       environment variables
  models.py       User, Workspace, Membership, Category, Expense, Budget, RevokedToken
  auth.py         register, login, logout, profile, password
  workspaces.py   workspaces, team members, workspace selection (X-Workspace-Id)
  categories.py   expenses.py   budgets.py   reports.py
  validation.py   input parsing (money, dates, ids)
run.py            entry point (dev server / gunicorn)
seed.py           demo data
```

## Design decisions

- **Money is stored as integer kobo** (`amount_minor`), never floats. Totals are cast back to integers because Postgres
  returns `SUM(bigint)` as a decimal.
- **Everything is scoped to a workspace you belong to.** Anything else returns 404, so IDs can't be probed.
- **In teams, members edit only their own expenses**; the owner can edit any.
- **CSV export escapes cells starting with `= + - @`** so a spreadsheet won't run them as formulas.
- **No migrations yet.** Tables are created if missing, but existing tables are never altered. Before changing a model on
  a database with real data, add Flask-Migrate (Alembic).
