# OncoTwin Project Rules

## Project

OncoTwin is an AI-driven Digital Twin clinical decision-support prototype for breast-cancer progression and treatment-outcome simulation.

## Architecture

* Frontend: React + TypeScript + Vite
* Backend: FastAPI running locally
* Database: PostgreSQL hosted in Supabase
* Authentication: Supabase/local auth architecture already present
* Backend connects to Supabase PostgreSQL
* Do NOT replace the existing architecture unless explicitly required.

## Critical rules

1. Preserve working functionality.
2. Do NOT rewrite large parts of the application unnecessarily.
3. Do NOT replace real backend functionality with mock data.
4. Do NOT add fake success messages for unfinished operations.
5. Every frontend API call must correspond to a real backend endpoint.
6. Every backend endpoint must validate authentication and role permissions where required.
7. Use the existing database/schema conventions before creating new tables.
8. Do NOT use SQLite as the target database. The real target is Supabase PostgreSQL.
9. Do NOT modify or delete existing Supabase data.
10. Do NOT expose, commit, or recreate secrets from `.env`.
11. Never hardcode API keys, JWT secrets, Supabase service keys, or passwords.
12. Do not add unnecessary dependencies.
13. Prefer small, focused changes over rewrites.
14. Keep existing UI design unless a UI change is required for functionality.
15. Do not remove working features just to make tests pass.
16. Do not claim a feature works unless it is actually connected end-to-end.

## Clinical/scientific rules

* Digital Twin state/versioning is distinct from ML prediction.
* Prediction must not be represented as ML unless an actual trained model is connected.
* Treatment simulation is currently a research/prototype mathematical simulation.
* Do not describe unvalidated simulation parameters as clinically validated.
* Explainability must not call cohort correlation "SHAP" or individual model attribution.
* Preserve auditability of patient/twin/prediction/simulation changes.

## Development workflow

For each task:

1. Inspect only the relevant files.
2. State a short implementation plan.
3. Implement the smallest correct change.
4. Run relevant tests/type checks.
5. Fix errors caused by the change.
6. Report changed files and verification results.
7. Stop after the requested task.

Do not perform unrelated refactors.

## Token/context discipline

* Keep responses concise.
* Do not dump entire files into the response.
* Do not repeatedly reread unchanged files.
* Do not generate large explanations.
* Do not modify unrelated files.
* Use targeted searches.
* After completing a phase, start a fresh Claude Code session with `/clear`.
* Use `/compact` only when continuing the same task requires it.

## Important target flow

Patient
→ Clinical Data
→ Digital Twin
→ Prediction
→ Treatment Simulation
→ Explainability
→ Clinical Decision Support
→ Treatment Plan

Document workflow:

Medical Document
→ Upload
→ Storage
→ OCR
→ Extract Clinical Fields
→ Doctor Verification
→ Patient Update
→ New Digital Twin Version
→ Prediction

## Final quality requirements

Before declaring a feature complete:

* frontend endpoint exists
* backend endpoint exists
* request/response contracts match
* authentication works
* authorization works
* database operation works
* loading/error states work
* success state is real
* no TODO placeholder remains
* relevant tests pass
