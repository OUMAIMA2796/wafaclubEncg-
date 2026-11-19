"""Catalogue et cycle de vie des récompenses."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from ..config import REWARD_CODE_TTL_DAYS
from ..errors import AccessDenied, ConflictError, NotFoundError, ValidationError
from ..models import (
    LoyaltyAccount,
    Merchant,
    NotificationType,
    PointTransaction,
    RedemptionStatus,
    Reward,
    RewardRedemption,
    RewardType,
    TransactionType,
    User,
    UserRole,
    utcnow,
)
from ..security import generate_code, generate_reference, to_decimal
from . import audit, notifications


def _clean_title(value: str) -> str:
    title = (value or "").strip()
    if len(title) < 3:
        raise ValidationError("Le titre de la récompense est obligatoire.", code="reward_title_required")
    return title


def _validate_dates(starts_at: datetime, expires_at: datetime) -> None:
    if expires_at <= starts_at:
        raise ValidationError(
            "La date de fin doit être postérieure à la date de début.",
            code="invalid_dates",
        )


def _assert_owner(session: Session, merchant_id: int, actor_id: int) -> Merchant:
    merchant = session.get(Merchant, merchant_id)
    if not merchant:
        raise NotFoundError("Commerce introuvable.", code="merchant_not_found")
    if merchant.owner_id != actor_id:
        raise AccessDenied("Ce commerce ne vous appartient pas.", code="merchant_access_denied")
    return merchant


def get_reward(session: Session, reward_id: int) -> Reward:
    stmt = select(Reward).options(joinedload(Reward.merchant)).where(Reward.id == reward_id)
    reward = session.scalar(stmt)
    if not reward:
        raise NotFoundError("Récompense introuvable.", code="reward_not_found")
    return reward


def list_catalog(
    session: Session,
    *,
    city: str | None = None,
    category: str | None = None,
    merchant_id: int | None = None,
    limit: int = 100,
) -> list[Reward]:
    now = utcnow()
    stmt = (
        select(Reward)
        .outerjoin(Merchant, Reward.merchant_id == Merchant.id)
        .options(joinedload(Reward.merchant))
        .where(
            Reward.is_active.is_(True),
            Reward.starts_at <= now,
            Reward.expires_at >= now,
            or_(Reward.merchant_id.is_(None), Merchant.is_active.is_(True)),
            or_(Reward.stock.is_(None), Reward.stock > 0),
        )
    )
    if city:
        stmt = stmt.where(or_(Merchant.city == city, Reward.merchant_id.is_(None)))
    if category:
        stmt = stmt.where(or_(Merchant.category == category, Reward.merchant_id.is_(None)))
    if merchant_id:
        stmt = stmt.where(Reward.merchant_id == merchant_id)
    stmt = stmt.order_by(Reward.points_cost.asc(), Reward.id.asc()).limit(limit)
    return list(session.scalars(stmt).unique())


def list_merchant_rewards(session: Session, merchant_id: int, *, active_only: bool = False) -> list[Reward]:
    stmt = select(Reward).where(Reward.merchant_id == merchant_id)
    if active_only:
        stmt = stmt.where(Reward.is_active.is_(True))
    stmt = stmt.order_by(Reward.is_active.desc(), Reward.points_cost.asc())
    return list(session.scalars(stmt))


def create_reward(
    session: Session,
    *,
    merchant_id: int,
    actor_id: int,
    title: str,
    description: str,
    type: RewardType,
    points_cost: int,
    value: Decimal | str | float | None,
    icon: str,
    starts_at: datetime,
    expires_at: datetime,
    stock: int | None,
) -> Reward:
    _assert_owner(session, merchant_id, actor_id)
    clean_title = _clean_title(title)
    if points_cost <= 0:
        raise ValidationError("Le coût en points doit être positif.", code="invalid_points_cost")
    if stock is not None and stock < 0:
        raise ValidationError("Le stock ne peut pas être négatif.", code="invalid_stock")
    _validate_dates(starts_at, expires_at)
    reward = Reward(
        merchant_id=merchant_id,
        title=clean_title,
        description=(description or "").strip(),
        type=type,
        points_cost=int(points_cost),
        value=to_decimal(value) if value not in (None, "") else None,
        icon=(icon or "🎁")[:8],
        starts_at=starts_at,
        expires_at=expires_at,
        stock=stock,
        is_active=True,
    )
    session.add(reward)
    session.flush()
    audit.record(
        session,
        actor_id=actor_id,
        action="REWARD_CREATED",
        entity_type="Reward",
        entity_id=reward.id,
        metadata={"merchant_id": merchant_id, "points_cost": points_cost},
    )
    return reward


def update_reward(
    session: Session,
    *,
    reward_id: int,
    actor_id: int,
    title: str,
    description: str,
    type: RewardType,
    points_cost: int,
    value: Decimal | str | float | None,
    icon: str,
    starts_at: datetime,
    expires_at: datetime,
    stock: int | None,
    is_active: bool,
) -> Reward:
    reward = get_reward(session, reward_id)
    if not reward.merchant_id:
        raise ValidationError("Récompense réseau non modifiable depuis un commerce.", code="global_reward")
    _assert_owner(session, reward.merchant_id, actor_id)
    clean_title = _clean_title(title)
    if points_cost <= 0:
        raise ValidationError("Le coût en points doit être positif.", code="invalid_points_cost")
    if stock is not None and stock < 0:
        raise ValidationError("Le stock ne peut pas être négatif.", code="invalid_stock")
    _validate_dates(starts_at, expires_at)
    reward.title = clean_title
    reward.description = (description or "").strip()
    reward.type = type
    reward.points_cost = int(points_cost)
    reward.value = to_decimal(value) if value not in (None, "") else None
    reward.icon = (icon or "🎁")[:8]
    reward.starts_at = starts_at
    reward.expires_at = expires_at
    reward.stock = stock
    reward.is_active = is_active
    audit.record(
        session,
        actor_id=actor_id,
        action="REWARD_UPDATED",
        entity_type="Reward",
        entity_id=reward.id,
        metadata={"merchant_id": reward.merchant_id},
    )
    return reward


def set_reward_active(session: Session, *, reward_id: int, actor_id: int, active: bool) -> Reward:
    reward = get_reward(session, reward_id)
    if not reward.merchant_id:
        raise ValidationError("Récompense réseau non modifiable.", code="global_reward")
    _assert_owner(session, reward.merchant_id, actor_id)
    reward.is_active = active
    audit.record(
        session,
        actor_id=actor_id,
        action="REWARD_ACTIVATED" if active else "REWARD_DEACTIVATED",
        entity_type="Reward",
        entity_id=reward.id,
    )
    return reward


def _generate_redemption_code(session: Session) -> str:
    for _ in range(10):
        code = generate_code("RWD", groups=2)
        if not session.scalar(select(RewardRedemption.id).where(RewardRedemption.code == code)):
            return code
    raise ConflictError("Impossible de générer un code récompense.", code="code_generation_failed")


def redeem_reward(session: Session, *, user_id: int, reward_id: int) -> RewardRedemption:
    user = session.get(User, user_id)
    if not user or user.role != UserRole.CLIENT or not user.is_active:
        raise ValidationError("Compte client invalide.", code="client_inactive")
    reward = get_reward(session, reward_id)
    now = utcnow()
    if not reward.is_active or reward.starts_at > now or reward.expires_at < now:
        raise ValidationError("Cette récompense n'est pas disponible.", code="reward_unavailable")
    if reward.merchant and not reward.merchant.is_active:
        raise ValidationError("Le commerce de cette récompense est désactivé.", code="reward_unavailable")
    if reward.stock is not None and reward.stock <= 0:
        raise ValidationError("Cette récompense est épuisée.", code="reward_out_of_stock")

    account = session.scalar(select(LoyaltyAccount).where(LoyaltyAccount.user_id == user_id).with_for_update())
    if not account:
        raise NotFoundError("Carte de fidélité introuvable.", code="loyalty_account_not_found")
    if account.total_points < reward.points_cost:
        raise ValidationError(
            f"Solde insuffisant : il vous manque {reward.points_cost - account.total_points} points.",
            code="insufficient_points",
        )

    new_balance = account.total_points - reward.points_cost
    account.total_points = new_balance
    code = _generate_redemption_code(session)
    redemption = RewardRedemption(
        reward_id=reward.id,
        user_id=user_id,
        merchant_id=reward.merchant_id,
        code=code,
        status=RedemptionStatus.PENDING,
        expires_at=now + timedelta(days=REWARD_CODE_TTL_DAYS),
    )
    session.add(redemption)
    session.flush()
    session.add(
        PointTransaction(
            user_id=user_id,
            merchant_id=reward.merchant_id,
            type=TransactionType.REDEEMED,
            points=-reward.points_cost,
            purchase_amount=None,
            description=f"Récompense : {reward.title}",
            reference=f"RDM-{redemption.id}",
            balance_after=new_balance,
        )
    )
    if reward.stock is not None:
        reward.stock = max(0, reward.stock - 1)
    notifications.notify(
        session,
        user_id,
        type=NotificationType.REWARD_REDEEMED,
        title="Récompense obtenue",
        message=(
            f"Votre récompense « {reward.title} » est prête. Code : {code}. Présentez-le au commerce pour validation."
        ),
        link_page="client.my_rewards",
    )
    audit.record(
        session,
        actor_id=user_id,
        action="REWARD_REDEEMED",
        entity_type="RewardRedemption",
        entity_id=redemption.id,
        metadata={
            "reward_id": reward.id,
            "points": reward.points_cost,
            "balance_after": new_balance,
        },
    )
    session.flush()
    return redemption


def list_user_redemptions(session: Session, user_id: int, *, refresh_expired: bool = True) -> list[RewardRedemption]:
    if refresh_expired:
        expired = list(
            session.scalars(
                select(RewardRedemption).where(
                    RewardRedemption.user_id == user_id,
                    RewardRedemption.status == RedemptionStatus.PENDING,
                    RewardRedemption.expires_at < utcnow(),
                )
            )
        )
        for redemption in expired:
            redemption.status = RedemptionStatus.EXPIRED
        if expired:
            session.flush()
    stmt = (
        select(RewardRedemption)
        .options(joinedload(RewardRedemption.reward), joinedload(RewardRedemption.merchant))
        .where(RewardRedemption.user_id == user_id)
        .order_by(RewardRedemption.created_at.desc())
    )
    return list(session.scalars(stmt).unique())


def validate_redemption(session: Session, *, code: str, merchant_id: int, actor_id: int) -> RewardRedemption:
    clean_code = (code or "").strip().upper()
    if not clean_code:
        raise ValidationError("Saisissez le code de la récompense.", code="code_required")
    redemption = session.scalar(
        select(RewardRedemption)
        .options(joinedload(RewardRedemption.reward), joinedload(RewardRedemption.user))
        .where(RewardRedemption.code == clean_code)
        .with_for_update()
    )
    if not redemption:
        raise NotFoundError("Code récompense introuvable.", code="reward_code_not_found")
    if redemption.status == RedemptionStatus.USED:
        raise ConflictError("Cette récompense a déjà été utilisée.", code="reward_already_used")
    if redemption.status == RedemptionStatus.CANCELLED:
        raise ConflictError("Cette récompense a été annulée.", code="reward_cancelled")
    if redemption.status == RedemptionStatus.EXPIRED or redemption.expires_at < utcnow():
        if redemption.status != RedemptionStatus.EXPIRED:
            redemption.status = RedemptionStatus.EXPIRED
        raise ConflictError("Ce code de récompense a expiré.", code="reward_code_expired")
    if redemption.merchant_id and redemption.merchant_id != merchant_id:
        raise AccessDenied("Cette récompense appartient à un autre commerce.", code="reward_wrong_merchant")
    merchant = session.get(Merchant, merchant_id)
    if not merchant or not merchant.is_active:
        raise ValidationError("Commerce désactivé.", code="merchant_inactive")

    redemption.status = RedemptionStatus.USED
    redemption.redeemed_at = utcnow()
    redemption.validated_by_merchant_id = merchant_id
    notifications.notify(
        session,
        redemption.user_id,
        type=NotificationType.REWARD_VALIDATED,
        title="Récompense validée",
        message=f"Votre récompense « {redemption.reward.title} » a été validée chez {merchant.business_name}.",
        link_page="client.my_rewards",
    )
    audit.record(
        session,
        actor_id=actor_id,
        action="REWARD_VALIDATED",
        entity_type="RewardRedemption",
        entity_id=redemption.id,
        metadata={"merchant_id": merchant_id, "code": clean_code},
    )
    session.flush()
    return redemption


def redemption_points_reference(redemption_id: int) -> str:
    return generate_reference(f"RDM{redemption_id}")
