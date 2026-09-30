"""
Shared read helpers for the clinical modules.

Every clinical router addresses patients the way the frontend does - by the
human-facing `patient_code` (`PT-1004`) - while every child table's foreign
key points at the internal `patients.id` uuid. Confusing the two is exactly
what made `POST /simulations/run` fail with an IntegrityError on every call,
so the translation lives here once instead of being re-derived per router.

Raw SQL matches the style of `routers/clinical.py`; the clinical tables are
not mapped by SQLAlchemy models (only the identity tables in
`app/models/identity.py` are).
"""
from __future__ import annotations

from typing import Any, Mapping

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PATIENT_COLUMNS = (
    "patient_code, name, age, gender, phone, email, hospital, stage, tumor_size_mm, "
    "er_status, pr_status, her2_status, ki67, grade, nodes_involved, current_treatment, "
    "status, risk, survival_probability, last_updated, diagnosed_on, twin_status, history, notes"
)


async def resolve_patient(session: AsyncSession, patient_id: str) -> Mapping[str, Any]:
    """Return the patient row addressed by either `patient_code` or `id`.

    Raises 404 rather than returning None: every caller treats a missing
    patient as a dead end, and raising here keeps that behaviour identical
    across routers.
    """
    row = (
        await session.execute(
            text(
                f"""
                SELECT id, {PATIENT_COLUMNS}
                FROM patients
                WHERE deleted_at IS NULL AND (patient_code = :patient_id OR id = :patient_id)
                LIMIT 1
                """
            ),
            {"patient_id": patient_id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return row


async def patient_uuid(session: AsyncSession, patient_id: str) -> str:
    """The internal uuid for a patient addressed by code or uuid."""
    return str((await resolve_patient(session, patient_id))["id"])
