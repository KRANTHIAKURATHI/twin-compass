"""
Notifications router.

Reads and updates the existing `notifications` table (id, user_id,
audience_role, title, body, time, unread, type) with raw SQL, the same way
`documents.py` / `twins.py` use tables that live in Supabase Postgres rather
than in a local migration. This replaces the legacy sync
`app/routers/notifications.py`, which is not mounted by the running app.

A notification belongs to a caller when it is addressed to them directly
(`user_id`) or broadcast to their role (`audience_role`). `user_id` is a text
column, so the caller's profile id is compared as text.

Nothing in the application creates notifications yet, so an empty list is the
real answer until a producer exists - it is not padded with sample data.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.dependencies.auth import CurrentUser, get_current_user

router = APIRouter(tags=["notifications"])

_OWNED = "(user_id = :user_id OR audience_role = :role)"


def _params(user: CurrentUser) -> dict[str, str]:
    return {"user_id": str(user.id), "role": str(user.role)}


@router.get("/notifications")
async def list_notifications(
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, object]]:
    result = await session.execute(
        text(
            "SELECT id, title, body, time, unread, type FROM notifications "
            f"WHERE {_OWNED} ORDER BY time DESC"
        ),
        _params(user),
    )
    return [
        {
            "id": row["id"],
            "title": row["title"] or "",
            "body": row["body"] or "",
            "time": row["time"] or "",
            "unread": bool(row["unread"]),
            "type": row["type"],
        }
        for row in result.mappings()
    ]


@router.post("/notifications/read-all")
async def mark_all_read(
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    await session.execute(
        text(f"UPDATE notifications SET unread = false WHERE unread AND {_OWNED}"),
        _params(user),
    )
    await session.commit()
    return {"ok": True, "message": "All notifications marked as read"}


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    row = (
        await session.execute(
            text("SELECT user_id, audience_role FROM notifications WHERE id = :id"),
            {"id": notification_id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if row["user_id"] != str(user.id) and row["audience_role"] != str(user.role):
        raise HTTPException(status_code=403, detail="Not authorized to modify this notification.")
    await session.execute(
        text("UPDATE notifications SET unread = false WHERE id = :id"),
        {"id": notification_id},
    )
    await session.commit()
    return {"ok": True, "message": "Marked as read"}
