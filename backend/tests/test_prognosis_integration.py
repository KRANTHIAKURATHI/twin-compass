"""METABRIC OS/RFS research models wired into the prediction service (prognostic only; not validated)."""
from __future__ import annotations

import pytest

pytest.importorskip("sksurv")

from app.ml import prognosis as pg  # noqa: E402
from app.ml.interface import set_prediction_model  # noqa: E402
from tests.test_predictions_run_model import _FakeModel, _doctor_headers, db  # noqa: E402,F401

PATIENT = {"age": 55, "stage": "II", "tumor_size_mm": 25.0, "er_status": "Positive", "pr_status": "Positive",
           "her2_status": "Negative", "grade": 2, "nodes_involved": 1}


@pytest.fixture(autouse=True)
def _reset_model():
    yield
    set_prediction_model(None)


def test_os_artifact_loads():
    a = pg._load("os")
    assert a.metadata["model_name"] == "METABRIC overall survival model"
    assert a.metadata["status"].startswith("Research model")


def test_rfs_artifact_loads():
    a = pg._load("rfs")
    assert a.metadata["model_name"] == "METABRIC relapse-free survival model"


def test_clinical_feature_mapping():
    m = pg.map_clinical_features({**PATIENT, "stage": "IIIA", "er_status": "positive", "grade": 3})
    assert m == {"AGE_AT_DIAGNOSIS": 55.0, "LYMPH_NODES_EXAMINED_POSITIVE": 1.0, "TUMOR_SIZE": 25.0, "GRADE": 3.0,
                 "TUMOR_STAGE": 3.0, "ER_STATUS": "Positive", "PR_STATUS": "Positive", "HER2_STATUS": "Negative"}
    assert pg.map_clinical_features({"stage": "IV"})["TUMOR_STAGE"] == 4.0
    assert pg.map_clinical_features({"stage": "0"})["TUMOR_STAGE"] == 0.0


def test_missing_and_invalid_features_are_not_invented():
    m = pg.map_clinical_features({"age": 0, "tumor_size_mm": 0, "stage": "unknown", "er_status": "Unknown", "grade": 7})
    assert m == {}
    out = pg.prognosis_for_patient({**PATIENT, "er_status": None, "tumor_size_mm": 0})
    for key in ("overallSurvival", "relapseFreeSurvival"):
        r = out[key]
        assert r["status"] == "unavailable" and "riskScore" not in r
        assert r["featureAvailability"]["missingRequired"] == ["TUMOR_SIZE", "ER_STATUS"]
        assert r["clinicallyValidated"] is False


def test_unrecorded_features_never_filled():
    out = pg.prognosis_for_patient(PATIENT)["overallSurvival"]
    av = out["featureAvailability"]
    assert "CLAUDIN_SUBTYPE" in av["notRecordedInOncoTwin"] and "CHEMOTHERAPY" in av["notRecordedInOncoTwin"]
    assert set(av["mapped"]) == set(pg.FEATURE_SOURCE)
    assert av["molecularExpressionUsed"] is False


def _check_prediction(r, label, kind):
    assert r["status"] == "available" and r["model"] == label and r["estimateKind"] == kind
    assert isinstance(r["riskScore"], float)
    assert "not a probability" in r["riskScoreNote"]
    assert r["timeHorizonsMonths"] == [60, 120]
    for e in r["estimates"]:
        assert e["probability"] is None or 0.0 <= e["probability"] <= 1.0
    assert any(e["probability"] is not None for e in r["estimates"])


def test_os_prediction():
    _check_prediction(pg.prognosis_for_patient(PATIENT)["overallSurvival"],
                      "METABRIC overall survival model — research only", "overall_survival_probability")


def test_rfs_prediction():
    _check_prediction(pg.prognosis_for_patient(PATIENT)["relapseFreeSurvival"],
                      "METABRIC relapse-free survival model — research only", "relapse_free_probability")


def test_higher_risk_patient_scores_higher():
    low = pg.prognosis_for_patient({**PATIENT, "nodes_involved": 0, "stage": "I", "grade": 1, "tumor_size_mm": 10})
    high = pg.prognosis_for_patient({**PATIENT, "nodes_involved": 12, "stage": "III", "grade": 3, "tumor_size_mm": 70})
    assert high["overallSurvival"]["riskScore"] > low["overallSurvival"]["riskScore"]


def test_provenance_metadata():
    for r in pg.prognosis_for_patient(PATIENT).values():
        p = r["provenance"]
        assert r["researchStatus"] == "Research model — not clinically validated"
        assert p["clinicallyValidated"] is False and p["externalValidation"] is False
        assert "Not a treatment-response model" in p["purpose"]
        assert p["modelVersion"] and "METABRIC" in p["dataset"]


def test_no_synthetic_expression_generation(monkeypatch):
    seen = []
    a = pg._load("os")
    orig = a.predict
    monkeypatch.setattr(type(a), "predict", lambda self, rows: (seen.extend(rows), orig(rows))[1])
    pg.prognosis_for_patient(PATIENT)
    assert seen and all(set(r) <= set(pg.FEATURE_SOURCE) for r in seen)
    assert not any("expression" in k.lower() or k.startswith("ENSG") for r in seen for k in r)


def test_wdbc_prediction_unchanged():
    pytest.importorskip("sklearn")
    from app.ml.interface import get_prediction_model

    set_prediction_model(None)
    model = get_prediction_model()
    before = model.predict({"stage": "II", "nodesInvolved": 1, "tumorSizeMm": 25, "grade": 2, "age": 55})
    pg.prognosis_for_patient(PATIENT)
    assert model.predict({"stage": "II", "nodesInvolved": 1, "tumorSizeMm": 25, "grade": 2, "age": 55}) == before
    assert {"survival", "recurrence", "confidence", "risk", "status"} <= set(before)


def test_run_endpoint_backward_compatible_with_prognosis(client, db):
    set_prediction_model(_FakeModel())
    r = client.post("/predictions/run", json={"patientId": "PT-1"}, headers=_doctor_headers(client))
    assert r.status_code == 201, r.text
    body = r.json()
    assert {"id", "date", "twinVersion", "model", "survival", "recurrence", "riskBand", "confidence", "status"} <= set(body["data"])
    assert body["data"]["survival"] == 90.0 and body["data"]["recurrence"] == 20.0  # heuristic fields untouched
    assert body["message"] == "Prediction run recorded."
    assert body["prognosis"]["overallSurvival"]["status"] == "available"
    assert body["prognosis"]["relapseFreeSurvival"]["status"] == "available"


def test_prognosis_endpoint_requires_auth_and_works(client, db):
    assert client.get("/predictions/PT-1/prognosis").status_code in (401, 403)
    r = client.get("/predictions/PT-1/prognosis", headers=_doctor_headers(client))
    assert r.status_code == 200 and r.json()["overallSurvival"]["status"] == "available"
