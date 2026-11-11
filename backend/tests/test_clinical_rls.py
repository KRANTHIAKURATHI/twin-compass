"""
C4 / Phase 6.2-A: row-level security on patient-linked clinical tables, tested at the DATABASE layer.

The backend connects as `postgres` (BYPASSRLS), so API tests cannot prove these policies. Here the database is
queried directly as the Supabase roles `anon` / `authenticated` (SET ROLE + the `request.jwt.claim.sub` setting that
Supabase's auth.uid() reads), against a scratch PostgreSQL built from every migration (same guards as the other PG
tests: local host, database `oncotwin_it`, role `oncotwin_test`). Production Supabase is never contacted.

Plain PostgreSQL has no Supabase platform, so the fixture stands in for exactly three things: roles `anon` and
`authenticated`, `auth.uid()` (reads the JWT-subject setting like Supabase), and Supabase's default grants (SELECT on every
table to both roles - the worst case the policies must hold against).
"""
from __future__ import annotations

import asyncio
import uuid

import asyncpg
import pytest

from tests import test_audit_pg_integration as base
from tests import test_clinical_defaults_migration as m
from tests.test_audit_pg_integration import PG_URL

pytestmark = pytest.mark.skipif(not PG_URL, reason="ONCOTWIN_TEST_PG_URL is not set")

DIRECT = ["patients", "appointments", "documents", "imaging_studies", "lab_results", "ocr_extractions", "patient_report_refs",
          "prediction_runs", "reports", "simulation_runs", "timeline_events", "treatment_plans", "twin_snapshots", "twin_versions"]
CHILDREN = {  # child -> (parent class it reaches the patient through)
    "document_versions": "documents", "ocr_fields": "documents", "ocr_extraction_fields": "ocr_extractions",
    "report_versions": "reports", "report_downloads": "reports", "download_records": "reports",
}
ALL = DIRECT + list(CHILDREN)
MIGRATION = m.MIGRATIONS / "20261107120000_clinical_rls.sql"

U = {k: str(uuid.uuid4()) for k in ("docA", "docB", "docC", "docD", "pat1", "pat2", "res", "adm")}
P1, P2 = "rls-p1", "rls-p2"


async def _conn():
    return await base._raw()


async def _setup():
    await m._build(include_new=True)
    c = await _conn()
    try:
        await c.execute("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
            END $$;
            CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
              $$ SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
            GRANT USAGE ON SCHEMA public, auth TO anon, authenticated;
            GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon, authenticated;      -- Supabase default grants (worst case)
            GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated;
        """)
        # the migration already ran inside _build (no roles then); run it again as it would be on a Supabase project
        await c.execute(MIGRATION.read_text(encoding="utf-8"))
        await c.execute("INSERT INTO roles (id, name, description) VALUES (1,'doctor','d'),(2,'admin','a'),(3,'researcher','r'),(4,'patient','p')")
        role_of = {"docA": 1, "docB": 1, "docC": 1, "docD": 1, "pat1": 4, "pat2": 4, "res": 3, "adm": 2}
        for k, uid in U.items():
            await c.execute("INSERT INTO profiles (id, full_name, email, is_active) VALUES ($1::uuid, $2, $3, true)", uid, k, f"{k}@example.com")
            await c.execute("INSERT INTO user_roles (id, profile_id, role_id) VALUES (gen_random_uuid(), $1::uuid, $2)", uid, role_of[k])
        for pid, code in ((P1, "PT-R1"), (P2, "PT-R2")):
            await c.execute("INSERT INTO patients (id, patient_code, name) VALUES ($1, $2, $3)", pid, code, "Name " + code)
        grants = [(P1, "docA", "care_team"), (P2, "docB", "care_team"), (P1, "pat1", "self"), (P2, "pat2", "self"),
                  (P1, "res", "care_team"),      # a researcher with a stray care-team row must still see nothing
                  (P1, "docD", "self")]          # a doctor with a 'self' row must still see nothing
        for pid, k, rel in grants:
            await c.execute("INSERT INTO patient_access (patient_id, profile_id, relationship) VALUES ($1, $2::uuid, $3)", pid, U[k], rel)
        for n, pid in ((1, P1), (2, P2)):
            s = f"-{n}"
            await c.execute(f"INSERT INTO documents (id, name, patient_id) VALUES ('doc{s}', 'f', '{pid}')")
            await c.execute(f"INSERT INTO ocr_extractions (id, document_id, patient_id) VALUES ('ext{s}', 'doc{s}', '{pid}')")
            await c.execute(f"INSERT INTO reports (id, title, patient_id) VALUES ('rep{s}', 't', '{pid}')")
            for t in ("appointments", "imaging_studies", "lab_results", "patient_report_refs", "prediction_runs",
                      "simulation_runs", "timeline_events", "treatment_plans", "twin_snapshots", "twin_versions"):
                await c.execute(f"INSERT INTO {t} (id, patient_id) VALUES ('{t}{s}', '{pid}')")
            await c.execute(f"INSERT INTO document_versions (id, document_id) VALUES ('dv{s}', 'doc{s}')")
            await c.execute(f"INSERT INTO ocr_fields (id, document_id, field) VALUES ('of{s}', 'doc{s}', 'f')")
            await c.execute(f"INSERT INTO ocr_extraction_fields (id, extraction_id, field_name, label) VALUES ('oef{s}', 'ext{s}', 'a', 'a')")
            await c.execute(f"INSERT INTO report_versions (id, report_id) VALUES ('rv{s}', 'rep{s}')")
            await c.execute(f"INSERT INTO report_downloads (id, report_id, format, downloaded_at) VALUES ('rd{s}', 'rep{s}', 'pdf', 'x')")
            await c.execute(f"INSERT INTO download_records (id, report_id) VALUES ('dr{s}', 'rep{s}')")
    finally:
        await c.close()


@pytest.fixture(scope="module", autouse=True)
def database():
    asyncio.run(_setup())


async def as_role(role: str, uid: str | None, sql: str, *args):
    c = await _conn()
    try:
        await c.execute(f"SET ROLE {role}")
        await c.execute("SELECT set_config('request.jwt.claim.sub', $1, false)", uid or "")
        return await c.fetch(sql, *args)
    finally:
        try:
            await c.execute("RESET ROLE")
        finally:
            await c.close()


def count(role, who, table):
    rows = asyncio.run(as_role(role, U.get(who), f"SELECT count(*) AS n FROM public.{table}"))
    return rows[0]["n"]


# ------------------------------------------------------------------ structure

def test_rls_is_enabled_exactly_on_the_approved_clinical_tables_and_patient_access_stays_policy_free():
    async def go():
        c = await _conn()
        try:
            rls = {r["relname"] for r in await c.fetch(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity")}
            pol = await c.fetch("SELECT tablename, policyname, cmd, roles FROM pg_policies WHERE schemaname='public'")
            return rls, pol
        finally:
            await c.close()
    rls, pol = asyncio.run(go())
    assert set(ALL) <= rls and "patient_access" in rls
    # not enabled blindly: audit_logs / notifications / registries are outside this change
    assert not {"audit_logs", "notifications", "ml_models", "datasets", "hospitals"} & rls
    assert {p["tablename"] for p in pol} == set(ALL)                      # nothing on patient_access
    assert all(p["cmd"] == "SELECT" for p in pol)                         # no write policy for any role
    assert all(list(p["roles"]) == ["authenticated"] for p in pol)        # and none for anon / public
    assert len(pol) == len(ALL)                                           # exactly one policy per protected table
    assert not any(p["policyname"].endswith(("_write_clinical_roles", "_review_clinical_roles", "_read_clinical_roles")) for p in pol)


def test_policy_helper_is_locked_down():
    async def go():
        c = await _conn()
        try:
            f = (await c.fetch("SELECT prosecdef, proconfig, proacl::text AS acl FROM pg_proc WHERE proname='can_read_patient'"))[0]
            return f
        finally:
            await c.close()
    f = asyncio.run(go())
    assert f["prosecdef"] is True and any("search_path=pg_catalog, public" in x for x in f["proconfig"])
    import re
    assert "authenticated=X" in f["acl"] and "anon=" not in f["acl"] and not re.search(r"(^|[{,])=X/", f["acl"])   # no PUBLIC/anon execute


def test_policy_lookup_columns_are_indexed():
    async def go():
        c = await _conn()
        try:
            return [r["indexdef"] for r in await c.fetch("SELECT indexdef FROM pg_indexes WHERE schemaname='public'")]
        finally:
            await c.close()
    idx = " ".join(asyncio.run(go()))
    assert "patient_access USING btree (patient_id, profile_id, relationship)" in idx        # the policy's lookup
    for t in ALL:
        if t == "patients":
            continue
        assert f"ON public.{t} USING btree" in idx, t                                        # FK / join columns are indexed


# ------------------------------------------------------------------ anon

@pytest.mark.parametrize("table", ALL)
def test_anon_has_no_table_privileges_and_no_rows(table):
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        count("anon", None, table)                                  # grants revoked by the migration


def test_anon_still_sees_nothing_if_its_grants_come_back():
    async def regrant():
        c = await _conn()
        try:
            await c.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon")
        finally:
            await c.close()
    asyncio.run(regrant())
    try:
        for t in ALL:
            assert count("anon", None, t) == 0, t                   # RLS alone: no policy for anon
    finally:
        asyncio.run(_revoke_anon())


async def _revoke_anon():
    c = await _conn()
    try:
        await c.execute(MIGRATION.read_text(encoding="utf-8"))      # idempotent: re-applies the revokes
    finally:
        await c.close()


@pytest.mark.parametrize("table", ["patients", "documents", "reports", "prediction_runs", "twin_versions", "treatment_plans"])
def test_anon_reads_no_patient_records_documents_reports_predictions_twins_or_plans(table):
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        count("anon", None, table)


# ------------------------------------------------------------------ authenticated roles

@pytest.mark.parametrize("table", ALL)
def test_assigned_doctor_sees_only_their_patients_rows(table):
    assert count("authenticated", "docA", table) == 1
    assert count("authenticated", "docB", table) == 1


@pytest.mark.parametrize("table", ALL)
def test_unassigned_doctor_sees_nothing(table):
    assert count("authenticated", "docC", table) == 0


@pytest.mark.parametrize("table", ALL)
def test_patient_sees_only_their_own_rows(table):
    assert count("authenticated", "pat1", table) == 1
    assert count("authenticated", "pat2", table) == 1


@pytest.mark.parametrize("table", ALL)
def test_researcher_sees_no_identified_data_even_with_a_stray_access_row(table):
    assert count("authenticated", "res", table) == 0


@pytest.mark.parametrize("table", ALL)
def test_a_doctor_with_only_a_self_row_sees_nothing(table):
    assert count("authenticated", "docD", table) == 0                # relationship must match the role


@pytest.mark.parametrize("table", ALL)
def test_admin_sees_every_row(table):
    assert count("authenticated", "adm", table) == 2


def test_the_rows_returned_belong_to_the_right_patient():
    rows = asyncio.run(as_role("authenticated", U["docA"], "SELECT id, patient_code FROM public.patients"))
    assert [(r["id"], r["patient_code"]) for r in rows] == [(P1, "PT-R1")]
    rows = asyncio.run(as_role("authenticated", U["pat2"], "SELECT patient_id FROM public.twin_versions"))
    assert [r["patient_id"] for r in rows] == [P2]
    rows = asyncio.run(as_role("authenticated", U["docA"], "SELECT report_id FROM public.report_downloads"))
    assert [r["report_id"] for r in rows] == ["rep-1"]               # child row reached through its parent report


def test_an_unauthenticated_authenticated_session_sees_nothing():
    assert asyncio.run(as_role("authenticated", None, "SELECT count(*) AS n FROM public.patients"))[0]["n"] == 0


# ------------------------------------------------------------------ writes, helper, patient_access

@pytest.mark.parametrize("table", ["patients", "documents", "twin_versions", "ocr_extractions", "ocr_extraction_fields", "reports"])
def test_no_write_path_through_the_data_api(table):
    # authenticated holds no INSERT/UPDATE/DELETE privilege (only the default SELECT grant) and no write policy exists
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(as_role("authenticated", U["adm"], f"UPDATE public.{table} SET id = id"))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(as_role("authenticated", U["adm"], f"DELETE FROM public.{table}"))


def test_even_with_write_grants_no_write_policy_means_no_rows_change():
    async def go():
        c = await _conn()
        try:
            await c.execute("GRANT UPDATE, DELETE, INSERT ON public.patients TO authenticated")
        finally:
            await c.close()
    asyncio.run(go())
    try:
        rows = asyncio.run(as_role("authenticated", U["adm"], "UPDATE public.patients SET name = 'tampered' RETURNING id"))
        assert rows == []                                            # RLS: no UPDATE policy -> zero rows touched
        with pytest.raises(asyncpg.InsufficientPrivilegeError):   # insert: 'violates row-level security policy' is SQLSTATE 42501
            asyncio.run(as_role("authenticated", U["adm"], "INSERT INTO public.patients (id, patient_code, name) VALUES ('x','PT-X','x')"))
        assert asyncio.run(_superuser("SELECT count(*) AS n FROM patients WHERE name='tampered'"))[0]["n"] == 0
    finally:
        asyncio.run(_superuser("REVOKE INSERT, UPDATE, DELETE ON public.patients FROM authenticated"))


async def _superuser(sql):
    c = await _conn()
    try:
        return await c.fetch(sql)
    finally:
        await c.close()


def test_patient_access_stays_closed_to_authenticated_callers():
    # RLS on, no policy: a doctor cannot enumerate access grants through the Data API either
    for who in ("docA", "adm", "pat1"):
        assert count("authenticated", who, "patient_access") == 0


def test_helper_answers_only_for_the_caller_and_denies_unknown_patients():
    def can(who, pid):
        return asyncio.run(as_role("authenticated", U.get(who), "SELECT public.can_read_patient($1) AS ok", pid))[0]["ok"]
    assert can("docA", P1) is True and can("docA", P2) is False and can("docC", P1) is False
    assert can("adm", P2) is True and can("adm", "no-such-patient") is True      # admin: any (incl. orphan rows)
    assert can("docA", None) is False and can("res", P1) is False
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(as_role("anon", None, "SELECT public.can_read_patient('rls-p1')"))


def test_migration_is_idempotent_and_changes_no_data():
    before = asyncio.run(_superuser("SELECT (SELECT count(*) FROM patients) p, (SELECT count(*) FROM documents) d, (SELECT count(*) FROM patient_access) a"))[0]
    asyncio.run(_revoke_anon())                                       # re-apply the migration
    after = asyncio.run(_superuser("SELECT (SELECT count(*) FROM patients) p, (SELECT count(*) FROM documents) d, (SELECT count(*) FROM patient_access) a"))[0]
    assert dict(before) == dict(after)
    n = asyncio.run(_superuser("SELECT count(*) AS n FROM pg_policies WHERE schemaname='public'"))[0]["n"]
    assert n == len(ALL)
