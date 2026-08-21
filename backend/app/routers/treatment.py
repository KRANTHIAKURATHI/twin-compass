"""Treatment plan endpoint. Thin: delegates to TreatmentPlanService, which also
owns the regimen reference data so a promoted simulation and a freshly created
plan describe the same regimen the same way."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.deps import get_current_user
from app.services.treatment_service import TreatmentPlanService

router = APIRouter(prefix="/patients", tags=["treatment"])


@router.get(
    "/{patient_id}/treatment-plan",
    response_model=schemas.TreatmentPlan,
    description=(
        "The patient's active plan, created on first read from their current "
        "treatment if none exists. Listed side effects are the regimen's "
        "expected profile, not adverse events observed in this patient."
    ),
)
def plan(
    patient_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return TreatmentPlanService(db).get_or_create_plan(patient_id, user)
