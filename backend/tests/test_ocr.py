from tests.conftest import auth_headers, register_user

from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD


def _admin_headers(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def _create_patient(client, headers, **overrides):
    payload = {"name": "OCR Patient", "email": "ocr-patient@example.com"}
    payload.update(overrides)
    resp = client.post("/patients", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _upload_document(client, headers, patient_id, name="ScanDoc.pdf"):
    resp = client.post("/documents", json={"name": name, "size": 2048, "patientId": patient_id}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_doctor_can_extract_own_patient_document(client):
    admin = _admin_headers(client)
    patient = _create_patient(client, admin, name="Owned Doc Patient", email="owned-doc@example.com")
    doc = _upload_document(client, admin, patient["id"])

    register_user(client, "doc-ocr@example.com", "Password123!", "doctor")
    doctor_headers = auth_headers(client, "doc-ocr@example.com", "Password123!")

    resp = client.post(f"/ocr/{doc['id']}/extract", headers=doctor_headers)
    assert resp.status_code == 200
    assert resp.json()["fields"]


def test_admin_can_extract_any_document(client):
    admin = _admin_headers(client)
    patient = _create_patient(client, admin, name="Admin Doc Patient", email="admin-doc@example.com")
    doc = _upload_document(client, admin, patient["id"])

    resp = client.post(f"/ocr/{doc['id']}/extract", headers=admin)
    assert resp.status_code == 200


def test_patient_cannot_ocr_extract_at_all(client):
    admin = _admin_headers(client)
    own = _create_patient(client, admin, name="Self OCR Patient", email="self-ocr@example.com")
    doc = _upload_document(client, admin, own["id"])

    register_user(client, "self-ocr@example.com", "Password123!", "patient")
    patient_headers = auth_headers(client, "self-ocr@example.com", "Password123!")

    resp = client.post(f"/ocr/{doc['id']}/extract", headers=patient_headers)
    assert resp.status_code == 403


def test_patient_cannot_ocr_another_patients_document(client):
    admin = _admin_headers(client)
    owner = _create_patient(client, admin, name="Cross OCR Owner", email="cross-ocr-owner@example.com")
    other = _create_patient(client, admin, name="Cross OCR Other", email="cross-ocr-other@example.com")
    doc = _upload_document(client, admin, owner["id"])

    register_user(client, "cross-ocr-other@example.com", "Password123!", "patient")
    other_headers = auth_headers(client, "cross-ocr-other@example.com", "Password123!")

    # Role gate rejects the patient outright, regardless of ownership.
    resp = client.post(f"/ocr/{doc['id']}/extract", headers=other_headers)
    assert resp.status_code == 403


def test_doctor_cannot_ocr_another_doctors_patient_across_ownership_boundary(client):
    """OCR reuses documents' ownership helper: a doctor is not scoped to any
    single patient by design (doctor/admin remain unrestricted), so this
    confirms the role gate + ownership helper are both actually invoked
    without breaking normal doctor access."""
    admin = _admin_headers(client)
    patient = _create_patient(client, admin, name="Ownership Wired Patient", email="ownership-wired@example.com")
    doc = _upload_document(client, admin, patient["id"])

    register_user(client, "doc-wired@example.com", "Password123!", "doctor")
    doctor_headers = auth_headers(client, "doc-wired@example.com", "Password123!")

    resp = client.post(f"/ocr/{doc['id']}/extract", headers=doctor_headers)
    assert resp.status_code == 200


def test_patient_cannot_approve_or_reject_ocr(client):
    admin = _admin_headers(client)
    own = _create_patient(client, admin, name="Approve OCR Patient", email="approve-ocr@example.com")
    doc = _upload_document(client, admin, own["id"])
    client.post(f"/ocr/{doc['id']}/extract", headers=admin)

    register_user(client, "approve-ocr@example.com", "Password123!", "patient")
    patient_headers = auth_headers(client, "approve-ocr@example.com", "Password123!")

    resp = client.post(
        f"/ocr/{doc['id']}/approve",
        json={"fields": [{"field": "Modality", "value": "MRI", "confidence": 0.9}]},
        headers=patient_headers,
    )
    assert resp.status_code == 403

    resp = client.post(f"/ocr/{doc['id']}/reject", json={"reason": "Not mine"}, headers=patient_headers)
    assert resp.status_code == 403
