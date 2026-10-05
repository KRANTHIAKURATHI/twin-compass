"""
Digital twin router.

Reads and writes `twin_versions` / `twin_snapshots`. A "twin" is not its own
table: it is the ordered set of versions belonging to a patient, with the
`Active` one describing the twin's current state. That is why the list
endpoint projects one row per patient rather than per version.
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
from app.services.clinical_queries import resolve_patient

router = APIRouter(tags=["digital-twins"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _version_response(row) -> dict[str, object]:
    return {
        "version": row["version"],
        "createdAt": row["created_at"],
        "status": row["status"] or "Archived",
        "author": row["author"] or "",
        "summary": row["summary"] or "",
        "tumorSizeMm": row["tumor_size_mm"] or 0,
        "survival": row["survival"] or 0,
        "risk": row["risk"] or "low",
        "model": row["model"] or "",
    }


async def _versions_for(session: AsyncSession, patient_uuid: str) -> list[dict[str, object]]:
    result = await session.execute(
        text(
            "SELECT version, created_at, status, author, summary, tumor_size_mm, survival, "
            "risk, model FROM twin_versions WHERE patient_id = :pid ORDER BY created_at DESC"
        ),
        {"pid": patient_uuid},
    )
    return [_version_response(row) for row in result.mappings()]


def _twin_status(version: object, version_status: object, patient_twin_status: object) -> str:
    """A patient with no twin_versions row has no twin, whatever
    `patients.twin_status` says (its column default is "Synced")."""
    if not version:
        return "Not created"
    return str(version_status or patient_twin_status or "Not created")


def _twin_survival(version: object, version_survival: object) -> object:
    """Only a twin version records survival. `patients.survival_probability`
    is a column default until then, so a twin-less patient has none."""
    return version_survival if version else None


def _next_version(versions: list[dict[str, object]]) -> str:
    """`v3` after `v2`. Falls back to counting when a label is non-numeric."""
    numbers = []
    for item in versions:
        label = str(item["version"]).lstrip("vV")
        if label.isdigit():
            numbers.append(int(label))
    return f"v{(max(numbers) + 1) if numbers else len(versions) + 1}"


@router.get("/digital-twins")
async def list_twins(
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    """One entry per patient, described by that patient's active version."""
    result = await session.execute(
        text(
            """
            SELECT p.patient_code, p.name, p.twin_status, p.risk AS patient_risk,
                   p.survival_probability, p.tumor_size_mm AS patient_tumor,
                   tv.version, tv.created_at, tv.status, tv.author, tv.summary,
                   tv.tumor_size_mm, tv.survival, tv.risk, tv.model
            FROM patients p
            LEFT JOIN LATERAL (
                SELECT * FROM twin_versions t
                WHERE t.patient_id = p.id
                ORDER BY (t.status = 'Active') DESC, t.created_at DESC
                LIMIT 1
            ) tv ON TRUE
            WHERE p.deleted_at IS NULL
            ORDER BY p.patient_code
            """
        )
    )
    twins = []
    for row in result.mappings():
        twins.append(
            {
                "patientId": row["patient_code"],
                "patient": row["name"],
                # A patient with no twin_versions row genuinely has no twin
                # yet; say so rather than inventing a version label.
                "version": row["version"],
                "status": _twin_status(row["version"], row["status"], row["twin_status"]),
                "createdAt": row["created_at"],
                "author": row["author"] or "",
                "summary": row["summary"] or "",
                "tumorSizeMm": row["tumor_size_mm"] if row["version"] else row["patient_tumor"],
                "survival": _twin_survival(row["version"], row["survival"]),
                "risk": row["risk"] or row["patient_risk"] or "low",
                "model": row["model"] or "",
            }
        )
    return twins


@router.get("/digital-twins/{patient_id}")
async def get_twin(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    patient = await resolve_patient(session, patient_id)
    versions = await _versions_for(session, str(patient["id"]))
    active = next((v for v in versions if v["status"] == "Active"), versions[0] if versions else None)
    return {
        "patientId": patient["patient_code"],
        "patient": patient["name"],
        "twinStatus": (patient["twin_status"] or "Not created") if versions else "Not created",
        "active": active,
        "versions": versions,
    }


@router.get("/digital-twins/{patient_id}/versions")
async def twin_versions(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    patient = await resolve_patient(session, patient_id)
    return await _versions_for(session, str(patient["id"]))


@router.get("/digital-twins/{patient_id}/snapshots")
async def twin_snapshots(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    patient = await resolve_patient(session, patient_id)
    result = await session.execute(
        text(
            'SELECT id, version, taken_at, "trigger", size FROM twin_snapshots '
            "WHERE patient_id = :pid ORDER BY taken_at DESC"
        ),
        {"pid": str(patient["id"])},
    )
    return [
        {
            "id": row["id"],
            "version": row["version"],
            "takenAt": row["taken_at"],
            "trigger": row["trigger"] or "",
            "size": row["size"] or "",
        }
        for row in result.mappings()
    ]


@router.post("/digital-twins/{patient_id}/resync")
async def resync_twin(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    """Cut a new active version from the patient's current record.

    The twin's numbers are copied from the patient row, which is the only
    measured state this system holds - no model is invoked, so nothing here
    is predicted.
    """
    patient = await resolve_patient(session, patient_id)
    pid = str(patient["id"])
    versions = await _versions_for(session, pid)
    version = _next_version(versions)
    now = _now()

    snapshot = {
        key: patient[key]
        for key in ("patient_code", "name", "age", "stage", "tumor_size_mm", "er_status",
                    "pr_status", "her2_status", "ki67", "grade", "nodes_involved", "risk",
                    "survival_probability")
    }
    await session.execute(
        text("UPDATE twin_versions SET status = 'Superseded' WHERE patient_id = :pid AND status = 'Active'"),
        {"pid": pid},
    )
    await session.execute(
        text(
            """
            INSERT INTO twin_versions
                (id, patient_id, version, created_at, status, author, summary,
                 tumor_size_mm, survival, risk, model, snapshot)
            VALUES
                (:id, :pid, :version, :created_at, 'Active', :author, :summary,
                 :tumor_size_mm, :survival, :risk, :model, CAST(:snapshot AS jsonb))
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": pid,
            "version": version,
            "created_at": now,
            "author": current_user.email or str(current_user.id),
            "summary": "Resynced from the current patient record.",
            "tumor_size_mm": patient["tumor_size_mm"],
            "survival": patient["survival_probability"],
            "risk": patient["risk"],
            "model": "Patient record snapshot",
            "snapshot": json.dumps(snapshot, default=str),
        },
    )
    await session.execute(
        text("UPDATE patients SET twin_status = 'Synced', last_updated = :now WHERE id = :pid"),
        {"pid": pid, "now": now},
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
            "title": f"Digital twin resynced ({version})",
            "detail": f"New active version cut from the patient record by {current_user.email or current_user.id}.",
        },
    )
    await session.commit()
    return {"ok": True, "data": {"version": version}, "message": f"Digital twin resynced to {version}."}


@router.post("/digital-twins/{patient_id}/versions/{version}/restore")
async def restore_twin_version(
    patient_id: str,
    version: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    """Promote an older version back to Active by copying it forward.

    History is append-only: restoring writes a new version carrying the old
    one's values rather than mutating the original, so the audit trail of
    what the twin looked like at each point survives.
    """
    patient = await resolve_patient(session, patient_id)
    pid = str(patient["id"])
    source = (
        await session.execute(
            text("SELECT * FROM twin_versions WHERE patient_id = :pid AND version = :version"),
            {"pid": pid, "version": version},
        )
    ).mappings().first()
    if source is None:
        raise HTTPException(status_code=404, detail="Twin version not found.")

    versions = await _versions_for(session, pid)
    new_version = _next_version(versions)
    now = _now()
    await session.execute(
        text("UPDATE twin_versions SET status = 'Superseded' WHERE patient_id = :pid AND status = 'Active'"),
        {"pid": pid},
    )
    await session.execute(
        text(
            """
            INSERT INTO twin_versions
                (id, patient_id, version, created_at, status, author, summary,
                 tumor_size_mm, survival, risk, model, snapshot)
            VALUES
                (:id, :pid, :version, :created_at, 'Active', :author, :summary,
                 :tumor_size_mm, :survival, :risk, :model, :snapshot)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": pid,
            "version": new_version,
            "created_at": now,
            "author": current_user.email or str(current_user.id),
            "summary": f"Restored from {version}.",
            "tumor_size_mm": source["tumor_size_mm"],
            "survival": source["survival"],
            "risk": source["risk"],
            "model": source["model"],
            "snapshot": source["snapshot"],
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
            "title": f"Digital twin restored to {version}",
            "detail": f"Version {version} copied forward as {new_version}.",
        },
    )
    await session.commit()
    return {"ok": True, "data": {"version": new_version}, "message": f"Restored {version} as {new_version}."}


@router.post("/digital-twins/{patient_id}/archive")
async def archive_twin(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    patient = await resolve_patient(session, patient_id)
    pid = str(patient["id"])
    await session.execute(
        text("UPDATE twin_versions SET status = 'Archived' WHERE patient_id = :pid"),
        {"pid": pid},
    )
    await session.execute(
        text("UPDATE patients SET twin_status = 'Archived', last_updated = :now WHERE id = :pid"),
        {"pid": pid, "now": _now()},
    )
    await session.commit()
    return {"ok": True, "message": "Digital twin archived."}
