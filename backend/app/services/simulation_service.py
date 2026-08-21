"""Business logic for treatment simulations.

Every number here is *simulated*: the model is re-run on the patient's severity
after applying a regimen's documented efficacy profile. Nothing in a simulation
is an observed outcome, and nothing is a hardcoded per-scenario result.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.exceptions import NotFoundError, ValidationError
from app.deps import assert_patient_readable, log_audit
from app.ml.interface import (
    PredictionModel,
    explain_delta,
    get_prediction_model,
    patient_to_model_fields,
)
from app.ml.regimens import REGIMENS
from app.repositories.simulation_repository import SimulationRepository

_SIM_CAVEAT = (
    "Simulated comparison, not an observed outcome. Each scenario re-runs the "
    "model on the patient's recorded fields after applying that regimen's "
    "documented relative efficacy; results are decision-support estimates and "
    "are not clinically validated."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_schema(r: models.SimulationRun) -> schemas.SimulationRun:
    return schemas.SimulationRun(
        id=r.id, date=r.date, patient=r.patient_name, patient_id=r.patient_id,
        twin_version=r.twin_version, model=r.model, selected=r.selected,
        compared=r.compared or [], decision=r.decision, decided_by=r.decided_by,
        notes=r.notes or "", survival=r.survival, response=r.response, confidence=r.confidence,
    )


class SimulationService:
    def __init__(self, db: Session, model: PredictionModel | None = None):
        self.db = db
        self.repo = SimulationRepository(db)
        self.model = model or get_prediction_model()

    # ----------------------------------------------------------- internals --

    def _commit(self) -> None:
        """Guarded commit: roll back on failure so the session stays usable and
        the global handler can return a generic 500."""
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def _readable_patient(self, patient_id: str, user: models.User) -> models.Patient:
        p = self.repo.get_patient(patient_id)
        if not p:
            raise NotFoundError("Patient not found")
        assert_patient_readable(p, user)
        return p

    def _readable_simulation(self, sim_id: str, user: models.User) -> models.SimulationRun:
        row = self.repo.get(sim_id)
        if not row:
            raise NotFoundError("Simulation not found")
        if row.patient_id:
            p = self.repo.get_patient(row.patient_id)
            if p:
                assert_patient_readable(p, user)
        return row

    def _model_metadata(self) -> schemas.ModelMetadata:
        m = self.model.metadata
        return schemas.ModelMetadata(
            name=m.name, version=m.version, dataset_name=m.dataset_name, trained_at=m.trained_at,
            model_type=m.model_type, is_validated=m.is_validated, disclaimer=m.disclaimer,
        )

    def _latest_twin_version(self, patient_id: str) -> str:
        tv = (
            self.db.query(models.TwinVersion)
            .filter(models.TwinVersion.patient_id == patient_id)
            .order_by(models.TwinVersion.created_at.desc())
            .first()
        )
        return tv.version if tv else "v1"

    # ---------------------------------------------------------------- reads --

    def list_simulations(self, user: models.User) -> list[schemas.SimulationRun]:
        rows = (
            self.repo.list_for_patient_email(user.email)
            if user.role == "patient"
            else self.repo.list_all()
        )
        return [_row_to_schema(r) for r in rows]

    def get_simulation(self, sim_id: str, user: models.User) -> schemas.SimulationRun | None:
        row = self.repo.get(sim_id)
        if not row:
            return None
        return _row_to_schema(self._readable_simulation(sim_id, user))

    def run_ephemeral(self, patient_id: str | None, user: models.User) -> dict:
        """Scenario comparison for the simulator UI. Persists nothing."""
        if not patient_id:
            raise ValidationError("patientId is required")
        p = self._readable_patient(patient_id, user)
        scenarios = self.model.simulate_all(patient_to_model_fields(p))
        return {
            "patientId": patient_id,
            "scenarios": [
                schemas.Scenario(
                    id=str(uuid.uuid4()), name=s["regimen"], regimen=s["regimen"],
                    predicted_response=s["predicted_response"], tumor_change=s["tumor_change"],
                    risk=s["risk"], confidence=s["confidence"], survival5y=s["survival5y"],
                    side_effect_risk=s["side_effect_risk"], recovery_weeks=s["recovery_weeks"],
                    recommended=s["recommended"],
                ).model_dump(by_alias=True)
                for s in scenarios
            ],
        }

    def explain(self, sim_id: str, user: models.User, top_n: int = 8) -> schemas.SimulationExplanation:
        """Why this regimen's simulated outcome differs from doing nothing.

        The baseline is `Active Surveillance` — the closest thing the regimen set
        has to "no active treatment" — so the delta isolates the regimen's
        modelled effect rather than comparing against an arbitrary alternative.
        """
        row = self._readable_simulation(sim_id, user)
        p = self._readable_patient(row.patient_id, user)
        fields = patient_to_model_fields(p)

        baseline = self.model.simulate(fields, "Active Surveillance")
        scenario = self.model.simulate(fields, row.selected)

        # The scenario's modelled effect is a *reduced tumour burden*, so the
        # delta is computed between the patient's real fields and the same
        # fields with the simulated tumour change applied.
        scenario_fields = dict(fields)
        scenario_fields["tumorSizeMm"] = max(
            float(fields.get("tumorSizeMm") or 0) + float(scenario["tumor_change"]), 0.0
        )

        return schemas.SimulationExplanation(
            simulation_id=row.id,
            patient_id=row.patient_id,
            regimen=row.selected,
            baseline_survival=baseline["survival5y"],
            simulated_survival=scenario["survival5y"],
            features=[schemas.DeltaFeature(**d) for d in explain_delta(fields, scenario_fields, self.model, top_n=top_n)],
            model=self._model_metadata(),
            caveat=_SIM_CAVEAT,
        )

    # --------------------------------------------------------------- writes --

    def save(self, patient_id: str | None, draft: schemas.ScenarioDraft, user: models.User) -> schemas.SimulationRun:
        if not patient_id:
            # Previously this fell back to `db.query(Patient).first()`, silently
            # attaching the simulation to an arbitrary patient.
            raise ValidationError("patient_id is required")
        p = self._readable_patient(patient_id, user)
        result = self.model.simulate_all(patient_to_model_fields(p))
        match = next((s for s in result if s["regimen"] == draft.regimen), result[0])

        row = models.SimulationRun(
            patient_id=p.id, patient_name=p.name, twin_version=self._latest_twin_version(p.id),
            model=self.model.metadata.name, selected=draft.regimen,
            compared=[s["regimen"] for s in result if s["regimen"] != draft.regimen],
            decision="Under review", decided_by=user.name, notes=draft.notes,
            survival=match["survival5y"], response=match["predicted_response"] / 100,
            confidence=match["confidence"], scenarios=result,
        )
        self.repo.add(row)
        self._commit()
        self.db.refresh(row)
        log_audit(self.db, actor=user.email, actor_role=user.role, action="save_simulation", target=p.name,
                  after={"id": row.id, "patient_id": row.patient_id, "selected": row.selected,
                         "decision": row.decision, "model": row.model})
        return _row_to_schema(row)

    def duplicate(self, sim_id: str, user: models.User) -> schemas.SimulationRun:
        original = self._readable_simulation(sim_id, user)
        clone = models.SimulationRun(
            patient_id=original.patient_id, patient_name=original.patient_name,
            twin_version=original.twin_version, model=original.model, selected=original.selected,
            compared=original.compared, decision="Under review", decided_by=user.name,
            notes=f"Duplicated from {original.id}", survival=original.survival,
            response=original.response, confidence=original.confidence, scenarios=original.scenarios,
        )
        self.repo.add(clone)
        self._commit()
        self.db.refresh(clone)
        log_audit(self.db, actor=user.email, actor_role=user.role, action="duplicate_simulation",
                  target=original.patient_name or original.selected,
                  before={"id": original.id, "decision": original.decision},
                  after={"id": clone.id, "patient_id": clone.patient_id, "selected": clone.selected,
                         "decision": clone.decision})
        return _row_to_schema(clone)

    def promote(self, sim_id: str, notes: str | None, user: models.User) -> str:
        """Records a clinician's decision to adopt a simulated regimen.

        The clinician makes this decision; promoting only records it and
        materializes the corresponding treatment plan row.
        """
        row = self._readable_simulation(sim_id, user)
        before = {"decision": row.decision, "notes": row.notes}
        row.decision = "Promoted to plan"
        if notes is not None:
            row.notes = notes

        profile = REGIMENS.get(row.selected, {})
        plan = self.repo.get_plan(row.patient_id)
        if not plan:
            plan = models.TreatmentPlanRow(patient_id=row.patient_id)
            self.repo.add(plan)
        plan.regimen = row.selected
        plan.cycle = 1
        plan.total_cycles = max(int(profile.get("recovery_weeks", 12) / 3), 1)
        plan.adherence = 1.0

        patient = self.repo.get_patient(row.patient_id)
        if patient:
            patient.current_treatment = row.selected
            patient.last_updated = _now()

        self._commit()
        log_audit(self.db, actor=user.email, actor_role=user.role, action="promote_simulation",
                  target=row.selected, before=before,
                  after={"decision": row.decision, "patient_id": row.patient_id,
                         "regimen": plan.regimen, "total_cycles": plan.total_cycles})
        return row.selected
