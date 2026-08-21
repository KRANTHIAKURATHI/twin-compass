"""SQLAlchemy ORM models — one table per entity in src/types/models.ts.

IDs are UUID4 strings (works unchanged against SQLite today and Supabase
Postgres later — see README "Switching to Supabase"). JSON columns hold the
small nested lists (history, compared, sideEffects, medications) that the
frontend types as arrays of primitives/simple objects.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="doctor")  # doctor|patient|researcher|admin
    title = Column(String, nullable=True)
    hospital = Column(String, nullable=True)
    department = Column(String, nullable=True)
    specialization = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    status = Column(String, default="Active")
    last_active = Column(String, default=now_iso)
    created_at = Column(String, default=now_iso)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class PatientCodeCounter(Base):
    """Single-row counter used to allocate human-readable PT-1000-style
    patient codes. A dedicated table (rather than a DB SEQUENCE) keeps
    allocation portable across SQLite (dev) and Postgres (prod)."""

    __tablename__ = "patient_code_counters"
    id = Column(Integer, primary_key=True, default=1)
    next_value = Column(Integer, default=1000)


class Patient(Base):
    __tablename__ = "patients"
    id = Column(String, primary_key=True, default=gen_id)
    patient_code = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    age = Column(Integer, default=0)
    gender = Column(String, default="")
    phone = Column(String, default="")
    email = Column(String, default="")
    hospital = Column(String, default="")
    stage = Column(String, default="I")
    tumor_size_mm = Column(Float, default=0)
    er_status = Column(String, default="Negative")
    pr_status = Column(String, default="Negative")
    her2_status = Column(String, default="Negative")
    ki67 = Column(Float, default=10)
    grade = Column(Integer, default=1)
    nodes_involved = Column(Integer, default=0)
    current_treatment = Column(String, default="")
    status = Column(String, default="Monitoring")
    risk = Column(String, default="low")
    survival_probability = Column(Float, default=0.9)
    last_updated = Column(String, default=now_iso)
    diagnosed_on = Column(String, default=now_iso)
    twin_status = Column(String, default="Synced")
    history = Column(JSON, default=list)
    notes = Column(Text, default="")
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(String, default=now_iso)
    deleted_at = Column(DateTime, nullable=True)

    # -- Medical history --
    comorbidities = Column(JSON, default=list)
    allergies = Column(JSON, default=list)
    current_medications = Column(JSON, default=list)
    previous_treatments = Column(JSON, default=list)
    family_history = Column(Text, default="")
    smoking_status = Column(String, default="Unknown")  # Never|Former|Current|Unknown
    alcohol_use = Column(String, default="Unknown")  # None|Occasional|Regular|Unknown
    surgical_history = Column(JSON, default=list)

    timeline = relationship("TimelineEvent", cascade="all, delete-orphan", backref="patient")
    reports = relationship("PatientReportRef", cascade="all, delete-orphan", backref="patient")
    labs = relationship("LabResult", cascade="all, delete-orphan", backref="patient")
    imaging = relationship("ImagingStudy", cascade="all, delete-orphan", backref="patient")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    date = Column(String, default=now_iso)
    title = Column(String, default="")
    detail = Column(Text, default="")
    kind = Column(String, default="note")  # diagnosis|treatment|scan|note


class PatientReportRef(Base):
    __tablename__ = "patient_report_refs"
    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    name = Column(String, default="")
    type = Column(String, default="")
    date = Column(String, default=now_iso)
    size = Column(String, default="0 KB")


class LabResult(Base):
    __tablename__ = "lab_results"
    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    date = Column(String, default=now_iso)
    panel = Column(String, default="")
    marker = Column(String, default="")
    value = Column(String, default="")
    unit = Column(String, default="")
    range = Column(String, default="")
    flag = Column(String, default="normal")


class ImagingStudy(Base):
    __tablename__ = "imaging_studies"
    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    modality = Column(String, default="MRI")
    region = Column(String, default="")
    date = Column(String, default=now_iso)
    finding = Column(Text, default="")
    radiologist = Column(String, default="")
    status = Column(String, default="Pending")


class TwinVersion(Base):
    __tablename__ = "twin_versions"
    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    version = Column(String, default="v1")
    created_at = Column(String, default=now_iso)
    status = Column(String, default="Active")  # Active|Superseded|Archived|Draft
    author = Column(String, default="")
    summary = Column(String, default="")
    tumor_size_mm = Column(Float, default=0)
    survival = Column(Float, default=0.9)
    risk = Column(String, default="low")
    model = Column(String, default="")
    snapshot = Column(JSON, default=dict)  # full patient field snapshot, for restore


class TwinSnapshotRow(Base):
    __tablename__ = "twin_snapshots"
    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    version = Column(String, default="v1")
    taken_at = Column(String, default=now_iso)
    trigger = Column(String, default="manual")
    size = Column(String, default="0 KB")


class PredictionRun(Base):
    __tablename__ = "prediction_runs"
    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    date = Column(String, default=now_iso)
    twin_version = Column(String, default="v1")
    model = Column(String, default="")
    survival = Column(Float, default=0.9)
    recurrence = Column(Float, default=0.1)
    response = Column(String, default="Favorable")
    confidence = Column(Float, default=0.8)
    status = Column(String, default="Complete")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id = Column(String, primary_key=True, default=gen_id)
    date = Column(String, default=now_iso)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    patient_name = Column(String, default="")
    twin_version = Column(String, default="v1")
    model = Column(String, default="")
    selected = Column(String, default="")
    compared = Column(JSON, default=list)
    decision = Column(String, default="Under review")
    decided_by = Column(String, default="")
    notes = Column(Text, default="")
    survival = Column(Float, default=0.9)
    response = Column(Float, default=0.5)
    confidence = Column(Float, default=0.7)
    scenarios = Column(JSON, default=list)


class DocumentRecord(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    category = Column(String, default="Blood")
    patient_id = Column(String, ForeignKey("patients.id"), nullable=True)
    patient_name = Column(String, default="")
    date = Column(String, default=now_iso)
    size = Column(String, default="0 KB")
    version = Column(Integer, default=1)
    status = Column(String, default="Pending OCR")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id = Column(String, primary_key=True, default=gen_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    version = Column(Integer, default=1)
    date = Column(String, default=now_iso)
    author = Column(String, default="")
    note = Column(String, default="")


class OcrFieldRow(Base):
    __tablename__ = "ocr_fields"
    id = Column(String, primary_key=True, default=gen_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    field = Column(String, default="")
    value = Column(String, default="")
    confidence = Column(Float, default=0.5)
    model = Column(String, default="ocr-heuristic-v1")
    extracted_at = Column(String, default=now_iso)
    approved = Column(Boolean, default=False)
    rejected = Column(Boolean, default=False)


class SavedReport(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String, default="")
    patient_id = Column(String, ForeignKey("patients.id"), nullable=True)
    patient_name = Column(String, default="")
    type = Column(String, default="Clinical summary")
    created = Column(String, default=now_iso)
    version = Column(Integer, default=1)
    status = Column(String, default="Draft")
    downloads = Column(Integer, default=0)


class ReportVersion(Base):
    __tablename__ = "report_versions"
    id = Column(String, primary_key=True, default=gen_id)
    report_id = Column(String, ForeignKey("reports.id"), nullable=False)
    version = Column(Integer, default=1)
    date = Column(String, default=now_iso)
    author = Column(String, default="")
    note = Column(String, default="")


class DownloadRecord(Base):
    __tablename__ = "download_records"
    id = Column(String, primary_key=True, default=gen_id)
    report_id = Column(String, ForeignKey("reports.id"), nullable=False)
    format = Column(String, default="pdf")
    by = Column(String, default="")
    date = Column(String, default=now_iso)


class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String, default="")
    doctor = Column(String, default="")
    patient_id = Column(String, ForeignKey("patients.id"), nullable=True)
    date = Column(String, default=now_iso)
    time = Column(String, default="09:00")
    location = Column(String, default="")
    status = Column(String, default="Scheduled")


class TreatmentPlanRow(Base):
    __tablename__ = "treatment_plans"
    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), unique=True, nullable=False)
    regimen = Column(String, default="")
    cycle = Column(Integer, default=1)
    total_cycles = Column(Integer, default=6)
    started_on = Column(String, default=now_iso)
    next_dose = Column(String, default=now_iso)
    adherence = Column(Float, default=1.0)
    side_effects = Column(JSON, default=list)
    medications = Column(JSON, default=list)


class NotificationItem(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    audience_role = Column(String, nullable=True)  # broadcast to a role when user_id is null
    title = Column(String, default="")
    body = Column(Text, default="")
    time = Column(String, default=now_iso)
    unread = Column(Boolean, default=True)
    type = Column(String, nullable=True)


class Hospital(Base):
    __tablename__ = "hospitals"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, default="")
    city = Column(String, default="")
    beds = Column(Integer, default=0)
    doctors = Column(Integer, default=0)
    patients = Column(Integer, default=0)
    status = Column(String, default="Active")


class Department(Base):
    __tablename__ = "departments"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, default="")
    head = Column(String, default="")
    staff = Column(Integer, default=0)
    active_cases = Column(Integer, default=0)


class AuditLogEntry(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=gen_id)
    time = Column(String, default=now_iso)
    actor = Column(String, default="")
    actor_role = Column(String, default="")
    action = Column(String, default="")
    target = Column(String, default="")
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)
    ip = Column(String, default="")


class PermissionRow(Base):
    __tablename__ = "permissions"
    id = Column(String, primary_key=True, default=gen_id)
    capability = Column(String, unique=True, nullable=False)
    doctor = Column(Boolean, default=False)
    patient = Column(Boolean, default=False)
    technician = Column(Boolean, default=False)
    admin = Column(Boolean, default=True)


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, default="")
    records = Column(Integer, default=0)
    modalities = Column(String, default="")
    updated = Column(String, default=now_iso)


class TrainingRun(Base):
    __tablename__ = "training_runs"
    id = Column(String, primary_key=True, default=gen_id)
    model = Column(String, default="")
    started = Column(String, default=now_iso)
    duration = Column(String, default="")
    epochs = Column(Integer, default=1)
    loss = Column(Float, default=0.0)
    status = Column(String, default="Complete")


class ModelVersionRow(Base):
    __tablename__ = "model_versions"
    id = Column(String, primary_key=True, default=gen_id)
    version = Column(String, default="v1.0.0")
    released = Column(String, default=now_iso)
    auc = Column(Float, default=0.0)
    notes = Column(String, default="")
    stage = Column(String, default="Production")


class MLModelRow(Base):
    __tablename__ = "ml_models"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, default="")
    version = Column(String, default="v1.0.0")
    task = Column(String, default="Malignancy risk classification")
    auc = Column(Float, default=0.0)
    status = Column(String, default="Production")


class PerformancePointRow(Base):
    __tablename__ = "performance_points"
    id = Column(String, primary_key=True, default=gen_id)
    month = Column(String, default="")
    auc = Column(Float, default=0.0)
    precision = Column(Float, default=0.0)
    recall = Column(Float, default=0.0)
