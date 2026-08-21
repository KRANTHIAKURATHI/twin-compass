import json

from tests.conftest import auth_headers

from app import models
from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD


def _admin_headers(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def _latest_audit_row(db_session, action: str):
    return (
        db_session.query(models.AuditLogEntry)
        .filter(models.AuditLogEntry.action == action)
        .order_by(models.AuditLogEntry.time.desc())
        .first()
    )


def test_update_patient_logs_before_after(client, db_session):
    headers = _admin_headers(client)
    resp = client.post("/patients", json={"name": "Audit Subject", "email": "audit@example.com"}, headers=headers)
    patient_id = resp.json()["data"]["id"]

    resp = client.patch(f"/patients/{patient_id}", json={"name": "Audit Subject Renamed"}, headers=headers)
    assert resp.status_code == 200

    row = _latest_audit_row(db_session, "update_patient")
    assert row is not None
    assert row.actor_role == "admin"
    assert row.actor == DEFAULT_ADMIN_EMAIL
    assert row.before["name"] == "Audit Subject"
    assert row.after["name"] == "Audit Subject Renamed"


def test_delete_patient_logs_before_only(client, db_session):
    headers = _admin_headers(client)
    resp = client.post("/patients", json={"name": "Deletable", "email": "deletable@example.com"}, headers=headers)
    patient_id = resp.json()["data"]["id"]

    resp = client.delete(f"/patients/{patient_id}", headers=headers)
    assert resp.status_code == 200

    row = _latest_audit_row(db_session, "delete_patient")
    assert row is not None
    assert row.actor_role == "admin"
    assert row.before["name"] == "Deletable"
    assert row.after is None


def test_create_patient_logs_after_only(client, db_session):
    headers = _admin_headers(client)
    resp = client.post("/patients", json={"name": "Created", "email": "created@example.com"}, headers=headers)
    assert resp.status_code == 200

    row = _latest_audit_row(db_session, "create_patient")
    assert row is not None
    assert row.actor_role == "admin"
    assert row.before is None
    assert row.after["name"] == "Created"


def test_login_logs_actor_role_with_no_before_after(client, db_session):
    resp = client.post("/auth/login", json={"email": DEFAULT_ADMIN_EMAIL, "password": DEFAULT_ADMIN_PASSWORD})
    assert resp.status_code == 200

    row = _latest_audit_row(db_session, "login")
    assert row is not None
    assert row.actor_role == "admin"
    assert row.before is None
    assert row.after is None


def test_upload_document_logs_actor_role_and_after(client, db_session):
    headers = _admin_headers(client)
    resp = client.post("/patients", json={"name": "Audit Doc Patient", "email": "audit-doc@example.com"}, headers=headers)
    patient_id = resp.json()["data"]["id"]

    resp = client.post("/documents", json={"name": "AuditScan.pdf", "size": 4096, "patientId": patient_id}, headers=headers)
    assert resp.status_code == 200

    row = _latest_audit_row(db_session, "upload_document")
    assert row is not None
    assert row.actor_role == "admin"
    assert row.before is None
    assert row.after["name"] == "AuditScan.pdf"


def test_ocr_extract_logs_status_transition_without_secrets(client, db_session):
    headers = _admin_headers(client)
    resp = client.post("/patients", json={"name": "OCR Audit Patient", "email": "ocr-audit@example.com"}, headers=headers)
    patient_id = resp.json()["data"]["id"]
    resp = client.post("/documents", json={"name": "OcrAudit.pdf", "size": 4096, "patientId": patient_id}, headers=headers)
    doc_id = resp.json()["data"]["id"]

    resp = client.post(f"/ocr/{doc_id}/extract", headers=headers)
    assert resp.status_code == 200

    row = _latest_audit_row(db_session, "ocr_extract")
    assert row is not None
    assert row.actor_role == "admin"
    assert row.before == {"status": "Pending OCR"}
    assert row.after["status"] == "Needs review"

    # No audit row anywhere should ever contain a password/token/secret value.
    serialized = json.dumps(
        [
            {"before": r.before, "after": r.after}
            for r in db_session.query(models.AuditLogEntry).all()
        ]
    ).lower()
    for forbidden in ("password", "accesstoken", "resettoken", "secret", "jwt"):
        assert forbidden not in serialized
