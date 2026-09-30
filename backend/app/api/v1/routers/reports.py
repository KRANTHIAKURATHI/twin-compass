"""
Reports router (Phase 8).

A report is a snapshot, not a live view: `generate` reads the patient's
current clinical record, active twin version, latest prediction run, recent
simulation runs, document count and recent timeline events, then freezes
that into `reports.content` as a new immutable version. Nothing here is
computed or predicted - every field is either read straight out of another
table or explicitly marked absent.

Scientific honesty, carried through from `routers/predictions.py`:
  * `prediction.basis` is `"measured"` (a real recorded run exists) or
    `"none"` - never a fabricated forecast. There is no trained ML model in
    this codebase.
  * Every simulation entry is labelled `"prototype"` - a research kinetic
    projection, not a clinically validated recommendation.

RBAC follows the same convention as `routers/documents.py` / `routers/
twins.py` / `routers/predictions.py`: doctor/researcher/admin only. There is
no profile-to-patient-record link in this codebase for a patient-role user
to self-scope reports by (see the Phase 6 report), so reports are not yet
exposed to the patient role - extending that is out of this phase's scope.

Patient isolation is structural rather than a filter: every report row
carries the `patient_id` it was generated for, and `/reports/{id}` looks up
by that row's own primary key, so there is no query shape that can return
one patient's report for another patient's id.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.dependencies.auth import CurrentUser, require_roles
from app.schemas.reports import ExportReportRequest, GenerateReportRequest
from app.services.clinical_queries import resolve_patient

router = APIRouter(tags=["reports"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_REPORT_SELECT = """
    SELECT r.id, r.patient_id, r.type, r.title, r.version, r.status,
           r.generated_at, r.content, p.patient_code, p.name AS patient_name
    FROM reports r
    JOIN patients p ON p.id = r.patient_id
"""


async def _downloads_count(session: AsyncSession, report_id: str) -> int:
    row = (
        await session.execute(
            text("SELECT count(*) AS n FROM report_downloads WHERE report_id = :id"),
            {"id": report_id},
        )
    ).mappings().one()
    return int(row["n"])


async def _report_response(session: AsyncSession, row) -> dict[str, object]:
    return {
        "id": row["id"],
        "title": row["title"],
        "patient": row["patient_name"],
        "patientId": row["patient_code"],
        "type": row["type"],
        "created": row["generated_at"],
        "version": row["version"],
        "status": row["status"],
        "downloads": await _downloads_count(session, row["id"]),
    }


async def _get_report_row(session: AsyncSession, report_id: str):
    row = (
        await session.execute(text(f"{_REPORT_SELECT} WHERE r.id = :id"), {"id": report_id})
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return row


@router.get("/reports")
async def list_reports(
    patientId: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    where = ""
    params: dict[str, object] = {}
    if patientId:
        where = "WHERE p.patient_code = :patient_id OR p.id::text = :patient_id"
        params["patient_id"] = patientId
    result = await session.execute(
        text(f"{_REPORT_SELECT} {where} ORDER BY r.generated_at DESC"), params
    )
    rows = result.mappings().all()
    return [await _report_response(session, row) for row in rows]


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    row = await _get_report_row(session, report_id)
    base = await _report_response(session, row)
    return {**base, "content": row["content"]}


@router.get("/reports/{report_id}/versions")
async def report_versions(
    report_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    """Every version generated for this report's (patient, type) lineage -
    not just the one `report_id` names - so history shows the full chain."""
    anchor = await _get_report_row(session, report_id)
    result = await session.execute(
        text(
            """
            SELECT r.version, r.generated_at, r.content, pr.email AS author_email
            FROM reports r
            LEFT JOIN profiles pr ON pr.id = r.generated_by
            WHERE r.patient_id = :pid AND r.type = :type
            ORDER BY r.version DESC
            """
        ),
        {"pid": str(anchor["patient_id"]), "type": anchor["type"]},
    )
    versions = []
    for row in result.mappings():
        content = row["content"] or {}
        note = content.get("generationNote") if isinstance(content, dict) else None
        versions.append(
            {
                "version": row["version"],
                "date": row["generated_at"],
                "author": row["author_email"] or "",
                "note": note or ("Initial generation" if row["version"] == 1 else f"Regenerated as v{row['version']}"),
            }
        )
    return versions


@router.get("/reports/downloads")
async def download_history(
    reportId: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    where = ""
    params: dict[str, object] = {}
    if reportId:
        where = "WHERE d.report_id = :report_id"
        params["report_id"] = reportId
    result = await session.execute(
        text(
            f"""
            SELECT d.id, d.report_id, d.format, d.downloaded_at, pr.email AS by_email
            FROM report_downloads d
            LEFT JOIN profiles pr ON pr.id = d.downloaded_by
            {where}
            ORDER BY d.downloaded_at DESC
            """
        ),
        params,
    )
    return [
        {
            "id": row["id"],
            "report": row["report_id"],
            "format": row["format"].upper(),
            "by": row["by_email"] or "",
            "at": row["downloaded_at"],
        }
        for row in result.mappings()
    ]


async def _next_version(session: AsyncSession, patient_uuid: str, report_type: str) -> int:
    row = (
        await session.execute(
            text("SELECT max(version) AS v FROM reports WHERE patient_id = :pid AND type = :type"),
            {"pid": patient_uuid, "type": report_type},
        )
    ).mappings().one()
    return (row["v"] or 0) + 1


@router.post("/reports/generate", status_code=201)
async def generate_report(
    payload: GenerateReportRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    """Aggregate the patient's current real clinical state into a new,
    immutable report version. Nothing is invented: a section with no
    underlying data is represented as absent, not filled in."""
    patient = await resolve_patient(session, payload.patient_id)
    pid = str(patient["id"])

    twin = (
        await session.execute(
            text(
                "SELECT version, created_at, status, tumor_size_mm, survival, risk, model "
                "FROM twin_versions WHERE patient_id = :pid "
                "ORDER BY (status = 'Active') DESC, created_at DESC LIMIT 1"
            ),
            {"pid": pid},
        )
    ).mappings().first()

    prediction = (
        await session.execute(
            text(
                "SELECT date, twin_version, model, survival, recurrence, response, confidence "
                "FROM prediction_runs WHERE patient_id = :pid ORDER BY date DESC LIMIT 1"
            ),
            {"pid": pid},
        )
    ).mappings().first()

    simulations = (
        await session.execute(
            text(
                "SELECT id, date, selected, decision, survival, response, confidence "
                "FROM simulation_runs WHERE patient_id = :pid ORDER BY date DESC LIMIT 5"
            ),
            {"pid": pid},
        )
    ).mappings().all()

    doc_count_row = (
        await session.execute(
            text("SELECT count(*) AS n FROM documents WHERE patient_id = :pid"),
            {"pid": pid},
        )
    ).mappings().one()

    timeline = (
        await session.execute(
            text(
                "SELECT date, title, detail, kind FROM timeline_events "
                "WHERE patient_id = :pid ORDER BY date DESC LIMIT 10"
            ),
            {"pid": pid},
        )
    ).mappings().all()

    content: dict[str, object] = {
        "patient": {
            "name": patient["name"],
            "patientId": patient["patient_code"],
            "age": patient["age"],
            "stage": patient["stage"],
            "tumorSizeMm": patient["tumor_size_mm"],
            "erStatus": patient["er_status"],
            "prStatus": patient["pr_status"],
            "her2Status": patient["her2_status"],
            "currentTreatment": patient["current_treatment"],
            "status": patient["status"],
        },
        "digitalTwin": (
            {
                "version": twin["version"],
                "createdAt": twin["created_at"],
                "status": twin["status"],
                "tumorSizeMm": twin["tumor_size_mm"],
                "survival": twin["survival"],
                "risk": twin["risk"],
            }
            if twin is not None
            else None
        ),
        "prediction": (
            {
                "basis": "measured",
                "date": prediction["date"],
                "twinVersion": prediction["twin_version"],
                "model": prediction["model"],
                "survival": prediction["survival"],
                "recurrence": prediction["recurrence"],
                "riskBand": prediction["response"],
                "confidence": prediction["confidence"],
            }
            if prediction is not None
            else {
                "basis": "none",
                "caveat": "No prediction run has been recorded for this patient. This system has no trained ML model attached.",
            }
        ),
        "simulations": {
            "basis": "prototype",
            "caveat": "Research/prototype kinetic simulation projection - not a clinically validated recommendation.",
            "runs": [
                {
                    "id": s["id"],
                    "date": s["date"],
                    "selected": s["selected"],
                    "decision": s["decision"],
                    "survival": s["survival"],
                    "response": s["response"],
                    "confidence": s["confidence"],
                }
                for s in simulations
            ],
        },
        "documents": {"count": int(doc_count_row["n"])},
        "timeline": [
            {"date": t["date"], "title": t["title"], "detail": t["detail"] or "", "kind": t["kind"]}
            for t in timeline
        ],
        "notes": patient["notes"],
    }

    version = await _next_version(session, pid, payload.type)
    if version > 1:
        content["generationNote"] = f"Regenerated as v{version} from the current patient record."
    report_id = str(uuid.uuid4())
    now = _now()
    title = f"{payload.type} — {patient['name']}"

    await session.execute(
        text(
            """
            INSERT INTO reports
                (id, patient_id, type, title, version, status, generated_by, generated_at, content, created_at)
            VALUES
                (:id, :pid, :type, :title, :version, 'Final', :generated_by, :generated_at, CAST(:content AS jsonb), :generated_at)
            """
        ),
        {
            "id": report_id,
            "pid": pid,
            "type": payload.type,
            "title": title,
            "version": version,
            "generated_by": str(current_user.id),
            "generated_at": now,
            "content": json.dumps(content, default=str),
        },
    )
    await session.execute(
        text(
            "INSERT INTO timeline_events (id, patient_id, date, title, detail, kind) "
            "VALUES (:id, :pid, :date, :title, :detail, 'note')"
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": pid,
            "date": now,
            "title": f"Report generated ({payload.type} v{version})",
            "detail": f"Generated by {current_user.email or current_user.id}.",
        },
    )
    await session.commit()

    row = await _get_report_row(session, report_id)
    data = await _report_response(session, row)
    return {"ok": True, "data": data, "message": f"{payload.type} generated (v{version})."}


@router.post("/reports/{report_id}/export")
async def export_report(
    report_id: str,
    payload: ExportReportRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    """Record a real export/download event and return the report's frozen
    content so the caller can render it (print) or serialize it (CSV) from
    actual data, rather than a client-side placeholder."""
    row = await _get_report_row(session, report_id)
    fmt = payload.format.lower()
    if fmt not in ("pdf", "csv"):
        raise HTTPException(status_code=422, detail="format must be 'pdf' or 'csv'.")

    await session.execute(
        text(
            "INSERT INTO report_downloads (id, report_id, format, downloaded_by, downloaded_at) "
            "VALUES (:id, :report_id, :format, :by, :at)"
        ),
        {
            "id": str(uuid.uuid4()),
            "report_id": report_id,
            "format": fmt,
            "by": str(current_user.id),
            "at": _now(),
        },
    )
    await session.commit()

    base = await _report_response(session, row)
    return {
        "ok": True,
        "data": {**base, "content": row["content"], "format": fmt},
        "message": f"{fmt.upper()} export recorded.",
    }
