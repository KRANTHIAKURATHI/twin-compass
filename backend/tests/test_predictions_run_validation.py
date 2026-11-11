"""
POST /predictions/run must not score a patient whose model inputs are missing or unusable.

The WDBC severity mapping (`app.ml.model.clinical_factors`) has a silent default for each of its nine inputs, so before
this rule a patient with nothing recorded was scored `low` / survival 0.99 / `Complete`. Now the route answers 422, names
the fields, calls no model and writes nothing (no prediction run, no timeline event, no patient change).
"""
from __future__ import annotations

import pytest

from app.api.v1.routers.predictions import _WDBC_RULES, _run_model, _wdbc_model_inputs
from app.core.exceptions import ValidationAppError
from app.ml.interface import set_prediction_model
from tests.test_predictions_run_model import _FakeModel, _doctor_headers, _reset_model, db  # noqa: F401  (fixtures/helpers)

REQUIRED = list(_WDBC_RULES)            # patients columns: age, tumor_size_mm, nodes_involved, grade, ki67, stage, *_status
VALID = {"age": 55, "tumor_size_mm": 25, "nodes_involved": 1, "grade": 2, "ki67": 18, "stage": "II",
         "er_status": "Positive", "pr_status": "Positive", "her2_status": "Negative"}


def _snapshot(db):
    return {
        "patient": db("SELECT * FROM patients ORDER BY id", fetch=True),
        "runs": db("SELECT * FROM prediction_runs", fetch=True),
        "timeline": db("SELECT * FROM timeline_events", fetch=True),
    }


def _post(client, db, **patch):
    fake = _FakeModel()
    set_prediction_model(fake)
    sets = ", ".join(f"{k} = {'NULL' if v is None else repr(v)}" for k, v in patch.items())
    if sets:
        db(f"UPDATE patients SET {sets} WHERE id = 'p1'")
    before = _snapshot(db)
    r = client.post("/predictions/run", json={"patientId": "PT-1"}, headers=_doctor_headers(client))
    return r, fake, before


def test_the_nine_required_inputs_are_exactly_the_models_inputs():
    # these are the nine fields `clinical_factors` reads; a new model input must be added to the rules deliberately
    assert sorted(REQUIRED) == sorted(VALID)
    assert sorted(name for name, _ in _WDBC_RULES.values()) == sorted(
        ["age", "tumorSizeMm", "nodesInvolved", "grade", "ki67", "stage", "erStatus", "prStatus", "her2Status"])


@pytest.mark.parametrize("column", REQUIRED)
def test_each_missing_required_field_is_a_422_that_names_it_and_writes_nothing(client, db, column):
    r, fake, before = _post(client, db, **{column: None})
    assert r.status_code == 422, r.text
    error = r.json()["error"]
    assert error["code"] == "VALIDATION_ERROR" and error["field"] == column
    assert f"not recorded: {column}" in error["message"] and "nothing was saved" in error["message"]
    assert fake.calls == []                                   # the model was never called
    assert _snapshot(db) == before                            # no run, no timeline event, patient untouched


def test_several_missing_fields_are_all_listed(client, db):
    r, fake, before = _post(client, db, ki67=None, her2_status=None, grade=None)
    assert r.status_code == 422
    message = r.json()["error"]["message"]
    assert "not recorded: grade, ki67, her2_status" in message
    assert fake.calls == [] and _snapshot(db) == before


def test_a_patient_with_nothing_recorded_is_refused(client, db):
    r, fake, before = _post(client, db, **{c: None for c in REQUIRED})
    assert r.status_code == 422
    message = r.json()["error"]["message"]
    assert all(c in message for c in REQUIRED)
    assert fake.calls == [] and _snapshot(db) == before


@pytest.mark.parametrize(
    "column, value",
    [("age", 0), ("age", 200), ("tumor_size_mm", 0), ("tumor_size_mm", -4), ("nodes_involved", -1), ("grade", 4), ("grade", 0),
     ("ki67", 150), ("ki67", -1), ("stage", "IIA"), ("stage", "V"), ("er_status", "maybe"), ("pr_status", "unknown"),
     ("her2_status", "2+")],
)
def test_out_of_range_or_unrecognised_values_are_refused_not_corrected(client, db, column, value):
    r, fake, before = _post(client, db, **{column: value})
    assert r.status_code == 422, r.text
    error = r.json()["error"]
    assert error["field"] == column and "outside the supported range or not a recognised value" in error["message"]
    assert fake.calls == [] and _snapshot(db) == before


def test_blank_strings_count_as_not_recorded(client, db):
    r, fake, before = _post(client, db, stage="  ", er_status="")
    assert r.status_code == 422 and "not recorded: stage, er_status" in r.json()["error"]["message"]
    assert fake.calls == [] and _snapshot(db) == before


def test_valid_input_still_records_exactly_one_run_with_the_same_response_contract(client, db):
    r, fake, before = _post(client, db)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert {"id", "date", "twinVersion", "model", "survival", "recurrence", "riskBand", "confidence", "status"} <= set(data)
    assert data["survival"] == 90.0 and data["confidence"] == 85.0 and "prognosis" in r.json()
    assert len(fake.calls) == 1 and len(db("SELECT * FROM prediction_runs", fetch=True)) == 1


def test_canonical_spelling_is_applied_but_no_value_is_invented(client, db):
    r, fake, _ = _post(client, db, stage="ii", er_status="positive", pr_status=" NEGATIVE ", her2_status="Positive")
    assert r.status_code == 201, r.text
    call = fake.calls[0]
    assert (call["stage"], call["erStatus"], call["prStatus"], call["her2Status"]) == ("II", "Positive", "Negative", "Positive")
    assert call["age"] == 55 and call["tumorSizeMm"] == 25 and call["ki67"] == 18   # recorded numbers pass through unchanged


def test_run_model_helper_refuses_a_blank_patient_and_lists_the_fields():
    blank = {c: None for c in REQUIRED}
    with pytest.raises(ValidationAppError) as exc:
        _run_model(blank)
    assert all(c in exc.value.message for c in REQUIRED)
    with pytest.raises(ValidationAppError):
        _wdbc_model_inputs({**VALID, "grade": None})
    assert _wdbc_model_inputs(VALID)["stage"] == "II"


def test_the_real_model_scores_a_fully_recorded_patient(client, db):
    # no fake model: the real WDBC artifact + mapping, so a refusal rule that is too strict would show up here
    set_prediction_model(None)
    r = client.post("/predictions/run", json={"patientId": "PT-1"}, headers=_doctor_headers(client))
    assert r.status_code == 201, r.text
    assert "heuristic survival/recurrence" in r.json()["data"]["model"]
    assert len(db("SELECT * FROM prediction_runs", fetch=True)) == 1
