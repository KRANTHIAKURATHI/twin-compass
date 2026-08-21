"""Data access for treatment simulations (`simulation_runs`) and the treatment
plan row they promote into. No business logic here — that lives in
app/services/simulation_service.py."""

from sqlalchemy.orm import Session

from app import models


class SimulationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_patient(self, patient_id: str) -> models.Patient | None:
        p = self.db.get(models.Patient, patient_id)
        return p if p and p.deleted_at is None else None

    def list_all(self) -> list[models.SimulationRun]:
        return self.db.query(models.SimulationRun).order_by(models.SimulationRun.date.desc()).all()

    def list_for_patient_email(self, email: str) -> list[models.SimulationRun]:
        """Joins instead of the previous per-row `db.get(Patient, ...)` loop,
        which issued one query per simulation."""
        return (
            self.db.query(models.SimulationRun)
            .join(models.Patient, models.SimulationRun.patient_id == models.Patient.id)
            .filter(models.Patient.email == email, models.Patient.deleted_at.is_(None))
            .order_by(models.SimulationRun.date.desc())
            .all()
        )

    def get(self, sim_id: str) -> models.SimulationRun | None:
        return self.db.get(models.SimulationRun, sim_id)

    def get_plan(self, patient_id: str) -> models.TreatmentPlanRow | None:
        return (
            self.db.query(models.TreatmentPlanRow)
            .filter(models.TreatmentPlanRow.patient_id == patient_id)
            .first()
        )

    def add(self, row) -> None:
        self.db.add(row)
