# OncoTwin deployment runbook (Vercel + Render + Supabase)

Status: prepared on branch `phase-6-deployment`. Nothing here has been run against production. No secret value appears
in this file; variable *names* and formats come from `backend/app/core/config.py`, `nitro.config.ts` and `src/services/`.

## 0. Order of operations

1. Supabase: take a backup / confirm point-in-time recovery, then apply schema (section 3).
2. Render: create the backend service, set env, deploy, confirm `/health` and `/health/ready`.
3. Vercel: set `API_PROXY_TARGET` (section 2) and deploy the frontend.
4. Bootstrap the first administrator, then approve users and assign patients (sections 4-5).
5. Run the H3 checklist (section 6) on the real domains before announcing anything.

## 1. Render (backend)

* Service type **Web Service**, runtime **Docker**, root directory `backend` (the Dockerfile installs Tesseract; the
  native Python runtime cannot, see `backend/OCR-DEPLOYMENT.md`). Health check path: `/health` (liveness, no I/O).
  `/health/ready` also checks the database and is safe to expose: it returns no error text.
* The container listens on `$PORT` (Render injects it; the Dockerfile defaults to 10000). One uvicorn process.
* Size: the image carries scikit-learn / scikit-survival / PyMuPDF / Tesseract. Start with at least 1-2 GB RAM
  (assumption, not measured; watch for out-of-memory restarts during OCR).
* Keep **one instance**. The rate limiter is in memory per process (see H4 below).
* Nothing is written to disk that needs to persist: documents live in Supabase Storage, OCR text is not stored.

Environment variables (names only; set values in Render, never in the repo):

| Variable | Value / format |
|---|---|
| `ENVIRONMENT` | exactly `prod` (accepted: `local`, `dev`, `staging`, `prod`; `production`/`development` are rejected) |
| `AUTH_PROVIDER` | `supabase` |
| `DATABASE_URL` | Supabase **pooler** connection string (port 6543, transaction mode). `postgresql://...` is accepted and upgraded to `postgresql+asyncpg://`. Do **not** append `?sslmode=...` (asyncpg rejects it). |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` | from the Supabase project settings; the service-role key must exist only on Render |
| `CORS_ALLOWED_ORIGINS` | a **JSON array** of exact origins, e.g. `["https://<frontend-domain>"]`. A bare URL or comma list fails at boot. No `*`. |
| `REFRESH_COOKIE_SAMESITE` | `lax` (the default; do not set `none`) |
| `REFRESH_COOKIE_SECURE` | leave unset (default `true`; `prod` refuses `false`) |
| `PASSWORD_RESET_REDIRECT_URL` | `https://<frontend-domain>/reset-password` (the default points at localhost) |
| `SUPABASE_STORAGE_BUCKET` | default `clinical-documents`; the bucket must exist and be **private** |
| `ACCESS_TOKEN_TTL_SECONDS` | only used by the local provider. In Supabase mode the access-token lifetime is the project's JWT expiry setting. |
| `OCR_PROVIDER` | `tesseract` (image default) |

`CORS_ALLOWED_ORIGINS` is also the allow-list for the refresh/logout CSRF check. It must contain **every** origin users
actually browse from (custom domain and any `*.vercel.app` alias they use). A listed-nowhere origin can log in (login is
not origin-gated) but its `/auth/refresh` is rejected with 403, so the session ends at the next reload.

## 2. Vercel (frontend)

* Build command `npm run build`, framework Nitro/TanStack Start (the Vercel preset is selected automatically by `VERCEL`).
* **Install command: set it explicitly to `npm ci`.** The repo has both `package-lock.json` (current) and `bun.lock`
  (older); Vercel prefers Bun when `bun.lock` exists, which could install a different dependency tree.
* Environment variable `API_PROXY_TARGET` = the Render service's public `https://` base URL, no trailing path.
  Scope it to **Production and Preview** (the build fails by design if it is missing on any Vercel build, and if it is not
  `https://`).
* Do not set `VITE_API_BASE_URL` on Vercel. Production builds always use `/api` and ignore an absolute URL.
* The rewrite `/api/*` -> `<target>/*` strips the prefix; the backend has no `/api` routes.
* Previews: every preview has its own origin, so it is rejected by the refresh CSRF check unless that exact origin is in
  `CORS_ALLOWED_ORIGINS`. Verify H3 on the production (or one stable alias) domain.

## 3. Supabase (database) - nothing is applied automatically

Two migration systems, in this order:

1. **Alembic** (`backend/alembic`): creates `roles`, `profiles`, `user_roles` (+ local-auth tables). The API refuses to
   start without `profiles`. Run `alembic upgrade head` once (Render shell or a trusted machine with `DATABASE_URL` set in
   the environment, never in a file in the repo). Production already has these tables if the OCR migration was applied.
2. **Supabase SQL** (`supabase/migrations`, apply with `supabase db push` against the linked project). New, not yet applied
   to production as far as this repo can tell (compare with `supabase migration list`):
   * `20261105120000_drop_clinical_data_defaults.sql` - drops column defaults only, no data touched.
   * `20261106120000_patient_access.sql` - new table; requires `profiles` and `patients`.
   * `20261107120000_clinical_rls.sql` - `can_read_patient()` plus SELECT-only RLS policies on clinical tables.
   Each file runs in one transaction. Try them on a Supabase branch or a restored copy first.

Before and after applying, run the read-only checks (SQL editor, as `postgres`):

```sql
-- the backend's database role must bypass RLS (the migrations assume it); expect rolbypassrls = true
select rolname, rolbypassrls, rolsuper from pg_roles where rolname = current_user;
-- RLS state of every public table
select c.relname as table_name, c.relrowsecurity as rls_enabled, c.relforcerowsecurity as rls_forced
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r' order by 1;
-- what the Data API roles can touch
select table_name, grantee, string_agg(privilege_type, ',' order by privilege_type) as privileges
from information_schema.role_table_grants
where table_schema = 'public' and grantee in ('anon', 'authenticated') group by 1, 2 order by 1, 2;
select tablename, policyname, cmd, roles from pg_policies where schemaname = 'public' order by 1, 2;
select p.proname, p.prosecdef, p.proconfig from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.proname = 'can_read_patient';
```

**Known gap to decide before launch.** The RLS migration covers the clinical tables only. These migration-created tables
have no RLS in the repo: `users` (legacy, has a `password_hash` column), `password_reset_tokens`, `audit_logs`,
`notifications`, `permissions`, `hospitals`, `departments`, `datasets`, `ml_models`, `model_versions`, `training_runs`,
`performance_points`, `patient_code_counters`. If production grants `anon`/`authenticated` access to them (Supabase's
default for new public tables), the Data API could read them with the public anon key. The checks above show whether that
is the case; if it is, enable RLS (no policies needed, the backend bypasses it) on those tables in a follow-up migration.
The frontend never calls the Data API, so this should not affect the application.

## 4. First administrator and patient access (no admin UI yet)

The admin portal pages in the frontend (users, doctors, hospitals, departments, permissions, audit) still render fixture data; they are not connected to the new
admin endpoints. Until a UI exists, run the workflow through the API.

1. Register the future admin through the normal registration page (choose Doctor: it is created with no role).
2. In the SQL editor, give that profile the admin role once:
   ```sql
   insert into user_roles (id, profile_id, role_id)
   select gen_random_uuid(), p.id, r.id from profiles p, roles r
   where p.email = '<admin e-mail>' and r.name = 'admin'
     and not exists (select 1 from user_roles ur where ur.profile_id = p.id);
   ```
3. Sign in as that admin and call the API with the access token (browser dev tools, `Authorization: Bearer ...`), through
   the frontend domain so the same-origin proxy is used:
   * `GET  /api/admin/users/pending` - accounts waiting for a role
   * `POST /api/admin/users/{profile_id}/role` - grant `doctor` / `researcher`
   * `POST /api/admin/patients/{patient_id}/access` - add a `care_team` doctor or a `self` patient login
   * `GET  /api/admin/patients/{patient_id}/access`, `DELETE .../access/{profile_id}`
4. Existing patients: run `patient-access-backfill.sql` (same folder) section 1, then 2, review, then 3. It only restates
   "the creating doctor is on the care team" from the audit trail. Everything else must be assigned by an administrator.
   Until then doctors see no patients and only administrators can open them.

## 5. After deploy: what a pending user sees

A doctor/researcher registers, gets a "pending approval" message, and cannot sign in ("no assigned role") until step 4.3.

## 6. H3 verification on the real deployment (not done yet)

On the production frontend domain, with a throwaway account, in Chrome DevTools (Network + Application):

1. Every request goes to `https://<frontend-domain>/api/...`, never to the Render hostname.
2. `GET /api/auth/me` without a token -> 401 JSON from the backend; a query string (`/api/patients?search=a`) arrives intact.
3. Login: `Set-Cookie` shows `HttpOnly; Secure; SameSite=Lax; Path=/`, no `Domain`; the cookie is not in `document.cookie`;
   `localStorage`/`sessionStorage` hold no token.
4. Reload: exactly one `POST /api/auth/refresh`, status 200; the app stays signed in.
5. `POST /api/auth/refresh` and `/api/auth/logout` with a forged `Origin` (fetch from another site's console) -> 403,
   and the real session still refreshes afterwards.
6. A preflight from an unlisted origin gets no `Access-Control-Allow-Origin`; no response ever carries `*`.
7. Open a second tab: it restores with one refresh; sign out in one tab signs the other out.
8. Logout -> cookie cleared; a refresh afterwards is 401.
9. Upload a small PDF (and, if OCR is in scope, run OCR) to confirm multipart bodies pass the rewrite.

## 7. H4 (rate limiting) - open

The limiter is in memory, keyed on the connecting address (`request.client.host`), and uvicorn trusts forwarded headers
only from `127.0.0.1`. Verified locally: forged `X-Forwarded-For` does not change the key, and two instances keep separate
buckets. **Not verified on Render/Vercel:** what address the backend actually sees (probably Render's proxy, i.e. one shared
bucket for all users), and whether `/auth/login` etc. then throttle everyone together. Do not set `FORWARDED_ALLOW_IPS=*`.
Run one instance. Only login, register, forgot-password and reset-password are limited; refresh, logout, upload and OCR are not.

## 8. Supabase Auth notes

* In Supabase mode the refresh-token rotation and reuse detection are Supabase Auth's own (project settings); the atomic
  single-use rotation implemented and tested in this repo applies to `AUTH_PROVIDER=local` only. The cross-tab Web Locks
  coordination in the frontend still prevents tabs racing each other.
* Configure Auth e-mail (SMTP/templates) and the site/redirect URLs to the frontend domain; confirm whether e-mail
  confirmation is required before login.

## 9. Rollback

* Render/Vercel: redeploy the previous build.
* Migrations 20261105/06/07 are additive or policy-only. To undo RLS: `DROP POLICY ... ` for the `*_patient_scope` policies
  and `ALTER TABLE ... DISABLE ROW LEVEL SECURITY` (the backend is unaffected either way because it bypasses RLS).
