"""
OCR provider boundary (Phase 7).

No OCR/document-AI engine is installed in this project: `requirements.txt`
carries no pytesseract, no pdf2image/Pillow, no cloud OCR SDK (Textract,
Document AI, Azure Document Intelligence, ...). This module is the seam a
real provider plugs into. Until `settings.OCR_PROVIDER` names one that is
actually implemented below, extraction fails loudly with an actionable
error - it never invents clinical values to make the feature look finished.

To make OCR real: add the provider's SDK to requirements.txt, implement a
branch below that calls it and returns `ExtractedField`s with genuine
`confidence` from the provider (omit confidence rather than fabricate it
when the provider doesn't supply one), and set OCR_PROVIDER.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.core.exceptions import UpstreamServiceError


@dataclass(frozen=True)
class ExtractedField:
    field: str
    value: str
    confidence: float | None  # None when the provider does not supply one - never fabricated.


async def extract_fields(content: bytes, mime_type: str) -> list[ExtractedField]:
    """Run OCR/field extraction over an already-retrieved document's bytes.

    Raises UpstreamServiceError when no provider is configured or the named
    provider has no implementation here - both real failures, not a stub
    returning an empty/fake result.
    """
    provider = get_settings().OCR_PROVIDER
    if not provider:
        raise UpstreamServiceError(
            "No OCR provider is configured (OCR_PROVIDER is unset). Extraction "
            "requires an OCR/document-AI dependency to be added and configured; "
            "no clinical fields were extracted."
        )
    raise UpstreamServiceError(f"OCR provider '{provider}' is not implemented.")
