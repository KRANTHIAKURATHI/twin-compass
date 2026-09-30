"""
Targeted tests for the Prediction endpoints (Phase 4).

Scope note: `routers/predictions.py` reads/writes `prediction_runs` and reads
`twin_versions` / `patients` with Postgres-only SQL against tables that exist
only in Supabase Postgres, not in any local migration. The project's test DB
is SQLite (see conftest.py) and project rules forbid treating SQLite as the
target database, so run/history/progression/confidence-trend/explainability
bodies cannot be exercised here without either faking the result
(misrepresenting coverage) or rewriting production SQL to be
SQLite-compatible (out of scope for this audit pass). This mirrors the
precedent set in test_patients_endpoints.py and test_digital_twins_endpoints.py.

What IS safely testable against the real dependency graph, because
`require_roles` rejects before any prediction SQL runs: authentication and
role enforcement on every prediction route, route mounting, and request-body
validation on the run endpoint.

Behaviour that requires a real Postgres/Supabase instance and is NOT covered
here - flagged rather than faked:
  * a recorded run reflecting the active twin version's stored state
  * null-through behaviour for unset survival/confidence (not coerced to 0)
  * prediction history ordering (most recent first) and patient isolation
  * confidence-trend omitting runs with no recorded confidence
  * progression reading real twin_versions measurements
  * explainability's cohort-size floor (insufficient below 3 records) and
    the reliability threshold at 10 records
  * model unavailability: there is no trained model in this codebase, so
    "model unavailable" is not a distinct failure mode - every run records
    twin state and labels itself "Twin state snapshot (no model attached)"
These require an integration suite run against real Postgres/Supabase.
"""
from __future__ import annotations

import pytest

from tests.conftest import login, register

# (method, mounted route template, concrete path to call in tests)
PREDICTION_ROUTES = [
    ("GET", "/predictions/{patient_id}", "/predictions/PT-1"),
    ("GET", "/predictions/{patient_id}/history", "/predictions/PT-1/history"),
    ("GET", "/predictions/{patient_id}/confidence-trend", "/predictions/PT-1/confidence-trend"),
    ("GET", "/predictions/{patient_id}/progression", "/predictions/PT-1/progression"),
    ("GET", "/predictions/{patient_id}/explainability", "/predictions/PT-1/explainability"),
    ("POST", "/predictions/run", "/predictions/run"),
]

RUN_PATH = "/predictions/run"


def test_every_frontend_prediction_route_is_mounted(client):
    mounted = {(method, route.path) for route in client.app.routes for method in getattr(route, "methods", set())}
    for method, template, _ in PREDICTION_ROUTES:
        assert (method, template) in mounted, f"{method} {template} is missing"


@pytest.mark.parametrize("method,_template,path", PREDICTION_ROUTES)
def test_prediction_routes_require_authentication(client, method, _template, path):
    kwargs = {"json": {"patientId": "PT-1"}} if path == RUN_PATH else {}
    r = getattr(client, method.lower())(path, **kwargs)
    assert r.status_code == 401
    envelope = r.json()["error"]
    assert set(envelope) == {"code", "message", "field", "request_id"}


@pytest.mark.parametrize("method,_template,path", PREDICTION_ROUTES)
def test_prediction_routes_reject_patient_role(client, method, _template, path):
    """A logged-in patient account has no access to any prediction route."""
    register(client, email="patient@example.com", role="patient")
    token = login(client, email="patient@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    kwargs = {"json": {"patientId": "PT-1"}} if path == RUN_PATH else {}
    r = getattr(client, method.lower())(path, headers=headers, **kwargs)
    assert r.status_code == 403


@pytest.mark.parametrize("method,_template,path", PREDICTION_ROUTES)
def test_researcher_role_reaches_read_and_write_routes(client, method, _template, path):
    """Researchers may read prediction data and record runs - both are
    doctor/researcher/admin per require_roles in predictions.py."""
    register(client, email="researcher@example.com", role="researcher")
    token = login(client, email="researcher@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    kwargs = {"json": {"patientId": "PT-1"}} if path == RUN_PATH else {}
    r = getattr(client, method.lower())(path, headers=headers, **kwargs)
    assert r.status_code not in (401, 403)


@pytest.mark.parametrize("method,_template,path", PREDICTION_ROUTES)
def test_doctor_role_accepted_past_the_authorization_check(client, method, _template, path):
    """
    A doctor clears `require_roles` - proven by getting past 401/403 into the
    endpoint body. What happens after that depends on `prediction_runs` /
    `twin_versions` / `patients`, which are Postgres-only (see module
    docstring), so this only asserts the response is *not* an authorization
    rejection.
    """
    register(client, email="doc2@example.com", role="doctor")
    token = login(client, email="doc2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    kwargs = {"json": {"patientId": "PT-1"}} if path == RUN_PATH else {}
    r = getattr(client, method.lower())(path, headers=headers, **kwargs)
    assert r.status_code not in (401, 403)


def test_run_prediction_rejects_missing_patient_id(client):
    """422 before any SQL runs - `PredictionRequest` requires patientId."""
    register(client, email="doc3@example.com", role="doctor")
    token = login(client, email="doc3@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(RUN_PATH, headers=headers, json={})
    assert r.status_code == 422


def test_run_prediction_rejects_patient_role_before_validation(client):
    """RBAC is checked before body validation - a patient gets 403, not 422,
    even with an invalid/empty body."""
    register(client, email="patient2@example.com", role="patient")
    token = login(client, email="patient2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(RUN_PATH, headers=headers, json={})
    assert r.status_code == 403
