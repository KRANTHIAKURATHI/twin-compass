"""Load the treatment-response research artifact and score samples. Research model - not clinically validated."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .data import CLINICAL_FEATURES
from .pipeline import KINDS, FittedModel


@dataclass
class TreatmentResponseArtifact:
    models: dict[str, FittedModel]
    primary: str
    metadata: dict

    def predict(self, clinical: list[dict[str, object]], expression: list[dict[str, float]], model: str | None = None) -> list[dict[str, object]]:
        """One result per sample. `clinical`: keys age, er, pr, her2 (1/0), grade, stage; `expression`: Ensembl ID -> TPM.

        Missing clinical values take their training median/mode; genes absent from `expression` take their training median.
        Returns P(pCR) for the GSE163882 neoadjuvant taxane cohort - not a treatment recommendation."""
        kind = model or self.primary
        if kind not in self.models:
            raise ValueError(f"unknown model {kind!r}; choose from {sorted(self.models)}")
        if len(clinical) != len(expression):
            raise ValueError("clinical and expression must have one entry per sample")
        m = self.models[kind]
        frame = pd.DataFrame([{c: _number(p.get(c)) for c in CLINICAL_FEATURES} for p in clinical], columns=CLINICAL_FEATURES)
        tpm = None
        if m.expression is not None:
            genes = m.expression.all_ids
            tpm = np.array([[_number(e.get(g)) for g in genes] for e in expression], dtype=float).reshape(len(expression), len(genes))
        proba = m.predict_proba(frame, tpm)
        thr = float(self.metadata["decision_thresholds"][kind])
        return [
            {"pcr_probability": float(p), "predicted_pcr": bool(p >= thr), "threshold": thr, "model": self.metadata["model_name"], "variant": kind, "status": self.metadata["status"]}
            for p in proba
        ]


def _number(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def load_artifact(directory: str | Path) -> TreatmentResponseArtifact:
    path = Path(directory)
    bundle = joblib.load(path if str(path).endswith(".joblib") else path / "model.joblib")
    assert set(bundle["models"]) <= set(KINDS)
    return TreatmentResponseArtifact(bundle["models"], bundle["primary"], bundle["metadata"])
