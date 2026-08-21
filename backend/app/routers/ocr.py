"""OCR endpoints.

No image/PDF OCR engine is wired in yet (documents are stored as metadata
only — see docs/backend-integration-report.md). `extract` runs a
deterministic, category-aware field template against the *real* stored
document record and persists the result, so repeated calls return the same
DB-backed rows rather than a fresh random payload each time. Swap
`_extract_fields` for a real OCR/NLP call (e.g. Tesseract, Textract, an LLM
vision call) once scanned documents are actually stored.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.deps import log_audit, require_roles
from app.routers.documents import _assert_document_readable

router = APIRouter(prefix="/ocr", tags=["ocr"])

_clinical_staff = require_roles("doctor", "admin")

_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "MRI": [("Modality", "MRI"), ("Region", "Breast, bilateral"), ("Finding", "Pending radiologist review")],
    "CT": [("Modality", "CT"), ("Region", "Chest/Abdomen"), ("Finding", "Pending radiologist review")],
    "PET": [("Modality", "PET-CT"), ("Region", "Whole body"), ("Finding", "Pending radiologist review")],
    "Biopsy": [("Specimen type", "Core needle biopsy"), ("Histology", "Pending pathology"), ("Grade", "Pending")],
    "Blood": [("Panel", "CBC + Tumor markers"), ("CA 15-3", "Pending"), ("CEA", "Pending")],
}


@router.post("/{document_id}/extract", response_model=schemas.OcrExtraction)
def extract(document_id: str, db: Session = Depends(get_db), user: models.User = Depends(_clinical_staff)):
    doc = db.get(models.DocumentRecord, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    _assert_document_readable(db, doc, user)

    before_status = doc.status
    existing = db.query(models.OcrFieldRow).filter(models.OcrFieldRow.document_id == document_id).all()
    if not existing:
        for field, value in _TEMPLATES.get(doc.category, [("Document name", doc.name), ("Category", doc.category)]):
            db.add(models.OcrFieldRow(document_id=document_id, field=field, value=value, confidence=0.78))
        doc.status = "Needs review"
        db.commit()
        existing = db.query(models.OcrFieldRow).filter(models.OcrFieldRow.document_id == document_id).all()

    log_audit(db, actor=user.email, actor_role=user.role, action="ocr_extract", target=doc.name,
              before={"status": before_status}, after={"status": doc.status, "field_count": len(existing)})
    return schemas.OcrExtraction(
        document_id=document_id, model="ocr-heuristic-v1",
        extracted_at=datetime.now(timezone.utc).isoformat(),
        fields=[schemas.OcrField(field=f.field, value=f.value, confidence=f.confidence) for f in existing],
    )


@router.get("/{document_id}/fields", response_model=list[schemas.OcrField])
def fields(document_id: str, db: Session = Depends(get_db), user: models.User = Depends(_clinical_staff)):
    doc = db.get(models.DocumentRecord, document_id)
    if doc:
        _assert_document_readable(db, doc, user)
    rows = db.query(models.OcrFieldRow).filter(models.OcrFieldRow.document_id == document_id).all()
    return [schemas.OcrField(field=r.field, value=r.value, confidence=r.confidence) for r in rows]


@router.post("/{document_id}/approve", response_model=schemas.MutationResult)
def approve(document_id: str, payload: schemas.OcrFieldApprovalRequest, db: Session = Depends(get_db), user: models.User = Depends(_clinical_staff)):
    doc = db.get(models.DocumentRecord, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    _assert_document_readable(db, doc, user)
    before_status = doc.status
    db.query(models.OcrFieldRow).filter(models.OcrFieldRow.document_id == document_id).delete()
    for f in payload.fields:
        db.add(models.OcrFieldRow(document_id=document_id, field=f.field, value=f.value, confidence=f.confidence, approved=True))
    doc.status = "Verified"
    db.commit()
    log_audit(db, actor=user.email, actor_role=user.role, action="ocr_approve", target=doc.name,
              before={"status": before_status}, after={"status": doc.status, "approved_field_count": len(payload.fields)})
    return schemas.MutationResult(ok=True, message="OCR fields approved")


@router.post("/{document_id}/reject", response_model=schemas.MutationResult)
def reject(document_id: str, payload: schemas.OcrRejectInput, db: Session = Depends(get_db), user: models.User = Depends(_clinical_staff)):
    doc = db.get(models.DocumentRecord, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    _assert_document_readable(db, doc, user)
    before_status = doc.status
    doc.status = "Needs review"
    db.query(models.OcrFieldRow).filter(models.OcrFieldRow.document_id == document_id).update({"rejected": True})
    db.commit()
    log_audit(db, actor=user.email, actor_role=user.role, action="ocr_reject", target=f"{doc.name}: {payload.reason}",
              before={"status": before_status}, after={"status": doc.status})
    return schemas.MutationResult(ok=True, message="OCR extraction rejected")
