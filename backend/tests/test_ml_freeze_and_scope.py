"""
Freeze-and-scope checks for the four research/prototype models (WDBC, METABRIC OS, METABRIC RFS, GSE163882 pCR).

* the artifacts are exactly the ones recorded in app/ml/artifacts/artifact_manifest.json (a retrain or replacement
  must be a deliberate, reviewed change to that file);
* the pCR model is not reachable from any API route, service or frontend file - it needs gene-expression input
  OncoTwin does not hold, so it must not be presented as an available patient prediction;
* the two gaps found in the Phase 1 audit are closed and pinned here (WDBC run refuses a patient with missing inputs;
  the pCR model refuses to score without a usable gene-expression profile), against the REAL frozen artifacts.
  Their detailed behaviour is covered in test_predictions_run_validation.py and test_treatment_response.py.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("sksurv")

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "backend" / "app" / "ml" / "artifacts"
MANIFEST = json.loads((ARTIFACTS / "artifact_manifest.json").read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix == ".json":  # same normalisation as the manifest generator: independent of git CRLF/LF
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("relative", sorted(MANIFEST["sha256"]))
def test_artifact_file_matches_the_frozen_manifest(relative):
    assert _digest(ARTIFACTS / relative) == MANIFEST["sha256"][relative], (
        f"{relative} changed. If a model was retrained or replaced on purpose, re-verify its metrics and update "
        "artifact_manifest.json in the same change."
    )


def test_manifest_covers_every_file_of_the_four_models():
    on_disk = {p.relative_to(ARTIFACTS).as_posix() for d in ("", "survival", "survival_rfs", "treatment_response")
               for p in (ARTIFACTS / d).glob("*.*") if p.is_file() and p.name != "artifact_manifest.json"}
    assert on_disk == set(MANIFEST["sha256"])


def test_the_pcr_model_is_not_served_by_any_route_service_or_page():
    from app.main import app

    paths = " ".join(getattr(r, "path", "") for r in app.routes).lower()
    assert not re.search(r"pcr|treatment[-_]response", paths), "a pCR / treatment-response route is mounted"

    pattern = re.compile(r"treatment_response|GSE163882|\bpcr\b", re.I)
    offenders = []
    for base in (ROOT / "backend" / "app" / "api", ROOT / "backend" / "app" / "services", ROOT / "src"):
        for p in base.rglob("*"):
            if p.suffix in (".py", ".ts", ".tsx") and "__pycache__" not in p.parts and p.name != "routeTree.gen.ts":
                if pattern.search(p.read_text(encoding="utf-8", errors="ignore")):
                    offenders.append(p.relative_to(ROOT).as_posix())
    assert offenders == [], f"pCR model referenced outside app/ml: {offenders}"


def test_every_served_model_is_labelled_research_in_its_artifact_metadata():
    for directory in ("survival", "survival_rfs", "treatment_response"):
        meta = json.loads((ARTIFACTS / directory / "metadata.json").read_text(encoding="utf-8"))
        assert "not clinically validated" in meta["status"].lower(), directory


# --- the two closed gaps, against the real artifacts -------------------------------------------------------------


def test_wdbc_run_refuses_a_patient_with_no_recorded_clinical_fields():
    from app.api.v1.routers.predictions import _run_model
    from app.core.exceptions import ValidationAppError

    blank = dict(stage=None, grade=None, ki67=None, nodes_involved=None, tumor_size_mm=None,
                 er_status=None, pr_status=None, her2_status=None, age=None)
    with pytest.raises(ValidationAppError):
        _run_model(blank)


def test_pcr_predict_refuses_missing_gene_expression_and_scores_a_complete_profile():
    from app.ml.treatment_response.predict import load_artifact

    art = load_artifact(ARTIFACTS / "treatment_response")
    clin = {"age": 50, "er": 1, "pr": 1, "her2": 0, "grade": 2, "stage": 2}
    used = art.models["combined"].expression.selected_ids(int(art.models["combined"].config["k"]))
    complete = {g: 5.0 for g in art.models["combined"].expression.all_ids}

    for absent in ({}, None, {"unrelated": 1.0}):                    # absent, empty, or no gene the model uses
        with pytest.raises(ValueError):
            art.predict([clin], [absent])
    partial = dict(complete)
    del partial[used[0]]
    with pytest.raises(ValueError, match="gene"):
        art.predict([clin], [partial])
    with pytest.raises(ValueError):                                  # empty clinical AND empty expression: the 0.407 case
        art.predict([{}], [{}])

    only_used = art.predict([clin], [{g: 5.0 for g in used}])[0]      # genes the model does not use are irrelevant
    assert only_used["pcr_probability"] == pytest.approx(art.predict([clin], [complete])[0]["pcr_probability"])

    out = art.predict([clin], [complete])[0]
    assert 0.0 <= out["pcr_probability"] <= 1.0 and out["variant"] == "combined"
    assert "not clinically validated" in out["status"].lower()
