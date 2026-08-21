import json
from collections import OrderedDict
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.core.database import get_db
from app.deps import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

METRICS_PATH = Path(__file__).resolve().parent.parent / "ml" / "artifacts" / "metrics.json"


def _month_key(iso_date: str) -> str:
    try:
        return iso_date[:7]  # YYYY-MM
    except Exception:
        return "unknown"


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _user: models.User = Depends(get_current_user)):
    """Real cumulative patient/twin growth per calendar month, derived from
    each patient's `diagnosed_on` and their first twin version's
    `created_at` — no placeholder series."""
    patients = db.query(models.Patient).order_by(models.Patient.diagnosed_on.asc()).all()
    twins = db.query(models.TwinVersion).order_by(models.TwinVersion.created_at.asc()).all()

    patient_months = OrderedDict()
    for p in patients:
        key = _month_key(p.diagnosed_on)
        patient_months[key] = patient_months.get(key, 0) + 1

    twin_first_month: dict[str, str] = {}
    for t in twins:
        if t.patient_id not in twin_first_month:
            twin_first_month[t.patient_id] = _month_key(t.created_at)
    twin_months = OrderedDict()
    for month in twin_first_month.values():
        twin_months[month] = twin_months.get(month, 0) + 1

    all_months = sorted(set(patient_months) | set(twin_months))
    running_patients = 0
    running_twins = 0
    rows = []
    for month in all_months:
        running_patients += patient_months.get(month, 0)
        running_twins += twin_months.get(month, 0)
        rows.append({"month": month, "patients": running_patients, "twins": running_twins})
    return rows


@router.get("/cohort")
def cohort(db: Session = Depends(get_db), _user: models.User = Depends(get_current_user)):
    """Real stage distribution across every patient currently in the DB."""
    counts: dict[str, int] = {}
    for (stage,) in db.query(models.Patient.stage).all():
        counts[stage] = counts.get(stage, 0) + 1
    order = ["0", "I", "II", "III", "IV"]
    return [{"stage": f"Stage {s}", "count": counts.get(s, 0)} for s in order if s in counts or True]


@router.get("/accuracy")
def accuracy(_user: models.User = Depends(get_current_user)):
    """Real cross-validation fold performance from the trained model
    (see app/ml/train.py) — five actual held-out folds, not a fabricated
    monthly trend."""
    if not METRICS_PATH.exists():
        return []
    metrics = json.loads(METRICS_PATH.read_text())
    fold_acc = metrics.get("fold_accuracies", [])
    return [{"month": f"Fold {i + 1}", "accuracy": round(v * 100, 2)} for i, v in enumerate(fold_acc)]
