from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.session import get_db_session
from app.dependencies.auth import CurrentUser, require_roles
from app.schemas.clinical import PatientInput, SimulationRequest
from app.services.clinical_queries import patient_uuid, resolve_patient
from app.services.response_model import project_scenarios

router = APIRouter(tags=["clinical"])


PATIENT_COLUMNS = (
    "patient_code, name, age, gender, phone, email, hospital, stage, tumor_size_mm, "
    "er_status, pr_status, her2_status, ki67, grade, nodes_involved, current_treatment, "
    "status, risk, survival_probability, last_updated, diagnosed_on, twin_status, history, notes"
)


def _patient_response(row) -> dict[str, object]:
    """Project a patient row for the API.

    Clinical facts are passed through as null when the record does not carry
    them. They used to be defaulted - a patient with no recorded HER2 status
    came back "Negative", a missing grade came back G1, a missing risk came
    back "low" - which turns an absent measurement into a clinical claim. Free
    text still collapses to "" because there the empty string *is* "nothing
    recorded" and the UI renders it the same way.
    """
    return {
        "id": row["patient_code"],
        "name": row["name"],
        "age": row["age"],
        "gender": row["gender"] or "",
        "phone": row["phone"] or "",
        "email": row["email"] or "",
        "hospital": row["hospital"] or "",
        "stage": row["stage"],
        "tumorSizeMm": row["tumor_size_mm"],
        "erStatus": row["er_status"],
        "prStatus": row["pr_status"],
        "her2Status": row["her2_status"],
        "ki67": row["ki67"],
        "grade": row["grade"],
        "nodesInvolved": row["nodes_involved"],
        "currentTreatment": row["current_treatment"] or "",
        "status": row["status"],
        "risk": row["risk"],
        "survivalProbability": row["survival_probability"],
        "lastUpdated": row["last_updated"] or "",
        "diagnosedOn": row["diagnosed_on"] or "",
        "twinStatus": row["twin_status"],
        "history": row["history"] or [],
        "notes": row["notes"] or "",
        "timeline": [],
        "reports": [],
    }


async def _research_rows(session: AsyncSession, table: str, order_by: str) -> list[dict[str, object]]:
    # Table names are fixed at call sites; values are never accepted from the request.
    result = await session.execute(text(f"SELECT * FROM {table} ORDER BY {order_by}"))
    return [dict(row) for row in result.mappings()]


@router.get("/research/models")
async def research_models(session: AsyncSession = Depends(get_db_session), _user: CurrentUser = Depends(require_roles("researcher", "admin"))):
    return await _research_rows(session, "ml_models", "name, version")


@router.get("/research/datasets")
async def research_datasets(session: AsyncSession = Depends(get_db_session), _user: CurrentUser = Depends(require_roles("researcher", "admin"))):
    return await _research_rows(session, "datasets", "name")


@router.get("/research/training-runs")
async def research_training_runs(session: AsyncSession = Depends(get_db_session), _user: CurrentUser = Depends(require_roles("researcher", "admin"))):
    return await _research_rows(session, "training_runs", "started DESC")


@router.get("/research/model-versions")
async def research_model_versions(session: AsyncSession = Depends(get_db_session), _user: CurrentUser = Depends(require_roles("researcher", "admin"))):
    return await _research_rows(session, "model_versions", "released DESC")


@router.get("/research/performance")
async def research_performance(session: AsyncSession = Depends(get_db_session), _user: CurrentUser = Depends(require_roles("researcher", "admin"))):
    return await _research_rows(session, "performance_points", "month")


def _simulation_response(row) -> dict[str, object]:
    return {
        "id": row["id"],
        "date": row["date"],
        "patient": row["patient_name"],
        # The stored column is the FK to patients.id; the frontend addresses
        # patients by their code everywhere else, so expose that instead and
        # fall back to the raw id for rows whose patient has since gone.
        "patientId": row["patient_code"] or row["patient_id"],
        "twinVersion": row["twin_version"],
        "model": row["model"],
        "selected": row["selected"],
        "compared": row["compared"] or [],
        "decision": row["decision"],
        "decidedBy": row["decided_by"],
        "notes": row["notes"] or "",
        "survival": row["survival"],
        "response": row["response"],
        "confidence": row["confidence"],
        # The scenarios exactly as they were recorded at run time, so reopening
        # a run shows what was actually decided on rather than recomputing it.
        "scenarios": row["scenarios"] or [],
    }


@router.get("/simulations")
async def list_simulations(
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
    patientId: str | None = None,
):
    # The patient detail page asks for one patient's runs; the simulations
    # index asks for all of them. Same shape either way.
    params: dict[str, object] = {}
    where = ""
    if patientId:
        params["pid"] = await patient_uuid(session, patientId)
        where = "WHERE sr.patient_id = :pid"
    result = await session.execute(
        text(
            "SELECT sr.*, p.patient_code FROM simulation_runs sr "
            "LEFT JOIN patients p ON p.id = sr.patient_id "
            f"{where} ORDER BY sr.date DESC"
        ),
        params,
    )
    return [_simulation_response(row) for row in result.mappings()]


@router.get("/simulations/{simulation_id}")
async def get_simulation(
    simulation_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
):
    row = (
        await session.execute(
            text(
                "SELECT sr.*, p.patient_code FROM simulation_runs sr "
                "LEFT JOIN patients p ON p.id = sr.patient_id "
                "WHERE sr.id = :id"
            ),
            {"id": simulation_id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Simulation run not found.")
    return _simulation_response(row)


@router.post("/simulations", status_code=status.HTTP_201_CREATED)
async def save_scenario(
    payload: SimulationRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    """Evaluate and persist a single custom regimen as its own run.

    Distinct from `/simulations/run`, which always projects the full set of
    dose-intensity variants for comparison. This projects only the "Current
    plan" variant - the one the builder's fields describe - and records it on
    its own, so a clinician can keep a scenario they typed without also
    generating three variants they did not ask to compare.
    """
    patient = (
        await session.execute(
            text(
                """
                SELECT id, patient_code, name, stage, tumor_size_mm, risk,
                       survival_probability, current_treatment,
                       ki67, er_status, pr_status, her2_status
                FROM patients
                WHERE deleted_at IS NULL AND (patient_code = :patient_id OR id = :patient_id)
                LIMIT 1
                """
            ),
            {"patient_id": payload.patient_id},
        )
    ).mappings().first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    state, twin_version = await _twin_state(session, patient)
    risk = str(state["risk"]).lower() if state["risk"] else None
    regimen = payload.regimen or patient["current_treatment"] or "Current treatment"

    scenarios, provenance = project_scenarios(
        tumor_size_mm=_as_float(state["tumor_size_mm"]),
        ki67=_as_float(state["ki67"]),
        er_status=state["er_status"],  # type: ignore[arg-type]
        pr_status=state["pr_status"],  # type: ignore[arg-type]
        her2_status=state["her2_status"],  # type: ignore[arg-type]
        survival_probability=_as_float(state["survival_probability"]),
        risk=risk,
        regimen=regimen,
        duration_weeks=payload.duration_weeks,
    )
    # The first variant is always "Current plan" (intensity 1.0, no toxicity
    # or recovery multiplier) - the one un-modified projection of the regimen
    # as given, which is what "save this scenario" means here.
    scenario = scenarios[0]
    if payload.name:
        scenario = {**scenario, "name": payload.name}

    now = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    await session.execute(
        text(
            """
            INSERT INTO simulation_runs
                (id, date, patient_id, patient_name, twin_version, model, selected,
                 compared, decision, decided_by, notes, survival, response, confidence, scenarios)
            VALUES
                (:id, :date, :patient_id, :patient_name, :twin_version, :model, :selected,
                 CAST(:compared AS jsonb), :decision, :decided_by, :notes, :survival,
                 :response, :confidence, CAST(:scenarios AS jsonb))
            """
        ),
        {
            "id": run_id,
            "date": now,
            "patient_id": patient["id"],
            "patient_name": patient["name"],
            "twin_version": twin_version or "none",
            "model": provenance["model"] if provenance["unavailableReason"] is None else None,
            "selected": scenario["name"],
            "compared": json.dumps([scenario["name"]]),
            # Distinct from a comparison run's "Under review" so the list and
            # detail pages show at a glance that this was saved, not run for
            # a decision between variants.
            "decision": "Saved",
            "decided_by": str(current_user.id),
            "notes": payload.notes or "Scenario saved without a full variant comparison.",
            "survival": scenario["survival5y"],
            "response": scenario["predictedResponse"],
            "confidence": scenario["confidence"],
            "scenarios": json.dumps([scenario]),
        },
    )
    await session.commit()
    row = (
        await session.execute(
            text(
                "SELECT sr.*, p.patient_code FROM simulation_runs sr "
                "LEFT JOIN patients p ON p.id = sr.patient_id WHERE sr.id = :id"
            ),
            {"id": run_id},
        )
    ).mappings().one()
    return {"ok": True, "data": _simulation_response(row), "message": "Scenario saved."}


@router.post("/simulations/{simulation_id}/duplicate", status_code=status.HTTP_201_CREATED)
async def duplicate_simulation(
    simulation_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    """Clone a persisted run's configuration and results under a new id.

    The clone starts back at "Under review" regardless of what the original
    had decided - a duplicate is a new starting point for review, not a
    second copy of a decision already made, so it never inherits "Promoted to
    plan" and never touches `treatment_plans`.
    """
    original = (
        await session.execute(text("SELECT * FROM simulation_runs WHERE id = :id"), {"id": simulation_id})
    ).mappings().first()
    if original is None:
        raise HTTPException(status_code=404, detail="Simulation run not found.")

    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await session.execute(
        text(
            """
            INSERT INTO simulation_runs
                (id, date, patient_id, patient_name, twin_version, model, selected,
                 compared, decision, decided_by, notes, survival, response, confidence, scenarios)
            VALUES
                (:id, :date, :patient_id, :patient_name, :twin_version, :model, :selected,
                 CAST(:compared AS jsonb), :decision, :decided_by, :notes, :survival,
                 :response, :confidence, CAST(:scenarios AS jsonb))
            """
        ),
        {
            "id": new_id,
            "date": now,
            "patient_id": original["patient_id"],
            "patient_name": original["patient_name"],
            "twin_version": original["twin_version"],
            "model": original["model"],
            "selected": original["selected"],
            "compared": json.dumps(original["compared"] or []),
            "decision": "Under review",
            "decided_by": str(current_user.id),
            "notes": f"Duplicated from simulation {simulation_id}.",
            "survival": original["survival"],
            "response": original["response"],
            "confidence": original["confidence"],
            "scenarios": json.dumps(original["scenarios"] or []),
        },
    )
    await session.commit()
    row = (
        await session.execute(
            text(
                "SELECT sr.*, p.patient_code FROM simulation_runs sr "
                "LEFT JOIN patients p ON p.id = sr.patient_id WHERE sr.id = :id"
            ),
            {"id": new_id},
        )
    ).mappings().one()
    return {"ok": True, "data": _simulation_response(row), "message": "Simulation duplicated."}


@router.post("/simulations/{simulation_id}/promote")
async def promote_simulation(
    simulation_id: str,
    payload: dict[str, str] | None = None,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "admin")),
):
    simulation = (await session.execute(text("SELECT * FROM simulation_runs WHERE id = :id"), {"id": simulation_id})).mappings().first()
    if simulation is None:
        raise HTTPException(status_code=404, detail="Simulation run not found.")

    scenarios = simulation["scenarios"] or []
    selected = next((item for item in scenarios if item.get("name") == simulation["selected"]), None)
    regimen = selected.get("regimen") if selected else simulation["selected"]
    plan_id = str(uuid.uuid4())
    started_on = datetime.now(timezone.utc).date().isoformat()
    next_dose = datetime.now(timezone.utc).date().isoformat()
    await session.execute(
        text(
            """
            INSERT INTO treatment_plans
                (id, patient_id, regimen, cycle, total_cycles, started_on, next_dose,
                 adherence, side_effects, medications)
            VALUES
                (:id, :patient_id, :regimen, 1, 6, :started_on, :next_dose, 0,
                 CAST(:side_effects AS jsonb), CAST(:medications AS jsonb))
            """
        ),
        {
            "id": plan_id,
            "patient_id": simulation["patient_id"],
            "regimen": regimen,
            "started_on": started_on,
            "next_dose": next_dose,
            "side_effects": json.dumps([]),
            "medications": json.dumps([]),
        },
    )
    await session.execute(
        text("UPDATE simulation_runs SET decision = 'Promoted to plan', notes = :notes WHERE id = :id"),
        {"id": simulation_id, "notes": (payload or {}).get("notes") or "Promoted to treatment plan."},
    )
    await session.commit()
    return {"ok": True, "data": {"id": plan_id}, "message": "Simulation promoted to treatment plan."}


async def _twin_state(session: AsyncSession, patient: Mapping[str, object]) -> tuple[dict[str, object], str | None]:
    """The state a simulation runs against: the active twin, else the patient row.

    A simulation asks "what would this treatment do to *this* tumour", so the
    tumour it starts from has to be the twin's - the versioned, reviewed snapshot
    a clinician signed off on. The patients table holds the same fields but they
    are the live, unversioned values; a run recorded against them cannot be
    reproduced later because nothing pins down what they were at the time.

    Returns the merged state and the twin version it came from (None when the
    patient has no twin yet, in which case the patient row is all there is).
    """
    twin = (
        await session.execute(
            text(
                """
                SELECT version, snapshot, tumor_size_mm, survival, risk
                FROM twin_versions
                WHERE patient_id = :pid
                ORDER BY CASE WHEN lower(status) = 'active' THEN 0 ELSE 1 END, created_at DESC
                LIMIT 1
                """
            ),
            {"pid": patient["id"]},
        )
    ).mappings().first()

    state: dict[str, object] = {
        key: patient[key]
        for key in (
            "tumor_size_mm", "survival_probability", "risk", "stage",
            "ki67", "er_status", "pr_status", "her2_status",
        )
    }
    if twin is None:
        return state, None

    # The snapshot jsonb is the richest record - it is what the twin was built
    # from. The version's own columns are the fallback for anything missing.
    snapshot = twin["snapshot"] if isinstance(twin["snapshot"], dict) else {}
    for key in state:
        value = snapshot.get(key)
        if value is not None and value != "":
            state[key] = value
    for snapshot_key, column in (("tumor_size_mm", "tumor_size_mm"), ("survival_probability", "survival"), ("risk", "risk")):
        if state[snapshot_key] is None and twin[column] is not None:
            state[snapshot_key] = twin[column]
    return state, twin["version"]


def _as_float(value: object) -> float | None:
    """Snapshot values arrive as whatever was written into the jsonb."""
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


@router.get("/patients")
async def list_patients(
    session: AsyncSession = Depends(get_db_session),
    _current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
    search: str | None = None,
) -> list[dict[str, object]]:
    search_clause = "AND (name ILIKE :search OR patient_code ILIKE :search)" if search else ""
    result = await session.execute(
        text(
            f"SELECT {PATIENT_COLUMNS} FROM patients WHERE deleted_at IS NULL {search_clause} ORDER BY patient_code"
        ),
        {"search": f"%{search}%"} if search else {},
    )
    return [_patient_response(row) for row in result.mappings()]


@router.post("/patients", status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientInput,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    next_code = (
        await session.execute(
            text("SELECT COALESCE(MAX(CAST(SUBSTR(patient_code, 4) AS INTEGER)), 999) + 1 FROM patients WHERE patient_code LIKE 'PT-%'")
        )
    ).scalar_one()
    # `patients.created_by` still references the legacy `users` table, but the
    # active login identity is a `profiles` id. Only store it when it resolves
    # there (so the FK holds); otherwise leave it NULL and record the actor in
    # `audit_logs` instead. The FK itself is intentionally untouched.
    actor_id = str(current_user.id)
    legacy_user = (await session.execute(text("SELECT id FROM users WHERE id = :uid"), {"uid": actor_id})).scalar()
    values = payload.model_dump(exclude_none=True)
    values.update({"id": str(uuid.uuid4()), "patient_code": f"PT-{next_code}"})
    if legacy_user is not None:
        values["created_by"] = legacy_user
    columns = ", ".join(values)
    params = ", ".join(f":{key}" for key in values)
    try:
        await session.execute(text(f"INSERT INTO patients ({columns}) VALUES ({params})"), values)
        await session.execute(
            text(
                "INSERT INTO audit_logs (id, time, actor, actor_role, action, target, after) "
                "VALUES (:id, :time, :actor, :role, 'patient.created', :target, :after)"
            ),
            {
                "id": str(uuid.uuid4()),
                "time": datetime.now(timezone.utc).isoformat(),
                "actor": current_user.email or actor_id,
                "role": str(current_user.role),
                "target": values["patient_code"],
                "after": json.dumps({"actorId": actor_id, "patientId": values["id"]}),
            },
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("The patient could not be saved because it conflicts with existing data.") from exc
    row = (await session.execute(text(f"SELECT {PATIENT_COLUMNS} FROM patients WHERE patient_code = :code"), {"code": values["patient_code"]})).mappings().one()
    return {"ok": True, "data": _patient_response(row), "message": "Patient created."}


@router.patch("/patients/{patient_id}")
async def update_patient(
    patient_id: str,
    payload: PatientInput,
    session: AsyncSession = Depends(get_db_session),
    _current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    values = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not values:
        raise HTTPException(status_code=400, detail="At least one patient field is required.")
    assignments = ", ".join(f"{key} = :{key}" for key in values)
    values["patient_id"] = patient_id
    result = await session.execute(text(f"UPDATE patients SET {assignments} WHERE deleted_at IS NULL AND (patient_code = :patient_id OR id = :patient_id) RETURNING {PATIENT_COLUMNS}"), values)
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    await session.commit()
    return {"ok": True, "data": _patient_response(row), "message": "Patient updated."}


@router.delete("/patients/{patient_id}")
async def delete_patient(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    result = await session.execute(text("UPDATE patients SET deleted_at = now() WHERE deleted_at IS NULL AND (patient_code = :patient_id OR id = :patient_id)"), {"patient_id": patient_id})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Patient not found.")
    await session.commit()
    return {"ok": True, "message": "Patient removed."}


def _timeline_response(row) -> dict[str, object]:
    return {
        "date": row["date"],
        "title": row["title"],
        "detail": row["detail"] or "",
        "kind": row["kind"] or "note",
    }


async def _timeline_for(session: AsyncSession, patient_uuid: str) -> list[dict[str, object]]:
    result = await session.execute(
        text("SELECT date, title, detail, kind FROM timeline_events WHERE patient_id = :pid ORDER BY date DESC"),
        {"pid": patient_uuid},
    )
    return [_timeline_response(row) for row in result.mappings()]


async def _reports_for(session: AsyncSession, patient_uuid: str) -> list[dict[str, object]]:
    result = await session.execute(
        text(
            "SELECT title, type, created, version FROM reports WHERE patient_id = :pid ORDER BY created DESC"
        ),
        {"pid": patient_uuid},
    )
    return [
        {
            "name": row["title"],
            "type": row["type"] or "Report",
            "date": row["created"],
            # `reports` stores no byte size; the version is the useful fact
            # to surface in its place rather than inventing a file size.
            "size": f"v{row['version'] or 1}",
        }
        for row in result.mappings()
    ]


@router.get("/patients/{patient_id}")
async def get_patient(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    patient = await resolve_patient(session, patient_id)
    response = _patient_response(patient)
    response["timeline"] = await _timeline_for(session, str(patient["id"]))
    response["reports"] = await _reports_for(session, str(patient["id"]))
    return response


@router.get("/patients/{patient_id}/labs")
async def patient_labs(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> list[dict[str, object]]:
    patient = await resolve_patient(session, patient_id)
    result = await session.execute(
        text(
            'SELECT date, panel, marker, value, unit, "range", flag '
            "FROM lab_results WHERE patient_id = :pid ORDER BY date DESC, panel, marker"
        ),
        {"pid": str(patient["id"])},
    )
    return [
        {
            "date": row["date"],
            "panel": row["panel"] or "",
            "marker": row["marker"] or "",
            "value": row["value"] or "",
            "unit": row["unit"] or "",
            "range": row["range"] or "",
            "flag": row["flag"] or "normal",
        }
        for row in result.mappings()
    ]


@router.get("/patients/{patient_id}/imaging")
async def patient_imaging(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> list[dict[str, object]]:
    patient = await resolve_patient(session, patient_id)
    result = await session.execute(
        text(
            "SELECT id, modality, region, date, finding, radiologist, status "
            "FROM imaging_studies WHERE patient_id = :pid ORDER BY date DESC"
        ),
        {"pid": str(patient["id"])},
    )
    return [
        {
            "id": row["id"],
            "modality": row["modality"] or "",
            "region": row["region"] or "",
            "date": row["date"],
            "finding": row["finding"] or "",
            "radiologist": row["radiologist"] or "",
            "status": row["status"] or "Pending",
        }
        for row in result.mappings()
    ]


@router.get("/patients/{patient_id}/timeline")
async def patient_timeline(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> list[dict[str, object]]:
    patient = await resolve_patient(session, patient_id)
    return await _timeline_for(session, str(patient["id"]))


@router.get("/patients/{patient_id}/treatment-plan")
async def patient_treatment_plan(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    _current_user: CurrentUser = Depends(require_roles("doctor", "patient", "admin")),
) -> dict[str, object] | None:
    patient = await resolve_patient(session, patient_id)
    row = (
        await session.execute(
            text(
                "SELECT regimen, cycle, total_cycles, started_on, next_dose, adherence, "
                "side_effects, medications FROM treatment_plans WHERE patient_id = :pid "
                "ORDER BY started_on DESC LIMIT 1"
            ),
            {"pid": str(patient["id"])},
        )
    ).mappings().first()
    # No plan is a legitimate state (nothing prescribed yet), not an error -
    # the UI renders its empty state from a null body.
    if row is None:
        return None
    return {
        "regimen": row["regimen"] or "",
        "cycle": row["cycle"] or 0,
        "totalCycles": row["total_cycles"] or 0,
        "startedOn": row["started_on"],
        "nextDose": row["next_dose"],
        "adherence": row["adherence"] or 0,
        "sideEffects": row["side_effects"] or [],
        "medications": row["medications"] or [],
    }


@router.post("/simulations/run", status_code=status.HTTP_201_CREATED)
async def run_simulation(
    payload: SimulationRequest,
    session: AsyncSession = Depends(get_db_session),
    # Matches list/get/promote: running a comparison against a twin is a
    # clinical decision-support action, not something a patient account
    # should be able to trigger against any patient_id it names.
    current_user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    patient = (
        await session.execute(
            text(
                """
                SELECT id, patient_code, name, stage, tumor_size_mm, risk,
                       survival_probability, current_treatment,
                       ki67, er_status, pr_status, her2_status
                FROM patients
                WHERE deleted_at IS NULL AND (patient_code = :patient_id OR id = :patient_id)
                LIMIT 1
                """
            ),
            {"patient_id": payload.patient_id},
        )
    ).mappings().first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    state, twin_version = await _twin_state(session, patient)
    # No default risk band. An unassessed patient is unassessed, not moderate.
    risk = str(state["risk"]).lower() if state["risk"] else None
    regimen = payload.regimen or patient["current_treatment"] or "Current treatment"

    scenarios, provenance = project_scenarios(
        tumor_size_mm=_as_float(state["tumor_size_mm"]),
        ki67=_as_float(state["ki67"]),
        er_status=state["er_status"],  # type: ignore[arg-type]
        pr_status=state["pr_status"],  # type: ignore[arg-type]
        her2_status=state["her2_status"],  # type: ignore[arg-type]
        # Null when the patient has no recorded probability - not 0.0, which
        # would display as a 0% five-year survival on every card.
        survival_probability=_as_float(state["survival_probability"]),
        risk=risk,
        regimen=regimen,
        duration_weeks=payload.duration_weeks,
    )
    # The patient's current plan is the baseline the others are compared against.
    # It is not a recommendation: the projection ranks tumour kill, which is only
    # one of the things a clinician weighs against toxicity and the patient's own
    # priorities, so the choice stays with them.
    selected = scenarios[0]
    now = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    await session.execute(
        text(
            """
            INSERT INTO simulation_runs
                (id, date, patient_id, patient_name, twin_version, model, selected,
                 compared, decision, decided_by, notes, survival, response, confidence, scenarios)
            VALUES
                (:id, :date, :patient_id, :patient_name, :twin_version, :model, :selected,
                 CAST(:compared AS jsonb), :decision, :decided_by, :notes, :survival,
                 :response, :confidence, CAST(:scenarios AS jsonb))
            """
        ),
        {
            "id": run_id,
            "date": now,
            # simulation_runs.patient_id is a FK to patients.id (the internal
            # uuid), not to the human-facing patient_code the API speaks in -
            # inserting the code here raised an IntegrityError on every run.
            "patient_id": patient["id"],
            "patient_name": patient["name"],
            # The twin the projection actually ran against, so a stored run can
            # be traced back to the state that produced it. It used to say
            # "current", which identifies nothing once the twin moves on.
            "twin_version": twin_version or "none",
            # Named only when the projection ran. A run that produced no numbers
            # was produced by no model.
            "model": provenance["model"] if provenance["unavailableReason"] is None else None,
            "selected": selected["name"],
            "compared": json.dumps([item["name"] for item in scenarios]),
            "decision": "Under review",
            "decided_by": str(current_user.id),
            "notes": payload.notes or "Scenario comparison projected from the active digital twin.",
            "survival": selected["survival5y"],
            "response": selected["predictedResponse"],
            "confidence": selected["confidence"],
            "scenarios": json.dumps(scenarios),
        },
    )
    await session.commit()
    return {
        "id": run_id,
        "patientId": patient["patient_code"],
        "scenarios": scenarios,
        # Carried to the UI so every card can say where its numbers came from,
        # and so an empty comparison can say why it is empty.
        "provenance": provenance,
    }
