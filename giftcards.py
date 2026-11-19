"""Cartes cadeaux simulées (aucun paiement réel)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from ..config import GIFT_CARD_MAX_AMOUNT, GIFT_CARD_MIN_AMOUNT, GIFT_CARD_TTL_DAYS
from ..errors import ConflictError, NotFoundError, ValidationError
from ..models import (
    GiftCard,
    GiftCardStatus,
    Merchant,
    NotificationType,
    User,
    UserRole,
    utcnow,
)
from ..security import generate_code, normalize_moroccan_phone, to_decimal
from . import audit, notifications

SIMULATED_PAYMENT_STATUS = "PAID_SIMULATED"


def _generate_card_code(session: Session) -> str:
    for _ in range(12):
        code = generate_code("WFC", groups=3)
        if not session.scalar(select(GiftCard.id).where(GiftCard.code == code)):
            return code
    raise ConflictError("Impossible de générer un code carte cadeau.", code="code_generation_failed")


def create_gift_card(
    session: Session,
    *,
    sender_id: int,
    amount: Decimal | str | float,
    recipient_name: str,
    recipient_phone: str | None = None,
    merchant_id: int | None = None,
    message: str = "",
    recipient_is_self: bool = False,
) -> GiftCard:
    sender = session.get(User, sender_id)
    if not sender or sender.role != UserRole.CLIENT or not sender.is_active:
        raise ValidationError("Compte client invalide.", code="client_inactive")

    value = to_decimal(amount)
    if value < Decimal(str(GIFT_CARD_MIN_AMOUNT)):
        raise ValidationError(f"Le montant minimum est de {GIFT_CARD_MIN_AMOUNT} MAD.", code="giftcard_amount_too_low")
    if value > Decimal(str(GIFT_CARD_MAX_AMOUNT)):
        raise ValidationError(f"Le montant maximum est de {GIFT_CARD_MAX_AMOUNT} MAD.", code="giftcard_amount_too_high")

    merchant = None
    if merchant_id is not None:
        merchant = session.get(Merchant, merchant_id)
        if not merchant or not merchant.is_active:
            raise ValidationError("Commerce partenaire indisponible.", code="merchant_inactive")

    recipient_user_id: int | None = None
    clean_phone: str | None = None
    if recipient_is_self:
        recipient_user_id = sender.id
        clean_name = sender.full_name
        clean_phone = sender.phone
    else:
        clean_name = (recipient_name or "").strip()
        if len(clean_name) < 2:
            raise ValidationError("Le nom du destinataire est obligatoire.", code="recipient_required")
        if recipient_phone:
            clean_phone = normalize_moroccan_phone(recipient_phone)
            recipient = session.scalar(select(User).where(User.phone == clean_phone))
            if recipient and recipient.role == UserRole.CLIENT and recipient.is_active:
                recipient_user_id = recipient.id

    card = GiftCard(
        sender_id=sender.id,
        recipient_user_id=recipient_user_id,
        recipient_name=clean_name,
        recipient_phone=clean_phone,
        merchant_id=merchant.id if merchant else None,
        amount=value,
        code=_generate_card_code(session),
        status=GiftCardStatus.ACTIVE,
        message=(message or "").strip()[:255] or None,
        expires_at=utcnow() + timedelta(days=GIFT_CARD_TTL_DAYS),
        simulated_payment_status=SIMULATED_PAYMENT_STATUS,
    )
    session.add(card)
    session.flush()

    scope = merchant.business_name if merchant else "tous les commerces partenaires WafaClub"
    if recipient_user_id:
        notifications.notify(
            session,
            recipient_user_id,
            type=NotificationType.GIFT_CARD_RECEIVED,
            title="Une carte cadeau vous attend",
            message=(
                f"{sender.full_name} vous offre une carte cadeau de {value} MAD, "
                f"valable chez {scope}. Code : {card.code}."
            ),
            link_page="client.gift_cards",
        )
    else:
        notifications.notify(
            session,
            sender.id,
            type=NotificationType.GIFT_CARD_RECEIVED,
            title="Carte cadeau créée",
            message=(
                f"Votre carte cadeau de {value} MAD est active. Partagez le code {card.code} "
                f"avec {clean_name}. Valable chez {scope}."
            ),
            link_page="client.gift_cards",
        )
    audit.record(
        session,
        actor_id=sender.id,
        action="GIFT_CARD_CREATED",
        entity_type="GiftCard",
        entity_id=card.id,
        metadata={
            "amount": str(value),
            "merchant_id": card.merchant_id,
            "recipient_user_id": recipient_user_id,
            "simulated_payment": True,
        },
    )
    session.flush()
    return card


def get_gift_card(session: Session, card_id: int) -> GiftCard:
    stmt = (
        select(GiftCard)
        .options(
            joinedload(GiftCard.sender),
            joinedload(GiftCard.recipient_user),
            joinedload(GiftCard.merchant),
        )
        .where(GiftCard.id == card_id)
    )
    card = session.scalar(stmt)
    if not card:
        raise NotFoundError("Carte cadeau introuvable.", code="giftcard_not_found")
    return card


def refresh_expired_cards(session: Session) -> int:
    cards = list(
        session.scalars(
            select(GiftCard).where(
                GiftCard.status == GiftCardStatus.ACTIVE,
                GiftCard.expires_at < utcnow(),
            )
        )
    )
    for card in cards:
        card.status = GiftCardStatus.EXPIRED
    if cards:
        session.flush()
    return len(cards)


def list_user_gift_cards(session: Session, user_id: int, *, refresh_expired: bool = True) -> list[GiftCard]:
    if refresh_expired:
        refresh_expired_cards(session)
    stmt = (
        select(GiftCard)
        .options(
            joinedload(GiftCard.sender),
            joinedload(GiftCard.recipient_user),
            joinedload(GiftCard.merchant),
        )
        .where(or_(GiftCard.sender_id == user_id, GiftCard.recipient_user_id == user_id))
        .order_by(GiftCard.created_at.desc())
    )
    return list(session.scalars(stmt).unique())


def _check_card_usable(card: GiftCard, merchant_id: int) -> None:
    if card.status == GiftCardStatus.USED:
        raise ConflictError("Cette carte cadeau a déjà été utilisée.", code="giftcard_already_used")
    if card.status == GiftCardStatus.CANCELLED:
        raise ConflictError("Cette carte cadeau a été annulée.", code="giftcard_cancelled")
    if card.status == GiftCardStatus.EXPIRED or card.expires_at < utcnow():
        if card.status != GiftCardStatus.EXPIRED:
            card.status = GiftCardStatus.EXPIRED
        raise ConflictError("Cette carte cadeau a expiré.", code="giftcard_expired")
    if card.merchant_id is not None and card.merchant_id != merchant_id:
        raise ValidationError(
            "Cette carte cadeau est valable dans un autre commerce.",
            code="giftcard_wrong_merchant",
        )


def verify_gift_card(session: Session, *, code: str, merchant_id: int) -> GiftCard:
    clean_code = (code or "").strip().upper()
    if not clean_code:
        raise ValidationError("Saisissez le code de la carte cadeau.", code="code_required")
    card = session.scalar(
        select(GiftCard)
        .options(joinedload(GiftCard.merchant), joinedload(GiftCard.sender))
        .where(GiftCard.code == clean_code)
    )
    if not card:
        raise NotFoundError("Carte cadeau introuvable.", code="giftcard_not_found")
    merchant = session.get(Merchant, merchant_id)
    if not merchant or not merchant.is_active:
        raise ValidationError("Commerce désactivé.", code="merchant_inactive")
    _check_card_usable(card, merchant_id)
    return card


def validate_gift_card(session: Session, *, code: str, merchant_id: int, actor_id: int) -> GiftCard:
    clean_code = (code or "").strip().upper()
    if not clean_code:
        raise ValidationError("Saisissez le code de la carte cadeau.", code="code_required")
    card = session.scalar(
        select(GiftCard).options(joinedload(GiftCard.merchant)).where(GiftCard.code == clean_code).with_for_update()
    )
    if not card:
        raise NotFoundError("Carte cadeau introuvable.", code="giftcard_not_found")
    merchant = session.get(Merchant, merchant_id)
    if not merchant or not merchant.is_active:
        raise ValidationError("Commerce désactivé.", code="merchant_inactive")
    _check_card_usable(card, merchant_id)

    card.status = GiftCardStatus.USED
    card.redeemed_at = utcnow()
    card.redeemed_by_merchant_id = merchant_id
    notifications.notify(
        session,
        card.sender_id,
        type=NotificationType.GIFT_CARD_VALIDATED,
        title="Carte cadeau utilisée",
        message=(f"Votre carte cadeau de {card.amount} MAD a été utilisée chez {merchant.business_name}."),
        link_page="client.gift_cards",
    )
    if card.recipient_user_id and card.recipient_user_id != card.sender_id:
        notifications.notify(
            session,
            card.recipient_user_id,
            type=NotificationType.GIFT_CARD_VALIDATED,
            title="Carte cadeau utilisée",
            message=(f"La carte cadeau de {card.amount} MAD a été validée chez {merchant.business_name}."),
            link_page="client.gift_cards",
        )
    audit.record(
        session,
        actor_id=actor_id,
        action="GIFT_CARD_VALIDATED",
        entity_type="GiftCard",
        entity_id=card.id,
        metadata={"merchant_id": merchant_id, "amount": str(card.amount)},
    )
    session.flush()
    return card
