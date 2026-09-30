"""
Targeted tests for the OCR extraction endpoints (Phase 7).

Scope note: `routers/ocr.py` reads/writes `ocr_extractions` /
`ocr_extraction_fields` (new tables - see
`supabase/migrations/0001_ocr_extractions.sql`) plus `documents` and
`patients`, all Postgres-only tables that do not exist in the SQLite test
database (see `test_documents_endpoints.py` / `test_digital_twins_endpoints.py`
for the same situation and rationale). So, as with those modules, what's
tested here against the real dependency graph is: route mounting,
authentication, and role enforcement - everything `require_roles` decides
before any OCR SQL or storage/provider call runs.

The one piece of real application logic that has no I/O and so *is* fully
exercised here is `services/ocr_provider.extract_fields` - the seam a real
OCR provider plugs into. No provider is configured in this environment
(no OCR SDK in requirements.txt), so it must fail loudly rather than
inventing fields; that failure is asserted directly, not mocked away.

Behaviour that requires a real Postgres/Supabase instance (and, for
`/extract`, a real configured OCR provider) and is NOT covered here -
flagged rather than faked:
  * persisting an extraction and its fields
  * reviewing fields before they reach the patient
  * approve applying only explicitly-approved, non-empty fields
  * approve triggering the existing twin resync and leaving prior versions
    immutable
  * reject leaving the patient and document untouched
  * re-approving/re-rejecting an already-reviewed extraction (409)
  * patient isolation and audit trail (timeline events, reviewed_by/at)
These require an integration suite run against real Postgres/Supabase with
an OCR provider configured.
"""
from __future__ import annotations

import pytest

from tests.conftest import login, register

OCR_ROUTES = [
    ("POST", "/ocr/{document_id}/extract", "/ocr/doc-1/extract"),
    ("GET", "/ocr/{document_id}/fields", "/ocr/doc-1/fields"),
    ("POST", "/ocr/{document_id}/approve", "/ocr/doc-1/approve"),
    ("POST", "/ocr/{document_id}/reject", "/ocr/doc-1/reject"),
]

# Read (fields) is doctor/researcher/admin; every mutation (extract/approve/
# reject) is doctor/admin only - approval/rejection of clinical data is never
# a researcher action.
MUTATING_PATHS = {"/ocr/doc-1/extract", "/ocr/doc-1/approve", "/ocr/doc-1/reject"}


def test_every_frontend_ocr_route_is_mounted(client):
    mounted = {(method, route.path) for route in client.app.routes for method in getattr(route, "methods", set())}
    for method, template, _ in OCR_ROUTES:
        assert (method, template) in mounted, f"{method} {template} is missing"


@pytest.mark.parametrize("method,_template,path", OCR_ROUTES)
def test_ocr_routes_require_authentication(client, method, _template, path):
    r = getattr(client, method.lower())(path)
    assert r.status_code == 401
    envelope = r.json()["error"]
    assert set(envelope) == {"code", "message", "field", "request_id"}


@pytest.mark.parametrize("method,_template,path", OCR_ROUTES)
def test_ocr_routes_reject_patient_role(client, method, _template, path):
    """A patient account can never approve/reject/view OCR data for any
    patient_id it names - there is no profile-to-patient-record linkage for
    it to self-scope by (same blocker as documents, see Phase 6 report)."""
    register(client, email="patient@example.com", role="patient")
    token = login(client, email="patient@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = getattr(client, method.lower())(path, headers=headers)
    assert r.status_code == 403


@pytest.mark.parametrize("method,_template,path", [rt for rt in OCR_ROUTES if rt[2] in MUTATING_PATHS])
def test_researcher_cannot_mutate_ocr_data(client, method, _template, path):
    """Researchers have no clinical approval authority (Task 11)."""
    register(client, email="researcher@example.com", role="researcher")
    token = login(client, email="researcher@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = getattr(client, method.lower())(path, headers=headers)
    assert r.status_code == 403


def test_researcher_can_reach_fields_route(client):
    """Confirms the read role passes RBAC (the request then fails downstream
    on the missing `ocr_extractions` table - real behaviour on SQLite, not
    what this test is asserting)."""
    register(client, email="researcher2@example.com", role="researcher")
    token = login(client, email="researcher2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/ocr/doc-1/fields", headers=headers)
    assert r.status_code not in (401, 403)


@pytest.mark.parametrize("method,_template,path", OCR_ROUTES)
def test_doctor_role_accepted_past_the_authorization_check(client, method, _template, path):
    register(client, email="doc2@example.com", role="doctor")
    token = login(client, email="doc2@example.com").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = getattr(client, method.lower())(path, headers=headers)
    assert r.status_code not in (401, 403)


class TestOcrProviderBoundary:
    """`services/ocr_provider.extract_fields` has no I/O, so it is exercised
    directly rather than mocked. No OCR SDK is installed (see that module's
    docstring): with OCR_PROVIDER unset (the default), extraction must fail
    loudly instead of returning fabricated fields."""

    async def test_extraction_fails_without_a_configured_provider(self):
        from app.core.exceptions import UpstreamServiceError
        from app.services import ocr_provider

        with pytest.raises(UpstreamServiceError):
            await ocr_provider.extract_fields(b"%PDF-1.4 ...", "application/pdf")

    async def test_extraction_fails_for_an_unimplemented_named_provider(self):
        from app.core.config import get_settings
        from app.core.exceptions import UpstreamServiceError
        from app.services import ocr_provider

        get_settings().OCR_PROVIDER = "some-future-vendor"
        try:
            with pytest.raises(UpstreamServiceError):
                await ocr_provider.extract_fields(b"%PDF-1.4 ...", "application/pdf")
        finally:
            get_settings().OCR_PROVIDER = None
