from tests.conftest import auth_headers

from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD


def _admin_headers(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def _create_patient(client, headers, **overrides):
    payload = {"name": "Jane Doe", "email": "jane@example.com"}
    payload.update(overrides)
    resp = client.post("/patients", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_create_patient_assigns_sequential_codes(client):
    headers = _admin_headers(client)
    p1 = _create_patient(client, headers, name="Patient One", email="one@example.com")
    p2 = _create_patient(client, headers, name="Patient Two", email="two@example.com")
    assert p1["patientCode"] == "PT-1000"
    assert p2["patientCode"] == "PT-1001"


def test_medical_history_fields_round_trip(client):
    headers = _admin_headers(client)
    p = _create_patient(
        client, headers, name="History Patient", email="hist@example.com",
        comorbidities=["Diabetes"], allergies=["Penicillin"], currentMedications=["Metformin"],
        familyHistory="Mother had breast cancer", smokingStatus="Former", alcoholUse="Occasional",
        surgicalHistory=["Appendectomy"],
    )
    assert p["comorbidities"] == ["Diabetes"]
    assert p["allergies"] == ["Penicillin"]
    assert p["currentMedications"] == ["Metformin"]
    assert p["familyHistory"] == "Mother had breast cancer"
    assert p["smokingStatus"] == "Former"
    assert p["alcoholUse"] == "Occasional"
    assert p["surgicalHistory"] == ["Appendectomy"]


def test_delete_soft_deletes(client):
    headers = _admin_headers(client)
    p = _create_patient(client, headers, name="To Delete", email="del@example.com")

    resp = client.delete(f"/patients/{p['id']}", headers=headers)
    assert resp.status_code == 200

    resp = client.get(f"/patients/{p['id']}", headers=headers)
    assert resp.status_code == 404

    resp = client.get("/patients", headers=headers)
    assert all(row["id"] != p["id"] for row in resp.json())
