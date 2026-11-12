"""Prediction is built from the Active Digital Twin, maps the nine model inputs faithfully, and says what it is.

Endpoint tests run on the per-test SQLite database with fixture tables (see test_predictions_run_model); the twin's
snapshot is stored as JSON text there, exactly as a driver may return jsonb.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.api.v1.routers import clinical
from app.api.v1.routers.predictions import _input_state, _prognosis, _wdbc_model_inputs
from app.ml import model as rf
from app.ml.inputs import WDBC_RULES, check_patient_columns, require_model_fields
from app.ml.interface import HeuristicRandomForestModel, set_prediction_model
from app.services.clinical_queries import resolve_patient
from app.services.twin_state import active_twin_state
from tests.test_predictions_run_model import _FakeModel, _doctor_headers, _reset_model, db  # noqa: F401  (fixtures)

# The twin (v2) froze these; the patient row (fixture: age 55, stage II, 25 mm, ki67 18 ...) says something else today.
TWIN = {
    "age": 60, "stage": "III", "tumor_size_mm": 40.0, "grade": 3, "nodes_involved": 4, "ki67": 35.0,
    "er_status": "Negative", "pr_status": "Negative", "her2_status": "Positive", "risk": "high",
    "survival_probability": 0.7,
}
TWIN_AS_MODEL_INPUT = {
    "stage": "III", "grade": 3, "ki67": 35.0, "nodesInvolved": 4, "tumorSizeMm": 40.0,
    "erStatus": "Negative", "prStatus": "Negative", "her2Status": "Positive", "age": 60,
}
NINE = ("age", "tumor_size_mm", "nodes_involved", "grade", "ki67", "stage", "er_status", "pr_status", "her2_status")


def _add_version(db, version, status, created_at, snapshot):
    db(
        "INSERT INTO twin_versions (patient_id, version, status, created_at, snapshot) "
        "VALUES ('p1', :v, :s, :c, :snap)",
        {"v": version, "s": status, "c": created_at, "snap": json.dumps(snapshot)},
    )


def _run(client, headers):
    return client.post("/predictions/run", json={"patientId": "PT-1"}, headers=headers)


# ---- which state the model sees ---------------------------------------------------------------------------


def test_prediction_uses_the_active_twin_not_the_newer_patient_row(client, db):
    _add_version(db, "v2", "Active", "2026-01-01", TWIN)
    fake = _FakeModel()
    set_prediction_model(fake)
    r = _run(client, _doctor_headers(client))

    assert r.status_code == 201, r.text
    assert fake.calls == [TWIN_AS_MODEL_INPUT]  # not stage II / 25 mm / ki67 18 from the patient row
    assert r.json()["data"]["twinVersion"] == "v2"
    assert db("SELECT twin_version FROM prediction_runs", fetch=True)[0]["twin_version"] == "v2"


def test_a_patient_row_edit_after_the_twin_was_cut_does_not_change_the_prediction_input(client, db):
    _add_version(db, "v2", "Active", "2026-01-01", TWIN)
    fake = _FakeModel()
    set_prediction_model(fake)
    headers = _doctor_headers(client)
    assert _run(client, headers).status_code == 201
    db("UPDATE patients SET tumor_size_mm = 99, ki67 = 1, stage = 'IV', er_status = 'Positive' WHERE id = 'p1'")
    assert _run(client, headers).status_code == 201
    assert fake.calls[0] == fake.calls[1] == TWIN_AS_MODEL_INPUT


def test_a_superseded_version_is_never_the_twin(client, db):
    _add_version(db, "v2", "Active", "2026-01-01", TWIN)
    # Newer than the Active one, but Superseded: it must not be selected.
    _add_version(db, "v3", "Superseded", "2026-06-01", {**TWIN, "tumor_size_mm": 5.0, "stage": "I"})
    fake = _FakeModel()
    set_prediction_model(fake)
    r = _run(client, _doctor_headers(client))
    assert r.status_code == 201 and fake.calls == [TWIN_AS_MODEL_INPUT]
    assert r.json()["data"]["twinVersion"] == "v2"


def test_with_no_active_twin_the_patient_row_is_used_and_the_version_is_none(client, db):
    _add_version(db, "v1", "Archived", "2026-01-01", TWIN)  # archived is not the current twin
    fake = _FakeModel()
    set_prediction_model(fake)
    r = _run(client, _doctor_headers(client))
    assert r.status_code == 201
    assert fake.calls[0]["tumorSizeMm"] == 25 and fake.calls[0]["stage"] == "II"  # the patient row, explicitly
    assert r.json()["data"]["twinVersion"] == "none"
    assert r.json()["modelInfo"]["inputState"] == {
        "basis": "current patient record (no active digital twin)", "twinVersion": None,
    }


# ---- nothing is defaulted or borrowed ---------------------------------------------------------------------


@pytest.mark.parametrize("field", NINE)
def test_a_twin_missing_any_of_the_nine_inputs_is_refused_and_nothing_is_borrowed_from_the_row(client, db, field):
    _add_version(db, "v2", "Active", "2026-01-01", {k: v for k, v in TWIN.items() if k != field})
    fake = _FakeModel()
    set_prediction_model(fake)
    r = _run(client, _doctor_headers(client))

    assert r.status_code == 422, r.text
    assert field in r.json()["error"]["message"]  # the patient row HAS this value; it must not be used
    assert fake.calls == []
    assert db("SELECT count(*) AS n FROM prediction_runs", fetch=True)[0]["n"] == 0


def test_a_blank_twin_value_counts_as_missing(client, db):
    _add_version(db, "v2", "Active", "2026-01-01", {**TWIN, "ki67": "", "stage": "  "})
    set_prediction_model(_FakeModel())
    r = _run(client, _doctor_headers(client))
    assert r.status_code == 422 and "ki67" in r.json()["error"]["message"] and "stage" in r.json()["error"]["message"]


def test_prediction_and_simulation_receive_the_same_clinical_state(client, db, db_sessionmaker):
    _add_version(db, "v2", "Active", "2026-01-01", TWIN)

    async def both():
        async with db_sessionmaker() as s:
            patient = await resolve_patient(s, "PT-1")
            return await clinical._twin_state(s, patient), await active_twin_state(s, patient)

    (sim_state, sim_version), (pred_state, pred_version) = asyncio.run(both())
    assert sim_state == pred_state and sim_version == pred_version == "v2"
    assert pred_state["tumor_size_mm"] == 40.0 and pred_state["ki67"] == 35.0  # the twin's, not the row's 25 / 18


# ---- the nine inputs map correctly ------------------------------------------------------------------------


def test_all_nine_fields_map_to_the_right_model_input_with_canonical_values():
    state = {
        "age": 60, "tumor_size_mm": "40", "nodes_involved": 4, "grade": "2.0", "ki67": "35.5",
        "stage": "iii", "er_status": "negative", "pr_status": "POSITIVE", "her2_status": "Positive",
    }
    fields, missing, invalid = check_patient_columns(state)
    assert (missing, invalid) == ([], [])
    assert fields == {
        "age": 60, "tumorSizeMm": "40", "nodesInvolved": 4, "grade": 2, "ki67": "35.5",  # numerics pass through unscaled
        "stage": "III", "erStatus": "Negative", "prStatus": "Positive", "her2Status": "Positive",
    }
    assert set(WDBC_RULES) == set(NINE)
    require_model_fields(fields)  # the model's own guard accepts exactly this dict


def test_the_factor_levels_are_in_the_documented_units_and_nothing_is_inverted():
    levels = rf.clinical_factors({
        "stage": "II", "grade": 3, "ki67": 20, "nodesInvolved": 3, "tumorSizeMm": 40, "age": 60,
        "erStatus": "Negative", "prStatus": "Negative", "her2Status": "Positive",
    })
    assert levels["Stage"] == 0.4
    assert levels["Tumour grade"] == 1.0  # grade 3 of 1..3
    assert levels["Ki-67 proliferation index"] == pytest.approx(0.20)  # percent -> fraction
    assert levels["Lymph nodes involved"] == pytest.approx(3 / 15)
    assert levels["Tumour size"] == pytest.approx(40 / 80)  # millimetres
    assert levels["Receptor profile (ER/PR/HER2)"] == pytest.approx(0.40)  # ER-, PR-, HER2+ all raise risk
    assert levels["Age at assessment"] == pytest.approx(0.5)
    # Direction: the same patient with positive ER/PR and negative HER2 has the lower receptor level.
    favourable = rf.clinical_factors({
        "stage": "II", "grade": 3, "ki67": 20, "nodesInvolved": 3, "tumorSizeMm": 40, "age": 60,
        "erStatus": "Positive", "prStatus": "Positive", "her2Status": "Negative",
    })
    assert favourable["Receptor profile (ER/PR/HER2)"] == 0.0


def test_the_model_refuses_a_missing_input_instead_of_using_clinical_factors_defaults():
    # clinical_factors() has documented defaults for an absent key; the model boundary must never reach them.
    with pytest.raises(ValueError, match="needs every clinical input"):
        HeuristicRandomForestModel().predict({"stage": "II", "grade": 2})
    with pytest.raises(ValueError):
        HeuristicRandomForestModel().predict({**TWIN_AS_MODEL_INPUT, "ki67": None})


def test_wdbc_model_inputs_report_every_missing_field_by_name():
    with pytest.raises(Exception) as err:
        _wdbc_model_inputs({"age": 60})
    message = str(err.value)
    for column in NINE:
        if column != "age":
            assert column in message


# ---- what the model is, and what the response says it is --------------------------------------------------


def test_the_response_identifies_the_model_its_dataset_validation_status_and_input_source(client, db):
    _add_version(db, "v2", "Active", "2026-01-01", TWIN)
    set_prediction_model(None)
    r = _run(client, _doctor_headers(client))
    assert r.status_code == 201, r.text
    body = r.json()
    info = body["modelInfo"]
    assert info["name"] == "OncoTwin Malignancy Risk Model" and info["version"] == "v1.0.0"
    assert info["datasetName"] == "Wisconsin Diagnostic Breast Cancer (sklearn)"
    assert info["modelType"] == "development" and info["isValidated"] is False
    assert "Not clinically validated" in info["disclaimer"]
    assert info["inputState"] == {"basis": "active digital twin snapshot", "twinVersion": "v2"}
    data = body["data"]
    assert "RF malignancy classifier; heuristic survival/recurrence" in data["model"]
    assert data["twinVersion"] == "v2" and data["date"] and data["status"] in ("Complete", "Low confidence")
    # Stored == returned.
    stored = db("SELECT * FROM prediction_runs", fetch=True)[0]
    assert (stored["model"], stored["twin_version"], stored["response"]) == (data["model"], "v2", data["riskBand"])
    assert (stored["survival"], stored["recurrence"], stored["confidence"]) == (
        data["survival"], data["recurrence"], data["confidence"],
    )


def test_the_artifact_matches_the_metadata_and_the_documented_benchmark_metrics():
    root = Path(rf.__file__).parent / "artifacts"
    metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
    joblib = pytest.importorskip("joblib")
    bundle = joblib.load(root / "model.joblib")
    assert (metrics["model_name"], metrics["model_version"]) == (bundle["model_name"], bundle["model_version"])
    assert metrics["dataset_records"] == 569 and metrics["n_features"] == len(bundle["feature_names"]) == 30
    assert type(bundle["model"]).__name__ == "RandomForestClassifier" and bundle["model"].n_estimators == 300
    assert metrics["accuracy"] == pytest.approx(0.9561, abs=1e-4)
    assert metrics["precision"] == pytest.approx(0.9589, abs=1e-4)
    assert metrics["recall"] == pytest.approx(0.9722, abs=1e-4)
    assert metrics["auc"] == pytest.approx(0.9931, abs=1e-4)
    # sklearn's WDBC target: 0 = malignant, 1 = benign; the code reads predict_proba[:, 1] as benign.
    assert list(bundle["model"].classes_) == [0, 1]


def test_the_wdbc_model_scores_a_synthetic_severity_vector_not_the_patients_own_measurements():
    pytest.importorskip("sklearn")
    out = rf.predict_from_patient(TWIN_AS_MODEL_INPUT)
    assert out["severity"] == pytest.approx(rf.clinical_severity(TWIN_AS_MODEL_INPUT), abs=1e-4)
    # The result is a function of the 0..1 severity composite alone: any patient with the same severity scores the same.
    assert rf.predict_from_severity(out["severity"])["proba_malignant"] == out["proba_malignant"]
    # What it outputs: a malignancy probability and heuristic formulas over it - survival is not a survival model.
    assert out["survival"] == pytest.approx(round(0.5 + out["proba_benign"] * 0.5 - out["severity"] * 0.05, 4), abs=1e-4)
    assert out["confidence"] == max(out["proba_malignant"], out["proba_benign"])


# ---- prognosis is a separate research model ----------------------------------------------------------------


def test_prognosis_reads_the_same_twin_state_and_is_kept_apart_from_the_malignancy_result(client, db):
    _add_version(db, "v2", "Active", "2026-01-01", TWIN)
    set_prediction_model(_FakeModel())
    body = _run(client, _doctor_headers(client)).json()
    prognosis, data = body["prognosis"], body["data"]

    # Prognosis is computed from the same state as the run (its own payload is a pinned frontend contract, so the
    # source is stated once, in `modelInfo.inputState`).
    assert body["modelInfo"]["inputState"] == {"basis": "active digital twin snapshot", "twinVersion": "v2"}
    for key in ("overallSurvival", "relapseFreeSurvival"):
        assert prognosis[key]["clinicallyValidated"] is False  # present whether available or unavailable
        assert "METABRIC" in json.dumps(prognosis[key]) or prognosis[key]["status"] == "unavailable"
    # The malignancy run carries no METABRIC score and the prognosis carries no malignancy probability.
    assert "riskScore" not in data and "riskScore" not in json.dumps(data)
    assert "proba_malignant" not in json.dumps(prognosis) and "riskBand" not in json.dumps(prognosis)


def test_prognosis_inputs_come_from_the_twin_state_and_its_risk_score_is_not_called_a_probability():
    state = dict(TWIN)
    out = _prognosis(state)
    for key in ("overallSurvival", "relapseFreeSurvival"):
        assert out[key]["clinicallyValidated"] is False
        if out[key]["status"] == "available":
            assert "not a probability" in out[key]["riskScoreNote"].lower()
    # Recorded survival / risk are inputs to nothing here: changing them changes no prognosis.
    assert json.dumps(_prognosis({**state, "risk": "low", "survival_probability": 0.99}), sort_keys=True) == json.dumps(
        out, sort_keys=True
    )


def test_input_state_never_claims_a_twin_that_was_not_used():
    assert _input_state(None)["twinVersion"] is None and "no active digital twin" in _input_state(None)["basis"]
    assert _input_state("v7") == {"basis": "active digital twin snapshot", "twinVersion": "v7"}


# ---- a patient created with the full form can be predicted for ----------------------------------------------------


def test_a_patient_created_with_all_nine_fields_satisfies_the_prediction_inputs_and_blanks_stay_blank():
    from app.schemas.clinical import PatientInput

    full = PatientInput.model_validate({
        "name": "N", "age": 55, "tumorSizeMm": 25, "nodesInvolved": 1, "grade": 2, "ki67": 18, "stage": "II",
        "erStatus": "Positive", "prStatus": "Positive", "her2Status": "Negative",
    })
    fields, missing, invalid = check_patient_columns(full.model_dump())
    assert (missing, invalid) == ([], []) and set(fields) == {
        "age", "tumorSizeMm", "nodesInvolved", "grade", "ki67", "stage", "erStatus", "prStatus", "her2Status",
    }
    # A blank field is omitted from the stored values (no default), and prediction then names it as missing.
    sparse = PatientInput.model_validate({"name": "N", "age": 55})
    assert sparse.model_dump(exclude_none=True) == {"name": "N", "age": 55}
    _, missing, _ = check_patient_columns(sparse.model_dump())
    assert set(missing) == set(NINE) - {"age"}
