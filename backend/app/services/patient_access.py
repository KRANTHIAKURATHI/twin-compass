"""
Patient-level authorization (who may touch WHICH patient), on top of the role checks in `require_roles`.

Model: table `patient_access` (supabase/migrations/20261106120000_patient_access.sql), one row per
(patient, profile, relationship):

  * relationship 'care_team' - a clinician (role doctor) who may work with the patient;
  * relationship 'self'      - the login (role patient) that IS the patient.

Rules (server-side, for every patient-linked route):
  * admin       - every patient;
  * doctor      - only patients with a 'care_team' row for that doctor;
  * patient     - only the patient with a 'self' row for that login;
  * researcher  - never: researchers have no identified patient access (aggregate analytics only).

Rows are created by the doctor who creates the patient (care_team) and by administrators
(`/admin/patients/{id}/access`). Patients that predate the table have no rows and are therefore reachable by
administrators only until someone is assigned - ownership is never inferred or backfilled.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError

RELATIONSHIP_FOR_ROLE = {"doctor": "care_team", "patient": "self"}
DENIED = "You do not have access to this patient."


def access_predicate(user: Any, patient_id_expr: str) -> tuple[str, dict[str, object]]:
    """(SQL predicate, bind params) restricting `patient_id_expr` to patients `user` may access."""
    role = str(user.role)
    if role == "admin":
        return "1 = 1", {}
    relationship = RELATIONSHIP_FOR_ROLE.get(role)
    if relationship is None:
        return "1 = 0", {}
    return (
        f"{patient_id_expr} IN (SELECT pa.patient_id FROM patient_access pa "
        "WHERE pa.profile_id = :acc_uid AND pa.relationship = :acc_rel)",
        {"acc_uid": str(user.id), "acc_rel": relationship},
    )


async def has_patient_access(session: AsyncSession, user: Any, patient_uuid: object) -> bool:
    role = str(user.role)
    if role == "admin":
        return True
    relationship = RELATIONSHIP_FOR_ROLE.get(role)
    if relationship is None:
        return False
    found = (
        await session.execute(
            text(
                "SELECT 1 FROM patient_access WHERE patient_id = :pid AND profile_id = :uid "
                "AND relationship = :rel LIMIT 1"
            ),
            {"pid": str(patient_uuid), "uid": str(user.id), "rel": relationship},
        )
    ).first()
    return found is not None


async def require_patient_access(session: AsyncSession, user: Any, patient_uuid: object) -> None:
    if not await has_patient_access(session, user, patient_uuid):
        raise AuthorizationError(DENIED)


async def grant_care_team(session: AsyncSession, patient_uuid: str, profile_id: object, granted_by: object | None) -> None:
    """Idempotent care-team grant (no commit: the caller's transaction owns it)."""
    await session.execute(
        text(
            "INSERT INTO patient_access (patient_id, profile_id, relationship, granted_by) "
            "VALUES (:pid, :uid, 'care_team', :by) ON CONFLICT DO NOTHING"
        ),
        {"pid": patient_uuid, "uid": str(profile_id), "by": str(granted_by) if granted_by else None},
    )
