"""Modèle de données WafaClub (SQLAlchemy 2.0).

Le journal `PointTransaction` est append-only : aucun service ne le modifie et des
écouteurs ORM bloquent toute mise à jour/suppression accidentelle.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    event,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .errors import ImmutableLedgerError


def utcnow() -> datetime:
    """Horodatage UTC naïf, portable SQLite/PostgreSQL."""
    return datetime.utcnow()


def _enum(enum_cls: type[StrEnum]) -> SAEnum:
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


class UserRole(StrEnum):
    CLIENT = "CLIENT"
    MERCHANT = "MERCHANT"
    ADMIN = "ADMIN"


class Language(StrEnum):
    FR = "fr"
    AR = "ar"
    DARIJA = "darija"  # Legacy database value; the UI falls back to French.


class TransactionType(StrEnum):
    EARNED = "EARNED"
    REDEEMED = "REDEEMED"
    ADJUSTMENT = "ADJUSTMENT"
    EXPIRED = "EXPIRED"
    REFUND = "REFUND"


class RewardType(StrEnum):
    DISCOUNT = "DISCOUNT"
    PRODUCT = "PRODUCT"
    VOUCHER = "VOUCHER"


class RedemptionStatus(StrEnum):
    PENDING = "PENDING"
    USED = "USED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class GiftCardStatus(StrEnum):
    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class NotificationType(StrEnum):
    WELCOME = "WELCOME"
    POINTS_EARNED = "POINTS_EARNED"
    REWARD_REDEEMED = "REWARD_REDEEMED"
    REWARD_VALIDATED = "REWARD_VALIDATED"
    NEARBY_PROMOTION = "NEARBY_PROMOTION"
    GIFT_CARD_RECEIVED = "GIFT_CARD_RECEIVED"
    GIFT_CARD_VALIDATED = "GIFT_CARD_VALIDATED"
    GIFT_CARD_EXPIRING = "GIFT_CARD_EXPIRING"
    POINTS_EXPIRING = "POINTS_EXPIRING"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(first_name)) > 0", name="ck_users_first_name"),
        CheckConstraint("length(trim(last_name)) > 0", name="ck_users_last_name"),
        Index("ix_users_role_city", "role", "city"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(191), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole), default=UserRole.CLIENT, index=True)
    preferred_language: Mapped[Language] = mapped_column(_enum(Language), default=Language.FR)
    city: Mapped[str] = mapped_column(String(80), default="Agadir")
    neighborhood: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    loyalty_account: Mapped[LoyaltyAccount | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    merchants: Mapped[list[Merchant]] = relationship(back_populates="owner", foreign_keys="Merchant.owner_id")
    notifications: Mapped[list[Notification]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Merchant(Base):
    __tablename__ = "merchants"
    __table_args__ = (
        CheckConstraint("points_per_amount > 0", name="ck_merchants_points_rule"),
        CheckConstraint("latitude IS NULL OR (latitude >= -90 AND latitude <= 90)", name="ck_merchants_latitude"),
        CheckConstraint("longitude IS NULL OR (longitude >= -180 AND longitude <= 180)", name="ck_merchants_longitude"),
        Index("ix_merchants_city_category", "city", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    business_name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(255), default="")
    city: Mapped[str] = mapped_column(String(80), index=True)
    neighborhood: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[str] = mapped_column(String(80), index=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    points_per_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("10.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(back_populates="merchants", foreign_keys=[owner_id])
    rewards: Mapped[list[Reward]] = relationship(back_populates="merchant", cascade="all, delete-orphan")
    promotions: Mapped[list[Promotion]] = relationship(back_populates="merchant", cascade="all, delete-orphan")


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"
    __table_args__ = (CheckConstraint("total_points >= 0", name="ck_loyalty_total_nonnegative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    qr_code_token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="loyalty_account")


class PointTransaction(Base):
    __tablename__ = "point_transactions"
    __table_args__ = (
        CheckConstraint("purchase_amount IS NULL OR purchase_amount >= 0", name="ck_points_amount_nonnegative"),
        CheckConstraint("points <> 0", name="ck_points_nonzero"),
        CheckConstraint("balance_after >= 0", name="ck_points_balance_nonnegative"),
        Index("ix_points_user_created", "user_id", "created_at"),
        Index("ix_points_merchant_created", "merchant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    type: Mapped[TransactionType] = mapped_column(_enum(TransactionType), index=True)
    points: Mapped[int] = mapped_column(Integer)
    purchase_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    reference: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    user: Mapped[User] = relationship()
    merchant: Mapped[Merchant | None] = relationship()


@event.listens_for(PointTransaction, "before_update")
def _block_point_transaction_update(mapper, connection, target) -> None:  # noqa: ARG001
    raise ImmutableLedgerError("Une transaction du journal ne peut pas être modifiée.")


@event.listens_for(PointTransaction, "before_delete")
def _block_point_transaction_delete(mapper, connection, target) -> None:  # noqa: ARG001
    raise ImmutableLedgerError("Une transaction du journal ne peut pas être supprimée.")


class Reward(Base):
    __tablename__ = "rewards"
    __table_args__ = (
        CheckConstraint("points_cost > 0", name="ck_rewards_points_cost"),
        CheckConstraint("stock IS NULL OR stock >= 0", name="ck_rewards_stock"),
        CheckConstraint("expires_at > starts_at", name="ck_rewards_dates"),
        Index("ix_rewards_merchant_active", "merchant_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[RewardType] = mapped_column(_enum(RewardType), default=RewardType.DISCOUNT)
    points_cost: Mapped[int] = mapped_column(Integer)
    value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icon: Mapped[str] = mapped_column(String(16), default="🎁")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    merchant: Mapped[Merchant | None] = relationship(back_populates="rewards")


class RewardRedemption(Base):
    __tablename__ = "reward_redemptions"
    __table_args__ = (Index("ix_redemptions_user_status", "user_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reward_id: Mapped[int] = mapped_column(ForeignKey("rewards.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    validated_by_merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    status: Mapped[RedemptionStatus] = mapped_column(
        _enum(RedemptionStatus), default=RedemptionStatus.PENDING, index=True
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    reward: Mapped[Reward] = relationship(foreign_keys=[reward_id])
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    merchant: Mapped[Merchant | None] = relationship(foreign_keys=[merchant_id])
    validated_by_merchant: Mapped[Merchant | None] = relationship(foreign_keys=[validated_by_merchant_id])


class GiftCard(Base):
    __tablename__ = "gift_cards"
    __table_args__ = (
        CheckConstraint("amount >= 20 AND amount <= 2000", name="ck_gift_cards_amount"),
        Index("ix_gift_cards_recipient", "recipient_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    recipient_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recipient_name: Mapped[str] = mapped_column(String(120))
    recipient_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    status: Mapped[GiftCardStatus] = mapped_column(_enum(GiftCardStatus), default=GiftCardStatus.ACTIVE, index=True)
    message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    simulated_payment_status: Mapped[str] = mapped_column(String(40), default="PAID_SIMULATED")
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    redeemed_by_merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    sender: Mapped[User] = relationship(foreign_keys=[sender_id])
    recipient_user: Mapped[User | None] = relationship(foreign_keys=[recipient_user_id])
    merchant: Mapped[Merchant | None] = relationship(foreign_keys=[merchant_id])
    redeemed_by_merchant: Mapped[Merchant | None] = relationship(foreign_keys=[redeemed_by_merchant_id])


class Promotion(Base):
    __tablename__ = "promotions"
    __table_args__ = (
        CheckConstraint("expires_at > starts_at", name="ck_promotions_dates"),
        Index("ix_promotions_city_dates", "city", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icon: Mapped[str] = mapped_column(String(16), default="🏷️")
    city: Mapped[str] = mapped_column(String(80), index=True)
    neighborhood: Mapped[str] = mapped_column(String(120), default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    merchant: Mapped[Merchant] = relationship(back_populates="promotions")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[NotificationType] = mapped_column(_enum(NotificationType), default=NotificationType.WELCOME)
    title: Mapped[str] = mapped_column(String(140))
    message: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    link_page: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    user: Mapped[User] = relationship(back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_phone_created", "phone", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20))
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


__all__ = [
    "AuditLog",
    "GiftCard",
    "GiftCardStatus",
    "Language",
    "LoginAttempt",
    "LoyaltyAccount",
    "Merchant",
    "Notification",
    "NotificationType",
    "PointTransaction",
    "Promotion",
    "RedemptionStatus",
    "Reward",
    "RewardRedemption",
    "RewardType",
    "TransactionType",
    "User",
    "UserRole",
    "utcnow",
]
