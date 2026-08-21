# OncoTwin Backend

A FastAPI backend for the OncoTwin frontend (`../src`), implementing every
endpoint listed in `../src/services/endpoints.ts` for the core clinical
workflow: auth, patients, digital twins, predictions, treatment simulation,
and analytics — plus real (if simpler) CRUD for documents/OCR/reports/
appointments/notifications/admin/research. No route returns hardcoded or
random fixture data; every response is read from the database or computed
by the trained model / rule engine in `app/ml/`.

## Prediction model

Trained on the **Wisconsin Diagnostic Breast Cancer** dataset bundled with
scikit-learn (`sklearn.datasets.load_breast_cancer`) — 569 real, publicly
documented samples, 30 numeric features per sample, binary malignant/benign
label. A patient's real clinical fields (stage, grade, Ki-67, nodes
involved, tumor size, receptor status, age) are combined into a severity
score and interpolated between the dataset's real benign/malignant feature
centroids, then run through a trained `RandomForestClassifier`. See
`app/ml/model.py` and `app/ml/train.py` for the full pipeline and
`app/ml/regimens.py` for how the Treatment Simulator perturbs that severity
per regimen.

Retrain any time with:

```sh
python -m app.ml.train
```

This writes `app/ml/artifacts/model.joblib` and `metrics.json` (real
accuracy/precision/recall/AUC + 5-fold CV curve — this is what seeds the
Research → Performance page).

## Setup

```sh
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # macOS/Linux

pip install -r requirements.txt
copy env.example .env          # Windows; `cp` on macOS/Linux
uvicorn app.main:app --reload --port 8000
```

On first startup the app will:
1. Apply all pending Alembic migrations (creating SQLite file `onco_twin.db`
   by default) — see "Database migrations (Alembic)" below.
2. Train the model if `app/ml/artifacts/model.joblib` doesn't exist yet.
3. Seed one admin login and reference data (see "First login" below) —
   no patients, predictions, or documents are seeded.

Then point the frontend at it: in the frontend project root, set
`VITE_API_BASE_URL=http://localhost:8000` (see `../src/services/api-client.ts`)
and restart the frontend dev server.

## First login

```
email:    admin@oncotwin.io
password: ChangeMe123!
```

Change this password immediately, or register a fresh doctor/researcher/
admin account via `POST /auth/register`.

## Database migrations (Alembic)

Schema changes are tracked as Alembic revisions in `app/migrations/versions/`,
not created ad-hoc. `env.py` reads `DATABASE_URL` from the same settings the
app uses, so migrations always target whatever database you've configured.

```sh
alembic upgrade head              # apply pending migrations (also runs on app startup)
alembic revision --autogenerate -m "describe the change"   # after editing app/models.py
alembic downgrade -1              # roll back one revision
```

If you already had a database created by the old `Base.metadata.create_all()`
behavior (pre-Alembic), stamp it at the baseline instead of re-running DDL
against existing tables:

```sh
alembic stamp head
```

`supabase_schema.sql` is a hand-maintained mirror of the same schema for
provisioning a Supabase project directly via its SQL editor (useful if you
want to review/adjust the DDL before the app ever touches the database).
If you use it, run `alembic stamp head` against that database afterward so
Alembic knows the baseline is already applied — see "Switching to Supabase"
below. The migrations directory is still the source of truth for schema
*changes* going forward; keep this file in sync manually when you add
columns/tables.

## Switching to Supabase

Set `DATABASE_URL` in `.env` to your Supabase project's Postgres connection
string:

```
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

Tables are created by running `alembic upgrade head` (automatically on app
startup, or manually — see "Database migrations" above). If you'd rather
provision the tables yourself in the Supabase SQL editor first — e.g. to
review/adjust constraints before the app ever touches the database — run
`supabase_schema.sql` once, then `alembic stamp head` against the same
`DATABASE_URL` so Alembic treats the baseline as already applied.

Then install the Postgres driver (kept out of the default install since it
needs a C++ toolchain on some platforms):

```sh
pip install -r requirements-postgres.txt
```

Restart the app — table
creation and seeding run automatically against whatever `DATABASE_URL`
points to. No code changes are required; every model in `app/models.py`
uses plain SQLAlchemy types (String/Integer/Float/Boolean/JSON) that map
directly onto Postgres. If you'd rather use Supabase's client/RLS instead
of a direct Postgres connection, the routers are the only layer that would
need to change — schemas (`app/schemas.py`) and the ML pipeline are
storage-agnostic.

## API docs

Interactive Swagger UI: `http://localhost:8000/docs`

## What's real vs. what's a documented simplification

Real: auth (JWT + bcrypt), all patient/twin/prediction/simulation data,
analytics aggregates, role-based access control (doctor/admin write clinical
records, `patient`-role users are scoped to their own record by email match),
audit logging (actor + role + before/after diffs on patient mutations), CSV/PDF
report generation, admin data.

## Tests

```sh
pip install -r requirements.txt   # pytest + httpx
pytest tests -v
```

Each test gets its own throwaway SQLite file (created directly from
`Base.metadata`, no Alembic involved) and a `TestClient` with `get_db`
overridden to it — no test ever touches your local `onco_twin.db`. Covers
auth, patient CRUD (including patient-code sequencing and soft delete), RBAC
(`patient`-role write/read scoping), and audit log enrichment.

Simplified (clearly marked with comments in code, no external service
wired up yet):
- **OCR** (`app/routers/ocr.py`): documents are stored as metadata only
  (per the frontend's current contract — see
  `../docs/backend-integration-report.md`), so `extract` runs a
  deterministic category-based field template rather than real image OCR.
  Swap in Tesseract/Textract/an LLM vision call once scanned files are
  actually stored.
- **Forgot password email**: a real reset token is generated and stored
  with a 1-hour expiry, but no email provider is wired up — in
  `ENVIRONMENT=development` the token is returned directly in the
  response so you can test the reset flow end-to-end.
- **Simulation `save`**: the frontend's `ScenarioDraft` payload doesn't
  include a `patientId` (see `SimulationService.save` in
  `../src/services/contracts.ts`), so the backend attaches the saved
  scenario to the first patient in the database. Consider adding
  `patientId` to that payload on the frontend if you want this to target
  a specific patient without ambiguity.

## Endpoint groups implemented

Auth · Patients (+ labs/imaging/timeline) · Digital Twins (+ versions/
snapshots/resync/restore/archive) · Predictions (+ history/confidence-trend/
explainability) · Simulations (+ save/duplicate/promote) · Documents ·
OCR · Reports (+ CSV/PDF download) · Appointments · Treatment Plan ·
Notifications · Analytics · Admin · Research · Global Search.
