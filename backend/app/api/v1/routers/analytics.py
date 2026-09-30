"""
Analytics router - every figure aggregated from rows in this database.

Two rules this module follows, because the dashboards it feeds are the
easiest place for invented numbers to look authoritative:

  1. No back-filling. A series covers the periods the data actually spans.
     Five patients produce a five-patient chart, not a smoothed year.
  2. No deltas without a baseline. A "+4.2% this month" needs a previous
     month to compare against; where the data cannot support one the delta
     is `null` and the UI omits the chip rather than printing a made-up
     trend.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.dependencies.auth import CurrentUser, require_roles

router = APIRouter(tags=["analytics"])

RISK_BANDS = ("low", "moderate", "high")

AGE_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("0-24", 0, 24),
    ("25-34", 25, 34),
    ("35-44", 35, 44),
    ("45-54", 45, 54),
    ("55-64", 55, 64),
    ("65-74", 65, 74),
    ("75+", 75, 200),
)


def _month_key(value: object) -> str | None:
    """`2026-08-19T...` -> `2026-08`. None when unparseable."""
    if not value:
        return None
    raw = str(value)[:10]
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m")
    except ValueError:
        return None


async def _scalar(session: AsyncSession, sql: str) -> float:
    return (await session.execute(text(sql))).scalar() or 0


@router.get("/analytics/dashboard")
async def dashboard(
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    total_patients = await _scalar(session, "SELECT count(*) FROM patients WHERE deleted_at IS NULL")
    # Joined to patients so a soft-deleted patient's twin stops being counted
    # the moment the patient is removed from every other figure on the page.
    active_twins = await _scalar(
        session,
        "SELECT count(DISTINCT t.patient_id) FROM twin_versions t "
        "JOIN patients p ON p.id = t.patient_id "
        "WHERE t.status = 'Active' AND p.deleted_at IS NULL",
    )
    high_risk = await _scalar(
        session, "SELECT count(*) FROM patients WHERE deleted_at IS NULL AND lower(risk) = 'high'"
    )
    # Both scoped to live patients for the same reason as the twin count -
    # every stat on this page describes the same cohort or none of them do.
    simulations = await _scalar(
        session,
        "SELECT count(*) FROM simulation_runs s JOIN patients p ON p.id = s.patient_id "
        "WHERE p.deleted_at IS NULL",
    )
    predictions = await _scalar(
        session,
        "SELECT count(*) FROM prediction_runs r JOIN patients p ON p.id = r.patient_id "
        "WHERE p.deleted_at IS NULL",
    )
    avg_survival = (
        await session.execute(
            text(
                "SELECT avg(survival_probability) FROM patients "
                "WHERE deleted_at IS NULL AND survival_probability IS NOT NULL"
            )
        )
    ).scalar()

    model = (
        await session.execute(
            text("SELECT name, version, auc, status FROM ml_models ORDER BY version DESC LIMIT 1")
        )
    ).mappings().first()

    stats = [
        {"key": "patients", "label": "Total Patients", "value": int(total_patients), "format": "count"},
        {"key": "twins", "label": "Active Digital Twins", "value": int(active_twins), "format": "count"},
        {"key": "highRisk", "label": "High Risk Patients", "value": int(high_risk), "format": "count"},
        {"key": "simulations", "label": "Treatment Simulations", "value": int(simulations), "format": "count"},
        {"key": "predictions", "label": "Prediction Runs", "value": int(predictions), "format": "count"},
        {
            "key": "survival",
            "label": "Avg. Survival Probability",
            # Averaged over the patients that actually carry a recorded
            # probability; null when none do.
            "value": round(float(avg_survival) * 100, 1) if avg_survival is not None else None,
            "format": "percent",
        },
    ]

    return {
        "stats": stats,
        "model": (
            {
                "name": model["name"],
                "version": model["version"],
                "auc": model["auc"],
                "status": model["status"],
            }
            if model
            else None
        ),
        "patientGrowth": await _patient_growth(session),
        "riskDistribution": await _risk_distribution(session),
        "stageDistribution": await _stage_distribution(session),
        "treatmentComparison": await _treatment_comparison(session),
        "accuracy": await _accuracy(session),
        "recentActivity": await _recent_activity(session),
        "followUps": await _follow_ups(session),
    }


@router.get("/analytics/cohort")
async def cohort(
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    return {
        "ageDistribution": await _age_distribution(session),
        "stageDistribution": await _stage_distribution(session),
        "riskDistribution": await _risk_distribution(session),
        "treatmentComparison": await _treatment_comparison(session),
        "survivalByRisk": await _survival_by_risk(session),
    }


@router.get("/analytics/accuracy")
async def accuracy(
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    return await _accuracy(session)


# --------------------------------------------------------------------------
# Aggregations
# --------------------------------------------------------------------------


async def _patient_growth(session: AsyncSession) -> list[dict[str, object]]:
    """Cumulative patients and twins per calendar month actually present."""
    patient_months = [
        _month_key(r["created_at"] or r["diagnosed_on"])
        for r in (
            await session.execute(
                text("SELECT created_at, diagnosed_on FROM patients WHERE deleted_at IS NULL")
            )
        ).mappings()
    ]
    twin_months = [
        _month_key(r["created_at"])
        for r in (
            await session.execute(
                text(
                    "SELECT t.created_at FROM twin_versions t "
                    "JOIN patients p ON p.id = t.patient_id WHERE p.deleted_at IS NULL"
                )
            )
        ).mappings()
    ]
    patient_counts = Counter(m for m in patient_months if m)
    twin_counts = Counter(m for m in twin_months if m)

    months = sorted(set(patient_counts) | set(twin_counts))
    series: list[dict[str, object]] = []
    running_patients = running_twins = 0
    for month in months:
        running_patients += patient_counts.get(month, 0)
        running_twins += twin_counts.get(month, 0)
        series.append({"month": month, "patients": running_patients, "twins": running_twins})
    return series


async def _risk_distribution(session: AsyncSession) -> list[dict[str, object]]:
    rows = (
        await session.execute(
            text(
                "SELECT lower(coalesce(risk, 'low')) AS risk, count(*) AS n "
                "FROM patients WHERE deleted_at IS NULL GROUP BY 1"
            )
        )
    ).mappings().all()
    counts = {r["risk"]: r["n"] for r in rows}
    # Bands with no patients are kept at zero so the legend stays stable
    # rather than the chart silently changing shape between refreshes.
    return [
        {"key": band, "name": f"{band.capitalize()} risk", "value": counts.get(band, 0)}
        for band in RISK_BANDS
    ]


async def _stage_distribution(session: AsyncSession) -> list[dict[str, object]]:
    rows = (
        await session.execute(
            text(
                "SELECT coalesce(nullif(stage, ''), 'Unknown') AS stage, count(*) AS n "
                "FROM patients WHERE deleted_at IS NULL GROUP BY 1 ORDER BY 1"
            )
        )
    ).mappings().all()
    return [{"stage": f"Stage {r['stage']}" if r["stage"] != "Unknown" else "Unknown", "count": r["n"]} for r in rows]


async def _age_distribution(session: AsyncSession) -> list[dict[str, object]]:
    ages = [
        r["age"]
        for r in (
            await session.execute(
                text("SELECT age FROM patients WHERE deleted_at IS NULL AND age IS NOT NULL AND age > 0")
            )
        ).mappings()
    ]
    buckets = OrderedDict((label, 0) for label, _, _ in AGE_BUCKETS)
    for age in ages:
        for label, low, high in AGE_BUCKETS:
            if low <= age <= high:
                buckets[label] += 1
                break
    return [{"range": label, "count": count} for label, count in buckets.items()]


async def _treatment_comparison(session: AsyncSession) -> list[dict[str, object]]:
    """Recorded response per selected regimen, from simulation runs.

    `recurrence` is the complement of the recorded 5-year survival for those
    runs - a restatement of stored numbers, not a separate estimate.
    """
    rows = (
        await session.execute(
            text(
                "SELECT s.selected AS treatment, avg(s.response) AS response, "
                "avg(s.survival) AS survival, count(*) AS runs "
                "FROM simulation_runs s JOIN patients p ON p.id = s.patient_id "
                "WHERE p.deleted_at IS NULL AND s.selected IS NOT NULL AND s.selected <> '' "
                "GROUP BY s.selected ORDER BY count(*) DESC, s.selected"
            )
        )
    ).mappings().all()
    return [
        {
            "treatment": r["treatment"],
            "response": round(float(r["response"] or 0), 1),
            "recurrence": round(100 - float(r["survival"] or 0), 1),
            "runs": r["runs"],
        }
        for r in rows
    ]


async def _accuracy(session: AsyncSession) -> dict[str, object]:
    """Validation performance of the registered model.

    `performance_points` holds cross-validation folds, not a monthly time
    series - the label is carried through as-is so the chart cannot imply
    improvement over time that was never measured.
    """
    rows = (
        await session.execute(
            text("SELECT month, auc, precision, recall FROM performance_points ORDER BY month")
        )
    ).mappings().all()
    model = (
        await session.execute(
            text("SELECT name, version, auc, task, status FROM ml_models ORDER BY version DESC LIMIT 1")
        )
    ).mappings().first()
    return {
        "series": [
            {
                "label": r["month"],
                "auc": r["auc"],
                "precision": r["precision"],
                "recall": r["recall"],
            }
            for r in rows
        ],
        "seriesKind": "cross-validation-folds",
        "model": (
            {
                "name": model["name"],
                "version": model["version"],
                "auc": model["auc"],
                "task": model["task"],
                "status": model["status"],
            }
            if model
            else None
        ),
    }


async def _survival_by_risk(session: AsyncSession) -> dict[str, object]:
    """Average recorded survival probability per risk band.

    Deliberately two anchor points per band, not a six-point curve: baseline
    (100% at diagnosis, true by definition) and the recorded probability
    this database actually stores. The intermediate years in the old chart
    were invented; there is no longitudinal survival data here to fill them.
    """
    rows = (
        await session.execute(
            text(
                "SELECT lower(coalesce(risk, 'low')) AS risk, avg(survival_probability) AS s, "
                "count(*) AS n FROM patients WHERE deleted_at IS NULL "
                "AND survival_probability IS NOT NULL GROUP BY 1"
            )
        )
    ).mappings().all()
    by_band = {r["risk"]: (float(r["s"]), r["n"]) for r in rows}

    baseline: dict[str, object] = {"point": "At diagnosis"}
    recorded: dict[str, object] = {"point": "Recorded probability"}
    cohort_sizes: dict[str, int] = {}
    for band in RISK_BANDS:
        value, n = by_band.get(band, (None, 0))
        baseline[band] = 100 if n else None
        recorded[band] = round(value * 100, 1) if value is not None else None
        cohort_sizes[band] = n

    return {
        "points": [baseline, recorded],
        "cohortSizes": cohort_sizes,
        "caveat": (
            "Average of the survival probability recorded on each patient "
            "record, grouped by risk band. Not a longitudinal survival curve - "
            "this database holds no year-by-year outcome data."
        ),
    }


async def _recent_activity(session: AsyncSession) -> list[dict[str, object]]:
    """Newest audit-log entries, which is the only real activity feed here."""
    rows = (
        await session.execute(
            text(
                "SELECT time, actor, actor_role, action, target FROM audit_logs "
                "ORDER BY time DESC LIMIT 8"
            )
        )
    ).mappings().all()
    return [
        {
            "title": (r["action"] or "activity").replace("_", " ").capitalize(),
            "detail": f"{r['actor'] or 'system'} · {r['target'] or ''}".strip(" ·"),
            "time": r["time"],
            "actorRole": r["actor_role"] or "",
        }
        for r in rows
    ]


async def _follow_ups(session: AsyncSession) -> list[dict[str, object]]:
    """Upcoming appointments. Empty until appointments are recorded."""
    now = datetime.now(timezone.utc).isoformat()
    rows = (
        await session.execute(
            text(
                "SELECT a.id, a.title, a.date, a.time, a.status, p.patient_code, p.name "
                "FROM appointments a LEFT JOIN patients p ON p.id = a.patient_id "
                "WHERE a.date >= :now AND lower(coalesce(a.status,'')) <> 'cancelled' "
                "ORDER BY a.date ASC, a.time ASC LIMIT 6"
            ),
            {"now": now[:10]},
        )
    ).mappings().all()
    return [
        {
            "patient": r["name"] or "Unknown",
            "id": r["patient_code"],
            "when": f"{r['date']} · {r['time']}".strip(" ·"),
            "type": r["title"] or "Appointment",
        }
        for r in rows
    ]
