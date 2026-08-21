from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.deps import assert_patient_readable, get_current_user, log_audit

router = APIRouter(prefix="/documents", tags=["documents"])


def _row_to_schema(d: models.DocumentRecord) -> schemas.DocumentRecord:
    return schemas.DocumentRecord(id=d.id, name=d.name, category=d.category, patient=d.patient_name,
                                   date=d.date, size=d.size, version=d.version, status=d.status)


def _assert_document_readable(db: Session, doc: models.DocumentRecord, user: models.User) -> None:
    if doc.patient_id:
        patient = db.get(models.Patient, doc.patient_id)
        if patient:
            assert_patient_readable(patient, user)


@router.get("", response_model=list[schemas.DocumentRecord])
def list_documents(search: str | None = Query(None), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.DocumentRecord)
    if search:
        q = q.filter(models.DocumentRecord.name.ilike(f"%{search}%"))
    rows = q.order_by(models.DocumentRecord.date.desc()).all()
    if user.role == "patient":
        def _owned(d: models.DocumentRecord) -> bool:
            p = db.get(models.Patient, d.patient_id) if d.patient_id else None
            return bool(p and p.email == user.email)
        rows = [d for d in rows if _owned(d)]
    return [_row_to_schema(d) for d in rows]


@router.get("/{doc_id}", response_model=schemas.DocumentRecord | None)
def get_document(doc_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    d = db.get(models.DocumentRecord, doc_id)
    if not d:
        return None
    _assert_document_readable(db, d, user)
    return _row_to_schema(d)


@router.post("", response_model=schemas.MutationResult[schemas.DocumentRecord])
def upload(payload: schemas.DocumentUploadInput, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    patient_name = ""
    if payload.patient_id:
        patient = db.get(models.Patient, payload.patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        assert_patient_readable(patient, user)
        patient_name = patient.name

    size_kb = max(round(payload.size / 1024, 1), 0.1)
    row = models.DocumentRecord(
        name=payload.name, category=payload.category or _guess_category(payload.name),
        patient_id=payload.patient_id, patient_name=patient_name, size=f"{size_kb} KB",
        version=1, status="Pending OCR",
    )
    db.add(row)
    db.flush()
    db.add(models.DocumentVersion(document_id=row.id, version=1, date=row.date, author=user.name, note="Initial upload"))
    db.commit()
    db.refresh(row)
    log_audit(db, actor=user.email, actor_role=user.role, action="upload_document", target=row.name,
              after={"id": row.id, "name": row.name, "category": row.category, "patient_id": row.patient_id, "status": row.status})
    return schemas.MutationResult(ok=True, data=_row_to_schema(row), message="Document uploaded")


def _guess_category(name: str) -> str:
    lowered = name.lower()
    for key in ("mri", "ct", "pet", "biopsy", "blood"):
        if key in lowered:
            return key.upper() if key in ("mri", "ct", "pet") else key.capitalize()
    return "Blood"


@router.get("/{doc_id}/versions", response_model=list[schemas.DocumentVersion])
def versions(doc_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    doc = db.get(models.DocumentRecord, doc_id)
    if doc:
        _assert_document_readable(db, doc, user)
    rows = db.query(models.DocumentVersion).filter(models.DocumentVersion.document_id == doc_id).order_by(models.DocumentVersion.version.desc()).all()
    return [schemas.DocumentVersion(version=r.version, date=r.date, author=r.author, note=r.note) for r in rows]


@router.get("/{doc_id}/links", response_model=list[schemas.DocumentRecord])
def links(doc_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    doc = db.get(models.DocumentRecord, doc_id)
    if not doc or not doc.patient_id:
        return []
    _assert_document_readable(db, doc, user)
    rows = db.query(models.DocumentRecord).filter(models.DocumentRecord.patient_id == doc.patient_id, models.DocumentRecord.id != doc_id).all()
    return [_row_to_schema(r) for r in rows]


@router.get("/{doc_id}/timeline", response_model=list[schemas.TimelineEvent])
def timeline(doc_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    doc = db.get(models.DocumentRecord, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    _assert_document_readable(db, doc, user)
    versions_rows = db.query(models.DocumentVersion).filter(models.DocumentVersion.document_id == doc_id).order_by(models.DocumentVersion.version.desc()).all()
    return [
        schemas.TimelineEvent(date=v.date, title=f"Version {v.version} uploaded", detail=v.note, kind="note")
        for v in versions_rows
    ]
