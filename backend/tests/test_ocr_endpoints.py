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

The provider seam (`services/ocr_provider.extract_fields`) is covered at
the bottom of this file and, in depth, by `test_ocr_engine.py` / `test_ocr_parser.py`.

Behaviour that requires a real Postgres/Supabase instance (and, for
`/extract`, an installed Tesseract) and is NOT covered here -
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
    """The provider seam fails loudly (never returns empty fields) when OCR cannot run."""

    async def test_disabled_provider_fails_loudly(self):
        from app.core.config import get_settings
        from app.core.exceptions import UpstreamServiceError
        from app.services import ocr_provider

        prior = get_settings().OCR_PROVIDER
        get_settings().OCR_PROVIDER = None
        try:
            with pytest.raises(UpstreamServiceError):
                await ocr_provider.extract_fields(b"%PDF-1.4 ...", "application/pdf")
        finally:
            get_settings().OCR_PROVIDER = prior

    async def test_unimplemented_named_provider_fails_loudly(self):
        from app.core.config import get_settings
        from app.core.exceptions import UpstreamServiceError
        from app.services import ocr_provider

        prior = get_settings().OCR_PROVIDER
        get_settings().OCR_PROVIDER = "some-future-vendor"
        try:
            with pytest.raises(UpstreamServiceError):
                await ocr_provider.extract_fields(b"%PDF-1.4 ...", "application/pdf")
        finally:
            get_settings().OCR_PROVIDER = prior


class TestOcrTimestampBinding:
    """Regression: TIMESTAMPTZ params must be datetime objects, not ISO strings
    (asyncpg raises `TypeError: expected a datetime.date or datetime.datetime
    instance, got 'str'`). The SQL stays parameterized."""

    @staticmethod
    def _recording_session():
        from unittest.mock import AsyncMock, MagicMock

        calls: list[tuple[str, dict]] = []

        async def execute(statement, params=None):
            calls.append((str(statement), params or {}))
            return MagicMock()

        session = MagicMock()
        session.execute = AsyncMock(side_effect=execute)
        session.commit = AsyncMock()
        return session, calls

    async def test_extract_binds_timezone_aware_datetime(self, monkeypatch):
        from datetime import datetime
        from types import SimpleNamespace

        from app.api.v1.routers import ocr as ocr_router
        from app.core.config import get_settings
        from app.services import ocr_provider, storage

        async def fake_doc(session, document_id):
            return {"id": document_id, "storage_path": "p", "mime_type": "application/pdf"}

        async def fake_download(path):
            return b"%PDF-1.4"

        async def fake_extract(content, mime):
            return [ocr_provider.ExtractedField(field="stage", value="II", confidence=0.9)]

        monkeypatch.setattr(ocr_router, "_get_document_row", fake_doc)
        monkeypatch.setattr(storage, "download_document", fake_download)
        monkeypatch.setattr(ocr_provider, "extract_fields", fake_extract)
        monkeypatch.setattr(ocr_provider, "engine_label", lambda: "mock-ocr")
        monkeypatch.setattr(get_settings(), "OCR_SUPPORTED_MIME_TYPES", ["application/pdf"], raising=False)

        session, calls = self._recording_session()
        result = await ocr_router.extract_document(
            "doc-1", session=session, current_user=SimpleNamespace(id="u1", email="d@example.com")
        )

        assert result is not None
        extraction_insert = next(p for sql, p in calls if "INSERT INTO ocr_extractions" in sql)
        field_insert = next(p for sql, p in calls if "INSERT INTO ocr_extraction_fields" in sql)
        for params in (extraction_insert, field_insert):
            assert isinstance(params["now"], datetime)
            assert params["now"].tzinfo is not None
        session.commit.assert_awaited()

    async def test_reject_binds_datetime_for_reviewed_at(self, monkeypatch):
        from datetime import datetime
        from types import SimpleNamespace

        from app.api.v1.routers import ocr as ocr_router
        from app.schemas.ocr import OcrRejectRequest

        row = {
            "id": "e1", "status": "Extracted", "document_id": "doc-1", "patient_code": "P1",
            "model": "m", "extracted_at": None, "reviewed_at": None,
            "reject_reason": None, "reviewed_by_email": None,
        }

        async def fake_latest(session, document_id):
            return row

        async def fake_fields(session, extraction_id):
            return []

        monkeypatch.setattr(ocr_router, "_latest_extraction", fake_latest)
        monkeypatch.setattr(ocr_router, "_fields_for", fake_fields)

        session, calls = self._recording_session()
        await ocr_router.reject_extraction(
            "doc-1", OcrRejectRequest(reason="bad scan"), session=session,
            current_user=SimpleNamespace(id="u1", email="d@example.com"),
        )
        update = next(p for sql, p in calls if "reviewed_at" in sql)
        assert isinstance(update["now"], datetime) and update["now"].tzinfo is not None

    async def test_approve_binds_datetime_for_reviewed_at_and_resyncs_twin(self, monkeypatch):
        from datetime import datetime
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from app.api.v1.routers import ocr as ocr_router
        from app.schemas.ocr import OcrApproveRequest

        row = {
            "id": "e1", "status": "Extracted", "document_id": "doc-1", "patient_id": "pat-1",
            "patient_code": "P1", "model": "m", "extracted_at": None, "reviewed_at": None,
            "reject_reason": None, "reviewed_by_email": None,
        }

        async def fake_latest(session, document_id):
            return row

        async def fake_fields(session, extraction_id):
            return []

        resync = AsyncMock()
        monkeypatch.setattr(ocr_router, "_latest_extraction", fake_latest)
        monkeypatch.setattr(ocr_router, "_fields_for", fake_fields)
        monkeypatch.setattr(ocr_router, "resync_twin", resync)

        session, calls = self._recording_session()
        user = SimpleNamespace(id="u1", email="d@example.com")
        payload = OcrApproveRequest(fields=[{"field": "stage", "value": "II"}])
        await ocr_router.approve_extraction("doc-1", payload, session=session, current_user=user)

        by_sql = {sql: p for sql, p in calls}
        reviewed = next(p for sql, p in by_sql.items() if "SET status = 'Approved'" in sql)
        assert isinstance(reviewed["now"], datetime) and reviewed["now"].tzinfo is not None
        # Text columns keep ISO strings (patients.last_updated, timeline_events.date).
        patient_update = next(p for sql, p in by_sql.items() if "UPDATE patients" in sql)
        timeline = next(p for sql, p in by_sql.items() if "INSERT INTO timeline_events" in sql)
        assert isinstance(patient_update["now"], str)
        assert isinstance(timeline["date"], str)
        # Twin resync runs once, after the commit, for the right patient.
        resync.assert_awaited_once()
        assert resync.await_args.args[0] == "pat-1"


class TestOcrDocumentStatus:
    """documents.status follows the OCR lifecycle, inside the same transaction."""

    @staticmethod
    def _session():
        from unittest.mock import AsyncMock, MagicMock

        events: list[tuple] = []

        async def execute(statement, params=None):
            events.append(("sql", str(statement), params or {}))
            return MagicMock()

        async def commit():
            events.append(("commit",))

        session = MagicMock()
        session.execute = AsyncMock(side_effect=execute)
        session.commit = AsyncMock(side_effect=commit)
        return session, events

    @staticmethod
    def _status_updates(events):
        return [(e[2]["status"], e[2]) for e in events if e[0] == "sql" and "UPDATE documents" in e[1]]

    @staticmethod
    def _row():
        return {
            "id": "e1", "status": "Extracted", "document_id": "doc-1", "patient_id": "pat-1",
            "patient_code": "P1", "model": "m", "extracted_at": None, "reviewed_at": None,
            "reject_reason": None, "reviewed_by_email": None,
        }

    def _patch_reads(self, monkeypatch):
        from app.api.v1.routers import ocr as ocr_router

        row = self._row()

        async def fake_latest(session, document_id):
            return row

        async def fake_fields(session, extraction_id):
            return []

        monkeypatch.setattr(ocr_router, "_latest_extraction", fake_latest)
        monkeypatch.setattr(ocr_router, "_fields_for", fake_fields)

    @staticmethod
    def _assert_before_commit(events):
        update_at = next(i for i, e in enumerate(events) if e[0] == "sql" and "UPDATE documents" in e[1])
        commit_at = next(i for i, e in enumerate(events) if e[0] == "commit")
        assert update_at < commit_at

    @staticmethod
    def _assert_text_updated_at(params):
        # documents.updated_at is a text column: ISO string, never a datetime.
        assert isinstance(params["now"], str)
        assert params["id"] == "doc-1"

    @staticmethod
    def _user():
        from types import SimpleNamespace

        return SimpleNamespace(id="u1", email="d@x.test")

    def _patch_extract_deps(self, monkeypatch, extract):
        from app.api.v1.routers import ocr as ocr_router
        from app.core.config import get_settings
        from app.services import ocr_provider, storage

        async def fake_doc(session, document_id):
            return {"id": document_id, "storage_path": "p", "mime_type": "application/pdf"}

        async def fake_download(path):
            return b"%PDF-1.4"

        monkeypatch.setattr(ocr_router, "_get_document_row", fake_doc)
        monkeypatch.setattr(storage, "download_document", fake_download)
        monkeypatch.setattr(ocr_provider, "extract_fields", extract)
        monkeypatch.setattr(ocr_provider, "engine_label", lambda: "mock-ocr")
        monkeypatch.setattr(get_settings(), "OCR_SUPPORTED_MIME_TYPES", ["application/pdf"], raising=False)

    async def test_extract_sets_needs_review(self, monkeypatch):
        from app.api.v1.routers import ocr as ocr_router
        from app.services import ocr_provider

        async def fake_extract(content, mime):
            return [ocr_provider.ExtractedField(field="stage", value="II", confidence=0.9)]

        self._patch_reads(monkeypatch)
        self._patch_extract_deps(monkeypatch, fake_extract)

        session, events = self._session()
        await ocr_router.extract_document("doc-1", session=session, current_user=self._user())

        updates = self._status_updates(events)
        assert [s for s, _ in updates] == ["Needs review"]
        self._assert_text_updated_at(updates[0][1])
        self._assert_before_commit(events)

    async def test_extract_binds_field_source(self, monkeypatch):
        from app.api.v1.routers import ocr as ocr_router
        from app.services import ocr_provider

        async def fake_extract(content, mime):
            return [
                ocr_provider.ExtractedField(field="stage", value="II", confidence=None, source="text-layer"),
                ocr_provider.ExtractedField(field="ki67", value="30", confidence=0.8, source="ocr"),
                ocr_provider.ExtractedField(field="grade", value="2", confidence=None),
            ]

        self._patch_reads(monkeypatch)
        self._patch_extract_deps(monkeypatch, fake_extract)
        session, events = self._session()
        await ocr_router.extract_document("doc-1", session=session, current_user=self._user())

        inserts = [e[2] for e in events if e[0] == "sql" and "INSERT INTO ocr_extraction_fields" in e[1]]
        assert {p["field_name"]: p["source"] for p in inserts} == {"stage": "text-layer", "ki67": "ocr", "grade": None}

    async def test_extract_failure_touches_no_document_status(self, monkeypatch):
        import pytest

        from app.api.v1.routers import ocr as ocr_router
        from app.core.exceptions import UpstreamServiceError

        async def failing_extract(content, mime):
            raise UpstreamServiceError("ocr down")

        self._patch_extract_deps(monkeypatch, failing_extract)

        session, events = self._session()
        with pytest.raises(UpstreamServiceError):
            await ocr_router.extract_document("doc-1", session=session, current_user=self._user())
        assert self._status_updates(events) == []
        assert not any(e[0] == "commit" for e in events)

    async def test_approve_sets_verified_before_commit(self, monkeypatch):
        from unittest.mock import AsyncMock

        from app.api.v1.routers import ocr as ocr_router
        from app.schemas.ocr import OcrApproveRequest

        self._patch_reads(monkeypatch)
        monkeypatch.setattr(ocr_router, "resync_twin", AsyncMock())

        session, events = self._session()
        payload = OcrApproveRequest(fields=[{"field": "stage", "value": "II"}])
        await ocr_router.approve_extraction("doc-1", payload, session=session, current_user=self._user())

        updates = self._status_updates(events)
        assert [s for s, _ in updates] == ["Verified"]
        self._assert_text_updated_at(updates[0][1])
        self._assert_before_commit(events)

    async def test_approve_failure_commits_nothing(self, monkeypatch):
        import pytest
        from unittest.mock import AsyncMock, MagicMock

        from app.api.v1.routers import ocr as ocr_router
        from app.schemas.ocr import OcrApproveRequest

        self._patch_reads(monkeypatch)
        resync = AsyncMock()
        monkeypatch.setattr(ocr_router, "resync_twin", resync)
        session, events = self._session()

        async def failing_execute(statement, params=None):
            sql = str(statement)
            if "INSERT INTO timeline_events" in sql:
                raise RuntimeError("db error")
            events.append(("sql", sql, params or {}))
            return MagicMock()

        session.execute = AsyncMock(side_effect=failing_execute)
        payload = OcrApproveRequest(fields=[{"field": "stage", "value": "II"}])
        with pytest.raises(RuntimeError):
            await ocr_router.approve_extraction("doc-1", payload, session=session, current_user=self._user())
        # Never committed: get_db_session rolls the whole request back, so the
        # (later-issued) status update cannot persist without the approval.
        assert not any(e[0] == "commit" for e in events)
        assert self._status_updates(events) == []
        resync.assert_not_awaited()

    async def test_approve_with_no_usable_fields_does_not_change_status(self, monkeypatch):
        import pytest

        from app.api.v1.routers import ocr as ocr_router
        from app.core.exceptions import ValidationAppError
        from app.schemas.ocr import OcrApproveRequest

        self._patch_reads(monkeypatch)
        session, events = self._session()
        payload = OcrApproveRequest(fields=[{"field": "stage", "value": ""}])
        with pytest.raises(ValidationAppError):
            await ocr_router.approve_extraction("doc-1", payload, session=session, current_user=self._user())
        assert events == []

    async def test_reject_returns_document_to_pending_ocr(self, monkeypatch):
        from app.api.v1.routers import ocr as ocr_router
        from app.schemas.ocr import OcrRejectRequest

        self._patch_reads(monkeypatch)
        session, events = self._session()
        await ocr_router.reject_extraction(
            "doc-1", OcrRejectRequest(reason="bad scan"), session=session, current_user=self._user()
        )

        updates = self._status_updates(events)
        assert [s for s, _ in updates] == ["Pending OCR"]
        self._assert_text_updated_at(updates[0][1])
        self._assert_before_commit(events)
        # The historical extraction record keeps its Rejected status.
        assert any(e[0] == "sql" and "SET status = 'Rejected'" in e[1] for e in events)

    async def test_conflict_on_already_reviewed_extraction_changes_nothing(self, monkeypatch):
        import pytest

        from app.api.v1.routers import ocr as ocr_router
        from app.core.exceptions import ConflictError
        from app.schemas.ocr import OcrRejectRequest

        row = {**self._row(), "status": "Approved"}

        async def fake_latest(session, document_id):
            return row

        monkeypatch.setattr(ocr_router, "_latest_extraction", fake_latest)
        session, events = self._session()
        with pytest.raises(ConflictError):
            await ocr_router.reject_extraction(
                "doc-1", OcrRejectRequest(reason="x"), session=session, current_user=self._user()
            )
        assert events == []


def test_extraction_response_serializes_null_and_numeric_confidence():
    """The API keeps a missing confidence as JSON null and a real one as a number (never 0 or a default)."""
    import json

    from fastapi.encoders import jsonable_encoder

    from app.api.v1.routers import ocr as ocr_router

    row = {
        "document_id": "doc-1", "patient_code": "P1", "status": "Extracted", "model": "tesseract 5.3.0",
        "extracted_at": None, "reviewed_by_email": None, "reviewed_at": None, "reject_reason": None,
    }
    fields = [
        {"field_name": "stage", "label": "Stage", "extracted_value": "II", "confidence": None,
         "source": None, "status": "pending"},  # historical row: source never recorded
        {"field_name": "ki67", "label": "Ki-67", "extracted_value": "30", "confidence": 0.77,
         "source": "ocr", "status": "pending"},
        {"field_name": "grade", "label": "Grade", "extracted_value": "2", "confidence": None,
         "source": "text-layer", "status": "pending"},
    ]
    payload = json.loads(json.dumps(jsonable_encoder(ocr_router._extraction_response(row, fields))))
    by_field = {f["field"]: f["confidence"] for f in payload["fields"]}
    assert by_field == {"stage": None, "ki67": 0.77, "grade": None}
    sources = {f["field"]: f["source"] for f in payload["fields"]}
    assert sources == {"stage": None, "ki67": "ocr", "grade": "text-layer"}
