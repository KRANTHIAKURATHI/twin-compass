from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateReportRequest(BaseModel):
    patient_id: str = Field(validation_alias="patientId")
    type: str = "Clinical summary"

    model_config = {"populate_by_name": True}


class ExportReportRequest(BaseModel):
    format: str
