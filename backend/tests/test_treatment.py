"""Treatment plan endpoint: lazy creation, promoted-regimen reflection, ownership."""

from tests.conftest import auth_headers, register_user

from app.ml.regimens import REGIMENS
from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD

_PATIENT = {"name": "Plan Subject", "email": "plan-subject@example.com", "age": 55, "stage": "II"}


def _admin(client):
    return auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def _patient(client, headers, payload=None):
    resp = client.post("/patients", json=payload or _PATIENT, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_plan_is_created_lazily_on_first_read(client):
    headers = _admin(client)
    p = _patient(client, headers)
    first = client.get(f"/patients/{p['id']}/treatment-plan", headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body["regimen"] in REGIMENS
    assert body["cycle"] == 1
    assert body["totalCycles"] >= 1


def test_repeat_reads_return_the_same_plan(client):
    headers = _admin(client)
    p = _patient(client, headers)
    first = client.get(f"/patients/{p['id']}/treatment-plan", headers=headers).json()
    second = client.get(f"/patients/{p['id']}/treatment-plan", headers=headers).json()
    assert first == second


def test_plan_defaults_to_active_surveillance_for_an_unknown_treatment(client):
    headers = _admin(client)
    p = _patient(client, headers, {**_PATIENT, "currentTreatment": "Something not in the regimen set"})
    body = client.get(f"/patients/{p['id']}/treatment-plan", headers=headers).json()
    assert body["regimen"] == "Active Surveillance"


def test_plan_adopts_the_patients_recorded_treatment(client):
    headers = _admin(client)
    regimen = "TC (Docetaxel/Cyclophosphamide)"
    p = _patient(client, headers, {**_PATIENT, "currentTreatment": regimen})
    body = client.get(f"/patients/{p['id']}/treatment-plan", headers=headers).json()
    assert body["regimen"] == regimen
    assert [m["name"] for m in body["medications"]] == ["Docetaxel", "Cyclophosphamide"]


def test_higher_toxicity_regimens_list_more_serious_side_effects(client):
    headers = _admin(client)
    chemo = _patient(client, headers, {
        **_PATIENT, "email": "plan-chemo@example.com",
        "currentTreatment": "AC-T (Doxorubicin/Cyclophosphamide + Paclitaxel)"})
    endocrine = _patient(client, headers, {
        **_PATIENT, "email": "plan-endo@example.com",
        "currentTreatment": "Endocrine Therapy (Tamoxifen/AI)"})

    chemo_effects = client.get(f"/patients/{chemo['id']}/treatment-plan", headers=headers).json()["sideEffects"]
    endo_effects = client.get(f"/patients/{endocrine['id']}/treatment-plan", headers=headers).json()["sideEffects"]
    assert [e["name"] for e in chemo_effects] == ["Neutropenia"]
    assert [e["name"] for e in endo_effects] == ["Mild nausea"]


def test_plan_reflects_a_promoted_simulation(client):
    headers = _admin(client)
    p = _patient(client, headers, {**_PATIENT, "email": "plan-promoted@example.com"})
    regimen = "HER2-Targeted Therapy (Trastuzumab + Pertuzumab)"
    draft = {"name": "HER2 plan", "regimen": regimen, "dosage": "6 mg/kg", "durationWeeks": 12, "notes": ""}
    saved = client.post(f"/simulations?patient_id={p['id']}", json=draft, headers=headers).json()["data"]
    client.post(f"/simulations/{saved['id']}/promote", headers=headers)

    body = client.get(f"/patients/{p['id']}/treatment-plan", headers=headers).json()
    assert body["regimen"] == regimen
    assert [m["name"] for m in body["medications"]] == ["Trastuzumab", "Pertuzumab"]
    assert body["sideEffects"]


def test_a_plan_created_before_promotion_is_updated_by_it(client):
    headers = _admin(client)
    p = _patient(client, headers, {**_PATIENT, "email": "plan-existing@example.com"})
    before = client.get(f"/patients/{p['id']}/treatment-plan", headers=headers).json()

    regimen = "TC (Docetaxel/Cyclophosphamide)"
    draft = {"name": "TC plan", "regimen": regimen, "dosage": "75 mg/m²", "durationWeeks": 12, "notes": ""}
    saved = client.post(f"/simulations?patient_id={p['id']}", json=draft, headers=headers).json()["data"]
    client.post(f"/simulations/{saved['id']}/promote", headers=headers)

    after = client.get(f"/patients/{p['id']}/treatment-plan", headers=headers).json()
    assert before["regimen"] != regimen
    assert after["regimen"] == regimen


def test_missing_patient_is_404(client):
    headers = _admin(client)
    assert client.get("/patients/nope/treatment-plan", headers=headers).status_code == 404


def test_deleted_patient_is_404(client):
    headers = _admin(client)
    p = _patient(client, headers, {**_PATIENT, "email": "plan-deleted@example.com"})
    client.delete(f"/patients/{p['id']}", headers=headers)
    assert client.get(f"/patients/{p['id']}/treatment-plan", headers=headers).status_code == 404


def test_unauthenticated_access_is_401(client):
    assert client.get("/patients/anything/treatment-plan").status_code == 401


def test_patient_cannot_read_another_patients_plan(client):
    headers = _admin(client)
    other = _patient(client, headers)
    _patient(client, headers, {"name": "Plan Nosy", "email": "plan-nosy@example.com"})
    register_user(client, "plan-nosy@example.com", "Password123!", "patient")
    nosy = auth_headers(client, "plan-nosy@example.com", "Password123!")
    assert client.get(f"/patients/{other['id']}/treatment-plan", headers=nosy).status_code == 403


def test_patient_can_read_their_own_plan(client):
    headers = _admin(client)
    own = _patient(client, headers, {**_PATIENT, "email": "plan-self@example.com"})
    register_user(client, "plan-self@example.com", "Password123!", "patient")
    self_headers = auth_headers(client, "plan-self@example.com", "Password123!")
    assert client.get(f"/patients/{own['id']}/treatment-plan", headers=self_headers).status_code == 200
