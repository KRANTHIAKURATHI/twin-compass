"""
Reports against the live text-id schema (legacy `reports` row shape plus the
columns added by supabase/migrations/0004_reports_live_text_schema.sql).

The SQL used by these routes is portable apart from `CAST(... AS jsonb)` in
the generate INSERT, which SQLite turns into a numeric cast. Tests therefore
assert the persisted columns, not the stored content, for generate.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from tests.conftest import login, register

_PATIENT_COLS = (
    "id, patient_code, name, age, gender, phone, email, hospital, stage, tumor_size_mm, "
    "er_status, pr_status, her2_status, ki67, grade, nodes_involved, current_treatment, "
    "status, risk, survival_probability, last_updated, diagnosed_on, twin_status, history, "
    "notes, deleted_at"
)
LEGACY_CREATED = "2026-08-19T09:37:42.299443+00:00"


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
    run("CREATE TABLE twin_versions (patient_id, version, created_at, status, tumor_size_mm, survival, risk, model)")
    run("CREATE TABLE prediction_runs (patient_id, date, twin_version, model, survival, recurrence, response, confidence)")
    run("CREATE TABLE simulation_runs (id, patient_id, date, selected, decision, survival, response, confidence)")
    run("CREATE TABLE documents (id, patient_id)")
    run("CREATE TABLE timeline_events (id, patient_id, date, title, detail, kind)")
    # Legacy shape + 0004 columns.
    run("CREATE TABLE reports (id, title, patient_id, patient_name, type, created, version, status, downloads, "
        "generated_by, generated_at, content, created_at)")
    run("CREATE TABLE report_downloads (id, report_id, format, downloaded_by, downloaded_at)")
    run("INSERT INTO patients (id, patient_code, name, age, stage) VALUES ('p1', 'PT-1', 'Pat One', 55, 'II')")
    run("INSERT INTO reports (id, title, patient_id, patient_name, type, created, version, status, downloads) "
        "VALUES ('L1', 'Legacy', 'p1', '', 'Clinical summary', :c, 1, 'Final', 0)", {"c": LEGACY_CREATED})
    return run


def _headers(client, role="doctor"):
    email = f"rep-{role}@example.com"
    register(client, email=email, role=role)
    return {"Authorization": f"Bearer {login(client, email=email).json()['accessToken']}"}


def test_downloads_route_is_declared_before_the_id_route(client):
    paths = [r.path for r in client.app.routes if "GET" in getattr(r, "methods", set())]
    assert paths.index("/reports/downloads") < paths.index("/reports/{report_id}")


def test_downloads_history_is_not_shadowed_by_the_id_route(client, db):
    r = client.get("/reports/downloads", headers=_headers(client))
    assert r.status_code == 200 and r.json() == []


def test_legacy_row_uses_created_date_and_has_no_invented_content(client, db):
    h = _headers(client)
    listed = client.get("/reports", headers=h).json()
    assert len(listed) == 1 and listed[0]["created"] == LEGACY_CREATED and listed[0]["patientId"] == "PT-1"

    detail = client.get("/reports/L1", headers=h).json()
    assert detail["created"] == LEGACY_CREATED
    c = detail["content"]
    assert c["prediction"]["basis"] == "none" and c["digitalTwin"] is None
    assert c["simulations"]["runs"] == [] and c["timeline"] == []
    assert c["patient"]["age"] is None and c["patient"]["stage"] is None
    assert "Legacy report" in c["generationNote"]
    # Nothing was written back to the legacy row.
    assert db("SELECT content, generated_at FROM reports WHERE id='L1'", fetch=True) == [
        {"content": None, "generated_at": None}
    ]

    versions = client.get("/reports/L1/versions", headers=h).json()
    assert versions[0]["date"] == LEGACY_CREATED and versions[0]["author"] == ""


def test_generate_persists_live_schema_columns(client, db):
    h = _headers(client)
    r = client.post("/reports/generate", json={"patientId": "PT-1", "type": "Clinical summary"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["data"]["version"] == 2  # follows the legacy v1 for the same patient/type
    row = db("SELECT * FROM reports WHERE id != 'L1'", fetch=True)[0]
    assert row["patient_id"] == "p1" and row["patient_name"] == "Pat One"
    assert row["generated_by"] and row["generated_at"] and row["created"] == row["generated_at"] == row["created_at"]
    assert db("SELECT count(*) AS n FROM timeline_events", fetch=True)[0]["n"] == 1


def test_export_records_a_text_id_download_and_history_resolves_the_user(client, db):
    h = _headers(client)
    r = client.post("/reports/L1/export", json={"format": "csv"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["content"]["generationNote"].startswith("Legacy report")
    dl = db("SELECT * FROM report_downloads", fetch=True)
    assert len(dl) == 1 and dl[0]["report_id"] == "L1" and dl[0]["format"] == "csv" and dl[0]["downloaded_by"]

    # profiles.id is uuid live; the join compares as text. (SQLite stores the
    # fixture uuid without dashes, so point the row at the stored profile id.)
    db("UPDATE report_downloads SET downloaded_by = (SELECT id FROM profiles WHERE email = 'rep-doctor@example.com')")
    hist = client.get("/reports/downloads", headers=h).json()
    assert hist[0]["report"] == "L1" and hist[0]["format"] == "CSV" and hist[0]["by"] == "rep-doctor@example.com"
    assert client.get("/reports", headers=h).json()[0]["downloads"] == 1
