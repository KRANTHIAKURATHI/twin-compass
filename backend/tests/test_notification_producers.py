"""
Notification producers (services/notifications.py) and their two integration points:
OCR extraction ready for review (routers/ocr.py) and prediction run recorded (routers/predictions.py).

Handler-level tests use a recording session so the ORDER of commit vs notification insert and the
failure isolation can be asserted exactly. Visibility is tested against the real /notifications
endpoint on the per-test SQLite database.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from app.api.v1.routers import ocr as ocr_router
from app.api.v1.routers import predictions as pred_router
from app.core.config import get_settings
from app.core.exceptions import UpstreamServiceError
from app.schemas.clinical import PredictionRequest
from app.services import notifications, ocr_provider, storage
from tests.conftest import login, register

USER = SimpleNamespace(id="u1", email="d@x.test")


def _session(fail_notification: bool = False):
    events: list[tuple] = []

    async def execute(statement, params=None):
        sql = str(statement)
        if fail_notification and "INSERT INTO notifications" in sql:
            raise RuntimeError("db unavailable")
        events.append(("sql", sql, params or {}))
        return MagicMock()

    async def commit():
        events.append(("commit",))

    async def rollback():
        events.append(("rollback",))

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute)
    session.commit = AsyncMock(side_effect=commit)
    session.rollback = AsyncMock(side_effect=rollback)
    return session, events


def _inserts(events):
    return [e[2] for e in events if e[0] == "sql" and "INSERT INTO notifications" in e[1]]


def _index(events, pred):
    return next(i for i, e in enumerate(events) if pred(e))


def _assert_broadcast_rows(rows, roles, type_):
    assert sorted(r["role"] for r in rows) == sorted(roles)
    for r in rows:
        assert r["type"] == type_ and r["unread"] is True
        assert r["title"] and r["body"]
        assert datetime.fromisoformat(r["time"]).tzinfo is not None  # ISO-8601, timezone-aware
    assert len({r["id"] for r in rows}) == len(rows)  # distinct ids


# --- OCR ---------------------------------------------------------------------------------------


def _patch_ocr(monkeypatch, extract):
    async def fake_doc(session, document_id):
        return {"id": document_id, "storage_path": "p", "mime_type": "application/pdf"}

    async def fake_download(path):
        return b"%PDF-1.4"

    async def fake_latest(session, document_id):
        return {
            "id": "e1", "status": "Extracted", "document_id": document_id, "patient_id": "pat-1",
            "patient_code": "PT-1001", "model": "m", "extracted_at": None, "reviewed_at": None,
            "reject_reason": None, "reviewed_by_email": None,
        }

    async def fake_fields(session, extraction_id):
        return []

    monkeypatch.setattr(ocr_router, "_get_document_row", fake_doc)
    monkeypatch.setattr(ocr_router, "_latest_extraction", fake_latest)
    monkeypatch.setattr(ocr_router, "_fields_for", fake_fields)
    monkeypatch.setattr(storage, "download_document", fake_download)
    monkeypatch.setattr(ocr_provider, "extract_fields", extract)
    monkeypatch.setattr(ocr_provider, "engine_label", lambda: "mock-ocr")
    monkeypatch.setattr(get_settings(), "OCR_SUPPORTED_MIME_TYPES", ["application/pdf"], raising=False)


async def _one_field(content, mime):
    return [ocr_provider.ExtractedField(field="stage", value="SECRET-VALUE", confidence=0.9)]


async def test_ocr_extract_notifies_doctor_and_admin_after_commit(monkeypatch):
    _patch_ocr(monkeypatch, _one_field)
    session, events = _session()
    result = await ocr_router.extract_document("doc-1", session=session, current_user=USER)

    assert result["ok"] is True
    rows = _inserts(events)
    _assert_broadcast_rows(rows, ["doctor", "admin"], "ocr")
    # user_id is a literal NULL in the SQL, never a bound profile id.
    assert all(":user_id" not in e[1] for e in events if e[0] == "sql" and "INSERT INTO notifications" in e[1])
    # Business data is committed before the notification is written.
    first_commit = _index(events, lambda e: e[0] == "commit")
    first_notification = _index(events, lambda e: e[0] == "sql" and "INSERT INTO notifications" in e[1])
    assert first_commit < first_notification
    # Minimal content: identifiers only, never extracted values.
    for r in rows:
        assert "doc-1" in r["body"] and "PT-1001" in r["body"]
        assert "SECRET-VALUE" not in r["title"] + r["body"]


async def test_ocr_failed_extraction_creates_no_notification(monkeypatch):
    async def failing(content, mime):
        raise UpstreamServiceError("ocr down")

    _patch_ocr(monkeypatch, failing)
    session, events = _session()
    with pytest.raises(UpstreamServiceError):
        await ocr_router.extract_document("doc-1", session=session, current_user=USER)
    assert _inserts(events) == []


async def test_ocr_extraction_with_no_fields_creates_no_notification(monkeypatch):
    async def nothing(content, mime):
        return []

    _patch_ocr(monkeypatch, nothing)
    session, events = _session()
    await ocr_router.extract_document("doc-1", session=session, current_user=USER)
    assert _inserts(events) == []


async def test_ocr_notification_failure_does_not_fail_or_undo_extraction(monkeypatch):
    _patch_ocr(monkeypatch, _one_field)
    session, events = _session(fail_notification=True)
    result = await ocr_router.extract_document("doc-1", session=session, current_user=USER)

    assert result["ok"] is True and result["data"]["documentId"] == "doc-1"
    kinds = [e[0] for e in events]
    assert kinds.count("commit") == 1          # the business commit happened and nothing re-committed
    assert kinds.index("commit") < kinds.index("rollback")
    # Only the failed notification transaction is rolled back; the document status update came before the commit.
    status_update = _index(events, lambda e: e[0] == "sql" and "UPDATE documents" in e[1])
    assert status_update < kinds.index("commit")


# --- predictions -------------------------------------------------------------------------------


def _patch_prediction(monkeypatch, run_model=None):
    async def fake_resolve(session, patient_id):
        return {"id": "pid-1", "patient_code": "PT-2002"}

    async def fake_history(session, patient_uuid):
        return [{"id": "run"}]

    def default_model(patient):
        return {"survival": 0.9, "recurrence": 0.1, "risk": "low", "confidence": 0.8, "status": "Complete"}, "model-x"

    monkeypatch.setattr(pred_router, "resolve_patient", fake_resolve)
    monkeypatch.setattr(pred_router, "_history", fake_history)
    monkeypatch.setattr(pred_router, "_run_model", run_model or default_model)
    monkeypatch.setattr(pred_router, "_prognosis", lambda patient: {})


async def _run_prediction(session):
    return await pred_router.run_prediction(PredictionRequest(patient_id="PT-2002"), session=session, _user=USER)


async def test_prediction_notifies_doctor_admin_researcher_after_commit(monkeypatch):
    _patch_prediction(monkeypatch)
    session, events = _session()
    result = await _run_prediction(session)

    assert result["ok"] is True
    rows = _inserts(events)
    _assert_broadcast_rows(rows, ["doctor", "admin", "researcher"], "prediction")
    run_id = next(e[2]["id"] for e in events if e[0] == "sql" and "INSERT INTO prediction_runs" in e[1])
    first_commit = _index(events, lambda e: e[0] == "commit")
    first_notification = _index(events, lambda e: e[0] == "sql" and "INSERT INTO notifications" in e[1])
    assert first_commit < first_notification
    for r in rows:
        assert run_id in r["body"] and "PT-2002" in r["body"]
        # No clinical results in the message.
        assert not any(token in r["title"] + r["body"] for token in ("survival", "recurrence", "risk", "model-x", "Complete"))


async def test_prediction_failure_creates_no_notification(monkeypatch):
    def failing_model(patient):
        raise UpstreamServiceError("model unavailable")

    _patch_prediction(monkeypatch, run_model=failing_model)
    session, events = _session()
    with pytest.raises(UpstreamServiceError):
        await _run_prediction(session)
    assert _inserts(events) == []
    assert not any(e[0] == "commit" for e in events)


async def test_prediction_notification_failure_does_not_fail_or_undo_run(monkeypatch):
    _patch_prediction(monkeypatch)
    session, events = _session(fail_notification=True)
    result = await _run_prediction(session)

    assert result["ok"] is True and result["message"] == "Prediction run recorded."
    kinds = [e[0] for e in events]
    assert kinds.count("commit") == 1 and kinds.index("commit") < kinds.index("rollback")
    run_insert = _index(events, lambda e: e[0] == "sql" and "INSERT INTO prediction_runs" in e[1])
    assert run_insert < kinds.index("commit")


# --- helper + visibility through the real endpoint -----------------------------------------------


async def test_helper_returns_false_and_rolls_back_on_failure():
    session, events = _session(fail_notification=True)
    ok = await notifications.notify_roles(session, ("doctor",), type_="ocr", title="t", body="b")
    assert ok is False and ("rollback",) in events and ("commit",) not in events


@pytest.fixture()
def notif_table(db_sessionmaker):
    async def _setup():
        async with db_sessionmaker() as s:
            await s.execute(
                text(
                    "CREATE TABLE notifications (id TEXT PRIMARY KEY, user_id TEXT, audience_role TEXT, "
                    "title TEXT, body TEXT, time TEXT, unread BOOLEAN DEFAULT 1, type TEXT)"
                )
            )
            await s.commit()

    asyncio.run(_setup())
    return db_sessionmaker


def _headers(client, email, role):
    register(client, email=email, role=role)
    return {"Authorization": f"Bearer {login(client, email=email).json()['accessToken']}"}


def test_only_intended_roles_see_each_broadcast(client, notif_table):
    async def _produce():
        async with notif_table() as s:
            assert await notifications.notify_roles(s, ("doctor", "admin"), type_="ocr", title="OCR t", body="OCR b")
            assert await notifications.notify_roles(
                s, ("doctor", "admin", "researcher"), type_="prediction", title="P t", body="P b"
            )

    asyncio.run(_produce())

    def types_for(role):
        headers = _headers(client, f"{role}-vis@example.com", role)
        r = client.get("/notifications", headers=headers)
        assert r.status_code == 200
        return sorted(n["type"] for n in r.json())

    assert types_for("doctor") == ["ocr", "prediction"]
    assert types_for("researcher") == ["prediction"]       # not an OCR recipient
    assert types_for("patient") == []                      # not a recipient of either

    # Admin cannot self-register, so its broadcast rows are checked in the table instead.
    async def _admin_types():
        async with notif_table() as s:
            rows = await s.execute(text("SELECT type FROM notifications WHERE audience_role = 'admin' AND user_id IS NULL"))
            return sorted(r[0] for r in rows)

    assert asyncio.run(_admin_types()) == ["ocr", "prediction"]
