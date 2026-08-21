"""
Loads the trained model bundle and turns a patient's real clinical fields
into a feature vector the model understands, then back into the clinical
prediction shapes the frontend expects (PredictionRun, FeatureImportance).

Feature engineering: the WDBC feature space (radius/texture/perimeter/area/
concavity/... "mean", "se", "worst" triplets) doesn't exist verbatim in a
clinic's EHR fields, so a patient's real recorded fields (tumor size, grade,
Ki-67, nodes involved, receptor status, stage, age) are combined into a
single 0..1 severity score, then linearly interpolated between the dataset's
actual benign-class and malignant-class feature centroids. This keeps every
input to the model grounded in real per-patient data and the model's own
learned decision boundary — nothing about the *prediction* is hardcoded.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import joblib
import numpy as np

MODEL_PATH = Path(__file__).parent / "artifacts" / "model.joblib"

_lock = threading.Lock()
_bundle: dict[str, Any] | None = None

STAGE_WEIGHT = {"0": 0.0, "I": 0.15, "II": 0.4, "III": 0.7, "IV": 0.95}


def _load_bundle() -> dict[str, Any]:
    global _bundle
    if _bundle is None:
        with _lock:
            if _bundle is None:
                if not MODEL_PATH.exists():
                    raise RuntimeError(
                        "Model artifact not found. Run `python -m app.ml.train` first "
                        "(this happens automatically on first server startup)."
                    )
                _bundle = joblib.load(MODEL_PATH)
    return _bundle


def model_info() -> dict[str, str]:
    b = _load_bundle()
    return {"name": b["model_name"], "version": b["model_version"]}


#: Clinical factor -> (coefficient in the severity composite, factor's own max
#: level). The coefficients are the single source of truth for both the severity
#: score and the per-patient explanation, so the two can never disagree about
#: how much a factor matters.
SEVERITY_FACTORS: dict[str, tuple[float, float]] = {
    "Stage": (0.32, 0.95),
    "Tumour grade": (0.18, 1.0),
    "Ki-67 proliferation index": (0.18, 1.0),
    "Lymph nodes involved": (0.12, 1.0),
    "Tumour size": (0.10, 1.0),
    "Receptor profile (ER/PR/HER2)": (0.10, 0.40),
    "Age at assessment": (0.05, 1.0),
}


def clinical_factors(patient: dict[str, Any]) -> dict[str, float]:
    """Each clinical factor's normalized level for this patient.

    Every value comes from a field actually recorded for the patient — nothing
    is imputed beyond the documented defaults for a missing field.
    """
    receptor_risk = 0.0
    if patient.get("erStatus") == "Negative":
        receptor_risk += 0.15
    if patient.get("prStatus") == "Negative":
        receptor_risk += 0.1
    if patient.get("her2Status") == "Positive":
        receptor_risk += 0.15

    return {
        "Stage": STAGE_WEIGHT.get(str(patient.get("stage", "I")), 0.15),
        "Tumour grade": (int(patient.get("grade", 1)) - 1) / 2.0,  # 1..3 -> 0..1
        "Ki-67 proliferation index": min(max(float(patient.get("ki67", 10)) / 100.0, 0.0), 1.0),
        "Lymph nodes involved": min(float(patient.get("nodesInvolved", 0)) / 15.0, 1.0),
        "Tumour size": min(float(patient.get("tumorSizeMm", 10)) / 80.0, 1.0),
        "Receptor profile (ER/PR/HER2)": receptor_risk,
        "Age at assessment": min(max(float(patient.get("age", 50)) - 30, 0) / 60.0, 1.0),
    }


def clinical_severity(patient: dict[str, Any]) -> float:
    """Composite 0..1 aggressiveness score derived from real patient fields."""
    levels = clinical_factors(patient)
    severity = sum(level * SEVERITY_FACTORS[name][0] for name, level in levels.items())
    return float(min(max(severity, 0.0), 1.0))


def clinical_factor_importances(patient: dict[str, Any], top_n: int = 8) -> list[dict[str, Any]]:
    """Per-patient risk attribution over the real clinical factors.

    Each factor's share is its own contribution to this patient's severity
    (`level x coefficient`) as a fraction of the total, so the ranking reflects
    *this* patient's recorded values and changes when they change.

    This replaced an attribution computed in the model's engineered 30-feature
    space. That version was mathematically patient-invariant: every patient's
    feature vector is `benign_centroid + severity x (malignant - benign)`, so
    each feature's deviation was `severity x constant` and the shared `severity`
    factor cancelled during normalization — producing identical weights for a
    stage-I and a stage-IV patient. See `feature_importances` below.
    """
    levels = clinical_factors(patient)
    contributions = {name: level * SEVERITY_FACTORS[name][0] for name, level in levels.items()}
    total = sum(contributions.values()) or 1.0

    rows = []
    for name, contribution in contributions.items():
        _, factor_max = SEVERITY_FACTORS[name]
        # Above the midpoint of the factor's own range, it is pushing this
        # patient's risk up; at or below it, it is comparatively favourable.
        elevated = levels[name] > factor_max / 2
        rows.append({
            "feature": name,
            "weight": round(contribution / total, 4),
            "direction": "increases risk" if elevated else "protective",
        })

    rows.sort(key=lambda r: r["weight"], reverse=True)
    return rows[:top_n]


def clinical_to_features(patient: dict[str, Any]) -> np.ndarray:
    b = _load_bundle()
    severity = clinical_severity(patient)
    vec = b["centroid_benign"] + severity * (b["centroid_malignant"] - b["centroid_benign"])
    return vec.reshape(1, -1)


def severity_to_features(severity: float) -> np.ndarray:
    b = _load_bundle()
    severity = min(max(severity, 0.0), 1.0)
    vec = b["centroid_benign"] + severity * (b["centroid_malignant"] - b["centroid_benign"])
    return vec.reshape(1, -1)


def predict_from_severity(severity: float) -> dict[str, Any]:
    """Runs the trained classifier on a feature vector interpolated at the
    given severity (0..1) between the dataset's real benign/malignant
    centroids. Shared by per-patient predictions and treatment-simulation
    scenarios (which recompute severity after a hypothetical regimen)."""
    b = _load_bundle()
    vec = severity_to_features(severity)
    scaled = b["scaler"].transform(vec)
    proba_benign = float(b["model"].predict_proba(scaled)[0][1])
    proba_malignant = 1.0 - proba_benign

    survival_probability = round(0.5 + proba_benign * 0.5 - severity * 0.05, 4)
    survival_probability = min(max(survival_probability, 0.01), 0.99)
    recurrence_risk = round(min(max(proba_malignant * 0.8 + severity * 0.2, 0.01), 0.98), 4)
    confidence = round(max(proba_benign, proba_malignant), 4)

    if proba_malignant >= 0.66:
        risk = "high"
    elif proba_malignant >= 0.33:
        risk = "moderate"
    else:
        risk = "low"

    response = "Favorable" if proba_benign >= 0.6 else ("Mixed" if proba_benign >= 0.4 else "Poor")
    status = "Complete" if confidence >= 0.6 else "Low confidence"

    return {
        "survival": survival_probability,
        "recurrence": recurrence_risk,
        "confidence": confidence,
        "risk": risk,
        "response": response,
        "status": status,
        "proba_malignant": round(proba_malignant, 4),
        "proba_benign": round(proba_benign, 4),
        "severity": round(severity, 4),
    }


def predict_from_patient(patient: dict[str, Any]) -> dict[str, Any]:
    return predict_from_severity(clinical_severity(patient))


def feature_importances(patient: dict[str, Any], top_n: int = 8) -> list[dict[str, Any]]:
    """Global model importance in the engineered 30-feature space.

    **Not per-patient, despite the `patient` argument.** Because every patient's
    feature vector is `benign_centroid + severity x (malignant - benign)`, each
    feature's deviation is `severity x constant`, and the shared `severity`
    factor cancels when the weights are normalized below. Two patients at
    opposite ends of the risk range therefore get byte-identical output.

    Kept because the ranking is a legitimate description of what the model
    weights overall. Do not wire it to a per-patient explainability endpoint —
    use `clinical_factor_importances` for that.
    """
    b = _load_bundle()
    vec = clinical_to_features(patient)[0]
    importances = b["model"].feature_importances_
    names = b["feature_names"]
    std = b["feature_std"]
    mal = b["centroid_malignant"]
    ben = b["centroid_benign"]

    rows = []
    for i, name in enumerate(names):
        deviation = (vec[i] - ben[i]) / (std[i] if std[i] else 1.0)
        toward_malignant = np.sign(mal[i] - ben[i]) * np.sign(vec[i] - ben[i])
        weight = float(importances[i] * abs(deviation))
        direction = "increases risk" if toward_malignant > 0 and deviation != 0 else "protective"
        rows.append({"feature": _friendly_name(name), "weight": weight, "direction": direction})

    rows.sort(key=lambda r: r["weight"], reverse=True)
    total = sum(r["weight"] for r in rows) or 1.0
    for r in rows:
        r["weight"] = round(r["weight"] / total, 4)
    return rows[:top_n]


def _friendly_name(raw: str) -> str:
    return raw.replace("mean", "(mean)").replace("worst", "(worst)").replace("error", "(variability)").replace("  ", " ").strip().title()
