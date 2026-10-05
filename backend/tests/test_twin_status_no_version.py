"""A patient with no twin_versions row has no twin, whatever patients.twin_status says."""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from app.api.v1.routers.twins import _twin_status, _twin_survival
from tests.conftest import login, register

_PATIENT_COLS = (
    "id, patient_code, name, age, gender, phone, email, hospital, stage, tumor_size_mm, "
    "er_status, pr_status, her2_status, ki67, grade, nodes_involved, current_treatment, "
    "status, risk, survival_probability, last_updated, diagnosed_on, twin_status, history, "
    "notes, deleted_at"
)


def test_list_status_helper():
    assert _twin_status(None, None, "Synced") == "Not created"
    assert _twin_status("v1", "Active", "Synced") == "Active"
    assert _twin_status("v1", None, "Synced") == "Synced"


def test_survival_only_comes_from_a_twin_version():
    assert _twin_survival(None, None) is None
    assert _twin_survival(None, 0.9) is None
    assert _twin_survival("v1", 0.82) == 0.82


@pytest.fixture()
def db(db_sessionmaker, client):
    def run(sql, params=None, fetch=False):
        async def _go():
            async with db_sessionmaker() as s:
                res = await s.execute(text(sql), params or {})
                await s.commit()
                return [dict(r) for r in res.mappings()] if fetch else None

        return asyncio.run(_go())

    run(f"CREATE TABLE patients ({_PATIENT_COLS})")
    run("CREATE TABLE twin_versions (id, patient_id, version, created_at, status, author, summary, "
        "tumor_size_mm, survival, risk, model, snapshot)")
    run("CREATE TABLE timeline_events (id, patient_id, date, title, detail, kind)")
    # twin_status 'Synced' mirrors the live column default.
    run("INSERT INTO patients (id, patient_code, name, age, stage, tumor_size_mm, risk, "
        "survival_probability, twin_status) VALUES ('p1', 'PT-1', 'Pat One', 24, 'I', 24, 'low', 0.9, 'Synced')")
    return run


def _headers(client):
    register(client, email="twin-doc@example.com", role="doctor")
    return {"Authorization": f"Bearer {login(client, email='twin-doc@example.com').json()['accessToken']}"}


def test_detail_reports_not_created_with_zero_versions(client, db):
    r = client.get("/digital-twins/PT-1", headers=_headers(client))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["twinStatus"] == "Not created" and body["active"] is None and body["versions"] == []


def test_detail_after_resync_has_v1_active(client, db):
    headers = _headers(client)
    assert client.post("/digital-twins/PT-1/resync", headers=headers).status_code == 200
    body = client.get("/digital-twins/PT-1", headers=headers).json()
    assert body["twinStatus"] == "Synced"
    assert body["active"]["version"] == "v1" and body["active"]["status"] == "Active"
