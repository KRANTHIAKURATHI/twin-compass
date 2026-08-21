"""Prediction endpoints: persistence, ownership, explainability, provenance."""

from tests.conftest import auth_headers, register_user

from app import models
from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD

_HIGH_RISK = {
    "name": "High Risk", "email": "pred-high@example.com", "age": 71, "stage": "IV", "grade": 3,
    "ki67": 80, "nodesInvolved": 12, "tumorSizeMm": 62,
    "erStatus": "Negative", "prStatus": "Negative", "her2Status": "Positive",
}
_LOW_RISK = {
    "name": "Low Risk", "email": "pred-low@example.com", "age": 41, "stage": "I", "grade": 1,
    "ki67": 5, "nodesInvolved": 0, "tumorSizeMm": 8,
    "erStatus": "Positive", "prStatus": "Positive", "her2Status": "Negative",
}


def _admin(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def _patient(client, headers, payload):
    resp = client.post("/patients", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _run(client, headers, patient_id):
    resp = client.post("/predictions/run", json={"patientId": patient_id}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_run_persists_a_prediction_retrievable_by_patient(client):
    headers = _admin(client)
    p = _patient(client, headers, _HIGH_RISK)
    created = _run(client, headers, p["id"])

    latest = client.get(f"/predictions/{p['id']}", headers=headers).json()
    assert latest["id"] == created["id"]
    assert latest["model"]
    assert 0.0 <= latest["survival"] <= 1.0
    assert 0.0 <= latest["recurrence"] <= 1.0


def test_run_updates_the_patients_derived_risk(client):
    """The patient row and the prediction must not disagree."""
    headers = _admin(client)
    p = _patient(client, headers, _HIGH_RISK)
    run = _run(client, headers, p["id"])

    refreshed = client.get(f"/patients/{p['id']}", headers=headers).json()
    assert refreshed["survivalProbability"] == run["survival"]
    assert refreshed["risk"] in ("low", "moderate", "high")


def test_run_tags_the_prediction_with_the_latest_twin_version(client):
    headers = _admin(client)
    p = _patient(client, headers, _LOW_RISK)
    first = _run(client, headers, p["id"])
    assert first["twinVersion"] == "v1"  # created with the patient

    client.post(f"/digital-twins/{p['id']}/resync", headers=headers)
    later = _run(client, headers, p["id"])
    assert later["twinVersion"] == "v2"


def test_repeat_runs_on_an_unchanged_patient_are_reproducible(client):
    headers = _admin(client)
    p = _patient(client, headers, _HIGH_RISK)
    first = _run(client, headers, p["id"])
    second = _run(client, headers, p["id"])

    assert first["id"] != second["id"]  # separate audit-able rows
    for field in ("survival", "recurrence", "confidence", "response", "status", "model"):
        assert first[field] == second[field]


def test_history_and_confidence_trend_are_ordered_oppositely(client):
    headers = _admin(client)
    p = _patient(client, headers, _LOW_RISK)
    _run(client, headers, p["id"])
    _run(client, headers, p["id"])

    history = client.get(f"/predictions/{p['id']}/history", headers=headers).json()
    trend = client.get(f"/predictions/{p['id']}/confidence-trend", headers=headers).json()
    assert len(history) >= 2
    assert len(trend) == len(history)
    assert [h["date"] for h in history] == sorted([h["date"] for h in history], reverse=True)
    assert [t["date"] for t in trend] == sorted([t["date"] for t in trend])


def test_no_prediction_yet_returns_null_not_an_error(client):
    headers = _admin(client)
    p = _patient(client, headers, {"name": "Fresh", "email": "pred-fresh@example.com"})
    # A patient is created with a twin version but no prediction run.
    db_rows = client.get(f"/predictions/{p['id']}/history", headers=headers).json()
    resp = client.get(f"/predictions/{p['id']}", headers=headers)
    assert resp.status_code == 200
    assert (resp.json() is None) == (len(db_rows) == 0)


def test_missing_patient_is_404_everywhere(client):
    headers = _admin(client)
    for path in ("", "/history", "/confidence-trend", "/explainability", "/explainability/summary"):
        resp = client.get(f"/predictions/no-such-patient{path}", headers=headers)
        assert resp.status_code == 404, path
    assert client.post("/predictions/run", json={"patientId": "no-such-patient"}, headers=headers).status_code == 404


def test_unauthenticated_access_is_401(client):
    assert client.get("/predictions/anything").status_code == 401
    assert client.post("/predictions/run", json={"patientId": "anything"}).status_code == 401


def test_patient_cannot_read_another_patients_prediction(client):
    headers = _admin(client)
    other = _patient(client, headers, _HIGH_RISK)
    _patient(client, headers, {"name": "Nosy", "email": "pred-nosy@example.com"})
    _run(client, headers, other["id"])

    register_user(client, "pred-nosy@example.com", "Password123!", "patient")
    nosy = auth_headers(client, "pred-nosy@example.com", "Password123!")

    for path in ("", "/history", "/confidence-trend", "/explainability"):
        assert client.get(f"/predictions/{other['id']}{path}", headers=nosy).status_code == 403, path


def test_patient_can_read_their_own_prediction(client):
    headers = _admin(client)
    own = _patient(client, headers, {**_LOW_RISK, "email": "pred-self@example.com"})
    _run(client, headers, own["id"])

    register_user(client, "pred-self@example.com", "Password123!", "patient")
    self_headers = auth_headers(client, "pred-self@example.com", "Password123!")
    assert client.get(f"/predictions/{own['id']}", headers=self_headers).status_code == 200


def test_patient_role_cannot_trigger_a_prediction_run(client):
    headers = _admin(client)
    own = _patient(client, headers, {**_LOW_RISK, "email": "pred-norun@example.com"})
    register_user(client, "pred-norun@example.com", "Password123!", "patient")
    self_headers = auth_headers(client, "pred-norun@example.com", "Password123!")
    resp = client.post("/predictions/run", json={"patientId": own["id"]}, headers=self_headers)
    assert resp.status_code == 403


def test_explainability_differs_between_two_different_patients(client):
    """Regression guard: attributions were previously identical for every
    patient because the shared severity factor cancelled during normalization."""
    headers = _admin(client)
    high = _patient(client, headers, _HIGH_RISK)
    low = _patient(client, headers, _LOW_RISK)

    a = client.get(f"/predictions/{high['id']}/explainability", headers=headers).json()
    b = client.get(f"/predictions/{low['id']}/explainability", headers=headers).json()
    assert {r["feature"]: r["weight"] for r in a} != {r["feature"]: r["weight"] for r in b}


def test_explainability_tracks_an_edit_to_the_patient_record(client):
    headers = _admin(client)
    p = _patient(client, headers, _HIGH_RISK)
    before = {r["feature"]: r["weight"] for r in
              client.get(f"/predictions/{p['id']}/explainability", headers=headers).json()}

    # `name` is included because PatientInput.name is required, so PATCH cannot
    # currently accept a genuinely partial body.
    patch = client.patch(
        f"/patients/{p['id']}",
        json={"name": _HIGH_RISK["name"], "nodesInvolved": 0, "stage": "I"},
        headers=headers,
    )
    assert patch.status_code == 200, patch.text
    after = {r["feature"]: r["weight"] for r in
             client.get(f"/predictions/{p['id']}/explainability", headers=headers).json()}

    assert after["Lymph nodes involved"] < before["Lymph nodes involved"]
    assert after["Stage"] < before["Stage"]


def test_explainability_summary_states_its_provenance_and_caveat(client):
    headers = _admin(client)
    p = _patient(client, headers, _HIGH_RISK)
    body = client.get(f"/predictions/{p['id']}/explainability/summary", headers=headers).json()

    assert body["patientId"] == p["id"]
    assert body["features"]
    assert body["model"]["isValidated"] is False
    assert body["model"]["modelType"] == "development"
    assert "current patient record" in body["computedFrom"]
    assert "not clinically validated" in body["caveat"].lower()


def test_explainability_response_avoids_overclaiming_language(client):
    headers = _admin(client)
    p = _patient(client, headers, _HIGH_RISK)
    text = client.get(f"/predictions/{p['id']}/explainability/summary", headers=headers).text.lower()
    for forbidden in ("guaranteed", "definitive", "clinically proven"):
        assert forbidden not in text


def test_run_is_audited_with_the_stored_outputs(client, db_session):
    headers = _admin(client)
    p = _patient(client, headers, _HIGH_RISK)
    run = _run(client, headers, p["id"])

    row = (
        db_session.query(models.AuditLogEntry)
        .filter(models.AuditLogEntry.action == "run_prediction")
        .order_by(models.AuditLogEntry.time.desc())
        .first()
    )
    assert row is not None
    assert row.actor == DEFAULT_ADMIN_EMAIL
    assert row.actor_role == "admin"
    assert row.after["patient_id"] == p["id"]
    assert row.after["survival"] == run["survival"]
    assert row.after["model"] == run["model"]
