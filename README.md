# OncoTwin — AI-Driven Digital Twin for Personalized Cancer Progression and Treatment Outcome Simulation

Full project: React/TanStack frontend + FastAPI backend.

```
.                     React + TypeScript + Vite frontend
├── src/              routes, components, services, types
├── backend/          FastAPI backend (Module 1: auth) — see backend/README.md
├── supabase/         Supabase project config
├── docs/             architecture and integration notes
└── BACKEND-CHANGES.md   what was broken, what was fixed, and how it was verified
```

`node_modules/` and `.venv/` are deliberately not included — they are
machine- and OS-specific and are recreated by the install steps below. The
`node_modules` in the previously uploaded archive had been installed on
Windows (`@rolldown/binding-win32-x64-msvc`), so it could not build on any
other platform; reinstalling per machine is the fix.

---

## 1. Backend (start this first)

Runs in two modes. The default needs **nothing external** — no Supabase, no
PostgreSQL, no network.

```sh
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # already set to file mode
uvicorn app.main:app --reload --port 8000
```

Confirm:

```sh
curl localhost:8000/health/ready
# {"status":"ok","auth_provider":"local","database":"sqlite","database_ok":true,...}
```

A SQLite database and the four seed roles are created on first boot. To use
Supabase instead, see `backend/README.md`.

## 2. Frontend

```sh
npm install
```

Create `.env` in the project root:

```
VITE_API_BASE_URL=http://localhost:8000
```

That single variable switches the app from fixtures to the live backend
(`src/services/api-client.ts`). Then:

```sh
npm run dev      # http://localhost:5173
```

Leaving `VITE_API_BASE_URL` unset keeps the whole UI running on typed
fixtures, which is still the only way to view the modules that have no
backend yet (see Scope).

## 3. Verify the two halves are talking

```sh
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"secret123","name":"Dr You","role":"doctor"}'
```

Then sign in through the UI at `/login` with those credentials.

---

## Scope — what actually has a backend

**Implemented:** authentication and authorization.

```
POST /auth/register        POST /auth/refresh          GET   /auth/me
POST /auth/login           POST /auth/forgot-password  PATCH /users/profile
POST /auth/logout          POST /auth/reset-password
GET  /health               GET  /health/ready
```

**Not implemented:** everything else. `src/services/endpoints.ts` declares
roughly sixty routes across patients, digital twins, predictions,
simulations, documents, OCR, reports, admin and research. Those pages keep
resolving from fixtures even with `VITE_API_BASE_URL` set, because no server
answers them yet. `backend/app/api/v1/router.py` is where each new module's
router gets registered as it is built.

## Tests

```sh
cd backend && pip install -r requirements-dev.txt && pytest -q   # 78 tests
```

The integration tests run the real service, repository and auth provider
against a temporary SQLite database. Please don't stub the service layer in
new tests — that is precisely how a bug which made every database-backed
endpoint return HTTP 500 stayed hidden behind a green suite.

## Security

`backend/.env` previously shipped with a live `SUPABASE_SERVICE_ROLE_KEY` and
`SUPABASE_JWT_SECRET`. **Rotate both in the Supabase dashboard** — a
service-role key bypasses row-level security entirely. No secrets are present
in this archive.
