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

from app.core.exceptions import ConflictError
from app.db.session import get_db_session
from app.dependencies.auth import CurrentUser, require_roles
from app.services.audit import record_audit
from app.services.patient_access import access_predicate
from app.services.twin_state import TWIN_CLINICAL_KEYS, missing_twin_fields
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
        # NULL stays NULL: a version that holds no value must not read as 0 mm / 0% / "low".
        "tumorSizeMm": row["tumor_size_mm"],
        "survival": row["survival"],
        "risk": row["risk"],
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
    _user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> list[dict[str, object]]:
    """One entry per patient, described by that patient's active version."""
    predicate, params = access_predicate(_user, "p.id")
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
            WHERE p.deleted_at IS NULL AND """ + predicate + """
            ORDER BY p.patient_code
            """
        ),
        params,
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
                "risk": row["risk"] or row["patient_risk"],
                "model": row["model"] or "",
            }
        )
    return twins


@router.get("/digital-twins/{patient_id}")
async def get_twin(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    patient = await resolve_patient(session, patient_id, _user)
    versions = await _versions_for(session, str(patient["id"]))
    active = next((v for v in versions if v["status"] == "Active"), versions[0] if versions else None)
    sync_status = (patient["twin_status"] or None) if versions else None
    return {
        "patientId": patient["patient_code"],
        "patient": patient["name"],
        # Kept for existing clients: the patient's synchronization status (Synced/Recalculating/Stale).
        "twinStatus": sync_status or "Not created",
        "syncStatus": sync_status,
        # Version lifecycle status of `active`, computed exactly as the list endpoint does
        # (Active / Superseded / Archived / Draft, or "Not created" with no version).
        "status": _twin_status(active["version"] if active else None, active["status"] if active else None, patient["twin_status"]),
        "active": active,
        "versions": versions,
    }


@router.get("/digital-twins/{patient_id}/versions")
async def twin_versions(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> list[dict[str, object]]:
    patient = await resolve_patient(session, patient_id, _user)
    return await _versions_for(session, str(patient["id"]))


@router.get("/digital-twins/{patient_id}/snapshots")
async def twin_snapshots(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> list[dict[str, object]]:
    patient = await resolve_patient(session, patient_id, _user)
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


def _active_version(versions: list[dict[str, object]]) -> str | None:
    return next((str(v["version"]) for v in versions if v["status"] == "Active"), None)


async def cut_twin_version(
    session: AsyncSession,
    patient,
    current_user: CurrentUser,
    *,
    summary: str = "Resynced from the current patient record.",
) -> dict[str, str | None]:
    """Cut a new active version from `patient` inside the caller's transaction.

    Does NOT commit: the caller commits once, together with whatever else
    belongs to the same operation (an audit row, an approved OCR update).
    Returns the new version label and the version it superseded.

    The twin's numbers are copied from the patient row, which is the only
    measured state this system holds - no model is invoked, so nothing here
    is predicted.
    """
    pid = str(patient["id"])
    versions = await _versions_for(session, pid)
    version = _next_version(versions)
    now = _now()

    # Everything prediction and simulation read from a twin is in the snapshot, as recorded: a field the patient row
    # does not hold is stored as null - never defaulted - and named in the summary so the gap is visible.
    snapshot = {key: patient[key] for key in ("patient_code", "name", *TWIN_CLINICAL_KEYS)}
    gaps = missing_twin_fields(snapshot)
    if gaps:
        summary = f"{summary} Not recorded: {', '.join(gaps)}."
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
            "summary": summary,
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
    return {"version": version, "previousVersion": _active_version(versions)}


@router.post("/digital-twins/{patient_id}/resync")
async def resync_twin(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    """Cut a new active version from the patient's current record."""
    patient = await resolve_patient(session, patient_id, current_user)
    cut = await cut_twin_version(session, patient, current_user)
    await record_audit(
        session,
        actor=current_user,
        action="twin.resynced",
        target=patient["patient_code"],
        before={"activeVersion": cut["previousVersion"]},
        after={"version": cut["version"], "trigger": "manual"},
    )
    await session.commit()
    return {"ok": True, "data": {"version": cut["version"]}, "message": f"Digital twin resynced to {cut['version']}."}


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
    patient = await resolve_patient(session, patient_id, current_user)
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
                 :tumor_size_mm, :survival, :risk, :model, CAST(:snapshot AS jsonb))
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
            # asyncpg returns jsonb as a dict, but a jsonb parameter must be sent as JSON text.
            "snapshot": (
                json.dumps(source["snapshot"], default=str)
                if isinstance(source["snapshot"], (dict, list))
                else source["snapshot"]
            ),
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
    await record_audit(
        session,
        actor=current_user,
        action="twin.restored",
        target=patient["patient_code"],
        before={"activeVersion": _active_version(versions)},
        after={"version": new_version, "sourceVersion": version},
    )
    await session.commit()
    return {"ok": True, "data": {"version": new_version}, "message": f"Restored {version} as {new_version}."}


@router.post("/digital-twins/{patient_id}/archive")
async def archive_twin(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    """Archive the twin's Active version; older (Superseded) versions are left as they are.

    "Archived" is a version lifecycle state (`twin_versions.status`). The patient's
    `twin_status` is a sync state with its own CHECK (Synced/Recalculating/Stale), so an
    archived twin is marked Stale there - it no longer tracks the record.
    """
    patient = await resolve_patient(session, patient_id, current_user)
    pid = str(patient["id"])
    # Lock the patient, then read what is archivable under the lock: a concurrent archive
    # waits here and then finds no Active version.
    locked = (
        await session.execute(
            text("SELECT twin_status FROM patients WHERE id = :pid AND deleted_at IS NULL FOR UPDATE"),
            {"pid": pid},
        )
    ).mappings().first()
    if locked is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    active = (
        await session.execute(
            text(
                "SELECT version FROM twin_versions WHERE patient_id = :pid AND status = 'Active' "
                "ORDER BY created_at DESC"
            ),
            {"pid": pid},
        )
    ).mappings().first()
    if active is None:
        raise ConflictError("This patient has no active digital twin to archive.")

    await session.execute(
        text("UPDATE twin_versions SET status = 'Archived' WHERE patient_id = :pid AND status = 'Active'"),
        {"pid": pid},
    )
    await session.execute(
        text("UPDATE patients SET twin_status = 'Stale', last_updated = :now WHERE id = :pid"),
        {"pid": pid, "now": _now()},
    )
    await record_audit(
        session,
        actor=current_user,
        action="twin.archived",
        target=patient["patient_code"],
        before={"twinStatus": locked["twin_status"], "activeVersion": active["version"]},
        after={"twinStatus": "Stale", "versionStatus": "Archived", "archivedVersion": active["version"]},
    )
    await session.commit()
    return {"ok": True, "message": "Digital twin archived."}
