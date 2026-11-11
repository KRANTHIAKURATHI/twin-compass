"""
Verification of the saved METABRIC OS/RFS artifacts against the REAL clinical files.

The other survival tests use small synthetic fixtures. These re-derive, from the actual
`data_clinical_patient.txt` / `data_clinical_sample.txt`, the things the artifacts claim:
  * the files are the ones the artifacts were trained on (SHA-256 in metadata.json);
  * target construction and exclusions give the recorded cohort sizes and event counts;
  * the seeded, event-stratified split reproduces the recorded train/test sizes and events;
  * the saved preprocessor was fitted on the TRAINING rows only (not on all rows);
  * the saved model's held-out and train C-index, recomputed here, equal metrics.json.

Nothing is trained or written. Data location: $ONCOTWIN_METABRIC_DIR, else K:/ (where the
project keeps the files). The module skips when the files are absent.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("sksurv")

from sklearn.model_selection import train_test_split  # noqa: E402

from app.ml.survival.data import NUMERIC_FEATURES, build_target, file_sha256, load_clinical  # noqa: E402
from app.ml.survival.evaluate import c_index  # noqa: E402
from app.ml.survival.predict import load_artifact  # noqa: E402

DATA_DIR = Path(os.environ.get("ONCOTWIN_METABRIC_DIR", "K:/"))
PATIENT, SAMPLE = DATA_DIR / "data_clinical_patient.txt", DATA_DIR / "data_clinical_sample.txt"
ARTIFACTS = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts"
ENDPOINTS = {"OS": ARTIFACTS / "survival", "RFS": ARTIFACTS / "survival_rfs"}

pytestmark = pytest.mark.skipif(not (PATIENT.exists() and SAMPLE.exists()), reason="METABRIC clinical files not found")


@pytest.fixture(scope="module")
def frame():
    return load_clinical(PATIENT, SAMPLE)


def _meta(endpoint):
    return json.loads((ENDPOINTS[endpoint] / "metadata.json").read_text(encoding="utf-8"))


def _split(frame, endpoint):
    meta = _meta(endpoint)
    X, event, time = build_target(frame, endpoint)
    cfg = meta["training_config"]
    idx_tr, idx_te = train_test_split(
        np.arange(len(X)), test_size=cfg["test_size"], random_state=cfg["seed"], stratify=event
    )
    return X, event, time, idx_tr, idx_te


@pytest.mark.parametrize("endpoint", ["OS", "RFS"])
def test_artifact_was_trained_on_these_exact_files(endpoint):
    recorded = _meta(endpoint)["dataset"]["files"]
    assert recorded[PATIENT.name]["sha256"] == file_sha256(PATIENT)
    assert recorded[SAMPLE.name]["sha256"] == file_sha256(SAMPLE)


def test_cohort_is_one_row_per_patient_and_exclusions_match_metadata(frame):
    assert frame["PATIENT_ID"].is_unique and len(frame) == _meta("RFS")["dataset"]["patients_in_files"]
    for endpoint in ("OS", "RFS"):
        X, event, time = build_target(frame, endpoint)
        split = _meta(endpoint)["split"]
        assert len(X) == split["n_total"] == len(event) == len(time)
        assert (time >= 0).all() and not np.isnan(time).any()  # only patients with a valid time and status are kept
        # nothing is imputed for dropped patients: they are simply excluded
        excluded = split.get("n_excluded_no_target", split.get("n_excluded_missing_os"))
        assert excluded == len(frame) - len(X)


@pytest.mark.parametrize("endpoint", ["OS", "RFS"])
def test_split_is_reproduced_disjoint_and_stratified(frame, endpoint):
    X, event, _, idx_tr, idx_te = _split(frame, endpoint)
    split = _meta(endpoint)["split"]
    assert not set(idx_tr) & set(idx_te) and len(idx_tr) + len(idx_te) == len(X)
    assert (len(idx_tr), len(idx_te)) == (split["n_train"], split["n_test"])
    assert (int(event[idx_tr].sum()), int(event[idx_te].sum())) == (split["events_train"], split["events_test"])
    assert abs(event[idx_tr].mean() - event[idx_te].mean()) < 0.01  # event-stratified
    # censoring is real: both splits contain right-censored patients
    assert 0 < event[idx_tr].mean() < 1 and 0 < event[idx_te].mean() < 1


@pytest.mark.parametrize("endpoint", ["OS", "RFS"])
def test_saved_preprocessor_was_fitted_on_training_rows_only(frame, endpoint):
    X, _, _, idx_tr, idx_te = _split(frame, endpoint)
    pre = load_artifact(ENDPOINTS[endpoint]).preprocessor
    medians = pre.named_transformers_["num"].named_steps["impute"].statistics_
    train_medians = X.iloc[idx_tr][NUMERIC_FEATURES].median().to_numpy(dtype=float)
    all_medians = X[NUMERIC_FEATURES].median().to_numpy(dtype=float)
    np.testing.assert_allclose(medians, train_medians)
    # the check is meaningful only if "fitted on everything" would have given different numbers
    assert not np.allclose(train_medians, all_medians) or not np.allclose(
        X.iloc[idx_tr][NUMERIC_FEATURES].mean().to_numpy(dtype=float), X[NUMERIC_FEATURES].mean().to_numpy(dtype=float)
    )
    scaler = pre.named_transformers_["num"].named_steps["scale"]
    train_imputed = X.iloc[idx_tr][NUMERIC_FEATURES].fillna(pd.Series(train_medians, index=NUMERIC_FEATURES))
    np.testing.assert_allclose(scaler.mean_, train_imputed.mean().to_numpy(dtype=float))
    # categories seen by the encoder come from the training rows (a test-only level must not appear)
    train_levels = set(X.iloc[idx_tr]["CLAUDIN_SUBTYPE"].dropna().astype(str)) | {"Unknown"}
    cat = pre.named_transformers_["cat"].named_steps["onehot"]
    encoder_levels = set(cat.categories_[pre.transformers_[1][2].index("CLAUDIN_SUBTYPE")])
    assert encoder_levels == train_levels


@pytest.mark.parametrize("endpoint", ["OS", "RFS"])
def test_recomputed_c_index_matches_saved_metrics(frame, endpoint):
    X, event, time, idx_tr, idx_te = _split(frame, endpoint)
    art = load_artifact(ENDPOINTS[endpoint])
    saved = json.loads((ENDPOINTS[endpoint] / "metrics.json").read_text(encoding="utf-8"))["candidates"][
        _meta(endpoint)["selected_model"]
    ]
    risk_te = art.model.predict(art.preprocessor.transform(X.iloc[idx_te]))
    risk_tr = art.model.predict(art.preprocessor.transform(X.iloc[idx_tr]))
    test_c, train_c = c_index(event[idx_te], time[idx_te], risk_te), c_index(event[idx_tr], time[idx_tr], risk_tr)
    assert test_c == pytest.approx(saved["test_c_index"], abs=1e-9)
    assert train_c == pytest.approx(saved["train_c_index"], abs=1e-9)
    # honest, modest discrimination for a clinical-only model; far above chance, nowhere near perfect
    assert 0.6 < test_c < 0.8


@pytest.mark.parametrize("endpoint", ["OS", "RFS"])
def test_metadata_labels_the_model_as_research_and_not_treatment_response(endpoint):
    meta = _meta(endpoint)
    assert "not clinically validated" in meta["status"].lower()
    limitations = " ".join(meta["limitations"]).lower()
    assert "not a treatment-response model" in limitations and "no external validation" in limitations
