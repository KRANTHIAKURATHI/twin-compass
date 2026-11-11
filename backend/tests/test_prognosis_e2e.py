"""
End-to-end checks of GET /predictions/{patient_id}/prognosis through the real FastAPI app with the REAL saved
METABRIC OS/RFS artifacts (the patients table is a per-test SQLite fixture; nothing is mocked in the model path).

Covers what the other prognosis tests do not: invalid stored values at the route level (a clean 200 "unavailable",
never a 500 or a guessed value), the route serving exactly what the artifact computes, probability sanity, and the
response contract the frontend (`src/types/models.ts` SurvivalEstimate) reads.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("sksurv")

from app.ml.prognosis import FEATURE_SOURCE, NOT_RECORDED, REQUIRED, _load, map_clinical_features  # noqa: E402
from tests.test_prognosis_recorded_fields import _headers, _prognosis, db  # noqa: E402,F401  (fixtures/helpers)

VALID = {"name": "E2E Valid", "age": 61, "tumorSizeMm": 28, "stage": "II", "grade": 2, "nodesInvolved": 3,
         "erStatus": "Positive", "prStatus": "Positive", "her2Status": "Negative"}
MODELS = {"overallSurvival": "os", "relapseFreeSurvival": "rfs"}


def test_valid_patient_gets_both_estimates_labelled_research(client, db):
    h = _headers(client)
    _, prog = _prognosis(client, h, VALID)
    for key in MODELS:
        r = prog[key]
        assert r["status"] == "available"
        assert r["clinicallyValidated"] is False and "not clinically validated" in r["researchStatus"].lower()
        assert r["provenance"]["clinicallyValidated"] is False and r["provenance"]["externalValidation"] is False
        assert "treatment" in r["provenance"]["purpose"].lower() and "not a treatment-response" in r["provenance"]["purpose"].lower()
        assert r["featureAvailability"]["molecularExpressionUsed"] is False
        probs = [e["probability"] for e in r["estimates"]]
        assert [e["horizonMonths"] for e in r["estimates"]] == [60, 120]
        assert all(p is None or 0.0 < p < 1.0 for p in probs)
        assert probs[0] is not None and probs[1] is not None and probs[1] <= probs[0]  # survival never increases with time
        assert "not a probability" in r["riskScoreNote"].lower()


def test_route_returns_exactly_what_the_artifact_computes_for_the_recorded_values(client, db):
    h = _headers(client)
    data, prog = _prognosis(client, h, VALID)
    mapped = map_clinical_features({"age": 61, "tumor_size_mm": 28, "stage": "II", "grade": 2, "nodes_involved": 3,
                                    "er_status": "Positive", "pr_status": "Positive", "her2_status": "Negative"})
    for key, code in MODELS.items():
        direct = _load(code).predict([mapped])[0]
        assert prog[key]["riskScore"] == pytest.approx(direct["risk_score"])
        route = {e["horizonMonths"]: e["probability"] for e in prog[key]["estimates"]}
        assert route[60] == pytest.approx(direct["survival_probability"]["60_months"])
        assert route[120] == pytest.approx(direct["survival_probability"]["120_months"])


@pytest.mark.parametrize(
    "override, missing",
    [
        ({"grade": 4}, {"GRADE"}),                       # outside the 1-3 scale: not corrected, not used
        ({"erStatus": "Maybe"}, {"ER_STATUS"}),          # not a receptor status
        ({"age": 0}, {"AGE_AT_DIAGNOSIS"}),              # schema default, not a measurement
        ({"tumorSizeMm": 0}, {"TUMOR_SIZE"}),
        ({"stage": "V"}, {"TUMOR_STAGE"}),
        ({"nodesInvolved": -1}, {"LYMPH_NODES_EXAMINED_POSITIVE"}),
        ({"age": 400, "grade": 9}, {"AGE_AT_DIAGNOSIS", "GRADE"}),
    ],
)
def test_invalid_stored_values_give_a_clean_unavailable_not_a_guess(client, db, override, missing):
    h = _headers(client)
    _, prog = _prognosis(client, h, {**VALID, **override})
    for key in MODELS:
        r = prog[key]
        assert r["status"] == "unavailable" and "riskScore" not in r and "estimates" not in r
        assert set(r["featureAvailability"]["missingRequired"]) == missing
        assert all(m in r["reason"] for m in missing)


def test_optional_receptors_missing_do_not_block_a_prognosis_and_are_not_invented(client, db):
    h = _headers(client)
    body = {k: v for k, v in VALID.items() if k not in ("prStatus", "her2Status")}
    _, prog = _prognosis(client, h, body)
    for key in MODELS:
        r = prog[key]
        assert r["status"] == "available"
        mapped = set(r["featureAvailability"]["mapped"])
        assert "PR_STATUS" not in mapped and "HER2_STATUS" not in mapped
        assert set(r["featureAvailability"]["recordedButUnavailable"]) == {"PR_STATUS", "HER2_STATUS"}


def test_only_recorded_fields_are_mapped_and_treatment_variables_are_never_inferred(client, db):
    h = _headers(client)
    _, prog = _prognosis(client, h, {**VALID, "currentTreatment": "chemotherapy"})  # recorded text is not a METABRIC flag
    for key in MODELS:
        avail = prog[key]["featureAvailability"]
        assert set(avail["mapped"]) <= set(FEATURE_SOURCE)
        assert all(v["source"].startswith("patients.") for v in avail["mapped"].values())
        assert avail["notRecordedInOncoTwin"] == list(NOT_RECORDED)
        assert not set(avail["mapped"]) & set(NOT_RECORDED)


def test_unknown_patient_is_404_and_auth_is_enforced(client, db):
    h = _headers(client)
    assert client.get("/predictions/PT-DOES-NOT-EXIST/prognosis", headers=h).status_code == 404
    assert client.get("/predictions/PT-1000/prognosis").status_code == 401


def _ts_interface_keys(name: str) -> set[str]:
    source = (Path(__file__).resolve().parents[2] / "src" / "types" / "models.ts").read_text(encoding="utf-8")
    block = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.S).group(1)
    return set(re.findall(r"^\s{2}(\w+)\??:", block, re.M))


def test_response_satisfies_the_frontend_contract(client, db):
    h = _headers(client)
    _, ok = _prognosis(client, h, VALID)
    _, off = _prognosis(client, h, {**VALID, "name": "E2E Off", "grade": None})
    assert _ts_interface_keys("PrognosisResult") == {"overallSurvival", "relapseFreeSurvival"} == set(ok) == set(off)
    keys = _ts_interface_keys("SurvivalEstimate")
    required_always = {"status", "model", "researchStatus"}
    for key in MODELS:
        assert keys - {"reason"} <= set(ok[key]), keys - set(ok[key])    # available: every field the UI may read exists
        assert required_always | {"reason"} <= set(off[key])             # unavailable: the UI reads `reason`
        assert {"missingRequired", "notRecordedInOncoTwin"} <= set(ok[key]["featureAvailability"])
        assert {"modelVersion", "clinicallyValidated"} <= set(ok[key]["provenance"])
        assert all({"horizonMonths", "probability"} <= set(e) for e in ok[key]["estimates"])
    assert set(REQUIRED) == {"AGE_AT_DIAGNOSIS", "LYMPH_NODES_EXAMINED_POSITIVE", "TUMOR_SIZE", "GRADE", "TUMOR_STAGE", "ER_STATUS"}
