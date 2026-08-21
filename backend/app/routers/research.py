from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.deps import get_current_user

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/models", response_model=list[schemas.MLModel])
def models_(db: Session = Depends(get_db), _user: models.User = Depends(get_current_user)):
    rows = db.query(models.MLModelRow).all()
    return [schemas.MLModel(id=m.id, name=m.name, version=m.version, task=m.task, auc=m.auc, status=m.status) for m in rows]


@router.get("/datasets", response_model=list[schemas.Dataset])
def datasets(db: Session = Depends(get_db), _user: models.User = Depends(get_current_user)):
    rows = db.query(models.Dataset).all()
    return [schemas.Dataset(id=d.id, name=d.name, records=d.records, modalities=d.modalities, updated=d.updated) for d in rows]


@router.get("/training-runs", response_model=list[schemas.TrainingRun])
def training_runs(db: Session = Depends(get_db), _user: models.User = Depends(get_current_user)):
    rows = db.query(models.TrainingRun).order_by(models.TrainingRun.started.desc()).all()
    return [schemas.TrainingRun(id=t.id, model=t.model, started=t.started, duration=t.duration, epochs=t.epochs, loss=t.loss, status=t.status) for t in rows]


@router.get("/model-versions", response_model=list[schemas.ModelVersion])
def model_versions(db: Session = Depends(get_db), _user: models.User = Depends(get_current_user)):
    rows = db.query(models.ModelVersionRow).order_by(models.ModelVersionRow.released.desc()).all()
    return [schemas.ModelVersion(version=m.version, released=m.released, auc=m.auc, notes=m.notes, stage=m.stage) for m in rows]


@router.get("/performance", response_model=list[schemas.PerformancePoint])
def performance(db: Session = Depends(get_db), _user: models.User = Depends(get_current_user)):
    rows = db.query(models.PerformancePointRow).all()
    return [schemas.PerformancePoint(month=p.month, auc=p.auc, precision=p.precision, recall=p.recall) for p in rows]
