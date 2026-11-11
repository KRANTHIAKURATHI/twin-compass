"""Load the treatment-response research artifact and score samples. Research model - not clinically validated."""
from __future__ import annotations

import math
import numbers
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .data import CLINICAL_FEATURES
from .pipeline import KINDS, FittedModel

# What may be left out is decided by the training data, not by convenience. The GSE163882 expression matrix had NO
# missing values and the clinical columns age/ER/PR/HER2 had none either, so the stored imputation values for those were
# never exercised in training or in the nested-CV evaluation. Only grade and stage were missing in the cohort (1 and 14
# of 213 patients), so only those two may be absent. Everything else must be supplied.
_CLINICAL_REQUIRED = ("age", "er", "pr", "her2")
_CLINICAL_BINARY = ("er", "pr", "her2")
_CLINICAL_OPTIONAL = ("grade", "stage")


def _real(value: object) -> bool:
    """A finite real number (bool and numeric strings are not accepted)."""
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _check_clinical(sample: object, index: int, kind: str) -> None:
    if not isinstance(sample, Mapping):
        raise ValueError(f"sample {index}: clinical input must be a mapping, got {type(sample).__name__}")
    bad = [c for c in _CLINICAL_REQUIRED if not _real(sample.get(c))]
    bad += [c for c in _CLINICAL_BINARY if _real(sample.get(c)) and float(sample[c]) not in (0.0, 1.0)]
    if _real(sample.get("age")) and not 0 < float(sample["age"]) <= 120:
        bad.append("age")
    bad += [c for c in _CLINICAL_OPTIONAL if sample.get(c) is not None and not _real(sample[c])]
    if bad:
        raise ValueError(
            f"sample {index}: the '{kind}' model needs recorded, valid clinical values; missing or unusable: "
            f"{', '.join(dict.fromkeys(bad))} (only grade and stage may be left out; er/pr/her2 must be 0 or 1)"
        )


def _check_expression(model: FittedModel, sample: object, index: int, kind: str) -> None:
    if not isinstance(sample, Mapping) or not sample:
        raise ValueError(
            f"sample {index}: the '{kind}' model needs a gene-expression profile (Ensembl id -> TPM); it is absent or empty. "
            "No score is produced without it - training medians are never substituted for a whole profile."
        )
    needed = model.expression.selected_ids(int(model.config["k"]))
    bad = [g for g in needed if not _real(sample.get(g)) or float(sample[g]) < 0]
    if bad:
        raise ValueError(
            f"sample {index}: {len(bad)} of the {len(needed)} genes the '{kind}' model uses are missing, non-numeric or "
            f"negative TPM (e.g. {', '.join(bad[:5])}). The training data had no missing expression values, so imputing "
            "genes is not supported; supply a complete profile."
        )


@dataclass
class TreatmentResponseArtifact:
    models: dict[str, FittedModel]
    primary: str
    metadata: dict

    def predict(self, clinical: list[dict[str, object]], expression: list[dict[str, float]], model: str | None = None) -> list[dict[str, object]]:
        """One result per sample. `clinical`: keys age, er, pr, her2 (1/0), grade, stage; `expression`: Ensembl ID -> TPM.

        Raises ValueError instead of scoring when an input the chosen model depends on is absent, empty, malformed or
        unusable: the expression profile must contain every gene the model uses (the clinical-only variant ignores
        expression), and age/er/pr/her2 must be recorded; only grade and stage may be left out (they take their training
        median, as they were missing for a few training patients). Returns P(pCR) for the GSE163882 neoadjuvant
        taxane cohort - not a treatment recommendation."""
        kind = model or self.primary
        if kind not in self.models:
            raise ValueError(f"unknown model {kind!r}; choose from {sorted(self.models)}")
        if not isinstance(clinical, (list, tuple)) or not isinstance(expression, (list, tuple)):
            raise ValueError("clinical and expression must be lists with one entry per sample")
        if len(clinical) != len(expression):
            raise ValueError("clinical and expression must have one entry per sample")
        if not clinical:
            raise ValueError("no samples to score")
        m = self.models[kind]
        for i, (c, e) in enumerate(zip(clinical, expression)):
            if not isinstance(c, Mapping):
                raise ValueError(f"sample {i}: clinical input must be a mapping, got {type(c).__name__}")
            if kind in ("clinical", "combined"):
                _check_clinical(c, i, kind)
            if m.expression is not None:
                _check_expression(m, e, i, kind)
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
