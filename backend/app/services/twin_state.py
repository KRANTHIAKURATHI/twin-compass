"""The active digital twin as the authoritative clinical state for prediction and simulation.

A twin version freezes the patient's clinical state at the moment it was cut (`cut_twin_version`). Everything
downstream - the prediction input and the treatment-simulation input - must be built from that frozen state, never
from the live `patients` row, or a run recorded against "twin v8" could silently have used values that were entered
after v8 and cannot be reproduced later.

Nothing here defaults, estimates or corrects a value: a field the twin does not hold is returned as None and the
caller reports it as missing.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# The clinical state a twin snapshot preserves (and the only keys prediction and simulation read).
TWIN_CLINICAL_KEYS: tuple[str, ...] = (
    "age",
    "stage",
    "tumor_size_mm",
    "grade",
    "nodes_involved",
    "ki67",
    "er_status",
    "pr_status",
    "her2_status",
    "risk",
    "survival_probability",
)

# Older twin versions were cut before the snapshot carried everything; their own columns still hold these three.
_VERSION_COLUMN_FALLBACK = (
    ("tumor_size_mm", "tumor_size_mm"),
    ("survival_probability", "survival"),
    ("risk", "risk"),
)


def _present(value: object) -> bool:
    return value is not None and value != ""


def missing_twin_fields(state: Mapping[str, object], keys: Iterable[str] = TWIN_CLINICAL_KEYS) -> list[str]:
    """The clinical fields a state does not hold, in canonical order."""
    return [key for key in keys if not _present(state.get(key))]


def drifted_fields(changed: Iterable[str]) -> list[str]:
    """Which of the changed patient columns are part of the twin's clinical state."""
    return [key for key in changed if key in TWIN_CLINICAL_KEYS]


def _as_snapshot(raw: object) -> dict[str, object]:
    """The snapshot jsonb as a dict. Drivers return it as a dict or as JSON text; anything else is no snapshot."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


async def active_twin_state(
    session: AsyncSession, patient: Mapping[str, object]
) -> tuple[dict[str, object], str | None]:
    """The clinical state downstream runs must use, and the twin version it came from.

    With an Active twin version the state is that version's snapshot ONLY. A field missing from the snapshot stays
    missing (None): it is never filled from the patient's current row, which may have changed since the twin was cut.
    Versions cut before the snapshot held everything fall back to their own tumour size / survival / risk columns.

    A version that is not Active (Superseded, Archived) is not the twin and is never used. With no Active version the
    patient's current row is all there is, and the returned version is None so the run records "no twin".
    """
    twin = (
        await session.execute(
            text(
                """
                SELECT version, snapshot, tumor_size_mm, survival, risk
                FROM twin_versions
                WHERE patient_id = :pid AND lower(status) = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"pid": patient["id"]},
        )
    ).mappings().first()

    if twin is None:
        return {key: patient.get(key) for key in TWIN_CLINICAL_KEYS}, None

    snapshot = _as_snapshot(twin["snapshot"])
    state: dict[str, object] = {key: snapshot.get(key) if _present(snapshot.get(key)) else None for key in TWIN_CLINICAL_KEYS}
    for key, column in _VERSION_COLUMN_FALLBACK:
        if state[key] is None and _present(twin[column]):
            state[key] = twin[column]
    return state, twin["version"]
