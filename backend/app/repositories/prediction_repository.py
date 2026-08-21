"""Data access for stored model predictions (`prediction_runs`). No business
logic here — that lives in app/services/prediction_service.py."""

from sqlalchemy.orm import Session

from app import models


class PredictionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_patient(self, patient_id: str) -> models.Patient | None:
        p = self.db.get(models.Patient, patient_id)
        return p if p and p.deleted_at is None else None

    def latest(self, patient_id: str) -> models.PredictionRun | None:
        return (
            self.db.query(models.PredictionRun)
            .filter(models.PredictionRun.patient_id == patient_id)
            .order_by(models.PredictionRun.date.desc())
            .first()
        )

    def history(self, patient_id: str, ascending: bool = False) -> list[models.PredictionRun]:
        order = models.PredictionRun.date.asc() if ascending else models.PredictionRun.date.desc()
        return (
            self.db.query(models.PredictionRun)
            .filter(models.PredictionRun.patient_id == patient_id)
            .order_by(order)
            .all()
        )

    def latest_twin_version(self, patient_id: str) -> str:
        tv = (
            self.db.query(models.TwinVersion)
            .filter(models.TwinVersion.patient_id == patient_id)
            .order_by(models.TwinVersion.created_at.desc())
            .first()
        )
        return tv.version if tv else "v1"

    def add(self, row) -> None:
        self.db.add(row)
