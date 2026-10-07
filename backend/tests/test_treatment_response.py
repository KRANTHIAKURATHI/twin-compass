"""Tests for the GSE163882 pCR research model (offline). Synthetic data only: the real dataset is never needed."""
from __future__ import annotations

import gzip
import json

import numpy as np
import pandas as pd
import pytest

from app.ml.treatment_response import (
    CLAIM, MODEL_NAME, STATUS, TARGET, TREATMENT_CONTEXT, experiment as ex, pipeline as pl,
)
from app.ml.treatment_response.data import (
    CLINICAL_FEATURES, Cohort, assign_patient_groups, build_cohort, build_target, parse_series_matrix, read_expression,
)
from app.ml.treatment_response.predict import load_artifact


def _synthetic(n: int = 60, genes: int = 120, seed: int = 0, dup_pairs: int = 3):
    """TPM matrix with one planted pCR-associated gene (index 0) and a few replicate pairs."""
    rng = np.random.default_rng(seed)
    y = np.array([1, 0] * (n // 2))
    tpm = rng.gamma(2.0, 4.0, size=(n, genes))
    tpm[:, 0] = np.where(y == 1, rng.gamma(2, 20, n), rng.gamma(2, 4, n))
    labels = [f"S{i}-{1000 + i}" for i in range(n)]
    for p in range(dup_pairs):                   # sample 2p+... shares a specimen label with its neighbour; same class
        labels[2 * p + 2] = labels[2 * p]        # even rows are all pCR -> consistent label
    clin = pd.DataFrame({
        "age": rng.integers(30, 80, n).astype(float), "er": 1.0 - y * rng.integers(0, 2, n), "pr": rng.integers(0, 2, n).astype(float),
        "her2": rng.integers(0, 2, n).astype(float), "grade": rng.integers(1, 4, n).astype(float), "stage": rng.integers(1, 4, n).astype(float),
    })
    clin.loc[[3, 9], "stage"] = np.nan
    ids = [f"ENSG{i:011d}" for i in range(genes)]
    return tpm, y, labels, clin, ids


def _cohort(n=60, genes=120, **kw) -> Cohort:
    tpm, y, labels, clin, ids = _synthetic(n, genes, **kw)
    groups = np.array(assign_patient_groups(labels))
    site = np.array(["A", "B", "C"] * (n // 3))
    return Cohort([f"BA{i:05d}" for i in range(n)], tpm, ids, [f"g{i}" for i in range(genes)], clin, y, groups, site,
                  {"patients": len(set(groups)), "samples": n, "pcr": int(y.sum()), "rd": int((1 - y).sum()), "pcr_patients": int(y.sum()), "rd_patients": int((1 - y).sum())})


@pytest.fixture
def tiny_grid(monkeypatch):
    monkeypatch.setattr(pl, "K_GRID", (5, 10))
    monkeypatch.setattr(pl, "L1_GRID", (0.5, 1.0))
    monkeypatch.setattr(pl, "C_GRID", (0.1, 1.0))
    monkeypatch.setattr(pl, "CLIN_SCALE_GRID", (1.0, 5.0))
    monkeypatch.setattr(ex, "N_BOOT", 60)


# 1 ---------------------------------------------------------------- expression parsing
def test_expression_parsing_uses_ensembl_key_and_drops_annotation(tmp_path):
    path = tmp_path / "e.csv.gz"
    with gzip.open(path, "wt") as fh:
        fh.write(",BA1,BA2,annotation\n") if False else fh.write(",BA00002,BA00001,annotation\nENSG1,1.5,0,A;x\nENSG2,0,10,A;x\n")
    values, samples, genes, ann = read_expression(path)
    assert values.shape == (2, 2) and samples == ["BA00002", "BA00001"] and genes == ["ENSG1", "ENSG2"]
    assert ann == ["A;x", "A;x"]                     # duplicate display names do not matter: the key is the Ensembl id
    assert values[0].tolist() == [1.5, 0.0] and values[1].tolist() == [0.0, 10.0]


def test_expression_rejects_negative_or_missing(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text(",S1,annotation\nENSG1,-1,a\n")
    with pytest.raises(ValueError):
        read_expression(p)
    p.write_text(",S1,annotation\nENSG1,,a\n")
    with pytest.raises(ValueError):
        read_expression(p)


def _series(tmp_path, responses, labels=None):
    n = len(responses)
    labels = labels or [f"X{i}" for i in range(n)]
    q = lambda xs: "\t".join(f'"{x}"' for x in xs)
    rows = [
        "!Sample_title\t" + q([f"BA{i:05d}: {labels[i]}" for i in range(n)]),
        "!Sample_geo_accession\t" + q([f"GSM{i}" for i in range(n)]),
        "!Sample_source_name_ch1\t" + q(["breast cancer patients from UConn Health"] * n),
        "!Sample_characteristics_ch1\t" + q([f"response to nac: {r}" for r in responses]),
        "!Sample_characteristics_ch1\t" + q([f"age: {40 + i}" for i in range(n)]),
        "!Sample_characteristics_ch1\t" + q(["estrogen receptor status: P"] * n),
        "!Sample_characteristics_ch1\t" + q(["progesterone receptor status: N"] * n),
        "!Sample_characteristics_ch1\t" + q(["her2 receptor status: N"] * n),
        "!Sample_characteristics_ch1\t" + q(["tumor grage: 0"] + ["tumor grage: 2"] * (n - 1)),
        "!Sample_characteristics_ch1\t" + q(["breast cancer stage: NA"] + ["breast cancer stage: 2"] * (n - 1)),
    ]
    p = tmp_path / "series.txt"
    p.write_text("\n".join(rows) + "\n")
    return p


# 2 ---------------------------------------------------------------- target construction
def test_target_is_taken_only_from_response_field(tmp_path):
    meta = parse_series_matrix(_series(tmp_path, ["pCR", "RD", "pCR", "unknown"]))
    assert build_target(meta["response"]).tolist()[:3] == [1, 0, 1] and pd.isna(build_target(meta["response"]).iloc[3])
    tpm = np.ones((4, 3))
    c = build_cohort(meta, tpm, list(meta["sample_id"]), ["G1", "G2", "G3"], ["a", "b", "c"])
    assert c.y.tolist() == [1, 0, 1] and c.provenance["samples_without_explicit_label_dropped"] == 1   # unlabeled sample dropped, never inferred
    assert c.provenance["pcr"] == 2 and c.provenance["rd"] == 1
    assert np.isnan(c.clinical.loc[0, "grade"]) and np.isnan(c.clinical.loc[0, "stage"])   # grade 0 invalid, stage NA


def test_cohort_joins_by_sample_id_not_position(tmp_path):
    meta = parse_series_matrix(_series(tmp_path, ["pCR", "RD", "pCR"]))
    tpm = np.array([[3.0], [2.0], [1.0]])                          # expression rows in reverse order
    c = build_cohort(meta, tpm, ["BA00002", "BA00001", "BA00000"], ["G"], ["g"])
    assert c.sample_ids == ["BA00002", "BA00001", "BA00000"] and c.y.tolist() == [1, 0, 1]
    assert c.tpm[:, 0].tolist() == [3.0, 2.0, 1.0] and c.clinical["age"].tolist() == [42.0, 41.0, 40.0]


# 3 ---------------------------------------------------------------- patient grouping
def test_patient_grouping_rules_and_determinism():
    labels = ["S1-1", "S2-2", "S1-1", "S3/S4", "S4", "S5"]
    g = assign_patient_groups(labels)
    assert g[0] == g[2] and g[3] == g[4] and len(set(g)) == 4        # same label and shared token merge
    perm = [5, 3, 1, 0, 4, 2]
    assert assign_patient_groups([labels[i] for i in perm]) == [g[i] for i in perm]   # row order does not matter
    assert assign_patient_groups(labels) == g


def test_mixed_label_group_is_rejected(tmp_path):
    meta = parse_series_matrix(_series(tmp_path, ["pCR", "RD"], labels=["same", "same"]))
    with pytest.raises(ValueError, match="mixes"):
        build_cohort(meta, np.ones((2, 2)), list(meta["sample_id"]), ["a", "b"], ["a", "b"])


# 4 ---------------------------------------------------------------- duplicate-patient protection
def test_replicates_never_split_across_outer_or_inner_folds():
    c = _cohort(n=90, dup_pairs=4)
    assert len(set(c.groups)) < len(c.y)
    for tr, te, r, f in ex.outer_splits(c.y, c.groups, repeats=3):
        assert not set(c.groups[tr]) & set(c.groups[te])
        assert abs(c.y[te].mean() - c.y.mean()) < 0.12              # class balance preserved
    from sklearn.model_selection import StratifiedGroupKFold
    for tr, va in StratifiedGroupKFold(pl.INNER_FOLDS, shuffle=True, random_state=1).split(np.zeros(len(c.y)), c.y, c.groups):
        assert not set(c.groups[tr]) & set(c.groups[va])


# 5 ---------------------------------------------------------------- log transform
def test_log2_tpm_plus_one():
    assert pl.log2_tpm(np.array([0.0, 1.0, 3.0, 7.0])).tolist() == [0.0, 1.0, 2.0, 3.0]


# 6 ---------------------------------------------------------------- training-only gene filtering
def test_detection_filter_uses_training_rows_only():
    tpm, y, _, _, ids = _synthetic()
    tr, te = np.arange(0, 40), np.arange(40, 60)
    tpm = tpm.copy()
    tpm[tr, 5] = 0.2                       # never detected in training ...
    tpm[te, 5] = 500.0                     # ... but highly expressed in held-out rows
    tpm[tr, 6] = 5.0
    tpm[tr[:30], 7] = 0.0                  # detected in 10/40 = 25% of training
    tpm[tr[30:], 7] = 5.0
    tpm[tr[:33], 8] = 0.0                  # detected in 7/40 = 17.5% -> below the 20% threshold
    tpm[tr[33:], 8] = 5.0
    prep = pl.ExpressionPreprocessor.fit(tpm[tr], y[tr], ids)
    kept = set(prep.kept.tolist())
    assert 5 not in kept and 6 in kept and 7 in kept and 8 not in kept
    tpm2 = tpm.copy()
    tpm2[te] = np.random.default_rng(3).gamma(2, 50, tpm2[te].shape)   # scramble held-out rows
    assert pl.ExpressionPreprocessor.fit(tpm2[tr], y[tr], ids).kept.tolist() == prep.kept.tolist()


# 7 ---------------------------------------------------------------- training-only feature selection
def test_selection_uses_training_rows_only_and_finds_planted_gene():
    tpm, y, _, _, ids = _synthetic(n=80)
    tr, te = np.arange(0, 60), np.arange(60, 80)
    prep = pl.ExpressionPreprocessor.fit(tpm[tr], y[tr], ids)
    assert prep.selected_ids(3)[0] == ids[0]                        # the planted gene ranks first
    tpm2, y2 = tpm.copy(), y.copy()
    tpm2[te] = np.random.default_rng(4).gamma(2, 80, tpm2[te].shape)
    y2[te] = 1 - y2[te]                                             # held-out labels flipped as well
    prep2 = pl.ExpressionPreprocessor.fit(tpm2[tr], y2[tr], ids)
    assert prep2.selected_ids(20) == prep.selected_ids(20) and np.array_equal(prep2.t, prep.t)


# 8 ---------------------------------------------------------------- preprocessing leakage prevention
def test_scrambled_heldout_rows_change_nothing_learned(tiny_grid):
    c = _cohort(n=60)
    tr, te = np.arange(0, 45), np.arange(45, 60)
    base = ex._run_kinds(ex._subset(c, tr), ex._subset(c, te), 11)
    scrambled = _cohort(n=60)
    rng = np.random.default_rng(9)
    scrambled.tpm[te] = rng.gamma(2, 30, scrambled.tpm[te].shape)
    scrambled.clinical.loc[te, "age"] = 999.0
    alt = ex._run_kinds(ex._subset(scrambled, tr), ex._subset(scrambled, te), 11)
    for kind in pl.KINDS:
        assert base[kind]["config"] == alt[kind]["config"] and base[kind]["threshold"] == alt[kind]["threshold"]
        assert np.allclose(base[kind]["model"].clf.coef_, alt[kind]["model"].clf.coef_)
        if kind != "clinical":
            assert base[kind]["selected"] == alt[kind]["selected"]


def test_clinical_preprocessor_imputes_stage_from_training_only():
    clin = pd.DataFrame({"age": [40.0, 50, 60], "er": [1.0, 0, 1], "pr": [1.0, 0, 0], "her2": [0.0, 0, 1], "grade": [1.0, 2, 3], "stage": [1.0, np.nan, 3.0]})
    prep = pl.ClinicalPreprocessor.fit(clin)
    assert prep.fill["stage"] == 2.0
    held = pd.DataFrame({"age": [50.0], "er": [1.0], "pr": [0.0], "her2": [0.0], "grade": [2.0], "stage": [np.nan]})
    assert prep.transform(held)[0, CLINICAL_FEATURES.index("stage")] == pytest.approx(0.0)   # filled with the training median 2 -> z = 0


# 9 ---------------------------------------------------------------- tiny logistic training
def test_tiny_logistic_training_learns_planted_signal():
    tpm, y, _, clin, ids = _synthetic(n=80)
    for kind in pl.KINDS:
        cfg = {"k": 0 if kind == "clinical" else 10, "l1_ratio": 0.0 if kind == "clinical" else 0.5, "C": 1.0, "clin_scale": 1.0}
        m = pl.fit_model(kind, clin, tpm, y, ids, cfg, seed=1)
        p = m.predict_proba(clin, tpm)
        assert p.shape == (80,) and ((p >= 0) & (p <= 1)).all()
        if kind != "clinical":
            from sklearn.metrics import roc_auc_score
            assert roc_auc_score(y, p) > 0.9
    cfgB = {"k": 10, "l1_ratio": 1.0, "C": 0.2, "clin_scale": 1.0}
    assert (pl.fit_model("expression", clin, tpm, y, ids, cfgB, 1).coefficients() != 0).sum() < 10   # lasso zeroes some of the 10 genes


# 10-12 ----------------------------------------------------------- artifact, probabilities, metadata
@pytest.fixture
def artifact_dir(tmp_path, tiny_grid):
    c = _cohort(n=60)
    ex.run(c, repeats=1, n_jobs=1, out_dir=tmp_path / "art", log=lambda *_: None)
    return tmp_path / "art"


def test_artifact_files_and_metadata(artifact_dir):
    for name in ("model.joblib", "metadata.json", "metrics.json", "feature_names.json"):
        assert (artifact_dir / name).exists()
    meta = json.loads((artifact_dir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["model_name"] == MODEL_NAME == "GSE163882 neoadjuvant chemotherapy pCR prediction model"
    assert meta["status"] == STATUS == "Research model — not clinically validated"
    assert meta["target"] == TARGET == "Target: pathological complete response (pCR) vs residual disease (RD)"
    assert meta["treatment_context"] == TREATMENT_CONTEXT == "Treatment context: neoadjuvant taxane-based chemotherapy"
    assert meta["claim"] == CLAIM and "not be interpreted as a clinical treatment recommendation" in CLAIM
    for key in ("patient_count", "sample_count", "pcr_count", "rd_count", "grouping_strategy", "preprocessing", "detection_threshold",
                "selected_gene_count", "l1_ratio", "regularization", "random_seed", "cv_configuration"):
        assert key in meta
    assert meta["sample_count"] == 60 and meta["random_seed"] == 42 and meta["external_validation"] == "none"
    metrics = json.loads((artifact_dir / "metrics.json").read_text(encoding="utf-8"))
    assert set(metrics["models"]) == set(pl.KINDS) and metrics["cv"]["group_leak_check"].startswith("passed")
    assert "combined_minus_clinical" in metrics["primary_comparison"]["paired_differences_repeat_averaged_oof"]
    assert {"ER+", "TNBC"} <= set(metrics["subgroups"]["groups"]) and len(metrics["site_sensitivity"]["folds"]) == 3


def test_artifact_loads_and_predicts_probabilities(artifact_dir):
    art = load_artifact(artifact_dir)
    names = json.loads((artifact_dir / "feature_names.json").read_text(encoding="utf-8"))
    genes = [g["ensembl_id"] for g in names["combined"]["genes"]]
    assert names["combined"]["clinical_features"] == CLINICAL_FEATURES and len(genes) == art.metadata["selected_gene_count"]
    clin = [{"age": 50, "er": 1, "pr": 0, "her2": 0, "grade": 2, "stage": None}, {"age": 61, "er": 0, "pr": 0, "her2": 0, "grade": 3, "stage": 2}]
    expr = [{g: 10.0 for g in genes}, {}]                            # second sample: every gene missing -> training medians
    for variant in pl.KINDS:
        out = art.predict(clin, expr, model=variant)
        assert len(out) == 2 and all(0.0 <= o["pcr_probability"] <= 1.0 for o in out)
        assert out[0]["status"] == STATUS and out[0]["variant"] == variant and isinstance(out[0]["predicted_pcr"], bool)
    assert art.predict(clin, expr)[0]["variant"] == "combined"
    with pytest.raises(ValueError):
        art.predict(clin, expr[:1])
    with pytest.raises(ValueError):
        art.predict(clin, expr, model="nope")


def test_subgroup_and_site_underpowered_flags(artifact_dir):
    metrics = json.loads((artifact_dir / "metrics.json").read_text(encoding="utf-8"))
    assert all(g["status"] == "ok" or g["status"].startswith("underpowered") for g in metrics["subgroups"]["groups"].values())
    assert metrics["subgroups"]["groups"]["ER-"]["n"] < 40 or metrics["subgroups"]["groups"]["ER-"]["status"] == "ok"
    assert all(f["status"] in ("ok",) or f["status"].startswith("underpowered") for f in metrics["site_sensitivity"]["folds"])
