"""Training-fold-only preprocessing, gene screening, Elastic-Net logistic models and the inner (nested) search.

Everything learned here (detection filter, scaling, t-statistics, ranking, imputation values, hyper-parameters)
comes from the rows passed to `fit`; held-out rows only go through `transform`.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.model_selection import StratifiedGroupKFold

from .data import CLINICAL_FEATURES

DETECTION_TPM = 1.0          # a gene is "detected" in a sample when TPM > 1
DETECTION_FRACTION = 0.20    # ... and kept when detected in >= 20% of the TRAINING samples
K_GRID = (50, 100, 200, 500)
L1_GRID = (0.2, 0.5, 0.8, 1.0)
C_GRID = (0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0)
INNER_FOLDS = 4
CLINICAL_C_GRID = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 100.0)   # clinical-only baseline: wider so its optimum is not at the grid edge
CLIN_SCALE_GRID = (1.0, 5.0, 25.0)   # combined model only: clinical columns are multiplied by this, i.e. their L1/L2 penalty is divided by scale**2
KINDS = ("clinical", "expression", "combined")
KIND_LABEL = {"clinical": "A clinical-only", "expression": "B expression-only", "combined": "C clinical + expression"}


def log2_tpm(tpm: np.ndarray) -> np.ndarray:
    """log2(TPM + 1)."""
    return np.log2(np.asarray(tpm, dtype=np.float64) + 1.0)


# ---------------------------------------------------------------- expression

@dataclass
class ExpressionPreprocessor:
    """Detection filter + standardisation + univariate pCR-vs-RD screening, all learned from training rows."""
    all_ids: list[str]            # Ensembl ids of the columns this object expects
    kept: np.ndarray              # indices (into all_ids) of genes passing the training detection filter
    mean: np.ndarray              # per kept gene, of log2(TPM+1), training rows
    std: np.ndarray
    median: np.ndarray            # used only to fill missing values at prediction time
    t: np.ndarray                 # Welch t (pCR vs RD) per kept gene, training rows
    ranking: np.ndarray           # indices into `kept`, strongest |t| first (ties: lower index first)
    n_detected_filter: int = 0

    @classmethod
    def fit(cls, tpm: np.ndarray, y: np.ndarray, ensembl_ids: list[str]) -> "ExpressionPreprocessor":
        y = np.asarray(y)
        n1, n0 = int((y == 1).sum()), int((y == 0).sum())
        if n1 < 2 or n0 < 2:
            raise ValueError("need at least two samples of each class to screen genes")
        L = log2_tpm(tpm)
        detected = (L > np.log2(DETECTION_TPM + 1.0)).sum(axis=0)
        kept = np.flatnonzero(detected >= DETECTION_FRACTION * len(L) - 1e-9)
        if len(kept) == 0:
            raise ValueError("no gene passes the detection filter")
        Lk = L[:, kept]
        mean, std = Lk.mean(axis=0), Lk.std(axis=0)
        std = np.where(std > 1e-12, std, 1.0)
        Z = (Lk - mean) / std
        a, b = Z[y == 1], Z[y == 0]
        se = np.sqrt(a.var(axis=0, ddof=1) / n1 + b.var(axis=0, ddof=1) / n0)
        t = (a.mean(axis=0) - b.mean(axis=0)) / np.where(se > 1e-12, se, np.inf)
        ranking = np.argsort(-np.abs(t), kind="stable")
        return cls(list(ensembl_ids), kept, mean, std, np.median(Lk, axis=0), t, ranking, len(kept))

    def transform(self, tpm: np.ndarray, k: int) -> np.ndarray:
        """Standardised log2(TPM+1) of the top-k genes (columns ordered by rank); missing values -> training median."""
        idx = self.ranking[:k]
        L = log2_tpm(np.asarray(tpm, dtype=np.float64)[:, self.kept[idx]])
        L = np.where(np.isnan(L), self.median[idx], L)
        return (L - self.mean[idx]) / self.std[idx]

    def selected_ids(self, k: int) -> list[str]:
        return [self.all_ids[i] for i in self.kept[self.ranking[:k]]]

    def restrict(self, k: int) -> "ExpressionPreprocessor":
        """Keep only the top-k genes; the result expects a matrix whose columns are `selected_ids(k)`."""
        r = self.ranking[:k]
        return ExpressionPreprocessor(
            self.selected_ids(k), np.arange(len(r)), self.mean[r], self.std[r], self.median[r], self.t[r], np.arange(len(r)), self.n_detected_filter
        )


# ------------------------------------------------------------------ clinical

@dataclass
class ClinicalPreprocessor:
    """Median-impute (age, grade, stage) / mode-impute (ER, PR, HER2) and standardise ordinals; training rows only."""
    fill: dict[str, float]
    mean: dict[str, float]
    std: dict[str, float]
    NUMERIC = ("age", "grade", "stage")   # grade and stage are ordinal, entered as ordered scores

    @classmethod
    def fit(cls, clinical: pd.DataFrame) -> "ClinicalPreprocessor":
        fill: dict[str, float] = {}
        mean: dict[str, float] = {}
        std: dict[str, float] = {}
        for c in CLINICAL_FEATURES:
            col = pd.to_numeric(clinical[c], errors="coerce")
            if col.notna().sum() == 0:
                fill[c] = 0.0
            elif c in cls.NUMERIC:
                fill[c] = float(col.median())
            else:
                fill[c] = float(col.mode().iloc[0])
            if c in cls.NUMERIC:
                filled = col.fillna(fill[c])
                mean[c] = float(filled.mean())
                s = float(filled.std(ddof=0))
                std[c] = s if s > 1e-12 else 1.0
        return cls(fill, mean, std)

    def transform(self, clinical: pd.DataFrame) -> np.ndarray:
        cols = []
        for c in CLINICAL_FEATURES:
            col = pd.to_numeric(clinical[c], errors="coerce").fillna(self.fill[c]).to_numpy(dtype=np.float64)
            if c in self.NUMERIC:
                col = (col - self.mean[c]) / self.std[c]
            cols.append(col)
        return np.column_stack(cols)


# -------------------------------------------------------------------- models

def make_classifier(l1_ratio: float, C: float, seed: int) -> LogisticRegression:
    """l1_ratio 0 = ridge, 1 = lasso, in between = Elastic-Net."""
    return LogisticRegression(
        l1_ratio=l1_ratio, C=C, solver="saga" if l1_ratio > 0 else "lbfgs", max_iter=3000, tol=1e-3, random_state=seed
    )


def _fit_clf(X: np.ndarray, y: np.ndarray, l1_ratio: float, C: float, seed: int) -> LogisticRegression:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        return make_classifier(l1_ratio, C, seed).fit(X, y)


def config_grid(kind: str) -> list[dict[str, float]]:
    if kind == "clinical":
        return [{"k": 0, "l1_ratio": 0.0, "C": C, "clin_scale": 1.0} for C in CLINICAL_C_GRID]
    scales = CLIN_SCALE_GRID if kind == "combined" else (1.0,)
    return [{"k": k, "l1_ratio": l1, "C": C, "clin_scale": s} for s in scales for k in K_GRID for l1 in L1_GRID for C in C_GRID]


@dataclass
class FittedModel:
    kind: str
    config: dict[str, float]
    clinical: ClinicalPreprocessor | None
    expression: ExpressionPreprocessor | None
    clf: LogisticRegression
    feature_names: list[str] = field(default_factory=list)

    def design(self, clinical: pd.DataFrame, tpm: np.ndarray | None) -> np.ndarray:
        parts = []
        if self.kind in ("clinical", "combined"):
            parts.append(self.clinical.transform(clinical) * float(self.config.get("clin_scale", 1.0)))
        if self.kind in ("expression", "combined"):
            parts.append(self.expression.transform(tpm, int(self.config["k"])))
        return np.hstack(parts)

    def predict_proba(self, clinical: pd.DataFrame, tpm: np.ndarray | None) -> np.ndarray:
        """P(pCR)."""
        return self.clf.predict_proba(self.design(clinical, tpm))[:, 1]

    def coefficients(self) -> np.ndarray:
        return self.clf.coef_[0]


def fit_model(kind: str, clinical: pd.DataFrame, tpm: np.ndarray, y: np.ndarray, ensembl_ids: list[str], config: dict[str, float], seed: int) -> FittedModel:
    """Fit preprocessing + classifier on exactly the rows given."""
    cp = ClinicalPreprocessor.fit(clinical) if kind in ("clinical", "combined") else None
    ep = ExpressionPreprocessor.fit(tpm, y, ensembl_ids) if kind in ("expression", "combined") else None
    k = int(config["k"])
    names = (list(CLINICAL_FEATURES) if cp else []) + (ep.selected_ids(k) if ep else [])
    model = FittedModel(kind, dict(config), cp, ep, None, names)  # type: ignore[arg-type]
    model.clf = _fit_clf(model.design(clinical, tpm), y, config["l1_ratio"], config["C"], seed)
    return model


def inner_search(
    kind: str, clinical: pd.DataFrame, tpm: np.ndarray, y: np.ndarray, groups: np.ndarray, ensembl_ids: list[str], seed: int, n_splits: int = INNER_FOLDS
) -> dict[str, object]:
    """Choose (k, l1_ratio, C, clinical scale) by patient-grouped stratified inner CV on the TRAINING rows only.

    Within every inner fold the detection filter, scaling, gene ranking and imputation are re-fitted on that
    fold's training part. The criterion is the pooled out-of-fold log-loss; ties go to the smaller k, smaller
    l1_ratio, smaller C (first in grid order). Returns the best config, its out-of-fold probabilities (used to pick
    the decision threshold) and the whole score table.
    """
    grid = config_grid(kind)
    oof = np.full((len(grid), len(y)), np.nan)
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    k_max = max(int(c["k"]) for c in grid)
    for tr, va in splitter.split(np.zeros(len(y)), y, groups):
        cp = ClinicalPreprocessor.fit(clinical.iloc[tr]) if kind in ("clinical", "combined") else None
        ep = ExpressionPreprocessor.fit(tpm[tr], y[tr], ensembl_ids) if kind in ("expression", "combined") else None
        Ctr = cp.transform(clinical.iloc[tr]) if cp else None
        Cva = cp.transform(clinical.iloc[va]) if cp else None
        Etr = ep.transform(tpm[tr], k_max) if ep else None   # top-k genes are a prefix of the ranked columns
        Eva = ep.transform(tpm[va], k_max) if ep else None
        for i, c in enumerate(grid):
            k = int(c["k"])
            s = float(c["clin_scale"])
            Xtr = np.hstack([m for m in (Ctr * s if cp else None, Etr[:, :k] if ep else None) if m is not None])
            Xva = np.hstack([m for m in (Cva * s if cp else None, Eva[:, :k] if ep else None) if m is not None])
            clf = _fit_clf(Xtr, y[tr], c["l1_ratio"], c["C"], seed)
            oof[i, va] = clf.predict_proba(Xva)[:, 1]
    scores = np.array([log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)) for p in oof])
    best = int(np.argmin(scores))          # first minimum = grid-order tie-break
    return {
        "config": dict(grid[best]),
        "oof": oof[best],
        "cv_log_loss": float(scores[best]),
        "table": [{**c, "cv_log_loss": float(s)} for c, s in zip(grid, scores)],
    }


def choose_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """Probability threshold maximising balanced accuracy on (training-only) out-of-fold predictions."""
    best, best_ba = 0.5, -1.0
    for thr in np.round(np.arange(0.05, 0.951, 0.01), 2):
        pred = p >= thr
        sens = float(pred[y == 1].mean())
        spec = float((~pred[y == 0]).mean())
        ba = (sens + spec) / 2
        if ba > best_ba + 1e-12:
            best, best_ba = float(thr), ba
    return best
