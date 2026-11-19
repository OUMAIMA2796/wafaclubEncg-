"""Fixtures et fabriques de données pour les tests WafaClub."""

from __future__ import annotations

from datetime import timedelta

import pytest

from wafaclub.db import Database
from wafaclub.models import Language, Reward, RewardType, utcnow
from wafaclub.services import auth, loyalty, rewards


@pytest.fixture()
def session(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'wafaclub-test.db'}")
    db.create_all()
    database_session = db.session_factory()
    try:
        yield database_session
    finally:
        database_session.rollback()
        database_session.close()
        db.dispose()


def make_client(session, *, phone="+212661000001", first="Yasmine", last="Test", language=Language.FR):
    user = auth.register_client(
        session,
        first_name=first,
        last_name=last,
        phone=phone,
        password="Test2026!",
        city="Casablanca",
        neighborhood="Maârif",
        preferred_language=language,
    )
    session.commit()
    return user


def make_merchant(
    session,
    *,
    owner_phone="+212661000099",
    business_name="Café Test",
    points_per_amount=10,
    city="Casablanca",
):
    owner, merchant = auth.register_merchant_owner(
        session,
        first_name="Hamza",
        last_name="Test",
        phone=owner_phone,
        password="Test2026!",
        city=city,
        neighborhood="Maârif",
        business_name=business_name,
        business_phone="+212522000000",
        address="1 rue de Test",
        category="Café",
        points_per_amount=points_per_amount,
    )
    session.commit()
    return owner, merchant


def give_points(session, user, points: int):
    loyalty.adjust_points(
        session,
        user_id=user.id,
        points_delta=points,
        actor_id=user.id,
        description="Points de test",
    )
    session.commit()


def make_reward(
    session,
    merchant,
    owner,
    *,
    title="10 MAD de réduction",
    points_cost=100,
    stock=10,
    active=True,
    starts_at=None,
    expires_at=None,
    reward_type=RewardType.DISCOUNT,
) -> Reward:
    reward = rewards.create_reward(
        session,
        merchant_id=merchant.id,
        actor_id=owner.id,
        title=title,
        description="Récompense de test",
        type=reward_type,
        points_cost=points_cost,
        value=10,
        icon="🎁",
        starts_at=starts_at or (utcnow() - timedelta(days=1)),
        expires_at=expires_at or (utcnow() + timedelta(days=30)),
        stock=stock,
    )
    if not active:
        reward.is_active = False
    session.commit()
    return reward
