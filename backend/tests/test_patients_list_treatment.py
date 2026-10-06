"""The patient list shows the treatment plan's regimen, else the recorded treatment."""
from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import text

from app.services.response_model import project_scenarios
from tests.conftest import login, register
from tests.test_response_model import HER2_TWIN

SCENARIOS, _ = project_scenarios(regimen="AC-T", **HER2_TWIN)
LOWER = next(s for s in SCENARIOS if s["name"] == "Lower toxicity")
_COLS = ("id, patient_code, name, age, gender, phone, email, hospital, stage, tumor_size_mm, er_status, "
         "pr_status, her2_status, ki67, grade, nodes_involved, current_treatment, status, risk, "
         "survival_probability, last_updated, diagnosed_on, twin_status, history, notes, deleted_at")


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
    run("CREATE TABLE treatment_plans (id TEXT PRIMARY KEY, patient_id TEXT UNIQUE, regimen, cycle, "
        "total_cycles, started_on, next_dose, adherence, side_effects, medications)")
    run("CREATE TABLE simulation_runs (id, patient_id, selected, survival, response, decision, notes, scenarios)")
    for pid, code in (("p1", "PT-1"), ("p2", "PT-2")):
        run("INSERT INTO patients (id, patient_code, name, current_treatment) VALUES (:i, :c, :c, 'Recorded')",
            {"i": pid, "c": code})
    return run


def _headers(client):
    register(client, email="list-doc@example.com", role="doctor")
    return {"Authorization": f"Bearer {login(client, email='list-doc@example.com').json()['accessToken']}"}


def _treatments(client, headers):
    r = client.get("/patients", headers=headers)
    assert r.status_code == 200, r.text
    return {p["id"]: p["currentTreatment"] for p in r.json()}


def test_plan_regimen_shown_and_fallback_to_recorded_treatment(client, db):
    db("INSERT INTO treatment_plans (id, patient_id, regimen) VALUES ('t1', 'p1', 'Plan regimen')")
    assert _treatments(client, _headers(client)) == {"PT-1": "Plan regimen", "PT-2": "Recorded"}
    # Read-only: the recorded treatment is untouched.
    assert db("SELECT current_treatment FROM patients WHERE id = 'p1'", fetch=True)[0]["current_treatment"] == "Recorded"


def test_blank_plan_regimen_falls_back(client, db):
    db("INSERT INTO treatment_plans (id, patient_id, regimen) VALUES ('t1', 'p1', '')")
    assert _treatments(client, _headers(client))["PT-1"] == "Recorded"


def test_promoted_scenario_regimen_appears_in_list(client, db):
    db("INSERT INTO simulation_runs (id, patient_id, selected, scenarios) VALUES ('s1', 'p1', 'Current plan', :sc)",
       {"sc": json.dumps(SCENARIOS)})
    headers = _headers(client)
    r = client.post("/simulations/s1/promote", json={"selectedScenario": "Lower toxicity"}, headers=headers)
    assert r.status_code == 200, r.text
    got = _treatments(client, headers)
    assert got["PT-1"] == LOWER["regimen"] and got["PT-2"] == "Recorded"
