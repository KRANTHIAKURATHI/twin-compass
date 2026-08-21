"""Business logic for model predictions: running a prediction, persisting it,
recomputing the patient's derived risk, and explaining it.

This is the single place a prediction row is created. Previously three call
sites created `PredictionRun` rows independently (this router, `TwinService`
and patient-create), each with its own hardcoded model name.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.exceptions import NotFoundError
from app.deps import assert_patient_readable, log_audit
from app.ml.interface import PredictionModel, get_prediction_model, patient_to_model_fields
from app.repositories.prediction_repository import PredictionRepository

#: Honest framing for the explainability endpoints. Without a stored snapshot of
#: the feature vector, attributions can only be recomputed from the patient's
#: current record — so an explanation is reproducible for an unchanged patient,
#: not historically faithful to an older prediction.
_EXPLAIN_COMPUTED_FROM = "current patient record"
_EXPLAIN_CAVEAT = (
    "Feature attributions are recomputed live from the patient's current "
    "recorded fields, not from a stored snapshot taken when an earlier "
    "prediction was made. If the record has changed since, this explains the "
    "present state rather than that earlier prediction. Estimates are for "
    "decision support and are not clinically validated."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_to_schema(r: models.PredictionRun) -> schemas.PredictionRun:
    return schemas.PredictionRun(
        id=r.id, date=r.date, twin_version=r.twin_version, model=r.model, survival=r.survival,
        recurrence=r.recurrence, response=r.response, confidence=r.confidence, status=r.status,
    )


class PredictionService:
    def __init__(self, db: Session, model: PredictionModel | None = None):
        self.db = db
        self.repo = PredictionRepository(db)
        self.model = model or get_prediction_model()

    def model_metadata(self) -> schemas.ModelMetadata:
        return schemas.ModelMetadata(**{
            "name": self.model.metadata.name,
            "version": self.model.metadata.version,
            "dataset_name": self.model.metadata.dataset_name,
            "trained_at": self.model.metadata.trained_at,
            "model_type": self.model.metadata.model_type,
            "is_validated": self.model.metadata.is_validated,
            "disclaimer": self.model.metadata.disclaimer,
        })

    def _readable_patient(self, patient_id: str, user: models.User) -> models.Patient:
        p = self.repo.get_patient(patient_id)
        if not p:
            raise NotFoundError("Patient not found")
        assert_patient_readable(p, user)
        return p

    def get_latest(self, patient_id: str, user: models.User) -> schemas.PredictionRun | None:
        self._readable_patient(patient_id, user)
        run = self.repo.latest(patient_id)
        return _run_to_schema(run) if run else None

    def get_history(self, patient_id: str, user: models.User) -> list[schemas.PredictionRun]:
        self._readable_patient(patient_id, user)
        return [_run_to_schema(r) for r in self.repo.history(patient_id)]

    def get_confidence_trend(self, patient_id: str, user: models.User) -> list[schemas.ConfidencePoint]:
        self._readable_patient(patient_id, user)
        return [
            schemas.ConfidencePoint(date=r.date, confidence=r.confidence)
            for r in self.repo.history(patient_id, ascending=True)
        ]

    def explain(self, patient_id: str, user: models.User, top_n: int = 8) -> list[schemas.FeatureImportance]:
        p = self._readable_patient(patient_id, user)
        rows = self.model.explain(patient_to_model_fields(p), top_n=top_n)
        return [schemas.FeatureImportance(**r) for r in rows]

    def explain_summary(self, patient_id: str, user: models.User, top_n: int = 8) -> schemas.ExplanationSummary:
        return schemas.ExplanationSummary(
            patient_id=patient_id,
            features=self.explain(patient_id, user, top_n=top_n),
            model=self.model_metadata(),
            computed_from=_EXPLAIN_COMPUTED_FROM,
            caveat=_EXPLAIN_CAVEAT,
        )

    def run_for_patient(
        self,
        patient_id: str,
        user: models.User,
        twin_version: str | None = None,
        commit: bool = True,
    ) -> models.PredictionRun:
        """Runs the model, stores the result, and updates the patient's derived
        risk/survival so the patient row and the prediction never disagree.

        `commit=False` lets a caller already inside a transaction (e.g.
        `TwinService.resync`, which also writes a version and a snapshot) fold
        this into its own commit.
        """
        p = self._readable_patient(patient_id, user)
        result = self.model.predict(patient_to_model_fields(p))
        version = twin_version or self.repo.latest_twin_version(patient_id)

        row = models.PredictionRun(
            patient_id=patient_id, twin_version=version, model=self.model.metadata.name,
            survival=result["survival"], recurrence=result["recurrence"], response=result["response"],
            confidence=result["confidence"], status=result["status"],
        )
        p.risk = result["risk"]
        p.survival_probability = result["survival"]
        p.last_updated = _now()
        self.repo.add(row)

        if commit:
            try:
                self.db.commit()
            except SQLAlchemyError:
                # Leave the session usable and let the global handler turn this
                # into a generic 500 rather than leaking driver detail.
                self.db.rollback()
                raise
            self.db.refresh(row)
            log_audit(
                self.db, actor=user.email, actor_role=user.role, action="run_prediction", target=p.name,
                after={"patient_id": patient_id, "twin_version": row.twin_version, "model": row.model,
                       "survival": row.survival, "recurrence": row.recurrence, "response": row.response,
                       "confidence": row.confidence, "status": row.status},
            )
        return row

    def run_and_serialize(self, patient_id: str, user: models.User) -> schemas.PredictionRun:
        return _run_to_schema(self.run_for_patient(patient_id, user))
