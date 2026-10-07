"""METABRIC molecular survival experiment: parsing, cohort matching, leakage safety, tiny training, artifact.

Synthetic cBioPortal-layout files only; the real expression matrix is never read here.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("sksurv")

from sklearn.model_selection import train_test_split  # noqa: E402

from app.ml.molecular import RESEARCH_STATEMENT  # noqa: E402
from app.ml.molecular.experiment import DEFAULT_CONFIG, run, run_endpoint  # noqa: E402
from app.ml.molecular.expression import build_cohort, read_expression  # noqa: E402
from app.ml.molecular.predict import load_artifact  # noqa: E402
from app.ml.molecular.screening import cox_score_z, fit_screen  # noqa: E402
from app.ml.survival.data import load_clinical  # noqa: E402
from tests.test_survival_model import PATIENT_COLS, SAMPLE_COLS, _write  # noqa: E402
from tests.test_survival_rfs import _rfs_cohort  # noqa: E402

N_GENES = 60
TINY = {
    "cv_folds": 3, "screen_sizes": [10, 30], "l1_ratios": [0.9, 1.0], "n_alphas": 10,
    "bootstrap_resamples": 20, "cox_alpha_grid": [1.0, 10.0],
}


def _write_expression(path, sample_ids, values, entrez=None, hugo=None, dup_rows=()):
    """`values`: samples x genes. `dup_rows`: extra raw rows (entrez, hugo, cells) appended verbatim."""
    n_genes = values.shape[1]
    entrez = entrez or [str(1000 + g) for g in range(n_genes)]
    hugo = hugo or [f"GENE{g}" for g in range(n_genes)]
    lines = ["\t".join(["Hugo_Symbol", "Entrez_Gene_Id", *sample_ids])]
    for g in range(n_genes):
        lines.append("\t".join([hugo[g], entrez[g], *(("NA" if np.isnan(v) else f"{v:.4f}") for v in values[:, g])]))
    for e, h, cells in dup_rows:
        lines.append("\t".join([h, e, *cells]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    """160 patients; sample ids differ from patient ids; genes 0 and 1 carry the survival signal."""
    d = tmp_path_factory.mktemp("molecular")
    patients, samples = _rfs_cohort(160, seed=3)
    rng = np.random.default_rng(7)
    for s in samples:
        s["SAMPLE_ID"] = "S-" + s["PATIENT_ID"]
    risk = np.array([-np.log(float(p["RFS_MONTHS"]) + 1.0) for p in patients])
    X = rng.normal(size=(160, N_GENES))
    X[:, 0] = 1.5 * (risk - risk.mean()) / risk.std() + rng.normal(scale=0.3, size=160)
    X[:, 1] = -X[:, 0] + rng.normal(scale=0.5, size=160)
    X[3, 5] = np.nan
    pf, sf, ef = d / "patient.txt", d / "sample.txt", d / "expression.txt"
    _write(pf, PATIENT_COLS, patients)
    _write(sf, SAMPLE_COLS, samples)
    _write_expression(ef, [s["SAMPLE_ID"] for s in samples], X)
    return {"dir": d, "patient": pf, "sample": sf, "expression": ef, "X": X, "patients": patients, "samples": samples}


def test_expression_parsing_shape_missing_and_provenance(synth):
    expr = read_expression(synth["expression"])
    assert expr.values.shape == (160, N_GENES) and expr.values.dtype == np.float32
    assert expr.sample_ids[0] == "S-MB-0000" and expr.entrez_ids[:2] == ["1000", "1001"]
    assert int(np.isnan(expr.values).sum()) == 1 and np.isnan(expr.values[3, 5])
    assert expr.provenance["rows_in_file"] == N_GENES and expr.provenance["missing_values"] == 1


def test_duplicate_entrez_keeps_first_row_without_averaging(tmp_path):
    X = np.arange(12, dtype=float).reshape(3, 4)
    dup = [("1001", "GENE1_ALT", ["100", "200", "300"])]
    _write_expression(tmp_path / "e.txt", ["A", "B", "C"], X, dup_rows=dup)
    expr = read_expression(tmp_path / "e.txt")
    assert expr.entrez_ids == ["1000", "1001", "1002", "1003"] and expr.hugo_symbols[1] == "GENE1"
    assert expr.values[:, 1].tolist() == [1.0, 5.0, 9.0]  # the original row, not the alternative, not a mean
    assert expr.provenance["duplicate_entrez_rows_dropped"] == 1 and "no averaging" in expr.provenance["duplicate_rule"]


def test_duplicate_sample_ids_and_bad_header_are_rejected(tmp_path):
    (tmp_path / "dup.txt").write_text("Hugo_Symbol\tEntrez_Gene_Id\tA\tA\nG\t1\t0.1\t0.2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        read_expression(tmp_path / "dup.txt")
    (tmp_path / "bad.txt").write_text("Gene\tId\tA\nG\t1\t0.1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Entrez"):
        read_expression(tmp_path / "bad.txt")


def test_patient_sample_matching_aligns_rows_through_the_sample_file(synth):
    frame = load_clinical(synth["patient"], synth["sample"])
    expr = read_expression(synth["expression"])
    cohort = build_cohort(frame, expr, "RFS")
    assert len(cohort.patient_ids) == len(cohort.event) == cohort.expression.shape[0] == len(cohort.clinical) == 160
    # expression row i must be the sample of patient i (ids differ: S-<patient>)
    pos = {s: i for i, s in enumerate(expr.sample_ids)}
    for i in (0, 57, 159):
        assert np.allclose(cohort.expression[i], expr.values[pos["S-" + cohort.patient_ids[i]]], equal_nan=True)


def test_cohort_drops_missing_targets_and_unmatched_samples_without_imputing(synth, tmp_path):
    patients = [dict(p) for p in synth["patients"]]
    patients[0]["RFS_STATUS"] = "NA"
    patients[1]["RFS_MONTHS"] = "NA"
    pf = tmp_path / "p.txt"
    _write(pf, PATIENT_COLS, patients)
    samples = synth["samples"]
    # expression lacks the last 10 samples (clinical-only patients)
    ids = [s["SAMPLE_ID"] for s in samples[:150]]
    _write_expression(tmp_path / "e.txt", ids, synth["X"][:150])
    frame = load_clinical(pf, synth["sample"])
    cohort = build_cohort(frame, read_expression(tmp_path / "e.txt"), "RFS")
    assert len(cohort.event) == 148
    assert "MB-0000" not in cohort.patient_ids and "MB-0001" not in cohort.patient_ids
    assert "MB-0155" not in cohort.patient_ids  # clinical-only: no expression, no row


def test_cox_score_z_ranks_a_planted_gene_first_with_the_right_sign():
    rng = np.random.default_rng(0)
    n = 400
    x = rng.normal(size=n)
    time = rng.exponential(np.exp(-1.0 * x) * 50)           # higher x -> earlier event -> positive z
    event = rng.random(n) < 0.7
    Z = np.column_stack([rng.normal(size=n), x, rng.normal(size=n)])
    z = cox_score_z(Z, event, time)
    assert np.argmax(np.abs(z)) == 1 and z[1] > 5 and abs(z[0]) < 4 and abs(z[2]) < 4


def test_screen_is_learned_from_training_rows_and_handles_missing_values():
    rng = np.random.default_rng(1)
    Xtr = rng.normal(size=(120, 8))
    Xtr[5, 2] = np.nan
    ev, tm = rng.random(120) < 0.6, rng.exponential(30, 120)
    ids = [str(i) for i in range(8)]
    screen = fit_screen(Xtr, ev, tm, ids)
    assert screen.median[2] == pytest.approx(np.nanmedian(Xtr[:, 2]))      # training median, not a global value
    tf = screen.top(4)
    unseen = rng.normal(size=(5, 8)) * 100
    unseen[0, tf.columns[0]] = np.nan                                       # missing at scoring time
    out = tf.transform(unseen)
    assert out.shape == (5, 4) and not np.isnan(out).any()
    assert out[0, 0] == pytest.approx((tf.median[0] - tf.mean[0]) / tf.std[0])  # imputed with the TRAIN median
    assert out.max() <= (tf.hi - tf.mean).max() / tf.std.min() + 1e-9      # winsorised at training bounds


def test_selection_and_training_never_see_held_out_expression(synth, tmp_path):
    """Scramble the expression of the held-out patients: everything fitted on training rows is unchanged."""
    cfg = {**DEFAULT_CONFIG, **TINY}
    frame = load_clinical(synth["patient"], synth["sample"])
    expr = read_expression(synth["expression"])
    cohort = build_cohort(frame, expr, "RFS")
    _, idx_te = train_test_split(np.arange(len(cohort.event)), test_size=cfg["test_size"], random_state=cfg["seed"],
                                 stratify=cohort.event)
    test_ids = {"S-" + cohort.patient_ids[i] for i in idx_te}
    X2 = synth["X"].copy()
    rows = [i for i, s in enumerate(expr.sample_ids) if s in test_ids]
    X2[rows] = np.random.default_rng(99).normal(scale=25, size=(len(rows), N_GENES))
    _write_expression(tmp_path / "e2.txt", expr.sample_ids, X2)

    a = run_endpoint(frame, expr, "RFS", cfg, None)
    b = run_endpoint(frame, read_expression(tmp_path / "e2.txt"), "RFS", cfg, None)
    for m in ("B", "C"):
        ra, rb = a["models"][m], b["models"][m]
        assert ra["hyperparameters"] == rb["hyperparameters"]
        assert ra["nonzero_expression_genes"] == rb["nonzero_expression_genes"]
        assert ra["cv_c_index_mean"] == rb["cv_c_index_mean"]
        assert ra["train_c_index"] == pytest.approx(rb["train_c_index"])
        assert ra["test_c_index"] != rb["test_c_index"]      # only the held-out score may move
    assert a["models"]["A"]["train_c_index"] == b["models"]["A"]["train_c_index"]


@pytest.fixture(scope="module")
def trained(synth, tmp_path_factory):
    out = tmp_path_factory.mktemp("molecular_out")
    summary = run(synth["patient"], synth["sample"], synth["expression"], out, ("RFS",), TINY)
    return out, summary


def test_tiny_experiment_reports_all_four_models_with_required_fields(trained):
    _, summary = trained
    rep = summary["endpoints"]["RFS"]
    assert set(rep["models"]) == {"A", "A2", "B", "C"}
    split = rep["split"]
    assert split["n_train"] + split["n_test"] == split["n_patients"] == 160 and split["n_genes_available"] == N_GENES
    for m in rep["models"].values():
        assert 0 < m["train_c_index"] <= 1 and 0 < m["test_c_index"] <= 1
        assert {"n_patients_train", "events_train", "raw_clinical_features", "expression_features_considered",
                "expression_features_selected", "nonzero_coefficients", "test_c_index_ci95"} <= set(m)
        lo, hi = m["test_c_index_ci95"]
        assert 0 < lo <= hi <= 1
    assert rep["models"]["A"]["expression_features_considered"] == 0
    assert rep["models"]["B"]["expression_features_considered"] == N_GENES
    assert rep["models"]["C"]["hyperparameters"]["clinical_penalty_factor"] == 0.0
    assert rep["bootstrap"]["n_resamples"] > 0 and "C - A" in rep["bootstrap"]["paired_difference_ci95"]


def test_planted_signal_genes_are_selected(trained):
    genes = {g["entrez_id"] for g in trained[1]["endpoints"]["RFS"]["models"]["B"]["nonzero_expression_genes"]}
    assert genes & {"1000", "1001"}


def test_metadata_has_required_provenance_and_research_status(trained):
    out, _ = trained
    meta = json.loads((out / "rfs" / "metadata.json").read_text())
    assert meta["dataset"] == "METABRIC" and meta["endpoint"] == "RFS" and meta["model"] == "Elastic-Net Cox"
    assert meta["status"] == RESEARCH_STATEMENT == "Research model — not clinically validated"
    assert "Illumina" in meta["expression_source"] and meta["random_seed"] == 42
    assert meta["patient_count"] == 160 and meta["event_count"] > 0 and meta["selected_gene_count"] >= 0
    assert meta["l1_ratio"] in TINY["l1_ratios"] and "alpha" in meta["regularization"]
    assert meta["screening"]["chosen_size"] in TINY["screen_sizes"] and "training" in meta["feature_selection_methodology"]
    assert any("treatment-response" in s for s in meta["limitations"])
    assert (out / "experiment_report.json").exists() and (out / "rfs" / "metrics.json").exists()


def test_artifact_loads_and_predicts_expected_shape(trained):
    out, _ = trained
    art = load_artifact(out / "rfs")
    clinical = [{"AGE_AT_DIAGNOSIS": 55, "LYMPH_NODES_EXAMINED_POSITIVE": 6, "TUMOR_SIZE": 40, "GRADE": 3, "ER_STATUS": "Positive"}, {}]
    expression = [{"1000": 2.5, "1001": -2.0}, {}]   # absent genes fall back to training medians
    results = art.predict(clinical, expression)
    assert len(results) == 2
    for r in results:
        assert np.isfinite(r["risk_score"]) and set(r["survival_probability"]) == {"60_months", "120_months"}
        assert all(v is None or 0 <= v <= 1 for v in r["survival_probability"].values())
        assert r["status"] == RESEARCH_STATEMENT
    with pytest.raises(ValueError):
        art.predict(clinical, expression[:1])


def test_molecular_artifacts_do_not_touch_existing_survival_artifacts(trained):
    from app.ml.molecular import ARTIFACT_DIR as MOL
    from app.ml.survival.train import ARTIFACT_DIR, RFS_ARTIFACT_DIR
    assert MOL.name == "molecular_survival" and MOL not in (ARTIFACT_DIR, RFS_ARTIFACT_DIR)
    assert trained[0] not in (ARTIFACT_DIR, RFS_ARTIFACT_DIR)
