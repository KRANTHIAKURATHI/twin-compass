"""The active digital twin is the one authoritative clinical state for prediction and simulation.

No database: a recording fake session stands in for Postgres, so these tests pin the *logic* - which values a run is
built from and what a resync writes - not the SQL dialect.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.api.v1.routers import clinical, twins
from app.api.v1.routers.predictions import _wdbc_model_inputs
from app.core.exceptions import ValidationAppError
from app.services.response_model import project_scenarios
from app.services.twin_state import TWIN_CLINICAL_KEYS, active_twin_state, drifted_fields, missing_twin_fields

# What the twin froze (v2) versus what the patient row says today (edited after v2 was cut).
SNAPSHOT = {
    "age": 52, "stage": "II", "tumor_size_mm": 22.0, "grade": 2, "nodes_involved": 0, "ki67": 20.0,
    "er_status": "Positive", "pr_status": "Positive", "her2_status": "Positive", "risk": "low",
    "survival_probability": 0.9269,
}
PATIENT_ROW = {
    "id": "pid-1", "patient_code": "PT-1", "name": "N", "age": 52, "stage": "II", "tumor_size_mm": 30.0, "grade": 3,
    "nodes_involved": 1, "ki67": 45.0, "er_status": "Negative", "pr_status": "Negative", "her2_status": "Negative",
    "risk": "high", "survival_probability": 0.5,
}


class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    """Records every statement; answers the twin query and the version-list query from canned rows."""

    def __init__(self, twin=None, versions=()):
        self.twin = twin
        self.versions = list(versions)
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.calls.append((sql, params or {}))
        if "FROM twin_versions" in sql and "snapshot" in sql and "LIMIT 1" in sql:
            return _Result([self.twin] if self.twin else [])
        if "FROM twin_versions WHERE patient_id" in sql and "ORDER BY created_at DESC" in sql:
            return _Result(self.versions)
        return _Result([])


def _twin(snapshot=None, **columns):
    row = {"version": "v2", "snapshot": snapshot, "tumor_size_mm": None, "survival": None, "risk": None}
    row.update(columns)
    return row


def run(coro):
    return asyncio.run(coro)


# ---- the twin, not the patient row ------------------------------------------------------------------------


def test_active_twin_state_is_the_snapshot_and_ignores_newer_patient_values() -> None:
    session = FakeSession(twin=_twin(SNAPSHOT))
    state, version = run(active_twin_state(session, PATIENT_ROW))
    assert version == "v2"
    assert state == SNAPSHOT  # tumour 22 (not 30), ki67 20 (not 45), HER2 Positive (not Negative) ...
    assert set(state) == set(TWIN_CLINICAL_KEYS)


def test_a_field_the_twin_lacks_stays_missing_and_is_not_filled_from_the_patient_row() -> None:
    partial = {k: v for k, v in SNAPSHOT.items() if k not in ("ki67", "her2_status")}
    state, _ = run(active_twin_state(FakeSession(twin=_twin(partial)), PATIENT_ROW))
    assert state["ki67"] is None and state["her2_status"] is None
    assert missing_twin_fields(state) == ["ki67", "her2_status"]
    # An empty string is a missing value too, not a recorded one.
    blank = {**SNAPSHOT, "ki67": ""}
    assert run(active_twin_state(FakeSession(twin=_twin(blank)), PATIENT_ROW))[0]["ki67"] is None


def test_legacy_version_falls_back_only_to_its_own_columns_never_the_patient_row() -> None:
    legacy = _twin({}, tumor_size_mm=23.5, survival=0.91, risk="moderate")
    state, version = run(active_twin_state(FakeSession(twin=legacy), PATIENT_ROW))
    assert version == "v2"
    assert (state["tumor_size_mm"], state["survival_probability"], state["risk"]) == (23.5, 0.91, "moderate")
    assert state["ki67"] is None and state["er_status"] is None  # the row's 45 / Negative are NOT borrowed


def test_only_an_active_version_is_the_twin() -> None:
    session = FakeSession(twin=None)
    state, version = run(active_twin_state(session, PATIENT_ROW))
    assert version is None  # no Active twin -> the run records "none"
    assert state == {k: PATIENT_ROW.get(k) for k in TWIN_CLINICAL_KEYS}
    sql = session.calls[0][0].lower()
    assert "lower(status) = 'active'" in sql, "a Superseded/Archived version must never be picked up as the twin"


def test_drift_is_limited_to_the_clinical_state_a_twin_holds() -> None:
    assert drifted_fields(["ki67", "name", "phone"]) == ["ki67"]
    assert drifted_fields(["name", "email", "notes"]) == []
    assert "age" in TWIN_CLINICAL_KEYS


# ---- prediction and simulation read the same twin state -----------------------------------------------------


def test_prediction_input_is_the_twin_state_not_the_patient_row() -> None:
    session = FakeSession(twin=_twin(SNAPSHOT))
    state, _ = run(active_twin_state(session, PATIENT_ROW))
    fields = _wdbc_model_inputs(dict(state))
    assert fields["tumorSizeMm"] == 22.0 and fields["ki67"] == 20.0 and fields["her2Status"] == "Positive"
    assert fields["tumorSizeMm"] != PATIENT_ROW["tumor_size_mm"]


def test_prediction_refuses_when_the_twin_lacks_an_input_instead_of_using_the_row() -> None:
    partial = {k: v for k, v in SNAPSHOT.items() if k != "ki67"}
    state, _ = run(active_twin_state(FakeSession(twin=_twin(partial)), PATIENT_ROW))
    with pytest.raises(ValidationAppError) as err:
        _wdbc_model_inputs(dict(state))
    assert "ki67" in str(err.value)


def test_simulation_runs_on_the_same_twin_state_as_prediction() -> None:
    session = FakeSession(twin=_twin(SNAPSHOT))
    sim_state, sim_version = run(clinical._twin_state(session, PATIENT_ROW))
    pred_state, pred_version = run(active_twin_state(session, PATIENT_ROW))
    assert sim_state == pred_state and sim_version == pred_version == "v2"

    _, provenance = project_scenarios(
        tumor_size_mm=clinical._as_float(sim_state["tumor_size_mm"]),
        ki67=clinical._as_float(sim_state["ki67"]),
        er_status=sim_state["er_status"], pr_status=sim_state["pr_status"], her2_status=sim_state["her2_status"],
        survival_probability=clinical._as_float(sim_state["survival_probability"]),
        risk=sim_state["risk"], regimen="AC-T + Trastuzumab",
    )
    assert provenance["inputs"]["tumorSizeMm"] == 22.0 and provenance["inputs"]["ki67"] == 20.0
    assert provenance["inputs"]["HER2"] == "Positive" and provenance["subtype"] == "HER2-positive"


def test_simulation_is_unavailable_not_silently_filled_when_the_twin_lacks_ki67() -> None:
    partial = {k: v for k, v in SNAPSHOT.items() if k != "ki67"}
    state, _ = run(clinical._twin_state(FakeSession(twin=_twin(partial)), PATIENT_ROW))
    scenarios, provenance = project_scenarios(
        tumor_size_mm=22.0, ki67=clinical._as_float(state["ki67"]), er_status=state["er_status"],
        pr_status=state["pr_status"], her2_status=state["her2_status"], survival_probability=0.9, risk="low",
        regimen="AC-T + Trastuzumab",
    )
    assert "Ki-67" in (provenance["unavailableReason"] or "")
    assert all(s["tumorChange"] is None for s in scenarios)


# ---- resync -------------------------------------------------------------------------------------------------


def _version_row(version, status):
    return {
        "version": version, "created_at": "2026-01-01", "status": status, "author": "a", "summary": "s",
        "tumor_size_mm": 22.0, "survival": 0.9, "risk": "low", "model": "m",
    }


USER = SimpleNamespace(id="u1", email="doc@example.org")


def _cut(patient):
    session = FakeSession(versions=[_version_row("v2", "Active"), _version_row("v1", "Superseded")])
    out = run(twins.cut_twin_version(session, patient, USER))
    return session, out


def test_resync_supersedes_the_old_active_version_and_cuts_a_new_active_one_from_the_current_record() -> None:
    session, out = _cut(PATIENT_ROW)
    assert out == {"version": "v3", "previousVersion": "v2"}
    statements = [sql for sql, _ in session.calls]
    supersede = next(i for i, s in enumerate(statements) if "SET status = 'Superseded'" in s and "status = 'Active'" in s)
    insert = next(i for i, s in enumerate(statements) if s.startswith("INSERT INTO twin_versions"))
    assert supersede < insert, "the old Active version is superseded before the new one is inserted"
    assert "'Active'" in statements[insert]

    params = session.calls[insert][1]
    snapshot = json.loads(params["snapshot"])
    for key in TWIN_CLINICAL_KEYS:
        assert snapshot[key] == PATIENT_ROW[key], f"{key} was not preserved from the current patient record"
    assert (params["tumor_size_mm"], params["survival"], params["risk"]) == (30.0, 0.5, "high")


def test_resync_never_defaults_a_missing_value_and_names_the_gap() -> None:
    patient = {**PATIENT_ROW, "ki67": None, "grade": None}
    session, _ = _cut(patient)
    insert = next(c for c in session.calls if c[0].startswith("INSERT INTO twin_versions"))
    snapshot = json.loads(insert[1]["snapshot"])
    assert snapshot["ki67"] is None and snapshot["grade"] is None  # null, not 0 / "low" / a typical value
    assert "Not recorded: grade, ki67" in insert[1]["summary"] or "Not recorded: ki67, grade" in insert[1]["summary"]


def test_a_complete_resync_has_no_gap_note() -> None:
    session, _ = _cut(PATIENT_ROW)
    insert = next(c for c in session.calls if c[0].startswith("INSERT INTO twin_versions"))
    assert "Not recorded" not in insert[1]["summary"]
