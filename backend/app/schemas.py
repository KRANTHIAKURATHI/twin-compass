"""Pydantic schemas — mirror src/types/models.ts exactly (field-for-field).

Every schema's Python attribute is snake_case (matching the ORM column) and
serializes to camelCase via `alias_generator`, so FastAPI's JSON responses
match the TypeScript interfaces without any per-route reshaping.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


T = TypeVar("T")


class MutationResult(Camel, Generic[T]):
    ok: bool
    data: Optional[T] = None
    message: Optional[str] = None


class Paginated(Camel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------- Identity --


class Credentials(Camel):
    email: EmailStr
    password: str


class RegisterPayload(Credentials):
    name: str
    role: Literal["doctor", "patient", "researcher", "admin"] = "doctor"
    hospital: Optional[str] = None
    specialization: Optional[str] = None


class AuthUser(Camel):
    id: str
    name: str
    email: str
    role: Literal["doctor", "patient", "researcher", "admin"]
    title: Optional[str] = None
    hospital: Optional[str] = None
    avatar_url: Optional[str] = None


class AuthSession(Camel):
    user: AuthUser
    access_token: str
    expires_at: str


class ForgotPasswordPayload(Camel):
    email: EmailStr


class ResetPasswordPayload(Camel):
    token: str
    password: str


class ProfileUpdatePayload(Camel):
    name: Optional[str] = None
    title: Optional[str] = None
    hospital: Optional[str] = None
    avatar_url: Optional[str] = None


class ChangePasswordPayload(Camel):
    current_password: str
    new_password: str


# ------------------------------------------------------------ Clinical core --


class TimelineEvent(Camel):
    date: str
    title: str
    detail: str
    kind: Literal["diagnosis", "treatment", "scan", "note"]


class PatientReportRef(Camel):
    name: str
    type: str
    date: str
    size: str


class Patient(Camel):
    id: str
    patient_code: Optional[str] = None
    name: str
    age: int
    gender: str
    phone: str
    email: str
    hospital: str
    stage: Literal["0", "I", "II", "III", "IV"]
    tumor_size_mm: float
    er_status: Literal["Positive", "Negative"]
    pr_status: Literal["Positive", "Negative"]
    her2_status: Literal["Positive", "Negative"]
    ki67: float
    grade: Literal[1, 2, 3]
    nodes_involved: int
    current_treatment: str
    status: Literal["In Treatment", "Remission", "Monitoring", "Critical"]
    risk: Literal["low", "moderate", "high"]
    survival_probability: float
    last_updated: str
    diagnosed_on: str
    twin_status: Literal["Synced", "Recalculating", "Stale"]
    history: list[str] = Field(default_factory=list)
    notes: str = ""
    timeline: list[TimelineEvent] = Field(default_factory=list)
    reports: list[PatientReportRef] = Field(default_factory=list)
    comorbidities: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)
    previous_treatments: list[str] = Field(default_factory=list)
    family_history: str = ""
    smoking_status: Literal["Never", "Former", "Current", "Unknown"] = "Unknown"
    alcohol_use: Literal["None", "Occasional", "Regular", "Unknown"] = "Unknown"
    surgical_history: list[str] = Field(default_factory=list)


class PatientInput(Camel):
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    hospital: Optional[str] = None
    stage: Optional[Literal["0", "I", "II", "III", "IV"]] = None
    tumor_size_mm: Optional[float] = None
    er_status: Optional[Literal["Positive", "Negative"]] = None
    pr_status: Optional[Literal["Positive", "Negative"]] = None
    her2_status: Optional[Literal["Positive", "Negative"]] = None
    ki67: Optional[float] = None
    grade: Optional[Literal[1, 2, 3]] = None
    nodes_involved: Optional[int] = None
    current_treatment: Optional[str] = None
    status: Optional[Literal["In Treatment", "Remission", "Monitoring", "Critical"]] = None
    risk: Optional[Literal["low", "moderate", "high"]] = None
    survival_probability: Optional[float] = None
    diagnosed_on: Optional[str] = None
    notes: Optional[str] = None
    comorbidities: Optional[list[str]] = None
    allergies: Optional[list[str]] = None
    current_medications: Optional[list[str]] = None
    previous_treatments: Optional[list[str]] = None
    family_history: Optional[str] = None
    smoking_status: Optional[Literal["Never", "Former", "Current", "Unknown"]] = None
    alcohol_use: Optional[Literal["None", "Occasional", "Regular", "Unknown"]] = None
    surgical_history: Optional[list[str]] = None


class LabResult(Camel):
    date: str
    panel: str
    marker: str
    value: str
    unit: str
    range: str
    flag: str


class LabResultInput(Camel):
    date: Optional[str] = None
    panel: str
    marker: str
    value: str
    unit: str = ""
    range: str = ""
    flag: str = "normal"


class ImagingStudy(Camel):
    id: str
    modality: str
    region: str
    date: str
    finding: str
    radiologist: str
    status: str


class ImagingStudyInput(Camel):
    modality: str
    region: str
    date: Optional[str] = None
    finding: str = ""
    radiologist: str = ""
    status: str = "Pending"


# ------------------------------------------------------------- Digital twin --


class TwinVersion(Camel):
    version: str
    created_at: str
    status: Literal["Active", "Superseded", "Archived", "Draft"]
    author: str
    summary: str
    tumor_size_mm: float
    survival: float
    risk: Literal["low", "moderate", "high"]
    model: str


class TwinSnapshot(Camel):
    id: str
    version: str
    taken_at: str
    trigger: str
    size: str


# ------------------------------------------------------ Predictions/explain --


class PredictionRun(Camel):
    id: str
    date: str
    twin_version: str
    model: str
    survival: float
    recurrence: float
    response: str
    confidence: float
    status: Literal["Complete", "Low confidence", "Superseded"]


class ConfidencePoint(Camel):
    date: str
    confidence: float


class FeatureImportance(Camel):
    feature: str
    weight: float
    direction: str


class ModelMetadata(Camel):
    """Provenance for the model that produced a prediction or simulation.

    `is_validated` is `False` for the current development model: it is trained
    on a public diagnostic dataset, not on oncology outcome data, so its
    outputs are estimates for decision support and not validated prognoses.
    """

    # `model_type` collides with pydantic's reserved `model_` namespace; the
    # field name is part of the wire contract, so opt out of the guard.
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True, protected_namespaces=()
    )

    name: str
    version: str
    dataset_name: str
    trained_at: str
    model_type: str
    is_validated: bool
    disclaimer: str


class DeltaFeature(Camel):
    """One feature's shift between two model inputs (e.g. baseline vs regimen).

    Both weights come from the model's own attribution output; nothing here is
    canned narrative text.
    """

    feature: str
    weight_before: float
    weight_after: float
    contribution: float
    direction: str


class ExplanationSummary(Camel):
    """Explainability for a prediction, plus what it does and doesn't mean.

    `computed_from` states the honest caveat: feature attributions are computed
    live from the patient's *current* recorded fields, so an explanation
    reflects the patient's state now rather than at the time an older
    prediction was stored.
    """

    patient_id: str
    features: list[FeatureImportance] = Field(default_factory=list)
    model: ModelMetadata
    computed_from: str
    caveat: str


class SimulationExplanation(Camel):
    """Why a simulated regimen outcome differs from the untreated baseline."""

    simulation_id: str
    patient_id: str
    regimen: str
    baseline_survival: float
    simulated_survival: float
    features: list[DeltaFeature] = Field(default_factory=list)
    model: ModelMetadata
    caveat: str


class TwinState(Camel):
    """The patient's current derived twin state.

    Composed at read time from the live `Patient` record, the latest
    `TwinVersion` row and the latest stored prediction — it is a *derived* view,
    not a separately stored blob, which is why `derived_at` is a request
    timestamp rather than a persisted field.
    """

    patient_id: str
    patient_name: str
    twin_status: str
    version: str
    version_created_at: str
    last_updated: str
    stage: str
    tumor_size_mm: float
    grade: int
    ki67: float
    nodes_involved: int
    er_status: str
    pr_status: str
    her2_status: str
    age: int
    current_treatment: str
    risk: str
    survival_probability: float
    latest_prediction: Optional[PredictionRun] = None
    model: ModelMetadata
    derived_at: str
    caveat: str


# --------------------------------------------------------------- Simulation --


class Scenario(Camel):
    id: str
    name: str
    regimen: str
    predicted_response: float
    tumor_change: float
    risk: Literal["low", "moderate", "high"]
    confidence: float
    survival5y: float = Field(alias="survival5y")
    side_effect_risk: float
    recovery_weeks: int
    recommended: bool

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ScenarioDraft(Camel):
    name: str
    regimen: str
    dosage: str = ""
    duration_weeks: int = 12
    notes: str = ""


class SimulationRun(Camel):
    id: str
    date: str
    patient: str
    patient_id: str
    twin_version: str
    model: str
    selected: str
    compared: list[str] = Field(default_factory=list)
    decision: Literal["Promoted to plan", "Under review", "Rejected"]
    decided_by: str
    notes: str
    survival: float
    response: float
    confidence: float


# -------------------------------------------------------------- Docs / OCR --


class DocumentRecord(Camel):
    id: str
    name: str
    category: str
    patient: str
    date: str
    size: str
    version: int
    status: str


class DocumentUploadInput(Camel):
    name: str
    size: int
    patient_id: Optional[str] = None
    category: Optional[str] = None


class DocumentVersion(Camel):
    version: int
    date: str
    author: str
    note: str


class OcrField(Camel):
    field: str
    value: str
    confidence: float


class OcrFieldApprovalInput(Camel):
    field: str
    value: str
    confidence: float = 1.0


class OcrExtraction(Camel):
    document_id: str
    fields: list[OcrField]
    model: str
    extracted_at: str


class OcrRejectInput(Camel):
    reason: str


class OcrFieldApprovalRequest(Camel):
    fields: list[OcrFieldApprovalInput]


# ------------------------------------------------------------------ Reports --


class SavedReport(Camel):
    id: str
    title: str
    patient: str
    patient_id: str
    type: Literal["Clinical summary", "Tumor board packet", "Model audit", "Cohort summary"]
    created: str
    version: int
    status: Literal["Final", "Draft", "Archived"]
    downloads: int


class ReportVersion(Camel):
    version: int
    date: str
    author: str
    note: str


class DownloadRecord(Camel):
    id: str
    report: str
    format: str
    by: str
    date: str


class ReportExportInput(Camel):
    format: Literal["pdf", "csv"]
    report_id: Optional[str] = None


class GenerateReportInput(Camel):
    patient_id: str
    report_type: str = "Clinical summary"


# ---------------------------------------------------------- Care coordination --


class Appointment(Camel):
    id: str
    title: str
    doctor: str
    date: str
    time: str
    location: str
    status: str


class AppointmentInput(Camel):
    title: str
    doctor: str
    date: str
    time: str
    location: str = ""
    patient_id: Optional[str] = None


class SideEffect(Camel):
    name: str
    grade: str
    advice: str


class Medication(Camel):
    name: str
    dose: str
    schedule: str


class TreatmentPlan(Camel):
    regimen: str
    cycle: int
    total_cycles: int
    started_on: str
    next_dose: str
    adherence: float
    side_effects: list[SideEffect] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)


class NotificationItem(Camel):
    id: str
    title: str
    body: str
    time: str
    unread: bool
    type: Optional[str] = None


# ------------------------------------------------------------ Administration --


class Hospital(Camel):
    id: str
    name: str
    city: str
    beds: int
    doctors: int
    patients: int
    status: str


class HospitalInput(Camel):
    name: str
    city: str = ""
    beds: int = 0
    doctors: int = 0
    patients: int = 0
    status: str = "Active"


class DoctorProfile(Camel):
    id: str
    name: str
    dept: str
    hospital: str
    patients: int
    status: str


class Department(Camel):
    id: str
    name: str
    head: str
    staff: int
    active_cases: int


class PlatformUser(Camel):
    id: str
    name: str
    email: str
    role: str
    last_active: str
    status: str


class AuditLogEntry(Camel):
    id: str
    time: str
    actor: str
    actor_role: str = ""
    action: str
    target: str
    before: dict | None = None
    after: dict | None = None
    ip: str


class PermissionRow(Camel):
    capability: str
    doctor: bool
    patient: bool
    technician: bool
    admin: bool


# ------------------------------------------------------------------ Research --


class MLModel(Camel):
    id: str
    name: str
    version: str
    task: str
    auc: float
    status: str


class Dataset(Camel):
    id: str
    name: str
    records: int
    modalities: str
    updated: str


class TrainingRun(Camel):
    id: str
    model: str
    started: str
    duration: str
    epochs: int
    loss: float
    status: str


class ModelVersion(Camel):
    version: str
    released: str
    auc: float
    notes: str
    stage: str


class PerformancePoint(Camel):
    month: str
    auc: float
    precision: float
    recall: float


# ----------------------------------------------------------------- Analytics --

MetricPoint = dict[str, Any]
