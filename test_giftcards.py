from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from wafaclub.errors import ConflictError, ValidationError
from wafaclub.models import GiftCard, GiftCardStatus, Notification, NotificationType, utcnow
from wafaclub.services import giftcards

from .conftest import make_client, make_merchant


def _create_card(session, sender, **overrides):
    defaults = {
        "sender_id": sender.id,
        "amount": Decimal("100.00"),
        "recipient_name": "Nadia Amrani",
        "recipient_phone": "+212677889900",
        "merchant_id": None,
        "message": "Pour toi",
    }
    defaults.update(overrides)
    card = giftcards.create_gift_card(session, **defaults)
    session.commit()
    return card


def test_gift_card_creation_is_simulated_and_generates_code(session):
    client = make_client(session)
    card = _create_card(session, client)
    assert card.status == GiftCardStatus.ACTIVE
    assert card.code.startswith("WFC-")
    assert len(card.code.split("-")) == 4
    assert card.simulated_payment_status == "PAID_SIMULATED"
    assert Decimal(card.amount) == Decimal("100.00")
    assert card.expires_at > utcnow()


def test_gift_card_amount_bounds(session):
    client = make_client(session)
    with pytest.raises(ValidationError) as low:
        giftcards.create_gift_card(
            session,
            sender_id=client.id,
            amount=Decimal("19.99"),
            recipient_name="Test",
        )
    assert low.value.code == "giftcard_amount_too_low"
    with pytest.raises(ValidationError) as high:
        giftcards.create_gift_card(
            session,
            sender_id=client.id,
            amount=Decimal("2000.01"),
            recipient_name="Test",
        )
    assert high.value.code == "giftcard_amount_too_high"


def test_gift_cards_codes_are_unique(session):
    client = make_client(session)
    codes = {_create_card(session, client, recipient_name=f"Destinataire {index}").code for index in range(5)}
    assert len(codes) == 5


def test_gift_card_validation_and_double_use(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    card = _create_card(session, client, merchant_id=merchant.id)
    verified = giftcards.verify_gift_card(session, code=card.code, merchant_id=merchant.id)
    assert verified.id == card.id
    giftcards.validate_gift_card(session, code=card.code, merchant_id=merchant.id, actor_id=owner.id)
    session.commit()

    reloaded = session.get(GiftCard, card.id)
    assert reloaded.status == GiftCardStatus.USED
    assert reloaded.redeemed_at is not None
    assert reloaded.redeemed_by_merchant_id == merchant.id

    with pytest.raises(ConflictError) as error:
        giftcards.validate_gift_card(session, code=card.code, merchant_id=merchant.id, actor_id=owner.id)
    assert error.value.code == "giftcard_already_used"


def test_expired_gift_card_is_rejected(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    card = _create_card(session, client, merchant_id=merchant.id)
    card.expires_at = utcnow() - timedelta(days=1)
    session.commit()
    with pytest.raises(ConflictError) as error:
        giftcards.validate_gift_card(session, code=card.code, merchant_id=merchant.id, actor_id=owner.id)
    assert error.value.code == "giftcard_expired"
    session.rollback()


def test_gift_card_wrong_merchant_is_rejected(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    _, other_merchant = make_merchant(session, owner_phone="+212661000097", business_name="Autre épicerie")
    card = _create_card(session, client, merchant_id=merchant.id)
    with pytest.raises(ValidationError) as error:
        giftcards.verify_gift_card(session, code=card.code, merchant_id=other_merchant.id)
    assert error.value.code == "giftcard_wrong_merchant"


def test_gift_card_to_registered_recipient_creates_notification(session):
    sender = make_client(session)
    recipient = make_client(session, phone="+212662000002", first="Salma", last="Test")
    card = _create_card(
        session,
        sender,
        recipient_name="Salma Test",
        recipient_phone=recipient.phone,
        amount=Decimal("200"),
    )
    assert card.recipient_user_id == recipient.id
    notification = (
        session.query(Notification).filter_by(user_id=recipient.id, type=NotificationType.GIFT_CARD_RECEIVED).one()
    )
    assert "200" in notification.message


def test_self_gift_card_belongs_to_sender(session):
    client = make_client(session)
    card = _create_card(
        session,
        client,
        recipient_name=client.full_name,
        recipient_phone=client.phone,
        recipient_is_self=True,
    )
    assert card.recipient_user_id == client.id
    listed = giftcards.list_user_gift_cards(session, client.id)
    assert len(listed) == 1
