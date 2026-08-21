"""Data access for Patient. No business logic here — that lives in
app/services/patient_service.py. Every read excludes soft-deleted rows."""

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models


class PatientRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, patient_id: str) -> models.Patient | None:
        p = self.db.get(models.Patient, patient_id)
        return p if p and p.deleted_at is None else None

    def list(self, search: str | None, sort: str | None, order: str) -> list[models.Patient]:
        q = self.db.query(models.Patient).filter(models.Patient.deleted_at.is_(None))
        if search:
            like = f"%{search}%"
            q = q.filter(or_(models.Patient.name.ilike(like), models.Patient.hospital.ilike(like)))
        if sort and hasattr(models.Patient, sort):
            col = getattr(models.Patient, sort)
            q = q.order_by(col.desc() if order == "desc" else col.asc())
        return q.all()

    def add(self, patient: models.Patient) -> None:
        self.db.add(patient)

    def soft_delete(self, patient: models.Patient) -> None:
        patient.deleted_at = datetime.now(timezone.utc)

    def next_patient_code(self) -> str:
        counter = self.db.query(models.PatientCodeCounter).with_for_update().first()
        if not counter:
            counter = models.PatientCodeCounter(id=1, next_value=1000)
            self.db.add(counter)
            self.db.flush()
        code = f"PT-{counter.next_value}"
        counter.next_value += 1
        return code
