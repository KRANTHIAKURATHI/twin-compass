"""
Audit logging for clinical changes.

Writes one row per clinical operation to the existing `audit_logs` table
(columns: id, time, actor, actor_role, action, target, before, after, ip).

Transactional contract
----------------------
`record_audit` only *adds* the INSERT to the caller's open transaction. It
never commits and never swallows a failure, so the audit row and the business
change either commit together or roll back together. Callers must invoke it
before their single `session.commit()`.

Privacy contract
----------------
`before` / `after` hold only identifiers, version labels and the allow-listed
clinical fields below. Patient names, contact details, free-text notes, raw OCR
text, rejection reasons and credentials never belong in an audit payload;
`record_audit` refuses a payload that carries such a key at any depth.

Access note: `before` / `after` contain clinical values. The backend's database
role bypasses RLS, so these columns must only ever be exposed through endpoints
restricted to authorised internal roles.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import request_id_var

# The only patient columns whose values may appear in before/after.
PATIENT_AUDIT_FIELDS: tuple[str, ...] = (
    "tumor_size_mm",
    "er_status",
    "pr_status",
    "her2_status",
    "ki67",
    "grade",
    "nodes_involved",
    "stage",
    "diagnosed_on",
    "risk",
    "status",
    "survival_probability",
    "twin_status",
)

# Keys that must never be written to an audit payload (matched case-insensitively).
FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "name", "patient_name", "patientname", "phone", "email", "notes", "history",
        "reason", "reject_reason", "rejectreason", "raw_text", "rawtext", "ocr_text", "text",
        "password", "token", "access_token", "refresh_token", "secret", "api_key", "apikey",
        "authorization",
    }
)


def utc_now_iso() -> str:
    """ISO-8601 UTC timestamp (`audit_logs.time` is a text column)."""
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def pick_patient_fields(row: Mapping[str, Any], fields: tuple[str, ...] | list[str] | None = None) -> dict[str, Any]:
    """Allow-listed patient fields from `row`, JSON-safe. `fields` can only narrow the allow-list."""
    wanted = [f for f in (fields if fields is not None else PATIENT_AUDIT_FIELDS) if f in PATIENT_AUDIT_FIELDS]
    return {f: _json_safe(row[f]) for f in wanted if f in row.keys()}


def _assert_safe(payload: Any, path: str = "") -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"audit payload may not contain '{path}{key}'")
            _assert_safe(value, f"{path}{key}.")
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            _assert_safe(item, path)


def _dump(payload: Mapping[str, Any] | None) -> str | None:
    if payload is None:
        return None
    _assert_safe(payload)
    return json.dumps(payload, default=str)


async def record_audit(
    session: AsyncSession,
    *,
    actor: Any,
    action: str,
    target: str,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
) -> None:
    """Add an audit row to the caller's transaction (no commit).

    `actor` is the authenticated `CurrentUser`: its UUID is stored as `actor`
    and its role as `actor_role`. `target` is the patient_code. `ip` stays empty.
    The request id (when present) is added to `after` for log correlation.
    """
    after_payload: dict[str, Any] | None = dict(after) if after is not None else None
    request_id = request_id_var.get()
    if request_id:
        after_payload = {**(after_payload or {}), "requestId": request_id}

    await session.execute(
        text(
            "INSERT INTO audit_logs (id, time, actor, actor_role, action, target, before, after, ip) "
            "VALUES (:id, :time, :actor, :role, :action, :target, :before, :after, '')"
        ),
        {
            "id": str(uuid.uuid4()),
            "time": utc_now_iso(),
            "actor": str(actor.id),
            "role": str(actor.role),
            "action": action,
            "target": target,
            "before": _dump(before),
            "after": _dump(after_payload),
        },
    )
