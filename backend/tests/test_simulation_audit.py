"""Treatment simulation: built from the Active Twin, deterministic, honest about what it does and does not model.

The run endpoint is exercised end to end through the real route with the database stubbed (a recording fake
session), so these tests pin which state the projection is built from and what is stored - not the SQL dialect.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers import clinical
from app.db.session import get_db_session
from app.main import app
from app.services.response_model import (
    PARAMETERS_VERSION,
    classify_regimen,
    project_scenarios,
)
from app.services.twin_state import active_twin_state
from tests.test_simulation_promote_plan import SCENARIOS as PROMOTE_SCENARIOS, _promote, db as promote_db  # noqa: F401
from tests.test_twin_state import PATIENT_ROW, SNAPSHOT, FakeSession, _Result, _twin, run

OUTCOMES = ("predictedResponse", "tumorChange", "survival5y", "sideEffectRisk", "recoveryWeeks")
AC_T = "Anthracycline + taxane"

# A twin the AC-T regimen can be projected for (HR-positive / HER2-negative); the patient row below is different.
TWIN = {**SNAPSHOT, "her2_status": "Negative", "tumor_size_mm": 24.0, "ki67": 25.0, "survival_probability": 0.9762}


def project(regimen=AC_T, **over):
    args = dict(
        tumor_size_mm=24.0, ki67=25.0, er_status="Positive", pr_status="Positive", her2_status="Negative",
        survival_probability=0.9762, risk="low", regimen=regimen,
    )
    return project_scenarios(**{**args, **over})


def by_name(scenarios):
    return {s["name"]: s for s in scenarios}


# ---- the run endpoint, end to end with a stubbed database -----------------------------------------------------


class RunSession(FakeSession):
    """Answers the patient and twin queries and records the simulation_runs insert."""

    def __init__(self, patient, twin=None):
        super().__init__(twin=twin)
        self.patient = patient
        self.insert: dict | None = None

    async def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        if "FROM patients" in sql:
            return _Result([self.patient])
        if sql.startswith("INSERT INTO simulation_runs"):
            self.insert = params
            return _Result([])
        return await super().execute(statement, params)

    async def commit(self):
        return None


def _post(session, body):
    route = next(r for r in app.routes if getattr(r, "path", "") == "/simulations/run")
    keys = []
    for dep in route.dependant.dependencies:
        keys.append(dep.call)
        app.dependency_overrides[dep.call] = (
            (lambda: session) if dep.call is get_db_session else (lambda: SimpleNamespace(id="u", role="doctor", email="d@x.org"))
        )
    try:
        with patch.object(clinical, "require_patient_access", AsyncMock()):
            return TestClient(app).post("/simulations/run", json={"patientId": "PT-1", **body})
    finally:
        for key in keys:
            app.dependency_overrides.pop(key, None)


ROW = {**PATIENT_ROW, "current_treatment": AC_T, "tumor_size_mm": 30.0, "ki67": 45.0, "er_status": "Negative",
       "pr_status": "Negative", "her2_status": "Positive", "risk": "high", "survival_probability": 0.5}


def test_the_run_uses_the_active_twin_and_records_that_version():
    session = RunSession(ROW, twin=_twin(TWIN, version="v8"))
    r = _post(session, {"regimen": AC_T})
    assert r.status_code == 201, r.text
    inputs = r.json()["provenance"]["inputs"]
    # The twin's values - not the newer patient row's 30 mm / ki67 45 / HER2 positive / survival 0.5.
    assert (inputs["tumorSizeMm"], inputs["ki67"], inputs["HER2"], inputs["baselineSurvival"]) == (24.0, 25.0, "Negative", 0.9762)
    assert session.insert["twin_version"] == "v8"
    assert json.loads(session.insert["scenarios"]) == r.json()["scenarios"]  # stored == returned


def test_a_newer_patient_row_cannot_override_the_twin_even_for_a_missing_twin_field():
    partial = {k: v for k, v in TWIN.items() if k != "ki67"}  # the row HAS ki67 45
    session = RunSession(ROW, twin=_twin(partial, version="v8"))
    body = _post(session, {"regimen": AC_T}).json()
    assert body["provenance"]["inputs"]["ki67"] is None
    assert "Ki-67" in body["provenance"]["unavailableReason"]
    assert all(s[f] is None for s in body["scenarios"] for f in OUTCOMES)  # unavailable, not projected from 45


def test_with_no_active_twin_the_row_is_used_and_the_version_is_recorded_as_none():
    session = RunSession({**ROW, "her2_status": "Negative", "er_status": "Positive", "pr_status": "Positive"})
    r = _post(session, {"regimen": AC_T})
    assert r.status_code == 201 and session.insert["twin_version"] == "none"
    assert r.json()["provenance"]["inputs"]["tumorSizeMm"] == 30.0


def test_prediction_and_simulation_see_the_same_clinical_state():
    session = RunSession(ROW, twin=_twin(TWIN, version="v8"))
    sim = _post(session, {"regimen": AC_T}).json()["provenance"]["inputs"]
    state, version = run(active_twin_state(session, ROW))
    assert version == "v8" and session.insert["twin_version"] == version
    assert (sim["tumorSizeMm"], sim["ki67"], sim["ER"], sim["PR"], sim["HER2"], sim["baselineSurvival"], sim["baselineRisk"]) == (
        state["tumor_size_mm"], state["ki67"], state["er_status"], state["pr_status"], state["her2_status"],
        state["survival_probability"], state["risk"],
    )


def test_a_custom_scenario_reaches_the_projection_and_is_stored():
    session = RunSession(ROW, twin=_twin(TWIN, version="v8"))
    body = _post(session, {"regimen": AC_T, "name": "Dose-dense-AC-t", "dosage": "60", "durationWeeks": 8, "notes": "n"}).json()
    custom = body["scenarios"][-1]
    assert [s["name"] for s in body["scenarios"]][:4] == ["Current plan", "Dose-intensified", "Lower toxicity", "Clinical trial"]
    assert custom["name"] == "Dose-dense-AC-t" and custom["custom"] is True
    assert custom["customConfig"] == {"dosage": "60", "durationWeeks": 8, "notes": "n"} and custom["cycles"] == 3
    assert "Dose-dense-AC-t" in json.loads(session.insert["compared"])
    assert custom["id"] not in {s["id"] for s in body["scenarios"][:4]}


def test_a_custom_name_that_matches_a_standard_scenario_is_refused():
    assert _post(RunSession(ROW, twin=_twin(TWIN)), {"regimen": AC_T, "name": "current plan"}).status_code == 422


# ---- missing required inputs ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing, fragment",
    [
        ({"tumor_size_mm": None}, "tumour size"),
        ({"ki67": None}, "Ki-67"),
        ({"ki67": 0}, "Ki-67"),
        ({"her2_status": None}, "receptor"),
        ({"er_status": None, "her2_status": "Negative"}, "receptor"),
    ],
)
def test_a_missing_required_input_makes_the_projection_unavailable_and_nothing_is_defaulted(missing, fragment):
    scenarios, provenance = project(**missing)
    assert fragment in provenance["unavailableReason"]
    assert all(s[f] is None for s in scenarios for f in OUTCOMES)


# ---- which patient inputs influence the projection (and which do not) -----------------------------------------


def test_tumor_size_scales_the_projected_diameter_but_not_the_percentages():
    small, large = by_name(project(tumor_size_mm=10.0)[0])["Current plan"], by_name(project(tumor_size_mm=40.0)[0])["Current plan"]
    assert large["projectedSizeMm"] > small["projectedSizeMm"] and large["baselineSizeMm"] == 40.0
    # The kinetic model is size-independent in relative terms: percentages are identical. Stated, not assumed.
    assert (small["tumorChange"], small["predictedResponse"], small["survival5y"]) == (
        large["tumorChange"], large["predictedResponse"], large["survival5y"],
    )


def test_ki67_changes_the_projection_and_in_opposite_directions_for_cytotoxic_and_endocrine_regimens():
    lo, hi = by_name(project(ki67=5.0)[0])["Current plan"], by_name(project(ki67=60.0)[0])["Current plan"]
    assert hi["predictedResponse"] > lo["predictedResponse"] and hi["tumorChange"] != lo["tumorChange"]
    elo = by_name(project("Endocrine therapy", ki67=5.0)[0])["Current plan"]
    ehi = by_name(project("Endocrine therapy", ki67=60.0)[0])["Current plan"]
    assert elo["predictedResponse"] > ehi["predictedResponse"]


def test_receptors_select_the_subtype_and_with_it_the_parameter_row():
    hr = project(er_status="Positive", pr_status="Positive", her2_status="Negative")
    her2 = project(er_status="Positive", pr_status="Positive", her2_status="Positive")
    tnbc = project(er_status="Negative", pr_status="Negative", her2_status="Negative")
    assert (hr[1]["subtype"], her2[1]["subtype"], tnbc[1]["subtype"]) == (
        "HR-positive/HER2-negative", "HER2-positive", "Triple-negative",
    )
    responses = {by_name(x[0])["Current plan"]["predictedResponse"] for x in (hr, her2, tnbc)}
    assert len(responses) == 3, "each subtype has its own AC-T parameters"


def test_baseline_survival_is_a_zero_to_one_probability():
    current = by_name(project(survival_probability=0.9762)[0])["Current plan"]
    assert 97.62 < current["survival5y"] <= 100.0  # improved from the recorded 97.62%, never replaced by it
    # 97.62 typed as a percentage is not a probability: no projection, rather than a clamped 100%.
    assert by_name(project(survival_probability=97.62)[0])["Current plan"]["survival5y"] is None
    assert by_name(project(survival_probability=-0.2)[0])["Current plan"]["survival5y"] is None
    # With no baseline there is no survival projection, and the other outcomes are still projected.
    none = by_name(project(survival_probability=None)[0])["Current plan"]
    assert none["survival5y"] is None and none["tumorChange"] is not None


def test_baseline_risk_is_carried_as_a_label_and_never_changes_a_number():
    low, high = project(risk="low")[0], project(risk="high")[0]
    for a, b in zip(low, high):
        assert {k: v for k, v in a.items() if k not in ("risk", "provenance")} == {k: v for k, v in b.items() if k not in ("risk", "provenance")}


def test_duration_sets_cycles_and_nothing_else():
    short = by_name(project(duration_weeks=8)[0])["Current plan"]
    long = by_name(project(duration_weeks=24)[0])["Current plan"]
    assert (short["cycles"], long["cycles"]) == (3, 8) and short["tumorChange"] != long["tumorChange"]
    assert (short["recoveryWeeks"], short["sideEffectRisk"]) == (long["recoveryWeeks"], long["sideEffectRisk"])


# ---- regimen handling ------------------------------------------------------------------------------------------------


def test_each_supported_family_maps_to_its_own_parameters():
    her2 = dict(er_status="Positive", pr_status="Positive", her2_status="Positive")
    anthra = by_name(project(AC_T, **her2)[0])["Current plan"]
    herceptin = by_name(project("Trastuzumab-based HER2-targeted therapy", **her2)[0])["Current plan"]
    assert (anthra["recoveryWeeks"], herceptin["recoveryWeeks"]) == (14, 12)
    assert anthra["predictedResponse"] != herceptin["predictedResponse"]
    assert by_name(project("Endocrine therapy")[0])["Current plan"]["recoveryWeeks"] == 2
    assert by_name(project("CDK4/6 inhibitor + endocrine")[0])["Current plan"]["recoveryWeeks"] == 4
    tnbc = dict(er_status="Negative", pr_status="Negative", her2_status="Negative")
    assert by_name(project("Platinum-based", **tnbc)[0])["Current plan"]["recoveryWeeks"] == 12


@pytest.mark.parametrize("regimen", ["Not yet started", "Current treatment", "", "active surveillance", "Observation", "Protocol X"])
def test_an_unsupported_or_placeholder_regimen_never_becomes_another_treatment(regimen):
    assert classify_regimen(regimen) is None
    scenarios, provenance = project(regimen)
    assert provenance["regimenFamily"] is None and provenance["unavailableReason"]
    assert all(s[f] is None for s in scenarios for f in OUTCOMES)


def test_short_abbreviations_must_stand_alone_but_real_regimen_names_still_classify():
    assert classify_regimen("active surveillance") is None  # "act" inside "active" used to mean AC-T
    for name in ("AC-T", "ac-t + trastuzumab", "TC", "FEC-T", "dose-dense AC-T", "TCHP", "Letrozole"):
        assert classify_regimen(name) is not None, name


def test_a_regimen_outside_its_subtype_is_refused_not_substituted():
    _, provenance = project("Letrozole", er_status="Negative", pr_status="Negative", her2_status="Negative")
    assert "not a standard option" in provenance["unavailableReason"]


# ---- scenarios ----------------------------------------------------------------------------------------------------------


def test_the_clinical_trial_scenario_never_carries_efficacy_or_another_scenarios_numbers():
    scenarios, _ = project()
    trial = by_name(scenarios)["Clinical trial"]
    assert all(trial[f] is None for f in OUTCOMES) and trial["cycles"] is None
    assert trial["projectedSizeMm"] is None and "Investigational" in trial["basis"]


def test_variants_are_distinct_and_ordered_by_dose_intensity():
    s = by_name(project()[0])
    assert s["Dose-intensified"]["sideEffectRisk"] > s["Current plan"]["sideEffectRisk"] > s["Lower toxicity"]["sideEffectRisk"]
    assert s["Dose-intensified"]["tumorChange"] < s["Current plan"]["tumorChange"] < s["Lower toxicity"]["tumorChange"]


def test_the_simulation_is_deterministic_including_ids():
    a, pa = project(duration_weeks=8, custom_name="C", custom_dosage="60")
    b, pb = project(duration_weeks=8, custom_name="C", custom_dosage="60")
    assert a == b and pa == pb  # same inputs, same output - scenario ids included (they were salted per process)


def test_scenarios_do_not_contaminate_each_other():
    first, _ = project()
    reference = json.loads(json.dumps(first))
    first[0]["tumorChange"] = 999.0  # mutating one result...
    first[1]["recoveryWeeks"] = 999
    second, _ = project()
    assert second == reference  # ...changes nothing a later run produces (no shared mutable state)
    with_custom, _ = project(custom_name="X", custom_dosage="1")
    assert with_custom[:4] == reference  # a custom scenario never alters the standard four
    other, _ = project("Endocrine therapy")
    assert not {s["id"] for s in other} & {s["id"] for s in reference}  # a different regimen shares nothing
    unavailable, _ = project("Not yet started")
    assert all(s[f] is None for s in unavailable for f in OUTCOMES)  # an unavailable run inherits no earlier numbers


# ---- output semantics and provenance ---------------------------------------------------------------------------------------


def test_every_scenario_names_the_parameter_table_and_marks_it_unverified():
    scenarios, provenance = project()
    assert provenance["parametersVersion"] == PARAMETERS_VERSION == "kinetic-regimen-parameters-v1"
    for s in scenarios:
        assert s["provenance"]["parametersVersion"] == PARAMETERS_VERSION
        assert s["provenance"]["parametersVerified"] is False and "unvalidated" in s["provenance"]["model"]
    ui = (Path(__file__).resolve().parents[2] / "src" / "lib" / "simulationDisplay.ts").read_text(encoding="utf-8")
    assert "provenance?.parametersVersion" in ui  # the UI shows exactly the version the backend returned


def test_confidence_is_never_invented():
    scenarios, _ = project(custom_name="C")
    assert all(s["confidence"] is None for s in scenarios)


def test_recovery_is_a_regimen_level_figure_not_patient_specific():
    a = by_name(project(tumor_size_mm=8.0, ki67=5.0, risk="low")[0])
    b = by_name(project(tumor_size_mm=60.0, ki67=80.0, risk="high", survival_probability=0.3)[0])
    assert [a[n]["recoveryWeeks"] for n in ("Current plan", "Dose-intensified", "Lower toxicity")] == [14, 20, 10]
    assert [a[n]["recoveryWeeks"] for n in a] == [b[n]["recoveryWeeks"] for n in b]
    ui = (Path(__file__).resolve().parents[2] / "src" / "lib" / "simulationDisplay.ts").read_text(encoding="utf-8")
    assert "Regimen-level estimate · not patient-specific" in ui and "Estimated recovery" in ui


# ---- promoting a simulation never writes a label or an invented cycle count into the plan -----------------------------------


def test_a_scenario_without_a_projection_cannot_be_promoted(client, promote_db):
    r = _promote(client, {"selectedScenario": "Clinical trial"})
    assert r.status_code == 409 and "no projection" in r.text
    assert promote_db("SELECT count(*) AS n FROM treatment_plans", fetch=True)[0]["n"] == 0
    assert promote_db("SELECT decision FROM simulation_runs", fetch=True)[0]["decision"] is None  # not marked promoted


def test_promoting_a_projected_scenario_uses_the_projections_cycle_count(client, promote_db):
    r = _promote(client, {"selectedScenario": "Current plan"})
    assert r.status_code == 200, r.text
    current = next(s for s in PROMOTE_SCENARIOS if s["name"] == "Current plan")
    assert promote_db("SELECT total_cycles FROM treatment_plans", fetch=True)[0]["total_cycles"] == current["cycles"]
