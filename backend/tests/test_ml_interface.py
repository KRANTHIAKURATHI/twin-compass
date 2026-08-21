"""Unit-level tests for the model boundary. No HTTP, no database."""

from app.ml.interface import (
    HeuristicRandomForestModel,
    ModelMetadata,
    PredictionModel,
    explain_delta,
    get_prediction_model,
    patient_to_model_fields,
    set_prediction_model,
)

_LOW_RISK = {
    "stage": "I", "grade": 1, "ki67": 5, "nodesInvolved": 0, "tumorSizeMm": 8,
    "erStatus": "Positive", "prStatus": "Positive", "her2Status": "Negative", "age": 45,
}
_HIGH_RISK = {
    "stage": "IV", "grade": 3, "ki67": 80, "nodesInvolved": 12, "tumorSizeMm": 65,
    "erStatus": "Negative", "prStatus": "Negative", "her2Status": "Positive", "age": 72,
}


def test_metadata_reports_the_model_as_unvalidated_development():
    m = get_prediction_model().metadata
    assert m.model_type == "development"
    assert m.is_validated is False
    assert m.name
    assert m.version


def test_metadata_disclaimer_avoids_overclaiming_language():
    text = get_prediction_model().metadata.disclaimer.lower()
    for forbidden in ("guaranteed", "definitive", "clinically proven", "diagnosis of", "confirmed"):
        assert forbidden not in text
    assert "not clinically validated" in text


def test_metadata_survives_a_missing_metrics_file():
    """Provenance is descriptive, not load-bearing: predictions must not fail
    because metrics.json is absent."""
    m = HeuristicRandomForestModel(metrics={}).metadata
    assert m.is_validated is False
    assert m.version == "v0.0.0-unknown"


def test_prediction_is_deterministic_for_identical_input():
    model = get_prediction_model()
    assert model.predict(_LOW_RISK) == model.predict(_LOW_RISK)


def test_higher_clinical_severity_predicts_worse_outcomes():
    model = get_prediction_model()
    low = model.predict(_LOW_RISK)
    high = model.predict(_HIGH_RISK)
    assert high["survival"] < low["survival"]
    assert high["recurrence"] > low["recurrence"]


def test_explanations_vary_with_real_patient_fields():
    """Guards against attributions degenerating into fixed values."""
    model = get_prediction_model()
    low = {r["feature"]: r["weight"] for r in model.explain(_LOW_RISK)}
    high = {r["feature"]: r["weight"] for r in model.explain(_HIGH_RISK)}
    assert low != high


def test_explanation_weights_are_normalized_and_ordered():
    rows = get_prediction_model().explain(_HIGH_RISK, top_n=8)
    assert rows
    assert all(0.0 <= r["weight"] <= 1.0 for r in rows)
    assert rows == sorted(rows, key=lambda r: r["weight"], reverse=True)
    assert abs(sum(r["weight"] for r in rows) - 1.0) < 0.01


def test_explanation_names_real_clinical_factors():
    features = {r["feature"] for r in get_prediction_model().explain(_HIGH_RISK)}
    assert "Stage" in features
    assert "Tumour size" in features
    assert "Lymph nodes involved" in features
    assert "Receptor profile (ER/PR/HER2)" in features


def test_explanation_direction_reflects_the_patients_own_values():
    by_feature = {r["feature"]: r["direction"] for r in get_prediction_model().explain(_HIGH_RISK)}
    assert by_feature["Stage"] == "increases risk"
    assert by_feature["Lymph nodes involved"] == "increases risk"

    low = {r["feature"]: r["direction"] for r in get_prediction_model().explain(_LOW_RISK)}
    assert low["Stage"] == "protective"
    assert low["Lymph nodes involved"] == "protective"


def test_changing_one_field_changes_that_factors_weight():
    model = get_prediction_model()
    before = {r["feature"]: r["weight"] for r in model.explain(_HIGH_RISK)}
    after = {r["feature"]: r["weight"] for r in model.explain({**_HIGH_RISK, "nodesInvolved": 0})}
    assert after["Lymph nodes involved"] < before["Lymph nodes involved"]


def test_severity_still_matches_the_documented_composite():
    """The refactor that made explanations per-patient must not have changed the
    severity score itself, which drives every prediction."""
    from app.ml.model import SEVERITY_FACTORS, clinical_factors, clinical_severity

    for fields in (_LOW_RISK, _HIGH_RISK):
        levels = clinical_factors(fields)
        expected = sum(levels[k] * SEVERITY_FACTORS[k][0] for k in levels)
        assert abs(clinical_severity(fields) - min(max(expected, 0.0), 1.0)) < 1e-9


def test_simulate_all_covers_every_regimen_with_one_recommendation():
    model = get_prediction_model()
    scenarios = model.simulate_all(_HIGH_RISK)
    assert {s["regimen"] for s in scenarios} == set(model.regimen_names())
    assert sum(1 for s in scenarios if s["recommended"]) == 1


def test_active_surveillance_is_the_weakest_intervention():
    model = get_prediction_model()
    surveillance = model.simulate(_HIGH_RISK, "Active Surveillance")
    chemo = model.simulate(_HIGH_RISK, "AC-T (Doxorubicin/Cyclophosphamide + Paclitaxel)")
    assert surveillance["predicted_response"] < chemo["predicted_response"]
    assert surveillance["tumor_change"] > chemo["tumor_change"]  # less shrinkage


def test_delta_explanation_is_empty_of_change_for_identical_states():
    rows = explain_delta(_HIGH_RISK, _HIGH_RISK)
    assert rows
    assert all(r["contribution"] == 0.0 for r in rows)


def test_delta_explanation_tracks_a_real_field_change():
    shrunk = {**_HIGH_RISK, "tumorSizeMm": 10}
    rows = explain_delta(_HIGH_RISK, shrunk)
    assert rows
    assert any(r["contribution"] != 0.0 for r in rows)
    # Sorted by magnitude of change, so the largest shift leads.
    assert abs(rows[0]["contribution"]) >= abs(rows[-1]["contribution"])
    for r in rows:
        assert r["weightBefore"] != r["weightAfter"] or r["contribution"] == 0.0


def test_patient_field_mapping_covers_every_model_input():
    class _Row:
        stage, grade, ki67, nodes_involved, tumor_size_mm = "III", 2, 30.0, 4, 25.0
        er_status, pr_status, her2_status, age = "Positive", "Negative", "Negative", 58

    fields = patient_to_model_fields(_Row())
    assert set(fields) == set(_LOW_RISK)
    assert fields["stage"] == "III"
    assert fields["nodesInvolved"] == 4


def test_a_fake_model_can_be_substituted():
    """The point of the ABC: a real validated model could replace this one
    without touching any service or router."""

    class _Fake(PredictionModel):
        @property
        def metadata(self):
            return ModelMetadata(name="Fake", version="v9", dataset_name="none",
                                 trained_at="", model_type="test", is_validated=True)

        def predict(self, patient_fields):
            return {"survival": 0.5, "recurrence": 0.5, "confidence": 1.0, "risk": "low",
                    "response": "Favorable", "status": "Complete", "severity": 0.0}

        def explain(self, patient_fields, top_n=8):
            return [{"feature": "Fake", "weight": 1.0, "direction": "protective"}]

        def simulate(self, patient_fields, regimen_name):
            return {"regimen": regimen_name, "survival5y": 0.9}

        def simulate_all(self, patient_fields):
            return [self.simulate(patient_fields, "Fake Regimen")]

        def regimen_names(self):
            return ["Fake Regimen"]

    try:
        set_prediction_model(_Fake())
        assert get_prediction_model().metadata.name == "Fake"
        assert get_prediction_model().predict(_HIGH_RISK)["risk"] == "low"
    finally:
        set_prediction_model(None)

    assert get_prediction_model().metadata.name != "Fake"
