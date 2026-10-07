"""Load a molecular survival artifact and score patients. Research model - not clinically validated."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml.survival.data import FEATURES, NUMERIC_FEATURES, normalize_value

from . import ARTIFACT_DIR

HORIZONS_MONTHS = (60, 120)


@dataclass
class MolecularArtifact:
    clinical_preprocessor: object
    expression: object      # ExpressionTransformer for the selected genes
    model: object
    alpha: float
    metadata: dict

    def predict(self, clinical: list[dict[str, object]], expression: list[dict[str, float]]) -> list[dict[str, object]]:
        """One result per patient. `clinical`: METABRIC column names; `expression`: Entrez ID -> z-score.
        Missing clinical values become "Unknown"/median; missing genes take their training median.
        `risk_score` is relative to this model only."""
        if len(clinical) != len(expression):
            raise ValueError("clinical and expression must have one entry per patient")
        frame = pd.DataFrame([{c: normalize_value(p.get(c)) for c in FEATURES} for p in clinical], columns=FEATURES)
        for col in NUMERIC_FEATURES:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        genes = self.expression.entrez_ids
        E = np.array([[_number(e.get(g)) for g in genes] for e in expression], dtype=float).reshape(len(expression), len(genes))
        X = np.hstack([self.clinical_preprocessor.transform(frame).to_numpy(dtype=float), self.expression.transform(E, selected_only=True)])
        risk = self.model.predict(X, alpha=self.alpha)
        curves = self.model.predict_survival_function(X, alpha=self.alpha)
        out = []
        for score, curve in zip(risk, curves):
            lo, hi = curve.domain
            out.append({
                "risk_score": float(score),
                "survival_probability": {f"{h}_months": float(curve(h)) if lo <= h <= hi else None for h in HORIZONS_MONTHS},
                "model": self.metadata["model_name"],
                "status": self.metadata["status"],
            })
        return out


def _number(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def load_artifact(directory: str | Path) -> MolecularArtifact:
    bundle = joblib.load(Path(directory))  if str(directory).endswith(".joblib") else joblib.load(Path(directory) / "model.joblib")
    return MolecularArtifact(bundle["clinical_preprocessor"], bundle["expression"], bundle["model"], bundle["alpha"], bundle["metadata"])


def default_dir(endpoint: str) -> Path:
    return ARTIFACT_DIR / endpoint.lower()
