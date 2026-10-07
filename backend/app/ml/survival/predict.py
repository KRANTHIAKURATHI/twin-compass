"""Load the survival artifact and score patients. Research model - not clinically validated."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from .data import FEATURES, NUMERIC_FEATURES, normalize_value
from .train import ARTIFACT_DIR

HORIZONS_MONTHS = (60, 120)


@dataclass
class SurvivalArtifact:
    preprocessor: object
    model: object
    metadata: dict

    def predict(self, patients: list[dict[str, object]]) -> list[dict[str, object]]:
        """One result per patient dict (keys are METABRIC column names; absent or
        unrecognised values count as missing).

        `risk_score` is relative: higher means higher modelled hazard, and it is
        only comparable with other scores from the same model. Survival
        probabilities are None for a horizon beyond the training follow-up
        rather than extrapolated.
        """
        frame = pd.DataFrame(
            [{col: normalize_value(p.get(col)) for col in FEATURES} for p in patients], columns=FEATURES
        )
        for col in NUMERIC_FEATURES:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        X = self.preprocessor.transform(frame)
        risk = self.model.predict(X)
        curves = self.model.predict_survival_function(X)
        results = []
        for score, curve in zip(risk, curves):
            lo, hi = curve.domain
            results.append(
                {
                    "risk_score": float(score),
                    "survival_probability": {
                        f"{h}_months": float(curve(h)) if lo <= h <= hi else None for h in HORIZONS_MONTHS
                    },
                    "model": self.metadata["model_name"],
                    "status": self.metadata["status"],
                }
            )
        return results


def load_artifact(directory: str | Path = ARTIFACT_DIR) -> SurvivalArtifact:
    bundle = joblib.load(Path(directory) / "model.joblib")
    return SurvivalArtifact(bundle["preprocessor"], bundle["model"], bundle["metadata"])
