
# OncoTwin — AI-Powered Breast Cancer Digital Twin Platform

OncoTwin is a research-oriented web application for breast cancer patient information management, versioned clinical-state Digital Twins, exploratory prediction, and hypothetical treatment scenario comparison.

The platform combines a React and TypeScript frontend with a FastAPI backend and persistent database storage.

> **Research disclaimer:** OncoTwin is a software research platform. It is not a clinically validated biological Digital Twin, does not provide medical advice, and must not be used to make treatment decisions.

## 1. Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite |
| Routing and data | TanStack Router, TanStack Query |
| UI | Tailwind CSS, Radix UI |
| Charts | Recharts |
| Backend | Python, FastAPI, Uvicorn |
| Validation | Pydantic |
| Database | SQLAlchemy, SQLite, PostgreSQL |
| Migrations | Alembic |
| Authentication | JWT, bcrypt, Supabase Auth provider |
| Machine Learning | scikit-learn, NumPy, SciPy |
| Survival Analysis | scikit-survival, pandas |
| Document Processing | PyMuPDF, Pillow, pytesseract |

## 2. Project Structure

```text
twin-compass/
├── src/                         # React frontend
│   ├── routes/                  # Application routes
│   ├── components/              # UI components
│   ├── services/                # API clients and data services
│   ├── hooks/                   # Application hooks
│   └── types/                   # TypeScript types
│
├── backend/
│   ├── app/
│   │   ├── api/v1/routers/      # FastAPI route modules
│   │   ├── auth/                # Authentication and authorization
│   │   ├── models/              # Database models
│   │   ├── schemas/             # Request and response schemas
│   │   ├── services/            # Application services
│   │   ├── ml/                  # ML and research model components
│   │   │   ├── artifacts/       # WDBC model artifacts
│   │   │   ├── survival/        # METABRIC OS model
│   │   │   └── survival_rfs/    # METABRIC RFS model
│   │   └── main.py              # FastAPI application entrypoint
│   ├── tests/                   # Backend automated tests
│   ├── requirements.txt
│   └── requirements-dev.txt
│
├── supabase/                    # Supabase configuration
├── docs/                        # Architecture and project documentation
├── package.json
└── README.md
```

## 3. Implemented Functional Modules

The backend provides application services for the following workflows:

| Module | Functionality |
|---|---|
| Authentication | Registration, login, token verification, refresh, logout, password reset |
| Authorization | Role-based access control and protected operations |
| Patient Management | Patient record creation, retrieval, editing, and status management |
| Digital Twin | Active Twin, version history, clinical snapshots, synchronization, and comparison |
| Prediction | WDBC-based classification and heuristic estimates |
| Research Prognosis | Separate METABRIC overall-survival and relapse-free-survival estimates |
| Treatment Simulation | Deterministic kinetic treatment scenario projections |
| Scenario Comparison | Comparison of stored treatment scenarios |
| Scenario Promotion | Promotion of eligible scenarios into a patient treatment plan |
| Documents and OCR | Document management and clinical document text extraction |
| Analytics and Reports | Application analytics and report-related workflows |
| Notifications | Backend notification endpoints |

The application uses a shared Active Twin clinical state as the source for prediction, prognosis, and simulation workflows.

## 4. Machine Learning and Research Components

OncoTwin contains separate computational components with different datasets and purposes.

### 4.1 WDBC Random Forest Classifier

- Dataset: Wisconsin Diagnostic Breast Cancer (WDBC).
- 569 records and 30 numerical features.
- Random Forest classifier with 300 trees.
- Benchmark accuracy: approximately 95.61%.
- Benchmark ROC-AUC: approximately 99.31%.

**Important limitation:** The patient application does not collect the original 30 WDBC measurements. It constructs a synthetic WDBC-shaped feature vector from a hand-engineered clinical severity score. Therefore, benchmark metrics must not be interpreted as predictive accuracy on real patient records.

### 4.2 METABRIC Survival Models

Two separate research survival models use METABRIC clinical data:

- Overall Survival (OS): Cox Proportional Hazards and Random Survival Forest candidates.
- Relapse-Free Survival (RFS): Cox Proportional Hazards and Random Survival Forest candidates.

The saved artifacts select Cox Proportional Hazards for both endpoints.

The application maps available patient clinical fields to the model inputs. Features that are not recorded by OncoTwin are left missing and handled by the saved preprocessing pipeline.

These models are research prototypes and have not undergone external clinical validation.

### 4.3 Treatment Simulation

The treatment simulator uses a deterministic kinetic formulation based on log-kill and exponential regrowth.

It is not a trained machine-learning model. Its regimen parameters are unvalidated, and its projections are hypothetical rather than clinically established treatment outcomes.

### 4.4 Explainability

The platform includes clinical-factor contribution estimates over the hand-engineered severity score and cohort-level Pearson correlation analysis.

These are not SHAP values or individual Random Forest feature attributions.

## 5. Datasets

| Dataset | Purpose | Status |
|---|---|---|
| WDBC | Malignancy classification benchmark | Integrated |
| METABRIC | Overall-survival and relapse-free-survival research models | Integrated |
| TCGA-BRCA | Potential future research and validation | Not integrated |
| GEO GSE163882 | Offline treatment-response research experiment | Not served by an application endpoint |

The raw METABRIC clinical files are not included in the repository. Their file hashes are recorded in the model artifact metadata.

## 6. Getting Started

### Prerequisites

- Node.js 22 or compatible version
- Python 3.13 or compatible version
- npm
- Git

### Backend Setup

```bash
git clone https://github.com/KRANTHIAKURATHI/twin-compass.git
cd twin-compass

cd backend

python -m venv .venv
```

Activate the environment:

```bash
# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

The default local configuration uses SQLite. PostgreSQL/Supabase configuration requires the corresponding environment variables and database migrations.

Backend health endpoints:

```text
GET http://localhost:8000/health
GET http://localhost:8000/health/ready
```

### Frontend Setup

Open a second terminal:

```bash
cd twin-compass
npm install
```

Create a frontend `.env` file:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Start the frontend:

```bash
npm run dev
```

Open:

```text
http://localhost:5173
```

The frontend API client uses `VITE_API_BASE_URL` to connect to the backend. Without the variable, backend-dependent requests are not configured to use the local API.

## 7. Testing and Verification

### Backend

```bash
cd backend

pip install -r requirements-dev.txt

pytest -q
```

Some tests require external resources:

- PostgreSQL test database URL for PostgreSQL-specific integration and security tests.
- Raw METABRIC clinical files for real-data survival model verification.

### Frontend

```bash
npm test
```

TypeScript check and production build should also be run using the project's configured scripts and tooling.

### Recorded Verification Results

At repository commit `17e5a1f` (12 November 2026), the documented verification run reported:

| Verification | Result |
|---|---:|
| Backend tests passed | 784 |
| Backend tests failed | 3 |
| Backend tests skipped | 222 |
| Backend collection errors | 12 modules |
| Frontend tests passed | 97 |
| Frontend tests failed | 0 |
| TypeScript check | Passed |
| Production build | Passed |
| Browser E2E in final run | Not re-executed |

The three backend test failures and twelve collection errors were associated with legacy test modules. The skipped tests required PostgreSQL or raw METABRIC files unavailable in that verification environment.

These are software verification results, not clinical or model validation results. They should not be assumed to describe a later repository commit without rerunning the checks.

## 8. Research Limitations

- The WDBC benchmark classifier uses constructed rather than measured WDBC inputs in the application.
- METABRIC survival models have not undergone external clinical validation.
- Treatment simulation parameters are not clinically validated.
- The treatment simulator does not model custom dose quantitatively.
- The offline GEO treatment-response experiment is not integrated into an application prediction endpoint.
- Clinical effectiveness and safety have not been established.
- Demonstration records must not be assumed to be real, anonymized, or consented clinical data.

## 9. Future Work

- Replace synthetic classifier inputs with a validated clinical feature pipeline.
- Perform independent external validation of METABRIC survival models.
- Evaluate model calibration and uncertainty.
- Integrate suitable datasets such as TCGA-BRCA for clearly defined research tasks.
- Develop evidence-supported treatment-response models.
- Improve patient-specific toxicity and recovery modelling.
- Add individual-level model explainability.
- Strengthen healthcare data governance, audit logging, privacy, and security.
- Conduct clinical expert evaluation and appropriate ethical review.

## 10. Documentation

For backend-specific setup, configuration, database migrations, API behavior, and testing, see:

[`backend/README.md`](backend/README.md)

For the research methodology, datasets, model evaluation, limitations, and verification record, refer to the OncoTwin research paper.

---

## Disclaimer

OncoTwin is an academic research software project. It is intended for software development, demonstration, and research exploration. It is not a medical device, diagnostic system, or treatment recommendation tool.
