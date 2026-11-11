"""
PostgreSQL integration tests for transactional audit logging (commit 1c76827).

Runs the REAL handlers (routers/ocr.py, clinical.py, twins.py) with a real SQLAlchemy/asyncpg
session - built with the app's own `build_engine`, so it carries production's asyncpg settings -
against a disposable PostgreSQL database. Skipped unless ONCOTWIN_TEST_PG_URL is set.

Safety: the only connection setting read is ONCOTWIN_TEST_PG_URL (never DATABASE_URL). Before any
DDL the URL must name host 127.0.0.1/localhost, database exactly `oncotwin_it` and role exactly
`oncotwin_test`, and `current_database()` / `current_user` must agree. The public schema of that
database is dropped and rebuilt for every test from:
  * supabase/migrations/*.sql (the repo's schema chain, in timestamp order), and
  * the repo's identity models (`app.models.identity`, via Base.metadata) for profiles/roles,
    which the OCR migration references but which no SQL migration creates.
Supabase platform objects that exist on Supabase but not on plain Postgres (role `authenticated`,
schema `auth` with `auth.uid()`) are stubbed - they are referenced only by RLS policies.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1.routers import clinical as clinical_router
from app.api.v1.routers import ocr as ocr_router
from app.api.v1.routers import twins as twins_router
from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.db.session import build_engine
from app.dependencies.auth import CurrentUser
from app.models.base import Base
from app.models.identity import SEED_ROLES, Profile, Role
from app.schemas.clinical import PatientInput
from app.schemas.ocr import OcrApproveRequest, OcrRejectRequest
from app.services import ocr_provider, storage

PG_URL = os.environ.get("ONCOTWIN_TEST_PG_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="ONCOTWIN_TEST_PG_URL is not set")

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
USER_ID = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
USER = CurrentUser(id=USER_ID, email="it-doctor@example.test", role="doctor")


# --- safety + schema ----------------------------------------------------------------------------


def _checked_url():
    url = make_url(PG_URL)
    assert url.host in ("127.0.0.1", "localhost"), "test database must be local"
    assert url.database == "oncotwin_it", "database name must be exactly oncotwin_it"
    assert url.username == "oncotwin_test", "role must be exactly oncotwin_test"
    return url


async def _raw():
    url = _checked_url()
    conn = await asyncpg.connect(url.set(drivername="postgresql").render_as_string(hide_password=False))
    db, user = await conn.fetchrow("SELECT current_database(), current_user")
    if (db, user) != ("oncotwin_it", "oncotwin_test"):
        await conn.close()
        pytest.fail("connected session is not oncotwin_it / oncotwin_test - refusing to run any DDL")
    return conn


@pytest_asyncio.fixture()
async def pg():
    """Fresh schema per test; yields (engine, maker)."""
    conn = await _raw()  # guards have passed before any DDL below
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        await conn.execute(
            "CREATE SCHEMA IF NOT EXISTS auth;"
            "CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;"
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') "
            "THEN CREATE ROLE authenticated NOLOGIN; END IF; END $$;"
        )
        files = sorted(MIGRATIONS.glob("*.sql"))
        # identity tables go in after the baseline and before the OCR migration that references profiles
        for f in files:
            if f.name.startswith("20261007121000"):
                await _create_identity()
            await conn.execute(f.read_text(encoding="utf-8"))
    finally:
        await conn.close()
    engine = build_engine(PG_URL)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with maker() as s:
        s.add_all([Role(id=i, name=n, description=d) for i, n, d in SEED_ROLES])
        s.add(Profile(id=USER_ID, full_name="IT Doctor", email="it-doctor@example.test"))
        await s.commit()
    yield engine, maker
    await engine.dispose()


async def _create_identity():
    engine = build_engine(PG_URL)
    try:
        async with engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def q(sql, *args):
    conn = await _raw()
    try:
        return [dict(r) for r in await conn.fetch(sql, *args)]
    finally:
        await conn.close()


async def ddl(sql):
    conn = await _raw()
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


# --- seed + inspect -----------------------------------------------------------------------------


async def seed(code="PT-1001", fields=(("stage", "II", 0.93, "text-layer"), ("tumor_size_mm", "35.5", None, "ocr"))):
    conn = await _raw()
    try:
        pid, doc, ext = (f"pat-{code}", f"doc-{code}", f"ext-{code}")
        await conn.execute(
            "INSERT INTO patients (id, patient_code, name, age, phone, email, stage, tumor_size_mm, er_status, "
            "pr_status, her2_status, ki67, grade, nodes_involved, status, risk, survival_probability, twin_status, notes) "
            "VALUES ($1,$2,'SENTINEL-NAME',50,'SENTINEL-PHONE','SENTINEL-EMAIL','I',20,'Positive','Positive',"
            "'Negative',12,2,0,'Monitoring','low',0.9,'Synced','SENTINEL-NOTES')", pid, code)
        await conn.execute(
            "INSERT INTO twin_versions (id, patient_id, version, created_at, status, author, summary, tumor_size_mm, "
            "survival, risk, model, snapshot) VALUES ($1,$2,'v1','2026-01-01T00:00:00+00:00','Active','seed','',20,0.9,"
            "'low','seed','{}'::jsonb)", f"tv-{code}", pid)
        await conn.execute(
            "INSERT INTO documents (id, name, category, patient_id, status, mime_type, size_bytes, storage_path, "
            "created_at, updated_at) VALUES ($1,'scan.pdf','Blood',$2,'Needs review','application/pdf',10,'p',"
            "'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')", doc, pid)
        await conn.execute(
            "INSERT INTO ocr_extractions (id, document_id, patient_id, status, model) VALUES ($1,$2,$3,'Extracted','seed-ocr')",
            ext, doc, pid)
        await conn.execute("INSERT INTO patient_access (patient_id, profile_id, relationship) VALUES ($1, $2, 'care_team')", pid, USER_ID)
        for name, value, conf, source in fields:
            await conn.execute(
                "INSERT INTO ocr_extraction_fields (id, extraction_id, field_name, label, extracted_value, confidence, "
                "source, status) VALUES ($1,$2,$3,$3,$4,$5,$6,'pending')", f"f-{code}-{name}", ext, name, value, conf, source)
        return SimpleNamespace(code=code, pid=pid, doc=doc, ext=ext)
    finally:
        await conn.close()


async def state(case):
    """Everything an approval can change, read through a separate connection (committed data only)."""
    (patient,) = await q("SELECT stage, tumor_size_mm, twin_status, last_updated FROM patients WHERE id=$1", case.pid)
    (ext,) = await q("SELECT status, reviewed_by, reviewed_at FROM ocr_extractions WHERE id=$1", case.ext)
    (doc,) = await q("SELECT status, updated_at FROM documents WHERE id=$1", case.doc)
    return {
        "patient": patient, "extraction": ext, "document": doc,
        "fields": await q("SELECT field_name, status FROM ocr_extraction_fields WHERE extraction_id=$1 ORDER BY 1", case.ext),
        "twins": await q("SELECT version, status FROM twin_versions WHERE patient_id=$1 ORDER BY created_at, version", case.pid),
        "audit": await q("SELECT id FROM audit_logs WHERE target=$1", case.code),
        "timeline": await q("SELECT title FROM timeline_events WHERE patient_id=$1", case.pid),
    }


def jl(value):
    return json.loads(value) if isinstance(value, str) else value


async def approve(maker, case, fields, user=USER):
    async with maker() as s:  # closing the session without a commit rolls back, as get_db_session does
        return await ocr_router.approve_extraction(
            case.doc, OcrApproveRequest(fields=fields), session=s, current_user=user)


STAGE_III = [{"field": "stage", "value": "III"}, {"field": "tumor_size_mm", "value": "35.5"}]


# --- 1. OCR approval -> patient -> twin -> audit -------------------------------------------------


async def test_ocr_approval_updates_patient_twin_and_audit_atomically(pg):
    _, maker = pg
    case = await seed()
    result = await approve(maker, case, STAGE_III)
    assert result["ok"] is True

    st = await state(case)
    assert st["patient"]["stage"] == "III" and st["patient"]["tumor_size_mm"] == 35.5
    assert st["patient"]["twin_status"] == "Synced"
    assert st["extraction"]["status"] == "Approved" and st["extraction"]["reviewed_by"] == USER_ID
    assert st["document"]["status"] == "Verified"
    assert {f["field_name"]: f["status"] for f in st["fields"]} == {"stage": "approved", "tumor_size_mm": "approved"}
    assert [(t["version"], t["status"]) for t in st["twins"]] == [("v1", "Superseded"), ("v2", "Active")]
    assert len(st["timeline"]) == 2  # approval event + twin resync event

    (row,) = await q("SELECT *, actor::uuid AS actor_uuid, time::timestamptz AS ts FROM audit_logs WHERE target=$1", case.code)
    assert row["actor_uuid"] == USER_ID and row["actor"] == str(USER_ID) and row["actor_role"] == "doctor"
    assert row["action"] == "ocr.approved" and row["ip"] == ""
    assert row["ts"].utcoffset() == timedelta(0)
    before, after = jl(row["before"]), jl(row["after"])
    assert before == {"stage": "I", "tumor_size_mm": 20.0}
    assert after["applied"] == {"stage": "III", "tumor_size_mm": 35.5}
    assert after["fields"]["stage"] == {"extracted": "II", "edited": True, "confidence": 0.93, "source": "text-layer"}
    assert after["fields"]["tumor_size_mm"]["edited"] is False and after["fields"]["tumor_size_mm"]["source"] == "ocr"
    assert after["twinVersion"] == "v2" and after["previousTwinVersion"] == "v1"
    blob = json.dumps(row, default=str)
    assert not any(s in blob for s in ("SENTINEL-NAME", "SENTINEL-PHONE", "SENTINEL-EMAIL", "SENTINEL-NOTES"))
    # jsonb really is jsonb (not text holding json)
    (types,) = await q("SELECT jsonb_typeof(before) b, jsonb_typeof(after) a, jsonb_typeof(after->'applied') p, "
                       "jsonb_typeof(after->'applied'->'tumor_size_mm') n FROM audit_logs WHERE target=$1", case.code)
    assert types == {"b": "object", "a": "object", "p": "object", "n": "number"}


async def test_postgres_column_types_and_bindings(pg):
    _, maker = pg
    case = await seed()
    await approve(maker, case, STAGE_III)
    types = {(r["table_name"], r["column_name"]): r["data_type"] for r in await q(
        "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND "
        "(table_name, column_name) IN (('ocr_extractions','reviewed_by'),('ocr_extractions','reviewed_at'),"
        "('documents','updated_at'),('patients','last_updated'),('timeline_events','date'),('twin_versions','created_at'),"
        "('twin_versions','snapshot'),('audit_logs','before'),('audit_logs','after'),('audit_logs','time'))")}
    assert types[("ocr_extractions", "reviewed_by")] == "uuid"          # bound from a str UUID
    assert types[("ocr_extractions", "reviewed_at")] == "timestamp with time zone"  # bound from a datetime
    for col in (("documents", "updated_at"), ("patients", "last_updated"), ("timeline_events", "date"),
                ("twin_versions", "created_at"), ("audit_logs", "time")):
        assert types[col] == "text"                                      # bound from ISO strings
    assert types[("twin_versions", "snapshot")] == "jsonb" and types[("audit_logs", "after")] == "jsonb"
    st = await state(case)
    assert isinstance(st["extraction"]["reviewed_at"], datetime) and st["extraction"]["reviewed_at"].tzinfo
    assert datetime.fromisoformat(st["document"]["updated_at"]).utcoffset() == timedelta(0)
    assert datetime.fromisoformat(st["patient"]["last_updated"]).utcoffset() == timedelta(0)
    (snap,) = await q("SELECT jsonb_typeof(snapshot) t, snapshot->>'stage' s FROM twin_versions WHERE patient_id=$1 AND version='v2'", case.pid)
    assert snap == {"t": "object", "s": "III"}  # twin snapshot reflects the just-approved value (same transaction)


# --- 2. patient update -------------------------------------------------------------------------


async def test_patient_update_audit_has_exact_before_after_jsonb(pg):
    _, maker = pg
    case = await seed()
    async with maker() as s:
        out = await clinical_router.update_patient(
            case.code, PatientInput(name="SENTINEL-NAME-2", stage="II", tumor_size_mm=31.5, er_status="Positive", notes="SENTINEL-NOTES-2"),
            session=s, current_user=USER)
    assert out["ok"] is True
    (row,) = await q("SELECT * FROM audit_logs WHERE target=$1", case.code)
    assert (row["action"], row["actor"], row["actor_role"]) == ("patient.updated", str(USER_ID), "doctor")
    before, after = jl(row["before"]), jl(row["after"])
    assert before == {"stage": "I", "tumor_size_mm": 20.0}            # er_status unchanged -> omitted
    assert after["stage"] == "II" and after["tumor_size_mm"] == 31.5
    assert sorted(after["changedFields"]) == ["name", "notes", "stage", "tumor_size_mm"]
    blob = json.dumps(row, default=str)
    assert not any(s_ in blob for s_ in ("SENTINEL-NAME", "SENTINEL-NOTES"))
    (p,) = await q("SELECT stage, tumor_size_mm, name FROM patients WHERE id=$1", case.pid)
    assert p == {"stage": "II", "tumor_size_mm": 31.5, "name": "SENTINEL-NAME-2"}


async def test_patient_update_without_change_writes_no_audit_row(pg):
    _, maker = pg
    case = await seed()
    async with maker() as s:
        await clinical_router.update_patient(case.code, PatientInput(name="SENTINEL-NAME", stage="I", tumor_size_mm=20), session=s, current_user=USER)
    assert await q("SELECT 1 FROM audit_logs") == []


async def test_for_update_serializes_concurrent_patient_updates(pg):
    _, maker = pg
    case = await seed()

    async def upd(value):
        async with maker() as s:
            await clinical_router.update_patient(case.code, PatientInput(name="SENTINEL-NAME", tumor_size_mm=value), session=s, current_user=USER)

    await asyncio.gather(upd(30), upd(40))
    rows = await q("SELECT before, after FROM audit_logs WHERE target=$1 ORDER BY time", case.code)
    assert len(rows) == 2
    firsts = [jl(r["before"])["tumor_size_mm"] for r in rows]
    afters = [jl(r["after"])["tumor_size_mm"] for r in rows]
    # a serialized chain: 20 -> X -> Y, i.e. the second writer's `before` is the first writer's `after`
    assert firsts[0] == 20.0 and firsts[1] == afters[0] and {afters[0], afters[1]} == {30.0, 40.0}


async def test_patient_delete_is_audited(pg):
    _, maker = pg
    case = await seed()
    async with maker() as s:
        await clinical_router.delete_patient(case.code, session=s, current_user=USER)
    (p,) = await q("SELECT deleted_at FROM patients WHERE id=$1", case.pid)
    assert p["deleted_at"] is not None
    (row,) = await q("SELECT * FROM audit_logs WHERE target=$1", case.code)
    assert row["action"] == "patient.deleted" and jl(row["after"])["patientId"] == case.pid


# --- 3. manual resync / restore / archive ------------------------------------------------------


async def test_manual_resync_creates_version_and_audit(pg):
    _, maker = pg
    case = await seed()
    async with maker() as s:
        out = await twins_router.resync_twin(case.code, session=s, current_user=USER)
    assert out["data"]["version"] == "v2"
    assert [(t["version"], t["status"]) for t in (await state(case))["twins"]] == [("v1", "Superseded"), ("v2", "Active")]
    (row,) = await q("SELECT * FROM audit_logs WHERE target=$1", case.code)
    assert (row["action"], row["actor"]) == ("twin.resynced", str(USER_ID))
    assert jl(row["before"]) == {"activeVersion": "v1"}
    assert jl(row["after"])["version"] == "v2" and jl(row["after"])["trigger"] == "manual"
    assert "SENTINEL-NAME" not in json.dumps(row, default=str)  # the snapshot (holds the name) is not copied
    (v,) = await q("SELECT snapshot FROM twin_versions WHERE patient_id=$1 AND version='v2'", case.pid)
    assert jl(v["snapshot"])["patient_code"] == case.code


async def test_restore_twin_version_copies_jsonb_snapshot_and_audits(pg):
    _, maker = pg
    case = await seed()
    async with maker() as s:
        await twins_router.resync_twin(case.code, session=s, current_user=USER)  # v2: stage I
    async with maker() as s:
        await clinical_router.update_patient(case.code, PatientInput(name="SENTINEL-NAME", stage="II"), session=s, current_user=USER)
    async with maker() as s:
        await twins_router.resync_twin(case.code, session=s, current_user=USER)  # v3: stage II
    async with maker() as s:
        out = await twins_router.restore_twin_version(case.code, "v2", session=s, current_user=USER)  # -> v4
    assert out["data"]["version"] == "v4"

    versions = [(t["version"], t["status"]) for t in (await state(case))["twins"]]
    assert versions == [("v1", "Superseded"), ("v2", "Superseded"), ("v3", "Superseded"), ("v4", "Active")]
    (v4,) = await q("SELECT summary, tumor_size_mm, survival, risk, model, jsonb_typeof(snapshot) t, snapshot->>'stage' stage, "
                    "snapshot = (SELECT snapshot FROM twin_versions WHERE patient_id=$1 AND version='v2') same_as_v2 "
                    "FROM twin_versions WHERE patient_id=$1 AND version='v4'", case.pid)
    assert v4["summary"] == "Restored from v2." and v4["t"] == "object"
    assert v4["same_as_v2"] is True and v4["stage"] == "I"  # v2's snapshot, not the newer v3 one
    (v2,) = await q("SELECT tumor_size_mm, survival, risk, model FROM twin_versions WHERE patient_id=$1 AND version='v2'", case.pid)
    assert {k: v4[k] for k in v2} == v2
    # restore does not change the patient record (the twin and the record now differ - existing behaviour)
    assert (await q("SELECT stage FROM patients WHERE id=$1", case.pid))[0]["stage"] == "II"

    (row,) = await q("SELECT * FROM audit_logs WHERE action='twin.restored'")
    assert (row["target"], row["actor"], row["actor_role"], row["ip"]) == (case.code, str(USER_ID), "doctor", "")
    assert jl(row["before"]) == {"activeVersion": "v3"}
    assert jl(row["after"])["version"] == "v4" and jl(row["after"])["sourceVersion"] == "v2"
    assert "SENTINEL-NAME" not in json.dumps(row, default=str)
    assert len(await q("SELECT 1 FROM timeline_events WHERE patient_id=$1 AND title LIKE 'Digital twin restored%'", case.pid)) == 1


async def _resync(maker, case):
    async with maker() as s:
        await twins_router.resync_twin(case.code, session=s, current_user=USER)


async def _archive(maker, case):
    async with maker() as s:
        return await twins_router.archive_twin(case.code, session=s, current_user=USER)


async def _version_rows(case):
    return await q("SELECT id, version, status, created_at, summary, tumor_size_mm, survival, risk, model, snapshot::text AS snapshot "
                   "FROM twin_versions WHERE patient_id=$1 ORDER BY created_at, version", case.pid)


async def test_archive_archives_only_the_active_version_and_preserves_history(pg):
    _, maker = pg
    case = await seed()
    await _resync(maker, case)  # v2
    await _resync(maker, case)  # v3 Active; v1, v2 Superseded
    history = {r["version"]: r for r in await _version_rows(case)}
    assert [r["status"] for r in history.values()] == ["Superseded", "Superseded", "Active"]
    patient_before = (await q("SELECT stage, tumor_size_mm, er_status, name FROM patients WHERE id=$1", case.pid))[0]

    out = await _archive(maker, case)
    assert out["ok"] is True

    after = {r["version"]: r for r in await _version_rows(case)}
    assert {v: r["status"] for v, r in after.items()} == {"v1": "Superseded", "v2": "Superseded", "v3": "Archived"}
    for v in ("v1", "v2"):  # superseded history is untouched, field for field
        assert after[v] == history[v]
    assert {k: after["v3"][k] for k in after["v3"] if k != "status"} == {k: history["v3"][k] for k in history["v3"] if k != "status"}
    (p,) = await q("SELECT twin_status, stage, tumor_size_mm, er_status, name, last_updated FROM patients WHERE id=$1", case.pid)
    assert p["twin_status"] == "Stale" and p["last_updated"]
    assert {k: p[k] for k in patient_before} == patient_before  # the clinical record is not touched

    (row,) = await q("SELECT * FROM audit_logs WHERE action='twin.archived'")
    assert (row["target"], row["actor"], row["actor_role"], row["ip"]) == (case.code, str(USER_ID), "doctor", "")
    assert jl(row["before"]) == {"twinStatus": "Synced", "activeVersion": "v3"}
    assert jl(row["after"]) == {"twinStatus": "Stale", "versionStatus": "Archived", "archivedVersion": "v3"}
    assert "SENTINEL-NAME" not in json.dumps(row, default=str)

    # the detail and list endpoints report the same lifecycle status, and keep sync status separate
    async with maker() as s:
        detail = await twins_router.get_twin(case.code, session=s, _user=USER)
        listing = {t["patientId"]: t for t in await twins_router.list_twins(session=s, _user=USER)}
    assert detail["status"] == "Archived" and listing[case.code]["status"] == "Archived"
    assert detail["syncStatus"] == "Stale" and detail["twinStatus"] == "Stale"
    assert detail["active"]["version"] == "v3" and detail["active"]["status"] == "Archived"


async def test_get_twin_status_fields_for_active_and_missing_twins(pg):
    _, maker = pg
    case = await seed()
    async with maker() as s:
        detail = await twins_router.get_twin(case.code, session=s, _user=USER)
    assert (detail["status"], detail["syncStatus"], detail["twinStatus"]) == ("Active", "Synced", "Synced")
    await ddl(f"DELETE FROM twin_versions WHERE patient_id='{case.pid}'")
    async with maker() as s:
        detail = await twins_router.get_twin(case.code, session=s, _user=USER)
    assert (detail["status"], detail["syncStatus"], detail["twinStatus"], detail["active"]) == ("Not created", None, "Not created", None)


async def test_archive_without_an_active_version_is_409_and_changes_nothing(pg):
    _, maker = pg
    case = await seed()
    await _archive(maker, case)  # first archive succeeds
    before, versions = await state(case), await _version_rows(case)
    audits = await q("SELECT id FROM audit_logs")
    with pytest.raises(ConflictError):  # already archived: no Active version
        await _archive(maker, case)
    assert await state(case) == before and await _version_rows(case) == versions and await q("SELECT id FROM audit_logs") == audits

    other = await seed(code="PT-3001")
    await ddl(f"DELETE FROM twin_versions WHERE patient_id='{other.pid}'")  # a patient that never had a twin
    before = await state(other)
    with pytest.raises(ConflictError):
        await _archive(maker, other)
    assert await state(other) == before


async def test_archive_audit_failure_rolls_back_the_archive(pg):
    _, maker = pg
    case = await seed()
    await _resync(maker, case)
    before, versions = await state(case), await _version_rows(case)
    await ddl("ALTER TABLE audit_logs ADD CONSTRAINT force_archive_audit_failure CHECK (action <> 'twin.archived')")
    with pytest.raises(IntegrityError) as exc:
        await _archive(maker, case)
    assert "force_archive_audit_failure" in str(exc.value)
    assert await state(case) == before and await _version_rows(case) == versions  # still Active, still Synced
    assert before["patient"]["twin_status"] == "Synced"


async def test_concurrent_archive_has_one_winner(pg):
    _, maker = pg
    case = await seed()
    results = await asyncio.gather(_archive(maker, case), _archive(maker, case), return_exceptions=True)
    assert sum(isinstance(r, dict) for r in results) == 1 and sum(isinstance(r, ConflictError) for r in results) == 1, results
    assert [r["status"] for r in await _version_rows(case)] == ["Archived"]
    assert len(await q("SELECT 1 FROM audit_logs WHERE action='twin.archived'")) == 1


async def test_resync_after_archive_adds_a_new_active_version_and_keeps_archived_history(pg):
    _, maker = pg
    case = await seed()
    await _resync(maker, case)  # v2 Active
    await _archive(maker, case)  # v2 Archived
    archived_history = {r["version"]: r for r in await _version_rows(case)}
    assert archived_history["v2"]["status"] == "Archived"

    await _resync(maker, case)  # -> v3
    after = {r["version"]: r for r in await _version_rows(case)}
    assert {v: r["status"] for v, r in after.items()} == {"v1": "Superseded", "v2": "Archived", "v3": "Active"}
    assert after["v1"] == archived_history["v1"] and after["v2"] == archived_history["v2"]  # archived history unaltered
    assert (await q("SELECT twin_status FROM patients WHERE id=$1", case.pid))[0]["twin_status"] == "Synced"
    (row,) = await q("SELECT before, after FROM audit_logs WHERE action='twin.resynced' ORDER BY time DESC LIMIT 1")
    assert jl(row["before"]) == {"activeVersion": None} and jl(row["after"])["version"] == "v3"
    async with maker() as s:
        detail = await twins_router.get_twin(case.code, session=s, _user=USER)
    assert (detail["status"], detail["syncStatus"], detail["active"]["version"]) == ("Active", "Synced", "v3")


# --- 4-6. rollback scenarios -------------------------------------------------------------------


async def test_audit_insert_failure_rolls_back_the_whole_approval(pg):
    _, maker = pg
    case = await seed()
    before = await state(case)
    await ddl("ALTER TABLE audit_logs ADD CONSTRAINT force_audit_failure CHECK (action <> 'ocr.approved')")
    with pytest.raises(IntegrityError) as exc:
        await approve(maker, case, STAGE_III)
    assert "force_audit_failure" in str(exc.value)
    assert await state(case) == before  # patient, extraction, fields, document, twin, timeline: all unchanged


async def test_twin_failure_during_approval_rolls_back_the_whole_approval(pg):
    _, maker = pg
    case = await seed()
    before = await state(case)
    await ddl("CREATE FUNCTION fail_twin() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'forced twin failure'; END $$;"
              "CREATE TRIGGER fail_twin_insert BEFORE INSERT ON twin_versions FOR EACH ROW EXECUTE FUNCTION fail_twin();")
    with pytest.raises(Exception) as exc:
        await approve(maker, case, STAGE_III)
    assert "forced twin failure" in str(exc.value)
    after = await state(case)
    assert after == before
    assert after["patient"]["stage"] == "I" and after["extraction"]["status"] == "Extracted" and after["audit"] == []


async def test_check_constraint_failure_rolls_back_the_whole_approval(pg):
    _, maker = pg
    case = await seed(fields=(("stage", "IIA", 0.9, "ocr"),))  # OCR can read a sub-stage the column does not allow
    before = await state(case)
    with pytest.raises(IntegrityError) as exc:
        await approve(maker, case, [{"field": "stage", "value": "IIA"}])
    assert "patients_stage_check" in str(exc.value)
    assert await state(case) == before


# --- 7. concurrent approval --------------------------------------------------------------------


async def _assert_exactly_one_winner(case, results):
    wins = [r for r in results if isinstance(r, dict)]
    losses = [r for r in results if isinstance(r, ConflictError)]
    assert len(wins) == 1 and len(losses) == 1, results
    st = await state(case)
    assert st["extraction"]["status"] == "Approved"
    assert len(st["audit"]) == 1
    assert [(t["version"], t["status"]) for t in st["twins"]] == [("v1", "Superseded"), ("v2", "Active")]
    assert sum(1 for t in st["twins"] if t["status"] == "Active") == 1
    assert len(st["timeline"]) == 2  # one approval event + one resync event, not four
    return st


async def test_concurrent_approval_forced_interleaving_has_one_winner(pg, monkeypatch):
    """Both requests pass the 'status == Extracted' read before either claims the row (worst case)."""
    _, maker = pg
    case = await seed()
    original = ocr_router._latest_extraction
    arrived, gate = 0, asyncio.Event()

    async def gated(session, document_id):
        nonlocal arrived
        row = await original(session, document_id)
        arrived += 1
        if arrived >= 2:
            gate.set()
        await asyncio.wait_for(gate.wait(), 15)
        return row

    monkeypatch.setattr(ocr_router, "_latest_extraction", gated)
    results = await asyncio.gather(
        approve(maker, case, [{"field": "stage", "value": "III"}]),
        approve(maker, case, [{"field": "stage", "value": "IV"}]),
        return_exceptions=True,
    )
    st = await _assert_exactly_one_winner(case, results)
    assert st["patient"]["stage"] in ("III", "IV")
    (row,) = await q("SELECT after FROM audit_logs WHERE target=$1", case.code)
    assert jl(row["after"])["applied"]["stage"] == st["patient"]["stage"]  # audit describes the change that actually landed


async def test_concurrent_approval_unforced_race_repeated(pg):
    _, maker = pg
    for i in range(6):
        case = await seed(code=f"PT-20{i:02d}")
        results = await asyncio.gather(
            approve(maker, case, [{"field": "stage", "value": "III"}]),
            approve(maker, case, [{"field": "stage", "value": "III"}]),
            return_exceptions=True,
        )
        await _assert_exactly_one_winner(case, results)


# --- extract / reject --------------------------------------------------------------------------


async def test_extract_and_reject_sql_and_audit(pg, monkeypatch):
    _, maker = pg
    case = await seed(fields=())
    await ddl(f"UPDATE ocr_extractions SET status='Rejected' WHERE id='{case.ext}'")  # old extraction; extract makes a new one

    async def fake_download(path):
        return b"%PDF-1.4"

    async def fake_extract(content, mime):
        return [ocr_provider.ExtractedField(field="stage", value="SENTINEL-RAW", confidence=0.8, source="ocr"),
                ocr_provider.ExtractedField(field="grade", value="2", confidence=None, source="text-layer")]

    monkeypatch.setattr(storage, "download_document", fake_download)
    monkeypatch.setattr(ocr_provider, "extract_fields", fake_extract)
    monkeypatch.setattr(ocr_provider, "engine_label", lambda: "it-ocr")
    monkeypatch.setattr(get_settings(), "OCR_SUPPORTED_MIME_TYPES", ["application/pdf"], raising=False)

    async with maker() as s:
        out = await ocr_router.extract_document(case.doc, session=s, current_user=USER)
    assert out["ok"] is True
    (ex,) = await q("SELECT after FROM audit_logs WHERE action='ocr.extracted'")
    after = jl(ex["after"])
    assert after["fieldCount"] == 2 and after["sources"] == {"stage": "ocr", "grade": "text-layer"}
    assert "SENTINEL-RAW" not in json.dumps(ex, default=str)
    assert (await q("SELECT status FROM documents WHERE id=$1", case.doc))[0]["status"] == "Needs review"

    async with maker() as s:
        await ocr_router.reject_extraction(case.doc, OcrRejectRequest(reason="SENTINEL-REASON"), session=s, current_user=USER)
    (rej,) = await q("SELECT after FROM audit_logs WHERE action='ocr.rejected'")
    assert jl(rej["after"])["reasonProvided"] is True and "SENTINEL-REASON" not in json.dumps(rej, default=str)
    (stored,) = await q("SELECT reject_reason, status FROM ocr_extractions WHERE document_id=$1 ORDER BY extracted_at DESC LIMIT 1", case.doc)
    assert stored == {"reject_reason": "SENTINEL-REASON", "status": "Rejected"}  # the reason is kept where it always was
    with pytest.raises(ConflictError):
        async with maker() as s:
            await ocr_router.reject_extraction(case.doc, OcrRejectRequest(), session=s, current_user=USER)
