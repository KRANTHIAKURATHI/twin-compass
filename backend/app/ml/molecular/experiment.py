"""
METABRIC molecular survival experiment: clinical-only vs expression-only vs clinical + expression.

    python -m app.ml.molecular.experiment --patient P --sample S --expression E [--endpoint OS|RFS]

Offline research only. For each endpoint, one seeded event-stratified 80/20 split is shared
by every model. All expression preprocessing, gene screening and hyper-parameter choice
happens inside the training rows (and inside each training CV fold); the held-out rows are
used once, for the reported metrics.

Models
  A   clinical-only Cox (ridge, alpha by train-only CV)   - the existing survival-model recipe
  A2  clinical-only Elastic-Net Cox                        - control: same estimator as C
  B   selected expression -> Elastic-Net Cox
  C   clinical + selected expression -> Elastic-Net Cox    (clinical penalty factor 0)

Research model - not clinically validated. Prognostic only; not treatment-response prediction.
"""
from __future__ import annotations

import argparse
import json
import platform
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
import sksurv
from sklearn.model_selection import KFold, train_test_split
from sksurv.linear_model import CoxnetSurvivalAnalysis

from app.ml.survival.data import CATEGORICAL_FEATURES, NUMERIC_FEATURES, file_sha256, load_clinical
from app.ml.survival.evaluate import brier, c_index, evaluation_times, make_y, safe, time_dependent_auc
from app.ml.survival.preprocess import build_preprocessor
from app.ml.survival.train import _cv_stability, _fit_cox

from . import ARTIFACT_DIR, EXPRESSION_SOURCE, RESEARCH_STATEMENT
from .expression import build_cohort, read_expression
from .screening import WINSOR_PCT, fit_screen

DEFAULT_CONFIG: dict[str, object] = {
    "seed": 42,
    "test_size": 0.2,
    "cv_folds": 5,
    "cox_alpha_grid": [0.01, 0.1, 1.0, 10.0, 100.0],      # model A, as in the existing models
    "screen_sizes": [500, 1000, 2000, 5000],
    "l1_ratios": [0.5, 0.7, 0.9, 1.0],
    "n_alphas": 30,
    "alpha_min_ratio": 0.01,
    "clinical_penalty_factor": 0.0,   # clinical terms unpenalised in model C; expression terms factor 1
    "bootstrap_resamples": 1000,
}
MODEL_LABELS = {"A": "clinical-only Cox (ridge)", "A2": "clinical-only Elastic-Net Cox",
                "B": "expression-only Elastic-Net Cox", "C": "clinical + expression Elastic-Net Cox"}
METHODOLOGY = (
    "Per training set / CV fold: median-impute, winsorise (train percentiles "
    f"{WINSOR_PCT[0]:g}/{WINSOR_PCT[1]:g}) and standardise every gene with training statistics only; rank genes by "
    "|univariate Cox score z| on the training rows only; keep the top-k; fit Elastic-Net Cox along an alpha path. "
    "k, l1_ratio and alpha are chosen by train-only CV (screening repeated inside every fold). "
    "No variance filter (z-score genes have ~equal variance). Test rows are used only for the final metrics."
)


class _AlphaView:
    """A fitted Coxnet pinned to one alpha so the shared metric helpers can call it."""

    def __init__(self, model: CoxnetSurvivalAnalysis, alpha: float):
        self.model, self.alpha = model, alpha

    def predict(self, X):
        return self.model.predict(X, alpha=self.alpha)

    def predict_survival_function(self, X):
        return self.model.predict_survival_function(X, alpha=self.alpha)


def _clinical(pre, raw, names=None):
    """Processed clinical matrix. A CV-fold encoder can lack a rare category level that the full training
    set has; `names` (the full-training column names) keeps every matrix column-aligned (absent level = 0)."""
    frame = pre.transform(raw)
    if names is not None:
        frame = frame.reindex(columns=names, fill_value=0.0)
    return frame.to_numpy(dtype=float)


def _matrix(pre, genes, raw, expr, names=None):
    """Columns: [clinical..., selected genes in rank order]; a top-k model uses the first n_clin + k columns."""
    parts = []
    if pre is not None:
        parts.append(_clinical(pre, raw, names))
    if genes is not None:
        parts.append(genes.transform(expr))
    return np.hstack(parts)


def _penalty(n_clin: int, k: int, cfg: dict, use_expr: bool) -> np.ndarray:
    clin = cfg["clinical_penalty_factor"] if use_expr else 1.0
    return np.r_[np.full(n_clin, clin), np.ones(k)]


def _coxnet(cfg, l1, pf, **kw):
    return CoxnetSurvivalAnalysis(l1_ratio=l1, penalty_factor=pf, max_iter=100000, **kw)


def search_coxnet(clin_raw, expr, event, time, cfg, use_clin: bool, use_expr: bool) -> dict:
    """Choose (screen size k, l1_ratio, alpha) by train-only CV, then refit on all training rows.

    Within every fold the clinical preprocessor and the expression screen are re-fitted on that
    fold's training part, so nothing from the validation part - let alone the test set - is used.
    """
    ks = list(cfg["screen_sizes"]) if use_expr else [0]
    k_max = max(ks)
    ids = cfg["entrez_ids"]
    y = make_y(event, time)

    def prep(raw, e, ev, t):
        pre = build_preprocessor().fit(raw) if use_clin else None
        screen = fit_screen(e, ev, t, ids) if use_expr else None
        return pre, screen

    pre, screen = prep(clin_raw, expr, event, time)
    names = list(pre.get_feature_names_out()) if use_clin else None
    M = _matrix(pre, screen.top(k_max) if use_expr else None, clin_raw, expr)
    n_clin = M.shape[1] - (k_max if use_expr else 0)

    folds = []
    for tr, va in KFold(cfg["cv_folds"], shuffle=True, random_state=cfg["seed"]).split(M):
        p, s = prep(clin_raw.iloc[tr], expr[tr], event[tr], time[tr])
        g = s.top(k_max) if use_expr else None
        folds.append((_matrix(p, g, clin_raw.iloc[tr], expr[tr], names), _matrix(p, g, clin_raw.iloc[va], expr[va], names), y[tr], va))

    grid, failures, n_warn = [], [], 0
    best = None
    for k in ks:
        cols = n_clin + k
        pf = _penalty(n_clin, k, cfg, use_expr)
        for l1 in cfg["l1_ratios"]:
            scores = alphas = None
            for stretch in (1, 5, 25):  # Coxnet can fail at the weakly penalised end of the path: shorten it and retry
                ratio = min(cfg["alpha_min_ratio"] * stretch, 0.9)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    try:
                        alphas = _coxnet(cfg, l1, pf, n_alphas=cfg["n_alphas"], alpha_min_ratio=ratio).fit(M[:, :cols], y).alphas_
                        scores = np.empty((len(folds), len(alphas)))
                        for f, (Mtr, Mva, ytr, va) in enumerate(folds):
                            m = _coxnet(cfg, l1, pf, alphas=alphas).fit(Mtr[:, :cols], ytr)
                            for j, a in enumerate(alphas):
                                scores[f, j] = c_index(event[va], time[va], m.predict(Mva[:, :cols], alpha=a))
                        break
                    except (ArithmeticError, ValueError) as exc:  # Coxnet raises these on numerical failure
                        scores = None
                        failures.append({"screen_size": k, "l1_ratio": l1, "alpha_min_ratio": ratio,
                                         "error": f"{type(exc).__name__}: {exc}"})
            if scores is None:
                continue
            n_warn += len(caught)
            mean = scores.mean(axis=0)
            j = int(np.argmax(mean))
            grid.append({"screen_size": k, "l1_ratio": l1, "best_alpha": float(alphas[j]), "alpha_min_ratio": ratio, "best_at_path_end": bool(j == len(alphas) - 1),
                         "cv_c_index_mean": float(mean[j]), "cv_c_index_std": float(scores[:, j].std())})
            if best is None or mean[j] > best["cv_c_index_mean"]:  # ties keep the earlier (smaller k) config
                best = {"screen_size": k, "l1_ratio": l1, "alphas": alphas, "alpha_index": j, "at_path_end": bool(j == len(alphas) - 1), "cols": cols,
                        "cv_c_index_mean": float(mean[j]), "cv_c_index_std": float(scores[:, j].std())}
    if best is None:
        raise RuntimeError(f"no Elastic-Net configuration could be fitted: {failures}")

    k, l1, j = best["screen_size"], best["l1_ratio"], best["alpha_index"]
    pf = _penalty(n_clin, k, cfg, use_expr)
    final = _coxnet(cfg, l1, pf, alphas=best["alphas"][: j + 1], fit_baseline_model=True).fit(M[:, : best["cols"]], y)
    return {
        "view": _AlphaView(final, float(best["alphas"][j])), "model": final, "pre": pre,
        "screen_k": screen.top(k) if use_expr else None, "n_clin": n_clin, "k": k, "l1_ratio": l1,
        "alpha": float(best["alphas"][j]), "alpha_at_path_end": best["at_path_end"], "cv": {"mean": best["cv_c_index_mean"], "std": best["cv_c_index_std"]},
        "grid": grid, "failures": failures, "convergence_warnings": n_warn,
        "penalty_factor_clinical": float(pf[0]) if n_clin else None,
    }


def _coefficients(fit: dict, cohort_ids, hugo) -> dict:
    coef = fit["model"].coef_[:, -1]
    n_clin = fit["n_clin"]
    nz = np.flatnonzero(coef)
    names = {e: h for e, h in zip(cohort_ids, hugo)}
    genes = [{"entrez_id": fit["screen_k"].entrez_ids[i - n_clin], "hugo_symbol": names.get(fit["screen_k"].entrez_ids[i - n_clin]),
              "coefficient": float(coef[i])} for i in nz if i >= n_clin]
    genes.sort(key=lambda g: -abs(g["coefficient"]))
    return {"nonzero_total": int(len(nz)), "nonzero_clinical": int((nz < n_clin).sum()), "nonzero_expression": len(genes),
            "nonzero_expression_genes": genes}


def _score(risk_tr, risk_te, view, M_te, ev, tm, y_tr, y_te, times):
    auc, auc_err = safe(time_dependent_auc, y_tr, y_te, risk_te, times)
    ibs, ibs_err = safe(brier, view, M_te, y_tr, y_te, times) if view is not None else (None, "not computed")
    return {
        "train_c_index": c_index(ev["tr"], tm["tr"], risk_tr), "test_c_index": c_index(ev["te"], tm["te"], risk_te),
        "time_dependent_auc": auc, "integrated_brier_score": ibs,
        "metrics_not_computed": {k: v for k, v in (("time_dependent_auc", auc_err), ("integrated_brier_score", ibs_err)) if v},
    }


def bootstrap(event, time, risks: dict[str, np.ndarray], reference: list[str], n: int, seed: int) -> dict:
    """Percentile CIs for held-out C-index by resampling test patients (same resamples for every model).

    This captures test-set sampling noise only; the fitted models are fixed, so training
    variability is not included. Paired differences use the same resamples.
    """
    rng = np.random.default_rng(seed)
    draws = {k: [] for k in risks}
    for _ in range(n):
        idx = rng.integers(0, len(event), len(event))
        if event[idx].sum() == 0:
            continue
        for k, r in risks.items():
            draws[k].append(c_index(event[idx], time[idx], r[idx]))
    ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]  # noqa: E731
    out = {"n_resamples": len(draws[next(iter(draws))]),
           "test_c_index_ci95": {k: ci(v) for k, v in draws.items()}, "paired_difference_ci95": {}}
    for ref in reference:
        for k in risks:
            if k != ref and k in draws and ref in draws:
                d = np.asarray(draws[k]) - np.asarray(draws[ref])
                out["paired_difference_ci95"][f"{k} - {ref}"] = {"mean": float(d.mean()), "ci95": ci(d),
                                                                 "ci_excludes_zero": bool(ci(d)[0] > 0 or ci(d)[1] < 0)}
    return out


def run_endpoint(frame, expr, endpoint: str, cfg: dict, out_dir: Path | None) -> dict:
    cohort = build_cohort(frame, expr, endpoint)
    cfg = {**cfg, "entrez_ids": cohort.entrez_ids}
    ev, tm = cohort.event, cohort.time
    idx_tr, idx_te = train_test_split(np.arange(len(ev)), test_size=cfg["test_size"], random_state=cfg["seed"], stratify=ev)
    clin_tr, clin_te = cohort.clinical.iloc[idx_tr], cohort.clinical.iloc[idx_te]
    E_tr, E_te = cohort.expression[idx_tr], cohort.expression[idx_te]
    y_tr, y_te = make_y(ev[idx_tr], tm[idx_tr]), make_y(ev[idx_te], tm[idx_te])
    times = evaluation_times(y_te)
    evd, tmd = {"tr": ev[idx_tr], "te": ev[idx_te]}, {"tr": tm[idx_tr], "te": tm[idx_te]}
    n_expr = len(cohort.entrez_ids)

    results, risks, fits = {}, {}, {}

    # A: existing clinical recipe (ridge Cox) on this cohort
    pre_a = build_preprocessor().fit(clin_tr)
    Xa_tr, Xa_te = _clinical(pre_a, clin_tr), _clinical(pre_a, clin_te)
    cox, params = _fit_cox(Xa_tr, y_tr, cfg)
    risks["A"] = cox.predict(Xa_te)
    results["A"] = {**_score(cox.predict(Xa_tr), risks["A"], cox, Xa_te, evd, tmd, y_tr, y_te, times),
                    **_cv_stability(cox, clin_tr, y_tr, cfg), "hyperparameters": params,
                    "expression_features_considered": 0, "expression_features_selected": 0,
                    "n_coefficients": int(Xa_tr.shape[1]), "nonzero_coefficients": int((cox.coef_ != 0).sum())}

    for name, use_clin, use_expr in (("A2", True, False), ("B", False, True), ("C", True, True)):
        fit = search_coxnet(clin_tr, E_tr, ev[idx_tr], tm[idx_tr], cfg, use_clin, use_expr)
        fits[name] = fit
        M_tr = _matrix(fit["pre"], fit["screen_k"], clin_tr, E_tr)
        M_te = _matrix(fit["pre"], fit["screen_k"], clin_te, E_te)
        risks[name] = fit["view"].predict(M_te)
        coefs = _coefficients(fit, cohort.entrez_ids, cohort.hugo_symbols) if use_expr else {
            "nonzero_total": int((fit["model"].coef_[:, -1] != 0).sum()), "nonzero_clinical": int((fit["model"].coef_[:, -1] != 0).sum()),
            "nonzero_expression": 0, "nonzero_expression_genes": []}
        results[name] = {
            **_score(fit["view"].predict(M_tr), risks[name], fit["view"], M_te, evd, tmd, y_tr, y_te, times),
            "cv_c_index_mean": fit["cv"]["mean"], "cv_c_index_std": fit["cv"]["std"],
            "hyperparameters": {"screen_size": fit["k"] if use_expr else 0, "l1_ratio": fit["l1_ratio"], "alpha": fit["alpha"],
                                "clinical_penalty_factor": fit["penalty_factor_clinical"] if use_expr else 1.0,
                                "alpha_at_weak_end_of_path": fit["alpha_at_path_end"],
                                "selected_by": "train-only CV (screening repeated inside each fold)"},
            "cv_grid": fit["grid"], "cv_failed_configurations": fit["failures"], "convergence_warnings": fit["convergence_warnings"],
            "expression_features_considered": n_expr if use_expr else 0,
            "expression_features_selected": coefs["nonzero_expression"],
            "n_coefficients": int(M_tr.shape[1]), "nonzero_coefficients": coefs["nonzero_total"],
            "nonzero_clinical": coefs["nonzero_clinical"], "nonzero_expression_genes": coefs["nonzero_expression_genes"],
        }

    for r in results.values():
        r.update(n_patients_train=int(len(idx_tr)), n_patients_test=int(len(idx_te)), events_train=int(evd["tr"].sum()),
                 events_test=int(evd["te"].sum()), raw_clinical_features=len(NUMERIC_FEATURES + CATEGORICAL_FEATURES))
    ci = bootstrap(ev[idx_te], tm[idx_te], risks, ["A", "A2"], cfg["bootstrap_resamples"], cfg["seed"])
    for k in results:
        results[k]["test_c_index_ci95"] = ci["test_c_index_ci95"][k]

    split = {"endpoint": endpoint, "n_patients": int(len(ev)), "n_train": int(len(idx_tr)), "n_test": int(len(idx_te)),
             "events": int(ev.sum()), "events_train": int(evd["tr"].sum()), "events_test": int(evd["te"].sum()),
             "censoring_rate": float(1 - ev.mean()), "n_genes_available": n_expr, "p_over_n_train": n_expr / len(idx_tr),
             "evaluation_times_months": times.tolist()}
    report = {"endpoint": endpoint, "split": split, "models": results, "bootstrap": ci}
    if out_dir is not None:
        _save_artifact(out_dir / endpoint.lower(), endpoint, cfg, fits["C"], results["C"], split, report)
    return report


def _save_artifact(path: Path, endpoint: str, cfg: dict, fit: dict, result: dict, split: dict, report: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    metadata = {
        "model_name": f"METABRIC molecular survival experiment ({endpoint})",
        "status": RESEARCH_STATEMENT,
        "dataset": "METABRIC",
        "endpoint": endpoint,
        "model": "Elastic-Net Cox",
        "variant": "C: clinical + selected expression",
        "expression_source": EXPRESSION_SOURCE,
        "gene_identifier": "Entrez ID",
        "patient_count": split["n_patients"],
        "event_count": split["events"],
        "selected_gene_count": result["expression_features_selected"],
        "screened_gene_count": fit["k"],
        "l1_ratio": fit["l1_ratio"],
        "regularization": {"alpha": fit["alpha"], "n_alphas": cfg["n_alphas"], "alpha_min_ratio": cfg["alpha_min_ratio"],
                           "clinical_penalty_factor": fit["penalty_factor_clinical"], "expression_penalty_factor": 1.0},
        "screening": {"method": "univariate Cox score |z|, training rows only", "candidate_sizes": cfg["screen_sizes"],
                      "chosen_size": fit["k"], "winsorization_percentiles": list(WINSOR_PCT)},
        "random_seed": cfg["seed"],
        "feature_selection_methodology": METHODOLOGY,
        "split": split,
        "metrics": {k: result[k] for k in ("train_c_index", "test_c_index", "cv_c_index_mean", "cv_c_index_std",
                                           "time_dependent_auc", "integrated_brier_score", "test_c_index_ci95")},
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": platform.python_version(), "scikit-survival": sksurv.__version__, "scikit-learn": sklearn.__version__},
        "limitations": [
            "One METABRIC cohort; no external validation.", "Observational cohort; treatment flags are confounded by indication.",
            "High-dimensional molecular data; possible batch/cohort effects.",
            "Not treatment-response prediction. Not clinically validated.",
        ],
    }
    joblib.dump({"clinical_preprocessor": fit["pre"], "expression": fit["screen_k"], "model": fit["model"], "alpha": fit["alpha"],
                 "metadata": metadata}, path / "model.joblib", compress=3)
    (path / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (path / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def run(patient_path, sample_path, expression_path, out_dir=None, endpoints=("OS", "RFS"), config=None) -> dict:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    out_dir = Path(out_dir) if out_dir is not None else ARTIFACT_DIR
    frame = load_clinical(patient_path, sample_path)
    expr = read_expression(expression_path)
    reports = {ep: run_endpoint(frame, expr, ep, cfg, out_dir) for ep in endpoints}
    summary = {
        "status": RESEARCH_STATEMENT, "expression_source": EXPRESSION_SOURCE, "methodology": METHODOLOGY,
        "config": {k: v for k, v in cfg.items()}, "expression_provenance": expr.provenance,
        "files": {Path(p).name: {"sha256": file_sha256(p)} for p in (patient_path, sample_path, expression_path)},
        "endpoints": reports,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "experiment_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="METABRIC molecular survival research experiment.")
    p.add_argument("--patient", required=True)
    p.add_argument("--sample", required=True)
    p.add_argument("--expression", required=True)
    p.add_argument("--endpoint", choices=["OS", "RFS"], default=None, help="default: both")
    p.add_argument("--out", default=None)
    a = p.parse_args()
    run(a.patient, a.sample, a.expression, a.out, (a.endpoint,) if a.endpoint else ("OS", "RFS"))
    print("done")


if __name__ == "__main__":
    main()
