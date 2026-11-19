"""Promotions locales des commerces partenaires."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from ..errors import AccessDenied, NotFoundError, ValidationError
from ..models import Merchant, Promotion, utcnow
from . import audit


def get_promotion(session: Session, promotion_id: int) -> Promotion:
    stmt = select(Promotion).options(joinedload(Promotion.merchant)).where(Promotion.id == promotion_id)
    promotion = session.scalar(stmt)
    if not promotion:
        raise NotFoundError("Promotion introuvable.", code="promotion_not_found")
    return promotion


def _assert_owner(session: Session, merchant_id: int, actor_id: int) -> Merchant:
    merchant = session.get(Merchant, merchant_id)
    if not merchant:
        raise NotFoundError("Commerce introuvable.", code="merchant_not_found")
    if merchant.owner_id != actor_id:
        raise AccessDenied("Ce commerce ne vous appartient pas.", code="merchant_access_denied")
    return merchant


def list_promotions(
    session: Session,
    *,
    city: str | None = None,
    neighborhood: str | None = None,
    category: str | None = None,
    merchant_id: int | None = None,
    search: str | None = None,
    active_only: bool = True,
    limit: int = 100,
) -> list[Promotion]:
    now = utcnow()
    stmt = (
        select(Promotion)
        .join(Merchant, Promotion.merchant_id == Merchant.id)
        .options(joinedload(Promotion.merchant))
        .where(Merchant.is_active.is_(True))
    )
    if active_only:
        stmt = stmt.where(
            Promotion.is_active.is_(True),
            Promotion.starts_at <= now,
            Promotion.expires_at >= now,
        )
    if city:
        stmt = stmt.where(Promotion.city == city)
    if neighborhood:
        stmt = stmt.where(Promotion.neighborhood == neighborhood)
    if category:
        stmt = stmt.where(Merchant.category == category)
    if merchant_id:
        stmt = stmt.where(Promotion.merchant_id == merchant_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Promotion.title.ilike(like),
                Promotion.description.ilike(like),
                Merchant.business_name.ilike(like),
            )
        )
    stmt = stmt.order_by(Promotion.expires_at.asc(), Promotion.id.desc()).limit(limit)
    return list(session.scalars(stmt).unique())


def list_merchant_promotions(session: Session, merchant_id: int) -> list[Promotion]:
    stmt = (
        select(Promotion)
        .where(Promotion.merchant_id == merchant_id)
        .order_by(Promotion.is_active.desc(), Promotion.created_at.desc())
    )
    return list(session.scalars(stmt))


def create_promotion(
    session: Session,
    *,
    merchant_id: int,
    actor_id: int,
    title: str,
    description: str,
    icon: str,
    city: str,
    neighborhood: str,
    starts_at: datetime,
    expires_at: datetime,
) -> Promotion:
    merchant = _assert_owner(session, merchant_id, actor_id)
    clean_title = (title or "").strip()
    if len(clean_title) < 3:
        raise ValidationError("Le titre de la promotion est obligatoire.", code="promotion_title_required")
    if expires_at <= starts_at:
        raise ValidationError("La date de fin doit être postérieure à la date de début.", code="invalid_dates")
    promotion = Promotion(
        merchant_id=merchant_id,
        title=clean_title,
        description=(description or "").strip(),
        icon=(icon or "🏷️")[:8],
        city=(city or merchant.city).strip(),
        neighborhood=(neighborhood or merchant.neighborhood).strip(),
        starts_at=starts_at,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(promotion)
    session.flush()
    audit.record(
        session,
        actor_id=actor_id,
        action="PROMOTION_CREATED",
        entity_type="Promotion",
        entity_id=promotion.id,
        metadata={"merchant_id": merchant_id},
    )
    return promotion


def update_promotion(
    session: Session,
    *,
    promotion_id: int,
    actor_id: int,
    title: str,
    description: str,
    icon: str,
    city: str,
    neighborhood: str,
    starts_at: datetime,
    expires_at: datetime,
    is_active: bool,
) -> Promotion:
    promotion = get_promotion(session, promotion_id)
    _assert_owner(session, promotion.merchant_id, actor_id)
    clean_title = (title or "").strip()
    if len(clean_title) < 3:
        raise ValidationError("Le titre de la promotion est obligatoire.", code="promotion_title_required")
    if expires_at <= starts_at:
        raise ValidationError("La date de fin doit être postérieure à la date de début.", code="invalid_dates")
    promotion.title = clean_title
    promotion.description = (description or "").strip()
    promotion.icon = (icon or "🏷️")[:8]
    promotion.city = (city or "").strip()
    promotion.neighborhood = (neighborhood or "").strip()
    promotion.starts_at = starts_at
    promotion.expires_at = expires_at
    promotion.is_active = is_active
    audit.record(
        session,
        actor_id=actor_id,
        action="PROMOTION_UPDATED",
        entity_type="Promotion",
        entity_id=promotion.id,
    )
    return promotion


def set_promotion_active(session: Session, *, promotion_id: int, actor_id: int, active: bool) -> Promotion:
    promotion = get_promotion(session, promotion_id)
    _assert_owner(session, promotion.merchant_id, actor_id)
    promotion.is_active = active
    audit.record(
        session,
        actor_id=actor_id,
        action="PROMOTION_ACTIVATED" if active else "PROMOTION_DEACTIVATED",
        entity_type="Promotion",
        entity_id=promotion.id,
    )
    return promotion
