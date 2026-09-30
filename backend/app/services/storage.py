"""
Document storage - Supabase Storage.

Server-only: every call goes through the service-role client
(`get_admin_client`), which never reaches the frontend. Documents live in a
private bucket, so the only thing a client ever receives is a short-lived
signed URL, never a permanent public link or a raw storage credential.

`supabase-py`'s Storage client is synchronous, so every call is pushed to a
thread - the same pattern `supabase_provider.py` uses for Auth, and for the
same reason: a slow Storage round-trip must not block the event loop.
"""
from __future__ import annotations

import anyio

from app.auth.providers.supabase_provider import get_admin_client
from app.core.config import get_settings
from app.core.exceptions import UpstreamServiceError


def _bucket():
    settings = get_settings()
    if not settings.uses_supabase:
        raise UpstreamServiceError(
            "Document storage requires AUTH_PROVIDER=supabase. Configure Supabase to enable uploads."
        )
    return get_admin_client().storage.from_(settings.SUPABASE_STORAGE_BUCKET)


async def upload_document(storage_path: str, content: bytes, content_type: str) -> None:
    def _call():
        _bucket().upload(
            storage_path,
            content,
            {"content-type": content_type, "upsert": "false"},
        )

    try:
        await anyio.to_thread.run_sync(_call)
    except Exception as exc:  # supabase-py raises its own StorageException
        raise UpstreamServiceError(f"Could not store the uploaded file: {exc}") from exc


async def download_document(storage_path: str) -> bytes:
    """Fetch the actual stored bytes - used by OCR extraction, never by any
    client-facing route (those get a signed URL instead)."""

    def _call():
        return _bucket().download(storage_path)

    try:
        return await anyio.to_thread.run_sync(_call)
    except Exception as exc:  # supabase-py raises its own StorageException
        raise UpstreamServiceError(f"Could not retrieve the stored file: {exc}") from exc


async def delete_document(storage_path: str) -> None:
    """Best-effort cleanup - e.g. after a database write fails post-upload."""

    def _call():
        _bucket().remove([storage_path])

    try:
        await anyio.to_thread.run_sync(_call)
    except Exception:  # pragma: no cover - cleanup only, never surfaced to the caller
        pass


async def create_signed_url(storage_path: str) -> str:
    settings = get_settings()

    def _call():
        result = _bucket().create_signed_url(storage_path, settings.DOCUMENT_SIGNED_URL_TTL_SECONDS)
        return result["signedURL"] if isinstance(result, dict) else result.get("signed_url")  # type: ignore[union-attr]

    try:
        url = await anyio.to_thread.run_sync(_call)
    except Exception as exc:
        raise UpstreamServiceError(f"Could not create a download link: {exc}") from exc
    if not url:
        raise UpstreamServiceError("Could not create a download link.")
    return url
