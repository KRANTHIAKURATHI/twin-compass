from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field


class SimulationRequest(BaseModel):
    patient_id: str = Field(validation_alias="patientId")
    name: str | None = None
    regimen: str | None = None
    dosage: str | None = None
    duration_weeks: int | None = Field(default=None, validation_alias="durationWeeks")
    notes: str | None = None
    # The scenario the clinician picked on the comparison, by name. Optional:
    # absent or unknown falls back to the first scenario (the current plan).
    selected_scenario: str | None = Field(default=None, validation_alias="selectedScenario")

    model_config = {"populate_by_name": True}


class PredictionRequest(BaseModel):
    patient_id: str = Field(validation_alias="patientId")

    model_config = {"populate_by_name": True}


def _both(snake: str, camel: str) -> AliasChoices:
    """Accept either casing for a field.

    The frontend models are camelCase and `extra: "ignore"` means anything
    unrecognised is dropped without complaint - so before these aliases
    existed, a tumour size typed into the UI was accepted with a 201 and then
    silently discarded. Snake case stays valid for API clients and tests.
    """
    return AliasChoices(snake, camel)


class PatientInput(BaseModel):
    name: str
    age: int | None = None
    gender: str | None = None
    phone: str | None = None
    email: str | None = None
    hospital: str | None = None
    stage: str | None = None
    tumor_size_mm: float | None = Field(default=None, validation_alias=_both("tumor_size_mm", "tumorSizeMm"))
    er_status: str | None = Field(default=None, validation_alias=_both("er_status", "erStatus"))
    pr_status: str | None = Field(default=None, validation_alias=_both("pr_status", "prStatus"))
    her2_status: str | None = Field(default=None, validation_alias=_both("her2_status", "her2Status"))
    ki67: float | None = None
    grade: int | None = None
    nodes_involved: int | None = Field(default=None, validation_alias=_both("nodes_involved", "nodesInvolved"))
    current_treatment: str | None = Field(default=None, validation_alias=_both("current_treatment", "currentTreatment"))
    status: str | None = None
    risk: str | None = None
    survival_probability: float | None = Field(
        default=None, validation_alias=_both("survival_probability", "survivalProbability")
    )
    twin_status: str | None = Field(default=None, validation_alias=_both("twin_status", "twinStatus"))
    # Both columns exist on `patients` but were missing from this schema, so
    # saving a clinical note or a diagnosis date returned 200 and wrote nothing.
    diagnosed_on: str | None = Field(default=None, validation_alias=_both("diagnosed_on", "diagnosedOn"))
    notes: str | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}
