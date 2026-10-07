"""Training-only expression preprocessing and univariate survival screening.

Everything here is learned from the rows passed to `fit_screen`; held-out rows
only ever go through `ExpressionTransformer.transform`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

WINSOR_PCT = (1.0, 99.0)


def cox_score_z(Z: np.ndarray, event: np.ndarray, time: np.ndarray, chunk: int = 2000) -> np.ndarray:
    """Signed univariate Cox score statistic (beta = 0, Breslow ties) for every column.

    z = U / sqrt(I) where U is the sum over events of (x - mean of x in the risk
    set) and I the sum of the risk-set variances. |z| ranks genes by association
    with survival; it is the log-rank-type statistic and needs no model fit.
    """
    order = np.argsort(time, kind="stable")
    t, e, Zs = time[order], event[order].astype(float), Z[order]
    start = np.searchsorted(t, t, side="left")        # risk set of i = rows start[i]..n-1
    n_risk = (len(t) - start).astype(float)[:, None]
    out = np.empty(Z.shape[1])
    for lo in range(0, Z.shape[1], chunk):
        B = Zs[:, lo:lo + chunk].astype(np.float64)
        s1 = np.cumsum(B[::-1], axis=0)[::-1]
        s2 = np.cumsum(B[::-1] ** 2, axis=0)[::-1]
        mean = s1[start] / n_risk
        var = s2[start] / n_risk - mean ** 2
        u = ((B - mean) * e[:, None]).sum(axis=0)
        info = (var * e[:, None]).sum(axis=0)
        out[lo:lo + chunk] = u / np.sqrt(np.maximum(info, 1e-12))
    return out


@dataclass
class ExpressionTransformer:
    """Median-impute, winsorise and standardise a fixed set of genes using stored training statistics."""
    entrez_ids: list[str]
    columns: np.ndarray       # positions of these genes in the full gene-ordered matrix
    median: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    mean: np.ndarray
    std: np.ndarray

    def transform(self, X: np.ndarray, selected_only: bool = False) -> np.ndarray:
        """`X`: the full gene-ordered matrix, or (selected_only) just this transformer's genes in order."""
        X = np.asarray(X, dtype=np.float64)
        if not selected_only:
            X = X[:, self.columns]
        X = np.where(np.isnan(X), self.median, X)
        return (np.clip(X, self.lo, self.hi) - self.mean) / self.std


@dataclass
class ScreenResult:
    """Training-fitted statistics for ALL genes plus the |z| ranking."""
    entrez_ids: list[str]
    median: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    mean: np.ndarray
    std: np.ndarray
    z: np.ndarray
    ranking: np.ndarray          # gene indices, strongest |z| first (ties: lower index first)

    def top(self, k: int) -> ExpressionTransformer:
        idx = self.ranking[:k]
        return ExpressionTransformer(
            [self.entrez_ids[i] for i in idx], idx.copy(), self.median[idx], self.lo[idx], self.hi[idx], self.mean[idx], self.std[idx]
        )


def fit_screen(X: np.ndarray, event: np.ndarray, time: np.ndarray, entrez_ids: list[str]) -> ScreenResult:
    """Learn imputation values, winsorisation bounds, scaling and the screening ranking from `X` only."""
    X = np.asarray(X, dtype=np.float64)
    median = np.nan_to_num(np.nanmedian(X, axis=0), nan=0.0)   # all-missing gene: 0 (a z-score mean)
    filled = np.where(np.isnan(X), median, X)
    lo, hi = np.percentile(filled, WINSOR_PCT, axis=0)
    clipped = np.clip(filled, lo, hi)
    mean, std = clipped.mean(axis=0), clipped.std(axis=0)
    std = np.where(std > 0, std, 1.0)
    z = cox_score_z((clipped - mean) / std, event, time)
    ranking = np.argsort(-np.abs(z), kind="stable")
    return ScreenResult(list(entrez_ids), median, lo, hi, mean, std, z, ranking)
