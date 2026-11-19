from __future__ import annotations

from decimal import Decimal

import pytest

from wafaclub.errors import ImmutableLedgerError, ValidationError
from wafaclub.models import LoyaltyAccount, PointTransaction, TransactionType
from wafaclub.services import loyalty

from .conftest import give_points, make_client, make_merchant


def test_points_are_floored_per_complete_slice():
    assert loyalty.calculate_points(95, 10) == 9
    assert loyalty.calculate_points(100, 10) == 10
    assert loyalty.calculate_points(9.99, 10) == 0
    assert loyalty.calculate_points(10, 10) == 1
    assert loyalty.calculate_points(620, 12) == 51


def test_negative_purchase_is_rejected(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    with pytest.raises(ValidationError) as error:
        loyalty.add_purchase(
            session,
            client_id=client.id,
            merchant_id=merchant.id,
            amount=Decimal("-10.00"),
            actor_id=owner.id,
        )
    assert error.value.code == "invalid_amount"


def test_purchase_updates_balance_and_creates_ledger_entry(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    transaction = loyalty.add_purchase(
        session,
        client_id=client.id,
        merchant_id=merchant.id,
        amount=Decimal("95.00"),
        actor_id=owner.id,
    )
    session.commit()

    assert transaction.type == TransactionType.EARNED
    assert transaction.points == 9
    assert transaction.purchase_amount == Decimal("95.00")
    assert transaction.balance_after == 9
    account = session.query(LoyaltyAccount).filter_by(user_id=client.id).one()
    assert account.total_points == 9
    assert loyalty.ledger_is_consistent(session, client.id)

    second = loyalty.add_purchase(
        session,
        client_id=client.id,
        merchant_id=merchant.id,
        amount=Decimal("100.00"),
        actor_id=owner.id,
    )
    session.commit()
    assert second.points == 10
    assert second.balance_after == 19
    assert loyalty.summary(session, client.id)["balance"] == 19


def test_ledger_is_immutable(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    transaction = loyalty.add_purchase(
        session,
        client_id=client.id,
        merchant_id=merchant.id,
        amount=Decimal("50.00"),
        actor_id=owner.id,
    )
    session.commit()
    transaction.points = 999
    with pytest.raises(ImmutableLedgerError):
        session.flush()
    session.rollback()
    reloaded = session.get(PointTransaction, transaction.id)
    assert reloaded.points == 5


def test_refund_creates_opposite_entry_once(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    original = loyalty.add_purchase(
        session,
        client_id=client.id,
        merchant_id=merchant.id,
        amount=Decimal("100.00"),
        actor_id=owner.id,
    )
    session.commit()
    refund = loyalty.refund_purchase(session, original_transaction_id=original.id, actor_id=owner.id)
    session.commit()
    assert refund.type == TransactionType.REFUND
    assert refund.points == -10
    assert loyalty.summary(session, client.id)["balance"] == 0
    assert loyalty.ledger_is_consistent(session, client.id)

    with pytest.raises(Exception) as error:
        loyalty.refund_purchase(session, original_transaction_id=original.id, actor_id=owner.id)
    assert getattr(error.value, "code", "") == "already_refunded"


def test_inactive_merchant_cannot_award_points(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    merchant.is_active = False
    session.commit()
    with pytest.raises(ValidationError) as error:
        loyalty.add_purchase(
            session,
            client_id=client.id,
            merchant_id=merchant.id,
            amount=Decimal("100.00"),
            actor_id=owner.id,
        )
    assert error.value.code == "merchant_inactive"


def test_adjustment_is_journaled(session):
    client = make_client(session)
    give_points(session, client, 40)
    assert loyalty.summary(session, client.id)["balance"] == 40
    assert loyalty.ledger_is_consistent(session, client.id)
