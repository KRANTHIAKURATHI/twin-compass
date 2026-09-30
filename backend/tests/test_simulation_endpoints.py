"""
Targeted tests for the Treatment Simulation endpoints (Phase 5).

Scope note: `routers/clinical.py`'s simulation routes read/write
`simulation_runs` / `treatment_plans` and read `twin_versions` / `patients`
with Postgres-only SQL (jsonb casts) against tables that exist only in
Supabase Postgres, not in any local migration. The project's test DB is
SQLite (see conftest.py) and project rules forbid treating SQLite as the
target database, so run/list/get/save/duplicate/promote bodies cannot be
exercised here without either faking the result (misrepresenting coverage)
or rewriting production SQL to be SQLite-compatible (out of scope for this
audit pass). This mirrors the precedent set in test_predictions_endpoints.py.

What IS safely testable against the real dependency graph, because
`require_roles` rejects before any simulation SQL runs: authentication and
role enforcement on every simulation route, route mounting, and
request-body validation on the routes that take one.

Behaviour that requires a real Postgres/Supabase instance and is NOT covered
here - flagged rather than faked:
  * a run projecting against the patient's active twin state, not the raw
    patient row (`_twin_state`)
  * patient isolation on `GET /simulations?patientId=`
  * persistence of a run/save/duplicate/promote and the exact response shape
  * repeated promotion not creating a second `treatment_plans` row
  * a duplicate never inheriting "Promoted to plan" and never touching
    `treatment_plans`
These require an integration suite run against real Postgres/Supabase.

The mathematical projection itself (`app/services/response_model.py`) is
covered separately in test_response_model.py, which needs no database.
"""
from __future__ import annotations

import pytest

from tests.conftest import login, register

# (method, mounted route template, concrete path to call in tests)
SIMULATION_ROUTES = [
    ("GET", "/simulations", "/simulations"),
    ("GET", "/simulations/{simulation_id}", "/simulations/SIM-1"),
    ("POST", "/simulations", "/simulations"),
    ("POST", "/simulations/run", "/simulations/run"),
    ("POST", "/simulations/{simulation_id}/duplicate", "/simulations/SIM-1/duplicate"),
    ("POST", "/simulations/{simulation_id}/promote", "/simulations/SIM-1/promote"),
]

RUN_PATH = "/simulations/run"
SAVE_PATH = "/simulations"


def _body_for(method: str, path: str) -> dict | None:
    # GET /simulations and POST /simulations share a path - only the POST
    # (save_scenario) takes a body.
    if method == "POST" and path in (RUN_PATH, SAVE_PATH):
        return {"json": {"patientId": "PT-1", "regimen": "AC-T"}}
    return None


def test_every_frontend_simulation_route_is_mounted(client):
    mounted = {(method, route.path) for route in client.app.routes for method in getattr(route, "methods", set())}
    for method, template, _ in SIMULATION_ROUTES:
        assert (method, template) in mounted, f"{method} {template} is missing"


@pytest.mark.parametrize("method,_template,path", SIMULATION_ROUTES)
def test_simulation_routes_require_authentication(client, method, _template, path):
    kwargs = _body_for(method, path) or {}
    r = getattr(client, method.lower())(path, **kwargs)
    assert r.status_code == 401
    envelope = r.json()["error"]
    assert set(envelope) == {"code", "message", "field", "request_id"}


@pytest.mark.parametrize("method,_template,path", SIMULATION_ROUTES)
def test_simulation_routes_reject_patient_role(client, method, _template, path):
    """A logged-in patient account has no access to any simulation route.

    This is a clinical decision-support surface (running/saving/duplicating/
    promoting a treatment scenario), not a self-service one - matching
    list/get/promote's existing require_roles("doctor", "researcher", "admin")
    / ("doctor", "admin"), and the fix made here to `run_simulation`, which
    previously accepted any authenticated role including patient.
    """
    register(client, email="patient@example.com", role="patient")
    token = login(client, email="patient@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    kwargs = _body_for(method, path) or {}
    r = getattr(client, method.lower())(path, headers=headers, **kwargs)
    assert r.status_code == 403


@pytest.mark.parametrize(
    "method,_template,path",
    [(m, t, p) for m, t, p in SIMULATION_ROUTES if p != "/simulations/SIM-1/promote"],
)
def test_researcher_role_reaches_read_and_write_routes(client, method, _template, path):
    """Researchers may read simulation data, run projections, save and
    duplicate scenarios - all doctor/researcher/admin. Promotion is
    doctor/admin only and is covered separately."""
    register(client, email="researcher@example.com", role="researcher")
    token = login(client, email="researcher@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    kwargs = _body_for(method, path) or {}
    r = getattr(client, method.lower())(path, headers=headers, **kwargs)
    assert r.status_code not in (401, 403)


def test_researcher_role_is_rejected_from_promote(client):
    """Promotion is a doctor/admin-only clinical decision - a researcher
    clears authentication but not this authorization check."""
    register(client, email="researcher2@example.com", role="researcher")
    token = login(client, email="researcher2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/simulations/SIM-1/promote", headers=headers)
    assert r.status_code == 403


@pytest.mark.parametrize("method,_template,path", SIMULATION_ROUTES)
def test_doctor_role_accepted_past_the_authorization_check(client, method, _template, path):
    """
    A doctor clears `require_roles` - proven by getting past 401/403 into the
    endpoint body. What happens after that depends on `simulation_runs` /
    `twin_versions` / `patients`, which are Postgres-only (see module
    docstring), so this only asserts the response is *not* an authorization
    rejection.
    """
    register(client, email="doc2@example.com", role="doctor")
    token = login(client, email="doc2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    kwargs = _body_for(method, path) or {}
    r = getattr(client, method.lower())(path, headers=headers, **kwargs)
    assert r.status_code not in (401, 403)


def test_run_simulation_rejects_missing_patient_id(client):
    """422 before any SQL runs - `SimulationRequest` requires patientId."""
    register(client, email="doc3@example.com", role="doctor")
    token = login(client, email="doc3@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(RUN_PATH, headers=headers, json={})
    assert r.status_code == 422


def test_save_scenario_rejects_missing_patient_id(client):
    """422 before any SQL runs - `save_scenario` shares `SimulationRequest`."""
    register(client, email="doc4@example.com", role="doctor")
    token = login(client, email="doc4@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(SAVE_PATH, headers=headers, json={})
    assert r.status_code == 422


def test_run_simulation_rejects_patient_role_before_validation(client):
    """RBAC is checked before body validation - a patient gets 403, not 422,
    even with an invalid/empty body."""
    register(client, email="patient2@example.com", role="patient")
    token = login(client, email="patient2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(RUN_PATH, headers=headers, json={})
    assert r.status_code == 403
