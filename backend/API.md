# SpendWise API

Implements **API Contract v1.0** (7 October 2026). The contract is the source of truth; this page only adds the
decisions the contract leaves open (marked **Clarification**) so frontend and backend agree on them too.

## Rules

| Topic | Rule |
|---|---|
| Base path | Everything under `/api`, except `GET /health`. Nginx sends `/api/*` and `/health` to Flask on port 5000. No CORS. |
| Format | JSON, UTF-8. Dates `YYYY-MM-DD`, months `YYYY-MM`, IDs integers. |
| Money | JSON **number**, at most 2 decimals, e.g. `120.5`. Stored as `NUMERIC(12,2)`. NGN only, no currency field. |
| Auth | Login/register return `token`. Send `Authorization: Bearer <token>`. Lifetime 24 h. |
| Errors | Always `{"error": "message"}`. 400 malformed JSON, 401 not signed in / wrong credentials, 404 not found, 409 email taken, 422 validation. |
| Isolation | Another user's expense returns **404**, never 403. |
| Sorting | Expenses: newest `date` first, then newest `id`. |

## Endpoints

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/auth/register` | `{"email","password"}` | 201 `{"token","user":{"id","email"}}` | 409, 422 |
| POST | `/api/auth/login` | `{"email","password"}` | 200 `{"token","user":{"id","email"}}` | 401 |
| GET | `/api/expenses?category=&start_date=&end_date=` | none | 200 array of expenses | 401, 422 |
| POST | `/api/expenses` | `{"date","category","description","amount"}` | 201 the expense | 422 |
| PUT | `/api/expenses/<id>` | all four fields (full replace) | 200 the expense | 404, 422 |
| DELETE | `/api/expenses/<id>` | none | 204, no body | 404 |
| GET | `/api/expenses/export?category=&start_date=&end_date=` | none | 200 `text/csv`: `date,category,description,amount` | 401, 422 |
| GET | `/api/categories` | none | 200 `["Food","Transport",...]` | 401 |
| GET | `/api/budgets?month=YYYY-MM` | none | 200 `{"month","limit"}`, `limit` is `null` if not set | 422 |
| PUT | `/api/budgets` | `{"month","limit"}` | 200 `{"month","limit"}` | 422 |
| GET | `/health` | none | 200 `{"status":"ok","database":"ok"}` | 503 `{"status":"error","database":"down"}` |

Expense object:
```json
{ "id": 7, "date": "2026-10-05", "category": "Food", "description": "Weekly grocery shopping", "amount": 12050.5 }
```

## Validation

| Field | Rule |
|---|---|
| email | Valid format, max 254 chars, unique case-insensitive (stored lower-cased) |
| password | 8 to 128 characters, bcrypt-hashed, never returned |
| description | Required, trimmed, 1 to 140 characters |
| amount, limit | Number > 0, at most 2 decimals, max 9999999999.99 |
| date | Valid calendar date `YYYY-MM-DD` |
| category | `Food`, `Transport`, `Shopping`, `Utilities`, `Health`, `Entertainment`, `Education`, `Other` (exact case) |
| month | `YYYY-MM`, month 01 to 12 |

## Clarifications (the contract doesn't specify these)

1. **`amount` and `limit` must be JSON numbers.** `"120.5"` (a string) gets 422. Send `Number(input)` from form fields.
2. **`GET /api/budgets` without `month`** returns 422, same as a bad month.
3. **Unknown category in a filter** (`?category=Pets`) returns 422, not an empty list. `All` and empty mean no filter.
4. **Category is case-sensitive.** `food` gets 422; use the exact values from `GET /api/categories`.
5. **Login with a missing or non-string email or password** returns 401 (wrong credentials), not 422.
6. **PUT on someone else's or a missing expense** returns 404 before the body is validated.
7. **No future-date rule.** The contract doesn't forbid future dates, so they're accepted.
8. **CSV**: amounts are written with 2 decimals (`1500.50`), no currency symbol. A description starting with `= + - @`
   gets a leading `'` so spreadsheets don't run it as a formula.
9. **Unknown routes** return 404 `{"error":"Not found"}`; a wrong method returns 405 `{"error":"Method not allowed"}`.
