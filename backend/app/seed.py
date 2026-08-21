"""
One-time bootstrap data — run automatically on first startup (see main.py)
if the `users` table is empty. This is NOT fixture/mock clinical data: it's
the minimum an empty system needs to be usable (an admin login, the
permission matrix, and a record of the model that was actually trained).
No patients, predictions, or documents are seeded — those only exist once
created through the real endpoints.
"""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.core.security import hash_password

METRICS_PATH = Path(__file__).parent / "ml" / "artifacts" / "metrics.json"

DEFAULT_ADMIN_EMAIL = "admin@oncotwin.io"
DEFAULT_ADMIN_PASSWORD = "ChangeMe123!"

PERMISSIONS = [
    {"capability": "View patient records", "doctor": True, "patient": True, "technician": True, "admin": True},
    {"capability": "Edit patient records", "doctor": True, "patient": False, "technician": False, "admin": True},
    {"capability": "Run predictions/simulations", "doctor": True, "patient": False, "technician": False, "admin": True},
    {"capability": "Approve OCR extractions", "doctor": True, "patient": False, "technician": True, "admin": True},
    {"capability": "Generate/export reports", "doctor": True, "patient": False, "technician": False, "admin": True},
    {"capability": "Manage hospitals/departments", "doctor": False, "patient": False, "technician": False, "admin": True},
    {"capability": "Manage users & permissions", "doctor": False, "patient": False, "technician": False, "admin": True},
    {"capability": "View audit logs", "doctor": False, "patient": False, "technician": False, "admin": True},
]


def seed(db: Session) -> None:
    if db.query(models.User).count() > 0:
        return

    admin = models.User(
        name="System Administrator", email=DEFAULT_ADMIN_EMAIL,
        password_hash=hash_password(DEFAULT_ADMIN_PASSWORD), role="admin",
        title="Administrator", hospital="Northfield General Hospital", status="Active",
    )
    db.add(admin)

    db.add(models.Hospital(name="Northfield General Hospital", city="Northfield", beds=420, doctors=0, patients=0, status="Active"))
    db.add(models.Department(name="Oncology", head="Unassigned", staff=0, active_cases=0))

    for row in PERMISSIONS:
        db.add(models.PermissionRow(**row))

    if METRICS_PATH.exists():
        metrics = json.loads(METRICS_PATH.read_text())
        db.add(models.Dataset(
            name=metrics["dataset_name"], records=metrics["dataset_records"],
            modalities="Digitized FNA image features (30 numeric predictors)", updated=metrics["trained_at"][:10],
        ))
        db.add(models.MLModelRow(
            name=metrics["model_name"], version=metrics["model_version"],
            task="Malignancy risk classification (feeds survival/recurrence estimates)",
            auc=round(metrics["auc"], 4), status="Production",
        ))
        db.add(models.ModelVersionRow(
            version=metrics["model_version"], released=metrics["trained_at"][:10],
            auc=round(metrics["auc"], 4),
            notes=f"RandomForest ({metrics['n_estimators']} trees) trained on {metrics['dataset_records']} "
                  f"records; test accuracy {round(metrics['accuracy'] * 100, 1)}%.",
            stage="Production",
        ))
        db.add(models.TrainingRun(
            model=metrics["model_name"], duration="< 1 min", epochs=metrics["n_estimators"],
            loss=round(1 - metrics["accuracy"], 4), status="Complete",
        ))
        for i, auc in enumerate(metrics.get("fold_aucs", [])):
            db.add(models.PerformancePointRow(
                month=f"Fold {i + 1}", auc=round(auc, 4),
                precision=round(metrics.get("fold_precisions", [0] * 5)[i], 4),
                recall=round(metrics.get("fold_recalls", [0] * 5)[i], 4),
            ))

    db.commit()
    print(f"Seeded initial admin account: {DEFAULT_ADMIN_EMAIL} / {DEFAULT_ADMIN_PASSWORD} (change this immediately)")
