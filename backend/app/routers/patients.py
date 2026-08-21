from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.deps import get_current_user, require_roles
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])

_clinical_staff = require_roles("doctor", "admin")


def _assert_patient_readable(patient: models.Patient, user: models.User) -> None:
    if user.role == "patient" and patient.email != user.email:
        raise ForbiddenError("Not authorized to view this patient")


@router.get("", response_model=list[schemas.Patient])
def list_patients(
    search: str | None = Query(None),
    sort: str | None = Query(None),
    order: str = Query("asc"),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return PatientService(db).list_patients(search, sort, order, user)


@router.get("/{patient_id}", response_model=schemas.Patient)
def get_patient(patient_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return PatientService(db).get_patient(patient_id, user)


@router.post("", response_model=schemas.MutationResult[schemas.Patient])
def create_patient(
    payload: schemas.PatientInput,
    db: Session = Depends(get_db),
    user: models.User = Depends(_clinical_staff),
):
    patient = PatientService(db).create_patient(payload, user)
    return schemas.MutationResult(ok=True, data=patient, message="Patient created")


@router.patch("/{patient_id}", response_model=schemas.MutationResult[schemas.Patient])
def update_patient(
    patient_id: str,
    payload: schemas.PatientInput,
    db: Session = Depends(get_db),
    user: models.User = Depends(_clinical_staff),
):
    patient = PatientService(db).update_patient(patient_id, payload, user)
    return schemas.MutationResult(ok=True, data=patient, message="Patient updated")


@router.delete("/{patient_id}", response_model=schemas.MutationResult)
def delete_patient(patient_id: str, db: Session = Depends(get_db), user: models.User = Depends(_clinical_staff)):
    PatientService(db).delete_patient(patient_id, user)
    return schemas.MutationResult(ok=True, message="Patient deleted")


@router.get("/{patient_id}/labs", response_model=list[schemas.LabResult])
def get_labs(patient_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise NotFoundError("Patient not found")
    _assert_patient_readable(patient, user)
    rows = db.query(models.LabResult).filter(models.LabResult.patient_id == patient_id).order_by(models.LabResult.date.desc()).all()
    return [schemas.LabResult(date=r.date, panel=r.panel, marker=r.marker, value=r.value, unit=r.unit, range=r.range, flag=r.flag) for r in rows]


@router.post("/{patient_id}/labs", response_model=schemas.MutationResult[schemas.LabResult])
def add_lab(patient_id: str, payload: schemas.LabResultInput, db: Session = Depends(get_db), _user: models.User = Depends(_clinical_staff)):
    if not db.get(models.Patient, patient_id):
        raise NotFoundError("Patient not found")
    row = models.LabResult(
        patient_id=patient_id, date=payload.date or datetime.now(timezone.utc).isoformat(),
        panel=payload.panel, marker=payload.marker, value=payload.value, unit=payload.unit,
        range=payload.range, flag=payload.flag,
    )
    db.add(row)
    db.commit()
    return schemas.MutationResult(ok=True, data=schemas.LabResult(date=row.date, panel=row.panel, marker=row.marker, value=row.value, unit=row.unit, range=row.range, flag=row.flag))


@router.get("/{patient_id}/imaging", response_model=list[schemas.ImagingStudy])
def get_imaging(patient_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise NotFoundError("Patient not found")
    _assert_patient_readable(patient, user)
    rows = db.query(models.ImagingStudy).filter(models.ImagingStudy.patient_id == patient_id).order_by(models.ImagingStudy.date.desc()).all()
    return [schemas.ImagingStudy(id=r.id, modality=r.modality, region=r.region, date=r.date, finding=r.finding, radiologist=r.radiologist, status=r.status) for r in rows]


@router.post("/{patient_id}/imaging", response_model=schemas.MutationResult[schemas.ImagingStudy])
def add_imaging(patient_id: str, payload: schemas.ImagingStudyInput, db: Session = Depends(get_db), _user: models.User = Depends(_clinical_staff)):
    if not db.get(models.Patient, patient_id):
        raise NotFoundError("Patient not found")
    row = models.ImagingStudy(
        patient_id=patient_id, modality=payload.modality, region=payload.region,
        date=payload.date or datetime.now(timezone.utc).isoformat(), finding=payload.finding,
        radiologist=payload.radiologist, status=payload.status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return schemas.MutationResult(ok=True, data=schemas.ImagingStudy(id=row.id, modality=row.modality, region=row.region, date=row.date, finding=row.finding, radiologist=row.radiologist, status=row.status))


@router.get("/{patient_id}/timeline", response_model=list[schemas.TimelineEvent])
def get_timeline(patient_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise NotFoundError("Patient not found")
    _assert_patient_readable(patient, user)
    rows = db.query(models.TimelineEvent).filter(models.TimelineEvent.patient_id == patient_id).order_by(models.TimelineEvent.date.desc()).all()
    return [schemas.TimelineEvent(date=r.date, title=r.title, detail=r.detail, kind=r.kind) for r in rows]
