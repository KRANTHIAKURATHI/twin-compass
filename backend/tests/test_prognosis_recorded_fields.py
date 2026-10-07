"""A blank stage/grade/nodes/ER at patient creation must stay NULL (not the DB default) so prognosis reports it unavailable."""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

pytest.importorskip("sksurv")

from tests.conftest import login, register  # noqa: E402

_COLS = (
    "id, patient_code, name, age, gender, phone, email, hospital, stage, tumor_size_mm, er_status, "
    "pr_status, her2_status, ki67, grade, nodes_involved, current_treatment, status, risk, "
    "survival_probability, last_updated, diagnosed_on, twin_status, history, notes, created_by, deleted_at"
)
# Mirrors the live Supabase column defaults (verified read-only): stage 'I', grade 1, nodes 0, receptors 'Negative'.
_LIVE_DEFAULTS = {"stage": "'I'", "grade": "1", "nodes_involved": "0", "er_status": "'Negative'",
                  "pr_status": "'Negative'", "her2_status": "'Negative'", "age": "0", "tumor_size_mm": "0"}


@pytest.fixture()
def db(db_sessionmaker, client):
    def run(sql, params=None, fetch=False):
        async def _go():
            async with db_sessionmaker() as s:
                res = await s.execute(text(sql), params or {})
                await s.commit()
                return [dict(r) for r in res.mappings()] if fetch else None

        return asyncio.run(_go())

    cols = ", ".join(f"{c} DEFAULT {_LIVE_DEFAULTS[c]}" if c in _LIVE_DEFAULTS else c for c in (x.strip() for x in _COLS.split(",")))
    run(f"CREATE TABLE patients ({cols})")
    run("CREATE TABLE users (id)")
    run("CREATE TABLE audit_logs (id, time, actor, actor_role, action, target, after)")
    return run


def _headers(client):
    register(client, email="prog-doc@example.com", role="doctor")
    return {"Authorization": f"Bearer {login(client, email='prog-doc@example.com').json()['accessToken']}"}


def _prognosis(client, h, body):
    created = client.post("/patients", json=body, headers=h)
    assert created.status_code in (200, 201), created.text
    code = created.json()["data"]["id"]
    return created.json()["data"], client.get(f"/predictions/{code}/prognosis", headers=h).json()


def test_blank_stage_grade_are_not_defaulted_and_prognosis_unavailable(client, db):
    h = _headers(client)
    data, prog = _prognosis(client, h, {"name": "Blank", "age": 50, "tumorSizeMm": 20})
    assert data["stage"] is None and data["grade"] is None and data["nodesInvolved"] is None and data["erStatus"] is None
    for key in ("overallSurvival", "relapseFreeSurvival"):
        r = prog[key]
        assert r["status"] == "unavailable" and "riskScore" not in r
        assert set(r["featureAvailability"]["missingRequired"]) == {
            "LYMPH_NODES_EXAMINED_POSITIVE", "GRADE", "TUMOR_STAGE", "ER_STATUS"}


def test_explicitly_recorded_values_still_work(client, db):
    h = _headers(client)
    body = {"name": "Full", "age": 50, "tumorSizeMm": 20, "stage": "I", "grade": 1, "nodesInvolved": 0,
            "erStatus": "Negative", "prStatus": "Negative", "her2Status": "Negative"}
    data, prog = _prognosis(client, h, body)
    assert (data["stage"], data["grade"], data["nodesInvolved"], data["erStatus"]) == ("I", 1, 0, "Negative")
    assert prog["overallSurvival"]["status"] == "available" and prog["relapseFreeSurvival"]["status"] == "available"


def test_partially_recorded_names_only_the_missing_feature(client, db):
    h = _headers(client)
    body = {"name": "Part", "age": 50, "tumorSizeMm": 20, "stage": "II", "nodesInvolved": 2, "erStatus": "Positive"}
    _, prog = _prognosis(client, h, body)
    assert prog["overallSurvival"]["featureAvailability"]["missingRequired"] == ["GRADE"]


def test_prognosis_roles(client, db):
    h = _headers(client)
    code = client.post("/patients", json={"name": "R", "age": 40}, headers=h).json()["data"]["id"]
    assert client.get(f"/predictions/{code}/prognosis").status_code in (401, 403)
    register(client, email="researcher@example.com", role="researcher")
    for email in ("researcher@example.com",):  # admin cannot self-register; it shares the same require_roles dependency
        t = login(client, email=email).json()["accessToken"]
        assert client.get(f"/predictions/{code}/prognosis", headers={"Authorization": f"Bearer {t}"}).status_code == 200
    register(client, email="pat@example.com", role="patient")
    t = login(client, email="pat@example.com").json()["accessToken"]
    assert client.get(f"/predictions/{code}/prognosis", headers={"Authorization": f"Bearer {t}"}).status_code == 403
