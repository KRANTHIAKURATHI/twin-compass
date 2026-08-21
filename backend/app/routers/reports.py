import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.deps import assert_patient_readable, get_current_user, require_roles, log_audit
from app.serializers import patient_to_schema

router = APIRouter(prefix="/reports", tags=["reports"])

_clinical_staff = require_roles("doctor", "admin")


def _assert_report_readable(db: Session, report: models.SavedReport, user: models.User) -> None:
    if report.patient_id:
        patient = db.get(models.Patient, report.patient_id)
        if patient:
            assert_patient_readable(patient, user)


def _row_to_schema(r: models.SavedReport) -> schemas.SavedReport:
    return schemas.SavedReport(id=r.id, title=r.title, patient=r.patient_name, patient_id=r.patient_id or "",
                                type=r.type, created=r.created, version=r.version, status=r.status, downloads=r.downloads)


@router.get("", response_model=list[schemas.SavedReport])
def list_reports(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = db.query(models.SavedReport).order_by(models.SavedReport.created.desc()).all()
    if user.role == "patient":
        def _owned(r: models.SavedReport) -> bool:
            p = db.get(models.Patient, r.patient_id) if r.patient_id else None
            return bool(p and p.email == user.email)
        rows = [r for r in rows if _owned(r)]
    return [_row_to_schema(r) for r in rows]


@router.get("/downloads", response_model=list[schemas.DownloadRecord])
def downloads(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Download history. A `patient`-role caller sees only records for reports
    tied to their own patient record; staff see all."""
    rows = db.query(models.DownloadRecord).order_by(models.DownloadRecord.date.desc()).all()
    if user.role == "patient":
        own_report_ids = {
            r.id for r in db.query(models.SavedReport)
            .join(models.Patient, models.SavedReport.patient_id == models.Patient.id)
            .filter(models.Patient.email == user.email)
            .all()
        }
        rows = [r for r in rows if r.report_id in own_report_ids]
    return [schemas.DownloadRecord(id=r.id, report=r.report_id, format=r.format, by=r.by, date=r.date) for r in rows]


@router.get("/{report_id}", response_model=schemas.SavedReport | None)
def get_report(report_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    r = db.get(models.SavedReport, report_id)
    if not r:
        return None
    _assert_report_readable(db, r, user)
    return _row_to_schema(r)


@router.get("/{report_id}/versions", response_model=list[schemas.ReportVersion])
def versions(report_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    r = db.get(models.SavedReport, report_id)
    if r:
        _assert_report_readable(db, r, user)
    rows = db.query(models.ReportVersion).filter(models.ReportVersion.report_id == report_id).order_by(models.ReportVersion.version.desc()).all()
    return [schemas.ReportVersion(version=r.version, date=r.date, author=r.author, note=r.note) for r in rows]


@router.post("/generate", response_model=schemas.MutationResult[schemas.SavedReport])
def generate(payload: schemas.GenerateReportInput, db: Session = Depends(get_db), user: models.User = Depends(_clinical_staff)):
    patient = db.get(models.Patient, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    row = models.SavedReport(title=f"{payload.report_type} — {patient.name}", patient_id=patient.id, patient_name=patient.name,
                              type=payload.report_type, version=1, status="Draft")
    db.add(row)
    db.flush()
    db.add(models.ReportVersion(report_id=row.id, version=1, date=row.created, author=user.name, note="Generated from current patient + prediction data"))
    db.commit()
    db.refresh(row)
    log_audit(db, actor=user.email, actor_role=user.role, action="generate_report", target=row.title,
              after={"id": row.id, "patient_id": row.patient_id, "type": row.type, "status": row.status})
    return schemas.MutationResult(ok=True, data=_row_to_schema(row), message="Report generated")


@router.post("/export", response_model=schemas.MutationResult)
def export(payload: schemas.ReportExportInput, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Matches the frontend contract: returns a descriptor, not a binary
    stream (see docs/backend-integration-report.md). Use
    GET /reports/{id}/download?format=... below for the actual file bytes."""
    if payload.report_id:
        report = db.get(models.SavedReport, payload.report_id)
        if report:
            _assert_report_readable(db, report, user)
            report.downloads += 1
            db.add(models.DownloadRecord(report_id=report.id, format=payload.format, by=user.name))
            db.commit()
    return schemas.MutationResult(ok=True, data={"format": payload.format}, message=f"Export ready ({payload.format})")


@router.get("/{report_id}/download")
def download(report_id: str, format: str = "pdf", db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    report = db.get(models.SavedReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    _assert_report_readable(db, report, user)
    patient = db.get(models.Patient, report.patient_id) if report.patient_id else None

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Field", "Value"])
        writer.writerow(["Report", report.title])
        writer.writerow(["Type", report.type])
        writer.writerow(["Created", report.created])
        if patient:
            p = patient_to_schema(patient)
            for field, value in p.model_dump(by_alias=True).items():
                if not isinstance(value, (list, dict)):
                    writer.writerow([field, value])
        report.downloads += 1
        db.add(models.DownloadRecord(report_id=report.id, format="csv", by=user.name))
        db.commit()
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                  headers={"Content-Disposition": f'attachment; filename="{report.id}.csv"'})

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 740, report.title)
    c.setFont("Helvetica", 11)
    y = 710
    lines = [f"Type: {report.type}", f"Created: {report.created}", f"Status: {report.status}"]
    if patient:
        p = patient_to_schema(patient)
        lines += [
            f"Patient: {p.name} (age {p.age})", f"Stage: {p.stage}   Risk: {p.risk}",
            f"Tumor size: {p.tumor_size_mm} mm   Grade: {p.grade}",
            f"ER/PR/HER2: {p.er_status}/{p.pr_status}/{p.her2_status}",
            f"Current treatment: {p.current_treatment}",
            f"Survival probability: {round(p.survival_probability * 100, 1)}%",
        ]
    for line in lines:
        c.drawString(72, y, line)
        y -= 20
    c.showPage()
    c.save()
    buf.seek(0)
    report.downloads += 1
    db.add(models.DownloadRecord(report_id=report.id, format="pdf", by=user.name))
    db.commit()
    return StreamingResponse(buf, media_type="application/pdf",
                              headers={"Content-Disposition": f'attachment; filename="{report.id}.pdf"'})
