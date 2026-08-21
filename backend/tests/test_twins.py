"""Digital twin endpoints: derived state, resync side effects, restore,
archive, ownership."""

from tests.conftest import auth_headers, register_user

from app import models
from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD

_PATIENT = {
    "name": "Twin Subject", "email": "twin-subject@example.com", "age": 63, "stage": "III",
    "grade": 3, "ki67": 45, "nodesInvolved": 6, "tumorSizeMm": 38,
    "erStatus": "Positive", "prStatus": "Negative", "her2Status": "Negative",
}


def _admin(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def _patient(client, headers, payload=None):
    resp = client.post("/patients", json=payload or _PATIENT, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_state_composes_patient_fields_version_and_model_provenance(client):
    headers = _admin(client)
    p = _patient(client, headers)
    body = client.get(f"/digital-twins/{p['id']}/state", headers=headers).json()

    assert body["patientId"] == p["id"]
    assert body["patientName"] == _PATIENT["name"]
    assert body["stage"] == "III"
    assert body["nodesInvolved"] == 6
    assert body["tumorSizeMm"] == 38
    assert body["version"] == "v1"
    assert body["derivedAt"]
    assert body["model"]["isValidated"] is False
    assert body["model"]["modelType"] == "development"
    assert "derived view" in body["caveat"].lower()


def test_state_includes_the_latest_prediction_once_one_exists(client):
    headers = _admin(client)
    p = _patient(client, headers)
    assert client.get(f"/digital-twins/{p['id']}/state", headers=headers).json()["latestPrediction"] is None

    run = client.post("/predictions/run", json={"patientId": p["id"]}, headers=headers).json()["data"]
    body = client.get(f"/digital-twins/{p['id']}/state", headers=headers).json()
    assert body["latestPrediction"]["id"] == run["id"]


def test_state_reflects_the_current_record_not_a_stale_copy(client):
    headers = _admin(client)
    p = _patient(client, headers)
    client.patch(f"/patients/{p['id']}", json={"name": _PATIENT["name"], "stage": "I", "tumorSizeMm": 6},
                 headers=headers)
    body = client.get(f"/digital-twins/{p['id']}/state", headers=headers).json()
    assert body["stage"] == "I"
    assert body["tumorSizeMm"] == 6


def test_resync_creates_a_version_a_snapshot_and_a_prediction(client, db_session):
    headers = _admin(client)
    p = _patient(client, headers)
    resp = client.post(f"/digital-twins/{p['id']}/resync", headers=headers)
    assert resp.status_code == 200
    assert "v2" in resp.json()["message"]

    versions = client.get(f"/digital-twins/{p['id']}/versions", headers=headers).json()
    snapshots = client.get(f"/digital-twins/{p['id']}/snapshots", headers=headers).json()
    predictions = client.get(f"/predictions/{p['id']}/history", headers=headers).json()

    assert [v["version"] for v in versions] == ["v2", "v1"]
    assert [s["version"] for s in snapshots] == ["v2"]
    assert len(predictions) == 1
    assert predictions[0]["twinVersion"] == "v2"


def test_resync_leaves_the_twin_synced_and_records_one_audit_entry(client, db_session):
    headers = _admin(client)
    p = _patient(client, headers)
    client.post(f"/digital-twins/{p['id']}/resync", headers=headers)

    state = client.get(f"/digital-twins/{p['id']}/state", headers=headers).json()
    assert state["twinStatus"] == "Synced"

    rows = (
        db_session.query(models.AuditLogEntry)
        .filter(models.AuditLogEntry.action == "resync_twin")
        .all()
    )
    assert len(rows) == 1
    assert rows[0].after["version"] == "v2"
    assert rows[0].after["patient_id"] == p["id"]


def test_resync_and_the_stored_prediction_agree_on_survival(client):
    """Resync writes a version, a snapshot and a prediction in one commit; the
    numbers on all of them must match."""
    headers = _admin(client)
    p = _patient(client, headers)
    client.post(f"/digital-twins/{p['id']}/resync", headers=headers)

    version = client.get(f"/digital-twins/{p['id']}/versions", headers=headers).json()[0]
    prediction = client.get(f"/predictions/{p['id']}", headers=headers).json()
    state = client.get(f"/digital-twins/{p['id']}/state", headers=headers).json()

    assert version["survival"] == prediction["survival"] == state["survivalProbability"]
    assert version["risk"] == state["risk"]


def test_restore_reverts_the_patient_to_a_previous_version(client):
    headers = _admin(client)
    p = _patient(client, headers)
    client.patch(f"/patients/{p['id']}", json={"name": _PATIENT["name"], "stage": "IV", "tumorSizeMm": 70},
                 headers=headers)
    client.post(f"/digital-twins/{p['id']}/resync", headers=headers)  # v2 captures stage IV

    client.patch(f"/patients/{p['id']}", json={"name": _PATIENT["name"], "stage": "I", "tumorSizeMm": 5},
                 headers=headers)
    resp = client.post(f"/digital-twins/{p['id']}/versions/v2/restore", headers=headers)
    assert resp.status_code == 200

    state = client.get(f"/digital-twins/{p['id']}/state", headers=headers).json()
    assert state["stage"] == "IV"
    assert state["tumorSizeMm"] == 70


def test_restoring_an_unknown_version_is_404(client):
    headers = _admin(client)
    p = _patient(client, headers)
    assert client.post(f"/digital-twins/{p['id']}/versions/v99/restore", headers=headers).status_code == 404


def test_archive_marks_the_twin_stale_and_the_latest_version_archived(client):
    headers = _admin(client)
    p = _patient(client, headers)
    assert client.post(f"/digital-twins/{p['id']}/archive", headers=headers).status_code == 200

    state = client.get(f"/digital-twins/{p['id']}/state", headers=headers).json()
    versions = client.get(f"/digital-twins/{p['id']}/versions", headers=headers).json()
    assert state["twinStatus"] == "Stale"
    assert versions[0]["status"] == "Archived"


def test_missing_patient_is_404_on_every_twin_route(client):
    headers = _admin(client)
    for path in ("/state", "/versions", "/snapshots"):
        assert client.get(f"/digital-twins/nope{path}", headers=headers).status_code == 404, path
    assert client.post("/digital-twins/nope/resync", headers=headers).status_code == 404
    assert client.post("/digital-twins/nope/archive", headers=headers).status_code == 404


def test_unauthenticated_access_is_401(client):
    assert client.get("/digital-twins").status_code == 401
    assert client.get("/digital-twins/anything/state").status_code == 401
    assert client.post("/digital-twins/anything/resync").status_code == 401


def test_patient_cannot_read_another_patients_twin(client):
    headers = _admin(client)
    other = _patient(client, headers)
    _patient(client, headers, {"name": "Twin Nosy", "email": "twin-nosy@example.com"})
    register_user(client, "twin-nosy@example.com", "Password123!", "patient")
    nosy = auth_headers(client, "twin-nosy@example.com", "Password123!")

    for path in ("/state", "/versions", "/snapshots"):
        assert client.get(f"/digital-twins/{other['id']}{path}", headers=nosy).status_code == 403, path


def test_patient_sees_only_their_own_twin_in_the_list(client):
    headers = _admin(client)
    _patient(client, headers)
    own = _patient(client, headers, {"name": "Twin Self", "email": "twin-self@example.com"})
    register_user(client, "twin-self@example.com", "Password123!", "patient")
    self_headers = auth_headers(client, "twin-self@example.com", "Password123!")

    rows = client.get("/digital-twins", headers=self_headers).json()
    assert [r["id"] for r in rows] == [own["id"]]


def test_patient_role_cannot_resync_or_archive(client):
    headers = _admin(client)
    own = _patient(client, headers, {"name": "Twin RO", "email": "twin-ro@example.com"})
    register_user(client, "twin-ro@example.com", "Password123!", "patient")
    ro = auth_headers(client, "twin-ro@example.com", "Password123!")

    assert client.post(f"/digital-twins/{own['id']}/resync", headers=ro).status_code == 403
    assert client.post(f"/digital-twins/{own['id']}/archive", headers=ro).status_code == 403


def test_resyncing_one_patient_does_not_touch_another(client):
    headers = _admin(client)
    a = _patient(client, headers)
    b = _patient(client, headers, {"name": "Twin Isolated", "email": "twin-isolated@example.com"})
    before = client.get(f"/digital-twins/{b['id']}/state", headers=headers).json()

    client.post(f"/digital-twins/{a['id']}/resync", headers=headers)

    after = client.get(f"/digital-twins/{b['id']}/state", headers=headers).json()
    assert after["version"] == before["version"]
    assert after["lastUpdated"] == before["lastUpdated"]
    assert after["survivalProbability"] == before["survivalProbability"]
    assert client.get(f"/predictions/{b['id']}/history", headers=headers).json() == []
