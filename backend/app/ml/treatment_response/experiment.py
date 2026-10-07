"""Repeated nested patient-grouped stratified CV for the GSE163882 pCR research model.

    python -m app.ml.treatment_response.experiment --expression E --series S [--repeats 5] [--n-jobs 6]

Models: A clinical-only (ridge logistic), B expression-only and C clinical+expression (Elastic-Net logistic).
Outer loop: StratifiedGroupKFold(5), repeated; inner loop (inside each outer training set): the same splitter for
every choice of gene count k, l1_ratio and C. Nothing from an outer validation fold is used for preprocessing,
gene screening or tuning. Writes artifacts/treatment_response/.
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from joblib import Parallel, delayed
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

from . import ARTIFACT_DIR, CLAIM, MODEL_NAME, SEED, STATUS, TARGET, TREATMENT_CONTEXT
from .data import CLINICAL_FEATURES, Cohort, load_cohort
from .pipeline import (
    CLIN_SCALE_GRID, CLINICAL_C_GRID, C_GRID, DETECTION_FRACTION, DETECTION_TPM, INNER_FOLDS, K_GRID, KIND_LABEL, KINDS, L1_GRID,
    choose_threshold, fit_model, inner_search,
)

OUTER_FOLDS = 5
N_BOOT = 1000
MIN_SUBGROUP = 40          # a subgroup needs >= 40 samples ...
MIN_CLASS = 10             # ... and >= 10 of each class, otherwise it is reported as underpowered
MIN_SITE_CLASS = 10


# ---------------------------------------------------------------- metrics

def fold_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, float]:
    pred = p >= threshold
    sens = float(pred[y == 1].mean())
    spec = float((~pred[y == 0]).mean())
    return {
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))),
        "sensitivity": sens,
        "specificity": spec,
        "balanced_accuracy": (sens + spec) / 2,
        "threshold": float(threshold),
    }


def summarise(values: list[float]) -> dict[str, float]:
    v = np.asarray(values, dtype=float)
    return {
        "mean": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0, "median": float(np.median(v)),
        "p2.5": float(np.percentile(v, 2.5)), "p97.5": float(np.percentile(v, 97.5)), "n_folds": int(len(v)),
    }


def calibration(y: np.ndarray, p: np.ndarray, bins: int = 5) -> dict[str, object]:
    """Calibration slope/intercept (logistic recalibration on logit(p)) and a quantile-binned reliability table."""
    q = np.clip(p, 1e-6, 1 - 1e-6)
    logit = np.log(q / (1 - q)).reshape(-1, 1)
    lr = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000).fit(logit, y)
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    which = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    table = [
        {"bin": int(b), "n": int((which == b).sum()), "mean_predicted": float(p[which == b].mean()), "observed_pcr_rate": float(y[which == b].mean())}
        for b in range(len(edges) - 1) if (which == b).any()
    ]
    return {"slope": float(lr.coef_[0][0]), "intercept": float(lr.intercept_[0]), "reliability": table}


def group_bootstrap(groups: np.ndarray, rng: np.random.Generator, n: int) -> list[np.ndarray]:
    """Index sets from resampling whole patient groups with replacement."""
    ids = np.unique(groups)
    members = [np.flatnonzero(groups == g) for g in ids]
    return [np.concatenate([members[i] for i in rng.integers(0, len(ids), len(ids))]) for _ in range(n)]


def _ci(values: list[float]) -> list[float] | None:
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))] if len(values) >= 50 else None


def boot_metrics(y: np.ndarray, probs: dict[str, np.ndarray], boots: list[np.ndarray], subset: np.ndarray | None = None) -> dict[str, object]:
    """Patient-group bootstrap CI of AUC / PR-AUC per model and paired differences. Test-set sampling noise only."""
    auc: dict[str, list[float]] = {k: [] for k in probs}
    ap: dict[str, list[float]] = {k: [] for k in probs}
    for b in boots:
        if subset is not None:
            b = b[subset[b]]
        if len(b) == 0 or len(np.unique(y[b])) < 2:
            continue
        for k, p in probs.items():
            auc[k].append(roc_auc_score(y[b], p[b]))
            ap[k].append(average_precision_score(y[b], p[b]))
    out: dict[str, object] = {"n_resamples": len(next(iter(auc.values())))}
    for k in probs:
        out[k] = {"roc_auc_ci95": _ci(auc[k]), "pr_auc_ci95": _ci(ap[k])}
    diffs = {}
    for a, b in (("combined", "clinical"), ("combined", "expression"), ("expression", "clinical")):
        if a in probs and b in probs:
            da = np.array(auc[a]) - np.array(auc[b])
            dp = np.array(ap[a]) - np.array(ap[b])
            diffs[f"{a}_minus_{b}"] = {"roc_auc_ci95": _ci(list(da)), "pr_auc_ci95": _ci(list(dp)), "roc_auc_boot_mean": float(da.mean())}
    out["paired_differences"] = diffs
    return out


# ------------------------------------------------------------------ tasks

def _nonzero_ids(model) -> list[str]:
    coef = model.coefficients()
    ids = model.feature_names
    return [ids[i] for i in np.flatnonzero(np.abs(coef) > 1e-12) if ids[i] not in CLINICAL_FEATURES]


def _run_kinds(cohort_tr: dict, test: dict | None, seed: int, kinds=KINDS) -> dict[str, dict]:
    """Inner search + final fit on the training rows for every model; predict `test` if given."""
    out = {}
    for kind in kinds:
        s = inner_search(kind, cohort_tr["clinical"], cohort_tr["tpm"], cohort_tr["y"], cohort_tr["groups"], cohort_tr["ids"], seed)
        thr = choose_threshold(cohort_tr["y"], s["oof"])
        model = fit_model(kind, cohort_tr["clinical"], cohort_tr["tpm"], cohort_tr["y"], cohort_tr["ids"], s["config"], seed)
        rec = {"config": s["config"], "cv_log_loss": s["cv_log_loss"], "threshold": thr, "model": model}
        if test is not None:
            rec["proba"] = model.predict_proba(test["clinical"], test["tpm"])
            rec["selected"] = model.expression.selected_ids(int(s["config"]["k"])) if model.expression else []
            rec["nonzero"] = _nonzero_ids(model) if model.expression else []
        out[kind] = rec
    return out


def _subset(c: Cohort, idx: np.ndarray) -> dict:
    return {"clinical": c.clinical.iloc[idx].reset_index(drop=True), "tpm": c.tpm[idx], "y": c.y[idx], "groups": c.groups[idx], "ids": c.ensembl_ids}


def outer_task(c: Cohort, tr: np.ndarray, te: np.ndarray, r: int, f: int) -> dict:
    res = _run_kinds(_subset(c, tr), _subset(c, te), SEED + 100 * r + f)
    return {"repeat": r, "fold": f, "test": te, "kinds": {k: {x: v for x, v in rec.items() if x != "model"} for k, rec in res.items()}}


def site_task(c: Cohort, site: str) -> dict:
    te = np.flatnonzero(c.site == site)
    tr = np.flatnonzero(c.site != site)
    res = _run_kinds(_subset(c, tr), _subset(c, te), SEED + 7)
    y = c.y[te]
    out: dict[str, object] = {"site": site, "n_test": int(len(te)), "pcr_test": int(y.sum()), "rd_test": int((1 - y).sum()), "models": {}}
    if y.sum() < MIN_SITE_CLASS or (1 - y).sum() < MIN_SITE_CLASS:
        out["status"] = "underpowered: fewer than 10 samples in a class; point estimates are unstable"
    else:
        out["status"] = "ok"
    for k, rec in res.items():
        out["models"][k] = {**fold_metrics(y, rec["proba"], rec["threshold"]), "config": rec["config"]}
    return out


# ------------------------------------------------------------ aggregation

def subgroup_masks(c: Cohort) -> dict[str, np.ndarray]:
    er, pr, her2 = (c.clinical[x].to_numpy() for x in ("er", "pr", "her2"))
    tn = (er == 0) & (pr == 0) & (her2 == 0)
    return {"ER+": er == 1, "ER-": er == 0, "HER2+": her2 == 1, "HER2-": her2 == 0, "TNBC": tn, "non-TNBC": ~tn}


def aggregate(c: Cohort, results: list[dict], repeats: int, rng: np.random.Generator) -> dict[str, object]:
    n = len(c.y)
    per_fold = {k: [] for k in KINDS}
    pooled = {k: np.zeros((repeats, n)) for k in KINDS}
    cfg = {k: [] for k in KINDS}
    sel = {k: Counter() for k in ("expression", "combined")}
    nz = {k: Counter() for k in ("expression", "combined")}
    for res in results:
        te = res["test"]
        for k in KINDS:
            rec = res["kinds"][k]
            per_fold[k].append({"repeat": res["repeat"], "fold": res["fold"], **fold_metrics(c.y[te], rec["proba"], rec["threshold"]), "config": rec["config"]})
            pooled[k][res["repeat"], te] = rec["proba"]
            cfg[k].append(rec["config"])
            if k in sel:
                sel[k].update(rec["selected"])
                nz[k].update(rec["nonzero"])
    avg = {k: pooled[k].mean(axis=0) for k in KINDS}
    boots = group_bootstrap(c.groups, rng, N_BOOT)
    ci = boot_metrics(c.y, avg, boots)
    n_folds = len(results)
    annotation = dict(zip(c.ensembl_ids, c.annotation))
    models: dict[str, object] = {}
    for k in KINDS:
        metrics = {m: summarise([f[m] for f in per_fold[k]]) for m in ("roc_auc", "pr_auc", "brier", "log_loss", "sensitivity", "specificity", "balanced_accuracy")}
        rep_cal = [calibration(c.y, pooled[k][r]) for r in range(repeats)]
        full = {m: float(v) for m, v in zip(("roc_auc", "pr_auc", "brier"), (roc_auc_score(c.y, avg[k]), average_precision_score(c.y, avg[k]), brier_score_loss(c.y, avg[k])))}
        models[k] = {
            "label": KIND_LABEL[k],
            "fold_metrics": metrics,
            "repeat_averaged_oof": {**full, **ci[k]},
            "calibration": {
                "slope_per_repeat": summarise([x["slope"] for x in rep_cal]),
                "intercept_per_repeat": summarise([x["intercept"] for x in rep_cal]),
                "reliability_repeat_averaged": calibration(c.y, avg[k])["reliability"],
            },
            "selected_config_frequency": {
                "k": dict(Counter(int(x["k"]) for x in cfg[k])),
                "l1_ratio": dict(Counter(float(x["l1_ratio"]) for x in cfg[k])),
                "C": dict(Counter(float(x["C"]) for x in cfg[k])),
                "clin_scale": dict(Counter(float(x["clin_scale"]) for x in cfg[k])),
            },
        }
        if k in sel:
            models[k]["gene_selection"] = {
                "outer_folds": n_folds,
                "most_often_nonzero_coefficient": [
                    {"ensembl_id": g, "annotation": annotation.get(g, ""), "nonzero_in_folds": cnt, "in_screened_top_k_in_folds": sel[k][g]}
                    for g, cnt in nz[k].most_common(25)
                ],
                "most_often_screened": [{"ensembl_id": g, "annotation": annotation.get(g, ""), "in_folds": cnt} for g, cnt in sel[k].most_common(25)],
                "median_nonzero_genes_per_fold": float(np.median([len(r["kinds"][k]["nonzero"]) for r in results])),
            }
    # subgroups: repeat-averaged out-of-fold predictions
    sub: dict[str, object] = {}
    for name, mask in subgroup_masks(c).items():
        yy = c.y[mask]
        entry: dict[str, object] = {"n": int(mask.sum()), "pcr": int(yy.sum()), "rd": int((1 - yy).sum())}
        if mask.sum() < MIN_SUBGROUP or yy.sum() < MIN_CLASS or (1 - yy).sum() < MIN_CLASS:
            entry["status"] = "underpowered: not reported"
        else:
            entry["status"] = "ok"
            bs = boot_metrics(c.y, avg, boots, subset=mask)
            for k in KINDS:
                entry[k] = {
                    "roc_auc": float(roc_auc_score(yy, avg[k][mask])), "pr_auc": float(average_precision_score(yy, avg[k][mask])),
                    "brier": float(brier_score_loss(yy, avg[k][mask])), **bs[k],
                }
            entry["paired_differences"] = bs["paired_differences"]
        sub[name] = entry
    return {
        "models": models,
        "primary_comparison": {
            "question": "Does pretreatment gene expression improve pCR prediction beyond baseline clinical variables?",
            "paired_differences_repeat_averaged_oof": ci["paired_differences"],
            "n_bootstrap_resamples": ci["n_resamples"],
            "note": "Intervals resample patient groups of the repeat-averaged out-of-fold predictions: test-sampling noise only; "
                    "they ignore training variability and the dependence between repeated CV folds.",
        },
        "subgroups": {"basis": "repeat-averaged out-of-fold predictions from the primary nested CV", "groups": sub},
        "fold_records": {k: per_fold[k] for k in KINDS},
    }


# --------------------------------------------------------------- artifact

def _final_models(c: Cohort) -> dict[str, dict]:
    """Final fit on ALL labelled samples (hyper-parameters again chosen by grouped inner CV). Not used for evaluation."""
    res = _run_kinds({"clinical": c.clinical, "tpm": c.tpm, "y": c.y, "groups": c.groups, "ids": c.ensembl_ids}, None, SEED)
    for rec in res.values():
        m = rec["model"]
        if m.expression is not None:
            m.expression = m.expression.restrict(int(rec["config"]["k"]))   # keep only the selected genes in the artifact
    return res


def save_artifact(c: Cohort, final: dict, metrics: dict, meta_extra: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    annotation = dict(zip(c.ensembl_ids, c.annotation))
    models = {k: rec["model"] for k, rec in final.items()}
    names = {
        k: {
            "clinical_features": list(CLINICAL_FEATURES) if m.clinical else [],
            "genes": [{"ensembl_id": g, "annotation": annotation.get(g, ""), "coefficient": float(m.coefficients()[len(CLINICAL_FEATURES) * bool(m.clinical) + i])}
                      for i, g in enumerate(m.expression.all_ids)] if m.expression else [],
        }
        for k, m in models.items()
    }
    cfgC = final["combined"]["config"]
    cfgB = final["expression"]["config"]
    meta = {
        "model_name": MODEL_NAME, "status": STATUS, "target": TARGET, "treatment_context": TREATMENT_CONTEXT, "claim": CLAIM,
        "dataset": "GEO GSE163882 (AmpliSeq transcriptome, FFPE pretreatment breast biopsies; TPM)",
        "patient_count": c.provenance["patients"], "sample_count": c.provenance["samples"],
        "pcr_count": c.provenance["pcr"], "rd_count": c.provenance["rd"],
        "pcr_patients": c.provenance["pcr_patients"], "rd_patients": c.provenance["rd_patients"],
        "grouping_strategy": "specimen label (text after 'BA#####:' in the GEO sample title); samples with the same label or sharing an "
                             "accession token are one patient group (union-find). Patient identity is NOT proven; all samples of a group stay "
                             "in the same outer and inner fold.",
        "preprocessing": ["log2(TPM + 1)", f"detection filter fitted on training rows: TPM > {DETECTION_TPM:g} in >= {DETECTION_FRACTION:.0%} of samples",
                          "standardise with training mean/sd", "Welch t-test pCR vs RD on training rows, top-k genes",
                          "clinical: median/mode imputation and standardisation of age/grade/stage from training rows"],
        "detection_threshold": f"TPM > {DETECTION_TPM:g} in >= {DETECTION_FRACTION:.0%} of training samples",
        "gene_key": "Ensembl ID (annotation column is display-only)",
        "clinical_features": CLINICAL_FEATURES,
        "primary_model": "combined",
        "model_kinds": {k: KIND_LABEL[k] for k in KINDS},
        "final_model_hyperparameters": {k: final[k]["config"] for k in KINDS},
        "selected_gene_count": int(cfgC["k"]),
        "selected_gene_count_expression_only": int(cfgB["k"]),
        "l1_ratio": cfgC["l1_ratio"], "clinical_scale": cfgC["clin_scale"], "regularization": {"C": cfgC["C"], "type": "inverse strength, sklearn LogisticRegression (elastic-net)"},
        "decision_thresholds": {k: final[k]["threshold"] for k in KINDS},
        "random_seed": SEED,
        "cv_configuration": {
            "outer": f"StratifiedGroupKFold({OUTER_FOLDS}, shuffle=True, random_state=SEED+repeat), repeated",
            "inner": f"StratifiedGroupKFold({INNER_FOLDS}) inside each outer training set for k, l1_ratio, C (pooled out-of-fold log-loss)",
            "clinical_only_C_grid": list(CLINICAL_C_GRID), "k_grid": list(K_GRID), "clinical_scale_grid_combined_model": list(CLIN_SCALE_GRID), "l1_ratio_grid": list(L1_GRID), "C_grid": list(C_GRID), **meta_extra.pop("cv", {}),
        },
        "evaluation_note": "Final artifact is fitted on all labelled samples; performance claims come only from metrics.json (nested CV).",
        "external_validation": "none",
        "limitations": ["single small cohort, no external validation", "probable repeated patients (grouped, identity unproven)",
                        "regimen details unavailable", "pCR definition not independently verified from the metadata", "site/subtype confounding",
                        "research only"],
        "library_versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "numpy": np.__version__},
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **meta_extra,
    }
    joblib.dump({"models": models, "primary": "combined", "metadata": meta}, out_dir / "model.joblib", compress=3)
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "feature_names.json").write_text(json.dumps(names, indent=2, ensure_ascii=False), encoding="utf-8")


# -------------------------------------------------------------------- run

def outer_splits(y: np.ndarray, groups: np.ndarray, repeats: int):
    """Yield (train, validation, repeat, fold) for repeated stratified patient-grouped CV; asserts no group is shared."""
    for r in range(repeats):
        splitter = StratifiedGroupKFold(n_splits=OUTER_FOLDS, shuffle=True, random_state=SEED + r)
        for f, (tr, te) in enumerate(splitter.split(np.zeros(len(y)), y, groups)):
            if set(groups[tr]) & set(groups[te]):
                raise AssertionError("patient group present in both outer train and validation fold")
            yield tr, te, r, f


def run(c: Cohort, repeats: int = 5, n_jobs: int = 6, out_dir: Path | None = ARTIFACT_DIR, log=print) -> dict[str, object]:
    t0 = time.time()
    tasks = list(outer_splits(c.y, c.groups, repeats))
    pcr_rate = [float(c.y[te].mean()) for _, te, _, _ in tasks]
    log(f"{len(tasks)} outer folds; validation pCR rate {min(pcr_rate):.3f}-{max(pcr_rate):.3f}")
    results = Parallel(n_jobs=n_jobs, verbose=5)(delayed(outer_task)(c, tr, te, r, f) for tr, te, r, f in tasks)
    log(f"nested CV done in {time.time() - t0:.0f}s")
    metrics = aggregate(c, results, repeats, np.random.default_rng(SEED))
    sites = sorted(set(c.site))
    loso = Parallel(n_jobs=min(n_jobs, len(sites)))(delayed(site_task)(c, s) for s in sites)
    site_table = {s: {"samples": int((c.site == s).sum()), "pcr_rate": float(c.y[c.site == s].mean()), "tnbc_share": float(subgroup_masks(c)["TNBC"][c.site == s].mean())} for s in sites}
    metrics["site_sensitivity"] = {
        "design": "leave-one-site-group-out: train (with inner CV tuning) on two site groups, test on the third. Site groups come "
                  "from the GEO source field; this is NOT external validation (same cohort, same assay and pipeline).",
        "site_composition": site_table, "folds": loso,
    }
    metrics["cohort"] = c.provenance
    metrics["cv"] = {"outer_folds": OUTER_FOLDS, "repeats": repeats, "inner_folds": INNER_FOLDS, "bootstrap_resamples": N_BOOT, "seed": SEED,
                     "validation_pcr_rate_range": [min(pcr_rate), max(pcr_rate)], "group_leak_check": "passed (no group in both train and validation of any outer fold)"}
    metrics["statement"] = {"status": STATUS, "claim": CLAIM}
    final = _final_models(c)
    if out_dir is not None:
        save_artifact(c, final, metrics, {"cv": {"outer_repeats": repeats}, "cohort_provenance": c.provenance}, out_dir)
    log(f"total {time.time() - t0:.0f}s")
    return metrics


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--expression", required=True)
    ap.add_argument("--series", required=True)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--n-jobs", type=int, default=6)
    ap.add_argument("--out", default=str(ARTIFACT_DIR))
    a = ap.parse_args()
    cohort = load_cohort(a.expression, a.series)
    print(json.dumps(cohort.provenance, indent=2))
    run(cohort, a.repeats, a.n_jobs, Path(a.out))


if __name__ == "__main__":
    main()
