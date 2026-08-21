"""Data access for the Digital Twin aggregate (TwinVersion / TwinSnapshotRow /
PredictionRun rows tied to a patient). No business logic here — that lives in
app/services/twin_service.py."""

from sqlalchemy.orm import Session

from app import models


class TwinRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_patients(self) -> list[models.Patient]:
        return self.db.query(models.Patient).filter(models.Patient.deleted_at.is_(None)).all()

    def get_patient(self, patient_id: str) -> models.Patient | None:
        p = self.db.get(models.Patient, patient_id)
        return p if p and p.deleted_at is None else None

    def list_versions(self, patient_id: str) -> list[models.TwinVersion]:
        return (
            self.db.query(models.TwinVersion)
            .filter(models.TwinVersion.patient_id == patient_id)
            .order_by(models.TwinVersion.created_at.desc())
            .all()
        )

    def get_version(self, patient_id: str, version: str) -> models.TwinVersion | None:
        return (
            self.db.query(models.TwinVersion)
            .filter(models.TwinVersion.patient_id == patient_id, models.TwinVersion.version == version)
            .first()
        )

    def latest_version(self, patient_id: str) -> models.TwinVersion | None:
        return (
            self.db.query(models.TwinVersion)
            .filter(models.TwinVersion.patient_id == patient_id)
            .order_by(models.TwinVersion.created_at.desc())
            .first()
        )

    def list_snapshots(self, patient_id: str) -> list[models.TwinSnapshotRow]:
        return (
            self.db.query(models.TwinSnapshotRow)
            .filter(models.TwinSnapshotRow.patient_id == patient_id)
            .order_by(models.TwinSnapshotRow.taken_at.desc())
            .all()
        )

    def next_version_label(self, patient_id: str) -> str:
        count = self.db.query(models.TwinVersion).filter(models.TwinVersion.patient_id == patient_id).count()
        return f"v{count + 1}"

    def add(self, row) -> None:
        self.db.add(row)
