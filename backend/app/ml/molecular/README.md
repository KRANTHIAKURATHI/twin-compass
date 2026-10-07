# METABRIC molecular survival experiment

**Research model — not clinically validated.** Offline experiment, not connected to any API or UI. It is
**prognostic** modelling of overall survival (OS) and relapse-free survival (RFS). It is **not treatment-response
prediction**: it estimates nothing about the effect of any treatment.

## Question

Does adding tumour mRNA expression improve held-out prognostic performance beyond the clinical variables used by
the existing METABRIC OS/RFS models (`app/ml/survival/`)? Those models are unchanged; their artifacts are not touched.

## Data (kept outside the repository)

* `data_clinical_patient.txt`, `data_clinical_sample.txt` — loaded with the existing `app.ml.survival.data` loader.
* `data_mrna_illumina_microarray_zscores_ref_diploid_samples.txt` (~303 MB) — METABRIC Illumina microarray z-scores,
  streamed one row at a time (`expression.py`); never copied into the repo.
* 20,603 rows, 20,192 unique Entrez IDs, 1,980 samples (one per patient), 16 missing values.
* **Gene key = Entrez ID.** 411 rows repeat an Entrez ID. Rule: keep the **first row in file order**, drop the others;
  no averaging, and no data value is used, so the rule cannot leak. The count is stored in the provenance block.
* Cohorts: patients with a valid endpoint target (never imputed) **and** an expression sample — OS 1,980 patients
  (1,143 events), RFS 1,979 patients (803 events).

## Design

| | |
|---|---|
| Split | seed 42, 80/20, stratified on the event; the same split for every model of an endpoint |
| A | clinical-only Cox, ridge alpha by train-only CV — the existing recipe, recomputed on this cohort |
| A2 | clinical-only Elastic-Net Cox — control with the same estimator as C, so C vs A2 isolates expression |
| B | selected genes → Elastic-Net Cox |
| C | clinical (processed exactly as the existing models) + selected genes → Elastic-Net Cox |
| Penalties (C) | clinical terms **penalty factor 0** (unpenalised), expression terms factor 1 (`penalty_factor` in `CoxnetSurvivalAnalysis`) |
| Grid | screen size {500, 1000, 2000, 5000} × l1_ratio {0.5, 0.7, 0.9, 1.0} × 30-point alpha path (16 configurations) |

### Why molecular expression was added

Expression carries tumour biology (proliferation, hormone signalling, immune/stromal state) that the 15 clinical
fields only summarise coarsely.

### Why variance filtering was not used

The matrix is z-scored per gene, so every gene's variance is ≈ 1 (checked: all quantiles are 1.000). Variance
ranks nothing here. Genes are screened by association with survival instead.

### Why selection is nested inside training folds

Ranking genes with the outcome and then cross-validating on the same patients lets the validation fold influence which
genes exist, which inflates scores. Therefore, for the training set **and again inside every CV fold**, the pipeline
learns from those training rows only: median imputation, winsorisation (1st/99th percentile), standardisation, and the
|univariate Cox score z| ranking (`screening.py`, a vectorised log-rank-type statistic). Held-out rows are only
transformed. The clinical preprocessor is likewise re-fitted per fold. A test
(`test_selection_and_training_never_see_held_out_expression`) scrambles the held-out expression and asserts that every
training-derived quantity is unchanged.

### Why Elastic-Net Cox

With ~20k correlated genes and ~640–910 training events, an unpenalised Cox model is not estimable. L1 gives sparsity,
L2 stabilises correlated gene groups, and the path over alpha is cheap. The model stays a linear hazard model, so
coefficients can be read. PCA and signature scores were not run.

### Hyper-parameter choice

k, l1_ratio and alpha are chosen by 5-fold CV C-index on the training rows (ties go to the smaller k). The reported
"CV C-index" is the best configuration's CV score, so it is mildly optimistic by construction. If Coxnet failed at the
weakly penalised end of a path the path was shortened and retried; failures are recorded in `metrics.json`.

## Running

```
python -m app.ml.molecular.experiment --patient P --sample S --expression E [--endpoint OS|RFS]
```

Writes `artifacts/molecular_survival/{os,rfs}/` (model C artifact, `metadata.json`, `metrics.json` holding all four
models) and `experiment_report.json`. The run takes roughly 1.5 hours on a laptop CPU.

## Results

Test C-index, bootstrap 95% CI over test patients (1,000 resamples; test-set sampling noise only, training variability
is not included). Full numbers, CV scores, AUC, Brier scores, coefficients and genes: `metrics.json`.

| | OS | RFS |
|---|---|---|
| A clinical-only (ridge Cox) | 0.673 [0.637, 0.711] | 0.681 [0.639, 0.725] |
| A2 clinical-only (Elastic-Net) | 0.671 [0.635, 0.710] | 0.676 [0.632, 0.720] |
| B expression-only | 0.604 [0.563, 0.642] | 0.641 [0.595, 0.687] |
| C clinical + expression | 0.677 [0.642, 0.712] | 0.665 [0.621, 0.706] |
| C − A (paired, 95% CI) | +0.003 [−0.012, +0.019] | −0.017 [−0.049, +0.015] |

Adding expression did **not** produce a held-out improvement that is distinguishable from zero for either endpoint;
the OS difference is +0.003 and the RFS point estimate is negative. Expression alone is clearly worse than clinical
data for OS. Nothing here supports a claim of clinical benefit.

## Limitations

* One METABRIC cohort, one random split; no external validation.
* Observational data. Treatment flags are recorded after diagnosis and confounded by indication.
* High-dimensional molecular data (p/n ≈ 13 on the training set); selected genes are not stable evidence of biology.
* Possible batch/site effects across METABRIC contributing cohorts were not modelled.
* Elastic-Net coefficients are prognostic associations, not causal effects.
* Not treatment-response prediction. Not clinically validated.
