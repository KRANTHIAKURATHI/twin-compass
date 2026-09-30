"""
Targeted tests for the Patient Management endpoints (Phase 2).

Scope note: `routers/clinical.py` addresses `patients` with Postgres-only SQL
(`SUBSTRING(x FROM y)` for code allocation, `ILIKE` for search, `now()` for
soft delete) against a table that exists only in Supabase Postgres, not in
any local migration. The project's test DB is SQLite (see conftest.py) and
project rules forbid treating SQLite as the target database, so CRUD bodies
that touch `patients` cannot be exercised here without either faking the
result (misrepresenting coverage) or rewriting production SQL to be
SQLite-compatible (out of scope for a Phase 2 endpoint-wiring pass).

What IS safely testable against the real dependency graph, because
`require_roles` rejects before any patient SQL runs: authentication and
role enforcement on every patient route, and route mounting. Full CRUD
behaviour should be covered by an integration suite run against a real
Postgres/Supabase instance.
"""
from __future__ import annotations

import pytest

from tests.conftest import login, register

# (method, mounted route template, concrete path to call in tests)
PATIENT_ROUTES = [
    ("GET", "/patients", "/patients"),
    ("POST", "/patients", "/patients"),
    ("GET", "/patients/{patient_id}", "/patients/PT-1"),
    ("PATCH", "/patients/{patient_id}", "/patients/PT-1"),
    ("DELETE", "/patients/{patient_id}", "/patients/PT-1"),
    ("GET", "/patients/{patient_id}/labs", "/patients/PT-1/labs"),
    ("GET", "/patients/{patient_id}/imaging", "/patients/PT-1/imaging"),
    ("GET", "/patients/{patient_id}/timeline", "/patients/PT-1/timeline"),
    ("GET", "/patients/{patient_id}/treatment-plan", "/patients/PT-1/treatment-plan"),
]


def test_every_frontend_patient_route_is_mounted(client):
    mounted = {(method, route.path) for route in client.app.routes for method in getattr(route, "methods", set())}
    for method, template, _ in PATIENT_ROUTES:
        assert (method, template) in mounted, f"{method} {template} is missing"


@pytest.mark.parametrize("method,_template,path", PATIENT_ROUTES)
def test_patient_routes_require_authentication(client, method, _template, path):
    r = getattr(client, method.lower())(path)
    assert r.status_code == 401
    envelope = r.json()["error"]
    assert set(envelope) == {"code", "message", "field", "request_id"}


@pytest.mark.parametrize(
    "method,_template,path",
    # /treatment-plan deliberately also allows the "patient" role (a patient
    # views their own plan), so it is excluded from this doctor/admin-only set.
    [rt for rt in PATIENT_ROUTES if not rt[2].endswith("/treatment-plan")],
)
def test_patient_routes_reject_patient_role(client, method, _template, path):
    """A logged-in patient account has no access to the doctor/admin patient registry."""
    register(client, email="patient@example.com", role="patient")
    token = login(client, email="patient@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    kwargs = {"json": {"name": "Jane"}} if method in ("POST", "PATCH") else {}
    r = getattr(client, method.lower())(path, headers=headers, **kwargs)
    assert r.status_code == 403


@pytest.mark.parametrize(
    "method,_template,path",
    [rt for rt in PATIENT_ROUTES if rt[2] in ("/patients", "/patients/PT-1")],
)
def test_patient_routes_accept_doctor_role_past_the_authorization_check(client, method, _template, path):
    """
    A doctor clears `require_roles` — proven by getting past 401/403 into the
    endpoint body. What happens after that depends on the `patients` table,
    which is Postgres-only (see module docstring), so this only asserts the
    response is *not* an authorization rejection.
    """
    register(client, email="doc2@example.com", role="doctor")
    token = login(client, email="doc2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    kwargs = {"json": {"name": "Jane"}} if method in ("POST", "PATCH") else {}
    r = getattr(client, method.lower())(path, headers=headers, **kwargs)
    assert r.status_code not in (401, 403)
