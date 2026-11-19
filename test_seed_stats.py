from __future__ import annotations

from sqlalchemy import func, select

from wafaclub.db import Database
from wafaclub.models import (
    GiftCard,
    Language,
    LoyaltyAccount,
    Merchant,
    PointTransaction,
    Promotion,
    RedemptionStatus,
    RewardRedemption,
    User,
    UserRole,
)
from wafaclub.seed import seed_demo_data
from wafaclub.services import loyalty, merchants, stats


def test_seed_dataset_is_realistic_and_consistent(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'seed.db'}")
    db.create_all()
    with db.session() as session:
        summary = seed_demo_data(session)

    with db.session() as session:
        assert summary["clients"] == 3
        assert summary["merchants"] == 5
        assert summary["rewards"] >= 10
        assert session.scalar(select(func.count(User.id))) == 7
        assert session.scalar(select(func.count(User.id)).where(User.role == UserRole.CLIENT)) == 3
        assert session.scalar(select(func.count(Merchant.id))) == 5
        assert session.scalar(select(func.count(PointTransaction.id))) == 29
        assert session.scalar(select(func.count(GiftCard.id))) == 4
        assert (
            session.scalar(
                select(func.count(RewardRedemption.id)).where(RewardRedemption.status == RedemptionStatus.USED)
            )
            == 2
        )

        clients = list(session.scalars(select(User).where(User.role == UserRole.CLIENT)))
        for client in clients:
            assert client.city == "Agadir"
            assert client.neighborhood in merchants.AGADIR_NEIGHBORHOODS
            assert loyalty.ledger_is_consistent(session, client.id)
            account = session.scalar(select(LoyaltyAccount).where(LoyaltyAccount.user_id == client.id))
            assert account.total_points > 100

        users = list(session.scalars(select(User)))
        assert all(user.city == "Agadir" for user in users)
        assert all(user.preferred_language in {Language.FR, Language.AR} for user in users)
        seeded_merchants = list(session.scalars(select(Merchant)))
        assert all(merchant.city == "Agadir" for merchant in seeded_merchants)
        assert all(merchant.neighborhood in merchants.AGADIR_NEIGHBORHOODS for merchant in seeded_merchants)
        seeded_promotions = list(session.scalars(select(Promotion)))
        assert all(promotion.city == "Agadir" for promotion in seeded_promotions)
        assert all(promotion.neighborhood in merchants.AGADIR_NEIGHBORHOODS for promotion in seeded_promotions)
        cafe = session.scalar(select(Merchant).where(Merchant.business_name == "Café Argana"))
        dashboard = stats.merchant_dashboard(session, cafe.id)
        assert dashboard["clients"] == 3
        assert dashboard["purchases"] == 6
        assert dashboard["points_distributed"] == 107
        assert len(dashboard["series"]) == 14
        assert dashboard["recent"]
        assert dashboard["top_clients"]

        overview = stats.admin_overview(session)
        assert overview["clients"] == 3
        assert overview["merchant_owners"] == 3
        assert overview["merchants"] == 5
        assert overview["active_merchants"] == 5
        assert overview["transactions"] == 29
        assert overview["points_distributed"] == 1067
        assert overview["redemptions_used"] == 2
        assert overview["gift_cards"] == 4
        assert len(overview["series"]) == 30

        # Le code de démonstration peut être validé par le commerce concerné.
        pending = session.scalar(select(RewardRedemption).where(RewardRedemption.code == "RWD-DEMO-7K2M"))
        assert pending is not None
        assert pending.status == RedemptionStatus.PENDING

    db.dispose()


def test_seed_is_idempotent_when_users_exist(session):
    from .conftest import make_client

    make_client(session)
    result = seed_demo_data(session)
    assert result.get("skipped") == 1


def test_merchant_dashboard_handles_unknown_merchant(session):
    assert stats.merchant_dashboard(session, 9999) == {}
