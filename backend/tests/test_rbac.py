from tests.conftest import auth_headers, register_user

from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD


def _admin_headers(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def _create_patient(client, headers, **overrides):
    payload = {"name": "Jane Doe", "email": "jane@example.com"}
    payload.update(overrides)
    resp = client.post("/patients", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_patient_role_cannot_write(client):
    admin = _admin_headers(client)
    register_user(client, "patient1@example.com", "Password123!", "patient")
    patient_headers = auth_headers(client, "patient1@example.com", "Password123!")

    resp = client.post("/patients", json={"name": "New", "email": "new@example.com"}, headers=patient_headers)
    assert resp.status_code == 403

    p = _create_patient(client, admin, name="Existing", email="existing@example.com")
    resp = client.patch(f"/patients/{p['id']}", json={"name": "Changed"}, headers=patient_headers)
    assert resp.status_code == 403

    resp = client.delete(f"/patients/{p['id']}", headers=patient_headers)
    assert resp.status_code == 403


def test_patient_role_sees_only_own_record(client):
    admin = _admin_headers(client)
    own = _create_patient(client, admin, name="Own Record", email="patient2@example.com")
    other = _create_patient(client, admin, name="Other Record", email="someone-else@example.com")

    register_user(client, "patient2@example.com", "Password123!", "patient")
    patient_headers = auth_headers(client, "patient2@example.com", "Password123!")

    resp = client.get(f"/patients/{own['id']}", headers=patient_headers)
    assert resp.status_code == 200

    resp = client.get(f"/patients/{other['id']}", headers=patient_headers)
    assert resp.status_code == 403

    resp = client.get("/patients", headers=patient_headers)
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.json()]
    assert ids == [own["id"]]


def test_doctor_role_unrestricted(client):
    admin = _admin_headers(client)
    p = _create_patient(client, admin, name="Doctor Visible", email="docvis@example.com")

    register_user(client, "doc1@example.com", "Password123!", "doctor")
    doctor_headers = auth_headers(client, "doc1@example.com", "Password123!")

    resp = client.get(f"/patients/{p['id']}", headers=doctor_headers)
    assert resp.status_code == 200

    resp = client.patch(f"/patients/{p['id']}", json={"name": "Renamed"}, headers=doctor_headers)
    assert resp.status_code == 200
