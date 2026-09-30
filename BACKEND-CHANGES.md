# Backend review & rebuild — what changed and why

Every finding below was reproduced by running the code, not by reading it.

---

## 1. Blocking: the backend could not serve any database request

`GET /auth/me` with a valid token returned **HTTP 500**. So did login,
register and every other endpoint that touched the database.

`user_roles` has two foreign keys to `profiles.id` — `profile_id` and
`granted_by`. `UserRole.profile` declared `foreign_keys=[profile_id]`, but
`Profile.user_roles` did not, so SQLAlchemy could not choose a join condition
and raised `AmbiguousForeignKeysError` the moment any mapper was configured —
i.e. on the first real query.

**Fixed** in `app/models/identity.py` by declaring `foreign_keys` on both
sides. Pinned by `tests/test_provider_modes.py::test_identity_mappers_configure`.

**Why 27 tests didn't catch it:** `tests/test_auth_endpoints.py` overrode both
`get_auth_service` and `get_current_user` with fakes, so the suite never
constructed the real object graph. That is the more important problem, and
it is addressed in §9.

---

## 2. Every access log had `request_id: null`

Starlette applies middleware in **reverse** registration order — the last one
added is outermost. The original registered `RequestIdMiddleware` first
intending it to run first, which actually made it *innermost*, so
`LoggingMiddleware` ran outside the request-id context and the correlation id
it exists to record was always `null`.

**Fixed** in `app/main.py`; runtime order is now
RequestId → CORS → Logging → RateLimit → route.

---

## 3. Rate-limit responses broke the frontend error contract

`main.py` registered slowapi's default handler *after* the enveloped one,
overriding it. A 429 returned `{"error": "Rate limit exceeded: ..."}` — a
string where `src/services/api-client.ts` expects an object, so `ApiError`
lost its code and message.

**Fixed**: the override is removed; 429 now returns the standard envelope
with a `request_id`. Pinned by
`test_rate_limiting_returns_the_envelope_not_a_bare_string`.

---

## 4. Half of gotrue's exceptions escaped as 500s

`except AuthApiError` misses `AuthSessionMissingError`,
`AuthInvalidCredentialsError` and `AuthRetryableError` — they derive from
`CustomAuthError`, not `AuthApiError`. An expired reset link produced a 500
instead of a 401; a network blip produced a 500 instead of a 502.

**Fixed**: the common base `AuthError` is caught, plus `SupabaseException`
for a malformed or placeholder API key (which `create_client` raises eagerly).

---

## 5. Synchronous Supabase calls blocked the event loop

`supabase-py`'s client is synchronous and was called directly inside
`async def` handlers, so one slow Supabase round-trip stalled every other
in-flight request.

**Fixed**: all SDK calls go through `anyio.to_thread.run_sync`.

---

## 6. Migrations were Supabase-only

`0001` declared a hard foreign key to `auth.users.id` and created RLS
policies calling `auth.uid()`. Neither exists outside a Supabase project, so
the migration could not run on plain PostgreSQL or SQLite at all.

**Fixed**: the migration detects its target. The `auth.users` FK and the
`auth.uid()` policies are created only when the Supabase `auth` schema is
present; RLS is applied on PostgreSQL generally; `sa.Uuid` renders natively
on PostgreSQL and as `CHAR(32)` elsewhere. Verified `upgrade head` +
`downgrade base` on SQLite, plain PostgreSQL 16, and a simulated Supabase
schema.

---

## 7. The password policy disagreed with itself

Registration required a letter and a digit. Reset-password required only a
length floor — so a user could reset their way to a password that
registration would have refused.

**Fixed**: one policy in `app/core/passwords.py`, imported by both schemas
and configurable via `PASSWORD_*` settings.

---

## 8. Connection pooling contradicted its own docstring

`app/db/session.py` documented `NullPool` (correct in front of Supabase's
transaction-mode PgBouncer) but actually used the default `QueuePool` with
`pool_pre_ping` — exactly the configuration the comment warned against.

**Fixed**: `NullPool` plus `statement_cache_size=0` for asyncpg; SQLite gets
`check_same_thread=False`. The engine is now built lazily, so importing any
module no longer requires a reachable database.

---

## 9. Tests that could not fail

Rewritten. `tests/test_auth_flow.py` runs the **real** service, repository and
provider against a temporary SQLite database; only the DB session is
overridden. 78 tests pass, covering registration, case-insensitive duplicate
detection, login, token verification, refresh rotation, replay detection,
logout revocation, the full reset flow, session invalidation on password
change, profile updates and role-escalation attempts.

---

## 10. Credentials were in the archive

`backend/.env` shipped with a live `SUPABASE_SERVICE_ROLE_KEY` and
`SUPABASE_JWT_SECRET`. It is gitignored, but it was in the zip you sent.

**Action required on your side: rotate both in the Supabase dashboard.**
A service-role key bypasses RLS entirely. The `.env` in this archive now
contains file-mode defaults and no secrets.

---

## New capability: the backend runs with or without Supabase

`AUTH_PROVIDER` selects the identity backend behind a provider interface
(`app/auth/providers/`). Nothing above that seam changes, so the HTTP
contract is identical either way.

- **`local` (default)** — bcrypt credentials in `local_credentials`, HS256
  tokens signed locally with the same claim shape Supabase emits, refresh
  tokens stored SHA-256-hashed and rotated on every use with replay
  detection, account lockout after repeated failures, constant-time handling
  of unknown emails, reset links written to
  `data/password-reset-links.log`. SQLite file DB, schema and roles seeded on
  boot. **No network, no Postgres, no Supabase.**
- **`supabase`** — as before, now non-blocking and with correct error mapping.

Startup validates the combination and refuses impossible ones (Supabase mode
with a SQLite URL; a generated signing secret in production; insecure cookies
in production), naming exactly what is missing.

### Other additions
- `GET /health/ready` reports mode and database reachability.
- Registration now rolls back the provider user if the profile write fails.
  Previously that left an orphaned credential and permanently wedged the
  email address.
- Frontend: `/auth/refresh` was implemented by the backend but absent from
  `endpoints.ts` / `contracts.ts`, so it was unreachable. Now wired up.

---

## Scope — please read

The backend implements **authentication only**. Your frontend's
`src/services/endpoints.ts` declares ~60 routes across patients, digital
twins, predictions, simulations, documents, OCR, reports, admin and research.
Those have no backend implementation in this codebase and still resolve from
fixtures. "All features working" is not reachable from what was uploaded —
the remaining modules have to be built. `app/api/v1/router.py` is where each
new module's router gets registered.
