"""Statistiques agrégées pour les tableaux de bord."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, joinedload

from ..models import (
    GiftCard,
    GiftCardStatus,
    LoyaltyAccount,
    Merchant,
    PointTransaction,
    RedemptionStatus,
    RewardRedemption,
    TransactionType,
    User,
    UserRole,
    utcnow,
)


def _day_key(value: datetime) -> date:
    return value.date()


def _daily_series(rows: list[tuple[datetime, int]], days: int) -> list[dict]:
    today = utcnow().date()
    start = today - timedelta(days=days - 1)
    buckets = {start + timedelta(days=offset): {"count": 0, "points": 0} for offset in range(days)}
    for created_at, points in rows:
        key = _day_key(created_at)
        if key in buckets:
            buckets[key]["count"] += 1
            buckets[key]["points"] += int(points)
    return [{"date": day, **values} for day, values in sorted(buckets.items())]


def _merchant_transactions(session: Session, merchant_id: int, days: int) -> list[PointTransaction]:
    since = utcnow() - timedelta(days=days)
    stmt = (
        select(PointTransaction)
        .options(joinedload(PointTransaction.user))
        .where(PointTransaction.merchant_id == merchant_id, PointTransaction.created_at >= since)
        .order_by(PointTransaction.created_at.asc())
    )
    return list(session.scalars(stmt))


def merchant_dashboard(session: Session, merchant_id: int, *, days: int = 14) -> dict:
    merchant = session.get(Merchant, merchant_id)
    if not merchant:
        return {}
    purchases = (
        session.scalar(
            select(func.count(PointTransaction.id)).where(
                PointTransaction.merchant_id == merchant_id,
                PointTransaction.type == TransactionType.EARNED,
            )
        )
        or 0
    )
    points_distributed = (
        session.scalar(
            select(func.coalesce(func.sum(PointTransaction.points), 0)).where(
                PointTransaction.merchant_id == merchant_id,
                PointTransaction.type == TransactionType.EARNED,
            )
        )
        or 0
    )
    clients = (
        session.scalar(
            select(func.count(distinct(PointTransaction.user_id))).where(
                PointTransaction.merchant_id == merchant_id,
                PointTransaction.type == TransactionType.EARNED,
            )
        )
        or 0
    )
    first_purchase = (
        select(
            PointTransaction.user_id.label("user_id"),
            func.min(PointTransaction.created_at).label("first_at"),
        )
        .where(
            PointTransaction.merchant_id == merchant_id,
            PointTransaction.type == TransactionType.EARNED,
        )
        .group_by(PointTransaction.user_id)
        .subquery()
    )
    cutoff = utcnow() - timedelta(days=30)
    new_clients = (
        session.scalar(select(func.count()).select_from(first_purchase).where(first_purchase.c.first_at >= cutoff)) or 0
    )
    rewards_used = (
        session.scalar(
            select(func.count(RewardRedemption.id)).where(
                RewardRedemption.validated_by_merchant_id == merchant_id,
                RewardRedemption.status == RedemptionStatus.USED,
            )
        )
        or 0
    )
    gift_cards = (
        session.scalar(
            select(func.count(GiftCard.id)).where(
                GiftCard.merchant_id == merchant_id, GiftCard.status != GiftCardStatus.CANCELLED
            )
        )
        or 0
    )

    transactions = _merchant_transactions(session, merchant_id, days)
    rows = [(t.created_at, t.points) for t in transactions if t.type == TransactionType.EARNED]
    series = _daily_series(rows, days)

    recent_stmt = (
        select(PointTransaction)
        .options(joinedload(PointTransaction.user))
        .where(PointTransaction.merchant_id == merchant_id)
        .order_by(PointTransaction.created_at.desc())
        .limit(6)
    )
    recent = [
        {
            "created_at": t.created_at,
            "type": t.type,
            "points": t.points,
            "client": t.user.full_name if t.user else "—",
            "description": t.description,
        }
        for t in session.scalars(recent_stmt)
    ]

    top_clients = _top_clients(session, merchant_id)
    return {
        "merchant": merchant,
        "clients": int(clients),
        "new_clients": int(new_clients),
        "points_distributed": int(points_distributed),
        "rewards_used": int(rewards_used),
        "gift_cards": int(gift_cards),
        "purchases": int(purchases),
        "series": series,
        "recent": recent,
        "top_clients": top_clients,
    }


def _top_clients(session: Session, merchant_id: int, limit: int = 5) -> list[dict]:
    stmt = (
        select(
            User.id,
            User.first_name,
            User.last_name,
            User.phone,
            User.city,
            LoyaltyAccount.total_points,
            func.sum(PointTransaction.points).label("earned_here"),
            func.max(PointTransaction.created_at).label("last_visit"),
            func.count(PointTransaction.id).label("purchases"),
        )
        .join(PointTransaction, PointTransaction.user_id == User.id)
        .join(LoyaltyAccount, LoyaltyAccount.user_id == User.id)
        .where(
            PointTransaction.merchant_id == merchant_id,
            PointTransaction.type == TransactionType.EARNED,
        )
        .group_by(
            User.id,
            User.first_name,
            User.last_name,
            User.phone,
            User.city,
            LoyaltyAccount.total_points,
        )
        .order_by(func.sum(PointTransaction.points).desc())
        .limit(limit)
    )
    return [
        {
            "id": row.id,
            "name": f"{row.first_name} {row.last_name}",
            "phone": row.phone,
            "city": row.city,
            "balance": int(row.total_points),
            "earned_here": int(row.earned_here or 0),
            "last_visit": row.last_visit,
            "purchases": int(row.purchases or 0),
        }
        for row in session.execute(stmt)
    ]


def merchant_clients(session: Session, merchant_id: int, *, search: str | None = None) -> list[dict]:
    stmt = (
        select(
            User.id,
            User.first_name,
            User.last_name,
            User.phone,
            User.city,
            User.neighborhood,
            LoyaltyAccount.total_points,
            func.sum(PointTransaction.points).label("earned_here"),
            func.max(PointTransaction.created_at).label("last_visit"),
            func.count(PointTransaction.id).label("purchases"),
        )
        .join(PointTransaction, PointTransaction.user_id == User.id)
        .join(LoyaltyAccount, LoyaltyAccount.user_id == User.id)
        .where(
            PointTransaction.merchant_id == merchant_id,
            PointTransaction.type == TransactionType.EARNED,
        )
        .group_by(
            User.id,
            User.first_name,
            User.last_name,
            User.phone,
            User.city,
            User.neighborhood,
            LoyaltyAccount.total_points,
        )
        .order_by(func.max(PointTransaction.created_at).desc())
    )
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where((User.first_name.ilike(like)) | (User.last_name.ilike(like)) | (User.phone.ilike(like)))
    return [
        {
            "id": row.id,
            "name": f"{row.first_name} {row.last_name}",
            "phone": row.phone,
            "city": row.city,
            "neighborhood": row.neighborhood,
            "balance": int(row.total_points),
            "earned_here": int(row.earned_here or 0),
            "last_visit": row.last_visit,
            "purchases": int(row.purchases or 0),
        }
        for row in session.execute(stmt)
    ]


def merchant_transactions(
    session: Session,
    merchant_id: int,
    *,
    type_filter: TransactionType | None = None,
    limit: int = 200,
) -> list[PointTransaction]:
    stmt = (
        select(PointTransaction)
        .options(joinedload(PointTransaction.user))
        .where(PointTransaction.merchant_id == merchant_id)
    )
    if type_filter:
        stmt = stmt.where(PointTransaction.type == type_filter)
    stmt = stmt.order_by(PointTransaction.created_at.desc()).limit(limit)
    return list(session.scalars(stmt))


def admin_overview(session: Session, *, days: int = 30) -> dict:
    client_count = session.scalar(select(func.count(User.id)).where(User.role == UserRole.CLIENT)) or 0
    merchant_owners = session.scalar(select(func.count(User.id)).where(User.role == UserRole.MERCHANT)) or 0
    merchant_count = session.scalar(select(func.count(Merchant.id))) or 0
    active_merchants = session.scalar(select(func.count(Merchant.id)).where(Merchant.is_active.is_(True))) or 0
    txn_count = session.scalar(select(func.count(PointTransaction.id))) or 0
    points_distributed = (
        session.scalar(
            select(func.coalesce(func.sum(PointTransaction.points), 0)).where(
                PointTransaction.type == TransactionType.EARNED
            )
        )
        or 0
    )
    redemptions_used = (
        session.scalar(select(func.count(RewardRedemption.id)).where(RewardRedemption.status == RedemptionStatus.USED))
        or 0
    )
    gift_cards = session.scalar(select(func.count(GiftCard.id))) or 0
    gift_card_volume = session.scalar(select(func.coalesce(func.sum(GiftCard.amount), 0))) or Decimal("0.00")

    since = utcnow() - timedelta(days=days)
    rows = list(
        session.execute(
            select(PointTransaction.created_at, PointTransaction.points).where(PointTransaction.created_at >= since)
        )
    )
    series = _daily_series([(row[0], row[1]) for row in rows], days)
    city_rows = session.execute(
        select(Merchant.city, func.count(Merchant.id)).group_by(Merchant.city).order_by(func.count(Merchant.id).desc())
    )
    cities = [{"city": city, "merchants": int(count)} for city, count in city_rows]
    return {
        "clients": int(client_count),
        "merchant_owners": int(merchant_owners),
        "merchants": int(merchant_count),
        "active_merchants": int(active_merchants),
        "transactions": int(txn_count),
        "points_distributed": int(points_distributed),
        "redemptions_used": int(redemptions_used),
        "gift_cards": int(gift_cards),
        "gift_card_volume": Decimal(gift_card_volume),
        "series": series,
        "cities": cities,
    }
