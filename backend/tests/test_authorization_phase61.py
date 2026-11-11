"""
Phase 6.1 authorization: C1 (no self-granted privileged roles), C2 (patient-level access), C3 (patient ownership of
the treatment plan), H1 (researchers get no identified patient data).

Two tiers:
  * SQLite tier (always runs): registration / approval behaviour, which only touches the identity tables.
  * PostgreSQL tier (needs ONCOTWIN_TEST_PG_URL, same guards as the other PG tests): the real schema built from every
    migration including patient_access, the real routers, real admin approval and access endpoints, fake patients only.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import approve, login, register
from tests.test_audit_pg_integration import PG_URL

# ------------------------------------------------------------------ C1, SQLite tier


def _status(client, email, password="secret123"):
    return client.post("/auth/login", json={"email": email, "password": password}).status_code


def test_public_registration_as_doctor_creates_no_privileges(client):
    r = client.post("/auth/register", json={"email": "newdoc@example.com", "password": "secret123", "name": "N D", "role": "doctor"})
    assert r.status_code == 201 and r.json()["data"] is None and "approved by an administrator" in r.json()["message"]
    assert _status(client, "newdoc@example.com") == 401          # cannot sign in at all
    # and no token can be obtained, so no clinical API is reachable
    assert client.get("/patients").status_code == 401


def test_public_registration_as_researcher_creates_no_privileges(client):
    r = client.post("/auth/register", json={"email": "newres@example.com", "password": "secret123", "name": "N R", "role": "researcher"})
    assert r.status_code == 201 and r.json()["data"] is None
    assert _status(client, "newres@example.com") == 401


def test_default_registration_role_is_pending_not_active_doctor(client):
    r = client.post("/auth/register", json={"email": "dflt@example.com", "password": "secret123", "name": "D"})  # role defaults to doctor
    assert r.status_code == 201 and r.json()["data"] is None and _status(client, "dflt@example.com") == 401


def test_admin_role_still_cannot_be_self_registered(client):
    r = client.post("/auth/register", json={"email": "adm@example.com", "password": "secret123", "name": "A", "role": "admin"})
    assert r.status_code in (403, 422)


def test_patient_registration_still_works_and_signs_in(client):
    r = client.post("/auth/register", json={"email": "p@example.com", "password": "secret123", "name": "P", "role": "patient"})
    assert r.status_code == 201 and r.json()["data"]["role"] == "patient"
    assert _status(client, "p@example.com") == 200


def test_an_approved_doctor_can_authenticate_and_reach_permitted_apis(client):
    client.post("/auth/register", json={"email": "ap@example.com", "password": "secret123", "name": "A P", "role": "doctor"})
    assert _status(client, "ap@example.com") == 401              # pending
    approve(client, "ap@example.com", "doctor")                  # stands in for POST /admin/users/{id}/role (tested on PG below)
    r = client.post("/auth/login", json={"email": "ap@example.com", "password": "secret123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "doctor"
    h = {"Authorization": "Bearer " + r.json()["accessToken"]}
    assert client.get("/auth/me", headers=h).status_code == 200
    assert client.get("/digital-twins", headers=h).status_code != 403   # role check passes (data layer is not under test here)


def test_a_pending_account_with_a_forged_session_is_refused_by_every_api(client, db_sessionmaker):
    # even a validly signed token for a role-less profile must not open anything
    client.post("/auth/register", json={"email": "pend@example.com", "password": "secret123", "name": "P", "role": "doctor"})
    import jwt as pyjwt
    from app.core.config import get_settings
    from sqlalchemy import select
    from app.models.identity import Profile

    async def _pid():
        async with db_sessionmaker() as s:
            return (await s.execute(select(Profile.id).where(Profile.email == "pend@example.com"))).scalar_one()

    pid = asyncio.run(_pid())
    st = get_settings()
    import time
    token = pyjwt.encode({"sub": str(pid), "aud": st.jwt_audience, "exp": int(time.time()) + 600}, st.jwt_secret, algorithm="HS256")
    assert client.get("/patients", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# ------------------------------------------------------------------ PostgreSQL tier

pg_only = pytest.mark.skipif(not PG_URL, reason="ONCOTWIN_TEST_PG_URL is not set")
PW = "Audit-pass-123"
FULL = {"age": 61, "tumorSizeMm": 28, "stage": "II", "grade": 2, "nodesInvolved": 3, "erStatus": "Positive", "prStatus": "Positive",
        "her2Status": "Negative", "ki67": 25, "risk": "moderate", "survivalProbability": 0.8, "currentTreatment": "Endocrine therapy letrozole"}


class World:
    """One PostgreSQL database, built once: admin, two doctors (approved through the admin API), a researcher, two
    patient logins linked to their own record, and a full set of patient-linked resources for each of two patients."""


@pytest.fixture(scope="module")
def world():
    if not PG_URL:
        pytest.skip("ONCOTWIN_TEST_PG_URL is not set")
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.passwords import hash_password
    from app.db.session import build_engine, get_db_session
    from app.main import app
    from app.models.identity import SEED_ROLES, LocalCredential, Profile, Role, UserRole
    from tests import test_clinical_defaults_migration as m
    from tests import test_audit_pg_integration as base

    asyncio.run(m._build(include_new=True))
    engine = build_engine(PG_URL)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async def seed_admin():
        async with maker() as s:
            s.add_all([Role(id=i, name=n, description=d) for i, n, d in SEED_ROLES])
            await s.commit()
            admin = Profile(id=uuid.uuid4(), full_name="Admin", email="admin@example.com")
            s.add(admin)
            await s.flush()
            s.add(UserRole(profile_id=admin.id, role_id=next(i for i, n, _ in SEED_ROLES if n == "admin")))
            s.add(LocalCredential(profile_id=admin.id, password_hash=hash_password(PW)))
            await s.commit()

    asyncio.run(seed_admin())

    async def _override():
        async with maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = _override
    w = World()
    w.client = TestClient(app, raise_server_exceptions=False)
    w.client.__enter__()
    c = w.client

    def reg(email, role):
        r = c.post("/auth/register", json={"email": email, "password": PW, "name": email.split("@")[0], "role": role})
        assert r.status_code == 201, r.text

    def tok(email):
        r = c.post("/auth/login", json={"email": email, "password": PW})
        return {"Authorization": "Bearer " + r.json()["accessToken"]} if r.status_code == 200 else None

    w.reg, w.tok = reg, tok
    w.H = {"admin": tok("admin@example.com")}
    assert w.H["admin"], "admin login failed"
    for email, role in (("docA@example.com", "doctor"), ("docB@example.com", "doctor"), ("docC@example.com", "doctor"),
                        ("res@example.com", "researcher"), ("pat1@example.com", "patient"), ("pat2@example.com", "patient")):
        reg(email, role)
    pending = {p["email"]: p["id"] for p in c.get("/admin/users/pending", headers=w.H["admin"]).json()}
    assert {"doca@example.com", "docb@example.com", "docc@example.com", "res@example.com"} <= set(pending)
    for email, role in (("docA@example.com", "doctor"), ("docB@example.com", "doctor"), ("docC@example.com", "doctor"), ("res@example.com", "researcher")):
        r = c.post(f"/admin/users/{pending[email.lower()]}/role", json={"role": role}, headers=w.H["admin"])
        assert r.status_code == 200, r.text
    # patient logins already have their role; pat1/pat2 are not in the pending list
    for k, e in (("docA", "docA"), ("docB", "docB"), ("docC", "docC"), ("res", "res"), ("pat1", "pat1"), ("pat2", "pat2")):
        w.H[k] = tok(f"{e}@example.com")
        assert w.H[k], k

    def create(who, name):
        r = c.post("/patients", json={"name": name, **FULL}, headers=w.H[who])
        assert r.status_code == 201, r.text
        return r.json()["data"]["id"]

    w.A = create("docA", "SENTINEL-ALPHA")     # PT-1000, care team: docA
    w.B = create("docB", "SENTINEL-BRAVO")     # PT-1001, care team: docB
    ids = {e: asyncio.run(_profile_id(maker, e)) for e in ("pat1@example.com", "pat2@example.com")}
    for pat_login, code in (("pat1@example.com", w.A), ("pat2@example.com", w.B)):
        r = c.post(f"/admin/patients/{code}/access", json={"profileId": ids[pat_login], "relationship": "self"}, headers=w.H["admin"])
        assert r.status_code == 201, r.text
    w.res = {}
    for code, who in ((w.A, "docA"), (w.B, "docB")):
        assert c.post(f"/digital-twins/{code}/resync", headers=w.H[who]).status_code == 200
        assert c.post("/predictions/run", json={"patientId": code}, headers=w.H[who]).status_code == 201
        sim = c.post("/simulations/run", json={"patientId": code}, headers=w.H[who])
        assert sim.status_code == 201, sim.text
        rep = c.post("/reports/generate", json={"patientId": code, "type": "Clinical summary"}, headers=w.H[who])
        assert rep.status_code == 201, rep.text
        w.res[code] = {"report": rep.json()["data"]["id"], "sim": sim.json()["id"]}

    async def seed_docs():
        conn = await base._raw()
        try:
            for code in (w.A, w.B):
                pid = await conn.fetchval("select id from patients where patient_code=$1", code)
                await conn.execute("insert into documents (id, name, category, patient_id, status, mime_type, size_bytes, storage_path, created_at) "
                                   "values ($1,'scan.pdf','Biopsy',$2,'Needs review','application/pdf',10,$3,'2026-01-01')", f"doc-{code}", pid, f"{pid}/x.pdf")
                await conn.execute("insert into ocr_extractions (id, document_id, patient_id, status, model) values ($1,$2,$3,'Extracted','m')", f"ext-{code}", f"doc-{code}", pid)
                await conn.execute("insert into ocr_extraction_fields (id, extraction_id, field_name, label, extracted_value, status) values ($1,$2,'stage','Stage','II','pending')", f"f-{code}", f"ext-{code}")
        finally:
            await conn.close()

    asyncio.run(seed_docs())
    yield w
    app.dependency_overrides.pop(get_db_session, None)
    w.client.__exit__(None, None, None)
    asyncio.run(engine.dispose())


async def _profile_id(maker, email):
    from sqlalchemy import select
    from app.models.identity import Profile
    async with maker() as s:
        return str((await s.execute(select(Profile.id).where(Profile.email == email))).scalar_one())


def READS(code, doc, rep, sim):
    return [
        f"/patients/{code}", f"/patients/{code}/labs", f"/patients/{code}/imaging", f"/patients/{code}/timeline",
        f"/patients/{code}/treatment-plan",
        f"/digital-twins/{code}", f"/digital-twins/{code}/versions", f"/digital-twins/{code}/snapshots",
        f"/predictions/{code}", f"/predictions/{code}/history", f"/predictions/{code}/confidence-trend",
        f"/predictions/{code}/explainability", f"/predictions/{code}/prognosis", f"/predictions/{code}/progression",
        f"/documents/{doc}", f"/documents/{doc}/versions", f"/documents/{doc}/timeline", f"/documents/{doc}/links",
        f"/documents/{doc}/download", f"/documents/{doc}/preview", f"/ocr/{doc}/fields",
        f"/simulations/{sim}", f"/simulations?patientId={code}",
        f"/reports/{rep}", f"/reports/{rep}/versions", f"/reports?patientId={code}",
    ]


def WRITES(code, doc, rep, sim):
    return [
        ("PATCH", f"/patients/{code}", {"name": "tamper", "stage": "IV"}),
        ("DELETE", f"/patients/{code}", None),
        ("POST", f"/digital-twins/{code}/resync", None),
        ("POST", f"/digital-twins/{code}/archive", None),
        ("POST", f"/digital-twins/{code}/versions/v1/restore", None),
        ("POST", "/predictions/run", {"patientId": code}),
        ("POST", "/simulations/run", {"patientId": code}),
        ("POST", "/simulations", {"patientId": code}),
        ("POST", f"/simulations/{sim}/duplicate", None),
        ("POST", f"/simulations/{sim}/promote", None),
        ("POST", "/reports/generate", {"patientId": code, "type": "Clinical summary"}),
        ("POST", f"/reports/{rep}/export", {"format": "pdf"}),
        ("POST", f"/ocr/{doc}/extract", None),
        ("POST", f"/ocr/{doc}/approve", {"fields": [{"field": "stage", "value": "III"}]}),
        ("POST", f"/ocr/{doc}/reject", {"reason": "x"}),
    ]


def _ids(w, code):
    return f"doc-{code}", w.res[code]["report"], w.res[code]["sim"]


@pg_only
def test_pending_accounts_are_listed_for_admins_only_and_grants_are_one_way(world):
    c = world.client
    assert c.get("/admin/users/pending", headers=world.H["docA"]).status_code == 403
    assert c.get("/admin/users/pending", headers=world.H["pat1"]).status_code == 403
    assert c.get("/admin/users/pending").status_code == 401
    c.post("/auth/register", json={"email": "later@example.com", "password": PW, "name": "later", "role": "doctor"})
    pid = next(p["id"] for p in c.get("/admin/users/pending", headers=world.H["admin"]).json() if p["email"] == "later@example.com")
    assert c.post(f"/admin/users/{pid}/role", json={"role": "doctor"}, headers=world.H["docA"]).status_code == 403
    assert c.post(f"/admin/users/{pid}/role", json={"role": "admin"}, headers=world.H["admin"]).status_code == 422   # admins are never created here
    assert c.post(f"/admin/users/{pid}/role", json={"role": "doctor"}, headers=world.H["admin"]).status_code == 200
    assert c.post(f"/admin/users/{pid}/role", json={"role": "researcher"}, headers=world.H["admin"]).status_code == 409  # no silent role change
    assert world.tok("later@example.com")


@pg_only
@pytest.mark.parametrize("owner, intruder", [("A", "docB"), ("B", "docA"), ("A", "docC"), ("B", "docC")])
def test_doctor_cannot_read_or_write_another_doctors_patient(world, owner, intruder):
    code = world.A if owner == "A" else world.B
    doc, rep, sim = _ids(world, code)
    c, h = world.client, world.H[intruder]
    for path in READS(code, doc, rep, sim):
        r = c.get(path, headers=h)
        if path.startswith("/reports?patientId="):      # a filtered list: the caller's scope is applied, so it is empty, not an error
            assert r.status_code == 200 and r.json() == [], f"GET {path} -> {r.status_code}"
        else:
            assert r.status_code == 403, f"GET {path} -> {r.status_code}"
        assert "SENTINEL" not in r.text
    for method, path, body in WRITES(code, doc, rep, sim):
        r = c.request(method, path, json=body, headers=h)
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"
    # nothing was changed or deleted by the denied attempts
    p = world.client.get(f"/patients/{code}", headers=world.H["admin"]).json()
    assert p["stage"] == "II" and p["name"].startswith("SENTINEL")


@pg_only
@pytest.mark.parametrize("who, code_attr", [("docA", "A"), ("docB", "B")])
def test_assigned_doctor_keeps_full_access_to_own_patient(world, who, code_attr):
    code = getattr(world, code_attr)
    doc, rep, sim = _ids(world, code)
    for path in READS(code, doc, rep, sim):
        r = world.client.get(path, headers=world.H[who])
        denied = r.status_code == 403
        # preview/download need Supabase Storage (502 locally); the point is that authorization lets them through
        assert not denied and r.status_code < 600 and r.status_code != 401, f"GET {path} -> {r.status_code}"
        assert r.status_code in (200, 502, 404), f"GET {path} -> {r.status_code}"


@pg_only
def test_lists_only_contain_the_callers_patients(world):
    c = world.client
    a_names = [p["name"] for p in c.get("/patients", headers=world.H["docA"]).json()]
    assert a_names == ["SENTINEL-ALPHA"]
    assert [p["id"] for p in c.get("/patients", headers=world.H["docC"]).json()] == []          # unassigned doctor sees nothing
    assert {p["id"] for p in c.get("/patients", headers=world.H["admin"]).json()} == {world.A, world.B}
    assert {p["patientId"] for p in c.get("/digital-twins", headers=world.H["docA"]).json()} == {world.A}
    assert {d["patientId"] for d in c.get("/documents", headers=world.H["docA"]).json()} == {world.A}
    assert {r["patientId"] for r in c.get("/reports", headers=world.H["docA"]).json()} == {world.A}
    assert {s["patientId"] for s in c.get("/simulations", headers=world.H["docA"]).json()} == {world.A}
    assert c.get("/reports/downloads", headers=world.H["docC"]).json() == []
    for path in ("/digital-twins", "/documents", "/reports", "/simulations"):
        assert len(c.get(path, headers=world.H["admin"]).json()) >= 2, path
        assert c.get(path, headers=world.H["docC"]).json() == [], path


@pg_only
def test_admin_override_reaches_everything(world):
    for code in (world.A, world.B):
        doc, rep, sim = _ids(world, code)
        for path in READS(code, doc, rep, sim):
            assert world.client.get(path, headers=world.H["admin"]).status_code in (200, 502), path
    r = world.client.post(f"/digital-twins/{world.A}/resync", headers=world.H["admin"])
    assert r.status_code == 200


@pg_only
def test_patient_reads_only_their_own_treatment_plan(world):
    c = world.client
    assert c.get(f"/patients/{world.A}/treatment-plan", headers=world.H["pat1"]).status_code == 200      # own
    assert c.get(f"/patients/{world.B}/treatment-plan", headers=world.H["pat1"]).status_code == 403      # another patient
    assert c.get(f"/patients/{world.A}/treatment-plan", headers=world.H["pat2"]).status_code == 403
    assert c.get(f"/patients/{world.B}/treatment-plan", headers=world.H["pat2"]).status_code == 200
    assert c.get(f"/patients/{world.A}/treatment-plan", headers=world.H["docA"]).status_code == 200     # authorized doctor
    assert c.get(f"/patients/{world.A}/treatment-plan", headers=world.H["docB"]).status_code == 403     # unauthorized doctor
    assert c.get(f"/patients/{world.A}/treatment-plan", headers=world.H["admin"]).status_code == 200    # admin
    assert c.get(f"/patients/{world.A}/treatment-plan", headers=world.H["res"]).status_code == 403      # researcher


@pg_only
def test_patient_login_reaches_nothing_else_about_themselves_or_others(world):
    code = world.A
    doc, rep, sim = _ids(world, code)
    for path in READS(code, doc, rep, sim):
        if path.endswith("/treatment-plan"):
            continue
        assert world.client.get(path, headers=world.H["pat1"]).status_code == 403, path      # role check: patients have no clinical API
    for method, path, body in WRITES(code, doc, rep, sim):
        assert world.client.request(method, path, json=body, headers=world.H["pat1"]).status_code == 403, path


@pg_only
def test_an_unlinked_patient_login_reaches_no_treatment_plan(world):
    world.reg("pat3@example.com", "patient")
    h = world.tok("pat3@example.com")
    assert world.client.get(f"/patients/{world.A}/treatment-plan", headers=h).status_code == 403


@pg_only
def test_researcher_has_no_identified_patient_access(world):
    code = world.A
    doc, rep, sim = _ids(world, code)
    c, h = world.client, world.H["res"]
    for path in READS(code, doc, rep, sim) + ["/patients", "/documents", "/reports", "/reports/downloads", "/simulations", "/digital-twins"]:
        r = c.get(path, headers=h)
        assert r.status_code == 403, f"GET {path} -> {r.status_code}"
        assert "SENTINEL" not in r.text
    for method, path, body in WRITES(code, doc, rep, sim) + [("POST", "/patients", {"name": "x"})]:
        assert c.request(method, path, json=body, headers=h).status_code == 403, f"{method} {path}"
    assert "SENTINEL" not in json.dumps(c.get("/analytics/dashboard", headers=h).json())


@pg_only
def test_researcher_keeps_aggregate_and_research_functionality(world):
    c, h = world.client, world.H["res"]
    for path in ("/analytics/cohort", "/analytics/accuracy", "/research/models", "/research/datasets", "/research/performance"):
        assert c.get(path, headers=h).status_code == 200, path
    d = c.get("/analytics/dashboard", headers=h).json()
    assert d["recentActivity"] == [] and d["followUps"] == []          # audit rows / appointments name patients
    assert {s["key"] for s in d["stats"]} >= {"patients", "twins", "survival"}   # counts only
    assert "SENTINEL" not in json.dumps(c.get("/analytics/cohort", headers=h).json())


@pg_only
def test_doctor_dashboard_hides_other_doctors_appointments_and_audit_rows(world):
    d = world.client.get("/analytics/dashboard", headers=world.H["docA"]).json()
    assert d["recentActivity"] == []                                     # audit trail is admin-only
    admin = world.client.get("/analytics/dashboard", headers=world.H["admin"]).json()
    assert len(admin["recentActivity"]) > 0


@pg_only
def test_access_grants_are_validated_and_audited(world):
    c, adm = world.client, world.H["admin"]
    docc = asyncio.run(_pid_by_email("docc@example.com"))
    pat1 = asyncio.run(_pid_by_email("pat1@example.com"))
    assert c.post(f"/admin/patients/{world.A}/access", json={"profileId": pat1, "relationship": "care_team"}, headers=adm).status_code == 422   # patients are not care team
    assert c.post(f"/admin/patients/{world.A}/access", json={"profileId": docc, "relationship": "self"}, headers=adm).status_code == 422
    assert c.post(f"/admin/patients/{world.B}/access", json={"profileId": pat1, "relationship": "self"}, headers=adm).status_code == 409        # one login, one record
    assert c.post(f"/admin/patients/{world.A}/access", json={"profileId": docc, "relationship": "care_team"}, headers=world.H["docA"]).status_code == 403
    # grant -> access -> revoke -> denied
    assert c.get(f"/patients/{world.A}", headers=world.H["docC"]).status_code == 403
    assert c.post(f"/admin/patients/{world.A}/access", json={"profileId": docc, "relationship": "care_team"}, headers=adm).status_code == 201
    assert c.get(f"/patients/{world.A}", headers=world.H["docC"]).status_code == 200
    assert any(a["email"] == "docc@example.com" for a in c.get(f"/admin/patients/{world.A}/access", headers=adm).json())
    assert c.delete(f"/admin/patients/{world.A}/access/{docc}?relationship=care_team", headers=adm).status_code == 200
    assert c.get(f"/patients/{world.A}", headers=world.H["docC"]).status_code == 403
    rows = asyncio.run(_sql("select action from audit_logs where action like 'patient.access_%' or action = 'user.role_granted'"))
    assert {r["action"] for r in rows} >= {"patient.access_granted", "patient.access_revoked", "user.role_granted"}


@pg_only
def test_patient_notifications_do_not_name_patients(world):
    rows = asyncio.run(_sql("select body from notifications"))
    assert rows and not any("PT-" in r["body"] for r in rows)


@pg_only
def test_existing_patients_without_access_rows_are_admin_only(world):
    # a patient that predates patient_access (no rows) is not assigned to anyone automatically
    asyncio.run(_sql("insert into patients (id, patient_code, name) values ('legacy-1', 'PT-LEGACY', 'Legacy Patient')"))
    assert world.client.get("/patients/PT-LEGACY", headers=world.H["docA"]).status_code == 403
    assert world.client.get("/patients/PT-LEGACY", headers=world.H["admin"]).status_code == 200
    assert "PT-LEGACY" not in [p["id"] for p in world.client.get("/patients", headers=world.H["docA"]).json()]


async def _sql_async(q):
    from tests import test_audit_pg_integration as base
    conn = await base._raw()
    try:
        return [dict(r) for r in await conn.fetch(q)]
    finally:
        await conn.close()


def _sql(q):
    return _sql_async(q)


async def _pid_by_email(email):
    rows = await _sql_async(f"select id from profiles where email='{email}'")
    return str(rows[0]["id"])
