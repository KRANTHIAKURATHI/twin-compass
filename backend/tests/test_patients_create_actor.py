"""
POST /patients vs the live `patients.created_by -> users(id)` foreign key.

Active logins are `profiles` ids, which do not exist in the legacy `users`
table, so storing them in `created_by` violated the FK (a 500 in production).
The handler now stores `created_by` only when the id resolves in `users`, and
records the actor in `audit_logs` either way. The SQL is portable, so it runs
on the per-test SQLite DB with fixture tables shaped like the live ones and the
FK emulated by a trigger-free check on the `users` table.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from tests.conftest import login, register

_COLS = (
    "id, patient_code, name, age, gender, phone, email, hospital, stage, tumor_size_mm, er_status, "
    "pr_status, her2_status, ki67, grade, nodes_involved, current_treatment, status, risk, "
    "survival_probability, last_updated, diagnosed_on, twin_status, history, notes, created_by, deleted_at"
)
BODY = {"name": "Test", "age": 24, "tumorSizeMm": 24, "stage": "I", "her2Status": "Negative"}


@pytest.fixture()
def db(db_sessionmaker, client):
    def run(sql, params=None, fetch=False):
        async def _go():
            async with db_sessionmaker() as s:
                res = await s.execute(text(sql), params or {})
                await s.commit()
                return [dict(r) for r in res.mappings()] if fetch else None

        return asyncio.run(_go())

    run(f"CREATE TABLE patients ({_COLS})")
    run("CREATE TABLE users (id)")
    run("CREATE TABLE audit_logs (id, time, actor, actor_role, action, target, after)")
    return run


def _doctor(client):
    register(client, email="create-doc@example.com", role="doctor")
    body = login(client, email="create-doc@example.com").json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['accessToken']}"}


def test_profile_id_missing_from_users_stores_null_created_by_and_audits_actor(client, db):
    actor_id, headers = _doctor(client)
    r = client.post("/patients", json=BODY, headers=headers)

    assert r.status_code == 201, r.text
    assert r.json()["data"]["name"] == "Test"
    stored = db("SELECT patient_code, created_by, tumor_size_mm FROM patients", fetch=True)
    assert stored == [{"patient_code": "PT-1000", "created_by": None, "tumor_size_mm": 24.0}]
    audit = db("SELECT actor, actor_role, action, target, after FROM audit_logs", fetch=True)
    assert len(audit) == 1 and audit[0]["action"] == "patient.created" and audit[0]["target"] == "PT-1000"
    assert audit[0]["actor"] == "create-doc@example.com" and audit[0]["actor_role"] == "doctor"
    assert actor_id in audit[0]["after"]


def test_legacy_user_id_is_stored_in_created_by(client, db):
    actor_id, headers = _doctor(client)
    db("INSERT INTO users (id) VALUES (:i)", {"i": actor_id})
    r = client.post("/patients", json=BODY, headers=headers)

    assert r.status_code == 201, r.text
    assert db("SELECT created_by FROM patients", fetch=True) == [{"created_by": actor_id}]
    assert len(db("SELECT id FROM audit_logs", fetch=True)) == 1


def test_integrity_error_becomes_conflict_envelope_and_rolls_back(client, db):
    _, headers = _doctor(client)
    db("CREATE UNIQUE INDEX one_name ON patients (name)")
    assert client.post("/patients", json=BODY, headers=headers).status_code == 201
    r = client.post("/patients", json=BODY, headers=headers)

    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"
    assert len(db("SELECT id FROM patients", fetch=True)) == 1
    assert len(db("SELECT id FROM audit_logs", fetch=True)) == 1
