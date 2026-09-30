# Module 1 — Authentication & Authorization: Implementation Summary

**Status:** Implemented, tested (27/27 passing), integrated with the existing frontend.
**Scope:** Auth only, per the task brief — no Patients/Twins/Predictions/OCR in this module.

## What was built

- `backend/app/` — FastAPI service implementing exactly the 8 required endpoints:
  `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/refresh`,
  `POST /auth/forgot-password`, `POST /auth/reset-password`, `GET /auth/me`, `PATCH /users/profile`.
- `backend/alembic/versions/0001_identity_tables.py` — creates `roles`, `profiles`, `user_roles` only.
- `backend/tests/` — 27 passing tests (JWT verification, RBAC dependency, full HTTP contract tests
  with dependency overrides — no live Supabase/Postgres required to run this suite).
- Frontend patches (see "Frontend integration" below) fixing real bugs found in the existing
  auth pages, using only the app's own established `useAuth()`/`services` seam.

## Key decisions (with rationale)

1. **FastAPI proxies Supabase Auth; it never mints its own JWTs.** Access/refresh tokens are
   Supabase's own tokens, passed through. This matches the Database Blueprint's identity model
   exactly and avoids a second signing key to manage.

2. **Role resolved via DB lookup, not a JWT claim.** Configuring a Supabase Auth Hook to inject
   custom role claims requires project-level setup this module doesn't assume is present. A
   `profiles`/`user_roles` lookup per request (backed by an indexed FK) is simple, correct, and
   documented as upgradeable to a cached/claim-based approach later (`app/dependencies/auth.py`).

3. **Refresh token lives only in an httpOnly cookie — never in JS.** `AuthSession` (the frontend's
   own type) has no `refreshToken` field; this was a deliberate reading of that contract, not an
   omission. Access token still flows through the JSON body / `AuthProvider`'s existing
   `localStorage` persistence, unchanged from the current frontend design.

4. **`patient` added as a 4th seed role**, extending the Database Blueprint's 3-role model
   (`doctor`/`admin`/`researcher`). The frontend's finalized contract (`src/types/models.ts`,
   already committed before this module was built) requires it — a full Patient Portal with
   route guards keyed on `role: "patient"` already exists. The `roles` table was explicitly
   designed in the Database Blueprint as a low-risk lookup table for exactly this kind of
   addition; no other schema/RLS shape changed as a result.

5. **Admin cannot be self-registered.** `RegisterRequest.role` is typed as
   `Literal["doctor", "patient", "researcher"]` — Pydantic itself rejects `"admin"` before the
   service layer even runs, in addition to a server-side check. The frontend's `register.tsx`
   still visually offers "Hospital administrator" in its role select; this is a known,
   intentional mismatch — the backend enforces the correct security rule regardless of what the
   client sends. Recommend removing that option from the UI in a future (non-UI-redesign) pass.

6. **Password reset uses Supabase's native recovery-session flow.** The emailed link gives the
   frontend a temporary Supabase session; the frontend extracts its `access_token` and sends it
   as `token` to `/auth/reset-password`; the backend acts as *that* session (not the shared anon
   client) to call `update_user`. `reset-password.tsx` was patched — it previously read a `token`
   form field that didn't exist in the UI at all (see Frontend integration).

7. **Rate limiting via `slowapi`**, applied only to `login`/`register`/`forgot-password`/
   `reset-password` — the endpoints where brute-force/enumeration risk is concentrated.

## A real bug found and fixed along the way

`from __future__ import annotations` (PEP 563 postponed evaluation) in the router module, combined
with `slowapi`'s `functools.wraps`-based rate-limit decorator, silently broke FastAPI's request-body
type resolution — Pydantic models stopped being recognized as request bodies and were reinterpreted
as query parameters, failing validation on every rate-limited route. This was caught by the test
suite, not by inspection — worth flagging for any future router file that combines postponed
annotations with a decorator library.

## Frontend integration

No UI was redesigned. Changes were limited to wiring bugs in the already-built auth scaffolding:

- `login.tsx` / `patient-login.tsx`: now call `useAuth().login(...)` (so the session actually lands
  in `AuthProvider`'s context) instead of calling `authService.login(...)` directly and discarding
  the result. Both now surface a real inline error message on invalid credentials.
- `forgot-password.tsx`: the email input had no `name` attribute and the real value was never read
  (`authService.forgotPassword("demo")` was hardcoded). Fixed to read and send the real field.
- `reset-password.tsx`: read the Supabase recovery `access_token` from the URL (`?token=`, where
  the backend's `PASSWORD_RESET_REDIRECT_URL` sends it) instead of a nonexistent `token` form field
  that meant every reset silently failed before.
- `register.tsx`: now sends the selected `role` (previously collected by the UI but never sent);
  "admin" remains selectable in the UI (not a redesign) but is rejected server-side with a clear
  message, since backend enforcement is the actual security boundary regardless of UI copy.
- `TopBar.tsx`: added a sign-out affordance (there was none) using the same icon-button style as
  the existing Help/Notifications buttons, wired to `useAuth().logout()`. Now reflects the real
  signed-in user (name/role) instead of the hardcoded `doctor` fixture.
- `profile.tsx`: wired to `userService.updateProfile` + `useAuth().setUser` (a small, additive
  method added to `AuthProvider` following its existing `setRole` pattern) so a saved profile edit
  is reflected immediately across the app (e.g., TopBar). Fields outside Module 1's profile
  contract (`phone`, `experience`) stay fixture-backed and are clearly commented as such, rather
  than silently accepting edits that wouldn't actually persist — email is read-only in this form
  since changing it requires Supabase's separate re-verification flow.
- `api-client.ts`: added `credentials: "include"` to the underlying `fetch` call — required for the
  httpOnly refresh cookie to be sent/received cross-origin between the Vite dev server and the API
  — and updated its error-parsing to read the backend's actual `{error: {code, message, field}}`
  envelope shape.
- Added `UserService`/`userService.updateProfile` (`PATCH /users/profile`) to `contracts.ts`/
  `endpoints.ts`/`services/index.ts`/the `services` aggregate, following the codebase's own
  established one-liner-per-method pattern exactly.

No component was visually changed; no design tokens, layout, or copy were touched beyond the one
added TopBar icon button (styled identically to its neighbors).

### Verification performed

- `npx tsc --noEmit` → 0 errors across the entire frontend.
- `npm run build` → succeeds (TanStack Start SSR build completes cleanly).
- `npx eslint` on every touched file → 0 errors after formatting (one pre-existing `any` a few
  lines away, outside anything this module touched, left as-is — see below).
- The frontend repo already had 719 pre-existing lint (Prettier-formatting) errors across files
  unrelated to this module before any of this work began (confirmed by diffing against the
  baseline commit) — this module's changes were formatted to the project's own standard and net
  *reduced* the total error count (719 → 649) rather than adding to it. Reformatting the other
  ~600 pre-existing violations in untouched files was deliberately left out of scope for this
  module — that's a repo-wide housekeeping pass, not an Auth-module change.
- `pytest -q` → 27/27 passing (see "Testing" in `backend/README.md` for exactly what is and isn't
  covered by the automated suite vs. the manual Supabase integration checklist).

## Known limitations / follow-ups

- Registration is not transactionally atomic across Supabase Auth and our own `profiles` table — if
  the DB write fails after Supabase's `sign_up` succeeds, the auth user exists without a profile.
  Documented in `AuthService.register`; closing this needs a reconciliation job (out of scope here).
- No Supabase Auth Hook is configured for custom JWT claims — role is resolved via DB lookup per
  request (Section "Key decisions" #2). Fine at this scale; revisit if latency profiling says otherwise.
- CSRF mitigation relies on `SameSite=Lax` + the fact that the access token (not the cookie) drives
  all authorization-bearing requests. A double-submit CSRF token is a documented optional hardening,
  not implemented in this pass.
- Full integration tests against a real local Supabase instance (`supabase start`) are not included
  in the automated suite — see `backend/README.md` for the manual verification checklist.

## Extension points prepared for later modules

- `app/dependencies/auth.py`'s `get_current_user` / `require_roles(...)` are the exact dependencies
  every future module's routers will import — nothing about them is Auth-module-specific.
- `app/dependencies/services.py` establishes the DI composition-root pattern (`get_X_repository` →
  `get_X_service`) every future module's `dependencies/services.py` addition should follow.
