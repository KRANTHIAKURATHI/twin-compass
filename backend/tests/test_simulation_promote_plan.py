"""Promoting a simulation when the patient already has a treatment plan.

treatment_plans.patient_id is UNIQUE (one plan per patient), so promotion must
create the plan if absent and update it otherwise - never insert a second row.
Runs the real endpoint against SQLite tables shaped like the live ones, with
the same unique constraint.
"""
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


@pytest.fixture()
def db(db_sessionmaker, client):
    def run(sql, params=None, fetch=False):
        async def _go():
            async with db_sessionmaker() as s:
                res = await s.execute(text(sql), params or {})
                await s.commit()
                return [dict(r) for r in res.mappings()] if fetch else None

        return asyncio.run(_go())

    run("CREATE TABLE treatment_plans (id TEXT PRIMARY KEY, patient_id TEXT UNIQUE, regimen, cycle, "
        "total_cycles, started_on, next_dose, adherence, side_effects, medications)")
    run("CREATE TABLE simulation_runs (id, patient_id, selected, survival, response, decision, notes, scenarios)")
    run("INSERT INTO simulation_runs (id, patient_id, selected, scenarios) VALUES ('s1', 'p1', 'Current plan', :sc)",
        {"sc": json.dumps(SCENARIOS)})
    return run


def _promote(client, body):
    register(client, email="promo-doc@example.com", role="doctor")
    token = login(client, email="promo-doc@example.com").json()["accessToken"]
    return client.post("/simulations/s1/promote", json=body, headers={"Authorization": f"Bearer {token}"})


def test_promote_creates_plan_when_none_exists(client, db):
    r = _promote(client, {"notes": "n", "selectedScenario": "Lower toxicity"})
    assert r.status_code == 200, r.text
    plans = db("SELECT id, regimen FROM treatment_plans WHERE patient_id = 'p1'", fetch=True)
    assert len(plans) == 1 and plans[0]["regimen"] == LOWER["regimen"]
    assert r.json()["data"]["id"] == plans[0]["id"]
    run = db("SELECT selected, decision FROM simulation_runs", fetch=True)[0]
    assert run == {"selected": "Lower toxicity", "decision": "Promoted to plan"}


def test_promote_updates_existing_plan_instead_of_inserting(client, db):
    db("INSERT INTO treatment_plans (id, patient_id, regimen, cycle, total_cycles, started_on, next_dose, "
       "adherence) VALUES ('old', 'p1', 'Old regimen', 4, 8, '2020-01-01', '2020-02-01', 90)")
    r = _promote(client, {"selectedScenario": "Lower toxicity"})
    assert r.status_code == 200, r.text
    plans = db("SELECT id, regimen, cycle, total_cycles, adherence, started_on FROM treatment_plans", fetch=True)
    assert len(plans) == 1
    assert plans[0]["id"] == "old" and r.json()["data"]["id"] == "old"
    assert plans[0]["regimen"] == LOWER["regimen"] != "Old regimen"
    assert (plans[0]["cycle"], plans[0]["total_cycles"], plans[0]["adherence"]) == (1, 6, 0)
    assert plans[0]["started_on"] != "2020-01-01"
    assert db("SELECT decision FROM simulation_runs", fetch=True)[0]["decision"] == "Promoted to plan"


def test_promote_without_selection_uses_stored_scenario_regimen(client, db):
    r = _promote(client, {})
    assert r.status_code == 200, r.text
    assert db("SELECT regimen FROM treatment_plans", fetch=True)[0]["regimen"] == SCENARIOS[0]["regimen"]
