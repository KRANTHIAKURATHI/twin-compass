"""Pure OCR field parser tests (no Tesseract, no database)."""
from __future__ import annotations

import pytest

from app.api.v1.routers.ocr import FIELD_CATALOG
from app.services.ocr_parser import parse_clinical_fields


def parse(text: str) -> dict[str, str]:
    return {p.field: p.value for p in parse_clinical_fields(text)}


@pytest.mark.parametrize("text,expected", [
    ("Tumor size: 25 mm", "25"), ("Tumour measuring 2.5 cm", "25"), ("lesion of 1.2cm", "12"),
])
def test_tumor_size(text, expected):
    assert parse(text)["tumor_size_mm"] == expected


def test_tumor_size_ambiguous_or_multi_dimension_ignored():
    assert "tumor_size_mm" not in parse("Tumor size 25 x 18 mm")
    assert "tumor_size_mm" not in parse("Tumor size 25 mm. Mass of 30 mm")


def test_receptors():
    r = parse("ER: Positive\nPR: Negative\nHER2: Positive")
    assert (r["er_status"], r["pr_status"], r["her2_status"]) == ("Positive", "Negative", "Positive")
    assert parse("Estrogen receptor negative")["er_status"] == "Negative"


def test_combined_er_pr_not_split():
    r = parse("ER/PR positive")
    assert "er_status" not in r and "pr_status" not in r


def test_her2_ihc_mapping_and_equivocal():
    assert parse("HER2 IHC 3+")["her2_status"] == "Positive"
    assert parse("HER2 IHC 1+")["her2_status"] == "Negative"
    assert "her2_status" not in parse("HER2 IHC 2+")
    assert "her2_status" not in parse("HER2 equivocal")


def test_ki67_requires_percent():
    assert parse("Ki-67: 30%")["ki67"] == "30"
    assert "ki67" not in parse("Ki-67 30")
    assert "ki67" not in parse("Ki-67 > 20%")


def test_grade():
    assert parse("Histologic grade 2")["grade"] == "2"
    assert parse("Grade III")["grade"] == "3"
    assert "grade" not in parse("Grade 2-3")
    assert "grade" not in parse("nuclear grade 3")


def test_nodes():
    assert parse("2/12 lymph nodes positive")["nodes_involved"] == "2"
    assert parse("3 positive nodes")["nodes_involved"] == "3"
    assert "nodes_involved" not in parse("5/3 lymph nodes")


def test_stage():
    assert parse("Stage IIA")["stage"] == "II"
    assert parse("pT2 N1 M0")["stage"] == "II"
    assert "stage" not in parse("pT2 N1")          # no explicit M
    assert "stage" not in parse("locally advanced disease")


def test_diagnosis_date():
    assert parse("Date of diagnosis: 2024-03-15")["diagnosed_on"] == "2024-03-15"
    assert parse("Diagnosed on 15 March 2024")["diagnosed_on"] == "2024-03-15"


def test_ambiguous_or_unlabelled_dates_ignored():
    assert "diagnosed_on" not in parse("Date of diagnosis: 03/04/2024")
    assert "diagnosed_on" not in parse("Report date: 2024-03-15")
    assert "diagnosed_on" not in parse("Uploaded 2024-03-15")


def test_conflicting_mentions_not_extracted():
    assert "grade" not in parse("Grade 2 ... later Grade 3")


def test_only_catalog_fields_are_returned():
    text = "Tumor size 20 mm ER positive PR positive HER2 negative Ki-67 15% Grade 2 3/10 nodes positive Stage II diagnosed on 2023-01-20 Patient name John"
    assert {p.field for p in parse_clinical_fields(text)} <= set(FIELD_CATALOG)


def test_empty_and_irrelevant_text_gives_nothing():
    assert parse_clinical_fields("") == []
    assert parse_clinical_fields("Nothing clinical here.") == []
