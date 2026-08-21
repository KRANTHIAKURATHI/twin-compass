"""Public self-registration must never be able to grant a privileged role.

`POST /auth/register` is unauthenticated, so honoring a client-supplied `role`
would let anyone mint an admin account and read every patient record. Privileged
accounts come only from the admin-only `POST /admin/users`.
"""

import pytest

from tests.conftest import auth_headers

from app import models
from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD


def _admin_headers(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


@pytest.mark.parametrize("requested", ["admin", "doctor", "researcher"])
def test_self_registration_ignores_requested_privileged_role(client, requested):
    resp = client.post(
        "/auth/register",
        json={"name": "Escalator", "email": f"{requested}-escalate@example.com",
              "password": "Secret123!", "role": requested},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["role"] == "patient"


def test_self_registered_account_is_a_patient_in_the_database(client, db_session):
    client.post("/auth/register", json={"name": "DB Check", "email": "dbcheck@example.com",
                                        "password": "Secret123!", "role": "admin"})
    row = db_session.query(models.User).filter(models.User.email == "dbcheck@example.com").first()
    assert row is not None
    assert row.role == "patient"


def test_escalation_attempt_is_visible_in_the_audit_trail(client, db_session):
    client.post("/auth/register", json={"name": "Audited", "email": "audited@example.com",
                                        "password": "Secret123!", "role": "admin"})
    row = (
        db_session.query(models.AuditLogEntry)
        .filter(models.AuditLogEntry.action == "register",
                models.AuditLogEntry.actor == "audited@example.com")
        .first()
    )
    assert row is not None
    assert row.after["granted_role"] == "patient"
    assert row.after["requested_role"] == "admin"


def test_plain_patient_registration_records_no_requested_role(client, db_session):
    client.post("/auth/register", json={"name": "Plain", "email": "plain@example.com",
                                        "password": "Secret123!", "role": "patient"})
    row = (
        db_session.query(models.AuditLogEntry)
        .filter(models.AuditLogEntry.action == "register",
                models.AuditLogEntry.actor == "plain@example.com")
        .first()
    )
    assert row.after["granted_role"] == "patient"
    assert "requested_role" not in row.after


def test_duplicate_email_on_self_registration_is_409(client):
    body = {"name": "Dupe", "email": "dupe@example.com", "password": "Secret123!", "role": "patient"}
    assert client.post("/auth/register", json=body).status_code == 200
    assert client.post("/auth/register", json=body).status_code == 409


def test_admin_can_create_a_privileged_account(client):
    resp = client.post(
        "/admin/users",
        json={"name": "Real Doctor", "email": "realdoc@example.com",
              "password": "Secret123!", "role": "doctor"},
        headers=_admin_headers(client),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["role"] == "doctor"


def test_admin_created_account_can_log_in_with_its_role(client):
    client.post("/admin/users",
                json={"name": "Login Doctor", "email": "logindoc@example.com",
                      "password": "Secret123!", "role": "doctor"},
                headers=_admin_headers(client))
    resp = client.post("/auth/login", json={"email": "logindoc@example.com", "password": "Secret123!"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["role"] == "doctor"


def test_anonymous_caller_cannot_create_a_privileged_account(client):
    resp = client.post("/admin/users", json={"name": "Nope", "email": "nope@example.com",
                                             "password": "Secret123!", "role": "admin"})
    assert resp.status_code == 401


def test_non_admin_caller_cannot_create_a_privileged_account(client):
    client.post("/auth/register", json={"name": "Pat", "email": "pat-escalate@example.com",
                                        "password": "Secret123!", "role": "patient"})
    headers = auth_headers(client, "pat-escalate@example.com", "Secret123!")
    resp = client.post("/admin/users", json={"name": "Nope", "email": "nope2@example.com",
                                             "password": "Secret123!", "role": "admin"}, headers=headers)
    assert resp.status_code == 403


def test_admin_user_creation_is_audited_with_the_granted_role(client, db_session):
    client.post("/admin/users",
                json={"name": "Audited Doctor", "email": "auditeddoc@example.com",
                      "password": "Secret123!", "role": "doctor"},
                headers=_admin_headers(client))
    row = (
        db_session.query(models.AuditLogEntry)
        .filter(models.AuditLogEntry.action == "create_user")
        .order_by(models.AuditLogEntry.time.desc())
        .first()
    )
    assert row is not None
    assert row.actor == DEFAULT_ADMIN_EMAIL
    assert row.after["granted_role"] == "doctor"
