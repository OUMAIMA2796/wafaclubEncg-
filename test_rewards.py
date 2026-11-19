from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from wafaclub.errors import AccessDenied, ConflictError, ValidationError
from wafaclub.models import (
    LoyaltyAccount,
    RedemptionStatus,
    RewardRedemption,
    TransactionType,
    utcnow,
)
from wafaclub.services import loyalty, rewards

from .conftest import give_points, make_client, make_merchant, make_reward


def test_reward_redemption_with_enough_points(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    reward = make_reward(session, merchant, owner, points_cost=100)
    give_points(session, client, 150)

    redemption = rewards.redeem_reward(session, user_id=client.id, reward_id=reward.id)
    session.commit()

    assert redemption.code.startswith("RWD-")
    assert redemption.status == RedemptionStatus.PENDING
    account = session.query(LoyaltyAccount).filter_by(user_id=client.id).one()
    assert account.total_points == 50
    assert loyalty.ledger_is_consistent(session, client.id)
    redeemed_tx = (
        session.query(loyalty.PointTransaction).filter_by(user_id=client.id, type=TransactionType.REDEEMED).one()
    )
    assert redeemed_tx.points == -100
    assert reward.stock == 9


def test_reward_redemption_with_insufficient_points(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    reward = make_reward(session, merchant, owner, points_cost=500)
    give_points(session, client, 100)
    with pytest.raises(ValidationError) as error:
        rewards.redeem_reward(session, user_id=client.id, reward_id=reward.id)
    assert error.value.code == "insufficient_points"


def test_reward_cannot_be_used_twice(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    reward = make_reward(session, merchant, owner, points_cost=100)
    give_points(session, client, 200)
    redemption = rewards.redeem_reward(session, user_id=client.id, reward_id=reward.id)
    session.commit()

    used = rewards.validate_redemption(session, code=redemption.code, merchant_id=merchant.id, actor_id=owner.id)
    session.commit()
    assert used.status == RedemptionStatus.USED
    assert used.validated_by_merchant_id == merchant.id

    with pytest.raises(ConflictError) as error:
        rewards.validate_redemption(session, code=redemption.code, merchant_id=merchant.id, actor_id=owner.id)
    assert error.value.code == "reward_already_used"


def test_reward_wrong_merchant_is_rejected(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    other_owner, other_merchant = make_merchant(session, owner_phone="+212661000098", business_name="Autre commerce")
    reward = make_reward(session, merchant, owner, points_cost=50)
    give_points(session, client, 100)
    redemption = rewards.redeem_reward(session, user_id=client.id, reward_id=reward.id)
    session.commit()

    with pytest.raises(AccessDenied) as error:
        rewards.validate_redemption(
            session,
            code=redemption.code,
            merchant_id=other_merchant.id,
            actor_id=other_owner.id,
        )
    assert error.value.code == "reward_wrong_merchant"


def test_expired_reward_cannot_be_redeemed(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    reward = make_reward(
        session,
        merchant,
        owner,
        points_cost=50,
        starts_at=utcnow() - timedelta(days=10),
        expires_at=utcnow() - timedelta(days=1),
    )
    give_points(session, client, 100)
    with pytest.raises(ValidationError) as error:
        rewards.redeem_reward(session, user_id=client.id, reward_id=reward.id)
    assert error.value.code == "reward_unavailable"


def test_expired_redemption_code_is_rejected(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    reward = make_reward(session, merchant, owner, points_cost=20)
    give_points(session, client, 100)
    redemption = rewards.redeem_reward(session, user_id=client.id, reward_id=reward.id)
    redemption.expires_at = utcnow() - timedelta(days=1)
    session.commit()

    with pytest.raises(ConflictError) as error:
        rewards.validate_redemption(session, code=redemption.code, merchant_id=merchant.id, actor_id=owner.id)
    assert error.value.code == "reward_code_expired"


def test_redemption_list_marks_pending_code_expired(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    reward = make_reward(session, merchant, owner, points_cost=20)
    give_points(session, client, 100)
    redemption = rewards.redeem_reward(session, user_id=client.id, reward_id=reward.id)
    redemption.expires_at = utcnow() - timedelta(days=1)
    session.commit()

    listed = rewards.list_user_redemptions(session, client.id)
    session.commit()
    assert listed[0].status == RedemptionStatus.EXPIRED
    assert session.query(RewardRedemption).one().status == RedemptionStatus.EXPIRED


def test_reward_without_stock_is_unavailable(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    reward = make_reward(session, merchant, owner, points_cost=20, stock=0)
    give_points(session, client, 100)
    with pytest.raises(ValidationError) as error:
        rewards.redeem_reward(session, user_id=client.id, reward_id=reward.id)
    assert error.value.code == "reward_out_of_stock"


def test_value_is_stored_as_decimal(session):
    owner, merchant = make_merchant(session)
    reward = make_reward(session, merchant, owner, points_cost=100)
    assert reward.value == Decimal("10.00")
