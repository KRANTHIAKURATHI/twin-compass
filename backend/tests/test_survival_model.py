"""METABRIC survival research model: parsing, joining, target, preprocessing, artifact.

Uses small synthetic files in the cBioPortal layout (a few '#' metadata lines,
then a tab-separated header); nothing here reads the real cohort. The training
test fits a tiny model, so it stays fast.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("sksurv")

from app.ml.survival import MODEL_NAME, RESEARCH_STATEMENT  # noqa: E402
from app.ml.survival.data import (  # noqa: E402
    CATEGORICAL_FEATURES,
    FEATURES,
    NUMERIC_FEATURES,
    build_target,
    load_clinical,
    normalize_value,
    read_cbioportal,
)
from app.ml.survival.predict import load_artifact  # noqa: E402
from app.ml.survival.preprocess import UNKNOWN, build_preprocessor  # noqa: E402
from app.ml.survival.train import train  # noqa: E402

PATIENT_COLS = [
    "PATIENT_ID", "LYMPH_NODES_EXAMINED_POSITIVE", "NPI", "CHEMOTHERAPY", "HORMONE_THERAPY",
    "INFERRED_MENOPAUSAL_STATE", "AGE_AT_DIAGNOSIS", "OS_MONTHS", "OS_STATUS", "CLAUDIN_SUBTYPE",
    "VITAL_STATUS", "RADIO_THERAPY", "HISTOLOGICAL_SUBTYPE", "BREAST_SURGERY", "RFS_MONTHS", "RFS_STATUS",
]
SAMPLE_COLS = ["PATIENT_ID", "SAMPLE_ID", "ER_STATUS", "HER2_STATUS", "GRADE", "PR_STATUS", "TUMOR_SIZE", "TUMOR_STAGE"]


def _write(path, columns, rows):
    lines = ["#" + "\t".join(columns), "#" + "\t".join(["desc"] * len(columns)), "#" + "\t".join(["STRING"] * len(columns))]
    lines.append("\t".join(columns))
    lines += ["\t".join(str(r.get(c, "")) for c in columns) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cohort(n=160, seed=0):
    rng = np.random.default_rng(seed)
    patients, samples = [], []
    for i in range(n):
        pid = f"MB-{i:04d}"
        nodes, size, grade = int(rng.integers(0, 8)), int(rng.integers(5, 60)), int(rng.integers(1, 4))
        hazard = 0.15 * nodes + 0.02 * size + 0.3 * grade
        t = float(rng.exponential(120 / (1 + hazard)))
        dead = rng.random() < 0.6
        patients.append({
            "PATIENT_ID": pid, "LYMPH_NODES_EXAMINED_POSITIVE": nodes, "NPI": 3.5,
            "CHEMOTHERAPY": rng.choice(["YES", "NO"]), "HORMONE_THERAPY": rng.choice(["YES", "NO", ""]),
            "INFERRED_MENOPAUSAL_STATE": rng.choice(["Pre", "Post"]), "AGE_AT_DIAGNOSIS": round(40 + rng.random() * 40, 1),
            "OS_MONTHS": round(t, 2), "OS_STATUS": "1:DECEASED" if dead else "0:LIVING",
            "CLAUDIN_SUBTYPE": rng.choice(["LumA", "LumB", "Basal"]), "VITAL_STATUS": "Died of Disease" if dead else "Living",
            "RADIO_THERAPY": rng.choice(["YES", "NO"]), "HISTOLOGICAL_SUBTYPE": rng.choice(["Ductal/NST", "Lobular"]),
            "BREAST_SURGERY": rng.choice(["MASTECTOMY", "BREAST CONSERVING"]), "RFS_MONTHS": 10, "RFS_STATUS": "0:Not Recurred",
        })
        samples.append({
            "PATIENT_ID": pid, "SAMPLE_ID": pid, "ER_STATUS": rng.choice(["Positive", "Negative"]),
            "HER2_STATUS": rng.choice(["Positive", "Negative"]), "GRADE": grade, "PR_STATUS": rng.choice(["Positive", "Negative"]),
            "TUMOR_SIZE": size, "TUMOR_STAGE": rng.choice(["1", "2", "NA"]),
        })
    return patients, samples


@pytest.fixture()
def files(tmp_path):
    patients, samples = _cohort()
    pf, sf = tmp_path / "patient.txt", tmp_path / "sample.txt"
    _write(pf, PATIENT_COLS, patients)
    _write(sf, SAMPLE_COLS, samples)
    return pf, sf


def test_parser_skips_metadata_lines_and_normalizes_cells(tmp_path):
    p = tmp_path / "s.txt"
    _write(p, SAMPLE_COLS, [{"PATIENT_ID": "A", "SAMPLE_ID": "A", "ER_STATUS": "Positve", "GRADE": "NA", "PR_STATUS": " #N/A "}])
    frame = read_cbioportal(p)
    assert list(frame.columns) == SAMPLE_COLS and len(frame) == 1
    row = frame.iloc[0]
    assert row["ER_STATUS"] == "Positive" and pd.isna(row["GRADE"]) and pd.isna(row["PR_STATUS"])


@pytest.mark.parametrize("raw", ["", " ", "NA", "N/A", "#N/A", "Not Available", "UNDEF", "nan", None, float("nan")])
def test_missing_tokens_become_nan(raw):
    assert pd.isna(normalize_value(raw))


def test_value_normalization_does_not_invent_values():
    assert normalize_value("YES") == "Yes" and normalize_value("no") == "No"
    assert normalize_value("Present") == "Positive" and normalize_value("Absent") == "Negative"
    assert normalize_value("GAIN") == "GAIN"  # unrecognised text is kept, not mapped to a clinical value
    assert normalize_value("0") == "0"


def test_join_is_one_to_one_on_patient_id(files):
    frame = load_clinical(*files)
    assert len(frame) == 160 and frame["PATIENT_ID"].is_unique
    assert {"OS_MONTHS", "ER_STATUS", "TUMOR_SIZE"} <= set(frame.columns)


def test_join_rejects_duplicate_and_unmatched_ids(tmp_path):
    patients, samples = _cohort(5)
    pf, sf = tmp_path / "p.txt", tmp_path / "s.txt"
    _write(pf, PATIENT_COLS, patients + [patients[0]])
    _write(sf, SAMPLE_COLS, samples)
    with pytest.raises(ValueError, match="duplicate"):
        load_clinical(pf, sf)
    _write(pf, PATIENT_COLS, patients)
    _write(sf, SAMPLE_COLS, samples[:-1])
    with pytest.raises(ValueError, match="same patients"):
        load_clinical(pf, sf)


def test_target_is_event_and_time_and_drops_unusable_rows(tmp_path):
    patients, samples = _cohort(6)
    patients[0].update(OS_STATUS="1:DECEASED", OS_MONTHS="12.5")
    patients[1].update(OS_STATUS="0:LIVING", OS_MONTHS="30")
    patients[2].update(OS_STATUS="")           # no status: no target
    patients[3].update(OS_MONTHS="NA")         # no time: no target
    patients[4].update(OS_MONTHS="-1")         # impossible time
    pf, sf = tmp_path / "p.txt", tmp_path / "s.txt"
    _write(pf, PATIENT_COLS, patients)
    _write(sf, SAMPLE_COLS, samples)
    X, event, time = build_target(load_clinical(pf, sf))
    assert event.dtype == bool and time.dtype == float
    assert len(X) == len(event) == len(time) == 3  # patients 0, 1 and 5
    assert event.tolist()[:2] == [True, False] and time.tolist()[:2] == [12.5, 30.0]


def test_feature_set_excludes_derived_and_outcome_columns():
    assert set(FEATURES) == set(NUMERIC_FEATURES + CATEGORICAL_FEATURES)
    for banned in ("NPI", "OS_MONTHS", "OS_STATUS", "RFS_MONTHS", "RFS_STATUS", "VITAL_STATUS"):
        assert banned not in FEATURES


def test_preprocessing_is_fitted_on_training_rows_only(files):
    X, _, _ = build_target(load_clinical(*files))
    train_rows, test_rows = X.iloc[:100].copy(), X.iloc[100:].copy()
    test_rows["AGE_AT_DIAGNOSIS"] = 1000.0               # would shift a median/scale if test leaked in
    test_rows.loc[test_rows.index[0], "CLAUDIN_SUBTYPE"] = "Brand-new level"
    pre = build_preprocessor().fit(train_rows)

    num = pre.named_transformers_["num"]
    assert num.named_steps["impute"].statistics_[0] == pytest.approx(train_rows["AGE_AT_DIAGNOSIS"].median())
    assert num.named_steps["scale"].mean_[0] == pytest.approx(train_rows["AGE_AT_DIAGNOSIS"].mean())

    out = pre.transform(test_rows)  # unseen level must not raise
    names = list(pre.get_feature_names_out())
    assert not out.isna().any().any() and len(names) == out.shape[1]
    claudin_cols = [c for c in names if c.startswith("CLAUDIN_SUBTYPE_")]
    assert out.iloc[0][claudin_cols].sum() == 0
    assert any(c.endswith(f"_{UNKNOWN}") for c in names)  # explicit Unknown level exists (missing hormone therapy)


@pytest.fixture(scope="module")
def artifact_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("survival")
    patients, samples = _cohort()
    pf, sf = d / "patient.txt", d / "sample.txt"
    _write(pf, PATIENT_COLS, patients)
    _write(sf, SAMPLE_COLS, samples)
    out = d / "artifacts"
    train(pf, sf, out, config={"cv_folds": 3, "cox_alpha_grid": [1.0, 10.0],
                               "rsf": {"n_estimators": 10, "min_samples_leaf": 10, "max_features": "sqrt"}})
    return out


def test_training_writes_all_artifacts_and_both_candidates(artifact_dir):
    for name in ("model.joblib", "metadata.json", "metrics.json"):
        assert (artifact_dir / name).exists()
    report = json.loads((artifact_dir / "metrics.json").read_text())
    assert set(report["candidates"]) == {"cox", "rsf"}
    for m in report["candidates"].values():
        assert 0.0 < m["train_c_index"] <= 1.0 and 0.0 < m["test_c_index"] <= 1.0
    split = report["split"]
    assert split["n_train"] + split["n_test"] == split["n_total"]
    assert split["events_train"] > 0 and 0 < split["censoring_rate_train"] < 1
    assert split["n_features_after_preprocessing"] > split["n_features_raw"]


def test_metadata_carries_research_statement_and_provenance(artifact_dir):
    meta = json.loads((artifact_dir / "metadata.json").read_text())
    assert meta["model_name"] == MODEL_NAME == "METABRIC overall survival model"
    assert meta["status"] == RESEARCH_STATEMENT == "Research model — not clinically validated"
    assert meta["selected_model"] in {"cox", "rsf"} and meta["selection_reason"]
    assert meta["feature_names"] and meta["training_config"]["seed"] == 42
    assert all(len(f["sha256"]) == 64 for f in meta["dataset"]["files"].values())
    assert "OS_STATUS" in meta["target"]["event"]


def test_artifact_loads_and_predicts_expected_shape(artifact_dir):
    artifact = load_artifact(artifact_dir)
    assert artifact.metadata["status"] == RESEARCH_STATEMENT
    patients = [
        {"AGE_AT_DIAGNOSIS": 55, "LYMPH_NODES_EXAMINED_POSITIVE": 6, "TUMOR_SIZE": 40, "GRADE": 3,
         "ER_STATUS": "Positive", "CHEMOTHERAPY": "YES"},
        {},  # everything missing still scores: numeric median, "Unknown" categories
    ]
    results = artifact.predict(patients)
    assert len(results) == 2
    for r in results:
        assert isinstance(r["risk_score"], float) and np.isfinite(r["risk_score"])
        assert set(r["survival_probability"]) == {"60_months", "120_months"}
        for v in r["survival_probability"].values():
            assert v is None or 0.0 <= v <= 1.0
        assert r["model"] == MODEL_NAME and r["status"] == RESEARCH_STATEMENT
