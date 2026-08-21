from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.deps import get_current_user, require_roles
from app.services.twin_service import TwinService

router = APIRouter(prefix="/digital-twins", tags=["digital-twins"])

_clinical_staff = require_roles("doctor", "admin")


@router.get("", response_model=list[schemas.Patient])
def list_twins(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return TwinService(db).list_twins(user)


@router.get(
    "/{patient_id}/state",
    response_model=schemas.TwinState,
    description=(
        "The patient's current derived twin state: live clinical fields, the "
        "latest twin version, the latest stored prediction and the model's "
        "provenance. Composed at request time — it is a derived view, not a "
        "separately stored snapshot."
    ),
)
def state(patient_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return TwinService(db).get_state(patient_id, user)


@router.get("/{patient_id}/versions", response_model=list[schemas.TwinVersion])
def versions(patient_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return TwinService(db).list_versions(patient_id, user)


@router.get("/{patient_id}/snapshots", response_model=list[schemas.TwinSnapshot])
def snapshots(patient_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return TwinService(db).list_snapshots(patient_id, user)


@router.post("/{patient_id}/resync", response_model=schemas.MutationResult)
def resync(patient_id: str, db: Session = Depends(get_db), user: models.User = Depends(_clinical_staff)):
    version = TwinService(db).resync(patient_id, user)
    return schemas.MutationResult(ok=True, message=f"Digital twin resynced to {version}")


@router.post("/{patient_id}/versions/{version}/restore", response_model=schemas.MutationResult)
def restore(patient_id: str, version: str, db: Session = Depends(get_db), user: models.User = Depends(_clinical_staff)):
    TwinService(db).restore(patient_id, version, user)
    return schemas.MutationResult(ok=True, message=f"Restored to {version}")


@router.post("/{patient_id}/archive", response_model=schemas.MutationResult)
def archive(patient_id: str, db: Session = Depends(get_db), user: models.User = Depends(_clinical_staff)):
    TwinService(db).archive(patient_id, user)
    return schemas.MutationResult(ok=True, message="Digital twin archived")
