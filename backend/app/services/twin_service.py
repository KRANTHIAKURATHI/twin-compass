"""Business logic for the Digital Twin: resync/restore/archive side effects
(new TwinVersion/TwinSnapshotRow/PredictionRun rows, timeline events, audit
logging). Routers call into this and stay thin; data access goes through
TwinRepository."""

from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.exceptions import NotFoundError
from app.deps import assert_patient_readable, log_audit
from app.ml.interface import PredictionModel, get_prediction_model
from app.repositories.twin_repository import TwinRepository
from app.serializers import patient_to_schema
from app.services.prediction_service import PredictionService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TwinService:
    def __init__(self, db: Session, model: PredictionModel | None = None):
        self.db = db
        self.repo = TwinRepository(db)
        #: Injectable so tests can substitute a fake without loading the joblib
        #: artifact; defaults to the process-wide model.
        self.model = model or get_prediction_model()
        #: Prediction rows and the patient's risk writeback are owned by one
        #: service, shared here rather than duplicated.
        self.predictions = PredictionService(db, model=self.model)

    def _assert_readable(self, p: models.Patient, user: models.User) -> None:
        """Delegates to the single shared ownership rule in `app.deps`."""
        assert_patient_readable(p, user)

    def list_twins(self, user: models.User) -> list[schemas.Patient]:
        patients = self.repo.list_patients()
        if user.role == "patient":
            patients = [p for p in patients if p.email == user.email]
        return [patient_to_schema(p) for p in patients]

    def list_versions(self, patient_id: str, user: models.User) -> list[schemas.TwinVersion]:
        p = self.repo.get_patient(patient_id)
        if not p:
            raise NotFoundError("Patient not found")
        self._assert_readable(p, user)
        rows = self.repo.list_versions(patient_id)
        return [
            schemas.TwinVersion(version=r.version, created_at=r.created_at, status=r.status, author=r.author,
                                 summary=r.summary, tumor_size_mm=r.tumor_size_mm, survival=r.survival,
                                 risk=r.risk, model=r.model)
            for r in rows
        ]

    def list_snapshots(self, patient_id: str, user: models.User) -> list[schemas.TwinSnapshot]:
        p = self.repo.get_patient(patient_id)
        if not p:
            raise NotFoundError("Patient not found")
        self._assert_readable(p, user)
        rows = self.repo.list_snapshots(patient_id)
        return [schemas.TwinSnapshot(id=r.id, version=r.version, taken_at=r.taken_at, trigger=r.trigger, size=r.size) for r in rows]

    def resync(self, patient_id: str, user: models.User) -> str:
        p = self.repo.get_patient(patient_id)
        if not p:
            raise NotFoundError("Patient not found")
        self._assert_readable(p, user)
        p.twin_status = "Recalculating"
        self.db.commit()

        version = self.repo.next_version_label(patient_id)
        # PredictionService owns prediction creation and the risk/survival
        # writeback; `commit=False` folds its row into this resync's single
        # commit so a failure can't leave a version without its prediction.
        run = self.predictions.run_for_patient(patient_id, user, twin_version=version, commit=False)
        p.twin_status = "Synced"
        p.last_updated = _now()

        self.repo.add(models.TwinVersion(
            patient_id=patient_id, version=version, author=user.name,
            summary=f"Resynced from latest clinical data by {user.name}.",
            tumor_size_mm=p.tumor_size_mm, survival=p.survival_probability, risk=p.risk,
            model=self.model.metadata.name, snapshot=patient_to_schema(p).model_dump(by_alias=False),
        ))
        self.repo.add(models.TwinSnapshotRow(patient_id=patient_id, version=version, trigger="manual resync", size="12 KB"))
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        log_audit(self.db, actor=user.email, actor_role=user.role, action="resync_twin", target=p.name,
                  after={"patient_id": patient_id, "version": version, "risk": p.risk,
                         "survival": p.survival_probability, "confidence": run.confidence,
                         "model": self.model.metadata.name})
        return version

    def get_state(self, patient_id: str, user: models.User) -> schemas.TwinState:
        """The patient's current derived twin state.

        Composed at read time from the live patient record, the latest twin
        version and the latest stored prediction. There is no separate stored
        twin blob — `derived_at` is the time of this request, which is why the
        response says so rather than implying a persisted snapshot.
        """
        p = self.repo.get_patient(patient_id)
        if not p:
            raise NotFoundError("Patient not found")
        self._assert_readable(p, user)

        latest_version = self.repo.latest_version(patient_id)
        latest_run = self.predictions.get_latest(patient_id, user)
        m = self.model.metadata

        return schemas.TwinState(
            patient_id=p.id,
            patient_name=p.name,
            twin_status=p.twin_status,
            version=latest_version.version if latest_version else "v1",
            version_created_at=latest_version.created_at if latest_version else p.last_updated,
            last_updated=p.last_updated,
            stage=p.stage,
            tumor_size_mm=p.tumor_size_mm,
            grade=p.grade,
            ki67=p.ki67,
            nodes_involved=p.nodes_involved,
            er_status=p.er_status,
            pr_status=p.pr_status,
            her2_status=p.her2_status,
            age=p.age,
            current_treatment=p.current_treatment,
            risk=p.risk,
            survival_probability=p.survival_probability,
            latest_prediction=latest_run,
            model=schemas.ModelMetadata(
                name=m.name, version=m.version, dataset_name=m.dataset_name, trained_at=m.trained_at,
                model_type=m.model_type, is_validated=m.is_validated, disclaimer=m.disclaimer,
            ),
            derived_at=_now(),
            caveat=(
                "Derived view composed from the current patient record, the latest "
                "twin version and the latest stored prediction at request time. "
                "Model outputs are decision-support estimates and are not "
                "clinically validated."
            ),
        )

    def restore(self, patient_id: str, version: str, user: models.User) -> None:
        tv = self.repo.get_version(patient_id, version)
        p = self.repo.get_patient(patient_id)
        if not tv or not p:
            raise NotFoundError("Twin version not found")
        self._assert_readable(p, user)
        snap = tv.snapshot or {}
        for field in ("stage", "tumor_size_mm", "er_status", "pr_status", "her2_status", "ki67", "grade",
                      "nodes_involved", "current_treatment", "status", "risk", "survival_probability"):
            if field in snap:
                setattr(p, field, snap[field])
        p.twin_status = "Synced"
        p.last_updated = _now()
        self.repo.add(models.TimelineEvent(
            patient_id=patient_id, date=p.last_updated, title=f"Restored to {version}",
            detail=f"Digital twin restored by {user.name}.", kind="note",
        ))
        self.db.commit()
        log_audit(self.db, actor=user.email, actor_role=user.role, action="restore_twin", target=f"{p.name}:{version}")

    def archive(self, patient_id: str, user: models.User) -> None:
        p = self.repo.get_patient(patient_id)
        if not p:
            raise NotFoundError("Patient not found")
        self._assert_readable(p, user)
        p.twin_status = "Stale"
        latest = self.repo.latest_version(patient_id)
        if latest:
            latest.status = "Archived"
        self.db.commit()
        log_audit(self.db, actor=user.email, actor_role=user.role, action="archive_twin", target=p.name)
