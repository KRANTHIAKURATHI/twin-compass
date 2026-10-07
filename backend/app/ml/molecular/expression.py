"""Stream the cBioPortal expression matrix and align it with the clinical cohort."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.survival.data import ENDPOINTS, build_target

NA_TOKENS = {"", "na", "n/a", "#n/a", "nan", "null", "none"}


@dataclass
class ExpressionMatrix:
    values: np.ndarray            # samples x genes, float32, NaN = missing
    sample_ids: list[str]
    entrez_ids: list[str]         # canonical, unique, in file order
    hugo_symbols: list[str]
    provenance: dict[str, object]


def _row_values(cells: list[str]) -> np.ndarray:
    try:
        return np.asarray(cells, dtype=np.float32)  # fast path: every cell numeric
    except ValueError:
        return np.asarray([np.nan if c.strip().lower() in NA_TOKENS else float(c) for c in cells], dtype=np.float32)


def read_expression(path: str | Path) -> ExpressionMatrix:
    """Read the matrix one row at a time (the file is never loaded as text).

    Rows are keyed by Entrez ID. Where several rows share an Entrez ID the FIRST
    row in file order is kept and the others are dropped. The rule uses no data
    values (no averaging, no variance, no outcome), so it cannot leak; the
    alternative rows are counted in the provenance record.
    """
    path = Path(path)
    seen: set[str] = set()
    rows: list[np.ndarray] = []
    entrez: list[str] = []
    hugo: list[str] = []
    n_rows = n_dup = n_no_entrez = 0
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        if header[:2] != ["Hugo_Symbol", "Entrez_Gene_Id"]:
            raise ValueError("expected 'Hugo_Symbol' and 'Entrez_Gene_Id' as the first two columns")
        samples = header[2:]
        if len(set(samples)) != len(samples):
            raise ValueError("duplicate expression sample ids")
        for line in fh:
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            n_rows += 1
            if len(parts) != len(header):
                raise ValueError(f"row {n_rows} has {len(parts)} cells, expected {len(header)}")
            gene = parts[1].strip()
            if gene.lower() in NA_TOKENS:
                n_no_entrez += 1
                continue
            if gene in seen:
                n_dup += 1
                continue
            seen.add(gene)
            entrez.append(gene)
            hugo.append(parts[0])
            rows.append(_row_values(parts[2:]))
    values = np.ascontiguousarray(np.vstack(rows).T)  # samples x genes
    return ExpressionMatrix(
        values, samples, entrez, hugo,
        {
            "file": path.name,
            "rows_in_file": n_rows,
            "genes_kept": len(entrez),
            "duplicate_entrez_rows_dropped": n_dup,
            "rows_without_entrez_dropped": n_no_entrez,
            "duplicate_rule": "first row in file order kept per Entrez ID; no averaging; uses no data values",
            "missing_values": int(np.isnan(values).sum()),
            "samples": len(samples),
        },
    )


def _valid_target(frame: pd.DataFrame, endpoint: str) -> pd.Series:
    """Row mask with the exact validity rule of `build_target` (status 0/1, finite non-negative time)."""
    event_column, time_column = ENDPOINTS[endpoint]
    status = frame[event_column].astype("string").str.split(":").str[0]
    time = pd.to_numeric(frame[time_column], errors="coerce")
    return (status.isin(["0", "1"]) & time.notna() & (time >= 0)).fillna(False).to_numpy(dtype=bool)


@dataclass
class Cohort:
    clinical: pd.DataFrame   # raw clinical FEATURES, one row per patient
    expression: np.ndarray   # same row order, genes in `entrez_ids` order
    event: np.ndarray
    time: np.ndarray
    patient_ids: list[str]
    entrez_ids: list[str]
    hugo_symbols: list[str]


def build_cohort(frame: pd.DataFrame, expr: ExpressionMatrix, endpoint: str) -> Cohort:
    """Patients with a valid endpoint target AND an expression sample.

    Samples map to patients through the clinical sample file (`frame` is the
    patient+sample join). Targets are never imputed: rows without one are
    dropped by `build_target`.
    """
    frame = frame[frame["SAMPLE_ID"].isin(set(expr.sample_ids))]
    X, event, time = build_target(frame, endpoint)       # drops rows without a valid target and resets the index
    kept = frame.loc[_valid_target(frame, endpoint)]      # the same rows, with their ids
    if len(kept) != len(X):
        raise AssertionError("target mask out of step with build_target")
    if kept["PATIENT_ID"].duplicated().any():
        raise ValueError("more than one expression sample per patient")
    position = {s: i for i, s in enumerate(expr.sample_ids)}
    rows = [position[s] for s in kept["SAMPLE_ID"]]
    return Cohort(
        X, expr.values[rows], event, time,
        kept["PATIENT_ID"].tolist(), expr.entrez_ids, expr.hugo_symbols,
    )
