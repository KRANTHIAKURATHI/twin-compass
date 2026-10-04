"""Treatment response projection from digital-twin state.

WHAT THIS IS
------------
A deterministic pharmacodynamic model. It takes the twin's recorded state -
tumour diameter, proliferation index, receptor subtype - applies a regimen's
published effect parameters, and projects the tumour forward using Skipper's
log-kill hypothesis with exponential regrowth between cycles.

WHAT THIS IS NOT
----------------
It is not a trained model and it makes no claim to be one. Nothing here was
fitted to outcome data, because this deployment holds none: `treatment_plans`
records what was prescribed but never what happened, and the single row in
`ml_models` describes a *malignancy risk classifier* that does not take a
regimen as an input and therefore cannot compare regimens at all.

WHY THE PARAMETERS LIVE IN A TABLE
----------------------------------
This module replaced four hardcoded scenario cards whose numbers - 72% response,
-18% tumour change, 34% toxicity, 8 weeks recovery - were identical for every
patient and came from nowhere. The projection below is only worth more than
those literals because every clinical figure it uses sits in REGIMEN_PARAMETERS
with a `source` attached, in one flat table, so a clinician can check or correct
a number without reading a line of the arithmetic.

STATUS: the parameter table is UNVERIFIED. The figures are drawn from general
oncology knowledge of widely published trial results and have NOT been checked
against primary sources by a clinician. `PARAMETERS_VERIFIED` below is the flag
the API reports to the UI; flip it only once someone qualified has signed off on
the table, and record who and when.

An unclassifiable regimen or subtype yields nulls rather than a fallback
estimate. Refusing to answer is the correct behaviour when the inputs fall
outside what the table covers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Flipped only after a clinician has reviewed REGIMEN_PARAMETERS against primary
# sources. The UI surfaces this directly, so a reader always knows.
PARAMETERS_VERIFIED = False

SUBTYPE_HER2 = "HER2-positive"
SUBTYPE_HR = "HR-positive/HER2-negative"
SUBTYPE_TNBC = "Triple-negative"

ANTHRACYCLINE_TAXANE = "Anthracycline + taxane"
HER2_TARGETED = "HER2-targeted therapy"
ENDOCRINE = "Endocrine therapy"
CDK46 = "CDK4/6 inhibitor + endocrine"
PLATINUM = "Platinum-based"

# Keyword -> regimen family. Matched against the lower-cased regimen string.
# Ordered most specific first: a regimen naming both trastuzumab and a taxane is
# a HER2-targeted regimen, not a plain chemotherapy one.
_REGIMEN_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (HER2_TARGETED, ("trastuzumab", "pertuzumab", "herceptin", "perjeta", "tchp", "t-dm1", "kadcyla", "enhertu")),
    (CDK46, ("palbociclib", "ribociclib", "abemaciclib", "ibrance", "kisqali", "verzenio", "cdk4")),
    (ENDOCRINE, ("tamoxifen", "letrozole", "anastrozole", "exemestane", "fulvestrant", "aromatase", "endocrine", "hormone")),
    (PLATINUM, ("carboplatin", "cisplatin", "platinum")),
    (ANTHRACYCLINE_TAXANE, ("ac-t", "act", "doxorubicin", "adriamycin", "epirubicin", "cyclophosphamide",
                            "paclitaxel", "docetaxel", "taxane", "taxol", "tc", "fec", "chemotherapy")),
]


@dataclass(frozen=True)
class RegimenEffect:
    """Published effect of one regimen family in one receptor subtype.

    `log_kill_per_cycle` is the log10 cell kill Skipper's hypothesis assigns to a
    single cycle. `growth_suppression` is the separate, cytostatic half of the
    effect: the fraction of the tumour's intrinsic growth rate held down while
    the patient is on treatment. Cytotoxics kill hard and suppress moderately;
    endocrine therapy and CDK4/6 inhibitors barely kill at all and work almost
    entirely by suppression, which is why a kill-only model projects a tumour
    growing straight through letrozole. The rest are population rates from the
    cited trials.
    """

    objective_response_rate: float
    log_kill_per_cycle: float
    growth_suppression: float
    relative_risk_reduction: float
    grade3_toxicity_rate: float
    recovery_weeks: int
    cycles: int
    cycle_interval_days: int
    source: str


# (regimen family, subtype) -> effect. A missing key means the regimen is not a
# standard option in that subtype, and the projection returns nulls rather than
# inventing a number for a combination nobody would prescribe.
REGIMEN_PARAMETERS: dict[tuple[str, str], RegimenEffect] = {
    (ANTHRACYCLINE_TAXANE, SUBTYPE_HER2): RegimenEffect(
        0.60, 0.22, 0.50, 0.25, 0.35, 14, 8, 21,
        "NSABP B-27; EBCTCG polychemotherapy meta-analysis — UNVERIFIED",
    ),
    (ANTHRACYCLINE_TAXANE, SUBTYPE_HR): RegimenEffect(
        0.50, 0.19, 0.50, 0.20, 0.33, 14, 8, 21,
        "EBCTCG polychemotherapy meta-analysis; NCCN Breast — UNVERIFIED",
    ),
    (ANTHRACYCLINE_TAXANE, SUBTYPE_TNBC): RegimenEffect(
        0.65, 0.25, 0.50, 0.22, 0.36, 14, 8, 21,
        "NSABP B-27; CREATE-X — UNVERIFIED",
    ),
    (HER2_TARGETED, SUBTYPE_HER2): RegimenEffect(
        0.80, 0.33, 0.60, 0.40, 0.30, 12, 6, 21,
        "CLEOPATRA (Swain 2015); NeoSphere; APHINITY — UNVERIFIED",
    ),
    (ENDOCRINE, SUBTYPE_HR): RegimenEffect(
        0.35, 0.04, 0.90, 0.30, 0.05, 2, 12, 28,
        "EBCTCG tamoxifen/AI meta-analyses; ATAC — UNVERIFIED",
    ),
    (ENDOCRINE, SUBTYPE_HER2): RegimenEffect(
        # Deliberately weak. Endocrine therapy alone is not adequate treatment
        # for HER2-positive disease, and a projection showing the tumour roughly
        # holding steady rather than shrinking is the useful answer here.
        0.25, 0.025, 0.80, 0.18, 0.05, 2, 12, 28,
        "EBCTCG endocrine meta-analysis (HR+/HER2+ subgroup) — UNVERIFIED",
    ),
    (CDK46, SUBTYPE_HR): RegimenEffect(
        0.55, 0.06, 0.95, 0.35, 0.55, 4, 12, 28,
        "PALOMA-2; MONALEESA-2; MONARCH-3 — UNVERIFIED",
    ),
    (PLATINUM, SUBTYPE_TNBC): RegimenEffect(
        0.55, 0.22, 0.50, 0.20, 0.40, 12, 6, 21,
        "GeparSixto; CALGB 40603 — UNVERIFIED",
    ),
    (PLATINUM, SUBTYPE_HER2): RegimenEffect(
        0.45, 0.18, 0.50, 0.15, 0.38, 12, 6, 21,
        "TRYPHAENA (platinum backbone) — UNVERIFIED",
    ),
}


@dataclass(frozen=True)
class Variant:
    """One scenario card: the same regimen at a different dose intensity.

    `intensity` scales log kill, `toxicity_multiplier` scales the grade 3+ rate.
    """

    name: str
    suffix: str
    intensity: float
    toxicity_multiplier: float
    recovery_multiplier: float
    investigational: bool = False


VARIANTS: tuple[Variant, ...] = (
    Variant("Current plan", "", 1.0, 1.0, 1.0),
    Variant("Dose-intensified", " · intensified", 1.15, 1.5, 1.4),
    Variant("Lower toxicity", " · lower toxicity", 0.85, 0.6, 0.7),
    # An investigational protocol has no established effect size - that is what
    # makes it investigational. It gets a card and no numbers.
    Variant("Clinical trial", " · trial protocol", 1.0, 1.0, 1.0, investigational=True),
)


def classify_subtype(er: str | None, pr: str | None, her2: str | None) -> str | None:
    """Receptor subtype, or None when the twin does not record enough to tell."""
    if not her2:
        return None
    if _positive(her2):
        return SUBTYPE_HER2
    # HER2-negative: hormone receptors decide, and both must be on record.
    if er is None or pr is None or er == "" or pr == "":
        return None
    if _positive(er) or _positive(pr):
        return SUBTYPE_HR
    return SUBTYPE_TNBC


def classify_regimen(regimen: str | None) -> str | None:
    """Regimen family, or None when the text names nothing recognisable."""
    if not regimen:
        return None
    text = regimen.lower()
    for family, keywords in _REGIMEN_KEYWORDS:
        if any(word in text for word in keywords):
            return family
    return None


def project_scenarios(
    *,
    tumor_size_mm: float | None,
    ki67: float | None,
    er_status: str | None,
    pr_status: str | None,
    her2_status: str | None,
    survival_probability: float | None,
    risk: str | None,
    regimen: str,
    duration_weeks: int | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Project every scenario variant for one twin state.

    Returns the scenarios and a provenance block describing what the projection
    was based on - including, when it could not run, the reason why.
    """
    subtype = classify_subtype(er_status, pr_status, her2_status)
    family = classify_regimen(regimen)
    effect = REGIMEN_PARAMETERS.get((family, subtype)) if family and subtype else None

    reason = _unavailable_reason(subtype, family, effect, tumor_size_mm, regimen)
    provenance: dict[str, object] = {
        "kind": "kinetic-projection",
        "subtype": subtype,
        "regimenFamily": family,
        "source": effect.source if effect else None,
        "parametersVerified": PARAMETERS_VERIFIED,
        "model": "Log-kill projection with exponential regrowth (unvalidated parameters)",
        "unavailableReason": reason,
    }

    scenarios: list[dict[str, object]] = []
    for variant in VARIANTS:
        label = f"{regimen}{variant.suffix}"
        if reason or variant.investigational:
            scenario = _empty_scenario(variant.name, label, risk)
            scenario["basis"] = (
                "Investigational protocol — no established effect size."
                if variant.investigational and not reason
                else reason
            )
        else:
            assert effect is not None and tumor_size_mm is not None
            scenario = _project_one(
                variant, effect, label, tumor_size_mm, ki67, survival_probability, risk, duration_weeks
            )
            scenario["basis"] = f"Kinetic projection · {subtype} · {effect.source}"
        # Repeated on every card rather than held once at run level, because the
        # scenarios are what gets persisted to `simulation_runs.scenarios`, so
        # this is what survives to be read back when a run is reopened.
        scenario["provenance"] = provenance
        scenarios.append(scenario)
    return scenarios, provenance


def _project_one(
    variant: Variant,
    effect: RegimenEffect,
    label: str,
    tumor_size_mm: float,
    ki67: float | None,
    survival_probability: float | None,
    risk: str | None,
    duration_weeks: int | None,
) -> dict[str, object]:
    # Cytotoxic regimens are the kill-dominated ones; the cytostatic regimens
    # work through suppression and respond to Ki-67 in the opposite direction.
    cytotoxic = effect.growth_suppression <= 0.7
    sensitivity = _chemosensitivity(ki67, cytotoxic)
    growth = _growth_rate_per_day(ki67)
    cycles = effect.cycles
    if duration_weeks:
        cycles = max(1, round(duration_weeks * 7 / effect.cycle_interval_days))

    # Skipper log kill: a cycle removes a constant fraction of cells, not a
    # constant number, so the survival fraction is exponential in the log kill.
    surviving = 10 ** (-effect.log_kill_per_cycle * variant.intensity * sensitivity)
    # Regrowth in the interval before the next cycle, against whatever growth the
    # regimen does not suppress. Gompertzian growth is approximated as
    # exponential here because one cycle interval is short relative to the
    # curve's bend.
    on_treatment_growth = growth * (1 - effect.growth_suppression) if growth else None
    regrowth = math.exp(on_treatment_growth * effect.cycle_interval_days) if on_treatment_growth else 1.0
    per_cycle = surviving * regrowth

    volume_ratio = per_cycle**cycles
    # A tumour is not modelled below a microscopic floor; the model projects
    # bulk disease and says nothing about residual cells.
    volume_ratio = max(volume_ratio, 1e-6)
    diameter_ratio = volume_ratio ** (1 / 3)
    tumor_change = (diameter_ratio - 1) * 100

    # The proliferation modifier is damped here rather than applied at full
    # strength: an aggressive tumour is more chemosensitive, but a response
    # *rate* is bounded at 100% and applying the raw modifier pinned every
    # high-Ki-67 variant to the clamp, erasing the difference between them.
    response = effect.objective_response_rate * math.sqrt(sensitivity) * (1 + (variant.intensity - 1) * 0.5)
    survival5y = _survival_after(survival_probability, effect.relative_risk_reduction * variant.intensity)

    return {
        "id": f"SC-{abs(hash((variant.name, label))) % 10**8:08d}",
        "name": variant.name,
        "regimen": label,
        "predictedResponse": round(_clamp(response, 0.0, 0.95) * 100, 1),
        "tumorChange": round(tumor_change, 1),
        # Both ends of the projection, so the card can show the actual diameters
        # it moved between rather than a bare percentage. The baseline is the
        # twin's size, which is not always the patient row's.
        "baselineSizeMm": round(tumor_size_mm, 1),
        "projectedSizeMm": round(tumor_size_mm * diameter_ratio, 1),
        "risk": risk,
        # A kinetic projection has no model confidence. Reporting one would be
        # borrowing a word from a trained model that never ran.
        "confidence": None,
        "survival5y": round(survival5y * 100, 1) if survival5y is not None else None,
        "sideEffectRisk": round(_clamp(effect.grade3_toxicity_rate * variant.toxicity_multiplier, 0.0, 0.95) * 100, 1),
        "recoveryWeeks": max(1, round(effect.recovery_weeks * variant.recovery_multiplier)),
        "recommended": False,
        "cycles": cycles,
    }


def _empty_scenario(name: str, label: str, risk: str | None) -> dict[str, object]:
    return {
        "id": f"SC-{abs(hash((name, label))) % 10**8:08d}",
        "name": name,
        "regimen": label,
        "predictedResponse": None,
        "tumorChange": None,
        "baselineSizeMm": None,
        "projectedSizeMm": None,
        "risk": risk,
        "confidence": None,
        "survival5y": None,
        "sideEffectRisk": None,
        "recoveryWeeks": None,
        "recommended": False,
        "cycles": None,
    }


def _unavailable_reason(
    subtype: str | None,
    family: str | None,
    effect: RegimenEffect | None,
    tumor_size_mm: float | None,
    regimen: str,
) -> str | None:
    if subtype is None:
        return "The twin does not record enough receptor status to determine a subtype."
    if family is None:
        # Naming the regimen matters: a patient whose record still says
        # "Not yet started" is a different situation from one on a regimen the
        # table has simply never been extended to cover, and a message that does
        # not quote the text leaves the reader unable to tell which.
        return f'No parameters for the regimen on file ("{regimen}").'
    if effect is None:
        return f"{family} is not a standard option in {subtype} disease, so the table holds no parameters for it."
    if tumor_size_mm is None or tumor_size_mm <= 0:
        return "The twin records no tumour size, so there is nothing to project forward."
    return None


def _growth_rate_per_day(ki67: float | None) -> float | None:
    """Growth rate from the proliferation index.

    Ki-67 is the fraction of cells in cycle, so it stands in for volume doubling
    time. The 1200 constant places Ki-67 20% at a 60-day doubling time, within
    the range usually reported for breast cancer; the clamp keeps extreme
    indices inside 20-300 days rather than extrapolating past observed biology.
    """
    if ki67 is None or ki67 <= 0:
        return None
    doubling_days = _clamp(1200.0 / ki67, 20.0, 300.0)
    return math.log(2) / doubling_days


def _chemosensitivity(ki67: float | None, cytotoxic: bool) -> float:
    """How the proliferation index modulates the regimen's effect.

    Cytotoxic drugs act on dividing cells, so a high Ki-67 tumour is more
    chemosensitive. Endocrine therapy runs the other way: low-proliferation,
    receptor-driven disease responds best. Without a Ki-67 on record the
    modifier is 1.0 - no adjustment either way.
    """
    if ki67 is None or ki67 <= 0:
        return 1.0
    if cytotoxic:
        return _clamp(ki67 / 20.0, 0.6, 1.6)
    return _clamp(20.0 / ki67, 0.6, 1.4)


def _survival_after(baseline: float | None, relative_risk_reduction: float) -> float | None:
    """Apply a relative risk reduction to the twin's recorded survival.

    The baseline is the figure already on the twin - the model moves it, it does
    not replace it - so a patient with nothing recorded gets null, not a number
    conjured from the regimen alone.
    """
    if baseline is None:
        return None
    mortality = 1.0 - baseline
    return _clamp(1.0 - mortality * (1.0 - _clamp(relative_risk_reduction, 0.0, 0.9)), 0.0, 1.0)


def _positive(value: str | None) -> bool:
    return bool(value) and value.strip().lower().startswith("pos")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
