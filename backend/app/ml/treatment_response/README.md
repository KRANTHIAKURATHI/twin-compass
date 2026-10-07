# GSE163882 neoadjuvant chemotherapy pCR prediction model

**Research model — not clinically validated.** Offline experiment; not connected to any API, UI, Digital Twin or simulation.

> This model predicts pCR in the GSE163882 neoadjuvant taxane-based chemotherapy cohort. It does not estimate causal treatment effects and should not be interpreted as a clinical treatment recommendation.

It is **not** a general treatment-response model, and it does not replace or touch the WDBC, METABRIC OS or METABRIC RFS models.

## Question

Does pretreatment gene expression improve pCR prediction beyond baseline clinical variables?

## Data (kept outside the repository)

* GEO **GSE163882**: pretreatment FFPE breast-cancer biopsies, AmpliSeq Illumina Transcriptome panel, STAR+RSEM on hg38, **TPM**.
* `GSE163882_all.data.tpms_222Samples.csv.gz` (60,279 Ensembl genes x 222 samples, no missing values, no negative values) and the GEO
  series matrix (sample metadata). Both are only read; neither is copied into the repo. The **Ensembl ID is the gene key**; the
  `annotation` column (not unique) is used only for display.
* Samples are joined to metadata by sample ID (`BA#####`), never by position.

## Cohort and target

* 222 samples, ~213 patient groups. **Target: pCR = 1 (80 samples / 76 groups), RD = 0 (142 samples / 137 groups)**, taken only from the
  GEO field `response to nac`. Nothing is derived from survival, recurrence or any other field; a sample without an explicit pCR/RD
  label would be dropped, not inferred (none are).
* Treatment context: **neoadjuvant taxane-based chemotherapy** (the only treatment field). Anthracycline, anti-HER2 and carboplatin use are not recorded.
* Clinical features: age, ER, PR, HER2, grade, stage (ER/PR/HER2 P=1, N=0; grade 0 is an invalid value and treated as missing; stage has 14 missing).

## Patient grouping

Patient identity cannot be proven from GEO. Rule (`assign_patient_groups`, deterministic, row-order independent): the specimen label
(text after `BA#####:` in the sample title) identifies a specimen; samples with the same label, or sharing an accession token in a
multi-accession label (`S16-3384/S16-8771`), form one group (union-find). This gives 9 groups of two samples (all UConn, concordant
response, same ER/PR/HER2/age) — probable repeated patients. Grouping is conservative: replicate pairs always stay together in every
outer and inner fold (asserted on every split).

## Model

| | |
|---|---|
| A clinical-only | ridge logistic regression, C tuned |
| B expression-only | Elastic-Net logistic regression on the top-k screened genes |
| C clinical + expression | Elastic-Net logistic regression on clinical features + top-k genes; clinical columns are multiplied by a tuned scale {1, 5, 25}, i.e. their penalty is lowered, because a single shared penalty shrinks the few informative clinical variables |

Not used: Random Forest (not run — the primary models are linear), XGBoost (n too small), the published 18-/15-gene signatures
(derived on this same cohort; using them would leak).

## Preprocessing and feature selection (every step fitted on training rows only)

1. log2(TPM + 1).
2. Detection filter: TPM > 1 in >= 20% of the **training** samples.
3. Standardise with training mean/sd. No variance filter.
4. Univariate Welch t-test, pCR vs RD, on training rows; top-k genes, k in {50, 100, 200, 500}.
5. Elastic-Net logistic regression (saga), l1_ratio in {0.2, 0.5, 0.8, 1.0}, C in {0.001 … 1}.
6. Clinical: median (age, grade, stage) / mode (ER, PR, HER2) imputation and standardisation from training rows; grade and stage are
   ordinal scores. No missing-stage indicator (it could proxy the site).

k, l1_ratio, C (and the clinical scale for C) are chosen by inner 4-fold stratified patient-grouped CV on the outer training set
(pooled out-of-fold log-loss; ties go to the smaller k, l1_ratio, C). The decision threshold used for sensitivity/specificity is the one
maximising balanced accuracy on those inner out-of-fold predictions. Gene screening is redone inside every inner fold. Tests scramble
held-out expression and labels and check that nothing learned changes.

## Validation

* **Outer: 5-fold StratifiedGroupKFold x 5 repeats = 25 validation folds** (seeds 42 + repeat); validation pCR rate 35.6–36.4% in every fold.
* Inner: the same splitter, 4 folds, for all tuning.
* No 80/20 split is used. Metrics per fold: ROC-AUC, PR-AUC, Brier, log-loss, sensitivity, specificity, balanced accuracy; calibration
  slope/intercept per repeat and a reliability table.
* Confidence intervals: bootstrap over **patient groups** of the repeat-averaged out-of-fold predictions (1,000 resamples; also for paired
  differences between models). They capture test-sampling noise only, not training variability or the dependence between CV folds,
  so they are optimistic. Fold mean/SD/median/percentile range is also stored.
* Subgroups (ER, HER2, TNBC) are evaluated on the same out-of-fold predictions; a subgroup needs >= 40 samples and >= 10 per class,
  otherwise it is reported as underpowered.
* Leave-one-site-group-out (MT group, Hartford, UConn): train with inner tuning on two groups, test on the third.
  This is **not external validation** — same cohort, assay and pipeline.
* All 222 samples are evaluated, so the 9 replicate pairs are counted twice in the metrics (they are never split across folds).

## Results (`artifacts/treatment_response/metrics.json`)

Mean over 25 outer validation folds (SD in brackets); repeat-averaged out-of-fold AUC with bootstrap 95% CI.

| | ROC-AUC (fold mean, SD) | PR-AUC | Brier | Bal. acc. | pooled AUC [95% CI] |
|---|---|---|---|---|---|
| A clinical-only | 0.721 (0.067) | 0.596 | 0.200 | 0.655 | 0.724 [0.656, 0.790] |
| B expression-only | 0.686 (0.070) | 0.578 | 0.212 | 0.624 | 0.692 [0.618, 0.764] |
| C clinical + expression | 0.744 (0.058) | 0.624 | 0.197 | 0.682 | 0.747 [0.683, 0.809] |

Baseline for PR-AUC and Brier: pCR prevalence 36.0% (Brier of a constant prediction ≈ 0.230).
Paired AUC differences (95% CI): **C − A +0.023 [−0.015, +0.062]**, C − B +0.056 [+0.004, +0.108], B − A −0.033 [−0.113, +0.049].

**Conclusion:** adding expression to the clinical variables gave a small AUC gain whose interval includes zero, so this study does not
show that expression improves pCR prediction beyond clinical variables. Expression alone is about as good as clinical variables
within noise and worse in point estimate. Calibration slopes are below 1 (A 0.89, B 0.74, C 0.76), i.e. predictions are somewhat
over-confident. Subgroup and site results are in `metrics.json`; they are exploratory (intervals wide; Hartford has 9 pCR samples
and is flagged underpowered).

### Tuning-grid history (disclosed)

A first complete run chose the largest clinical C (1.0) in 17/25 folds and the largest clinical scale (5) in 25/25 folds, i.e. the
optimum sat on the grid edge. The clinical-only C grid was widened (to 100) and the scale grid extended (to 25) and the whole
experiment re-run; only that second run is saved. The two runs agreed to about 0.003 AUC for every model. The grids were changed after
seeing validation-fold results, a small analyst degree of freedom.

## Artifact

`model.joblib` (all three models, preprocessing fitted on all labelled samples; hyper-parameters from grouped inner CV), `metadata.json`,
`metrics.json`, `feature_names.json`. The artifact is a fit to the full cohort; performance claims come only from the nested CV in
`metrics.json`. `predict.py` loads it and returns P(pCR) from clinical fields and Ensembl-ID TPM values.

```
python -m app.ml.treatment_response.experiment --expression E.csv.gz --series series_matrix.txt.gz [--repeats 5] [--n-jobs 6]
```

(about 15 minutes on 7 CPU workers).

## Limitations

* **No external validation**; one small cohort (~213 patient groups, 76 pCR), wide uncertainty.
* **Probable repeated patients**: identity is inferred from specimen labels and cannot be proven.
* **Regimen details unavailable**: anthracycline, anti-HER2 therapy and carboplatin are unrecorded; 63 patients are HER2-positive.
* **pCR definition not independently verified** from the GEO metadata.
* **Site/subtype confounding**: TNBC is concentrated in the MT group (54% of its samples vs 5% in UConn), so site/batch can resemble subtype.
* AmpliSeq panel TPM values are relative within the panel; FFPE quality is unrecorded.
* Gene lists are association-based screens; selected genes are not evidence of mechanism. Selection frequencies are reported in `metrics.json`.
* Predictions are not causal treatment effects and not a recommendation. Research-only status.
