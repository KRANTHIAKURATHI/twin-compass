from __future__ import annotations

from pydantic import BaseModel, Field


class OcrFieldInput(BaseModel):
    """One clinician-reviewed field, as approved (value may have been
    corrected from the raw OCR output during review)."""

    field: str
    value: str | None = None
    confidence: float | None = None

    model_config = {"populate_by_name": True}


class OcrApproveRequest(BaseModel):
    fields: list[OcrFieldInput] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class OcrRejectRequest(BaseModel):
    reason: str | None = None

    model_config = {"populate_by_name": True}
