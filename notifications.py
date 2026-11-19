"""Notifications simulées du MVP."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..errors import NotFoundError
from ..models import Notification, NotificationType


def notify(
    session: Session,
    user_id: int,
    *,
    type: NotificationType,
    title: str,
    message: str,
    link_page: str | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        link_page=link_page,
    )
    session.add(notification)
    return notification


def list_notifications(session: Session, user_id: int, limit: int = 60) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def unread_count(session: Session, user_id: int) -> int:
    stmt = select(func.count(Notification.id)).where(Notification.user_id == user_id, Notification.is_read.is_(False))
    return int(session.scalar(stmt) or 0)


def mark_read(session: Session, user_id: int, notification_id: int) -> Notification:
    notification = session.get(Notification, notification_id)
    if not notification or notification.user_id != user_id:
        raise NotFoundError("Notification introuvable.", code="notification_not_found")
    notification.is_read = True
    return notification


def mark_all_read(session: Session, user_id: int) -> int:
    result = session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    return int(result.rowcount or 0)
