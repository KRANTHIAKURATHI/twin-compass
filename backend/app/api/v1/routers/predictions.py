"""
Predictions router.

An honesty note that governs this whole module: **this codebase contains no
trained model.** `patients.survival_probability` and `patients.risk` are
values stored on the record by whatever wrote it; nothing here infers them.

So every number this router returns is one of two things, and the response
labels which:

  * `measured`  - read straight out of the database (a recorded prediction
                  run, a tumour size logged against a twin version).
  * `cohort`    - an aggregate computed over the real patient rows in this
                  database (see `/explainability` and the survival curve in
                  the analytics router).

Nothing is a forecast, because there is nothing here that can forecast. When
a real model is attached, `POST /predictions/run` is the seam to change: it
currently records the twin's stored state as a prediction run, and would
instead record the model's output.
"""
from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.dependencies.auth import CurrentUser, require_roles
from app.schemas.clinical import PredictionRequest
from app.services.clinical_queries import resolve_patient

router = APIRouter(tags=["predictions"])


def _prediction_response(row) -> dict[str, object]:
    return {
        "id": row["id"],
        "date": row["date"],
        "twinVersion": row["twin_version"] or "",
        "model": row["model"] or "",
        # Null-through for the same reason as `confidence` below: a run that
        # recorded no survival figure is not a run that predicted 0% survival,
        # and `or 0` turned the first into the second.
        "survival": row["survival"],
        "recurrence": row["recurrence"],
        # The stored column is called `response`, but what a run actually writes
        # there is the twin's risk band - "low", "moderate", "high". Exposing it
        # under its real meaning stops the UI printing a risk band in the place
        # a treatment response belongs. The column keeps its name because the
        # schema lives in Supabase and is not migrated from here.
        "riskBand": row["response"],
        # Left null rather than coerced to 0: "no confidence recorded" and
        # "0% confident" are different claims and the UI must be able to tell
        # them apart.
        "confidence": row["confidence"],
        "status": row["status"] or "Complete",
    }


async def _history(session: AsyncSession, patient_uuid: str) -> list[dict[str, object]]:
    result = await session.execute(
        text(
            "SELECT id, date, twin_version, model, survival, recurrence, response, "
            "confidence, status FROM prediction_runs WHERE patient_id = :pid ORDER BY date DESC"
        ),
        {"pid": patient_uuid},
    )
    return [_prediction_response(row) for row in result.mappings()]


@router.get("/predictions/{patient_id}")
async def latest_prediction(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object] | None:
    """The most recent recorded run, or null when none has been run."""
    patient = await resolve_patient(session, patient_id)
    runs = await _history(session, str(patient["id"]))
    return runs[0] if runs else None


@router.get("/predictions/{patient_id}/history")
async def prediction_history(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    patient = await resolve_patient(session, patient_id)
    return await _history(session, str(patient["id"]))


@router.get("/predictions/{patient_id}/confidence-trend")
async def confidence_trend(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    """Confidence of each recorded run, oldest first - a real series, so it
    is empty until runs exist rather than being back-filled."""
    patient = await resolve_patient(session, patient_id)
    result = await session.execute(
        text(
            "SELECT date, confidence FROM prediction_runs WHERE patient_id = :pid ORDER BY date ASC"
        ),
        {"pid": str(patient["id"])},
    )
    return [
        {"date": row["date"], "confidence": row["confidence"]}
        for row in result.mappings()
        # Runs with no recorded confidence are omitted rather than plotted at
        # zero, which would draw a cliff that never happened.
        if row["confidence"] is not None
    ]


@router.get("/predictions/{patient_id}/progression")
async def tumor_size_history(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    """Measured tumour size across the patient's twin versions.

    This replaces what used to be a hardcoded "progression forecast". Each
    point is a real recorded measurement at a real timestamp; there is no
    projection past the latest version.
    """
    patient = await resolve_patient(session, patient_id)
    result = await session.execute(
        text(
            "SELECT version, created_at, tumor_size_mm, survival FROM twin_versions "
            "WHERE patient_id = :pid ORDER BY created_at ASC"
        ),
        {"pid": str(patient["id"])},
    )
    return [
        {
            "version": row["version"],
            "date": row["created_at"],
            "tumorSizeMm": row["tumor_size_mm"] or 0,
            "survival": round((row["survival"] or 0) * 100, 1),
        }
        for row in result.mappings()
    ]


# Factors the cohort statistic is computed over. Each entry says how to pull
# a comparable number out of a patient row; `higher_is_worse` records the
# expected direction so the sign of a weak correlation stays meaningful.
_FACTORS: list[tuple[str, str, bool]] = [
    ("Tumor size (mm)", "tumor_size_mm", True),
    ("Ki-67 index", "ki67", True),
    ("Lymph nodes involved", "nodes_involved", True),
    ("Grade", "grade", True),
    ("Age at diagnosis", "age", True),
]

# Every factor label mapped back to its patient column, so a response can
# show the patient's own value next to the cohort weight.
_COLUMN_FOR: dict[str, str] = {
    **{label: column for label, column, _ in _FACTORS},
    "ER status": "er_status",
    "PR status": "pr_status",
    "HER2 status": "her2_status",
}


# Below this many patients a Pearson correlation is dominated by the handful
# of points that happen to exist - three patients can produce a coefficient of
# exactly 1.0, which reads as certainty and is nothing of the kind. Cohorts
# under this size still return weights, flagged `indicative` so the UI can
# warn instead of charting them as settled.
_RELIABLE_COHORT = 10


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Correlation coefficient, 0.0 when undefined (constant input)."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


@router.get("/predictions/{patient_id}/explainability")
async def explainability(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    """Cohort-derived factor weights - explicitly NOT a model explanation.

    For each clinical factor this correlates its value against the recorded
    `survival_probability` across every patient in the database, then
    normalises the absolute correlations to sum to 1 so they read as
    relative weights. Categorical factors (ER/PR/HER2) are encoded as 0/1.

    This is a descriptive statistic about the cohort, not an attribution of
    any individual prediction, and the response says so in `basis` and
    `caveat` so the UI can label it truthfully. Swap this for real SHAP
    values once a model exists.
    """
    patient = await resolve_patient(session, patient_id)
    rows = (
        await session.execute(
            text(
                "SELECT tumor_size_mm, ki67, nodes_involved, grade, age, er_status, "
                "pr_status, her2_status, survival_probability FROM patients "
                "WHERE deleted_at IS NULL AND survival_probability IS NOT NULL"
            )
        )
    ).mappings().all()

    cohort_size = len(rows)
    if cohort_size < 3:
        # Two points make every correlation +/-1. Refuse rather than emit a
        # confident-looking number off a cohort that cannot support one.
        return {
            "basis": "cohort",
            "cohortSize": cohort_size,
            "reliability": "insufficient",
            "factors": [],
            "caveat": (
                "Not enough patient records to compute cohort statistics "
                f"(have {cohort_size}, need at least 3)."
            ),
        }

    survival = [float(r["survival_probability"]) for r in rows]
    raw: list[tuple[str, float]] = []

    for label, column, higher_is_worse in _FACTORS:
        values = [float(r[column]) if r[column] is not None else 0.0 for r in rows]
        raw.append((label, _pearson(values, survival)))

    for label, column in (("ER status", "er_status"), ("PR status", "pr_status"), ("HER2 status", "her2_status")):
        values = [1.0 if (r[column] or "").lower() == "positive" else 0.0 for r in rows]
        raw.append((label, _pearson(values, survival)))

    total = sum(abs(c) for _, c in raw)
    if total == 0:
        return {
            "basis": "cohort",
            "cohortSize": cohort_size,
            "reliability": "insufficient",
            "factors": [],
            "caveat": (
                "Every recorded factor is constant across the cohort, so no "
                "factor can be distinguished from another."
            ),
        }

    factors = []
    for label, corr in raw:
        column = _COLUMN_FOR[label]
        factors.append(
            {
                "feature": label,
                "weight": round(abs(corr) / total, 4),
                # Sign of the correlation with survival: positive means the
                # factor tracks *better* recorded survival in this cohort.
                "direction": "positive" if corr >= 0 else "negative",
                "correlation": round(corr, 4),
                "patientValue": patient[column],
            }
        )
    factors.sort(key=lambda f: f["weight"], reverse=True)
    reliable = cohort_size >= _RELIABLE_COHORT
    caveat = (
        f"Correlation across {cohort_size} patient records in this database, "
        "normalised to relative weights. This describes the cohort - it is not "
        "an explanation of an individual prediction."
    )
    if not reliable:
        caveat += (
            f" With only {cohort_size} records the coefficients are unstable and "
            f"can reach 1.0 by coincidence; treat them as indicative until at "
            f"least {_RELIABLE_COHORT} patients are recorded."
        )
    return {
        "basis": "cohort",
        "cohortSize": cohort_size,
        "reliability": "reasonable" if reliable else "indicative",
        "factors": factors,
        "caveat": caveat,
    }


@router.post("/predictions/run", status_code=201)
async def run_prediction(
    payload: PredictionRequest,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    """Record a prediction run from the twin's current stored state.

    No inference happens: survival and risk are copied from the active twin
    version (falling back to the patient record), and `model` names that
    provenance so a reader is never misled into thinking a model ran.
    Confidence is omitted - there is no model to be confident.
    """
    patient = await resolve_patient(session, payload.patient_id)
    pid = str(patient["id"])
    active = (
        await session.execute(
            text(
                "SELECT version, survival, risk, model FROM twin_versions WHERE patient_id = :pid "
                "ORDER BY (status = 'Active') DESC, created_at DESC LIMIT 1"
            ),
            {"pid": pid},
        )
    ).mappings().first()

    # Nothing is defaulted here. A patient with no recorded survival used to
    # have 0.0 written into the run - which reads as a 0% five-year survival and
    # a 100% recurrence risk - and one with no recorded risk band was stored as
    # "low", turning an absent assessment into a reassuring clinical claim.
    raw_survival = active["survival"] if active else patient["survival_probability"]
    survival = float(raw_survival) if raw_survival is not None else None
    risk = (active["risk"] if active else patient["risk"]) or None
    now = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())

    await session.execute(
        text(
            """
            INSERT INTO prediction_runs
                (id, patient_id, date, twin_version, model, survival, recurrence,
                 response, confidence, status)
            VALUES
                (:id, :pid, :date, :twin_version, :model, :survival, :recurrence,
                 :response, :confidence, :status)
            """
        ),
        {
            "id": run_id,
            "pid": pid,
            "date": now,
            "twin_version": (active["version"] if active else None) or "none",
            "model": "Twin state snapshot (no model attached)",
            "survival": round(survival * 100, 1) if survival is not None else None,
            # Complement of recorded survival - a restatement of the stored
            # number, not a separately estimated recurrence risk. With no
            # survival on file there is nothing to take the complement of.
            "recurrence": round((1.0 - survival) * 100, 1) if survival is not None else None,
            # The column is named `response`; the value is a risk band. See the
            # note in _prediction_response.
            "response": risk,
            "confidence": None,
            "status": "Complete",
        },
    )
    await session.execute(
        text(
            # `kind` is constrained to diagnosis|treatment|scan|note, so a run
            # is filed as a note; the title carries what it actually was.
            "INSERT INTO timeline_events (id, patient_id, date, title, detail, kind) "
            "VALUES (:id, :pid, :date, :title, :detail, 'note')"
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": pid,
            "date": now,
            "title": "Prediction run recorded",
            "detail": f"Recorded from twin state ({(active['version'] if active else 'no twin version')}).",
        },
    )
    await session.commit()

    runs = await _history(session, pid)
    return {"ok": True, "data": runs[0] if runs else None, "message": "Prediction run recorded."}
