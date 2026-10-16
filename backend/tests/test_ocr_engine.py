"""OCR engine tests. Real-Tesseract tests skip (with a reason) when the executable is absent;
the rest use a stubbed `run_tesseract` and need neither Tesseract nor a database."""
from __future__ import annotations

import io
import shutil

import pytest

pymupdf = pytest.importorskip("pymupdf")
PIL_Image = pytest.importorskip("PIL.Image")
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.exceptions import UpstreamServiceError, ValidationAppError  # noqa: E402
from app.services import ocr_provider as op  # noqa: E402

REPORT = "Tumor size: 25 mm\nER: Positive\nPR: Negative\nHER2: Negative\nGrade 2\nKi-67: 30%"
needs_tesseract = pytest.mark.skipif(
    shutil.which(get_settings().TESSERACT_CMD or "tesseract") is None,
    reason="Tesseract executable not installed (set TESSERACT_CMD or add it to PATH)",
)


def _image_bytes(fmt: str, text: str = REPORT) -> bytes:
    img = Image.new("RGB", (1000, 420), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        font = ImageFont.load_default(size=34)
    d.multiline_text((30, 30), text, fill="black", font=font, spacing=12)
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def _text_pdf(text: str, pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page().insert_text((72, 72), text, fontsize=12)
    return doc.tobytes()


def _scanned_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, stream=_image_bytes("PNG"))
    return doc.tobytes()


@pytest.fixture
def stub_tesseract(monkeypatch):
    calls = []

    def fake(image, settings):
        calls.append(image.size)
        words = "Tumor size: 25 mm".split()
        return [[(w, 0.91 if w != "25" else 0.77) for w in words]]

    monkeypatch.setattr(op, "run_tesseract", fake)
    return calls


# --- stubbed engine -----------------------------------------------------------------------


def test_digital_pdf_uses_text_layer_without_ocr(stub_tesseract):
    fields = op._extract_sync(_text_pdf("Tumor size: 25 mm. ER: Positive. Grade 2. " * 2), "application/pdf")
    assert stub_tesseract == []                       # Tesseract never called
    assert {f.field: f.value for f in fields} == {"tumor_size_mm": "25", "er_status": "Positive", "grade": "2"}
    assert all(f.confidence is None for f in fields)  # no OCR -> no confidence, never invented
    # No OCR word spans exist at all, so there is nothing a confidence could be derived from.
    assert op.extract_text_from_pdf(_text_pdf("Tumor size: 25 mm. " * 3)).words == []
    assert all(f.source == "text-layer" for f in fields)


def test_scanned_pdf_page_falls_back_to_ocr(stub_tesseract):
    fields = op._extract_sync(_scanned_pdf(), "application/pdf")
    assert len(stub_tesseract) == 1
    f = {x.field: x for x in fields}
    assert f["tumor_size_mm"].value == "25"
    assert f["tumor_size_mm"].confidence == 0.77      # min confidence of the value's words
    assert all(x.source == "ocr" for x in fields)


def test_missing_word_confidence_is_never_fabricated(monkeypatch):
    """If Tesseract reports no confidence for a word of the value, the field's confidence stays None."""
    words = [("Tumor", 0.9), ("size:", 0.9), ("25", None), ("mm", 0.9)]
    monkeypatch.setattr(op, "run_tesseract", lambda image, settings: [words])
    fields = op._extract_sync(_scanned_pdf(), "application/pdf")
    assert {f.field: f.confidence for f in fields}["tumor_size_mm"] is None


def test_value_overlapping_both_sources_or_neither_has_no_source():
    """Source is only set when unambiguous; the confidence rule is unchanged."""
    text = "Tumor size: 25 mm"
    both = op.DocumentText(parts=[text], length=len(text), words=[(12, 14, 0.9)], plain_spans=[(0, len(text))])
    fields = op.extract_clinical_fields(both)
    assert [f.field for f in fields] == ["tumor_size_mm"]
    assert fields[0].source is None and fields[0].confidence == 0.9

    neither = op.DocumentText(parts=[text], length=len(text))
    fields = op.extract_clinical_fields(neither)
    assert fields[0].source is None and fields[0].confidence is None


def test_source_never_depends_on_the_model_label(monkeypatch):
    monkeypatch.setattr(op, "engine_label", lambda: "tesseract 5.3.0")
    fields = op._extract_sync(_text_pdf("Tumor size: 25 mm. Grade 2. " * 2), "application/pdf")
    assert fields and all(f.source == "text-layer" for f in fields)


def test_image_confidence_is_tesseract_confidence(stub_tesseract):
    fields = op._extract_sync(_image_bytes("PNG"), "image/png")
    assert fields and fields[0].confidence == 0.77
    assert op._extract_sync(_image_bytes("JPEG"), "image/jpeg")[0].confidence == 0.77
    assert all(f.source == "ocr" for f in fields)


def test_mixed_pdf_ocrs_only_the_thin_page(stub_tesseract):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Grade 2. " * 10, fontsize=12)
    doc.new_page().insert_image(doc[0].rect, stream=_image_bytes("PNG"))
    fields = {f.field: f for f in op._extract_sync(doc.tobytes(), "application/pdf")}
    assert len(stub_tesseract) == 1
    # Each value is attributed to the page it actually came from.
    assert fields["grade"].source == "text-layer" and fields["grade"].confidence is None
    assert fields["tumor_size_mm"].source == "ocr" and fields["tumor_size_mm"].confidence == 0.77


def test_empty_document_rejected(stub_tesseract):
    with pytest.raises(ValidationAppError):
        op._extract_sync(b"", "application/pdf")


def test_unsupported_mime_rejected(stub_tesseract):
    with pytest.raises(ValidationAppError):
        op._extract_sync(b"hello", "text/plain")


def test_corrupt_files_rejected(stub_tesseract):
    with pytest.raises(ValidationAppError):
        op._extract_sync(b"not a pdf", "application/pdf")
    with pytest.raises(ValidationAppError):
        op._extract_sync(b"not a png", "image/png")


def test_mismatched_image_type_rejected(stub_tesseract):
    with pytest.raises(ValidationAppError):
        op._extract_sync(_image_bytes("JPEG"), "image/png")


def test_page_limit_enforced(stub_tesseract, monkeypatch):
    monkeypatch.setattr(get_settings(), "OCR_MAX_PAGES", 2)
    with pytest.raises(ValidationAppError):
        op._extract_sync(_text_pdf("Grade 2 " * 10, pages=3), "application/pdf")
    assert stub_tesseract == []


def test_tesseract_unavailable_is_an_explicit_error(monkeypatch):
    monkeypatch.setattr(get_settings(), "TESSERACT_CMD", "definitely-not-a-real-tesseract")
    with pytest.raises(UpstreamServiceError) as e:
        op._extract_sync(_image_bytes("PNG"), "image/png")
    assert "Tesseract" in str(e.value)


def test_errors_do_not_leak_document_content(stub_tesseract):
    with pytest.raises(ValidationAppError) as e:
        op._extract_sync(b"SECRET-PATIENT-DATA", "application/pdf")
    assert "SECRET" not in str(e.value)


def test_no_fields_found_returns_empty_list_when_engine_ran(monkeypatch):
    monkeypatch.setattr(op, "run_tesseract", lambda image, settings: [[("hello", 0.9)]])
    assert op._extract_sync(_image_bytes("PNG"), "image/png") == []


# --- real Tesseract -----------------------------------------------------------------------


@needs_tesseract
@pytest.mark.parametrize("fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_real_ocr_on_images(fmt, mime):
    got = {f.field: f for f in op._extract_sync(_image_bytes(fmt), mime)}
    assert got["tumor_size_mm"].value == "25" and got["er_status"].value == "Positive"
    assert 0.0 < got["tumor_size_mm"].confidence <= 1.0


@needs_tesseract
def test_real_ocr_on_scanned_pdf():
    fields = op._extract_sync(_scanned_pdf(), "application/pdf")
    got = {f.field: f.value for f in fields}
    assert got["tumor_size_mm"] == "25"
    # An image-only page has no text layer, so Tesseract ran and each value carries its real word confidence.
    assert fields and all(isinstance(f.confidence, float) and 0.0 < f.confidence <= 1.0 for f in fields)
    assert all(f.source == "ocr" for f in fields)


@needs_tesseract
def test_real_ocr_digital_pdf_never_gets_a_confidence():
    fields = op._extract_sync(_text_pdf("Tumor size: 25 mm. ER: Positive. Grade 2. " * 2), "application/pdf")
    assert {f.field for f in fields} >= {"tumor_size_mm", "er_status", "grade"}
    assert all(f.confidence is None for f in fields)
    assert all(f.source == "text-layer" for f in fields)


# --- provider selection ---------------------------------------------------------------------


def test_tesseract_is_the_default_provider(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("OCR_PROVIDER", raising=False)
    assert Settings(_env_file=None).OCR_PROVIDER == "tesseract"


def test_explicit_env_selects_provider_and_empty_disables(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("OCR_PROVIDER", "tesseract")
    assert Settings(_env_file=None).OCR_PROVIDER == "tesseract"
    monkeypatch.setenv("OCR_PROVIDER", "")
    assert not Settings(_env_file=None).OCR_PROVIDER


def test_selected_tesseract_provider_reaches_the_engine(stub_tesseract, monkeypatch):
    monkeypatch.setattr(get_settings(), "OCR_PROVIDER", "tesseract")
    assert op._extract_sync(_scanned_pdf(), "application/pdf")
    assert len(stub_tesseract) == 1
