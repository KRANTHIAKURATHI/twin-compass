from tests.conftest import auth_headers, register_user

from app import models
from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD


def _admin_headers(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def _create_patient(client, headers, **overrides):
    payload = {"name": "Report Patient", "email": "report-patient@example.com"}
    payload.update(overrides)
    resp = client.post("/patients", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _generate_report(client, headers, patient_id):
    resp = client.post("/reports/generate", json={"patientId": patient_id, "reportType": "Clinical summary"}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_patient_cannot_export_another_patients_report(client, db_session):
    admin = _admin_headers(client)
    owner = _create_patient(client, admin, name="Report Owner", email="report-owner@example.com")
    other = _create_patient(client, admin, name="Report Other", email="report-other@example.com")
    report = _generate_report(client, admin, other["id"])

    register_user(client, "report-owner@example.com", "Password123!", "patient")
    owner_headers = auth_headers(client, "report-owner@example.com", "Password123!")

    resp = client.post("/reports/export", json={"format": "pdf", "reportId": report["id"]}, headers=owner_headers)
    assert resp.status_code == 403

    # downloads counter and DownloadRecord must not have been created
    db_session.expire_all()
    refreshed = db_session.get(models.SavedReport, report["id"])
    assert refreshed.downloads == 0
    assert db_session.query(models.DownloadRecord).filter(models.DownloadRecord.report_id == report["id"]).count() == 0


def test_patient_can_export_own_report(client, db_session):
    admin = _admin_headers(client)
    owner = _create_patient(client, admin, name="Self Report Owner", email="self-report-owner@example.com")
    report = _generate_report(client, admin, owner["id"])

    register_user(client, "self-report-owner@example.com", "Password123!", "patient")
    owner_headers = auth_headers(client, "self-report-owner@example.com", "Password123!")

    resp = client.post("/reports/export", json={"format": "pdf", "reportId": report["id"]}, headers=owner_headers)
    assert resp.status_code == 200

    db_session.expire_all()
    refreshed = db_session.get(models.SavedReport, report["id"])
    assert refreshed.downloads == 1


def test_patient_cannot_download_another_patients_report(client):
    admin = _admin_headers(client)
    owner = _create_patient(client, admin, name="DL Owner", email="dl-owner@example.com")
    other = _create_patient(client, admin, name="DL Other", email="dl-other@example.com")
    report = _generate_report(client, admin, other["id"])

    register_user(client, "dl-owner@example.com", "Password123!", "patient")
    owner_headers = auth_headers(client, "dl-owner@example.com", "Password123!")

    resp = client.get(f"/reports/{report['id']}/download", headers=owner_headers)
    assert resp.status_code == 403


def test_download_history_is_scoped_to_the_calling_patient(client):
    """`GET /reports/downloads` used to return every record to any authenticated
    caller, exposing other patients' report ids and activity."""
    admin = _admin_headers(client)
    owner = _create_patient(client, admin, name="Hist Owner", email="hist-owner@example.com")
    other = _create_patient(client, admin, name="Hist Other", email="hist-other@example.com")
    own_report = _generate_report(client, admin, owner["id"])
    other_report = _generate_report(client, admin, other["id"])

    # Generate a download record for each report, as staff.
    for report_id in (own_report["id"], other_report["id"]):
        assert client.get(f"/reports/{report_id}/download", headers=admin).status_code == 200

    register_user(client, "hist-owner@example.com", "Password123!", "patient")
    owner_headers = auth_headers(client, "hist-owner@example.com", "Password123!")

    rows = client.get("/reports/downloads", headers=owner_headers).json()
    reports_seen = {r["report"] for r in rows}
    assert own_report["id"] in reports_seen
    assert other_report["id"] not in reports_seen


def test_download_history_is_unscoped_for_staff(client):
    admin = _admin_headers(client)
    a = _create_patient(client, admin, name="Staff A", email="staff-a@example.com")
    b = _create_patient(client, admin, name="Staff B", email="staff-b@example.com")
    report_a = _generate_report(client, admin, a["id"])
    report_b = _generate_report(client, admin, b["id"])
    for report_id in (report_a["id"], report_b["id"]):
        client.get(f"/reports/{report_id}/download", headers=admin)

    rows = client.get("/reports/downloads", headers=admin).json()
    reports_seen = {r["report"] for r in rows}
    assert {report_a["id"], report_b["id"]} <= reports_seen


def test_download_history_requires_authentication(client):
    assert client.get("/reports/downloads").status_code == 401
