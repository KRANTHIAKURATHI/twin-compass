"""METABRIC OS / RFS research prognosis for an OncoTwin patient.

Maps ONLY recorded OncoTwin clinical fields onto the METABRIC clinical features the saved Cox models were trained on, and scores
them with the saved preprocessing + model (`app.ml.survival.predict`). Nothing is invented: a METABRIC feature OncoTwin does not
record is left missing, so the artifact's own preprocessing handles it (its trained "Unknown" level / training median), and the
response lists exactly which features were mapped, which were not recorded, and which are required.

These are prognostic research models (overall survival / relapse-free survival). They are not treatment-response models, are not
clinically validated, use no molecular expression data, and their output is not "AI confidence".
"""
from __future__ import annotations

import math
import re
import threading
from pathlib import Path
from typing import Any

from app.ml.survival import RESEARCH_STATEMENT

_ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {}

MODELS: dict[str, dict[str, str]] = {
    "os": {
        "directory": "survival", "key": "overallSurvival", "endpoint": "overall_survival",
        "label": "METABRIC overall survival model — research only",
        "estimate": "overall_survival_probability", "display": "Overall survival estimate — METABRIC research model",
    },
    "rfs": {
        "directory": "survival_rfs", "key": "relapseFreeSurvival", "endpoint": "relapse_free_survival",
        "label": "METABRIC relapse-free survival model — research only",
        "estimate": "relapse_free_probability", "display": "Relapse-free survival estimate — METABRIC research model",
    },
}

# METABRIC feature -> the OncoTwin `patients` column it is read from. Features missing here are NOT recorded by OncoTwin.
FEATURE_SOURCE: dict[str, str] = {
    "AGE_AT_DIAGNOSIS": "age",                       # years; OncoTwin has no separate age-at-diagnosis field
    "LYMPH_NODES_EXAMINED_POSITIVE": "nodes_involved",
    "TUMOR_SIZE": "tumor_size_mm",                   # METABRIC TUMOR_SIZE is in mm
    "GRADE": "grade",                                # 1-3
    "TUMOR_STAGE": "stage",                          # roman numeral -> 0-4
    "ER_STATUS": "er_status",
    "PR_STATUS": "pr_status",
    "HER2_STATUS": "her2_status",
}
# Needed for a prognosis at all. The five numeric inputs would otherwise be median-imputed silently, and the ER-status
# level "Unknown" does not exist in the training data.
REQUIRED = ("AGE_AT_DIAGNOSIS", "LYMPH_NODES_EXAMINED_POSITIVE", "TUMOR_SIZE", "GRADE", "TUMOR_STAGE", "ER_STATUS")
# Model features OncoTwin does not record. They are never filled in; the trained "Unknown" level applies.
NOT_RECORDED = (
    "INFERRED_MENOPAUSAL_STATE", "CLAUDIN_SUBTYPE", "HISTOLOGICAL_SUBTYPE",
    "CHEMOTHERAPY", "HORMONE_THERAPY", "RADIO_THERAPY", "BREAST_SURGERY",
)

_STAGE = re.compile(r"^(?:stage\s*)?(0|iv|iii|ii|i|[0-4])\s*[a-c]?\d?$", re.IGNORECASE)
_STAGE_VALUE = {"0": 0, "i": 1, "ii": 2, "iii": 3, "iv": 4, "1": 1, "2": 2, "3": 3, "4": 4}


def _num(value: object) -> float | None:
    try:
        x = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _status(value: object) -> str | None:
    key = str(value).strip().lower() if value is not None else ""
    return {"positive": "Positive", "pos": "Positive", "+": "Positive", "negative": "Negative", "neg": "Negative", "-": "Negative"}.get(key)


def map_clinical_features(patient: dict[str, Any]) -> dict[str, object]:
    """OncoTwin patient dict (snake_case DB columns) -> {METABRIC feature: value} for features that are actually recorded and valid.

    Out-of-range values are treated as not recorded rather than corrected (for example age 0 or tumour size 0 mm, which are
    schema defaults and not measurements).
    """
    out: dict[str, object] = {}
    age = _num(patient.get("age"))
    if age is not None and 0 < age <= 120:
        out["AGE_AT_DIAGNOSIS"] = age
    nodes = _num(patient.get("nodes_involved"))
    if nodes is not None and nodes >= 0:
        out["LYMPH_NODES_EXAMINED_POSITIVE"] = nodes
    size = _num(patient.get("tumor_size_mm"))
    if size is not None and size > 0:
        out["TUMOR_SIZE"] = size
    grade = _num(patient.get("grade"))
    if grade is not None and grade in (1, 2, 3):
        out["GRADE"] = grade
    stage = patient.get("stage")
    m = _STAGE.match(str(stage).strip()) if stage is not None else None
    if m:
        out["TUMOR_STAGE"] = float(_STAGE_VALUE[m.group(1).lower()])
    for feature in ("ER_STATUS", "PR_STATUS", "HER2_STATUS"):
        s = _status(patient.get(FEATURE_SOURCE[feature]))
        if s:
            out[feature] = s
    return out


def availability(mapped: dict[str, object]) -> dict[str, object]:
    return {
        "mapped": {f: {"value": v, "source": f"patients.{FEATURE_SOURCE[f]}"} for f, v in mapped.items()},
        "required": list(REQUIRED),
        "missingRequired": [f for f in REQUIRED if f not in mapped],
        "recordedButUnavailable": [f for f in FEATURE_SOURCE if f not in mapped and f not in REQUIRED],
        "notRecordedInOncoTwin": list(NOT_RECORDED),
        "missingValueHandling": (
            "Features not recorded are not estimated. They are passed as missing and the saved preprocessing applies "
            "(training median for numerics, the trained 'Unknown' level for categories)."
        ),
        "molecularExpressionUsed": False,
    }


def _load(code: str):
    with _LOCK:
        if code not in _CACHE:
            from app.ml.survival.predict import load_artifact   # imports scikit-survival lazily

            _CACHE[code] = load_artifact(_ARTIFACTS / MODELS[code]["directory"])
        return _CACHE[code]


def _provenance(code: str, meta: dict[str, Any]) -> dict[str, object]:
    info = MODELS[code]
    return {
        "model": info["label"],
        "modelName": meta.get("model_name"),
        "modelVersion": meta.get("model_version"),
        "algorithm": "Cox proportional hazards" if meta.get("selected_model") == "cox" else meta.get("selected_model"),
        "dataset": "METABRIC (cBioPortal clinical files), clinical variables only",
        "trainedAt": meta.get("trained_at"),
        "testCIndex": (meta.get("metrics") or {}).get("test_c_index"),
        "status": RESEARCH_STATEMENT,
        "clinicallyValidated": False,
        "externalValidation": False,
        "purpose": "Prognostic modelling of the stated endpoint. Not a treatment-response model; not a treatment recommendation.",
        "calibration": "Not assessed. The estimates below come from the Cox baseline survival function.",
    }


def _unavailable(code: str, reason: str, avail: dict[str, object] | None = None, meta: dict[str, Any] | None = None) -> dict[str, object]:
    info = MODELS[code]
    return {
        "status": "unavailable", "reason": reason, "model": info["label"], "endpoint": info["endpoint"],
        "researchStatus": RESEARCH_STATEMENT, "clinicallyValidated": False,
        **({"featureAvailability": avail} if avail else {}),
        **({"provenance": _provenance(code, meta)} if meta else {}),
    }


def prognosis_for_patient(patient: dict[str, Any]) -> dict[str, object]:
    """Both METABRIC research estimates for one patient. Never raises: a missing artifact/dependency or a missing
    required feature gives that model an explicit `unavailable` result."""
    mapped = map_clinical_features(patient)
    avail = availability(mapped)
    out: dict[str, object] = {}
    for code, info in MODELS.items():
        try:
            artifact = _load(code)
        except (ImportError, OSError, RuntimeError, KeyError, ValueError) as exc:
            out[info["key"]] = _unavailable(code, f"Model artifact or its runtime is unavailable ({type(exc).__name__}).", avail)
            continue
        meta = artifact.metadata
        if avail["missingRequired"]:
            out[info["key"]] = _unavailable(
                code, "Required clinical features are not recorded for this patient: " + ", ".join(avail["missingRequired"]) + ".", avail, meta
            )
            continue
        result = artifact.predict([mapped])[0]
        out[info["key"]] = {
            "status": "available",
            "model": info["label"],
            "displayName": info["display"],
            "endpoint": info["endpoint"],
            "researchStatus": RESEARCH_STATEMENT,
            "clinicallyValidated": False,
            "modelVersion": meta.get("model_version"),
            "riskScore": result["risk_score"],
            "riskScoreNote": (
                "Relative Cox linear predictor (higher = higher modelled hazard). It is not a probability or percentage and is "
                "only comparable with other scores from this same model."
            ),
            "estimateKind": info["estimate"],
            "estimates": [
                {"horizonMonths": int(k.split("_")[0]), "probability": v} for k, v in result["survival_probability"].items()
            ],
            "estimateNote": "probability is null where the horizon lies beyond the model's training follow-up (not extrapolated).",
            "timeHorizonsMonths": [int(k.split("_")[0]) for k in result["survival_probability"]],
            "featureAvailability": avail,
            "provenance": _provenance(code, meta),
        }
    return out
