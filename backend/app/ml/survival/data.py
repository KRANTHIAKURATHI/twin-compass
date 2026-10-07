"""Parse the cBioPortal METABRIC clinical files and build the survival target."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

# cBioPortal spells "missing" many ways; all of them mean "not recorded", never
# a clinical value. Matching is case-insensitive on the stripped string.
MISSING_TOKENS = {"", "na", "n/a", "#n/a", "nan", "null", "none", "unknown", "not available", "undef", "nd"}

# Collapses spelling variants only (the files contain "Positve" and "Present"
# style values); anything unrecognised is kept as-is rather than guessed.
CANONICAL = {
    "yes": "Yes", "no": "No",
    "positive": "Positive", "positve": "Positive", "present": "Positive",
    "negative": "Negative", "absent": "Negative",
}

# Primary-model features, by the column name in the METABRIC files. NPI is
# deliberately absent (see README: it is computed from tumour size, grade and
# lymph-node status, which are already features). OS_*, RFS_* and VITAL_STATUS
# are outcomes and are never features. ER_IHC / HER2_SNP6 duplicate the
# sample-level ER_STATUS / HER2_STATUS and are left out for the same reason.
NUMERIC_FEATURES = [
    "AGE_AT_DIAGNOSIS", "LYMPH_NODES_EXAMINED_POSITIVE", "TUMOR_SIZE", "GRADE", "TUMOR_STAGE",
]
CATEGORICAL_FEATURES = [
    "INFERRED_MENOPAUSAL_STATE", "CLAUDIN_SUBTYPE", "HISTOLOGICAL_SUBTYPE",
    "CHEMOTHERAPY", "HORMONE_THERAPY", "RADIO_THERAPY", "BREAST_SURGERY",
    "ER_STATUS", "PR_STATUS", "HER2_STATUS",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
# Endpoint -> (event column, time column). Both are "<0|1>:<label>" status text
# and months; the feature set is identical for every endpoint.
ENDPOINTS = {"OS": ("OS_STATUS", "OS_MONTHS"), "RFS": ("RFS_STATUS", "RFS_MONTHS")}


def normalize_value(value: object) -> object:
    """A cleaned cell: NaN for any missing token, a canonical spelling for
    yes/no and positive/negative values, otherwise the stripped text."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    text = str(value).strip()
    key = text.lower()
    if key in MISSING_TOKENS:
        return np.nan
    return CANONICAL.get(key, text)


def read_cbioportal(path: str | Path) -> pd.DataFrame:
    """Read a cBioPortal clinical file: '#' metadata lines, then a header row."""
    frame = pd.read_csv(path, sep="\t", comment="#", dtype=str, keep_default_na=False)
    return frame.apply(lambda col: col.map(normalize_value))


def load_clinical(patient_path: str | Path, sample_path: str | Path) -> pd.DataFrame:
    """Patient and sample files joined one-to-one on PATIENT_ID.

    The join fails loudly on duplicate ids or unmatched rows instead of
    silently multiplying or dropping patients.
    """
    patients, samples = read_cbioportal(patient_path), read_cbioportal(sample_path)
    for name, frame, key in (("patient", patients, "PATIENT_ID"), ("sample", samples, "PATIENT_ID")):
        if frame[key].isna().any() or frame[key].duplicated().any():
            raise ValueError(f"{name} file has missing or duplicate {key}")
    if samples["SAMPLE_ID"].duplicated().any():
        raise ValueError("sample file has duplicate SAMPLE_ID")
    if set(patients["PATIENT_ID"]) != set(samples["PATIENT_ID"]):
        raise ValueError("patient and sample files do not cover the same patients")
    return patients.merge(samples, on="PATIENT_ID", how="inner", validate="one_to_one")


def build_target(frame: pd.DataFrame, endpoint: str = "OS") -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Features, event indicator and time in months for an endpoint.

    OS: event = deceased. RFS: event = recurred (the cohort's RFS definition
    also counts disease-specific death). "1:..." is the event, "0:..." is
    right-censored. Patients whose status or time is missing, or whose time is
    negative, have no valid target and are dropped; nothing is imputed for them.
    """
    event_column, time_column = ENDPOINTS[endpoint]
    status = frame[event_column].astype("string").str.split(":").str[0]
    time = pd.to_numeric(frame[time_column], errors="coerce")
    valid = status.isin(["0", "1"]) & time.notna() & (time >= 0)
    kept = frame.loc[valid]
    event = (status[valid] == "1").to_numpy(dtype=bool)
    months = time[valid].to_numpy(dtype=float)
    features = kept[FEATURES].copy()
    for col in NUMERIC_FEATURES:
        features[col] = pd.to_numeric(features[col], errors="coerce")
    return features.reset_index(drop=True), event, months


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
