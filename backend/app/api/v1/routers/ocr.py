"""
OCR extraction router (Phase 7).

Extends the Phase 6 document pipeline (`routers/documents.py`) with:

    document -> OCR extraction -> doctor review -> approve/reject
        -> approved patient update -> existing Digital Twin resync

OCR output is never trusted clinical truth: `/extract` only ever persists an
`ocr_extractions` row plus its `ocr_extraction_fields` (status "Extracted");
nothing about the patient record changes until a doctor/admin explicitly
calls `/approve`, and only the fields present in that approval payload are
applied. `/reject` marks the extraction rejected without touching the
patient at all. Both keep the original extraction row (and its fields) for
audit - nothing here deletes a reviewed extraction.

Real text/field extraction depends on `services/ocr_provider.py`, which has
no OCR engine configured (see that module's docstring) - `/extract` will
fail with a clear 502 until one is added. Everything else in this router
(storage retrieval, mime validation, persistence, review, approval, patient
update, twin resync, audit) is real and exercised independently of that.

Schema note: `ocr_extractions` / `ocr_extraction_fields` are new tables, not
yet present in any environment's Postgres - see
`supabase/migrations/0001_ocr_extractions.sql`, which must be applied to
Supabase before these endpoints can read/write for real (same situation
`routers/documents.py` was in for `documents`/`document_versions` before
Phase 6's tables existed).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers.documents import _get_document_row
from app.api.v1.routers.twins import resync_twin
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.db.session import get_db_session
from app.dependencies.auth import CurrentUser, require_roles
from app.schemas.ocr import OcrApproveRequest, OcrRejectRequest
from app.services import ocr_provider, storage

router = APIRouter(tags=["ocr"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# The only patient columns OCR is allowed to touch - clinically relevant
# fields already represented on `patients` (see `schemas/clinical.py`
# `PatientInput`). Never invented to make extraction look more capable than
# it is; a field extracted under any other name is dropped on approval.
FIELD_CATALOG: dict[str, dict[str, Any]] = {
    "tumor_size_mm": {"label": "Tumor size (mm)", "cast": float},
    "er_status": {"label": "ER status", "cast": str},
    "pr_status": {"label": "PR status", "cast": str},
    "her2_status": {"label": "HER2 status", "cast": str},
    "ki67": {"label": "Ki-67 (%)", "cast": float},
    "grade": {"label": "Grade", "cast": int},
    "nodes_involved": {"label": "Nodes involved", "cast": int},
    "stage": {"label": "Stage", "cast": str},
    "diagnosed_on": {"label": "Diagnosis date", "cast": str},
}


def _extraction_response(row, fields: list[Any]) -> dict[str, object]:
    return {
        "documentId": row["document_id"],
        "patientId": row["patient_code"],
        "status": row["status"],
        "model": row["model"],
        "extractedAt": row["extracted_at"],
        "reviewedBy": row["reviewed_by_email"],
        "reviewedAt": row["reviewed_at"],
        "rejectReason": row["reject_reason"],
        "fields": [
            {
                "field": f["field_name"],
                "label": f["label"],
                "value": f["extracted_value"],
                "confidence": f["confidence"],
                "status": f["status"],
            }
            for f in fields
        ],
    }


async def _latest_extraction(session: AsyncSession, document_id: str):
    row = (
        await session.execute(
            text(
                """
                SELECT e.*, p.patient_code, prof.email AS reviewed_by_email
                FROM ocr_extractions e
                JOIN patients p ON p.id = e.patient_id
                LEFT JOIN profiles prof ON prof.id = e.reviewed_by
                WHERE e.document_id = :document_id
                ORDER BY e.extracted_at DESC
                LIMIT 1
                """
            ),
            {"document_id": document_id},
        )
    ).mappings().first()
    if row is None:
        raise NotFoundError("No OCR extraction exists for this document yet.")
    return row


async def _fields_for(session: AsyncSession, extraction_id: str) -> list[Any]:
    result = await session.execute(
        text(
            "SELECT field_name, label, extracted_value, confidence, status "
            "FROM ocr_extraction_fields WHERE extraction_id = :id ORDER BY field_name"
        ),
        {"id": extraction_id},
    )
    return list(result.mappings())


@router.post("/ocr/{document_id}/extract", status_code=201)
async def extract_document(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    doc = await _get_document_row(session, document_id)
    settings = get_settings()
    if (doc["mime_type"] or "") not in settings.OCR_SUPPORTED_MIME_TYPES:
        raise ValidationAppError(
            f"Unsupported document type for OCR ({doc['mime_type'] or 'unknown'}). "
            f"Supported: {', '.join(settings.OCR_SUPPORTED_MIME_TYPES)}.",
            field="document",
        )

    # Retrieves the real stored bytes - failures here are genuine storage
    # errors, not something extraction can proceed past.
    content = await storage.download_document(doc["storage_path"])
    # Raises UpstreamServiceError (502) when no provider is configured - see
    # services/ocr_provider.py. Nothing is persisted on failure: an OCR run
    # that produced no fields extracted none.
    extracted = await ocr_provider.extract_fields(content, doc["mime_type"])

    extraction_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        text(
            """
            INSERT INTO ocr_extractions
                (id, document_id, patient_id, status, model, extracted_at, created_at)
            SELECT :id, :document_id, d.patient_id, 'Extracted', :model, :now, :now
            FROM documents d WHERE d.id = :document_id
            """
        ),
        {"id": extraction_id, "document_id": document_id, "model": get_settings().OCR_PROVIDER, "now": now},
    )
    for item in extracted:
        catalog_entry = FIELD_CATALOG.get(item.field)
        await session.execute(
            text(
                """
                INSERT INTO ocr_extraction_fields
                    (id, extraction_id, field_name, label, extracted_value, confidence, status, created_at)
                VALUES
                    (:id, :extraction_id, :field_name, :label, :value, :confidence, 'pending', :now)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "extraction_id": extraction_id,
                "field_name": item.field,
                "label": catalog_entry["label"] if catalog_entry else item.field,
                "value": item.value,
                "confidence": item.confidence,
                "now": now,
            },
        )
    await session.commit()

    row = await _latest_extraction(session, document_id)
    fields = await _fields_for(session, extraction_id)
    return {"ok": True, "data": _extraction_response(row, fields), "message": "Extraction complete — requires verification."}


@router.get("/ocr/{document_id}/fields")
async def get_extraction_fields(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    await _get_document_row(session, document_id)  # 404s if missing/isolated
    row = await _latest_extraction(session, document_id)
    fields = await _fields_for(session, str(row["id"]))
    return _extraction_response(row, fields)


@router.post("/ocr/{document_id}/approve")
async def approve_extraction(
    document_id: str,
    payload: OcrApproveRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    row = await _latest_extraction(session, document_id)
    if row["status"] != "Extracted":
        raise ConflictError(f"This extraction was already {row['status'].lower()}.")

    patient_id = str(row["patient_id"])
    updates: dict[str, object] = {}
    approved_field_names: list[str] = []
    for item in payload.fields:
        catalog_entry = FIELD_CATALOG.get(item.field)
        if catalog_entry is None:
            continue  # Not a recognised clinical field - never invented, never applied.
        value = item.value
        # Never let an approved-but-empty field blank out an existing value.
        if value is None or str(value).strip() == "":
            continue
        try:
            updates[item.field] = catalog_entry["cast"](value)
        except (TypeError, ValueError):
            raise ValidationAppError(f"Could not parse the approved value for '{item.field}'.", field=item.field)
        approved_field_names.append(item.field)

    if not updates:
        raise ValidationAppError("At least one non-empty approved field is required.")

    now = _now()
    assignments = ", ".join(f"{key} = :{key}" for key in updates)
    updates["patient_id"] = patient_id
    updates["now"] = now
    await session.execute(
        text(f"UPDATE patients SET {assignments}, last_updated = :now WHERE id = :patient_id"),
        updates,
    )

    await session.execute(
        text(
            "UPDATE ocr_extractions SET status = 'Approved', reviewed_by = :reviewer, reviewed_at = :now "
            "WHERE id = :id"
        ),
        {"reviewer": str(current_user.id), "now": now, "id": row["id"]},
    )
    if approved_field_names:
        await session.execute(
            text(
                "UPDATE ocr_extraction_fields SET status = 'approved' "
                "WHERE extraction_id = :id AND field_name = ANY(:names)"
            ),
            {"id": row["id"], "names": approved_field_names},
        )

    await session.execute(
        text(
            "INSERT INTO timeline_events (id, patient_id, date, title, detail, kind) "
            "VALUES (:id, :pid, :date, :title, :detail, 'note')"
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": patient_id,
            "date": now,
            "title": "Clinician-verified document fields applied",
            "detail": (
                f"{', '.join(approved_field_names)} updated from document {document_id} "
                f"by {current_user.email or current_user.id}."
            ),
        },
    )
    await session.commit()

    # Reuses the existing Digital Twin resync mechanism - no second
    # twin-generation path. Runs no prediction and no treatment simulation.
    await resync_twin(patient_id, session=session, current_user=current_user)

    updated_row = await _latest_extraction(session, document_id)
    fields = await _fields_for(session, str(row["id"]))
    return {
        "ok": True,
        "data": _extraction_response(updated_row, fields),
        "message": "Extraction approved — digital twin resynced.",
    }


@router.post("/ocr/{document_id}/reject")
async def reject_extraction(
    document_id: str,
    payload: OcrRejectRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    row = await _latest_extraction(session, document_id)
    if row["status"] != "Extracted":
        raise ConflictError(f"This extraction was already {row['status'].lower()}.")

    now = _now()
    await session.execute(
        text(
            "UPDATE ocr_extractions SET status = 'Rejected', reviewed_by = :reviewer, "
            "reviewed_at = :now, reject_reason = :reason WHERE id = :id"
        ),
        {"reviewer": str(current_user.id), "now": now, "reason": payload.reason, "id": row["id"]},
    )
    await session.execute(
        text("UPDATE ocr_extraction_fields SET status = 'rejected' WHERE extraction_id = :id"),
        {"id": row["id"]},
    )
    # Patient data and the document itself are untouched - rejection only
    # marks the extraction; the original document and its OCR result remain
    # for audit.
    await session.commit()

    updated_row = await _latest_extraction(session, document_id)
    fields = await _fields_for(session, str(row["id"]))
    return {"ok": True, "data": _extraction_response(updated_row, fields), "message": "Extraction rejected."}
