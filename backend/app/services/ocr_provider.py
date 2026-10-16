"""
Clinical document OCR (Phase 7): Tesseract 5.x via pytesseract.

Pipeline for an already-retrieved document's bytes:

    PNG/JPEG -> light preprocessing -> Tesseract (LSTM) -> text
    PDF      -> per page: embedded text layer if it has enough text,
                otherwise render the page and run Tesseract on the image
    text     -> deterministic parser (`ocr_parser`, FIELD_CATALOG fields only)

Honesty rules (do not weaken):
* `confidence` is Tesseract's own word confidence (0-1) for exactly the words
  that make up the extracted value - the minimum over those words. It is None
  when the value came from a PDF text layer (no OCR happened) and is never
  estimated. It is OCR evidence only; it says nothing about clinical correctness.
* `source` records, per field, whether the value's text came from the PDF text layer
  ("text-layer") or from Tesseract ("ocr"). It is None when the value overlaps both or
  neither, so it is only ever set when unambiguous.
* Tesseract missing/failing raises UpstreamServiceError. An unreadable, empty,
  oversized or unsupported document raises ValidationAppError. Neither ever
  degrades to "no fields".
* Nothing is written to disk, and no document bytes, OCR text or extracted
  values are logged or put into exception messages.

Tesseract is a system dependency: pytesseract is only a wrapper around the
executable (see backend/OCR-DEPLOYMENT.md).
"""
from __future__ import annotations

import io
import shutil
from dataclasses import dataclass, field
from functools import lru_cache

import anyio
import anyio.to_thread

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError, ValidationAppError
from app.services.ocr_parser import parse_clinical_fields

_MAX_IMAGE_PIXELS = 50_000_000      # decompression-bomb guard for uploaded images
_MAX_RENDER_SIDE_PX = 4000          # rendered PDF pages are capped on their longest side
_RENDER_DPI = 300
_TESSERACT_TIMEOUT_S = 120
_TESSERACT_CONFIG = "--oem 1 --psm 3"   # LSTM engine, automatic page segmentation
_LIMITER = anyio.CapacityLimiter(2)     # bounds concurrent OCR jobs (memory/CPU)
_IMAGE_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG"}


@dataclass(frozen=True)
class ExtractedField:
    field: str
    value: str
    confidence: float | None  # None when no OCR confidence applies - never fabricated.
    # Where the value's text came from: "text-layer" (PDF text, no OCR), "ocr" (Tesseract), or
    # None when that cannot be established unambiguously. Never inferred from the model label.
    source: str | None = None


@dataclass
class DocumentText:
    """Concatenated text plus, per OCR'd word, its span and Tesseract confidence."""

    parts: list[str] = field(default_factory=list)
    length: int = 0
    words: list[tuple[int, int, float | None]] = field(default_factory=list)
    plain_spans: list[tuple[int, int]] = field(default_factory=list)  # PDF text-layer text (no OCR)

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def _add(self, s: str) -> None:
        self.parts.append(s)
        self.length += len(s)

    def add_plain(self, s: str) -> None:
        """Text from a PDF text layer: no OCR, so no confidence."""
        text = s.rstrip()
        self.plain_spans.append((self.length, self.length + len(text)))
        self._add(text + "\n\n")

    def add_ocr_lines(self, lines: list[list[tuple[str, float]]]) -> None:
        for line in lines:
            for i, (word, conf) in enumerate(line):
                if i:
                    self._add(" ")
                self.words.append((self.length, self.length + len(word), conf))
                self._add(word)
            self._add("\n")
        self._add("\n")


# --- Tesseract ------------------------------------------------------------------------


def _resolve_tesseract(settings: Settings) -> str:
    cmd = settings.TESSERACT_CMD or "tesseract"
    found = shutil.which(cmd)
    if not found:
        raise UpstreamServiceError(
            "The Tesseract OCR engine was not found. Install Tesseract 5.x and put it on PATH, or set "
            "TESSERACT_CMD to the executable. No clinical fields were extracted."
        )
    return found


@lru_cache(maxsize=4)
def _tesseract_version(cmd: str) -> str:
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        return str(pytesseract.get_tesseract_version())
    except Exception:  # noqa: BLE001 - pytesseract raises several unrelated types; message stays generic
        raise UpstreamServiceError("The Tesseract OCR engine could not be started.") from None


def _ready_engine(settings: Settings) -> str:
    import pytesseract

    cmd = _resolve_tesseract(settings)
    version = _tesseract_version(cmd)
    if int(version.split(".")[0]) < 5:
        raise UpstreamServiceError(f"Tesseract 5.x is required (found {version}).")
    pytesseract.pytesseract.tesseract_cmd = cmd
    return version


def engine_label() -> str:
    """Model label recorded on an extraction row."""
    settings = get_settings()
    try:
        return f"tesseract {_tesseract_version(_resolve_tesseract(settings))}"
    except UpstreamServiceError:
        return "tesseract"


def run_tesseract(image, settings: Settings) -> list[list[tuple[str, float]]]:
    """OCR one PIL image -> lines of (word, confidence 0-1). Raises UpstreamServiceError if the engine fails."""
    import pytesseract

    _ready_engine(settings)
    try:
        data = pytesseract.image_to_data(
            image, lang=settings.OCR_LANGUAGE, config=_TESSERACT_CONFIG,
            output_type=pytesseract.Output.DICT, timeout=_TESSERACT_TIMEOUT_S,
        )
    except Exception:  # noqa: BLE001 - never surface engine output (could echo document content)
        raise UpstreamServiceError(
            "The Tesseract OCR engine failed to process the document (check OCR_LANGUAGE and the installed language data)."
        ) from None

    lines: dict[tuple[int, int, int], list[tuple[str, float]]] = {}
    for i, word in enumerate(data["text"]):
        word = (word or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if not word or conf < 0:
            continue
        key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
        lines.setdefault(key, []).append((word, round(conf / 100.0, 3)))
    return [lines[k] for k in sorted(lines)]


# --- images -----------------------------------------------------------------------------


def _preprocess(image):
    """Gentle clean-up only: upright, grayscale, contrast stretch, upscale small scans. No binarisation."""
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        image = Image.alpha_composite(base, rgba)
    image = ImageOps.autocontrast(image.convert("L"), cutoff=1)
    if image.width < 1000:
        scale = min(2, 1000 / image.width)
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    return image


def extract_text_from_image(content: bytes, mime_type: str, settings: Settings | None = None) -> DocumentText:
    from PIL import Image

    settings = settings or get_settings()
    expected = _IMAGE_FORMATS[mime_type]
    try:
        with Image.open(io.BytesIO(content)) as img:
            if img.format != expected:
                raise ValidationAppError("The file content does not match its declared image type.", field="document")
            if img.width * img.height > _MAX_IMAGE_PIXELS:
                raise ValidationAppError("The image is too large to OCR.", field="document")
            img.load()
            prepared = _preprocess(img)
    except ValidationAppError:
        raise
    except Exception:  # noqa: BLE001 - PIL raises many types for corrupt files
        raise ValidationAppError("The image could not be read.", field="document") from None
    out = DocumentText()
    out.add_ocr_lines(run_tesseract(prepared, settings))
    return out


# --- PDFs -------------------------------------------------------------------------------


def extract_text_from_pdf(content: bytes, settings: Settings | None = None) -> DocumentText:
    """Text layer where a page has enough of it; Tesseract on the rendered page otherwise."""
    import pymupdf
    from PIL import Image

    settings = settings or get_settings()
    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
    except Exception:  # noqa: BLE001
        raise ValidationAppError("The PDF could not be read.", field="document") from None
    out = DocumentText()
    with doc:
        if doc.needs_pass:
            raise ValidationAppError("Password-protected PDFs cannot be processed.", field="document")
        if doc.page_count == 0:
            raise ValidationAppError("The PDF has no pages.", field="document")
        if doc.page_count > settings.OCR_MAX_PAGES:
            raise ValidationAppError(
                f"The PDF has {doc.page_count} pages; OCR is limited to {settings.OCR_MAX_PAGES}.", field="document"
            )
        for page in doc:  # one page in memory at a time
            layer = page.get_text("text") or ""
            if len(layer.strip()) >= settings.OCR_MIN_TEXT_CHARS_PER_PAGE:
                out.add_plain(layer)
                continue
            rect = page.rect
            zoom = min(_RENDER_DPI / 72, _MAX_RENDER_SIDE_PX / max(rect.width, rect.height, 1))
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY, alpha=False)
            image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
            del pix
            out.add_ocr_lines(run_tesseract(_preprocess(image), settings))
            image.close()
            if layer.strip():
                out.add_plain(layer)  # keep the few embedded characters too
    return out


# --- fields -----------------------------------------------------------------------------


def extract_clinical_fields(doc: DocumentText) -> list[ExtractedField]:
    """Parse FIELD_CATALOG fields; attach the real OCR confidence of the value's words (None if none applies)."""
    results = []
    for p in parse_clinical_fields(doc.text):
        confs = [c for s, e, c in doc.words if s < p.end and e > p.start]
        confidence = min(confs) if confs and all(c is not None for c in confs) else None
        from_ocr = bool(confs)
        from_text_layer = any(s < p.end and e > p.start for s, e in doc.plain_spans)
        source = "ocr" if from_ocr and not from_text_layer else "text-layer" if from_text_layer and not from_ocr else None
        results.append(ExtractedField(p.field, p.value, confidence, source))
    return results


def _extract_sync(content: bytes, mime_type: str) -> list[ExtractedField]:
    settings = get_settings()
    if not settings.OCR_PROVIDER:
        raise UpstreamServiceError("OCR is disabled (OCR_PROVIDER is unset); no clinical fields were extracted.")
    if settings.OCR_PROVIDER != "tesseract":
        raise UpstreamServiceError(f"OCR provider '{settings.OCR_PROVIDER}' is not implemented.")
    if not content:
        raise ValidationAppError("The document is empty.", field="document")
    if mime_type == "application/pdf":
        doc = extract_text_from_pdf(content, settings)
    elif mime_type in _IMAGE_FORMATS:
        doc = extract_text_from_image(content, mime_type, settings)
    else:
        raise ValidationAppError(f"Unsupported document type for OCR ({mime_type or 'unknown'}).", field="document")
    return extract_clinical_fields(doc)


async def extract_fields(content: bytes, mime_type: str) -> list[ExtractedField]:
    """OCR + parse an already-retrieved document. Blocking work runs in a worker thread."""
    return await anyio.to_thread.run_sync(_extract_sync, content, mime_type, limiter=_LIMITER)
