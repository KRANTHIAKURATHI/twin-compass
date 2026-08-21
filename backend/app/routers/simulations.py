"""Treatment simulation endpoints. Thin: everything delegates to
SimulationService.

Simulations compare *hypothetical* regimen outcomes. Nothing returned here is an
observed result, and adopting a regimen ("promote") records a clinician's
decision rather than making one.
"""

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.deps import get_current_user, require_roles
from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/simulations", tags=["simulations"])

_clinical_staff = require_roles("doctor", "admin")


def _service(db: Session = Depends(get_db)) -> SimulationService:
    return SimulationService(db)


@router.get("", response_model=list[schemas.SimulationRun])
def list_simulations(
    svc: SimulationService = Depends(_service),
    user: models.User = Depends(get_current_user),
):
    """Saved simulations. A `patient`-role caller sees only their own."""
    return svc.list_simulations(user)


@router.get("/{sim_id}", response_model=schemas.SimulationRun | None)
def get_simulation(
    sim_id: str,
    svc: SimulationService = Depends(_service),
    user: models.User = Depends(get_current_user),
):
    return svc.get_simulation(sim_id, user)


@router.post(
    "/run",
    description=(
        "Simulates every known regimen for this patient and returns the "
        "comparison. Persists nothing — use POST /simulations to save one."
    ),
)
def run_simulation(
    payload: dict = Body(default_factory=dict),
    svc: SimulationService = Depends(_service),
    user: models.User = Depends(_clinical_staff),
):
    return svc.run_ephemeral(payload.get("patientId"), user)


@router.post(
    "",
    response_model=schemas.MutationResult[schemas.SimulationRun],
    description="Saves a simulated scenario against an explicit patient. `patient_id` is required.",
)
def save_simulation(
    draft: schemas.ScenarioDraft,
    patient_id: str | None = None,
    svc: SimulationService = Depends(_service),
    user: models.User = Depends(_clinical_staff),
):
    return schemas.MutationResult(ok=True, data=svc.save(patient_id, draft, user), message="Scenario saved")


@router.post("/{sim_id}/duplicate", response_model=schemas.MutationResult[schemas.SimulationRun])
def duplicate(
    sim_id: str,
    svc: SimulationService = Depends(_service),
    user: models.User = Depends(_clinical_staff),
):
    return schemas.MutationResult(ok=True, data=svc.duplicate(sim_id, user), message="Scenario duplicated")


@router.get(
    "/{sim_id}/explainability",
    response_model=schemas.SimulationExplanation,
    description=(
        "Why this regimen's simulated outcome differs from active surveillance, "
        "expressed as shifts in the model's own feature attributions for this "
        "patient. Simulated comparison, not an observed outcome."
    ),
)
def explainability(
    sim_id: str,
    svc: SimulationService = Depends(_service),
    user: models.User = Depends(get_current_user),
):
    return svc.explain(sim_id, user)


@router.post(
    "/{sim_id}/promote",
    response_model=schemas.MutationResult,
    description=(
        "Records a clinician's decision to adopt this regimen and materializes "
        "the corresponding treatment plan. The decision is the clinician's; this "
        "endpoint only records it."
    ),
)
def promote(
    sim_id: str,
    payload: dict | None = None,
    svc: SimulationService = Depends(_service),
    user: models.User = Depends(_clinical_staff),
):
    regimen = svc.promote(sim_id, (payload or {}).get("notes"), user)
    return schemas.MutationResult(ok=True, message=f"{regimen} promoted to treatment plan")
