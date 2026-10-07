"""Load GSE163882: TPM matrix + GEO series-matrix metadata, build the pCR/RD target and patient groups.

The datasets live outside the repository and are only read.
"""
from __future__ import annotations

import gzip
import io
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CLINICAL_FEATURES = ["age", "er", "pr", "her2", "grade", "stage"]
LABELS = {"pCR": 1, "RD": 0}
_KEYS = {
    "response to nac": "response",
    "age": "age",
    "estrogen receptor status": "er",
    "progesterone receptor status": "pr",
    "her2 receptor status": "her2",
    "tumor grage": "grade",      # (sic) spelling used by the GEO record
    "tumor grade": "grade",
    "breast cancer stage": "stage",
}
_SITES = {"MT group": "MT", "Hartford": "Hartford", "UConn": "UConn"}


def _open(path: Path):
    return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8") if str(path).endswith(".gz") else open(path, encoding="utf-8")


def _cells(line: str) -> list[str]:
    return [c.strip().strip('"') for c in line.rstrip("\n").split("\t")[1:]]


def parse_series_matrix(path: str | Path) -> pd.DataFrame:
    """One row per GEO sample: sample_id (BA#####), accession, specimen_label, site and the raw clinical fields.

    Fields are read exactly as written in the `!Sample_characteristics_ch1` rows ("key: value"); nothing is derived.
    """
    path = Path(path)
    accession: list[str] = []
    titles: list[str] = []
    sources: list[str] = []
    fields: dict[str, list[str]] = {}
    with _open(path) as fh:
        for line in fh:
            if line.startswith("!Sample_geo_accession"):
                accession = _cells(line)
            elif line.startswith("!Sample_title"):
                titles = _cells(line)
            elif line.startswith("!Sample_source_name_ch1"):
                sources = _cells(line)
            elif line.startswith("!Sample_characteristics_ch1"):
                cells = _cells(line)
                key = cells[0].split(":", 1)[0].strip().lower()
                if key in _KEYS:
                    fields[_KEYS[key]] = [c.split(":", 1)[1].strip() if ":" in c else "" for c in cells]
    if not accession or not titles or "response" not in fields:
        raise ValueError("series matrix lacks accession/title/response rows")
    sample_id, label = [], []
    for t in titles:
        head, _, rest = t.partition(":")
        sample_id.append(head.strip())
        label.append(rest.strip())
    frame = pd.DataFrame({"accession": accession, "sample_id": sample_id, "specimen_label": label})
    frame["site"] = [next((v for k, v in _SITES.items() if k in s), "unknown") for s in sources] if sources else "unknown"
    for col in ["response", *CLINICAL_FEATURES]:
        frame[col] = fields.get(col, [""] * len(frame))
    return frame


def read_expression(path: str | Path) -> tuple[np.ndarray, list[str], list[str], list[str]]:
    """TPM matrix as (samples x genes) float64, sample ids, Ensembl ids (canonical key), annotation (display only)."""
    df = pd.read_csv(path, index_col=0)
    if "annotation" in df.columns:
        annotation = df.pop("annotation").astype(str).tolist()
    else:
        annotation = [""] * len(df)
    if df.index.duplicated().any() or df.columns.duplicated().any():
        raise ValueError("duplicate Ensembl or sample ids")
    values = df.to_numpy(dtype=np.float64).T
    if np.isnan(values).any() or (values < 0).any():
        raise ValueError("expression must be non-negative TPM without missing values")
    return np.ascontiguousarray(values), df.columns.astype(str).tolist(), df.index.astype(str).tolist(), annotation


def build_target(response: pd.Series) -> pd.Series:
    """pCR=1, RD=0 from the GEO `response to nac` field ONLY. Anything else is NaN (never inferred)."""
    return response.astype("string").str.strip().map(LABELS).astype("Float64")


def _tokens(label: str) -> list[str]:
    return [t for t in re.split(r"\s*[/,;]\s*", label.strip().lower()) if t]


def assign_patient_groups(labels: list[str]) -> list[str]:
    """Deterministic conservative patient grouping from the specimen label.

    Patient identity cannot be proven from GEO. Rule: samples whose specimen
    labels are identical, OR that share any accession-style token (labels such
    as "S16-3384/S16-8771" are split on "/", ",", ";"), are the same group
    (union-find, connected components). Each group id is `grp:` + the
    lexicographically smallest member label (never an index), so it does not
    depend on row order. Singletons keep their own label.
    """
    n = len(labels)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner: dict[str, int] = {}
    for i, lab in enumerate(labels):
        for tok in _tokens(lab) or [f"__row{i}"]:
            if tok in owner:
                a, b = find(i), find(owner[tok])
                if a != b:
                    parent[max(a, b)] = min(a, b)
            else:
                owner[tok] = i
    comp: dict[int, list[str]] = {}
    for i, lab in enumerate(labels):
        comp.setdefault(find(i), []).append(" ".join(lab.lower().split()))
    return ["grp:" + min(comp[find(i)]) for i in range(n)]


@dataclass
class Cohort:
    sample_ids: list[str]
    tpm: np.ndarray                 # samples x genes, raw TPM
    ensembl_ids: list[str]
    annotation: list[str]
    clinical: pd.DataFrame          # CLINICAL_FEATURES (numeric, NaN = missing), same row order
    y: np.ndarray                   # 1 = pCR, 0 = RD
    groups: np.ndarray              # patient-group ids
    site: np.ndarray
    provenance: dict[str, object]


def _number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype("string").str.strip().replace({"NA": pd.NA, "": pd.NA, "N/A": pd.NA}), errors="coerce").astype(float)


def _binary(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.upper().map({"P": 1.0, "N": 0.0, "POSITIVE": 1.0, "NEGATIVE": 0.0}).astype(float)


def clinical_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Numeric clinical block. Out-of-range grade (0) / stage values become missing; ER/PR/HER2 P=1, N=0."""
    out = pd.DataFrame(index=raw.index)
    out["age"] = _number(raw["age"])
    for c in ("er", "pr", "her2"):
        out[c] = _binary(raw[c])
    grade, stage = _number(raw["grade"]), _number(raw["stage"])
    out["grade"] = grade.where(grade.between(1, 3))
    out["stage"] = stage.where(stage.between(1, 4))
    return out[CLINICAL_FEATURES]


def build_cohort(meta: pd.DataFrame, tpm: np.ndarray, sample_ids: list[str], ensembl_ids: list[str], annotation: list[str]) -> Cohort:
    """Join metadata and expression by sample id (never by position); keep rows with an explicit pCR/RD label."""
    meta = meta.set_index("sample_id", drop=False)
    if meta.index.duplicated().any():
        raise ValueError("duplicate sample ids in metadata")
    common = [s for s in sample_ids if s in meta.index]
    if not common:
        raise ValueError("no sample ids shared between expression and metadata")
    pos = {s: i for i, s in enumerate(sample_ids)}
    m = meta.loc[common]
    y = build_target(m["response"])
    keep = y.notna().to_numpy()
    m, common, y = m.loc[keep], [s for s, k in zip(common, keep) if k], y[keep].astype(int).to_numpy()
    groups = np.array(assign_patient_groups(m["specimen_label"].tolist()))
    # replicate samples must agree on the label, otherwise class-stratified grouping is ill-defined
    for g in np.unique(groups):
        if len(set(y[groups == g])) > 1:
            raise ValueError(f"group {g} mixes pCR and RD")
    clin = clinical_frame(m).reset_index(drop=True)
    return Cohort(
        common, np.ascontiguousarray(tpm[[pos[s] for s in common]]), list(ensembl_ids), list(annotation),
        clin, y, groups, m["site"].to_numpy(),
        {
            "samples_in_expression": len(sample_ids),
            "samples_in_metadata": int(len(meta)),
            "samples_without_explicit_label_dropped": int((~keep).sum()),
            "samples": len(common),
            "patients": int(len(np.unique(groups))),
            "pcr": int(y.sum()),
            "rd": int((1 - y).sum()),
            "pcr_patients": int(len({g for g, v in zip(groups, y) if v == 1})),
            "rd_patients": int(len({g for g, v in zip(groups, y) if v == 0})),
            "missing_expression_values": 0,
            "missing_clinical": {c: int(clin[c].isna().sum()) for c in CLINICAL_FEATURES},
        },
    )


def load_cohort(expression_path: str | Path, series_matrix_path: str | Path) -> Cohort:
    tpm, ids, genes, ann = read_expression(expression_path)
    return build_cohort(parse_series_matrix(series_matrix_path), tpm, ids, genes, ann)
