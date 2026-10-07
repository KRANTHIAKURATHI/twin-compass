"""
Train and evaluate the METABRIC overall-survival research models.

    python -m app.ml.survival.train --patient PATH/data_clinical_patient.txt --sample PATH/data_clinical_sample.txt

Compares Cox proportional hazards and a Random Survival Forest under one
protocol: a seeded, event-stratified train/test split; preprocessing and any
hyper-parameter choice (Cox penalty, by cross-validation) fitted on the
training rows only; the held-out test rows used only for the reported metrics.
Writes the selected model and a JSON report to app/ml/artifacts/survival/.

Research model - not clinically validated.
"""
from __future__ import annotations

import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
import sksurv
from sklearn.base import clone
from sklearn.model_selection import GridSearchCV, KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sksurv.ensemble import RandomSurvivalForest
from sksurv.linear_model import CoxPHSurvivalAnalysis

from . import MODEL_NAME, RESEARCH_STATEMENT, RFS_MODEL_NAME
from .data import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, build_target, file_sha256, load_clinical
from .evaluate import brier, c_index, evaluation_times, make_y, safe, time_dependent_auc
from .preprocess import build_preprocessor

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "survival"
RFS_ARTIFACT_DIR = ARTIFACT_DIR.parent / "survival_rfs"

# Per-endpoint naming; everything else (features, split, models, selection) is shared.
ENDPOINT_SPECS = {
    "OS": {
        "name": MODEL_NAME, "version": "metabric-os-v1", "dir": ARTIFACT_DIR,
        "target": {"time": "OS_MONTHS (months)", "event": "OS_STATUS: '1:DECEASED' -> True, '0:LIVING' -> False"},
    },
    "RFS": {
        "name": RFS_MODEL_NAME, "version": "metabric-rfs-v1", "dir": RFS_ARTIFACT_DIR,
        "target": {"time": "RFS_MONTHS (months)",
                   "event": "RFS_STATUS: '1:Recurred' -> True, '0:Not Recurred' -> False"},
    },
}
MODEL_VERSION = ENDPOINT_SPECS["OS"]["version"]

DEFAULT_CONFIG: dict[str, object] = {
    "seed": 42,
    "test_size": 0.2,
    "cv_folds": 5,
    "cox_alpha_grid": [0.01, 0.1, 1.0, 10.0, 100.0],
    # Sized so the saved artifact stays small: every forest leaf stores a full
    # survival curve, so trees x leaves dominates the file size.
    "rsf": {"n_estimators": 100, "min_samples_leaf": 40, "max_features": "sqrt"},
    # Cox is preferred over the forest unless the forest's held-out C-index is
    # higher by at least this much: it is the more interpretable model.
    "interpretability_margin": 0.01,
}


def _fit_cox(X_tr, y_tr, cfg):
    search = GridSearchCV(
        CoxPHSurvivalAnalysis(),
        {"alpha": cfg["cox_alpha_grid"]},
        cv=KFold(cfg["cv_folds"], shuffle=True, random_state=cfg["seed"]),
    ).fit(X_tr, y_tr)
    return search.best_estimator_, {"alpha": search.best_params_["alpha"], "selected_by": "train-only CV"}


def _fit_rsf(X_tr, y_tr, cfg):
    model = RandomSurvivalForest(**cfg["rsf"], n_jobs=-1, random_state=cfg["seed"]).fit(X_tr, y_tr)
    return model, {**cfg["rsf"], "selected_by": "fixed, not tuned"}


def _cv_stability(model, X_raw, y, cfg) -> dict[str, float]:
    """Train-only CV C-index with preprocessing re-fitted inside every fold."""
    pipe = Pipeline([("pre", build_preprocessor()), ("model", clone(model))])
    scores = cross_val_score(pipe, X_raw, y, cv=KFold(cfg["cv_folds"], shuffle=True, random_state=cfg["seed"]))
    return {"cv_c_index_mean": float(scores.mean()), "cv_c_index_std": float(scores.std())}


def select_model(metrics: dict[str, dict], margin: float) -> tuple[str, str]:
    cox, rsf = metrics["cox"]["test_c_index"], metrics["rsf"]["test_c_index"]
    if rsf - cox >= margin:
        return "rsf", f"RSF test C-index exceeds Cox by {rsf - cox:.4f} (>= {margin})."
    return "cox", (
        f"Cox preferred: RSF test C-index minus Cox is {rsf - cox:.4f}, below the {margin} margin "
        "required to prefer the less interpretable forest."
    )


def train(patient_path, sample_path, out_dir=None, config: dict | None = None, endpoint: str = "OS") -> dict:
    spec = ENDPOINT_SPECS[endpoint]
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    out_dir = Path(out_dir or spec["dir"])
    frame = load_clinical(patient_path, sample_path)
    X, event, time = build_target(frame, endpoint)

    idx_tr, idx_te = train_test_split(
        np.arange(len(X)), test_size=cfg["test_size"], random_state=cfg["seed"], stratify=event
    )
    X_tr_raw, X_te_raw = X.iloc[idx_tr], X.iloc[idx_te]
    y_tr, y_te = make_y(event[idx_tr], time[idx_tr]), make_y(event[idx_te], time[idx_te])

    pre = build_preprocessor().fit(X_tr_raw)  # training rows only
    X_tr, X_te = pre.transform(X_tr_raw), pre.transform(X_te_raw)
    feature_names = [str(n) for n in pre.get_feature_names_out()]
    times = evaluation_times(y_te)

    fitted, metrics, skipped = {}, {}, {}
    for name, fit in (("cox", _fit_cox), ("rsf", _fit_rsf)):
        model, params = fit(X_tr, y_tr, cfg)
        risk_tr, risk_te = model.predict(X_tr), model.predict(X_te)
        auc, auc_err = safe(time_dependent_auc, y_tr, y_te, risk_te, times)
        ibs, ibs_err = safe(brier, model, X_te, y_tr, y_te, times)
        fitted[name] = model
        metrics[name] = {
            "train_c_index": c_index(event[idx_tr], time[idx_tr], risk_tr),
            "test_c_index": c_index(event[idx_te], time[idx_te], risk_te),
            "time_dependent_auc": auc,
            "integrated_brier_score": ibs,
            **_cv_stability(model, X_tr_raw, y_tr, cfg),
            "hyperparameters": params,
        }
        skipped[name] = {k: v for k, v in (("time_dependent_auc", auc_err), ("integrated_brier_score", ibs_err)) if v}

    selected, reason = select_model(metrics, cfg["interpretability_margin"])
    split = {
        "n_total": int(len(X)),
        "n_train": int(len(idx_tr)),
        "n_test": int(len(idx_te)),
        "events_train": int(event[idx_tr].sum()),
        "events_test": int(event[idx_te].sum()),
        "censoring_rate_train": float(1 - event[idx_tr].mean()),
        "censoring_rate_test": float(1 - event[idx_te].mean()),
        "endpoint": endpoint,
        "n_excluded_no_target": int(len(frame) - len(X)),
        "n_features_raw": len(FEATURES),
        "n_features_after_preprocessing": len(feature_names),
        "evaluation_times_months": times.tolist(),
    }
    metadata = {
        "model_name": spec["name"],
        "endpoint": endpoint,
        "status": RESEARCH_STATEMENT,
        "model_version": spec["version"],
        "selected_model": selected,
        "selection_reason": reason,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "target": spec["target"],
        "feature_names": feature_names,
        "raw_features": {"numeric": NUMERIC_FEATURES, "categorical": CATEGORICAL_FEATURES},
        "dataset": {
            "source": "METABRIC, cBioPortal clinical files (patient + sample)",
            "files": {Path(p).name: {"sha256": file_sha256(p)} for p in (patient_path, sample_path)},
            "patients_in_files": int(len(frame)),
        },
        "training_config": cfg,
        "split": split,
        "environment": {
            "python": platform.python_version(),
            "scikit-survival": sksurv.__version__,
            "scikit-learn": sklearn.__version__,
        },
        "metrics": metrics[selected],
        "limitations": [
            "Research/prototype model; not clinically validated and not for patient care.",
            "Single random split of one historical cohort; no external validation.",
            "Treatment variables are recorded post-diagnosis and confounded by indication.",
            "Not a treatment-response model: it does not estimate the effect of any treatment.",
            *(["RFS counts recurrence and disease-specific death; prognostic outcome modelling only."] if endpoint == "RFS" else []),
        ],
    }
    report = {
        "model_name": spec["name"],
        "status": RESEARCH_STATEMENT,
        "split": split,
        "candidates": metrics,
        "metrics_not_computed": skipped,
        "selected_model": selected,
        "selection_reason": reason,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"preprocessor": pre, "model": fitted[selected], "metadata": metadata}, out_dir / "model.joblib", compress=3)
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the METABRIC overall-survival research models.")
    parser.add_argument("--patient", required=True, help="data_clinical_patient.txt")
    parser.add_argument("--sample", required=True, help="data_clinical_sample.txt")
    parser.add_argument("--endpoint", choices=sorted(ENDPOINT_SPECS), default="OS")
    parser.add_argument("--out", default=None, help="default: the endpoint's artifact directory")
    args = parser.parse_args()
    print(json.dumps(train(args.patient, args.sample, args.out, endpoint=args.endpoint), indent=2))


if __name__ == "__main__":
    main()
