# OncoTwin Backend

FastAPI backend for the OncoTwin platform. **Module 1 (Authentication &
Authorization) only** — see "Scope" below for what is and isn't implemented.

## Two run modes

`AUTH_PROVIDER` decides where identities and credentials live. Everything
above the provider seam (`app/auth/providers/`) is identical in both, so the
HTTP contract the frontend sees does not change.

| | `local` (default) | `supabase` |
|---|---|---|
| Credentials | `local_credentials` table, bcrypt | Supabase Auth (`auth.users`) |
| Access tokens | HS256, signed here | Supabase-issued, verified here |
| Refresh tokens | `auth_tokens`, SHA-256 hashed, rotated | Supabase, rotated |
| Database | SQLite file under `DATA_DIR` | PostgreSQL (Supabase) |
| Password reset | link appended to `data/password-reset-links.log` | email via Supabase |
| Needs network | no | yes |

## Quick start — file mode (nothing external required)

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # defaults are already file mode
uvicorn app.main:app --reload --port 8000
```

The SQLite database and the four seed roles are created on first boot.
Check it came up:

```sh
curl localhost:8000/health/ready
# {"status":"ok","auth_provider":"local","database":"sqlite","database_ok":true,...}
```

Then point the frontend at it with `VITE_API_BASE_URL=http://localhost:8000`
in the frontend `.env` — that single variable switches the whole app off
fixtures (`src/services/api-client.ts`).

Register, sign in, read the profile:

```sh
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"secret123","name":"Dr You","role":"doctor"}'

curl -c jar -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"secret123"}'

curl localhost:8000/auth/me -H "Authorization: Bearer <accessToken from above>"
```

To complete a password reset in file mode, read the link out of
`data/password-reset-links.log` — the local provider does not send email.

## Switching to Supabase

1. Uncomment the Supabase block in `.env` and set `AUTH_PROVIDER=supabase`.
   Startup fails with an explicit list of missing variables if any are absent.
2. Point `DATABASE_URL` at the **pooler** (port 6543, transaction mode).
3. `alembic upgrade head`.
4. `uvicorn app.main:app --port 8000`.

The migrations detect their target: the `profiles -> auth.users` foreign key
and the `auth.uid()` RLS policies are created only when the Supabase `auth`
schema is present, so the same history applies to SQLite, plain PostgreSQL
and Supabase.

## Migrations

```sh
alembic upgrade head        # apply
alembic downgrade -1        # roll back one
alembic revision -m "..."   # new migration
```

In file mode the schema is created from the models on boot, so migrations are
optional there; against PostgreSQL they are mandatory and the app refuses to
start with a clear message if `profiles` is missing.

## Testing

```sh
pip install -r requirements-dev.txt
pytest -q        # 78 tests
```

The integration tests (`tests/test_auth_flow.py`) run the **real** service,
repository and local provider against a temporary SQLite database. Only the
database session is overridden.

This matters: the previous suite replaced `AuthService` and
`get_current_user` with fakes, so no test ever constructed the real object
graph — and a SQLAlchemy mapper bug that made every database-backed endpoint
return HTTP 500 sat behind 27 passing tests. Please don't stub the service
layer in new tests.

Not covered automatically: a live pass against a real Supabase project.
Run the eight endpoints against `supabase start` once before deploying in
that mode.

## Endpoints

All mounted at bare paths to match the frontend registry
(`src/services/endpoints.ts`):

```
POST /auth/register        POST /auth/refresh          GET   /auth/me
POST /auth/login           POST /auth/forgot-password  PATCH /users/profile
POST /auth/logout          POST /auth/reset-password
GET  /health               GET  /health/ready
```

Errors always use one envelope, which `src/services/api-client.ts` parses
into `ApiError`:

```json
{"error": {"code": "...", "message": "...", "field": "...", "request_id": "..."}}
```

## Security notes

- The refresh token is httpOnly, `SameSite=Lax`, and never appears in a
  response body. Only the short-lived access token reaches JavaScript.
- Refresh tokens rotate on every use. Re-presenting a rotated token is
  treated as theft and revokes every session for that account.
- Changing a password revokes all outstanding refresh tokens.
- Login returns one message for both "no such account" and "wrong password",
  and spends the same time on each, so accounts cannot be enumerated.
- `admin` cannot be self-assigned at registration (schema-level and
  service-level).
- `PATCH /users/profile` rejects unknown fields, so role/email/is_active are
  unreachable from it.
- **Rotate `SUPABASE_SERVICE_ROLE_KEY` if it was ever committed or shared** —
  it bypasses RLS entirely.

## Scope

Implemented: authentication and authorization only.

The frontend's `src/services/endpoints.ts` declares roughly sixty routes
across patients, digital twins, predictions, simulations, documents, OCR,
reports, admin and research. Those are **not** implemented here; the frontend
continues to serve them from fixtures until `VITE_API_BASE_URL` is set, at
which point only the auth routes have a live backend. `app/api/v1/router.py`
is where each new module's router gets registered.
