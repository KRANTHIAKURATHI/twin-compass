"""Business logic for patients: risk recomputation, patient-code allocation,
timeline/twin-version side effects, audit logging. Routers call into this and
stay thin; data access goes through PatientRepository."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models, schemas
from app.core.exceptions import NotFoundError
from app.deps import assert_patient_readable, log_audit
from app.ml.interface import get_prediction_model, patient_to_model_fields
from app.repositories.patient_repository import PatientRepository
from app.serializers import patient_to_schema


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recompute_risk(p: models.Patient) -> None:
    """Derives risk/survival from the same clinical model used for
    predictions, so a freshly created/edited patient isn't left with
    stale placeholder values."""
    result = get_prediction_model().predict(patient_to_model_fields(p))
    p.risk = result["risk"]
    p.survival_probability = result["survival"]


class PatientService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PatientRepository(db)

    def _assert_readable(self, p: models.Patient, user: models.User) -> None:
        """Delegates to the single shared ownership rule in `app.deps`."""
        assert_patient_readable(p, user)

    def list_patients(self, search: str | None, sort: str | None, order: str, user: models.User) -> list[schemas.Patient]:
        patients = self.repo.list(search, sort, order)
        if user.role == "patient":
            patients = [p for p in patients if p.email == user.email]
        return [patient_to_schema(p) for p in patients]

    def get_patient(self, patient_id: str, user: models.User) -> schemas.Patient:
        p = self.repo.get(patient_id)
        if not p:
            raise NotFoundError("Patient not found")
        self._assert_readable(p, user)
        return patient_to_schema(p)

    def create_patient(self, payload: schemas.PatientInput, user: models.User) -> schemas.Patient:
        data = payload.model_dump(exclude_unset=True, by_alias=False)
        p = models.Patient(
            patient_code=self.repo.next_patient_code(),
            name=data["name"],
            age=data.get("age", 0),
            gender=data.get("gender", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            hospital=data.get("hospital", user.hospital or ""),
            stage=data.get("stage", "I"),
            tumor_size_mm=data.get("tumor_size_mm", 10),
            er_status=data.get("er_status", "Negative"),
            pr_status=data.get("pr_status", "Negative"),
            her2_status=data.get("her2_status", "Negative"),
            ki67=data.get("ki67", 10),
            grade=data.get("grade", 1),
            nodes_involved=data.get("nodes_involved", 0),
            current_treatment=data.get("current_treatment", "Not yet started"),
            status=data.get("status", "Monitoring"),
            diagnosed_on=data.get("diagnosed_on", _now()),
            notes=data.get("notes", ""),
            comorbidities=data.get("comorbidities", []),
            allergies=data.get("allergies", []),
            current_medications=data.get("current_medications", []),
            previous_treatments=data.get("previous_treatments", []),
            family_history=data.get("family_history", ""),
            smoking_status=data.get("smoking_status", "Unknown"),
            alcohol_use=data.get("alcohol_use", "Unknown"),
            surgical_history=data.get("surgical_history", []),
            created_by=user.id,
        )
        _recompute_risk(p)
        p.last_updated = _now()
        self.repo.add(p)
        self.db.flush()
        self.repo.add(models.TimelineEvent(
            patient_id=p.id, date=p.diagnosed_on, title="Patient record created",
            detail=f"Digital twin initialized by {user.name}.", kind="diagnosis",
        ))
        self.repo.add(models.TwinVersion(
            patient_id=p.id, version="v1", author=user.name,
            summary="Initial digital twin created from intake data.",
            tumor_size_mm=p.tumor_size_mm, survival=p.survival_probability, risk=p.risk,
            model=get_prediction_model().metadata.name, snapshot=patient_to_schema(p).model_dump(by_alias=False),
        ))
        self.db.commit()
        self.db.refresh(p)
        after = patient_to_schema(p).model_dump(by_alias=False)
        log_audit(self.db, actor=user.email, actor_role=user.role, action="create_patient", target=p.name, after=after)
        return patient_to_schema(p)

    def update_patient(self, patient_id: str, payload: schemas.PatientInput, user: models.User) -> schemas.Patient:
        p = self.repo.get(patient_id)
        if not p:
            raise NotFoundError("Patient not found")
        before = patient_to_schema(p).model_dump(by_alias=False)
        data = payload.model_dump(exclude_unset=True, by_alias=False)
        for key, value in data.items():
            if hasattr(p, key):
                setattr(p, key, value)
        _recompute_risk(p)
        p.last_updated = _now()
        self.repo.add(models.TimelineEvent(
            patient_id=p.id, date=p.last_updated, title="Patient record updated",
            detail=f"Clinical data updated by {user.name}.", kind="note",
        ))
        self.db.commit()
        self.db.refresh(p)
        after = patient_to_schema(p).model_dump(by_alias=False)
        log_audit(self.db, actor=user.email, actor_role=user.role, action="update_patient", target=p.name, before=before, after=after)
        return patient_to_schema(p)

    def delete_patient(self, patient_id: str, user: models.User) -> None:
        p = self.repo.get(patient_id)
        if not p:
            raise NotFoundError("Patient not found")
        name = p.name
        before = patient_to_schema(p).model_dump(by_alias=False)
        self.repo.soft_delete(p)
        self.db.commit()
        log_audit(self.db, actor=user.email, actor_role=user.role, action="delete_patient", target=name, before=before)
