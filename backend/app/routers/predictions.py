"""Prediction endpoints. Thin: authorization is expressed by the dependency,
everything else delegates to PredictionService.

These are model-derived, decision-support estimates from a development model
trained on a public diagnostic dataset. They are not clinically validated
prognoses and do not replace clinical judgement — every response carries the
model's own provenance so a caller can see that.
"""

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.deps import get_current_user, require_roles
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])

_clinical_staff = require_roles("doctor", "admin")


def _service(db: Session = Depends(get_db)) -> PredictionService:
    return PredictionService(db)


@router.get("/{patient_id}", response_model=schemas.PredictionRun | None)
def for_patient(
    patient_id: str,
    svc: PredictionService = Depends(_service),
    user: models.User = Depends(get_current_user),
):
    """Most recent stored prediction for this patient, or null if none exists."""
    return svc.get_latest(patient_id, user)


@router.get("/{patient_id}/history", response_model=list[schemas.PredictionRun])
def history(
    patient_id: str,
    svc: PredictionService = Depends(_service),
    user: models.User = Depends(get_current_user),
):
    return svc.get_history(patient_id, user)


@router.get("/{patient_id}/confidence-trend", response_model=list[schemas.ConfidencePoint])
def confidence_trend(
    patient_id: str,
    svc: PredictionService = Depends(_service),
    user: models.User = Depends(get_current_user),
):
    return svc.get_confidence_trend(patient_id, user)


@router.get(
    "/{patient_id}/explainability",
    response_model=list[schemas.FeatureImportance],
    description=(
        "Model feature attributions for this patient, derived from their real "
        "recorded fields (stage, tumour size, grade, Ki-67, nodes involved, "
        "receptor statuses, age). Recomputed from the current record, not from "
        "a snapshot taken at prediction time."
    ),
)
def explain(
    patient_id: str,
    svc: PredictionService = Depends(_service),
    user: models.User = Depends(get_current_user),
):
    return svc.explain(patient_id, user)


@router.get(
    "/{patient_id}/explainability/summary",
    response_model=schemas.ExplanationSummary,
    description=(
        "The same attributions plus model provenance and an explicit statement "
        "of what the explanation does and does not cover. Additive; the plain "
        "`/explainability` route is unchanged."
    ),
)
def explain_summary(
    patient_id: str,
    svc: PredictionService = Depends(_service),
    user: models.User = Depends(get_current_user),
):
    return svc.explain_summary(patient_id, user)


@router.post(
    "/run",
    response_model=schemas.MutationResult[schemas.PredictionRun],
    description=(
        "Runs the model against the patient's current record, stores the result "
        "and updates the patient's derived risk. Produces a predicted estimate "
        "for decision support, not a diagnosis."
    ),
)
def run(
    patient_id: str = Body(..., embed=True, alias="patientId"),
    svc: PredictionService = Depends(_service),
    user: models.User = Depends(_clinical_staff),
):
    return schemas.MutationResult(
        ok=True, message="Prediction complete", data=svc.run_and_serialize(patient_id, user)
    )
