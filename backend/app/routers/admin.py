from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.core.security import hash_password
from app.deps import log_audit, require_roles

router = APIRouter(prefix="/admin", tags=["admin"])
_admin_only = require_roles("admin")


@router.post("/users", response_model=schemas.MutationResult[schemas.AuthUser])
def create_user(
    payload: schemas.RegisterPayload,
    db: Session = Depends(get_db),
    user: models.User = Depends(_admin_only),
):
    """Creates an account with an explicit role. Admin-only.

    This is the only path that can grant a privileged role — public
    self-registration (`POST /auth/register`) always yields a `patient`.
    """
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    created = models.User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        hospital=payload.hospital,
        specialization=payload.specialization,
    )
    db.add(created)
    db.commit()
    db.refresh(created)
    log_audit(db, actor=user.email, actor_role=user.role, action="create_user",
              target=created.email, after={"email": created.email, "granted_role": created.role})
    return schemas.MutationResult(
        ok=True,
        data=schemas.AuthUser(
            id=created.id, name=created.name, email=created.email, role=created.role,
            title=created.title, hospital=created.hospital, avatar_url=created.avatar_url,
        ),
        message=f"{created.role.capitalize()} account created",
    )


@router.get("/hospitals", response_model=list[schemas.Hospital])
def hospitals(db: Session = Depends(get_db), _user: models.User = Depends(_admin_only)):
    rows = db.query(models.Hospital).all()
    return [schemas.Hospital(id=h.id, name=h.name, city=h.city, beds=h.beds, doctors=h.doctors, patients=h.patients, status=h.status) for h in rows]


@router.post("/hospitals", response_model=schemas.MutationResult[schemas.Hospital])
def create_hospital(
    payload: schemas.HospitalInput,
    db: Session = Depends(get_db),
    user: models.User = Depends(_admin_only),
):
    created = models.Hospital(
        name=payload.name,
        city=payload.city,
        beds=payload.beds,
        doctors=payload.doctors,
        patients=payload.patients,
        status=payload.status,
    )
    db.add(created)
    db.commit()
    db.refresh(created)
    log_audit(db, actor=user.email, actor_role=user.role, action="create_hospital",
              target=created.name, after={"name": created.name, "city": created.city, "status": created.status})
    return schemas.MutationResult(
        ok=True,
        data=schemas.Hospital(
            id=created.id, name=created.name, city=created.city, beds=created.beds,
            doctors=created.doctors, patients=created.patients, status=created.status,
        ),
        message="Hospital tenant created successfully",
    )


@router.get("/doctors", response_model=list[schemas.DoctorProfile])
def doctors(db: Session = Depends(get_db), _user: models.User = Depends(_admin_only)):
    rows = db.query(models.User).filter(models.User.role == "doctor").all()
    result = []
    for d in rows:
        patient_count = db.query(models.Patient).filter(models.Patient.created_by == d.id).count()
        result.append(schemas.DoctorProfile(id=d.id, name=d.name, dept=d.department or "General Oncology",
                                             hospital=d.hospital or "", patients=patient_count, status=d.status))
    return result


@router.get("/departments", response_model=list[schemas.Department])
def departments(db: Session = Depends(get_db), _user: models.User = Depends(_admin_only)):
    rows = db.query(models.Department).all()
    return [schemas.Department(id=d.id, name=d.name, head=d.head, staff=d.staff, active_cases=d.active_cases) for d in rows]


@router.get("/users", response_model=list[schemas.PlatformUser])
def users(db: Session = Depends(get_db), _user: models.User = Depends(_admin_only)):
    rows = db.query(models.User).all()
    return [schemas.PlatformUser(id=u.id, name=u.name, email=u.email, role=u.role, last_active=u.last_active, status=u.status) for u in rows]


@router.get("/audit-logs", response_model=list[schemas.AuditLogEntry])
def audit_logs(db: Session = Depends(get_db), _user: models.User = Depends(_admin_only)):
    rows = db.query(models.AuditLogEntry).order_by(models.AuditLogEntry.time.desc()).limit(500).all()
    return [
        schemas.AuditLogEntry(
            id=a.id, time=a.time, actor=a.actor, actor_role=a.actor_role, action=a.action,
            target=a.target, before=a.before, after=a.after, ip=a.ip,
        )
        for a in rows
    ]


@router.get("/permissions", response_model=list[schemas.PermissionRow])
def permissions(db: Session = Depends(get_db), _user: models.User = Depends(_admin_only)):
    rows = db.query(models.PermissionRow).all()
    return [schemas.PermissionRow(capability=p.capability, doctor=p.doctor, patient=p.patient, technician=p.technician, admin=p.admin) for p in rows]


@router.put("/permissions", response_model=schemas.MutationResult)
def update_permissions(
    payload: list[schemas.PermissionRow],
    db: Session = Depends(get_db),
    user: models.User = Depends(_admin_only),
):
    for item in payload:
        row = db.query(models.PermissionRow).filter(models.PermissionRow.capability == item.capability).first()
        if row:
            row.doctor = item.doctor
            row.patient = item.patient
            row.technician = item.technician
            row.admin = item.admin
        else:
            new_row = models.PermissionRow(
                capability=item.capability,
                doctor=item.doctor,
                patient=item.patient,
                technician=item.technician,
                admin=item.admin,
            )
            db.add(new_row)
    db.commit()
    log_audit(db, actor=user.email, actor_role=user.role, action="update_permissions",
              target="permissions_matrix", after={"count": len(payload)})
    return schemas.MutationResult(ok=True, message="Permissions matrix updated successfully")

