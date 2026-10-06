"""Scenario selection on simulation run/promote (pure helpers + request schema).

The run/promote bodies use Postgres-only SQL (see test_simulation_endpoints.py),
so the selection rules are tested where they live: the helpers and the request
model. The SQL path is exercised by a rolled-back run against live Postgres.
"""
from __future__ import annotations

from app.api.v1.routers.clinical import _pick_scenario, _resolve_promoted
from app.schemas.clinical import SimulationRequest
from app.services.response_model import project_scenarios
from tests.test_response_model import HER2_TWIN

SCENARIOS, _ = project_scenarios(regimen="AC-T", **HER2_TWIN)


def test_request_accepts_selected_scenario_alias_and_defaults_to_none():
    assert SimulationRequest.model_validate({"patientId": "PT-1"}).selected_scenario is None
    body = {"patientId": "PT-1", "regimen": "AC-T", "selectedScenario": "Lower toxicity"}
    parsed = SimulationRequest.model_validate(body)
    assert (parsed.regimen, parsed.selected_scenario) == ("AC-T", "Lower toxicity")


def test_selected_lower_toxicity_is_picked_and_projection_is_unchanged():
    picked = _pick_scenario(SCENARIOS, "Lower toxicity")
    assert picked["name"].endswith("Lower toxicity") or picked["name"] == "Lower toxicity"
    assert picked is not SCENARIOS[0]
    assert [s["name"] for s in SCENARIOS] == [s["name"] for s in project_scenarios(regimen="AC-T", **HER2_TWIN)[0]]


def test_no_selection_defaults_to_first_scenario():
    assert _pick_scenario(SCENARIOS, None) is SCENARIOS[0]
    assert _pick_scenario(SCENARIOS, "") is SCENARIOS[0]


def test_invalid_selection_falls_back_to_first_scenario():
    assert _pick_scenario(SCENARIOS, "No such scenario") is SCENARIOS[0]
    assert _pick_scenario([], "x") is None


def test_promote_uses_requested_scenarios_regimen():
    lower = _pick_scenario(SCENARIOS, "Lower toxicity")
    got = _resolve_promoted(SCENARIOS, SCENARIOS[0]["name"], lower["name"])
    assert got is lower and got["regimen"] != SCENARIOS[0]["regimen"]


def test_promote_without_or_with_unknown_request_uses_stored_selection():
    first = SCENARIOS[0]["name"]
    assert _resolve_promoted(SCENARIOS, first, None) is SCENARIOS[0]
    assert _resolve_promoted(SCENARIOS, first, "bogus") is SCENARIOS[0]
    assert _resolve_promoted(SCENARIOS, "gone", None) is None
