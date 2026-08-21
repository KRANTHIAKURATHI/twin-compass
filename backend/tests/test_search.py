from tests.conftest import auth_headers, register_user

from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD


def _admin_headers(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def _create_patient(client, headers, **overrides):
    payload = {"name": "Searchable Patient", "email": "searchable@example.com"}
    payload.update(overrides)
    resp = client.post("/patients", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_patient_search_finds_own_record_only(client):
    admin = _admin_headers(client)
    own = _create_patient(client, admin, name="Searchable Owner", email="search-owner@example.com")
    other = _create_patient(client, admin, name="Searchable Other", email="search-other@example.com")

    register_user(client, "search-owner@example.com", "Password123!", "patient")
    patient_headers = auth_headers(client, "search-owner@example.com", "Password123!")

    resp = client.get("/search", params={"q": "Searchable"}, headers=patient_headers)
    assert resp.status_code == 200
    body = resp.json()
    patient_ids = [p["id"] for p in body["patients"]]
    assert own["id"] in patient_ids
    assert other["id"] not in patient_ids


def test_patient_cannot_search_another_patients_documents(client):
    admin = _admin_headers(client)
    own = _create_patient(client, admin, name="Doc Owner", email="doc-owner@example.com")
    other = _create_patient(client, admin, name="Doc Other", email="doc-other@example.com")

    client.post("/documents", json={"name": "OwnerScanReport", "size": 1024, "patientId": own["id"]}, headers=admin)
    client.post("/documents", json={"name": "OtherScanReport", "size": 1024, "patientId": other["id"]}, headers=admin)

    register_user(client, "doc-owner@example.com", "Password123!", "patient")
    patient_headers = auth_headers(client, "doc-owner@example.com", "Password123!")

    resp = client.get("/search", params={"q": "ScanReport"}, headers=patient_headers)
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()["documents"]]
    assert "OwnerScanReport" in names
    assert "OtherScanReport" not in names


def test_doctor_search_sees_all_matching_patients(client):
    admin = _admin_headers(client)
    p1 = _create_patient(client, admin, name="DoctorSearchable One", email="ds1@example.com")
    p2 = _create_patient(client, admin, name="DoctorSearchable Two", email="ds2@example.com")

    register_user(client, "doc-search@example.com", "Password123!", "doctor")
    doctor_headers = auth_headers(client, "doc-search@example.com", "Password123!")

    resp = client.get("/search", params={"q": "DoctorSearchable"}, headers=doctor_headers)
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()["patients"]}
    assert {p1["id"], p2["id"]} <= ids


def test_admin_search_sees_all_matching_patients(client):
    admin = _admin_headers(client)
    p = _create_patient(client, admin, name="AdminSearchable", email="adminsearch@example.com")

    resp = client.get("/search", params={"q": "AdminSearchable"}, headers=admin)
    assert resp.status_code == 200
    ids = {p_["id"] for p_ in resp.json()["patients"]}
    assert p["id"] in ids


def test_researcher_search_never_returns_patient_data(client):
    admin = _admin_headers(client)
    _create_patient(client, admin, name="ResearcherTarget", email="researcher-target@example.com")

    register_user(client, "researcher1@example.com", "Password123!", "researcher")
    researcher_headers = auth_headers(client, "researcher1@example.com", "Password123!")

    resp = client.get("/search", params={"q": "ResearcherTarget"}, headers=researcher_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["patients"] == []
    assert body["documents"] == []
    assert body["reports"] == []
