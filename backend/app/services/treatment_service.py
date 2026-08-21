"""Business logic for the patient's active treatment plan.

No repository: this is a single read plus a lazy insert, which doesn't justify
one. The regimen reference data (medications, side-effect profiles) lives here
rather than in the router so `SimulationService.promote` and the plan endpoint
agree on what a regimen entails.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.exceptions import NotFoundError
from app.deps import assert_patient_readable
from app.ml.regimens import REGIMENS

#: Standard regimen compositions. Documented oncology dosing conventions, not
#: per-patient prescriptions — a clinician sets the actual orders.
MEDICATIONS_BY_REGIMEN: dict[str, list[dict]] = {
    "AC-T (Doxorubicin/Cyclophosphamide + Paclitaxel)": [
        {"name": "Doxorubicin", "dose": "60 mg/m^2 IV", "schedule": "Every 2 weeks x4"},
        {"name": "Paclitaxel", "dose": "80 mg/m^2 IV", "schedule": "Weekly x12"},
    ],
    "TC (Docetaxel/Cyclophosphamide)": [
        {"name": "Docetaxel", "dose": "75 mg/m^2 IV", "schedule": "Every 3 weeks x4"},
        {"name": "Cyclophosphamide", "dose": "600 mg/m^2 IV", "schedule": "Every 3 weeks x4"},
    ],
    "Endocrine Therapy (Tamoxifen/AI)": [
        {"name": "Tamoxifen", "dose": "20 mg PO", "schedule": "Daily x5 years"},
    ],
    "HER2-Targeted Therapy (Trastuzumab + Pertuzumab)": [
        {"name": "Trastuzumab", "dose": "6 mg/kg IV", "schedule": "Every 3 weeks x17"},
        {"name": "Pertuzumab", "dose": "420 mg IV", "schedule": "Every 3 weeks x17"},
    ],
    "Neoadjuvant Chemotherapy + Surgery": [
        {"name": "Per regimen", "dose": "As prescribed", "schedule": "Pre-operative course"},
    ],
    "Active Surveillance": [],
}

#: Anticipated side effects banded by the regimen's toxicity parameter. These
#: are expected-profile advisories, not observed adverse events for this patient.
_SIDE_EFFECTS_BY_TOXICITY = [
    (0.6, [{"name": "Neutropenia", "grade": "Grade 2", "advice": "Monitor CBC weekly; report fever immediately."}]),
    (0.3, [{"name": "Fatigue", "grade": "Grade 1", "advice": "Prioritize rest; light activity as tolerated."}]),
    (0.0, [{"name": "Mild nausea", "grade": "Grade 1", "advice": "Take antiemetic as prescribed with meals."}]),
]


def side_effects_for(regimen: str) -> list[dict]:
    toxicity = REGIMENS.get(regimen, {}).get("toxicity", 0.2)
    for threshold, effects in _SIDE_EFFECTS_BY_TOXICITY:
        if toxicity >= threshold:
            return effects
    return []


def cycles_for(regimen: str) -> int:
    profile = REGIMENS.get(regimen, {})
    return max(int(profile.get("recovery_weeks", 12) / 3), 1)


class TreatmentPlanService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_plan(self, patient_id: str, user: models.User) -> schemas.TreatmentPlan:
        patient = self.db.get(models.Patient, patient_id)
        if not patient or patient.deleted_at is not None:
            raise NotFoundError("Patient not found")
        assert_patient_readable(patient, user)

        row = (
            self.db.query(models.TreatmentPlanRow)
            .filter(models.TreatmentPlanRow.patient_id == patient_id)
            .first()
        )
        if not row:
            regimen = patient.current_treatment if patient.current_treatment in REGIMENS else "Active Surveillance"
            row = models.TreatmentPlanRow(
                patient_id=patient_id, regimen=regimen, cycle=1, total_cycles=cycles_for(regimen),
                started_on=patient.diagnosed_on, next_dose=patient.last_updated, adherence=1.0,
                side_effects=side_effects_for(regimen), medications=MEDICATIONS_BY_REGIMEN.get(regimen, []),
            )
            self.db.add(row)
            try:
                self.db.commit()
            except SQLAlchemyError:
                self.db.rollback()
                raise
            self.db.refresh(row)
        elif not row.medications and row.regimen in MEDICATIONS_BY_REGIMEN:
            # A plan materialized by `SimulationService.promote` carries the
            # regimen but not its composition; fill it in on first read rather
            # than returning an empty medication list.
            row.medications = MEDICATIONS_BY_REGIMEN[row.regimen]
            row.side_effects = side_effects_for(row.regimen)
            row.next_dose = row.next_dose or datetime.now(timezone.utc).isoformat()
            try:
                self.db.commit()
            except SQLAlchemyError:
                self.db.rollback()
                raise
            self.db.refresh(row)

        return schemas.TreatmentPlan(
            regimen=row.regimen, cycle=row.cycle, total_cycles=row.total_cycles,
            started_on=row.started_on, next_dose=row.next_dose, adherence=row.adherence,
            side_effects=[schemas.SideEffect(**s) for s in (row.side_effects or [])],
            medications=[schemas.Medication(**m) for m in (row.medications or [])],
        )
