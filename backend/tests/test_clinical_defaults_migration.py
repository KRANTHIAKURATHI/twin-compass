"""
Migration 20261105120000_drop_clinical_data_defaults.sql, on a disposable PostgreSQL database
(skipped unless ONCOTWIN_TEST_PG_URL is set; same safety guards as test_audit_pg_integration.py: local host, database
exactly `oncotwin_it`, role exactly `oncotwin_test`). Covers
  fresh database -> every migration -> schema checks, and
  existing schema + legacy rows -> the new migration -> data preservation.
The SQLite-tier tests at the bottom (read paths, no database defaults involved) always run.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.api.v1.routers import predictions as pred_router
from app.api.v1.routers import twins as twins_router
from app.ml.inputs import check_patient_columns
from app.services.response_model import project_scenarios
from tests import test_audit_pg_integration as base
from tests.test_audit_pg_integration import MIGRATIONS, PG_URL, ddl, q

NEW = "20261105120000_drop_clinical_data_defaults.sql"
pg_only = pytest.mark.skipif(not PG_URL, reason="ONCOTWIN_TEST_PG_URL is not set")

CLINICAL = {
    "patients": ["age", "stage", "tumor_size_mm", "er_status", "pr_status", "her2_status", "ki67", "grade", "nodes_involved",
                 "risk", "survival_probability"],
    "twin_versions": ["tumor_size_mm", "survival", "risk"],
    "prediction_runs": ["survival", "recurrence", "response", "confidence"],
    "simulation_runs": ["survival", "response", "confidence"],
}
KEPT = {"patients": ["status", "twin_status", "current_treatment"], "twin_versions": ["status"], "prediction_runs": ["status"]}


async def _build(include_new: bool):
    conn = await base._raw()
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        await conn.execute(
            "CREATE SCHEMA IF NOT EXISTS auth;"
            "CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;"
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') "
            "THEN CREATE ROLE authenticated NOLOGIN; END IF; END $$;")
        for f in sorted(MIGRATIONS.glob("*.sql")):
            if f.name.startswith("20261007121000"):
                await base._create_identity()
            if f.name == NEW and not include_new:
                continue
            await conn.execute(f.read_text(encoding="utf-8"))
    finally:
        await conn.close()


async def _defaults():
    rows = await q("SELECT table_name, column_name, column_default FROM information_schema.columns WHERE table_schema='public' "
                   "AND table_name = ANY($1)", list(CLINICAL))
    return {(r["table_name"], r["column_name"]): r["column_default"] for r in rows}


@pg_only
async def test_fresh_database_has_no_clinical_defaults_and_keeps_workflow_defaults():
    await _build(include_new=True)
    d = await _defaults()
    for table, cols in CLINICAL.items():
        for c in cols:
            assert d[(table, c)] is None, f"{table}.{c} still has default {d[(table, c)]}"
    assert "Monitoring" in d[("patients", "status")] and "Synced" in d[("patients", "twin_status")]
    assert "Active" in d[("twin_versions", "status")]

    # a patient / twin version / prediction run inserted without clinical values stores NULL
    await ddl("INSERT INTO patients (id, patient_code, name) VALUES ('p1', 'PT-1', 'No Data')")
    await ddl("INSERT INTO twin_versions (id, patient_id, version) VALUES ('t1', 'p1', 'v1')")
    await ddl("INSERT INTO prediction_runs (id, patient_id) VALUES ('r1', 'p1')")
    await ddl("INSERT INTO simulation_runs (id, patient_id) VALUES ('s1', 'p1')")
    for table, cols in CLINICAL.items():
        row = (await q(f"SELECT {', '.join(cols)} FROM {table}"))[0]
        assert all(v is None for v in row.values()), (table, row)


@pg_only
async def test_constraints_still_reject_invalid_values_and_accept_explicit_ones():
    await _build(include_new=True)
    await ddl("INSERT INTO patients (id, patient_code, name, stage, grade, er_status, tumor_size_mm, ki67, survival_probability, risk) "
              "VALUES ('p1', 'PT-1', 'Explicit', 'I', 1, 'Negative', 0, 10, 0.9, 'low')")   # explicit values equal to old defaults
    row = (await q("SELECT stage, grade, er_status, tumor_size_mm, ki67, survival_probability, risk FROM patients"))[0]
    assert row == {"stage": "I", "grade": 1, "er_status": "Negative", "tumor_size_mm": 0.0, "ki67": 10.0,
                   "survival_probability": 0.9, "risk": "low"}
    for bad in ("stage = 'IIA'", "grade = 4", "er_status = 'maybe'", "risk = 'extreme'"):
        with pytest.raises(Exception, match="check"):
            await ddl(f"UPDATE patients SET {bad}")


@pg_only
async def test_existing_rows_are_preserved_exactly_by_the_migration():
    await _build(include_new=False)
    before_defaults = await _defaults()
    assert before_defaults[("patients", "stage")] is not None            # the old schema really had the defaults
    # legacy rows: one written from defaults, one fully recorded, one with a model-generated run and a twin version
    await ddl("INSERT INTO patients (id, patient_code, name) VALUES ('legacy', 'PT-1', 'Defaulted')")
    await ddl("INSERT INTO patients (id, patient_code, name, age, stage, tumor_size_mm, er_status, pr_status, her2_status, ki67, "
              "grade, nodes_involved, risk, survival_probability) VALUES ('real', 'PT-2', 'Recorded', 61, 'III', 42.5, 'Positive', "
              "'Negative', 'Positive', 35, 3, 4, 'high', 0.41)")
    await ddl("INSERT INTO twin_versions (id, patient_id, version, model, survival, risk, tumor_size_mm) VALUES "
              "('tv', 'real', 'v1', 'Patient record snapshot', 0.41, 'high', 42.5), ('tv0', 'legacy', 'v1', '', DEFAULT, DEFAULT, DEFAULT)")
    await ddl("INSERT INTO prediction_runs (id, patient_id, model, survival, recurrence, response, confidence) VALUES "
              "('pr', 'real', 'OncoTwin Malignancy Risk Model v1.0.0 (RF malignancy classifier; heuristic survival/recurrence)', "
              "0.77, 0.23, 'Mixed', 0.88)")
    snapshot = {t: await q(f"SELECT * FROM {t} ORDER BY id") for t in ("patients", "twin_versions", "prediction_runs")}

    conn = await base._raw()
    try:
        await conn.execute((MIGRATIONS / NEW).read_text(encoding="utf-8"))
    finally:
        await conn.close()

    for t, rows in snapshot.items():                                       # every existing value is byte-for-byte unchanged
        assert await q(f"SELECT * FROM {t} ORDER BY id") == rows, t
    legacy = (await q("SELECT stage, grade, er_status, survival_probability FROM patients WHERE id='legacy'"))[0]
    assert legacy == {"stage": "I", "grade": 1, "er_status": "Negative", "survival_probability": 0.9}   # NOT rewritten to NULL
    assert (await q("SELECT survival FROM prediction_runs WHERE id='pr'"))[0]["survival"] == 0.77        # model output readable
    after = await _defaults()
    assert all(after[(t, c)] is None for t, cols in CLINICAL.items() for c in cols)

    await ddl("INSERT INTO patients (id, patient_code, name) VALUES ('new', 'PT-3', 'After')")
    new = (await q("SELECT stage, grade, er_status, survival_probability FROM patients WHERE id='new'"))[0]
    assert all(v is None for v in new.values())


@pg_only
async def test_migration_is_idempotent_and_documents_the_provenance_limit():
    await _build(include_new=True)
    conn = await base._raw()
    try:
        await conn.execute((MIGRATIONS / NEW).read_text(encoding="utf-8"))   # second run: no error
    finally:
        await conn.close()
    comment = (await q("SELECT col_description('patients'::regclass, attnum) c FROM pg_attribute "
                       "WHERE attrelid='patients'::regclass AND attname='stage'"))[0]["c"]
    assert "cannot be established" in comment


# --- always-on tests: values that were never supplied do not become inputs or numbers ----------------------------


def test_null_patient_values_never_reach_the_wdbc_pipeline():
    blank = {c: None for c in CLINICAL["patients"] if c not in ("risk", "survival_probability")}
    fields, missing, _ = check_patient_columns(blank)
    assert fields == {} and len(missing) == 9
    # the former defaults, if they were still stored, are only accepted when they are *values*: NULL is never defaulted
    assert check_patient_columns({**blank, "stage": "I"})[0] == {"stage": "I"}


def test_null_patient_values_produce_no_simulation_numbers():
    scenarios, provenance = project_scenarios(tumor_size_mm=None, ki67=None, er_status=None, pr_status=None, her2_status=None,
                                              survival_probability=None, risk=None, regimen="Endocrine therapy")
    assert provenance["unavailableReason"] and all(s["survival5y"] is None and s["projectedSizeMm"] is None for s in scenarios)


def test_twin_version_without_values_does_not_manufacture_survival_or_risk():
    row = {"version": "v1", "created_at": "2026-01-01", "status": "Active", "author": "a", "summary": "", "tumor_size_mm": None,
           "survival": None, "risk": None, "model": "Patient record snapshot"}
    out = twins_router._version_response(row)
    assert out["survival"] is None and out["risk"] is None and out["tumorSizeMm"] is None


def test_recorded_and_model_generated_twin_values_remain_readable():
    row = {"version": "v2", "created_at": "2026-01-02", "status": "Active", "author": "a", "summary": "", "tumor_size_mm": 42.5,
           "survival": 0.41, "risk": "high", "model": "Patient record snapshot"}
    out = twins_router._version_response(row)
    assert (out["tumorSizeMm"], out["survival"], out["risk"]) == (42.5, 0.41, "high")


async def test_progression_skips_versions_without_a_measurement_and_keeps_real_ones(monkeypatch):
    rows = [{"version": "v1", "created_at": "1", "tumor_size_mm": None, "survival": None},
            {"version": "v2", "created_at": "2", "tumor_size_mm": 0.0, "survival": 0.9},
            {"version": "v3", "created_at": "3", "tumor_size_mm": 30.0, "survival": None},
            {"version": "v4", "created_at": "4", "tumor_size_mm": 25.5, "survival": 0.8}]

    class _R:
        def mappings(self):
            return rows

    class _S:
        async def execute(self, *a, **k):
            return _R()

    async def fake_resolve(session, pid, user=None):
        return {"id": "p1"}

    monkeypatch.setattr(pred_router, "resolve_patient", fake_resolve)
    out = await pred_router.tumor_size_history("PT-1", session=_S(), _user=SimpleNamespace())
    assert [(p["version"], p["tumorSizeMm"], p["survival"]) for p in out] == [("v3", 30.0, None), ("v4", 25.5, 80.0)]


@pg_only
async def test_patient_created_through_the_api_without_clinical_values_stores_null_and_explicit_values_persist():
    from app.api.v1.routers import clinical
    from app.schemas.clinical import PatientInput
    await _build(include_new=True)
    maker = base.async_sessionmaker(bind=base.build_engine(PG_URL), expire_on_commit=False, autoflush=False)
    await ddl(f"INSERT INTO profiles (id, full_name, email, is_active) VALUES ('{base.USER_ID}', 'IT Doctor', 'it-doctor@example.test', true)")  # care-team FK
    async with maker() as s:
        await clinical.create_patient(PatientInput(name="Blank"), session=s, current_user=base.USER)
    async with maker() as s:
        await clinical.create_patient(PatientInput(name="Full", age=61, stage="III", tumor_size_mm=42.5, er_status="Positive",
                                                   pr_status="Negative", her2_status="Positive", ki67=35, grade=3,
                                                   nodes_involved=4, risk="high", survival_probability=0.41),
                                      session=s, current_user=base.USER)
    rows = {r["name"]: r for r in await q("SELECT * FROM patients")}
    assert all(rows["Blank"][c] is None for c in CLINICAL["patients"])
    assert (rows["Full"]["age"], rows["Full"]["stage"], rows["Full"]["tumor_size_mm"], rows["Full"]["er_status"],
            rows["Full"]["grade"], rows["Full"]["nodes_involved"], rows["Full"]["survival_probability"]) == (61, "III", 42.5, "Positive", 3, 4, 0.41)
    fields, missing, _ = check_patient_columns(dict(rows["Blank"]))
    assert fields == {} and len(missing) == 9                      # and nothing from it reaches the WDBC pipeline
