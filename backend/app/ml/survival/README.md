# METABRIC overall-survival model

**Research model — not clinically validated.** An offline research/prototype
model. It is not connected to `POST /predictions/run` or any other API, and it
is not a clinical-grade predictor or a treatment-response model.

## Data
METABRIC, from the official cBioPortal clinical files `data_clinical_patient.txt`
and `data_clinical_sample.txt` (2,509 patients; one sample each, joined 1:1 on
`PATIENT_ID`, with duplicate/unmatched ids rejected). The files are not in the
repository; `metadata.json` records their SHA-256.

## Target
Overall survival as a time-to-event pair: time = `OS_MONTHS`; event = `OS_STATUS`
`1:DECEASED` → True, `0:LIVING` → False (censored). 528 patients with no
`OS_STATUS` have no target and are excluded (not imputed); 1,981 remain.

## Features (15 → 45 after encoding)
- Numeric: `AGE_AT_DIAGNOSIS`, `LYMPH_NODES_EXAMINED_POSITIVE`, `TUMOR_SIZE`, `GRADE`, `TUMOR_STAGE`.
- Categorical: `INFERRED_MENOPAUSAL_STATE`, `CLAUDIN_SUBTYPE` (PAM50 + claudin-low; the
  "molecular subtype", derived from expression), `HISTOLOGICAL_SUBTYPE`, `CHEMOTHERAPY`,
  `HORMONE_THERAPY`, `RADIO_THERAPY`, `BREAST_SURGERY`, `ER_STATUS`, `PR_STATUS`, `HER2_STATUS`.

Deliberately excluded:
- **`NPI`** — derived. On this cohort `NPI` regressed on tumour size, grade and a
  lymph-node score (1/2/3 for 0 / 1–3 / ≥4 nodes) has R² = 0.93, with coefficients ≈ 1.00 for
  grade and node score. Its components are already features, so it would only add a duplicate.
- `OS_*`, `RFS_*`, `VITAL_STATUS` — outcomes (`VITAL_STATUS` encodes the death event).
- `ER_IHC`, `HER2_SNP6` — duplicate the sample-level `ER_STATUS`, `HER2_STATUS`.
  The files have no `PR_IHC` / `HER2_IHC` columns.

## Preprocessing (fitted on the training split only)
Missing tokens (`""`, `NA`, `#N/A`, `Not Available`, `UNDEF`, …) → missing; spelling
variants (`Positve`, `YES`) canonicalised; nothing else is recoded. Numeric: median
imputation + standardisation. Categorical: missing → explicit `Unknown`, one-hot,
unseen levels → all zeros.

## Protocol and models
Seed 42; 80/20 split stratified on the event; the test set is used only for reported
metrics. Compared: Cox proportional hazards (ridge penalty chosen by 5-fold CV on the
training rows) and a Random Survival Forest (fixed, untuned: 100 trees, min leaf 40,
sized to keep the artifact small). Selection rule, fixed before the first run: higher
held-out C-index, but Cox is kept unless the forest is better by ≥ 0.01 (interpretability).
Note the forest configuration was shrunk once after a first run (300 trees, min leaf 15,
a 520 MB artifact) to make the file committable; that changed which model was selected.

## Evaluation
Test and training concordance index, train-only 5-fold CV C-index (mean/std), time-dependent
AUC at 8 times (≈29–161 months) and integrated Brier score, for both candidates, in
`artifacts/survival/metrics.json`. A metric that cannot be computed is listed under
`metrics_not_computed`, not filled in.

## Use
```
pip install -r requirements-research.txt
python -m app.ml.survival.train --patient PATH/data_clinical_patient.txt --sample PATH/data_clinical_sample.txt
```
`predict.load_artifact().predict([{...METABRIC column names...}])` returns a relative
`risk_score` and 60/120-month survival probabilities (None beyond the follow-up covered).

## Limitations
- One random split of one historical, single-source cohort; no external or temporal validation.
- A test C-index around 0.67–0.69 is modest discrimination; calibration was not assessed.
- Treatment variables are recorded after diagnosis and confounded by indication; the model
  describes association with outcome, not the effect of any treatment.
- `CLAUDIN_SUBTYPE` needs expression profiling that OncoTwin patients may not have.
- Unrelated to the WDBC malignancy classifier; it does not replace it.


---

# METABRIC relapse-free-survival (RFS) model

**Research model — not clinically validated.** A second offline model on the same
pipeline; artifacts in `artifacts/survival_rfs/`. It is not connected to any API.

- **What it is:** relapse-free survival is a prognostic *outcome* endpoint. This is outcome
  modelling only. It is **not** treatment-response prediction: no treatment-response label
  exists in these files, none was created, and no causal treatment effect is estimated.
- **Not validated:** no clinical validation and no external validation have been performed.
- **Target:** time = `RFS_MONTHS`; event = `RFS_STATUS` `1:Recurred` -> True, `0:Not Recurred`
  -> False (right-censored). The cohort defines "Recurred" as loco-regional relapse, distant
  relapse or disease-specific death. 129 patients with no usable RFS status/time (including the
  21 coded `NA`) are excluded, not imputed.
- **Features, preprocessing, split, models, selection rule:** identical to the OS model above
  (same 15 features, same exclusions of `NPI`, `OS_*`, `RFS_*`, `VITAL_STATUS`, same train-only
  fitting, seed 42, 80/20 event-stratified split, Cox vs Random Survival Forest, Cox preferred
  unless the forest wins by >= 0.01 test C-index). The code is shared: `build_target(frame,
  endpoint="RFS")` and `train(..., endpoint="RFS")`.
- **Run:** `python -m app.ml.survival.train --endpoint RFS --patient ... --sample ...`;
  `predict.load_artifact(RFS_ARTIFACT_DIR)`.
- **Limitations:** as for OS. Additionally the Cox ridge penalty landed on the edge of the
  search grid (alpha = 100), so a stronger penalty was not explored; and because RFS includes
  disease-specific death, its events overlap with, but are not the same as, OS events.
