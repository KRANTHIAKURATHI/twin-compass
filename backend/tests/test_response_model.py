"""Behavioural guarantees for the treatment response projection.

These are not accuracy tests - the parameter table is unverified and there is no
outcome data in this deployment to test accuracy against. They pin the
properties that make the projection safe to show a clinician: it refuses to
answer when it cannot, it never fabricates a figure the twin does not support,
and its numbers move in the direction the biology says they should.
"""

from __future__ import annotations

import pytest

from app.services.response_model import (
    SUBTYPE_HER2,
    SUBTYPE_HR,
    SUBTYPE_TNBC,
    classify_regimen,
    classify_subtype,
    project_scenarios,
)

HER2_TWIN = {
    "tumor_size_mm": 22.0,
    "ki67": 20.0,
    "er_status": "Positive",
    "pr_status": "Positive",
    "her2_status": "Positive",
    "survival_probability": 0.9269,
    "risk": "low",
}

OUTCOME_FIELDS = ("predictedResponse", "tumorChange", "survival5y", "sideEffectRisk", "recoveryWeeks")


def test_subtype_needs_full_receptor_status() -> None:
    assert classify_subtype("Positive", "Positive", "Positive") == SUBTYPE_HER2
    assert classify_subtype("Positive", "Negative", "Negative") == SUBTYPE_HR
    assert classify_subtype("Negative", "Negative", "Negative") == SUBTYPE_TNBC
    # HER2 alone decides when positive; when negative both HR fields are needed.
    assert classify_subtype(None, None, "Positive") == SUBTYPE_HER2
    assert classify_subtype(None, "Negative", "Negative") is None
    assert classify_subtype("Positive", "Positive", None) is None


def test_regimen_family_prefers_the_targeted_agent() -> None:
    # A regimen naming both a taxane and trastuzumab is HER2-targeted therapy,
    # not plain chemotherapy - the more specific match has to win.
    assert classify_regimen("AC-T + Trastuzumab") == "HER2-targeted therapy"
    assert classify_regimen("AC-T") == "Anthracycline + taxane"
    assert classify_regimen("Palbociclib + letrozole") == "CDK4/6 inhibitor + endocrine"
    assert classify_regimen("Something nobody has heard of") is None
    assert classify_regimen(None) is None


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"her2_status": None}, "receptor status"),
        ({"tumor_size_mm": None}, "tumour size"),
    ],
)
def test_missing_twin_state_yields_nulls_and_a_reason(override: dict, fragment: str) -> None:
    scenarios, provenance = project_scenarios(regimen="AC-T", **{**HER2_TWIN, **override})
    assert fragment in (provenance["unavailableReason"] or "")
    for scenario in scenarios:
        for field in OUTCOME_FIELDS:
            assert scenario[field] is None, f"{field} was fabricated despite {fragment} being absent"


def test_unrecognised_regimen_is_refused_rather_than_guessed() -> None:
    _, provenance = project_scenarios(regimen="Protocol X", **HER2_TWIN)
    assert provenance["regimenFamily"] is None
    # The message quotes the regimen so "Not yet started" is distinguishable
    # from a regimen the table has simply never covered.
    assert "Protocol X" in provenance["unavailableReason"]


def test_regimen_outside_its_subtype_is_refused() -> None:
    tnbc = {**HER2_TWIN, "er_status": "Negative", "pr_status": "Negative", "her2_status": "Negative"}
    _, provenance = project_scenarios(regimen="Letrozole", **tnbc)
    assert "not a standard option" in provenance["unavailableReason"]


def test_clinical_trial_variant_never_carries_numbers() -> None:
    scenarios, _ = project_scenarios(regimen="AC-T + Trastuzumab", **HER2_TWIN)
    trial = next(s for s in scenarios if s["name"] == "Clinical trial")
    for field in OUTCOME_FIELDS:
        assert trial[field] is None
    assert "Investigational" in trial["basis"]


def test_projection_is_grounded_in_the_twin() -> None:
    scenarios, provenance = project_scenarios(regimen="AC-T + Trastuzumab", **HER2_TWIN)
    assert provenance["unavailableReason"] is None
    assert provenance["subtype"] == SUBTYPE_HER2
    current = scenarios[0]

    assert current["baselineSizeMm"] == HER2_TWIN["tumor_size_mm"]
    assert current["projectedSizeMm"] < current["baselineSizeMm"]
    assert current["tumorChange"] < 0
    # Five-year survival starts from the figure recorded on the twin and is
    # improved by the regimen's risk reduction - never replaced by one.
    assert current["survival5y"] > HER2_TWIN["survival_probability"] * 100
    # A kinetic projection has no model confidence to report.
    assert current["confidence"] is None
    assert current["risk"] == "low"


def test_dose_intensity_moves_efficacy_and_toxicity_together() -> None:
    scenarios, _ = project_scenarios(regimen="AC-T + Trastuzumab", **HER2_TWIN)
    by_name = {s["name"]: s for s in scenarios}
    intensified, current, gentle = by_name["Dose-intensified"], by_name["Current plan"], by_name["Lower toxicity"]

    assert intensified["tumorChange"] < current["tumorChange"] < gentle["tumorChange"]
    assert intensified["sideEffectRisk"] > current["sideEffectRisk"] > gentle["sideEffectRisk"]
    assert intensified["recoveryWeeks"] > current["recoveryWeeks"] > gentle["recoveryWeeks"]
    # The variants have to stay distinguishable rather than all pinning to the
    # response clamp, which is what a high-proliferation tumour used to do.
    assert len({s["predictedResponse"] for s in (intensified, current, gentle)}) == 3


def test_proliferation_drives_chemo_and_endocrine_in_opposite_directions() -> None:
    hr_twin = {**HER2_TWIN, "her2_status": "Negative"}
    brisk = project_scenarios(regimen="AC-T", **{**hr_twin, "ki67": 60.0})[0][0]
    indolent = project_scenarios(regimen="AC-T", **{**hr_twin, "ki67": 5.0})[0][0]
    # Cytotoxics act on dividing cells.
    assert brisk["predictedResponse"] > indolent["predictedResponse"]

    brisk_endocrine = project_scenarios(regimen="Letrozole", **{**hr_twin, "ki67": 60.0})[0][0]
    indolent_endocrine = project_scenarios(regimen="Letrozole", **{**hr_twin, "ki67": 5.0})[0][0]
    # Endocrine therapy runs the other way: receptor-driven, low-turnover
    # disease is what it controls best.
    assert indolent_endocrine["predictedResponse"] > brisk_endocrine["predictedResponse"]


def test_endocrine_therapy_is_modelled_as_cytostatic() -> None:
    """Endocrine therapy holds disease rather than shrinking it quickly.

    A kill-only model projected a tumour growing straight through letrozole,
    because the drug's log kill is near zero. The suppression term is what stops
    that, and this test is here so it cannot be dropped again.
    """
    hr_twin = {**HER2_TWIN, "her2_status": "Negative"}
    endocrine = project_scenarios(regimen="Letrozole", **hr_twin)[0][0]
    chemo = project_scenarios(regimen="AC-T", **hr_twin)[0][0]

    assert endocrine["tumorChange"] < 0, "tumour projected to grow while on endocrine therapy"
    assert endocrine["tumorChange"] > chemo["tumorChange"], "endocrine shrinkage should be the gentler of the two"
    assert endocrine["sideEffectRisk"] < chemo["sideEffectRisk"]


def test_absent_survival_probability_is_not_invented() -> None:
    scenarios, _ = project_scenarios(regimen="AC-T + Trastuzumab", **{**HER2_TWIN, "survival_probability": None})
    assert scenarios[0]["survival5y"] is None
    # The rest of the projection does not depend on it and still runs.
    assert scenarios[0]["tumorChange"] is not None


def test_duration_overrides_the_default_cycle_count() -> None:
    short = project_scenarios(regimen="AC-T + Trastuzumab", duration_weeks=6, **HER2_TWIN)[0][0]
    long = project_scenarios(regimen="AC-T + Trastuzumab", duration_weeks=24, **HER2_TWIN)[0][0]
    assert short["cycles"] < long["cycles"]
    assert short["tumorChange"] > long["tumorChange"]


def test_every_scenario_states_its_basis() -> None:
    scenarios, _ = project_scenarios(regimen="AC-T + Trastuzumab", **HER2_TWIN)
    for scenario in scenarios:
        assert scenario["basis"]
        # The parameter table is unverified until a clinician signs it off, and
        # the UI reads this flag to say so on every card.
        assert scenario["provenance"]["parametersVerified"] is False
