"""
No prediction, simulation or explanation may be produced by silently substituting a clinical default.

Paths covered: POST /simulations/run, POST /simulations, GET /predictions/{id}/explainability, clinical._twin_state,
and the WDBC model interface (explain / simulate / simulate_all / predict, reachable only through the legacy services
today). The METABRIC prognosis preprocessing is pinned unchanged at the bottom.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import text

from app.api.v1.routers import clinical
from app.ml import interface
from app.ml.inputs import WDBC_RULES, require_model_fields
from tests.conftest import grant_care_team_for_all, login, register

COLS = ("id, patient_code, name, age, gender, phone, email, hospital, stage, tumor_size_mm, er_status, pr_status, "
        "her2_status, ki67, grade, nodes_involved, current_treatment, status, risk, survival_probability, "
        "last_updated, diagnosed_on, twin_status, history, notes, deleted_at")
FULL = dict(age=55, tumor_size_mm=30.0, stage="II", er_status="Positive", pr_status="Positive", her2_status="Negative",
            ki67=25.0, grade=2, nodes_involved=1, current_treatment="Endocrine therapy letrozole",
            risk="moderate", survival_probability=0.8)
FULL_MODEL = {"age": 55, "tumorSizeMm": 30, "stage": "II", "erStatus": "Positive", "prStatus": "Positive",
              "her2Status": "Negative", "ki67": 25, "grade": 2, "nodesInvolved": 1}


class _Db:
    def __init__(self, maker):
        self.maker = maker

    def __call__(self, sql, params=None, fetch=False):
        async def _go():
            async with self.maker() as s:
                res = await s.execute(text(sql), params or {})
                await s.commit()
                return [dict(r) for r in res.mappings()] if fetch else None
        return asyncio.run(_go())

    def add(self, pid, code, **vals):
        cols = ["id", "patient_code", "name", *vals]
        self(f"INSERT INTO patients ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})",
             {"id": pid, "patient_code": code, "name": "P " + code, **vals})


@pytest.fixture()
def db(db_sessionmaker, client):
    d = _Db(db_sessionmaker)
    d(f"CREATE TABLE patients ({COLS})")
    d("CREATE TABLE twin_versions (id, patient_id, version, created_at, status, tumor_size_mm, survival, risk, snapshot)")
    d("CREATE TABLE simulation_runs (id, date, patient_id, patient_name, twin_version, model, selected, compared, "
      "decision, decided_by, notes, survival, response, confidence, scenarios)")
    return d


def _headers(client):
    register(client, email="nodef@example.com", role="doctor")
    return {"Authorization": f"Bearer {login(client, email='nodef@example.com').json()['accessToken']}"}


def _scenarios(response):
    body = response.json()
    found = body["data"]["scenarios"] if "data" in body else body["scenarios"]
    return json.loads(found) if isinstance(found, str) else found


def _empty(scenarios):
    return all(s["survival5y"] is None and s["predictedResponse"] is None and s["tumorChange"] is None
               and s["projectedSizeMm"] is None for s in scenarios)


@pytest.mark.parametrize("path", ["/simulations/run", "/simulations"])
def test_blank_patient_gets_no_simulation_numbers(client, db, path):
    db.add("p1", "PT-1")                                    # nothing recorded
    r = client.post(path, json={"patientId": "PT-1"}, headers=_headers(client))
    assert r.status_code == 201, r.text
    scenarios = _scenarios(r)
    assert _empty(scenarios) and all(s["basis"] for s in scenarios)
    stored = db("SELECT survival, response, model FROM simulation_runs", fetch=True)
    assert stored and all(row["survival"] is None and row["response"] is None and row["model"] is None for row in stored)


def _stored(db):
    # SQLite cannot round-trip `CAST(.. AS jsonb)`, so POST /simulations is checked through the plain columns it also writes.
    return db("SELECT survival, response, model FROM simulation_runs", fetch=True)


@pytest.mark.parametrize("missing, fragment", [("ki67", "Ki-67"), ("tumor_size_mm", "tumour size"), ("her2_status", "receptor")])
def test_a_single_missing_required_input_blocks_the_projection(client, db, missing, fragment):
    db.add("p1", "PT-1", **{**FULL, missing: None})
    h = _headers(client)
    r = client.post("/simulations/run", json={"patientId": "PT-1"}, headers=h)
    assert r.status_code == 201, r.text
    scenarios = _scenarios(r)
    assert _empty(scenarios) and any(fragment in (s["basis"] or "") for s in scenarios)
    assert client.post("/simulations", json={"patientId": "PT-1"}, headers=h).status_code == 201
    assert all(row["survival"] is None and row["response"] is None and row["model"] is None for row in _stored(db))


def test_complete_patient_still_gets_a_projection(client, db):
    db.add("p1", "PT-1", **FULL)
    h = _headers(client)
    r = client.post("/simulations/run", json={"patientId": "PT-1"}, headers=h)
    assert r.status_code == 201, r.text
    first = _scenarios(r)[0]
    assert first["survival5y"] is not None and first["projectedSizeMm"] is not None and first["predictedResponse"] is not None
    assert client.post("/simulations", json={"patientId": "PT-1"}, headers=h).status_code == 201
    saved = _stored(db)[-1]
    assert saved["survival"] is not None and saved["response"] is not None and saved["model"]


def test_zero_or_out_of_range_ki67_is_not_treated_as_recorded(client, db):
    h = _headers(client)
    for bad in (0, -3, 140):
        db.add(f"p{bad}", f"PT-{bad}", **{**FULL, "ki67": bad})
        grant_care_team_for_all(client, "nodef@example.com")
        r = client.post("/simulations/run", json={"patientId": f"PT-{bad}"}, headers=h)
        assert _empty(_scenarios(r))


def _state(maker, patient_code):
    async def _go():
        async with maker() as s:
            patient = (await s.execute(text("SELECT * FROM patients WHERE patient_code=:c"), {"c": patient_code})).mappings().first()
            return await clinical._twin_state(s, patient)
    return asyncio.run(_go())


def test_twin_state_does_not_manufacture_values_for_a_blank_patient(db_sessionmaker, client, db):
    db.add("p1", "PT-1")
    state, version = _state(db_sessionmaker, "PT-1")
    assert version is None and all(v is None for v in state.values())
    # a twin whose snapshot recorded nothing (resynced from a blank record) adds nothing either
    db("INSERT INTO twin_versions (id, patient_id, version, created_at, status, tumor_size_mm, survival, risk, snapshot) "
       "VALUES ('t1', 'p1', 'v1', '2026-01-01', 'Active', NULL, NULL, NULL, :s)",
       {"s": json.dumps({"stage": None, "ki67": "", "er_status": None})})
    state, version = _state(db_sessionmaker, "PT-1")
    assert version == "v1" and all(v is None for v in state.values())


def test_twin_state_passes_recorded_values_through_unchanged(db_sessionmaker, client, db):
    db.add("p1", "PT-1", **FULL)
    state, _ = _state(db_sessionmaker, "PT-1")
    assert state["ki67"] == 25.0 and state["tumor_size_mm"] == 30.0 and state["er_status"] == "Positive" and state["stage"] == "II"


# --- explainability ---------------------------------------------------------------------------------------------


def _explain(client, db, patients):
    for i, vals in enumerate(patients):
        db.add(f"p{i}", f"PT-{i}", **vals)
    return client.get("/predictions/PT-0/explainability", headers=_headers(client)).json()


def test_explanation_does_not_count_missing_values_as_zero(client, db):
    rows = [dict(FULL, ki67=k, survival_probability=s, tumor_size_mm=t, grade=g)
            for k, s, t, g in [(10, .9, 10, 1), (None, .8, 20, 2), (None, .6, 30, 3), (40, .4, 40, 2)]]
    out = _explain(client, db, rows)
    assert "Ki-67 index" in out["unavailableFactors"]
    assert "Ki-67 index" not in [f["feature"] for f in out["factors"]]
    assert any(f["feature"] == "Tumor size (mm)" for f in out["factors"])
    assert "Ki-67 index" in out["caveat"]


def test_explanation_does_not_count_a_missing_receptor_as_negative(client, db):
    rows = [dict(FULL, er_status=e, survival_probability=s)
            for e, s in [("Positive", .9), (None, .8), (None, .5), ("Negative", .3), (None, .6)]]
    out = _explain(client, db, rows)
    assert "ER status" in out["unavailableFactors"]


def test_explanation_with_no_usable_factor_is_insufficient(client, db):
    blank = dict(survival_probability=0.7)
    out = _explain(client, db, [blank, dict(blank), dict(blank), dict(blank)])
    assert out["reliability"] == "insufficient" and out["factors"] == [] and len(out["unavailableFactors"]) == 8


def test_explanation_with_a_tiny_cohort_is_still_refused(client, db):
    out = _explain(client, db, [dict(FULL), dict(FULL)])
    assert out["reliability"] == "insufficient" and out["factors"] == []


def test_complete_cohort_explanation_is_unchanged_in_shape(client, db):
    rows = [dict(FULL, survival_probability=s, ki67=k, tumor_size_mm=t, grade=g, nodes_involved=n, age=a,
                 er_status=e, pr_status=e, her2_status=h)
            for s, k, t, g, n, a, e, h in [(.9, 10, 10, 1, 0, 40, "Positive", "Negative"),
                                           (.7, 20, 25, 2, 1, 50, "Positive", "Positive"),
                                           (.5, 30, 35, 3, 3, 60, "Negative", "Negative"),
                                           (.3, 40, 50, 3, 5, 70, "Negative", "Positive")]]
    out = _explain(client, db, rows)
    assert out["basis"] == "cohort" and out["unavailableFactors"] == [] and len(out["factors"]) == 8
    assert abs(sum(f["weight"] for f in out["factors"]) - 1) < 0.01


# --- WDBC model interface ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("call", ["predict", "explain", "simulate_all", "simulate"])
def test_model_interface_refuses_a_blank_or_partial_patient(call):
    model = interface.get_prediction_model()
    for fields in ({}, {k: v for k, v in FULL_MODEL.items() if k != "ki67"}, {**FULL_MODEL, "grade": 4}):
        args = (fields, "TC (Docetaxel/Cyclophosphamide)") if call == "simulate" else (fields,)
        with pytest.raises(ValueError, match="needs every clinical input"):
            getattr(model, call)(*args)


@pytest.mark.parametrize("call", ["predict", "explain", "simulate_all"])
def test_model_interface_still_serves_a_complete_patient(call):
    assert getattr(interface.get_prediction_model(), call)(FULL_MODEL)
    require_model_fields(FULL_MODEL)


def test_rules_cover_exactly_the_nine_inputs_the_mapping_reads():
    import inspect

    from app.ml import model as m
    src = inspect.getsource(m.clinical_factors) + inspect.getsource(m.clinical_severity)
    for name, _ in WDBC_RULES.values():
        assert f'"{name}"' in src, name
    assert len(WDBC_RULES) == 9


# --- METABRIC preprocessing unchanged --------------------------------------------------------------------------


def test_metabric_missing_value_handling_is_unchanged():
    pytest.importorskip("sksurv")
    from app.ml.survival.data import CATEGORICAL_FEATURES, NUMERIC_FEATURES
    from app.ml.survival.preprocess import UNKNOWN, build_preprocessor
    assert UNKNOWN == "Unknown"
    by_name = {t[0]: t for t in build_preprocessor().transformers}
    assert by_name["num"][1].named_steps["impute"].strategy == "median"
    assert by_name["cat"][1].named_steps["impute"].fill_value == "Unknown"
    assert list(by_name["num"][2]) == NUMERIC_FEATURES and list(by_name["cat"][2]) == CATEGORICAL_FEATURES
