"""
Administrator-only endpoints for the two things authorization depends on:

  * approving privileged accounts - a doctor/researcher registration creates a profile with NO role; the account
    can neither sign in nor call any API until an administrator grants it one here;
  * patient access - who may reach which patient (`patient_access`, see services/patient_access.py).

Every change is audited (same transaction) and committed once. There is deliberately no endpoint that creates
administrators: that stays a manual, out-of-band step.
"""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.db.session import get_db_session
from app.dependencies.auth import CurrentUser, require_roles
from app.services.audit import record_audit
from app.services.clinical_queries import resolve_patient

router = APIRouter(tags=["admin"])

_GRANTABLE_ROLES = ("doctor", "researcher", "patient")


class GrantRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["doctor", "researcher", "patient"]


class GrantAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    profile_id: uuid.UUID = Field(alias="profileId")
    relationship: Literal["care_team", "self"]


async def _profile_roles(session: AsyncSession, profile_id: uuid.UUID) -> list[str] | None:
    """Role names of a profile, or None when the profile does not exist."""
    profile = (
        await session.execute(text("SELECT id FROM profiles WHERE id = :id AND deleted_at IS NULL"), {"id": str(profile_id)})
    ).first()
    if profile is None:
        return None
    rows = (
        await session.execute(
            text("SELECT r.name FROM user_roles ur JOIN roles r ON r.id = ur.role_id WHERE ur.profile_id = :id"),
            {"id": str(profile_id)},
        )
    ).all()
    return [r[0] for r in rows]


@router.get("/admin/users/pending")
async def pending_users(
    session: AsyncSession = Depends(get_db_session),
    _admin: CurrentUser = Depends(require_roles("admin")),
) -> list[dict[str, object]]:
    """Accounts that exist but hold no role (privileged registrations awaiting approval)."""
    rows = (
        await session.execute(
            text(
                "SELECT p.id, p.email, p.full_name, p.hospital, p.title, p.created_at FROM profiles p "
                "WHERE p.deleted_at IS NULL AND p.is_active AND NOT EXISTS "
                "(SELECT 1 FROM user_roles ur WHERE ur.profile_id = p.id) ORDER BY p.created_at"
            )
        )
    ).mappings().all()
    return [
        {"id": str(r["id"]), "email": r["email"], "name": r["full_name"], "hospital": r["hospital"],
         "title": r["title"], "createdAt": str(r["created_at"])}
        for r in rows
    ]


@router.post("/admin/users/{profile_id}/role")
async def grant_role(
    profile_id: uuid.UUID,
    payload: GrantRoleRequest,
    session: AsyncSession = Depends(get_db_session),
    admin: CurrentUser = Depends(require_roles("admin")),
) -> dict[str, object]:
    roles = await _profile_roles(session, profile_id)
    if roles is None:
        raise NotFoundError("Account not found.")
    if roles:
        raise ConflictError("This account already has a role; changing an existing role is not supported here.")
    await session.execute(
        text(
            "INSERT INTO user_roles (id, profile_id, role_id, granted_by) "
            "SELECT :id, :pid, r.id, :by FROM roles r WHERE r.name = :role"
        ),
        {"id": str(uuid.uuid4()), "pid": str(profile_id), "by": str(admin.id), "role": payload.role},
    )
    await record_audit(
        session, actor=admin, action="user.role_granted", target=str(profile_id),
        after={"profileId": str(profile_id), "role": payload.role},
    )
    await session.commit()
    return {"ok": True, "data": {"id": str(profile_id), "role": payload.role}, "message": f"{payload.role} access granted."}


@router.get("/admin/patients/{patient_id}/access")
async def list_access(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _admin: CurrentUser = Depends(require_roles("admin")),
) -> list[dict[str, object]]:
    patient = await resolve_patient(session, patient_id)
    rows = (
        await session.execute(
            text(
                "SELECT pa.profile_id, pa.relationship, pa.granted_at, p.email FROM patient_access pa "
                "JOIN profiles p ON p.id = pa.profile_id WHERE pa.patient_id = :pid ORDER BY pa.granted_at"
            ),
            {"pid": str(patient["id"])},
        )
    ).mappings().all()
    return [
        {"profileId": str(r["profile_id"]), "email": r["email"], "relationship": r["relationship"], "grantedAt": str(r["granted_at"])}
        for r in rows
    ]


@router.post("/admin/patients/{patient_id}/access", status_code=201)
async def grant_access(
    patient_id: str,
    payload: GrantAccessRequest,
    session: AsyncSession = Depends(get_db_session),
    admin: CurrentUser = Depends(require_roles("admin")),
) -> dict[str, object]:
    patient = await resolve_patient(session, patient_id)
    roles = await _profile_roles(session, payload.profile_id)
    if roles is None:
        raise NotFoundError("Account not found.")
    needed = "doctor" if payload.relationship == "care_team" else "patient"
    if needed not in roles:
        raise ValidationAppError(
            f"A '{payload.relationship}' relationship can only be granted to an account with the '{needed}' role.",
            field="profileId",
        )
    if payload.relationship == "self":
        # One login <-> one patient record: a patient account cannot be linked to a second record.
        other = (
            await session.execute(
                text("SELECT 1 FROM patient_access WHERE profile_id = :uid AND relationship = 'self' AND patient_id <> :pid"),
                {"uid": str(payload.profile_id), "pid": str(patient["id"])},
            )
        ).first()
        if other is not None:
            raise ConflictError("This patient account is already linked to a different patient record.")
    await session.execute(
        text(
            "INSERT INTO patient_access (patient_id, profile_id, relationship, granted_by) "
            "VALUES (:pid, :uid, :rel, :by) ON CONFLICT DO NOTHING"
        ),
        {"pid": str(patient["id"]), "uid": str(payload.profile_id), "rel": payload.relationship, "by": str(admin.id)},
    )
    await record_audit(
        session, actor=admin, action="patient.access_granted", target=patient["patient_code"],
        after={"profileId": str(payload.profile_id), "relationship": payload.relationship},
    )
    await session.commit()
    return {"ok": True, "message": "Access granted."}


@router.delete("/admin/patients/{patient_id}/access/{profile_id}")
async def revoke_access(
    patient_id: str,
    profile_id: uuid.UUID,
    relationship: Literal["care_team", "self"],
    session: AsyncSession = Depends(get_db_session),
    admin: CurrentUser = Depends(require_roles("admin")),
) -> dict[str, object]:
    patient = await resolve_patient(session, patient_id)
    result = await session.execute(
        text("DELETE FROM patient_access WHERE patient_id = :pid AND profile_id = :uid AND relationship = :rel"),
        {"pid": str(patient["id"]), "uid": str(profile_id), "rel": relationship},
    )
    if result.rowcount == 0:
        raise NotFoundError("No such access grant.")
    await record_audit(
        session, actor=admin, action="patient.access_revoked", target=patient["patient_code"],
        before={"profileId": str(profile_id), "relationship": relationship},
    )
    await session.commit()
    return {"ok": True, "message": "Access revoked."}
