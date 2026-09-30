"""
Targeted tests for the Digital Twin endpoints (Phase 3).

Scope note: `routers/twins.py` reads/writes `twin_versions` / `twin_snapshots`
with Postgres-only SQL (`LEFT JOIN LATERAL`, `CAST(:snapshot AS jsonb)`)
against tables that exist only in Supabase Postgres, not in any local
migration. The project's test DB is SQLite (see conftest.py) and project
rules forbid treating SQLite as the target database, so list/detail/resync/
restore/archive bodies that touch `twin_versions`/`twin_snapshots` cannot be
exercised here without either faking the result (misrepresenting coverage)
or rewriting production SQL to be SQLite-compatible (out of scope for this
audit pass). This mirrors the precedent set in test_patients_endpoints.py.

What IS safely testable against the real dependency graph, because
`require_roles` rejects before any twin SQL runs: authentication and role
enforcement on every digital-twin route, and route mounting.

Behaviour that requires a real Postgres/Supabase instance and is NOT covered
here — flagged rather than faked:
  * initial twin creation/initialization via resync
  * version increment and historical version immutability
  * snapshot correspondence to versions
  * restore creating a new version without mutating history
  * archive being non-destructive and idempotent
  * patient isolation across twin data
  * missing-patient 404 behaviour
These require an integration suite run against real Postgres/Supabase.
"""
from __future__ import annotations

import pytest

from tests.conftest import login, register

# (method, mounted route template, concrete path to call in tests)
TWIN_ROUTES = [
    ("GET", "/digital-twins", "/digital-twins"),
    ("GET", "/digital-twins/{patient_id}", "/digital-twins/PT-1"),
    ("GET", "/digital-twins/{patient_id}/versions", "/digital-twins/PT-1/versions"),
    ("GET", "/digital-twins/{patient_id}/snapshots", "/digital-twins/PT-1/snapshots"),
    ("POST", "/digital-twins/{patient_id}/resync", "/digital-twins/PT-1/resync"),
    (
        "POST",
        "/digital-twins/{patient_id}/versions/{version}/restore",
        "/digital-twins/PT-1/versions/v1/restore",
    ),
    ("POST", "/digital-twins/{patient_id}/archive", "/digital-twins/PT-1/archive"),
]

# Read-only routes allow doctor, researcher and admin; mutating routes
# (resync/restore/archive) are doctor/admin only.
MUTATING_PATHS = {"/digital-twins/PT-1/resync", "/digital-twins/PT-1/versions/v1/restore", "/digital-twins/PT-1/archive"}


def test_every_frontend_twin_route_is_mounted(client):
    mounted = {(method, route.path) for route in client.app.routes for method in getattr(route, "methods", set())}
    for method, template, _ in TWIN_ROUTES:
        assert (method, template) in mounted, f"{method} {template} is missing"


@pytest.mark.parametrize("method,_template,path", TWIN_ROUTES)
def test_twin_routes_require_authentication(client, method, _template, path):
    r = getattr(client, method.lower())(path)
    assert r.status_code == 401
    envelope = r.json()["error"]
    assert set(envelope) == {"code", "message", "field", "request_id"}


@pytest.mark.parametrize("method,_template,path", TWIN_ROUTES)
def test_twin_routes_reject_patient_role(client, method, _template, path):
    """A logged-in patient account has no access to any digital-twin route."""
    register(client, email="patient@example.com", role="patient")
    token = login(client, email="patient@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = getattr(client, method.lower())(path, headers=headers)
    assert r.status_code == 403


@pytest.mark.parametrize(
    "method,_template,path",
    [rt for rt in TWIN_ROUTES if rt[2] not in MUTATING_PATHS],
)
def test_researcher_role_reaches_read_routes(client, method, _template, path):
    """Researchers may read twin data but not mutate it."""
    register(client, email="researcher@example.com", role="researcher")
    token = login(client, email="researcher@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = getattr(client, method.lower())(path, headers=headers)
    assert r.status_code not in (401, 403)


@pytest.mark.parametrize("method,_template,path", [rt for rt in TWIN_ROUTES if rt[2] in MUTATING_PATHS])
def test_researcher_role_rejected_from_mutating_routes(client, method, _template, path):
    register(client, email="researcher2@example.com", role="researcher")
    token = login(client, email="researcher2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = getattr(client, method.lower())(path, headers=headers)
    assert r.status_code == 403


@pytest.mark.parametrize("method,_template,path", TWIN_ROUTES)
def test_doctor_role_accepted_past_the_authorization_check(client, method, _template, path):
    """
    A doctor clears `require_roles` - proven by getting past 401/403 into the
    endpoint body. What happens after that depends on `twin_versions` /
    `twin_snapshots`, which are Postgres-only (see module docstring), so this
    only asserts the response is *not* an authorization rejection.
    """
    register(client, email="doc2@example.com", role="doctor")
    token = login(client, email="doc2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = getattr(client, method.lower())(path, headers=headers)
    assert r.status_code not in (401, 403)
