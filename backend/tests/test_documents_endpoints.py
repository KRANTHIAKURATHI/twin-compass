"""
Targeted tests for the Documents endpoints (Phase 6).

Scope note: `routers/documents.py` reads/writes `documents` / `document_versions`
with Postgres-only SQL against tables that exist only in Supabase Postgres,
not in any local migration - same situation as `routers/twins.py` (see that
module's test file for the full rationale). The project's test DB is SQLite
and project rules forbid treating SQLite as the target database, so
list/detail/upload/versions/timeline/links/download/preview bodies cannot be
exercised here without either faking the result or rewriting production SQL
to be SQLite-compatible.

What IS safely testable against the real dependency graph, because
`require_roles` rejects before any document SQL or Storage call runs:
authentication and role enforcement on every document route, and route
mounting.

Behaviour that requires a real Postgres/Supabase instance and is NOT covered
here - flagged rather than faked:
  * document creation, metadata persistence, patient association
  * real multipart upload against Supabase Storage
  * file validation (size/type) against a real request body
  * download/preview signed-url generation
  * version and timeline projection
  * patient isolation across document data
  * missing-document 404 behaviour
  * storage-then-database failure cleanup
These require an integration suite run against real Postgres/Supabase and a
configured Storage bucket.
"""
from __future__ import annotations

import pytest

from tests.conftest import login, register

DOCUMENT_ROUTES = [
    ("GET", "/documents", "/documents"),
    ("GET", "/documents/{document_id}", "/documents/doc-1"),
    ("POST", "/documents", "/documents"),
    ("GET", "/documents/{document_id}/versions", "/documents/doc-1/versions"),
    ("GET", "/documents/{document_id}/timeline", "/documents/doc-1/timeline"),
    ("GET", "/documents/{document_id}/links", "/documents/doc-1/links"),
    ("GET", "/documents/{document_id}/download", "/documents/doc-1/download"),
    ("GET", "/documents/{document_id}/preview", "/documents/doc-1/preview"),
]

# Only doctor/admin may upload; doctor/researcher/admin may read.
MUTATING_PATHS = {"POST /documents"}


def test_every_frontend_document_route_is_mounted(client):
    mounted = {(method, route.path) for route in client.app.routes for method in getattr(route, "methods", set())}
    for method, template, _ in DOCUMENT_ROUTES:
        assert (method, template) in mounted, f"{method} {template} is missing"


@pytest.mark.parametrize("method,_template,path", DOCUMENT_ROUTES)
def test_document_routes_require_authentication(client, method, _template, path):
    r = getattr(client, method.lower())(path)
    assert r.status_code == 401
    envelope = r.json()["error"]
    assert set(envelope) == {"code", "message", "field", "request_id"}


@pytest.mark.parametrize("method,_template,path", DOCUMENT_ROUTES)
def test_document_routes_reject_patient_role(client, method, _template, path):
    """A logged-in patient account has no access to any document route yet -
    there is no profile-to-patient-record link in this codebase for a
    patient-role user to self-scope by (see Phase 6 report)."""
    register(client, email="patient@example.com", role="patient")
    token = login(client, email="patient@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = getattr(client, method.lower())(path, headers=headers)
    assert r.status_code == 403


def test_researcher_cannot_upload(client):
    """Reads are doctor/researcher/admin; upload is doctor/admin only."""
    register(client, email="researcher@example.com", role="researcher")
    token = login(client, email="researcher@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/documents", headers=headers)
    assert r.status_code == 403


def test_researcher_can_reach_list_route(client):
    """Confirms the read roles pass RBAC (the request then fails downstream
    on the missing `documents` table - real behaviour on SQLite, not what
    this test is asserting)."""
    register(client, email="researcher2@example.com", role="researcher")
    token = login(client, email="researcher2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/documents", headers=headers)
    assert r.status_code != 403 and r.status_code != 401
