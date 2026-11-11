"""
Audit logging (services/audit.py) and its integration into the clinical handlers.

Three tiers, all against throwaway data - nothing here touches a real database:

  * the helper against a real SQLite `audit_logs` table (commit / rollback / privacy guard);
  * handler tests against a scripted in-memory session that records every statement, so the
    ORDER of business writes, the audit insert and the single commit can be asserted, and so a
    failure injected at any step can be shown to leave nothing committed;
  * an HTTP-level twin resync on SQLite showing the audit row and the rollback for real.

What SQLite cannot show (flagged, not faked): the Postgres-only statements (`FOR UPDATE`,
`ANY(:names)`, `now()`, jsonb) are only checked as recorded SQL, not executed.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text

from app.api.v1.routers import clinical as clinical_router
from app.api.v1.routers import ocr as ocr_router
from app.api.v1.routers import twins as twins_router
from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.schemas.clinical import PatientInput
from app.schemas.ocr import OcrApproveRequest, OcrRejectRequest
from app.services import audit, ocr_provider, storage
from tests.conftest import login, register

ACTOR_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
ACTOR = SimpleNamespace(id=ACTOR_ID, email="doc@example.test", role="doctor")

# Distinctive strings that must never reach an audit payload.
SENTINELS = ("SENTINEL-NAME", "SENTINEL-PHONE", "SENTINEL-EMAIL", "SENTINEL-NOTES", "SENTINEL-REASON", "SENTINEL-RAW")


# --- scripted session ---------------------------------------------------------------------------


class _Result:
    def __init__(self, rows=(), rowcount=1):
        self._rows = list(rows)
        self.rowcount = rowcount

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    """Records statements; `rules` are (sql-substring, rows, rowcount), first match wins."""

    def __init__(self, rules=(), fail_on=None):
        self.rules = list(rules)
        self.fail_on = fail_on
        self.calls: list[tuple[str, dict]] = []
        self.commits = 0
        self.calls_at_commit: list[int] = []

    async def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("injected failure")
        self.calls.append((sql, params or {}))
        if "FROM patient_access" in sql:  # patient-level authorization: these handler tests act as an authorised caller
            return _Result([{"x": 1}], 1)
        for needle, rows, rowcount in self.rules:
            if needle in sql:
                return _Result(rows, rowcount)
        return _Result([], 1)

    async def commit(self):
        self.commits += 1
        self.calls_at_commit.append(len(self.calls))

    async def rollback(self):  # pragma: no cover - handlers never call it directly
        pass

    # helpers
    def audit_rows(self):
        return [p for sql, p in self.calls if "INSERT INTO audit_logs" in sql]

    def index_of(self, needle):
        return next(i for i, (sql, _) in enumerate(self.calls) if needle in sql)

    def audit(self):
        (row,) = self.audit_rows()
        return {
            **row,
            "actor_role": row["role"],
            "ip": "",  # a literal in the INSERT, asserted against the real table in the SQLite tests
            "before": json.loads(row["before"]) if row["before"] else None,
            "after": json.loads(row["after"]) if row["after"] else None,
        }


def assert_no_sentinels(session):
    blob = json.dumps(session.audit_rows(), default=str)
    for sentinel in SENTINELS:
        assert sentinel not in blob


def assert_audit_is_last_write_before_single_commit(session):
    assert session.commits == 1
    # the audit insert is the final statement before the commit: nothing is written after it
    assert session.calls_at_commit[0] == len(session.calls)
    assert session.index_of("INSERT INTO audit_logs") == len(session.calls) - 1


PATIENT = {
    "id": "pat-uuid-1", "patient_code": "PT-1001", "name": "SENTINEL-NAME", "age": 51, "gender": "F",
    "phone": "SENTINEL-PHONE", "email": "SENTINEL-EMAIL", "hospital": "H", "stage": "I",
    "tumor_size_mm": 20.0, "er_status": "Positive", "pr_status": "Positive", "her2_status": "Negative",
    "ki67": 12.0, "grade": 2, "nodes_involved": 0, "current_treatment": "", "status": "Monitoring",
    "risk": "low", "survival_probability": 0.9, "last_updated": "2026-01-01", "diagnosed_on": "2025-12-01",
    "twin_status": "Synced", "history": [], "notes": "SENTINEL-NOTES",
}

VERSIONS = [
    {"version": "v2", "created_at": "2", "status": "Active", "author": "a", "summary": "", "tumor_size_mm": 20.0,
     "survival": 0.9, "risk": "low", "model": "m"},
    {"version": "v1", "created_at": "1", "status": "Superseded", "author": "a", "summary": "", "tumor_size_mm": 18.0,
     "survival": 0.9, "risk": "low", "model": "m"},
]


# --- helper against real SQLite -----------------------------------------------------------------


@pytest_asyncio.fixture()
async def audit_db(db_sessionmaker):
    async with db_sessionmaker() as s:
        await s.execute(text("CREATE TABLE audit_logs (id, time, actor, actor_role, action, target, before, after, ip)"))
        await s.execute(text("CREATE TABLE biz (id)"))
        await s.commit()
    return db_sessionmaker


async def _rows(maker, table):
    async with maker() as s:
        return [dict(r) for r in (await s.execute(text(f"SELECT * FROM {table}"))).mappings()]


async def test_record_audit_persists_expected_columns(audit_db):
    async with audit_db() as s:
        await audit.record_audit(
            s, actor=ACTOR, action="patient.updated", target="PT-1001",
            before={"stage": "I"}, after={"stage": "II"},
        )
        await s.commit()
    (row,) = await _rows(audit_db, "audit_logs")
    assert row["actor"] == str(ACTOR_ID)  # the authenticated UUID, not the email
    assert "@" not in row["actor"]
    assert row["actor_role"] == "doctor"
    assert row["action"] == "patient.updated" and row["target"] == "PT-1001"
    assert row["ip"] == ""
    assert json.loads(row["before"]) == {"stage": "I"}
    assert json.loads(row["after"])["stage"] == "II"
    uuid.UUID(row["id"])
    stamp = datetime.fromisoformat(row["time"])
    assert stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0)  # ISO-8601 UTC


async def test_audit_row_rolls_back_with_the_business_change(audit_db):
    async with audit_db() as s:
        await s.execute(text("INSERT INTO biz (id) VALUES ('x')"))
        await audit.record_audit(s, actor=ACTOR, action="a", target="PT-1")
        await s.rollback()
    assert await _rows(audit_db, "audit_logs") == []
    assert await _rows(audit_db, "biz") == []


async def test_failed_audit_insert_prevents_business_commit(audit_db):
    async with audit_db() as s:
        await s.execute(text("DROP TABLE audit_logs"))  # make the audit insert fail
        await s.commit()
    async with audit_db() as s:
        await s.execute(text("INSERT INTO biz (id) VALUES ('x')"))
        with pytest.raises(Exception):
            await audit.record_audit(s, actor=ACTOR, action="a", target="PT-1")
        await s.rollback()  # what get_db_session does on any exception
    assert await _rows(audit_db, "biz") == []


@pytest.mark.parametrize("key", ["name", "phone", "email", "notes", "reason", "raw_text", "token", "password"])
async def test_record_audit_refuses_forbidden_keys_at_any_depth(audit_db, key):
    async with audit_db() as s:
        with pytest.raises(ValueError):
            await audit.record_audit(s, actor=ACTOR, action="a", target="PT-1", after={"nested": [{key: "x"}]})
        await s.rollback()
    assert await _rows(audit_db, "audit_logs") == []


def test_allow_list_contains_no_identifying_or_free_text_fields():
    assert not set(audit.PATIENT_AUDIT_FIELDS) & audit.FORBIDDEN_KEYS
    picked = audit.pick_patient_fields(PATIENT)
    assert set(picked) <= set(audit.PATIENT_AUDIT_FIELDS)
    assert not any(s in json.dumps(picked) for s in SENTINELS)
    # `fields` can only narrow the allow-list, never widen it
    assert audit.pick_patient_fields(PATIENT, ["stage", "name", "notes"]) == {"stage": "I"}


# --- OCR ----------------------------------------------------------------------------------------


def _extraction_row(status="Extracted"):
    return {
        "id": "e1", "status": status, "document_id": "doc-1", "patient_id": "pat-uuid-1",
        "patient_code": "PT-1001", "model": "m", "extracted_at": None, "reviewed_at": None,
        "reject_reason": None, "reviewed_by_email": None,
    }


def _patch_ocr_reads(monkeypatch, fields=()):
    async def fake_latest(session, document_id):
        return _extraction_row()

    async def fake_fields(session, extraction_id):
        return list(fields)

    monkeypatch.setattr(ocr_router, "_latest_extraction", fake_latest)
    monkeypatch.setattr(ocr_router, "_fields_for", fake_fields)


def _approve_session(**kwargs):
    return FakeSession(
        rules=[
            ("FOR UPDATE", [{"stage": "I", "tumor_size_mm": 20.0}], 1),
            ("FROM patients", [PATIENT], 1),  # resolve_patient
            ("FROM twin_versions", VERSIONS, 1),
        ],
        **kwargs,
    )


STAGE_FIELD = {"field_name": "stage", "extracted_value": "II", "confidence": 0.93, "source": "text-layer", "status": "pending", "label": "Stage"}


async def test_approve_is_one_transaction_with_twin_and_audit(monkeypatch):
    _patch_ocr_reads(monkeypatch, [STAGE_FIELD])
    session = _approve_session()
    payload = OcrApproveRequest(fields=[{"field": "stage", "value": "III"}, {"field": "name", "value": "SENTINEL-NAME"}])
    await ocr_router.approve_extraction("doc-1", payload, session=session, current_user=ACTOR)

    # one commit; patient update, twin version and audit all precede it, audit last
    assert_audit_is_last_write_before_single_commit(session)
    assert session.index_of("UPDATE patients SET stage") < session.index_of("INSERT INTO twin_versions")
    assert session.index_of("INSERT INTO twin_versions") < session.index_of("INSERT INTO audit_logs")

    event = session.audit()
    assert event["actor"] == str(ACTOR_ID) and event["actor_role"] == "doctor"
    assert event["action"] == "ocr.approved" and event["target"] == "PT-1001" and event["ip"] == ""
    assert event["before"] == {"stage": "I"}  # only the applied field, previous value
    after = event["after"]
    assert after["applied"] == {"stage": "III"}  # 'name' is not in the OCR catalog and is never applied
    assert after["fields"]["stage"] == {"extracted": "II", "edited": True, "confidence": 0.93, "source": "text-layer"}
    assert after["twinVersion"] == "v3" and after["previousTwinVersion"] == "v2"
    assert after["documentId"] == "doc-1" and after["extractionId"] == "e1"
    assert_no_sentinels(session)


async def test_approve_marks_unedited_values_as_not_edited(monkeypatch):
    _patch_ocr_reads(monkeypatch, [STAGE_FIELD])
    session = _approve_session()
    await ocr_router.approve_extraction(
        "doc-1", OcrApproveRequest(fields=[{"field": "stage", "value": "II"}]), session=session, current_user=ACTOR
    )
    assert session.audit()["after"]["fields"]["stage"]["edited"] is False


@pytest.mark.parametrize("failing", ["INSERT INTO audit_logs", "INSERT INTO twin_versions", "UPDATE patients SET stage"])
async def test_approve_failure_at_any_step_commits_nothing(monkeypatch, failing):
    _patch_ocr_reads(monkeypatch, [STAGE_FIELD])
    session = _approve_session(fail_on=failing)
    with pytest.raises(RuntimeError):
        await ocr_router.approve_extraction(
            "doc-1", OcrApproveRequest(fields=[{"field": "stage", "value": "II"}]), session=session, current_user=ACTOR
        )
    assert session.commits == 0  # get_db_session then rolls the whole transaction back
    if failing != "INSERT INTO audit_logs":
        assert session.audit_rows() == []


async def test_approve_twin_failure_leaves_no_audit_row(monkeypatch):
    # the audit row describes a completed change; it must not exist when the twin step failed
    _patch_ocr_reads(monkeypatch, [STAGE_FIELD])
    session = _approve_session(fail_on="INSERT INTO twin_versions")
    with pytest.raises(RuntimeError):
        await ocr_router.approve_extraction(
            "doc-1", OcrApproveRequest(fields=[{"field": "stage", "value": "II"}]), session=session, current_user=ACTOR
        )
    assert session.audit_rows() == [] and session.commits == 0


async def test_second_approval_loses_the_claim_and_writes_nothing(monkeypatch):
    _patch_ocr_reads(monkeypatch, [STAGE_FIELD])
    session = FakeSession(rules=[("UPDATE ocr_extractions", [], 0)])  # another request already claimed it
    with pytest.raises(ConflictError):
        await ocr_router.approve_extraction(
            "doc-1", OcrApproveRequest(fields=[{"field": "stage", "value": "II"}]), session=session, current_user=ACTOR
        )
    assert session.commits == 0 and session.audit_rows() == []
    assert not any("UPDATE patients" in sql for sql, _ in session.calls)


async def test_reject_audit_excludes_the_reason(monkeypatch):
    _patch_ocr_reads(monkeypatch)
    session = FakeSession()
    await ocr_router.reject_extraction(
        "doc-1", OcrRejectRequest(reason="SENTINEL-REASON"), session=session, current_user=ACTOR
    )
    assert_audit_is_last_write_before_single_commit(session)
    event = session.audit()
    assert (event["action"], event["target"], event["actor"], event["actor_role"]) == (
        "ocr.rejected", "PT-1001", str(ACTOR_ID), "doctor",
    )
    assert event["before"] is None
    assert event["after"]["reasonProvided"] is True and event["after"]["documentId"] == "doc-1"
    assert_no_sentinels(session)
    # the reason itself is still stored where it always was
    stored = next(p for sql, p in session.calls if "SET status = 'Rejected'" in sql)
    assert stored["reason"] == "SENTINEL-REASON"
    # rejection never touches the patient
    assert not any("UPDATE patients" in sql for sql, _ in session.calls)


async def test_reject_failure_and_lost_claim_commit_nothing(monkeypatch):
    _patch_ocr_reads(monkeypatch)
    failing = FakeSession(fail_on="INSERT INTO audit_logs")
    with pytest.raises(RuntimeError):
        await ocr_router.reject_extraction("doc-1", OcrRejectRequest(), session=failing, current_user=ACTOR)
    assert failing.commits == 0

    lost = FakeSession(rules=[("UPDATE ocr_extractions", [], 0)])
    with pytest.raises(ConflictError):
        await ocr_router.reject_extraction("doc-1", OcrRejectRequest(), session=lost, current_user=ACTOR)
    assert lost.commits == 0 and lost.audit_rows() == []


def _patch_extract(monkeypatch):
    async def fake_doc(session, document_id, user=None):
        return {"id": document_id, "storage_path": "p", "mime_type": "application/pdf", "patient_code": "PT-1001"}

    async def fake_download(path):
        return b"%PDF-1.4"

    async def fake_extract(content, mime):
        return [
            ocr_provider.ExtractedField(field="stage", value="SENTINEL-RAW", confidence=0.9, source="ocr"),
            ocr_provider.ExtractedField(field="grade", value="2", confidence=None, source="text-layer"),
        ]

    monkeypatch.setattr(ocr_router, "_get_document_row", fake_doc)
    monkeypatch.setattr(storage, "download_document", fake_download)
    monkeypatch.setattr(ocr_provider, "extract_fields", fake_extract)
    monkeypatch.setattr(ocr_provider, "engine_label", lambda: "mock-ocr")
    monkeypatch.setattr(get_settings(), "OCR_SUPPORTED_MIME_TYPES", ["application/pdf"], raising=False)
    _patch_ocr_reads(monkeypatch)


async def test_extract_audit_has_sources_but_no_values(monkeypatch):
    _patch_extract(monkeypatch)
    session = FakeSession()
    await ocr_router.extract_document("doc-1", session=session, current_user=ACTOR)

    # audit is written inside the extraction transaction, before its commit
    commit_at = session.calls_at_commit[0]
    assert session.index_of("INSERT INTO audit_logs") < commit_at
    event = session.audit()
    assert (event["action"], event["target"], event["actor"], event["actor_role"]) == (
        "ocr.extracted", "PT-1001", str(ACTOR_ID), "doctor",
    )
    assert event["after"]["fieldCount"] == 2
    assert event["after"]["sources"] == {"stage": "ocr", "grade": "text-layer"}
    assert_no_sentinels(session)


async def test_extract_audit_failure_commits_nothing(monkeypatch):
    _patch_extract(monkeypatch)
    session = FakeSession(fail_on="INSERT INTO audit_logs")
    with pytest.raises(RuntimeError):
        await ocr_router.extract_document("doc-1", session=session, current_user=ACTOR)
    assert session.commits == 0


# --- patients -----------------------------------------------------------------------------------


def _patient_session(updated=None, **kwargs):
    return FakeSession(
        rules=[
            ("FOR UPDATE", [PATIENT], 1),
            ("RETURNING", [{**PATIENT, **(updated or {})}], 1),
        ],
        **kwargs,
    )


async def test_patient_update_records_before_and_after_for_allow_listed_fields():
    session = _patient_session({"tumor_size_mm": 35.0, "stage": "II"})
    payload = PatientInput(name="SENTINEL-NAME", tumor_size_mm=35, stage="II", er_status="Positive")
    await clinical_router.update_patient("PT-1001", payload, session=session, current_user=ACTOR)

    assert_audit_is_last_write_before_single_commit(session)
    event = session.audit()
    assert (event["action"], event["target"], event["actor"], event["actor_role"]) == (
        "patient.updated", "PT-1001", str(ACTOR_ID), "doctor",
    )
    assert event["before"] == {"tumor_size_mm": 20.0, "stage": "I"}  # unchanged er_status is omitted
    assert event["after"]["tumor_size_mm"] == 35.0 and event["after"]["stage"] == "II"
    assert sorted(event["after"]["changedFields"]) == ["stage", "tumor_size_mm"]
    assert_no_sentinels(session)


async def test_patient_update_of_identifying_fields_logs_names_not_values():
    session = _patient_session({"name": "SENTINEL-NEW", "phone": "SENTINEL-PHONE-2", "notes": "SENTINEL-NOTES-2"})
    payload = PatientInput(name="SENTINEL-NEW", phone="SENTINEL-PHONE-2", notes="SENTINEL-NOTES-2")
    await clinical_router.update_patient("PT-1001", payload, session=session, current_user=ACTOR)

    event = session.audit()
    assert event["before"] == {}
    assert sorted(event["after"]["changedFields"]) == ["name", "notes", "phone"]
    blob = json.dumps(session.audit_rows())
    for leaked in ("SENTINEL-NEW", "SENTINEL-PHONE-2", "SENTINEL-NOTES-2", "SENTINEL-NAME"):
        assert leaked not in blob


async def test_patient_update_with_no_actual_change_writes_no_audit_row():
    session = _patient_session()
    # same values as stored (5 vs 5.0 style differences must not count as a change)
    payload = PatientInput(name="SENTINEL-NAME", stage="I", tumor_size_mm=20, grade=2)
    await clinical_router.update_patient("PT-1001", payload, session=session, current_user=ACTOR)
    assert session.audit_rows() == [] and session.commits == 1


async def test_patient_update_unknown_patient_is_404_without_audit():
    session = FakeSession(rules=[("FOR UPDATE", [], 1)])
    with pytest.raises(HTTPException) as exc:
        await clinical_router.update_patient("PT-9", PatientInput(name="x", stage="II"), session=session, current_user=ACTOR)
    assert exc.value.status_code == 404
    assert session.audit_rows() == [] and session.commits == 0


async def test_patient_update_audit_failure_commits_nothing():
    session = _patient_session({"stage": "II"}, fail_on="INSERT INTO audit_logs")
    with pytest.raises(RuntimeError):
        await clinical_router.update_patient("PT-1001", PatientInput(name="x", stage="II"), session=session, current_user=ACTOR)
    assert session.commits == 0


async def test_patient_delete_is_audited_atomically():
    session = FakeSession(rules=[("UPDATE patients SET deleted_at", [{"id": "pat-uuid-1", "patient_code": "PT-1001"}], 1),
                                 ("FROM patients WHERE deleted_at IS NULL AND (patient_code", [PATIENT], 1)])
    await clinical_router.delete_patient("PT-1001", session=session, current_user=ACTOR)
    assert_audit_is_last_write_before_single_commit(session)
    event = session.audit()
    assert (event["action"], event["target"], event["actor"], event["actor_role"]) == (
        "patient.deleted", "PT-1001", str(ACTOR_ID), "doctor",
    )
    assert event["after"]["patientId"] == "pat-uuid-1"
    assert_no_sentinels(session)

    failing = FakeSession(
        rules=[("UPDATE patients SET deleted_at", [{"id": "p", "patient_code": "PT-1"}], 1),
               ("FROM patients WHERE deleted_at IS NULL AND (patient_code", [PATIENT], 1)], fail_on="INSERT INTO audit_logs"
    )
    with pytest.raises(RuntimeError):
        await clinical_router.delete_patient("PT-1", session=failing, current_user=ACTOR)
    assert failing.commits == 0

    missing = FakeSession(rules=[("UPDATE patients SET deleted_at", [], 0), ("FROM patients WHERE deleted_at IS NULL AND (patient_code", [PATIENT], 1)])
    with pytest.raises(HTTPException):
        await clinical_router.delete_patient("PT-9", session=missing, current_user=ACTOR)
    assert missing.audit_rows() == [] and missing.commits == 0


# --- digital twin -------------------------------------------------------------------------------


def _twin_session(**kwargs):
    return FakeSession(
        rules=[
            ("SELECT * FROM twin_versions", [{**VERSIONS[1], "snapshot": "{}"}], 1),
            ("FROM twin_versions WHERE patient_id", VERSIONS, 1),
            ("FROM patients", [PATIENT], 1),
        ],
        **kwargs,
    )


async def test_resync_audits_in_the_same_transaction():
    session = _twin_session()
    result = await twins_router.resync_twin("PT-1001", session=session, current_user=ACTOR)
    assert result["data"]["version"] == "v3"
    assert_audit_is_last_write_before_single_commit(session)
    event = session.audit()
    assert (event["action"], event["target"], event["actor"], event["actor_role"]) == (
        "twin.resynced", "PT-1001", str(ACTOR_ID), "doctor",
    )
    assert event["before"] == {"activeVersion": "v2"}
    assert event["after"]["version"] == "v3" and event["after"]["trigger"] == "manual"
    assert_no_sentinels(session)  # the twin snapshot (which holds the name) is not copied into the audit


async def test_restore_audits_source_and_new_version():
    session = _twin_session()
    await twins_router.restore_twin_version("PT-1001", "v1", session=session, current_user=ACTOR)
    assert_audit_is_last_write_before_single_commit(session)
    event = session.audit()
    assert event["action"] == "twin.restored" and event["target"] == "PT-1001"
    assert event["before"] == {"activeVersion": "v2"}
    assert event["after"]["version"] == "v3" and event["after"]["sourceVersion"] == "v1"
    assert_no_sentinels(session)


async def test_restore_sends_a_dict_snapshot_as_json_text_with_a_jsonb_cast():
    # asyncpg returns jsonb as a dict; a jsonb parameter must be bound as JSON text (regression)
    session = FakeSession(
        rules=[
            ("SELECT * FROM twin_versions", [{**VERSIONS[1], "snapshot": {"stage": "I", "grade": 2}}], 1),
            ("FROM twin_versions WHERE patient_id", VERSIONS, 1),
            ("FROM patients", [PATIENT], 1),
        ]
    )
    await twins_router.restore_twin_version("PT-1001", "v1", session=session, current_user=ACTOR)
    sql, params = next((s, p) for s, p in session.calls if "INSERT INTO twin_versions" in s)
    assert "CAST(:snapshot AS jsonb)" in sql
    assert isinstance(params["snapshot"], str) and json.loads(params["snapshot"]) == {"stage": "I", "grade": 2}


async def test_archive_audits_previous_state():
    session = _twin_session()
    await twins_router.archive_twin("PT-1001", session=session, current_user=ACTOR)
    assert_audit_is_last_write_before_single_commit(session)
    event = session.audit()
    assert event["action"] == "twin.archived" and event["actor"] == str(ACTOR_ID)
    assert event["before"] == {"twinStatus": "Synced", "activeVersion": "v2"}
    assert event["after"] == {"twinStatus": "Stale", "versionStatus": "Archived", "archivedVersion": "v2"}
    # only the Active version is archived, and the patient is marked Stale (the CHECK-allowed sync state)
    archive_sql, _ = next((s, p) for s, p in session.calls if "UPDATE twin_versions SET status = 'Archived'" in s)
    assert "status = 'Active'" in archive_sql
    assert any("twin_status = 'Stale'" in s for s, _ in session.calls)
    assert not any("'Archived'" in s and "UPDATE patients" in s for s, _ in session.calls)


async def test_archive_without_an_active_version_is_a_conflict_and_writes_nothing():
    session = FakeSession(
        rules=[("SELECT version FROM twin_versions", [], 1), ("FROM patients", [PATIENT], 1)]
    )
    with pytest.raises(ConflictError):
        await twins_router.archive_twin("PT-1001", session=session, current_user=ACTOR)
    assert session.commits == 0 and session.audit_rows() == []
    assert not any(s.startswith("UPDATE") for s, _ in session.calls)


@pytest.mark.parametrize(
    "call",
    [
        lambda s: twins_router.resync_twin("PT-1001", session=s, current_user=ACTOR),
        lambda s: twins_router.restore_twin_version("PT-1001", "v1", session=s, current_user=ACTOR),
        lambda s: twins_router.archive_twin("PT-1001", session=s, current_user=ACTOR),
    ],
    ids=["resync", "restore", "archive"],
)
async def test_twin_operations_commit_nothing_when_the_audit_insert_fails(call):
    session = _twin_session(fail_on="INSERT INTO audit_logs")
    with pytest.raises(RuntimeError):
        await call(session)
    assert session.commits == 0


# --- HTTP level, real SQLite --------------------------------------------------------------------

_PATIENT_COLS = (
    "id, patient_code, name, age, gender, phone, email, hospital, stage, tumor_size_mm, "
    "er_status, pr_status, her2_status, ki67, grade, nodes_involved, current_treatment, "
    "status, risk, survival_probability, last_updated, diagnosed_on, twin_status, history, "
    "notes, deleted_at"
)


def _make_twin_db(maker, with_audit_table):
    def run(sql, params=None, fetch=False):
        async def _go():
            async with maker() as s:
                res = await s.execute(text(sql), params or {})
                await s.commit()
                return [dict(r) for r in res.mappings()] if fetch else None

        return asyncio.run(_go())

    run(f"CREATE TABLE patients ({_PATIENT_COLS})")
    run("CREATE TABLE twin_versions (id, patient_id, version, created_at, status, author, summary, "
        "tumor_size_mm, survival, risk, model, snapshot)")
    run("CREATE TABLE timeline_events (id, patient_id, date, title, detail, kind)")
    if with_audit_table:
        run("CREATE TABLE audit_logs (id, time, actor, actor_role, action, target, before, after, ip)")
    run("INSERT INTO patients (id, patient_code, name, age, stage, tumor_size_mm, risk, "
        "survival_probability, twin_status) VALUES ('p1', 'PT-1', 'SENTINEL-NAME', 50, 'I', 24, 'low', 0.9, 'Stale')")
    return run


def _doctor_headers(client):
    register(client, email="audit-doc@example.com", role="doctor")
    return {"Authorization": f"Bearer {login(client, email='audit-doc@example.com').json()['accessToken']}"}


def test_resync_endpoint_writes_audit_row_with_authenticated_uuid(client, db_sessionmaker):
    db = _make_twin_db(db_sessionmaker, with_audit_table=True)
    headers = _doctor_headers(client)
    assert client.post("/digital-twins/PT-1/resync", headers=headers).status_code == 200

    (row,) = db("SELECT * FROM audit_logs", fetch=True)
    uuid.UUID(row["actor"])  # the user's UUID, not an email
    assert row["actor_role"] == "doctor"
    assert row["action"] == "twin.resynced" and row["target"] == "PT-1" and row["ip"] == ""
    assert "SENTINEL-NAME" not in json.dumps(row)
    assert datetime.fromisoformat(row["time"]).utcoffset() == timedelta(0)
    assert len(db("SELECT * FROM twin_versions", fetch=True)) == 1


def test_resync_endpoint_rolls_back_the_twin_when_audit_cannot_be_written(client, db_sessionmaker):
    db = _make_twin_db(db_sessionmaker, with_audit_table=False)  # audit insert will fail
    headers = _doctor_headers(client)
    assert client.post("/digital-twins/PT-1/resync", headers=headers).status_code == 500

    assert db("SELECT * FROM twin_versions", fetch=True) == []
    assert db("SELECT twin_status FROM patients WHERE id='p1'", fetch=True)[0]["twin_status"] == "Stale"
    assert db("SELECT * FROM timeline_events", fetch=True) == []


def test_audit_failure_does_not_change_authorization(client, db_sessionmaker):
    _make_twin_db(db_sessionmaker, with_audit_table=True)
    register(client, email="audit-res@example.com", role="researcher")
    token = login(client, email="audit-res@example.com").json()["accessToken"]
    r = client.post("/digital-twins/PT-1/resync", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert client.post("/digital-twins/PT-1/resync").status_code == 401
