"""
Targeted tests for the Reports endpoints (Phase 8).

Scope note: `routers/reports.py` reads/writes `reports` / `report_downloads`
with Postgres-only SQL against tables that exist only in Supabase Postgres
(see that module's docstring and `supabase/migrations/0002_reports.sql`).
The project's test DB is SQLite and project rules forbid treating SQLite as
the target database, so list/detail/generate/versions/downloads/export
bodies cannot be exercised here without either faking the result or
rewriting production SQL to be SQLite-compatible.

What IS safely testable against the real dependency graph, because
`require_roles` rejects before any report SQL runs: authentication and role
enforcement on every report route, and route mounting.

Behaviour that requires a real Postgres/Supabase instance and is NOT
covered here - flagged rather than faked:
  * report generation, content aggregation, patient association
  * report/version/download persistence and listing
  * missing-report 404 behaviour
  * report-version immutability across regenerations
  * prediction-without-model and simulation-as-prototype labelling in
    generated content
These require an integration suite run against real Postgres/Supabase.
"""
from __future__ import annotations

import pytest

from tests.conftest import login, register

REPORT_ROUTES = [
    ("GET", "/reports", "/reports"),
    ("GET", "/reports/{report_id}", "/reports/rpt-1"),
    ("GET", "/reports/{report_id}/versions", "/reports/rpt-1/versions"),
    ("GET", "/reports/downloads", "/reports/downloads"),
    ("POST", "/reports/generate", "/reports/generate"),
    ("POST", "/reports/{report_id}/export", "/reports/rpt-1/export"),
]


def test_every_frontend_report_route_is_mounted(client):
    mounted = {(method, route.path) for route in client.app.routes for method in getattr(route, "methods", set())}
    for method, template, _ in REPORT_ROUTES:
        assert (method, template) in mounted, f"{method} {template} is missing"


@pytest.mark.parametrize("method,_template,path", REPORT_ROUTES)
def test_report_routes_require_authentication(client, method, _template, path):
    r = getattr(client, method.lower())(path)
    assert r.status_code == 401
    envelope = r.json()["error"]
    assert set(envelope) == {"code", "message", "field", "request_id"}


@pytest.mark.parametrize("method,_template,path", REPORT_ROUTES)
def test_report_routes_reject_patient_role(client, method, _template, path):
    """Reports are not yet exposed to the patient role - same limitation as
    documents/twins/predictions (no profile-to-patient-record link exists
    for a patient account to self-scope by)."""
    register(client, email="patient-reports@example.com", role="patient")
    token = login(client, email="patient-reports@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = getattr(client, method.lower())(path, headers=headers)
    assert r.status_code == 403


def test_researcher_can_reach_list_route(client):
    """Confirms read roles pass RBAC (the request then fails downstream on
    the missing `reports` table - real behaviour on SQLite, not what this
    test is asserting)."""
    register(client, email="researcher-reports@example.com", role="researcher")
    token = login(client, email="researcher-reports@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/reports", headers=headers)
    assert r.status_code != 403 and r.status_code != 401


def test_researcher_can_reach_generate_route(client):
    """Generation is allowed for doctor/researcher/admin (matches the
    existing pattern for /predictions/run and /simulations)."""
    register(client, email="researcher-reports2@example.com", role="researcher")
    token = login(client, email="researcher-reports2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/reports/generate", json={"patientId": "PT-0001"}, headers=headers)
    assert r.status_code != 403 and r.status_code != 401
