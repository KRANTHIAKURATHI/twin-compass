from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.deps import assert_patient_readable, get_current_user, log_audit

router = APIRouter(prefix="/appointments", tags=["appointments"])


def _row_to_schema(a: models.Appointment) -> schemas.Appointment:
    return schemas.Appointment(id=a.id, title=a.title, doctor=a.doctor, date=a.date, time=a.time, location=a.location, status=a.status)


def _assert_appointment_readable(db: Session, appt: models.Appointment, user: models.User) -> None:
    if appt.patient_id:
        patient = db.get(models.Patient, appt.patient_id)
        if patient:
            assert_patient_readable(patient, user)


@router.get("", response_model=list[schemas.Appointment])
def list_appointments(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = db.query(models.Appointment).order_by(models.Appointment.date.asc()).all()
    if user.role == "patient":
        def _owned(a: models.Appointment) -> bool:
            p = db.get(models.Patient, a.patient_id) if a.patient_id else None
            return bool(p and p.email == user.email)
        rows = [a for a in rows if _owned(a)]
    return [_row_to_schema(a) for a in rows]


@router.post("", response_model=schemas.MutationResult[schemas.Appointment])
def create(payload: schemas.AppointmentInput, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if payload.patient_id:
        patient = db.get(models.Patient, payload.patient_id)
        if patient:
            assert_patient_readable(patient, user)
    row = models.Appointment(title=payload.title, doctor=payload.doctor, date=payload.date, time=payload.time,
                              location=payload.location, patient_id=payload.patient_id, status="Scheduled")
    db.add(row)
    db.commit()
    db.refresh(row)
    log_audit(db, actor=user.email, actor_role=user.role, action="create_appointment", target=row.title,
              after={"id": row.id, "title": row.title, "date": row.date, "time": row.time, "status": row.status})
    return schemas.MutationResult(ok=True, data=_row_to_schema(row), message="Appointment scheduled")


@router.post("/{appointment_id}/cancel", response_model=schemas.MutationResult)
def cancel(appointment_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    row = db.get(models.Appointment, appointment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _assert_appointment_readable(db, row, user)
    before_status = row.status
    row.status = "Cancelled"
    db.commit()
    log_audit(db, actor=user.email, actor_role=user.role, action="cancel_appointment", target=row.title,
              before={"status": before_status}, after={"status": row.status})
    return schemas.MutationResult(ok=True, message="Appointment cancelled")
