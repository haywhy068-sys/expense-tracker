# SpendWise API

Flask backend for the SpendWise expense tracker. Implements **API Contract v1.0**. See [API.md](API.md).

## Run locally

Requires Python 3.11+ and a Supabase database with PostgreQL core.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set DATABASE_URL and JWT_SECRET_KEY
python run.py                   # http://127.0.0.1:5000
python seed.py                  # optional: demo@example.com / password123, 3 months of data
curl http://127.0.0.1:5000/health
```

Tables are created on first start if missing. `schema.sql` holds the same schema for the database group's init scripts.

**Frontend in development (Vite):** there is no CORS (the contract uses same-origin via Nginx). Proxy instead:
```js
// vite.config.js
server: { proxy: { "/api": "http://127.0.0.1:5000", "/health": "http://127.0.0.1:5000" } }
```

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | Yes | `postgresql://user:password@host:5432/db`. In Compose, host = the DB service name. |
| `JWT_SECRET_KEY` | Yes in production | 32+ chars. If unset in development, a random key is used per run. |
| `APP_ENV` | No | `development` (default) or `production`. |

## Production

```bash
APP_ENV=production gunicorn -w 2 -b 0.0.0.0:5000 run:app
```
Nginx: route `/api/` and `/health` to this on port 5000.

## Tests

The tests need a **separate, empty** Postgres database (they drop every table). They refuse to run against `DATABASE_URL`.
```bash
pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/spendwise_test pytest -q     # 74 tests
```

## Layout

```
app/
  __init__.py     app factory, JSON error handlers, table creation
  config.py       environment variables
  models.py       users, expenses, budgets; fixed category list
  validation.py   contract validation rules
  auth.py         register, login (bcrypt)
  expenses.py     list, create, replace, delete, CSV export
  categories.py   fixed list
  budgets.py      monthly budget get/set
  health.py       /health
schema.sql        DDL for the database group
seed.py           demo data
SpendWise_API.postman_collection.json
```

## Notes

- Passwords: SHA-256 then bcrypt. bcrypt alone silently ignores everything after 72 bytes, but the contract allows
  128 characters; the pre-hash makes every character count.
- No migrations yet. Add Flask-Migrate before changing a table that holds real data.
- Not in this version (removed per the contract): workspaces/teams, logout, password change, reports.

In DevOps’s Dockerfile or Compose file, the backend’s start command should be:
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "run:app"]
