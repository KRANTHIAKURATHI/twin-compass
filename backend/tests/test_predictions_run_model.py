"""
POST /predictions/run is wired to the existing `app.ml` model.

The run SQL is portable, so it runs against the per-test SQLite database with
fixture tables shaped like the live ones (the real tables live in Supabase
Postgres). A fake model is injected through `set_prediction_model` for most
cases; one test uses the real artifact and skips if the ML runtime is absent.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from app.ml import interface
from app.ml.interface import ModelMetadata, PredictionModel, set_prediction_model
from tests.conftest import login, register

_PATIENT_COLS = (
    "id, patient_code, name, age, gender, phone, email, hospital, stage, tumor_size_mm, "
    "er_status, pr_status, her2_status, ki67, grade, nodes_involved, current_treatment, "
    "status, risk, survival_probability, last_updated, diagnosed_on, twin_status, history, "
    "notes, deleted_at"
)
SNAPSHOT_LABEL = "Twin state snapshot (no model attached)"


class _FakeModel(PredictionModel):
    def __init__(self, error: Exception | None = None):
        self.error, self.calls = error, []

    @property
    def metadata(self):
        return ModelMetadata(name="Fake Model", version="v9", dataset_name="x", trained_at="")

    def predict(self, patient_fields):
        self.calls.append(patient_fields)
        if self.error:
            raise self.error
        return {"survival": 0.9, "recurrence": 0.2, "confidence": 0.85, "risk": "moderate",
                "response": "Favorable", "status": "Complete"}

    def explain(self, patient_fields, top_n=8): return []
    def simulate(self, patient_fields, regimen_name): return {}
    def simulate_all(self, patient_fields): return []
    def regimen_names(self): return []


@pytest.fixture(autouse=True)
def _reset_model():
    yield
    set_prediction_model(None)


@pytest.fixture()
def db(db_sessionmaker, client):
    """Creates the fixture tables, one patient, and returns a query helper."""

    def run(sql, params=None, fetch=False):
        async def _go():
            async with db_sessionmaker() as s:
                res = await s.execute(text(sql), params or {})
                await s.commit()
                return [dict(r) for r in res.mappings()] if fetch else None

        return asyncio.run(_go())

    run(f"CREATE TABLE patients ({_PATIENT_COLS})")
    run("CREATE TABLE twin_versions (patient_id, version, status, created_at)")
    run("CREATE TABLE prediction_runs (id, patient_id, date, twin_version, model, survival, "
        "recurrence, response, confidence, status)")
    run("CREATE TABLE timeline_events (id, patient_id, date, title, detail, kind)")
    run("INSERT INTO patients (id, patient_code, name, age, stage, tumor_size_mm, er_status, pr_status, "
        "her2_status, ki67, grade, nodes_involved) VALUES ('p1', 'PT-1', 'Pat One', 55, 'II', 25, "
        "'Positive', 'Positive', 'Negative', NULL, 2, 1)")
    return run


def _doctor_headers(client):
    register(client, email="pred-doc@example.com", role="doctor")
    token = login(client, email="pred-doc@example.com").json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_run_invokes_model_and_records_its_output(client, db):
    fake = _FakeModel()
    set_prediction_model(fake)
    r = client.post("/predictions/run", json={"patientId": "PT-1"}, headers=_doctor_headers(client))

    assert r.status_code == 201, r.text
    assert len(fake.calls) == 1
    # Mapped via patient_to_model_fields; NULL ki67 dropped so the model default applies.
    assert fake.calls[0]["stage"] == "II" and fake.calls[0]["nodesInvolved"] == 1
    assert "ki67" not in fake.calls[0]

    data = r.json()["data"]
    assert data["survival"] == 90.0 and data["recurrence"] == 20.0 and data["confidence"] == 85.0
    assert data["riskBand"] == "moderate"
    assert "Fake Model v9" in data["model"] and "heuristic survival/recurrence" in data["model"]
    assert data["model"] != SNAPSHOT_LABEL
    stored = db("SELECT model, survival FROM prediction_runs", fetch=True)
    assert len(stored) == 1 and stored[0]["model"] == data["model"] and stored[0]["survival"] == 90.0


def test_run_returns_503_and_records_nothing_when_model_unavailable(client, db):
    set_prediction_model(_FakeModel(error=RuntimeError("Model artifact not found.")))
    r = client.post("/predictions/run", json={"patientId": "PT-1"}, headers=_doctor_headers(client))

    assert r.status_code == 503
    assert r.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    assert db("SELECT count(*) AS n FROM prediction_runs", fetch=True)[0]["n"] == 0
    assert db("SELECT count(*) AS n FROM timeline_events", fetch=True)[0]["n"] == 0


def test_run_returns_503_when_real_artifact_is_missing(client, db, monkeypatch, tmp_path):
    from app.ml import model as rf

    monkeypatch.setattr(rf, "MODEL_PATH", tmp_path / "missing.joblib")
    monkeypatch.setattr(rf, "_bundle", None)
    set_prediction_model(None)  # default HeuristicRandomForestModel
    r = client.post("/predictions/run", json={"patientId": "PT-1"}, headers=_doctor_headers(client))

    assert r.status_code == 503 and r.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    assert db("SELECT count(*) AS n FROM prediction_runs", fetch=True)[0]["n"] == 0


def test_run_uses_the_real_random_forest_artifact(client, db):
    pytest.importorskip("sklearn")
    pytest.importorskip("joblib")
    from app.ml.model import predict_from_patient

    set_prediction_model(None)
    r = client.post("/predictions/run", json={"patientId": "PT-1"}, headers=_doctor_headers(client))
    assert r.status_code == 201, r.text

    expected = predict_from_patient({"stage": "II", "grade": 2, "nodesInvolved": 1, "tumorSizeMm": 25,
                                     "erStatus": "Positive", "prStatus": "Positive",
                                     "her2Status": "Negative", "age": 55})
    data = r.json()["data"]
    assert data["survival"] == round(expected["survival"] * 100, 1)
    assert data["confidence"] == round(expected["confidence"] * 100, 1)
    assert data["model"].startswith("OncoTwin Malignancy Risk Model") and data["model"] != SNAPSHOT_LABEL
    assert interface.get_prediction_model().metadata.name in data["model"]
