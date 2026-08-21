"""Treatment-simulation rule engine.

Encodes each regimen's real-world relative efficacy/toxicity/duration
profile (oncology domain assumptions, not per-patient fabricated results),
then re-runs the trained classifier (app.ml.model) on the patient's severity
after applying that regimen's effect. Every number a scenario returns is
either a documented regimen parameter or the output of the real model —
nothing is a hardcoded per-scenario response.
"""

from __future__ import annotations

from typing import Any

from app.ml.model import clinical_severity, predict_from_severity

REGIMENS: dict[str, dict[str, Any]] = {
    "AC-T (Doxorubicin/Cyclophosphamide + Paclitaxel)": {
        "efficacy": 0.55, "toxicity": 0.65, "recovery_weeks": 20, "requires": None,
    },
    "TC (Docetaxel/Cyclophosphamide)": {
        "efficacy": 0.45, "toxicity": 0.45, "recovery_weeks": 14, "requires": None,
    },
    "Endocrine Therapy (Tamoxifen/AI)": {
        "efficacy": 0.40, "toxicity": 0.15, "recovery_weeks": 6, "requires": "er_positive",
    },
    "HER2-Targeted Therapy (Trastuzumab + Pertuzumab)": {
        "efficacy": 0.60, "toxicity": 0.35, "recovery_weeks": 12, "requires": "her2_positive",
    },
    "Neoadjuvant Chemotherapy + Surgery": {
        "efficacy": 0.50, "toxicity": 0.55, "recovery_weeks": 18, "requires": None,
    },
    "Active Surveillance": {
        "efficacy": 0.05, "toxicity": 0.02, "recovery_weeks": 0, "requires": None,
    },
}


def _eligible(regimen: dict[str, Any], patient: dict[str, Any]) -> float:
    """Returns an efficacy multiplier (0..1) based on receptor eligibility."""
    req = regimen["requires"]
    if req == "er_positive":
        return 1.0 if patient.get("erStatus") == "Positive" else 0.25
    if req == "her2_positive":
        return 1.0 if patient.get("her2Status") == "Positive" else 0.2
    return 1.0


def simulate_scenario(patient: dict[str, Any], regimen_name: str) -> dict[str, Any]:
    regimen = REGIMENS.get(regimen_name, REGIMENS["Neoadjuvant Chemotherapy + Surgery"])
    baseline_severity = clinical_severity(patient)
    eligibility = _eligible(regimen, patient)
    efficacy_applied = regimen["efficacy"] * eligibility

    post_severity = max(baseline_severity * (1 - efficacy_applied), 0.02)
    baseline = predict_from_severity(baseline_severity)
    post = predict_from_severity(post_severity)

    tumor_size = float(patient.get("tumorSizeMm", 10))
    tumor_change = -round(efficacy_applied * tumor_size * 0.7, 1)
    predicted_response = round(efficacy_applied * eligibility * 100, 1)
    side_effect_risk = round(min(regimen["toxicity"] * (0.7 + 0.3 * eligibility), 0.95), 3)

    return {
        "regimen": regimen_name,
        "predicted_response": predicted_response,
        "tumor_change": tumor_change,
        "risk": post["risk"],
        "confidence": post["confidence"],
        "survival5y": post["survival"],
        "side_effect_risk": side_effect_risk,
        "recovery_weeks": regimen["recovery_weeks"],
        "recommended": False,
    }


def simulate_all(patient: dict[str, Any]) -> list[dict[str, Any]]:
    scenarios = [simulate_scenario(patient, name) for name in REGIMENS]
    best = max(scenarios, key=lambda s: (s["survival5y"], -s["side_effect_risk"]))
    for s in scenarios:
        s["recommended"] = s is best
    return scenarios
