"""METABRIC relapse-free-survival research model (same pipeline, RFS endpoint).

Synthetic cBioPortal-layout files only; helpers are shared with the OS tests.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("sksurv")

from app.ml.survival import MODEL_NAME, RESEARCH_STATEMENT, RFS_MODEL_NAME  # noqa: E402
from app.ml.survival.data import FEATURES, build_target, load_clinical  # noqa: E402
from app.ml.survival.predict import load_artifact  # noqa: E402
from app.ml.survival.preprocess import build_preprocessor  # noqa: E402
from app.ml.survival.train import ARTIFACT_DIR, RFS_ARTIFACT_DIR, train  # noqa: E402
from tests.test_survival_model import PATIENT_COLS, SAMPLE_COLS, _cohort, _write  # noqa: E402


def _rfs_cohort(n=160, seed=1):
    """OS and RFS deliberately disagree so a test fails if the wrong endpoint is read."""
    patients, samples = _cohort(n, seed)
    rng = np.random.default_rng(seed)
    for p in patients:
        recurred = rng.random() < 0.4
        p["RFS_STATUS"] = "1:Recurred" if recurred else "0:Not Recurred"
        p["RFS_MONTHS"] = round(float(rng.exponential(80)), 2)
    return patients, samples


def _files(tmp_path, patients, samples):
    pf, sf = tmp_path / "patient.txt", tmp_path / "sample.txt"
    _write(pf, PATIENT_COLS, patients)
    _write(sf, SAMPLE_COLS, samples)
    return pf, sf


def test_rfs_target_uses_rfs_columns_and_event_coding(tmp_path):
    patients, samples = _rfs_cohort(6)
    patients[0].update(RFS_STATUS="1:Recurred", RFS_MONTHS="12.5", OS_STATUS="0:LIVING", OS_MONTHS="99")
    patients[1].update(RFS_STATUS="0:Not Recurred", RFS_MONTHS="30", OS_STATUS="1:DECEASED", OS_MONTHS="5")
    frame = load_clinical(*_files(tmp_path, patients, samples))
    _, event, time = build_target(frame, "RFS")
    assert event.dtype == bool and time.dtype == float
    assert event[:2].tolist() == [True, False] and time[:2].tolist() == [12.5, 30.0]  # not the OS values
    _, os_event, os_time = build_target(frame, "OS")
    assert os_event[:2].tolist() == [False, True] and os_time[:2].tolist() == [99.0, 5.0]


def test_rfs_rows_without_status_or_valid_time_are_dropped_not_imputed(tmp_path):
    patients, samples = _rfs_cohort(6)
    patients[0].update(RFS_STATUS="NA")  # the real file uses NA for 21 patients
    patients[1].update(RFS_STATUS="")
    patients[2].update(RFS_MONTHS="NA")
    patients[3].update(RFS_MONTHS="-3")
    X, event, time = build_target(load_clinical(*_files(tmp_path, patients, samples)), "RFS")
    assert len(X) == len(event) == len(time) == 2  # patients 4 and 5
    assert np.isfinite(time).all() and (time >= 0).all()


def test_rfs_uses_the_same_leakage_safe_features_and_train_only_preprocessing(tmp_path):
    for banned in ("NPI", "OS_MONTHS", "OS_STATUS", "RFS_MONTHS", "RFS_STATUS", "VITAL_STATUS", "ER_IHC", "HER2_SNP6"):
        assert banned not in FEATURES
    patients, samples = _rfs_cohort()
    X, _, _ = build_target(load_clinical(*_files(tmp_path, patients, samples)), "RFS")
    assert list(X.columns) == FEATURES
    train_rows, test_rows = X.iloc[:100], X.iloc[100:].copy()
    test_rows["AGE_AT_DIAGNOSIS"] = 1000.0
    pre = build_preprocessor().fit(train_rows)
    assert pre.named_transformers_["num"].named_steps["scale"].mean_[0] == pytest.approx(
        train_rows["AGE_AT_DIAGNOSIS"].mean()
    )
    assert not pre.transform(test_rows).isna().any().any()


@pytest.fixture(scope="module")
def rfs_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("rfs")
    patients, samples = _rfs_cohort()
    pf, sf = _files(d, patients, samples)
    out = d / "artifacts"
    train(
        pf, sf, out, endpoint="RFS",
        config={"cv_folds": 3, "cox_alpha_grid": [1.0, 10.0],
                "rsf": {"n_estimators": 10, "min_samples_leaf": 10, "max_features": "sqrt"}},
    )
    return out


def test_rfs_tiny_training_reports_both_candidates(rfs_dir):
    report = json.loads((rfs_dir / "metrics.json").read_text())
    assert report["model_name"] == RFS_MODEL_NAME and set(report["candidates"]) == {"cox", "rsf"}
    split = report["split"]
    assert split["endpoint"] == "RFS" and split["n_train"] + split["n_test"] == split["n_total"]
    assert 0 < split["censoring_rate_train"] < 1 and split["events_train"] > 0
    assert split["n_features_raw"] == len(FEATURES) < split["n_features_after_preprocessing"]
    for m in report["candidates"].values():
        assert 0.0 < m["train_c_index"] <= 1.0 and 0.0 < m["test_c_index"] <= 1.0


def test_rfs_metadata_states_research_status_and_endpoint(rfs_dir):
    meta = json.loads((rfs_dir / "metadata.json").read_text())
    assert meta["model_name"] == "METABRIC relapse-free survival model"
    assert meta["status"] == "Research model — not clinically validated" == RESEARCH_STATEMENT
    assert meta["endpoint"] == "RFS" and "RFS_STATUS" in meta["target"]["event"]
    assert meta["feature_names"] and meta["selected_model"] in {"cox", "rsf"}
    assert any("treatment-response" in s for s in meta["limitations"])


def test_rfs_artifact_loads_and_predicts_expected_shape(rfs_dir):
    artifact = load_artifact(rfs_dir)
    results = artifact.predict([{"AGE_AT_DIAGNOSIS": 50, "GRADE": 3, "ER_STATUS": "Negative"}, {}])
    assert len(results) == 2
    for r in results:
        assert isinstance(r["risk_score"], float) and np.isfinite(r["risk_score"])
        assert set(r["survival_probability"]) == {"60_months", "120_months"}
        assert r["model"] == RFS_MODEL_NAME and r["status"] == RESEARCH_STATEMENT


def test_rfs_and_os_artifacts_live_in_separate_directories():
    assert RFS_ARTIFACT_DIR != ARTIFACT_DIR and RFS_ARTIFACT_DIR.name == "survival_rfs"
    assert RFS_MODEL_NAME != MODEL_NAME
