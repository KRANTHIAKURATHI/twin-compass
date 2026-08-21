"""Swappable prediction-model boundary.

Everything in the backend that needs a model output goes through
`PredictionModel` rather than importing `app.ml.model` directly. Two reasons:

1. **Substitutability.** A real, clinically validated model can be dropped in
   by implementing this ABC — no service or router changes. Today's
   implementation is `HeuristicRandomForestModel`, a pass-through to the
   existing RandomForest + regimen rules; numeric behaviour is unchanged.
2. **Honest labelling in one place.** The model's display name was previously a
   hardcoded string literal in three routers/services. It now comes from
   `ModelMetadata`, read from the same `artifacts/metrics.json` the seeder uses,
   and carries `model_type="development"` / `is_validated=False`.

The current model is trained on the sklearn Wisconsin Diagnostic Breast Cancer
dataset — a diagnostic (benign/malignant) dataset, **not** oncology outcome
data. Its outputs are research-prototype decision-support estimates, not
clinically validated prognoses, and `is_validated` is `False` to say so.
"""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.ml import model as _rf
from app.ml import regimens as _regimens

METRICS_PATH = Path(__file__).parent / "artifacts" / "metrics.json"

#: `top_n` value meaning "don't truncate" — larger than any feature space here.
_ALL_FEATURES = 10_000

#: Shown wherever a UI needs to explain what these numbers are and are not.
DISCLAIMER = (
    "Research-prototype decision-support estimate produced by a development "
    "model. Not clinically validated and not a diagnosis; clinical judgement "
    "governs all care decisions."
)


@dataclass(frozen=True)
class ModelMetadata:
    """Provenance for a single model implementation."""

    name: str
    version: str
    dataset_name: str
    trained_at: str
    model_type: str = "development"
    is_validated: bool = False
    disclaimer: str = DISCLAIMER

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "datasetName": self.dataset_name,
            "trainedAt": self.trained_at,
            "modelType": self.model_type,
            "isValidated": self.is_validated,
            "disclaimer": self.disclaimer,
        }


def patient_to_model_fields(p: Any) -> dict[str, Any]:
    """Maps a `models.Patient` row to the camelCase input dict every
    `PredictionModel` expects.

    This mapping previously existed verbatim in four places (twin service,
    patient service, predictions router, simulations router); a field added on
    one side but not the others silently changed predictions between endpoints.
    """
    return {
        "stage": p.stage,
        "grade": p.grade,
        "ki67": p.ki67,
        "nodesInvolved": p.nodes_involved,
        "tumorSizeMm": p.tumor_size_mm,
        "erStatus": p.er_status,
        "prStatus": p.pr_status,
        "her2Status": p.her2_status,
        "age": p.age,
    }


class PredictionModel(ABC):
    """The only contract services depend on.

    `patient_fields` is the camelCase dict produced by
    `app.serializers`/router `_patient_fields` helpers — real recorded clinical
    fields (stage, tumorSizeMm, grade, ki67, nodesInvolved, receptor statuses,
    age), never synthetic values.
    """

    @property
    @abstractmethod
    def metadata(self) -> ModelMetadata: ...

    @abstractmethod
    def predict(self, patient_fields: dict[str, Any]) -> dict[str, Any]:
        """Returns survival/recurrence/confidence/risk/response/status/severity."""

    @abstractmethod
    def explain(self, patient_fields: dict[str, Any], top_n: int = 8) -> list[dict[str, Any]]:
        """Per-patient feature contributions: `{feature, weight, direction}`."""

    @abstractmethod
    def simulate(self, patient_fields: dict[str, Any], regimen_name: str) -> dict[str, Any]:
        """One hypothetical regimen outcome. Simulated, not observed."""

    @abstractmethod
    def simulate_all(self, patient_fields: dict[str, Any]) -> list[dict[str, Any]]:
        """Every known regimen, with one flagged `recommended`."""

    @abstractmethod
    def regimen_names(self) -> list[str]:
        """Regimens this model can simulate."""


def _read_metrics() -> dict[str, Any]:
    if not METRICS_PATH.exists():
        return {}
    try:
        with METRICS_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        # Metadata is descriptive, not load-bearing: a missing or corrupt
        # metrics file must not take prediction endpoints down.
        return {}


class HeuristicRandomForestModel(PredictionModel):
    """Adapter over the existing `app.ml.model` + `app.ml.regimens`.

    Deliberately contains no numeric logic of its own — it exists so call sites
    depend on the interface rather than on module-level functions.
    """

    def __init__(self, metrics: dict[str, Any] | None = None) -> None:
        m = metrics if metrics is not None else _read_metrics()
        self._metadata = ModelMetadata(
            name=m.get("model_name", "OncoTwin Malignancy Risk Model"),
            version=m.get("model_version", "v0.0.0-unknown"),
            dataset_name=m.get("dataset_name", "unknown"),
            trained_at=m.get("trained_at", ""),
        )

    @property
    def metadata(self) -> ModelMetadata:
        return self._metadata

    def predict(self, patient_fields: dict[str, Any]) -> dict[str, Any]:
        return _rf.predict_from_patient(patient_fields)

    def explain(self, patient_fields: dict[str, Any], top_n: int = 8) -> list[dict[str, Any]]:
        # Deliberately not `_rf.feature_importances`: that one is patient-
        # invariant after normalization (see its docstring).
        return _rf.clinical_factor_importances(patient_fields, top_n=top_n)

    def simulate(self, patient_fields: dict[str, Any], regimen_name: str) -> dict[str, Any]:
        return _regimens.simulate_scenario(patient_fields, regimen_name)

    def simulate_all(self, patient_fields: dict[str, Any]) -> list[dict[str, Any]]:
        return _regimens.simulate_all(patient_fields)

    def regimen_names(self) -> list[str]:
        return list(_regimens.REGIMENS)


_lock = threading.Lock()
_instance: PredictionModel | None = None


def get_prediction_model() -> PredictionModel:
    """Process-wide singleton, mirroring `app.ml.model`'s lazy joblib load.

    Services accept `model: PredictionModel | None = None` and default to this,
    so a unit test can inject a fake without touching the joblib artifact.
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = HeuristicRandomForestModel()
    return _instance


def set_prediction_model(model: PredictionModel | None) -> None:
    """Test seam. Pass `None` to fall back to the default implementation."""
    global _instance
    with _lock:
        _instance = model


def explain_delta(
    baseline_fields: dict[str, Any],
    scenario_fields: dict[str, Any],
    model: PredictionModel | None = None,
    top_n: int = 8,
) -> list[dict[str, Any]]:
    """Which real patient factors move, and how, between two states.

    Both sides come from `model.explain`, so the entries are actual model
    feature attributions — there is no canned narrative text. Used for both
    "why did this prediction change" and "why does this regimen differ from
    baseline".
    """
    m = model or get_prediction_model()
    # Untruncated on both sides: a delta computed against differing top-N
    # windows would show spurious appear/disappear jumps.
    before = {r["feature"]: r for r in m.explain(baseline_fields, top_n=_ALL_FEATURES)}
    after = {r["feature"]: r for r in m.explain(scenario_fields, top_n=_ALL_FEATURES)}

    rows: list[dict[str, Any]] = []
    for feature in before.keys() | after.keys():
        b = before.get(feature)
        a = after.get(feature)
        weight_before = float(b["weight"]) if b else 0.0
        weight_after = float(a["weight"]) if a else 0.0
        contribution = round(weight_after - weight_before, 4)
        rows.append(
            {
                "feature": feature,
                "weightBefore": round(weight_before, 4),
                "weightAfter": round(weight_after, 4),
                "contribution": contribution,
                # Direction of the *change*, from the scenario side where known.
                "direction": (a or b or {}).get("direction", "unchanged"),
            }
        )

    rows.sort(key=lambda r: abs(r["contribution"]), reverse=True)
    return rows[:top_n]
