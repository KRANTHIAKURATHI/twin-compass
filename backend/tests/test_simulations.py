"""Treatment simulation endpoints: attachment correctness, isolation,
ownership, audit, promotion, explainability."""

from tests.conftest import auth_headers, register_user

from app import models
from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD

_REGIMEN = "AC-T (Doxorubicin/Cyclophosphamide + Paclitaxel)"

_PATIENT = {
    "name": "Sim Subject", "email": "sim-subject@example.com", "age": 58, "stage": "III",
    "grade": 3, "ki67": 40, "nodesInvolved": 5, "tumorSizeMm": 35,
    "erStatus": "Positive", "prStatus": "Positive", "her2Status": "Negative",
}

_DRAFT = {"name": "Aggressive chemo", "regimen": _REGIMEN, "dosage": "60 mg/m²",
          "durationWeeks": 12, "notes": "Considered at MDT."}


def _admin(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def _patient(client, headers, payload=None):
    resp = client.post("/patients", json=payload or _PATIENT, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _save(client, headers, patient_id, draft=None):
    resp = client.post(f"/simulations?patient_id={patient_id}", json=draft or _DRAFT, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_run_returns_every_regimen_and_persists_nothing(client):
    headers = _admin(client)
    p = _patient(client, headers)
    body = client.post("/simulations/run", json={"patientId": p["id"]}, headers=headers).json()

    assert body["patientId"] == p["id"]
    assert len(body["scenarios"]) == 6
    assert sum(1 for s in body["scenarios"] if s["recommended"]) == 1
    assert client.get("/simulations", headers=headers).json() == []


def test_run_requires_a_real_patient(client):
    headers = _admin(client)
    assert client.post("/simulations/run", json={}, headers=headers).status_code == 400
    assert client.post("/simulations/run", json={"patientId": "nope"}, headers=headers).status_code == 404


def test_save_attaches_the_simulation_to_the_named_patient(client):
    """Regression test: save previously fell back to `Patient.query.first()`,
    attaching the simulation to an arbitrary patient."""
    headers = _admin(client)
    first = _patient(client, headers, {"name": "Sim First", "email": "sim-first@example.com"})
    target = _patient(client, headers)

    saved = _save(client, headers, target["id"])
    assert saved["patientId"] == target["id"]
    assert saved["patientId"] != first["id"]
    assert saved["patient"] == _PATIENT["name"]


def test_save_without_a_patient_id_is_400_not_a_silent_guess(client):
    headers = _admin(client)
    _patient(client, headers)
    resp = client.post("/simulations", json=_DRAFT, headers=headers)
    assert resp.status_code == 400
    assert "patient_id" in resp.json()["detail"]
    assert client.get("/simulations", headers=headers).json() == []


def test_save_against_a_missing_patient_is_404(client):
    headers = _admin(client)
    assert client.post("/simulations?patient_id=nope", json=_DRAFT, headers=headers).status_code == 404


def test_save_against_a_deleted_patient_is_404(client):
    headers = _admin(client)
    p = _patient(client, headers)
    client.delete(f"/patients/{p['id']}", headers=headers)
    assert client.post(f"/simulations?patient_id={p['id']}", json=_DRAFT, headers=headers).status_code == 404


def test_saved_simulation_records_the_selected_and_compared_regimens(client):
    headers = _admin(client)
    p = _patient(client, headers)
    saved = _save(client, headers, p["id"])

    assert saved["selected"] == _REGIMEN
    assert _REGIMEN not in saved["compared"]
    assert len(saved["compared"]) == 5
    assert saved["decision"] == "Under review"
    assert saved["model"]


def test_save_tags_the_current_twin_version(client):
    headers = _admin(client)
    p = _patient(client, headers)
    client.post(f"/digital-twins/{p['id']}/resync", headers=headers)
    assert _save(client, headers, p["id"])["twinVersion"] == "v2"


def test_save_is_audited_with_the_patient_and_regimen(client, db_session):
    headers = _admin(client)
    p = _patient(client, headers)
    saved = _save(client, headers, p["id"])

    row = (
        db_session.query(models.AuditLogEntry)
        .filter(models.AuditLogEntry.action == "save_simulation")
        .order_by(models.AuditLogEntry.time.desc())
        .first()
    )
    assert row is not None
    assert row.after["patient_id"] == p["id"]
    assert row.after["id"] == saved["id"]
    assert row.after["selected"] == _REGIMEN


def test_duplicate_copies_the_scenario_onto_the_same_patient(client):
    headers = _admin(client)
    p = _patient(client, headers)
    original = _save(client, headers, p["id"])

    clone = client.post(f"/simulations/{original['id']}/duplicate", headers=headers).json()["data"]
    assert clone["id"] != original["id"]
    assert clone["patientId"] == original["patientId"]
    assert clone["selected"] == original["selected"]
    assert original["id"] in clone["notes"]


def test_duplicate_is_audited(client, db_session):
    headers = _admin(client)
    p = _patient(client, headers)
    original = _save(client, headers, p["id"])
    clone = client.post(f"/simulations/{original['id']}/duplicate", headers=headers).json()["data"]

    row = (
        db_session.query(models.AuditLogEntry)
        .filter(models.AuditLogEntry.action == "duplicate_simulation")
        .first()
    )
    assert row is not None
    assert row.before["id"] == original["id"]
    assert row.after["id"] == clone["id"]


def test_duplicating_a_missing_simulation_is_404(client):
    headers = _admin(client)
    assert client.post("/simulations/nope/duplicate", headers=headers).status_code == 404


def test_promote_records_the_decision_and_builds_the_treatment_plan(client):
    headers = _admin(client)
    p = _patient(client, headers)
    saved = _save(client, headers, p["id"])

    resp = client.post(f"/simulations/{saved['id']}/promote", json={"notes": "MDT agreed"}, headers=headers)
    assert resp.status_code == 200
    assert _REGIMEN in resp.json()["message"]

    assert client.get(f"/simulations/{saved['id']}", headers=headers).json()["decision"] == "Promoted to plan"
    plan = client.get(f"/patients/{p['id']}/treatment-plan", headers=headers).json()
    assert plan["regimen"] == _REGIMEN
    assert plan["medications"]  # composition filled in, not an empty list
    assert client.get(f"/patients/{p['id']}", headers=headers).json()["currentTreatment"] == _REGIMEN


def test_promote_is_audited_with_the_decision_transition(client, db_session):
    headers = _admin(client)
    p = _patient(client, headers)
    saved = _save(client, headers, p["id"])
    client.post(f"/simulations/{saved['id']}/promote", json={"notes": "MDT agreed"}, headers=headers)

    row = (
        db_session.query(models.AuditLogEntry)
        .filter(models.AuditLogEntry.action == "promote_simulation")
        .first()
    )
    assert row is not None
    assert row.before["decision"] == "Under review"
    assert row.after["decision"] == "Promoted to plan"
    assert row.after["patient_id"] == p["id"]
    assert row.after["regimen"] == _REGIMEN


def test_promoting_a_missing_simulation_is_404(client):
    headers = _admin(client)
    assert client.post("/simulations/nope/promote", headers=headers).status_code == 404


def test_explainability_compares_the_regimen_against_active_surveillance(client):
    headers = _admin(client)
    p = _patient(client, headers)
    saved = _save(client, headers, p["id"])

    body = client.get(f"/simulations/{saved['id']}/explainability", headers=headers).json()
    assert body["simulationId"] == saved["id"]
    assert body["patientId"] == p["id"]
    assert body["regimen"] == _REGIMEN
    assert body["simulatedSurvival"] > body["baselineSurvival"]
    assert body["features"]
    assert any(f["contribution"] != 0 for f in body["features"])
    assert body["model"]["isValidated"] is False
    assert "simulated" in body["caveat"].lower()


def test_explainability_avoids_overclaiming_language(client):
    headers = _admin(client)
    p = _patient(client, headers)
    saved = _save(client, headers, p["id"])
    text = client.get(f"/simulations/{saved['id']}/explainability", headers=headers).text.lower()
    for forbidden in ("guaranteed", "definitive", "clinically proven"):
        assert forbidden not in text


def test_unauthenticated_access_is_401(client):
    assert client.get("/simulations").status_code == 401
    assert client.post("/simulations/run", json={"patientId": "x"}).status_code == 401
    assert client.post("/simulations?patient_id=x", json=_DRAFT).status_code == 401


def test_patient_sees_only_their_own_simulations(client):
    headers = _admin(client)
    other = _patient(client, headers)
    own = _patient(client, headers, {"name": "Sim Self", "email": "sim-self@example.com"})
    _save(client, headers, other["id"])
    mine = _save(client, headers, own["id"])

    register_user(client, "sim-self@example.com", "Password123!", "patient")
    self_headers = auth_headers(client, "sim-self@example.com", "Password123!")
    rows = client.get("/simulations", headers=self_headers).json()
    assert [r["id"] for r in rows] == [mine["id"]]


def test_patient_cannot_read_another_patients_simulation(client):
    headers = _admin(client)
    other = _patient(client, headers)
    _patient(client, headers, {"name": "Sim Nosy", "email": "sim-nosy@example.com"})
    saved = _save(client, headers, other["id"])

    register_user(client, "sim-nosy@example.com", "Password123!", "patient")
    nosy = auth_headers(client, "sim-nosy@example.com", "Password123!")
    assert client.get(f"/simulations/{saved['id']}", headers=nosy).status_code == 403
    assert client.get(f"/simulations/{saved['id']}/explainability", headers=nosy).status_code == 403


def test_patient_role_cannot_save_duplicate_or_promote(client):
    headers = _admin(client)
    own = _patient(client, headers, {"name": "Sim RO", "email": "sim-ro@example.com"})
    saved = _save(client, headers, own["id"])

    register_user(client, "sim-ro@example.com", "Password123!", "patient")
    ro = auth_headers(client, "sim-ro@example.com", "Password123!")

    assert client.post(f"/simulations?patient_id={own['id']}", json=_DRAFT, headers=ro).status_code == 403
    assert client.post(f"/simulations/{saved['id']}/duplicate", headers=ro).status_code == 403
    assert client.post(f"/simulations/{saved['id']}/promote", headers=ro).status_code == 403


def test_simulating_for_one_patient_never_mutates_another(client):
    """Isolation: saving and promoting for patient A must leave patient B's
    record, twin and predictions untouched."""
    headers = _admin(client)
    a = _patient(client, headers)
    b = _patient(client, headers, {"name": "Sim Bystander", "email": "sim-bystander@example.com"})
    before = client.get(f"/digital-twins/{b['id']}/state", headers=headers).json()

    saved = _save(client, headers, a["id"])
    client.post(f"/simulations/{saved['id']}/promote", headers=headers)

    after = client.get(f"/digital-twins/{b['id']}/state", headers=headers).json()
    assert after["currentTreatment"] == before["currentTreatment"]
    assert after["survivalProbability"] == before["survivalProbability"]
    assert after["risk"] == before["risk"]
    assert after["version"] == before["version"]
    assert after["lastUpdated"] == before["lastUpdated"]
    assert client.get(f"/predictions/{b['id']}/history", headers=headers).json() == []
