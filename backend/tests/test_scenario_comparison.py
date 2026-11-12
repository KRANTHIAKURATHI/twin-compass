"""Scenario comparison: stored simulation results, one baseline, null is not zero, nothing is ranked clinically.

There is no separate comparison engine. A comparison is the scenarios one run stored, returned as stored by
`_simulation_response` and rendered side by side by the frontend. These tests pin that: values come from the stored
projection, every scenario in a run shares one twin baseline, ids are stable, and no scenario is declared best.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from app.api.v1.routers.clinical import _simulation_response
from tests.test_simulation_audit import AC_T, OUTCOMES, by_name, project
from tests.test_simulation_promote_plan import SCENARIOS as PROMOTE_SCENARIOS, _promote, db as promote_db  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
BASELINE_KEYS = ("tumorSizeMm", "ki67", "ER", "PR", "HER2", "baselineSurvival", "baselineRisk")


def stored_row(scenarios, version="v8", rid="run-1", provenance_twin=None):
    return {
        "id": rid, "date": "2026-11-12T00:00:00+00:00", "patient_name": "N", "patient_code": "PT-1", "patient_id": "p1",
        "twin_version": version, "model": "m", "selected": "Current plan", "compared": [s["name"] for s in scenarios],
        "decision": "Under review", "decided_by": "u", "notes": "", "survival": None, "response": None,
        "confidence": None, "scenarios": scenarios,
    }


def run_with_custom():
    return project(duration_weeks=8, custom_name="Dose-dense-AC-t", custom_dosage="60", custom_notes="n")[0]


# ---- the comparison is the stored results, one baseline ----------------------------------------------------------


def test_the_comparison_returns_exactly_what_the_run_stored():
    scenarios = run_with_custom()
    response = _simulation_response(stored_row(copy.deepcopy(scenarios)))
    assert response["scenarios"] == scenarios  # nothing recalculated, reordered, filled or dropped
    assert response["twinVersion"] == "v8" and response["compared"] == [s["name"] for s in scenarios]


def test_every_scenario_in_a_comparison_shares_one_twin_baseline():
    scenarios = run_with_custom()
    baselines = {json.dumps({k: s["provenance"]["inputs"][k] for k in BASELINE_KEYS}, sort_keys=True) for s in scenarios}
    assert len(baselines) == 1, "a comparison must be built from a single twin state"
    # The numeric baseline the projections started from is identical too (same tumour, same recorded survival).
    assert {s["baselineSizeMm"] for s in scenarios if s["baselineSizeMm"] is not None} == {24.0}
    assert {s["provenance"]["parametersVersion"] for s in scenarios} == {"kinetic-regimen-parameters-v1"}
    assert {s["provenance"]["requestedRegimen"] for s in scenarios} == {AC_T}


def test_runs_from_different_twin_versions_stay_separate_and_identified():
    v7 = _simulation_response(stored_row(project(tumor_size_mm=23.5, ki67=30.0)[0], version="v7", rid="a"))
    v8 = _simulation_response(stored_row(project()[0], version="v8", rid="b"))
    assert (v7["twinVersion"], v8["twinVersion"]) == ("v7", "v8")
    assert v7["scenarios"][0]["provenance"]["inputs"]["tumorSizeMm"] == 23.5   # the historical run keeps its own baseline
    assert v8["scenarios"][0]["provenance"]["inputs"]["tumorSizeMm"] == 24.0
    assert v7["scenarios"][0]["baselineSizeMm"] != v8["scenarios"][0]["baselineSizeMm"]  # not silently normalised
    # The frontend never merges runs: the extra run on the simulator page is shown under its own heading.
    page = (SRC / "routes" / "_shell.simulator.tsx").read_text(encoding="utf-8")
    assert "Previous simulation results" in page and "[...(shown ?? []), ...(pendingDraft ? [pendingDraft] : [])]" in page


# ---- identity ----------------------------------------------------------------------------------------------------------


def test_scenario_ids_are_stable_unique_and_tied_to_the_scenario():
    a, b = project()[0], project()[0]
    assert [s["id"] for s in a] == [s["id"] for s in b]            # same scenario -> same id, every request/process
    assert len({s["id"] for s in a}) == len(a)                       # unique within the run
    assert all(re.fullmatch(r"SC-[0-9a-f]{8}", s["id"]) for s in a)  # not the old salted-hash format
    other = project("Endocrine therapy")[0]
    assert not {s["id"] for s in a} & {s["id"] for s in other}       # a different regimen is a different identity


def test_scenario_types_are_distinguished_and_never_confused():
    s = by_name(run_with_custom())
    assert list(s)[:4] == ["Current plan", "Dose-intensified", "Lower toxicity", "Clinical trial"]
    assert s["Dose-dense-AC-t"]["custom"] is True
    for name in ("Current plan", "Dose-intensified", "Lower toxicity", "Clinical trial"):
        assert not s[name].get("custom"), f"{name} must not be reported as custom"
    assert s["Dose-intensified"]["regimen"].endswith("intensified") and s["Lower toxicity"]["regimen"].endswith("lower toxicity")
    assert s["Clinical trial"]["regimen"].endswith("trial protocol")


def test_a_custom_scenario_keeps_its_identity_and_metadata_and_does_not_claim_the_dose_changed_the_result():
    s = by_name(run_with_custom())
    custom, current = s["Dose-dense-AC-t"], s["Current plan"]
    assert custom["customConfig"] == {"dosage": "60", "durationWeeks": 8, "notes": "n"}
    assert custom["regimen"] == f"{AC_T} · 60 · 8 weeks" and custom["provenance"]["parametersVersion"] == "kinetic-regimen-parameters-v1"
    assert custom["id"] != current["id"]
    # Dose and notes are not modelled, so the projection equals Current plan's at the same regimen and duration.
    assert {k: custom[k] for k in OUTCOMES} == {k: current[k] for k in OUTCOMES}
    assert "not modelled" in custom["basis"]


# ---- null is not zero ------------------------------------------------------------------------------------------------


def test_the_clinical_trial_scenario_stays_null_and_is_never_compared_as_zero():
    trial = by_name(project()[0])["Clinical trial"]
    assert all(trial[f] is None for f in OUTCOMES) and trial["projectedSizeMm"] is None and trial["cycles"] is None
    assert "Investigational" in trial["basis"]
    # JSON round-trip (what is stored and served) keeps null - it does not become 0.
    assert json.loads(json.dumps(trial))["survival5y"] is None


def test_an_unavailable_run_stores_nulls_not_zeros_for_every_scenario():
    scenarios, _ = project("Not yet started")
    for s in scenarios:
        assert all(s[f] is None for f in OUTCOMES) and s["confidence"] is None
        assert 0 not in [s[f] for f in OUTCOMES]


def test_a_missing_survival_baseline_leaves_survival_null_while_the_other_metrics_remain():
    s = by_name(project(survival_probability=None)[0])["Current plan"]
    assert s["survival5y"] is None and s["tumorChange"] is not None


# ---- the compared metrics --------------------------------------------------------------------------------------------


def test_metrics_compare_numerically_with_the_right_direction():
    s = by_name(project()[0])
    inten, cur, low = s["Dose-intensified"], s["Current plan"], s["Lower toxicity"]
    reductions = {n: x["tumorChange"] for n, x in (("intensified", inten), ("current", cur), ("lower", low))}
    # A larger tumour REDUCTION is the more negative change: -38 beats -32.6 beats -26.9. Numerically, not as text.
    assert min(reductions, key=reductions.get) == "intensified" and max(reductions, key=reductions.get) == "lower"
    assert sorted(["-5.0", "-32.6", "-26.9"]) != sorted(["-5.0", "-32.6", "-26.9"], key=float)  # text order would be wrong
    assert inten["sideEffectRisk"] > cur["sideEffectRisk"] > low["sideEffectRisk"]   # toxicity rises with intensity
    assert inten["recoveryWeeks"] > cur["recoveryWeeks"] > low["recoveryWeeks"]       # fixed regimen-level multipliers
    assert (inten["recoveryWeeks"], cur["recoveryWeeks"], low["recoveryWeeks"]) == (20, 14, 10)


def test_projected_survival_is_the_scenarios_own_figure_and_never_the_baseline_or_a_model_probability():
    s = by_name(project(survival_probability=0.9762)[0])
    assert s["Current plan"]["survival5y"] != 97.62 and s["Current plan"]["survival5y"] > 97.62  # projected, from baseline
    assert s["Current plan"]["provenance"]["inputs"]["baselineSurvival"] == 0.9762               # the baseline, 0-1, untouched
    assert s["Dose-intensified"]["survival5y"] > s["Current plan"]["survival5y"] > s["Lower toxicity"]["survival5y"]
    # No scenario carries a classifier probability or a METABRIC score.
    assert not any(k in s["Current plan"] for k in ("proba_malignant", "riskScore", "riskBand"))


def test_baseline_survival_is_formatted_as_a_percentage_in_the_comparison_inputs():
    ui = (SRC / "lib" / "simulationDisplay.ts").read_text(encoding="utf-8")
    assert "Math.round(i.baselineSurvival * 10000) / 100" in ui  # 0.9762 -> 97.62, not "0.9762%"


def test_no_difference_or_ranking_is_computed_anywhere_in_the_comparison():
    for name in ("_shell.simulator.tsx", "_shell.simulations.$runId.tsx"):
        text = (SRC / "routes" / name).read_text(encoding="utf-8")
        assert not re.search(r"\.sort\(|\.reduce\(|delta|improvement|percentChange", text), name
        assert not re.search(r"best treatment|best scenario|optimal|winner|preferred treatment", text, re.I), name
    backend = (ROOT / "backend" / "app" / "services" / "response_model.py").read_text(encoding="utf-8")
    assert '"recommended": False' in backend and '"recommended": True' not in backend


def test_a_legacy_recommended_flag_is_not_shown_as_a_recommendation():
    page = (SRC / "routes" / "_shell.simulator.tsx").read_text(encoding="utf-8")
    assert "recommended: false," in page.split("const fromApi", 1)[1].split("});", 1)[0]


# ---- history, duplicates, determinism, promotion ------------------------------------------------------------------------


def test_the_same_stored_scenarios_always_produce_the_same_comparison():
    scenarios = run_with_custom()
    first = _simulation_response(stored_row(copy.deepcopy(scenarios)))
    second = _simulation_response(stored_row(copy.deepcopy(scenarios)))
    assert first == second
    assert project(duration_weeks=8, custom_name="C")[0] == project(duration_weeks=8, custom_name="C")[0]


def test_running_the_same_simulation_twice_gives_two_runs_with_identical_independent_scenarios():
    one = _simulation_response(stored_row(project()[0], rid="r1"))
    two = _simulation_response(stored_row(project()[0], rid="r2"))
    assert one["id"] != two["id"] and one["scenarios"] == two["scenarios"]  # separate historical runs, same results
    one["scenarios"][0]["tumorChange"] = 999.0
    assert two["scenarios"][0]["tumorChange"] != 999.0                       # no shared state between runs
    assert len({s["id"] for s in two["scenarios"]}) == len(two["scenarios"])  # no duplicate scenarios inside a run


def test_promoting_a_scenario_does_not_alter_the_stored_comparison(client, promote_db):
    before = promote_db("SELECT scenarios FROM simulation_runs", fetch=True)[0]["scenarios"]
    assert _promote(client, {"selectedScenario": "Lower toxicity"}).status_code == 200
    after = promote_db("SELECT scenarios, decision FROM simulation_runs", fetch=True)[0]
    assert json.loads(after["scenarios"]) == json.loads(before) == PROMOTE_SCENARIOS  # results untouched
    assert after["decision"] == "Promoted to plan"  # only the decision changed


# ---- the frontend shows stored values, honestly ------------------------------------------------------------------------


@pytest.mark.parametrize("page", ["_shell.simulator.tsx", "_shell.simulations.$runId.tsx"])
def test_both_comparison_tables_show_the_regimen_and_mark_custom_scenarios(page):
    text = (SRC / "routes" / page).read_text(encoding="utf-8")
    assert "{s.regimen}" in text and "CUSTOM_SCENARIO_NOTE" in text
    assert not re.search(r"from \"@/services/(data|fixtures)\"|from \"@/lib/mock", text)  # no fixture data


def test_the_simulator_header_no_longer_calls_the_patient_row_a_twin_state():
    page = (SRC / "routes" / "_shell.simulator.tsx").read_text(encoding="utf-8")
    assert "Baseline twin state" not in page and "Current patient record" in page
