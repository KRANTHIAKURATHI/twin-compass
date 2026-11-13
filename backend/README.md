
# OncoTwin Backend

The OncoTwin backend is a FastAPI application providing persistent APIs and application services for breast cancer patient record management, Digital Twin versioning, prediction, research prognosis, treatment simulation, scenario comparison, and scenario promotion.

## 1. Architecture

The backend follows a modular architecture:

```text
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── router.py
│   │       └── routers/
│   ├── auth/
│   ├── core/
│   ├── db/
│   ├── middleware/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── ml/
│   │   ├── artifacts/
│   │   ├── survival/
│   │   └── survival_rfs/
│   └── main.py
│
├── tests/
├── alembic/
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

Each functional area is separated into routers, schemas, services, and persistence components.

## 2. Implemented Backend Modules

| Module | Responsibilities |
|---|---|
| Authentication | Registration, login, token verification, refresh, logout, password reset |
| Authorization | Role-based access control and protected operations |
| Patient Management | Patient creation, retrieval, editing, and status management |
| Digital Twin | Active Twin, version history, clinical snapshots, synchronization, and comparison |
| Prediction | WDBC classification and heuristic estimates |
| Research Prognosis | METABRIC OS and RFS survival estimates |
| Treatment Simulation | Deterministic kinetic projections |
| Scenario Comparison | Comparison of stored simulation scenarios |
| Scenario Promotion | Promotion of eligible scenarios into treatment plans |
| Documents | Clinical document management |
| OCR | Document text extraction |
| Analytics | Application analytics |
| Reports | Report-related backend functionality |
| Notifications | Notification operations |

The FastAPI application mounts the route modules through:

```text
app/api/v1/router.py
```

The application entrypoint is:

```text
app/main.py
```

Routes are mounted using the configured API router. Refer to the router modules for exact HTTP paths and request/response contracts.

## 3. Database and Persistence

The backend uses SQLAlchemy for database access and Alembic for migrations.

Supported configurations include:

| Mode | Database |
|---|---|
| Local development | SQLite |
| PostgreSQL deployment | PostgreSQL |
| Supabase deployment | Supabase PostgreSQL and Auth integration |

The local SQLite configuration is designed for development without requiring an external database service.

PostgreSQL deployments require the correct database URL, environment configuration, and migration setup.

## 4. Authentication and Authorization

The authentication layer supports local and Supabase-based provider configurations.

The local provider uses:

- bcrypt password hashing
- JWT access tokens
- Refresh-token storage and rotation
- Session invalidation
- Password-reset workflow
- Role-based authorization checks

The Supabase provider uses Supabase Auth for identity management and verifies Supabase-issued tokens.

Sensitive credentials must be supplied through environment variables. Never commit `.env` files, service-role keys, JWT secrets, or database credentials.

## 5. Machine Learning Components

### 5.1 WDBC Classifier

The diagnostic classification component uses a Random Forest model trained on the Wisconsin Diagnostic Breast Cancer dataset.

| Property | Value |
|---|---|
| Dataset | WDBC |
| Records | 569 |
| Features | 30 |
| Algorithm | Random Forest |
| Trees | 300 |
| Benchmark accuracy | 95.61% |
| Benchmark precision | 95.89% |
| Benchmark recall | 97.22% |
| Benchmark ROC-AUC | 99.31% |

**Important:** Application patient records do not contain the original 30 WDBC features. The current inference adapter constructs a synthetic WDBC-shaped feature vector from a hand-engineered clinical severity score. The benchmark metrics are not evidence of accuracy on real patient records.

### 5.2 METABRIC Overall Survival (OS)

The OS research pipeline models the time-to-event outcome using:

```text
OS_MONTHS
OS_STATUS
```

Candidate algorithms:

- Cox Proportional Hazards
- Random Survival Forest

The saved artifact selects Cox Proportional Hazards according to the documented model-selection rule.

### 5.3 METABRIC Relapse-Free Survival (RFS)

The RFS pipeline models:

```text
RFS_MONTHS
RFS_STATUS
```

It independently evaluates Cox Proportional Hazards and Random Survival Forest candidates. The saved artifact also selects Cox Proportional Hazards.

### 5.4 Survival Model Inference

The application maps available patient fields to METABRIC model features:

- Age
- Positive lymph nodes
- Tumour size
- Tumour grade
- Tumour stage
- ER status
- PR status
- HER2 status

Other METABRIC training features are not recorded in the application and are not fabricated during inference. The saved preprocessing pipeline handles missing features.

The training feature set also includes a claudin/PAM50 molecular-subtype field derived from expression data. Raw gene-expression measurements are not directly used as model features.

The survival models are research prototypes. They have not undergone external clinical validation and are not treatment-response models.

Detailed methodology and reproduction instructions are available in:

```text
app/ml/survival/README.md
```

### 5.5 Treatment Simulation

The simulator uses a deterministic kinetic formulation based on log-kill and exponential regrowth.

It is not a trained machine-learning model.

Its regimen parameters are unvalidated. Custom dose information is recorded but is not currently modelled quantitatively in the equations. Its numerical outputs are hypothetical research projections.

## 6. Prediction and Prognosis Separation

The backend keeps the following outputs distinct:

| Component | Purpose |
|---|---|
| WDBC Random Forest | Malignancy classification benchmark |
| Heuristic estimates | Rule-based survival and recurrence estimates |
| METABRIC OS | Research overall-survival estimates |
| METABRIC RFS | Research relapse-free-survival estimates |
| Treatment simulator | Hypothetical kinetic projections |

The METABRIC research prognosis is exposed separately through:

```http
GET /predictions/{patient_id}/prognosis
```

The prediction run endpoint also returns an additive prognosis response when available. These survival estimates are not classifier confidence scores and are not treatment-response predictions.

## 7. Environment Setup

### Prerequisites

- Python 3.13 or compatible version
- pip
- Git

### Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

For development and testing:

```bash
pip install -r requirements-dev.txt
```

### Configure Environment

```bash
cp .env.example .env
```

Review the configuration before starting the server.

The default local configuration uses SQLite. Configure PostgreSQL or Supabase environment variables only when using those services.

### Start the Backend

```bash
uvicorn app.main:app --reload --port 8000
```

Health endpoints:

```text
GET /health
GET /health/ready
```

## 8. Database Migrations

For PostgreSQL or Supabase deployments:

```bash
alembic upgrade head
```

To create a migration:

```bash
alembic revision -m "describe_schema_change"
```

To roll back one migration:

```bash
alembic downgrade -1
```

Use migrations for schema changes and verify the target database before applying them.

## 9. Testing

Run the backend tests:

```bash
pytest -q
```

The test suite includes service, API, persistence, Digital Twin, prediction, simulation, comparison, promotion, and other backend tests.

Some tests are conditional on external resources:

| Test category | Requirement |
|---|---|
| PostgreSQL integration and security tests | PostgreSQL test database URL |
| METABRIC real-data verification | Original METABRIC clinical files |
| Local application tests | Local test configuration and dependencies |

### Recorded Verification Results

The documented verification run at commit `17e5a1f` (12 November 2026) reported:

| Result | Count |
|---|---:|
| Passed | 784 |
| Failed | 3 |
| Skipped | 222 |
| Modules with collection errors | 12 |

The three failures and twelve collection errors were associated with legacy test modules. The skipped tests required PostgreSQL or raw METABRIC files that were unavailable in the verification environment.

These figures describe that specific verification run and must not be assumed to describe later commits. Re-run the suite to establish the current status.

## 10. Security Considerations

- Never commit environment files or credentials.
- Rotate any exposed Supabase service-role key or JWT secret.
- Keep privileged operations behind authorization checks.
- Use HTTPS in deployed environments.
- Apply appropriate access controls to patient information.
- Configure database access and row-level security appropriately.
- Avoid logging passwords, access tokens, or sensitive clinical data.
- Review audit logging and privacy requirements before any real clinical deployment.

## 11. Research and Clinical Limitations

The backend is a research software implementation and is not clinically validated.

Important limitations:

1. The WDBC classifier receives constructed rather than measured WDBC features during patient inference.
2. METABRIC survival models have not been externally validated.
3. Treatment simulation parameters are unvalidated.
4. Custom dose is recorded but not modelled quantitatively.
5. The offline GEO treatment-response experiment is not served by an application endpoint.
6. No clinical effectiveness or safety claims have been established.

Do not use the application outputs for diagnosis, treatment selection, or clinical decision-making.

## 12. Related Documentation

- Root project documentation: [`../README.md`](../README.md)
- Survival model methodology: [`app/ml/survival/README.md`](app/ml/survival/README.md)
- Research paper: OncoTwin Research Paper

---

**OncoTwin Backend — Research Software for Breast Cancer Clinical-State Digital Twin Workflows**
