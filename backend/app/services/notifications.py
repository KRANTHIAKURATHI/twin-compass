"""
Notification producers: write role-broadcast rows into the existing `notifications` table.

A broadcast row has `user_id = NULL` and `audience_role` set, which is exactly what
`GET /notifications` already returns to every user holding that role (see
`api/v1/routers/notifications.py`). `user_id` is deliberately never set: it references the
legacy `users` table, while sign-in identities are `profiles` ids.

Best-effort by design. Callers invoke this only AFTER their business operation has
committed, so a failure here is logged and swallowed: it never turns a successful request
into a failed one, and the rollback below can only discard the notification rows because
nothing else is pending on the session.

Messages carry identifiers only (patient code, document / run id). Never put patient
names, clinical values, predictions or extracted content in a notification.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


async def notify_roles(
    session: AsyncSession,
    roles: Iterable[str],
    *,
    type_: str,
    title: str,
    body: str,
) -> bool:
    """Insert one broadcast notification per role in a single transaction. Returns False on failure."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        for role in roles:
            await session.execute(
                text(
                    "INSERT INTO notifications (id, user_id, audience_role, title, body, time, unread, type) "
                    "VALUES (:id, NULL, :role, :title, :body, :time, :unread, :type)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "role": role,
                    "title": title,
                    "body": body,
                    "time": now,
                    "unread": True,
                    "type": type_,
                },
            )
        await session.commit()
        return True
    except Exception as exc:  # noqa: BLE001 - a notification must never break the business operation
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            pass
        logger.warning(
            "notification creation failed",
            extra={"extra_fields": {"type": type_, "error": type(exc).__name__}},
        )
        return False
