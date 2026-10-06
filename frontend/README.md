# Spend-wise React frontend

## Day 2: run with sample data (no Flask needed)

Open PowerShell in the `frontend` folder and run:

```powershell
npm.cmd ci
npm.cmd run dev:mock
```

Open the Local URL printed by Vite and click **Open sample dashboard**. Mock mode is clearly labelled. You can add, edit, delete, filter, view charts and export CSV using sample records. Records and budgets reset on reload. Use sample credentials only; this mode does not authenticate against a backend or send requests to Flask.

Stop the server with Ctrl+C. When Flask is ready, use `npm.cmd run dev` and configure `VITE_API_URL` as below. `.env.mock` enables mock mode only for `dev:mock`; production builds disable it.

## Run locally with Flask

Use Node.js 22.13 or newer and npm.

```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Open the URL printed by Vite (normally `http://localhost:5173`). On Windows, copy `.env.example` to `.env` with File Explorer or PowerShell `Copy-Item .env.example .env`.

`VITE_API_URL` sets the API base URL and defaults to `/api`. For a separate backend origin use `http://localhost:5000/api` or `https://api.example.com/api`. Existing origin-only values such as `http://localhost:5000` also remain supported. The client prevents a duplicate `/api` prefix. An unset or empty value uses `/api` on the frontend origin. During Vite development, the included proxy forwards `/api` to `http://127.0.0.1:5000`. In production, `/api` requires the deployment ingress/reverse proxy to route `/api/*` to Flask on port 5000. The included Nginx configuration serves the frontend only; DevOps must configure that API routing or supply a separate API URL. Restart Vite after changes. Vite embeds environment values in the compiled assets, so they are public configuration and must never contain secrets.

`VITE_CURRENCY` sets the display currency, default `NGN`. Amounts are the API's major units (e.g. `120.50`), not integer cents. The frontend converts to cents only for accurate arithmetic. The supplied expense contract has no currency field, so one backend ledger must use a single agreed currency. Changing the display setting does not convert values. Multiple currencies require an additional agreed backend contract.

```bash
npm run build
npm test
npm run preview
```

## Docker

```bash
docker build --build-arg VITE_API_URL=https://api.example.com/api --build-arg VITE_CURRENCY=NGN -t spend-wise-frontend .
docker run --rm -p 8080:80 spend-wise-frontend
```

Open `http://localhost:8080`. The browser, not Nginx, calls the API URL. Use a backend URL reachable by visitors. Runtime `docker run -e VITE_API_URL=...` cannot change a built Vite bundle. Rebuild with the desired argument. Dockerfile uses a Node build stage and an Nginx static serving stage with SPA fallback and a health check. Docker execution was not verified in the authoring environment.

## Agreed auth contract

`POST /api/auth/register` and `POST /api/auth/login` send exactly:

```json
{"email":"user@example.com","password":"securepassword123"}
```

Successful response for both routes:

```json
{"token":"YOUR_JWT_TOKEN_STRING","user":{"id":1,"email":"user@example.com"}}
```

The token and user remain in React/module memory during the current session. Reloading requires login again. The app does not store financial records or JWTs in localStorage. Every protected request receives `Authorization: Bearer <token>`. A protected route returning 401 clears the session and returns to sign-in. Login errors remain on the form. Logout clears the token, records and session budget.

## Expense contract

Protected routes:

| Method | Route | Request body | Successful response |
| --- | --- | --- | --- |
| GET | `/api/expenses` | None | JSON array of expense objects |
| POST | `/api/expenses` | Expense fields without `id` | Created expense object (201 or 200) |
| PUT | `/api/expenses/<id>` | Expense fields without `id` | Updated expense object (200) |
| DELETE | `/api/expenses/<id>` | None | 204 empty body or 200 JSON |

The original brief did not define a GET list envelope or write response codes. This frontend uses the conventional array/object responses above. Please confirm these before integration.

```json
{"id":1,"date":"2026-10-05","category":"Food","description":"Weekly grocery shopping","amount":120.50}
```

Create/update sends only `date`, `category`, `description`, and numeric `amount`. The server assigns `id`; the frontend accepts string or numeric IDs. Dates use `YYYY-MM-DD`. Values display in the configured currency. Default categories: Food, Transport, Shopping, Utilities, Health, Entertainment, Education, Other. Existing additional categories appear in charts and can be preserved when editing.

### Filters

The client sends standard queries such as:

```text
/api/expenses?category=Food&start_date=2026-10-01&end_date=2026-10-05
```

`All` means all categories. Missing category must also mean all categories. Dates are inclusive. Results should contain only the authenticated user's expenses, ideally sorted by date descending. Monthly summary/charts request the full selected month without a category filter, independent of the filtered expense table. CSV export includes all rows returned for the current table filters, even when Overview displays only the latest five.

### Errors and CORS

Use non-2xx codes for errors, ideally `{"error":"Readable explanation"}` or `{"message":"Readable explanation"}`. Form failures preserve input. Abort obsolete filter requests. Reject invalid dates, non-positive amounts and unauthorized edits on the server.

For separate frontend/API origins, configure Flask CORS for the exact frontend origin, `Content-Type` and `Authorization` headers, and GET/POST/PUT/DELETE/OPTIONS methods. Handle OPTIONS preflight. The frontend uses bearer headers and does not request cross-origin cookie credentials. Use HTTPS in production. Hash passwords on the backend, verify JWT signatures/expiry and scope every query and mutation to the authenticated user. Never trust the expense ID as proof of ownership.

## Budget integration gap

The app includes a monthly budget view with progress and remaining/overspent amounts. It explicitly labels the plan as **session only**. It resets on reload/logout. It makes no invented budget API requests.

Suggested contract for team agreement, not an implemented/required existing endpoint:

- `GET /api/budgets?month=2026-10` returns `{"month":"2026-10","amount":150000}` or a defined empty state.
- `PUT /api/budgets/2026-10` accepts `{"amount":150000}` and returns the saved month/amount.
- Both require Bearer auth and per-user ownership.

After agreement, replace the session state in `src/App.tsx` with these API operations and define validation and absent-budget behavior.

## Testing and screenshots

`npm test` checks mock auth/CRUD/filter behavior, API contracts, decimal arithmetic and CSV quoting/formula safety. Earlier browser acceptance checks used a separate temporary mock API. The optional development mock adapter now has an automated auth, CRUD and filter test. Test records and screenshots are illustrative. Build and TypeScript checks passed. API tests verified auth and CRUD request shapes, header injection and 401 recovery. Browser checks verified expense add/edit/delete, filter results, session-budget progress and the 390-pixel layout. The browser download completion signal timed out, so a completed browser CSV download is not claimed. CSV generation, escaping and arithmetic passed automated tests. See `../TEST_RESULTS.md` for the actual results. No Flask/PostgreSQL server or Docker runtime was provided, so those integrations are not claimed as tested.

Core files: `src/api.ts` central request/auth client, `src/types.ts` DTOs, `src/App.tsx` views/forms, `src/money.mjs` arithmetic/export, `src/styles.css` responsive presentation.
