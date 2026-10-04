"""
Documents router (Phase 6).

Reads and writes the `documents` / `document_versions` tables the same way
`routers/twins.py` and `routers/predictions.py` read `twin_versions` /
`prediction_runs` - raw SQL against tables that live in Supabase Postgres,
not in any local migration (see `services/clinical_queries.py`'s module
docstring). The uploaded file itself is never stored in Postgres: it goes to
a private Supabase Storage bucket (`services/storage.py`), and only the
storage path/metadata are persisted here.

OCR (extraction, approval, twin updates from a document) is explicitly out
of scope - Phase 7. `status` on a freshly uploaded document is always
"Pending OCR" because nothing here has looked at its contents.

Links/timeline: there is no `document_id` column anywhere else in the
schema, so "linked records" for a document is only ever its patient (real),
and "timeline" is the document's own version history projected as events -
not a fabricated cross-module trail.
"""
from __future__ import annotations

import mimetypes
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.db.session import get_db_session
from app.dependencies.auth import CurrentUser, require_roles
from app.services import storage
from app.services.clinical_queries import resolve_patient

router = APIRouter(tags=["documents"])

_MAGIC_SNIFFERS: dict[str, bytes] = {
    "application/pdf": b"%PDF-",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _human_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def _safe_filename(name: str) -> str:
    """Strips any path component and disallowed characters.

    `secure_filename`-style handling - a filename of `../../etc/passwd` or
    one embedding a storage-path separator must not be able to influence
    where the object lands, since `storage_path` is built by joining this
    value onto the patient's own storage prefix.
    """
    base = (name or "upload").replace("\\", "/").rsplit("/", 1)[-1].strip()
    base = _UNSAFE_FILENAME_CHARS.sub("_", base) or "upload"
    return base[-180:]  # keep storage keys bounded


def _sniff_mime(content: bytes, declared: str | None) -> str:
    for mime, magic in _MAGIC_SNIFFERS.items():
        if content.startswith(magic):
            return mime
    # No magic match: fall back to the declared/guessed type so a file type
    # this sniffer does not know is not rejected outright, but it will still
    # be checked against the allow-list below.
    return declared or mimetypes.guess_type("x")[0] or "application/octet-stream"


def _document_response(row) -> dict[str, object]:
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"] or "Other",
        "patient": row["patient_name"],
        "patientId": row["patient_code"],
        "date": row["created_at"],
        "size": _human_size(row["size_bytes"] or 0),
        "sizeBytes": row["size_bytes"] or 0,
        "mimeType": row["mime_type"] or "",
        "version": row["version"] or 1,
        "status": row["status"] or "Pending OCR",
    }


_DOCUMENT_SELECT = """
    SELECT d.id, d.name, d.category, d.mime_type, d.size_bytes, d.storage_path,
           d.version, d.status, COALESCE(d.created_at, d.date) AS created_at,
           p.patient_code, p.name AS patient_name
    FROM documents d
    JOIN patients p ON p.id = d.patient_id
"""


@router.get("/documents")
async def list_documents(
    patientId: str | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    where = ["p.deleted_at IS NULL"]
    params: dict[str, object] = {}
    if patientId:
        where.append("(p.patient_code = :patient_id OR p.id::text = :patient_id)")
        params["patient_id"] = patientId
    if search:
        where.append("(d.name ILIKE :search OR p.name ILIKE :search)")
        params["search"] = f"%{search}%"
    query = (
        f"{_DOCUMENT_SELECT} WHERE {' AND '.join(where)} "
        "ORDER BY COALESCE(d.created_at, d.date) DESC"
    )
    result = await session.execute(text(query), params)
    return [_document_response(row) for row in result.mappings()]


async def _get_document_row(session: AsyncSession, document_id: str):
    row = (
        await session.execute(
            text(f"{_DOCUMENT_SELECT} WHERE d.id = :id AND p.deleted_at IS NULL"),
            {"id": document_id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return row


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    row = await _get_document_row(session, document_id)
    return _document_response(row)


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    patient_id: str = Form(..., alias="patientId"),
    category: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    settings = get_settings()
    patient = await resolve_patient(session, patient_id)

    content = await file.read()
    if not content:
        raise ValidationAppError("The selected file is empty.", field="file")
    max_bytes = settings.DOCUMENT_MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.DOCUMENT_MAX_UPLOAD_MB} MB upload limit.",
        )

    mime_type = _sniff_mime(content, file.content_type)
    if mime_type not in settings.DOCUMENT_ALLOWED_MIME_TYPES:
        raise ValidationAppError(
            f"Unsupported file type ({mime_type}). Allowed: {', '.join(settings.DOCUMENT_ALLOWED_MIME_TYPES)}.",
            field="file",
        )

    doc_id = str(uuid.uuid4())
    pid = str(patient["id"])
    safe_name = _safe_filename(file.filename or "upload")
    storage_path = f"{pid}/{doc_id}_{safe_name}"
    now = _now()

    await storage.upload_document(storage_path, content, mime_type)

    try:
        await session.execute(
            text(
                """
                INSERT INTO documents
                    (id, patient_id, name, category, mime_type, size_bytes, storage_path,
                     version, status, uploaded_by, created_at, updated_at)
                VALUES
                    (:id, :patient_id, :name, :category, :mime_type, :size_bytes, :storage_path,
                     1, 'Pending OCR', :uploaded_by, :created_at, :created_at)
                """
            ),
            {
                "id": doc_id,
                "patient_id": pid,
                "name": safe_name,
                "category": category,
                "mime_type": mime_type,
                "size_bytes": len(content),
                "storage_path": storage_path,
                "uploaded_by": str(current_user.id),
                "created_at": now,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO document_versions
                    (id, document_id, version, created_at, author, note, storage_path, size_bytes)
                VALUES
                    (:id, :document_id, 1, :created_at, :author, 'Original upload', :storage_path, :size_bytes)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "document_id": doc_id,
                "created_at": now,
                "author": current_user.email or str(current_user.id),
                "storage_path": storage_path,
                "size_bytes": len(content),
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()
        await storage.delete_document(storage_path)
        raise

    row = await _get_document_row(session, doc_id)
    return {"ok": True, "data": _document_response(row), "message": f"{safe_name} uploaded."}


@router.get("/documents/{document_id}/versions")
async def document_versions(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    await _get_document_row(session, document_id)  # 404s if missing/isolated
    result = await session.execute(
        text(
            "SELECT version, COALESCE(created_at, date) AS created_at, author, note "
            "FROM document_versions "
            "WHERE document_id = :id ORDER BY version DESC"
        ),
        {"id": document_id},
    )
    return [
        {
            "version": row["version"],
            "date": row["created_at"],
            "author": row["author"] or "",
            "note": row["note"] or "",
        }
        for row in result.mappings()
    ]


@router.get("/documents/{document_id}/timeline")
async def document_timeline(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> list[dict[str, object]]:
    """The document's own version history as a timeline - not a fabricated
    cross-module trail (see module docstring)."""
    await _get_document_row(session, document_id)
    versions = await document_versions(document_id, session=session, _user=_user)
    return [
        {
            "date": v["date"],
            "title": "Original upload" if v["version"] == 1 else f"Version {v['version']}",
            "detail": f"{v['note']} — {v['author']}" if v["note"] else v["author"],
            "kind": "note",
        }
        for v in sorted(versions, key=lambda v: v["version"])
    ]


@router.get("/documents/{document_id}/links")
async def document_links(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    """Only the patient link is backed by real data - see module docstring
    for why twin/prediction/report links are not fabricated here."""
    row = await _get_document_row(session, document_id)
    return {
        "patientId": row["patient_code"],
        "patient": row["patient_name"],
        "twinVersion": None,
        "prediction": None,
        "report": None,
    }


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    row = await _get_document_row(session, document_id)
    if not row["storage_path"]:
        # Rows created before file storage existed have metadata only.
        raise HTTPException(status_code=404, detail="No stored file for this document.")
    url = await storage.create_signed_url(row["storage_path"])
    return {"url": url, "expiresIn": get_settings().DOCUMENT_SIGNED_URL_TTL_SECONDS}


_PREVIEWABLE_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}


@router.get("/documents/{document_id}/preview")
async def preview_document(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    _user: CurrentUser = Depends(require_roles("doctor", "researcher", "admin")),
) -> dict[str, object]:
    row = await _get_document_row(session, document_id)
    mime_type = row["mime_type"] or ""
    if mime_type not in _PREVIEWABLE_MIME_TYPES or not row["storage_path"]:
        return {"available": False, "mimeType": mime_type, "url": None}
    url = await storage.create_signed_url(row["storage_path"])
    return {"available": True, "mimeType": mime_type, "url": url}
