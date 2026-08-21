from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models
from app.core.database import get_db
from app.deps import get_current_user

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def global_search(q: str = Query(..., min_length=1), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if user.role == "researcher":
        # Research role must never see patient-identifying search results.
        return {"patients": [], "documents": [], "reports": []}

    like = f"%{q}%"
    patients_query = db.query(models.Patient).filter(models.Patient.name.ilike(like))
    documents_query = db.query(models.DocumentRecord).filter(models.DocumentRecord.name.ilike(like))
    reports_query = db.query(models.SavedReport).filter(models.SavedReport.title.ilike(like))

    if user.role == "patient":
        own = db.query(models.Patient).filter(models.Patient.email == user.email).first()
        own_id = own.id if own else None
        patients_query = patients_query.filter(models.Patient.id == own_id)
        documents_query = documents_query.filter(models.DocumentRecord.patient_id == own_id)
        reports_query = reports_query.filter(models.SavedReport.patient_id == own_id)

    patients = patients_query.limit(10).all()
    documents = documents_query.limit(10).all()
    reports = reports_query.limit(10).all()

    return {
        "patients": [{"id": p.id, "name": p.name, "type": "patient"} for p in patients],
        "documents": [{"id": d.id, "name": d.name, "type": "document"} for d in documents],
        "reports": [{"id": r.id, "name": r.title, "type": "report"} for r in reports],
    }
