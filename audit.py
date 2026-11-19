"""Journal d'audit applicatif (actions sensibles uniquement)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog


def record(
    session: Session,
    *,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        metadata_json=metadata or {},
    )
    session.add(entry)
    return entry
