from sqlalchemy import or_
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _row_to_schema(n: models.NotificationItem) -> schemas.NotificationItem:
    return schemas.NotificationItem(id=n.id, title=n.title, body=n.body, time=n.time, unread=n.unread, type=n.type)


@router.get("", response_model=list[schemas.NotificationItem])
def list_notifications(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = (
        db.query(models.NotificationItem)
        .filter(or_(models.NotificationItem.user_id == user.id, models.NotificationItem.audience_role == user.role))
        .order_by(models.NotificationItem.time.desc())
        .all()
    )
    return [_row_to_schema(n) for n in rows]


@router.post("/{notification_id}/read", response_model=schemas.MutationResult)
def mark_read(notification_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    n = db.get(models.NotificationItem, notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    if n.user_id != user.id and n.audience_role != user.role:
        raise HTTPException(status_code=403, detail="Not authorized to modify this notification")
    n.unread = False
    db.commit()
    return schemas.MutationResult(ok=True, message="Marked as read")


@router.post("/read-all", response_model=schemas.MutationResult)
def mark_all_read(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = (
        db.query(models.NotificationItem)
        .filter(or_(models.NotificationItem.user_id == user.id, models.NotificationItem.audience_role == user.role))
        .all()
    )
    for n in rows:
        n.unread = False
    db.commit()
    return schemas.MutationResult(ok=True, message="All notifications marked as read")
