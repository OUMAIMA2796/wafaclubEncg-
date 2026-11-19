"""Test d'intégration UI : parcours critiques via Streamlit AppTest.

Ce test exécute l'application réelle sur une base SQLite temporaire et vérifie
les écritures métier principales : points, récompenses, promotions, cartes
cadeaux, validations commerçant et administration.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import streamlit as st
from sqlalchemy import select
from streamlit.testing.v1 import AppTest

import wafaclub.db as wafaclub_db
from wafaclub.db import Database
from wafaclub.models import (
    GiftCard,
    GiftCardStatus,
    Merchant,
    Promotion,
    RedemptionStatus,
    Reward,
    RewardRedemption,
)

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app.py"


def _check(at: AppTest, stage: str) -> None:
    assert not at.exception, f"{stage}: {[exc.value for exc in at.exception]}"


def _login_demo(at: AppTest, role: str) -> None:
    at.button(key="public_login").click().run()
    _check(at, "page de connexion")
    at.button(key=f"demo_{role}").click().run()
    _check(at, f"tableau de bord {role}")


def _nav(at: AppTest, page: str) -> None:
    at.button(key=page).click().run()
    _check(at, page)


def _submit(at: AppTest, form_key: str) -> None:
    prefix = f"FormSubmitter:{form_key}-"
    for button in at.button:
        if (button.key or "").startswith(prefix):
            button.click().run()
            _check(at, f"submit {form_key}")
            return
    raise AssertionError(f"Bouton de soumission introuvable pour {form_key}")


@pytest.fixture()
def app_test(tmp_path, monkeypatch):
    """Lance l'app sur une base isolée et partagée par tous les parcours."""
    database = Database(f"sqlite:///{(tmp_path / 'ui-smoke.db').as_posix()}")
    monkeypatch.setattr(wafaclub_db, "database", database)
    st.cache_resource.clear()
    try:
        at = AppTest.from_file(str(APP_PATH), default_timeout=120).run()
        _check(at, "démarrage")
        yield at, database
    finally:
        st.cache_resource.clear()
        database.dispose()


def test_ui_end_to_end_write_flows(app_test):
    at, database = app_test

    # --- Commerçant : points, récompense, promotion -----------------------
    _login_demo(at, "merchant")

    _nav(at, "nav_merchant.add_points")
    at.selectbox(key="demo_client").select_index(0).run()
    _check(at, "sélection client démo")
    for button in at.button:
        if button.label == "Client identifié":
            button.click().run()
            break
    else:
        raise AssertionError("Bouton « Client identifié » introuvable")
    _check(at, "formulaire d'achat")
    assert len(at.number_input) == 1
    at.number_input[0].set_value(250.0).run()
    _submit(at, "add_points_form")
    assert any("succès" in markdown.value.lower() for markdown in at.markdown)

    _nav(at, "nav_merchant.rewards")
    at.button(key="new_reward").click().run()
    _check(at, "formulaire récompense")
    at.text_input[0].set_value("Récompense test UI")
    at.text_area[0].set_value("Créée par le test d'intégration.")
    at.number_input[0].set_value(80)
    at.number_input[1].set_value(15.0)
    _submit(at, "reward_form")
    with database.session() as session:
        reward = session.scalar(select(Reward).where(Reward.title == "Récompense test UI"))
        assert reward is not None
        assert reward.points_cost == 80
        assert str(reward.value) == "15.00"

    _nav(at, "nav_merchant.promotions")
    at.button(key="new_promo").click().run()
    _check(at, "formulaire promotion")
    at.text_input[0].set_value("Promotion test UI")
    at.text_area[0].set_value("Créée par le test d'intégration.")
    _submit(at, "promotion_form")
    with database.session() as session:
        promotion = session.scalar(select(Promotion).where(Promotion.title == "Promotion test UI"))
        assert promotion is not None

    # --- Commerçant : validations ----------------------------------------
    _nav(at, "nav_merchant.validate_reward")
    at.text_input[0].set_value("RWD-DEMO-7K2M")
    _submit(at, "validate_reward_form")
    with database.session() as session:
        redemption = session.scalar(select(RewardRedemption).where(RewardRedemption.code == "RWD-DEMO-7K2M"))
        assert redemption.status == RedemptionStatus.USED
        assert redemption.redeemed_at is not None

    _nav(at, "nav_merchant.gift_cards")
    at.text_input[0].set_value("WFC-DEMO-4Q7N-9TX2")
    _submit(at, "verify_gift_form")
    at.button(key="confirm_gift_merchant").click().run()
    _check(at, "validation carte cadeau")
    with database.session() as session:
        card = session.scalar(select(GiftCard).where(GiftCard.code == "WFC-DEMO-4Q7N-9TX2"))
        assert card.status == GiftCardStatus.USED
        assert card.redeemed_at is not None

    at.button(key="logout").click().run()
    _check(at, "déconnexion commerçant")

    # --- Client : carte cadeau et rédemption ------------------------------
    _login_demo(at, "client")
    _nav(at, "nav_client.gift_cards")
    at.button(key="new_gift").click().run()
    _check(at, "formulaire carte cadeau")
    at.text_input[0].set_value("Nadia Test UI")
    at.checkbox[0].check()
    _submit(at, "gift_create_form")
    _check(at, "confirmation carte cadeau")
    at.button(key="confirm_gift").click().run()
    _check(at, "succès carte cadeau")
    with database.session() as session:
        created = session.scalar(select(GiftCard).where(GiftCard.recipient_name == "Nadia Test UI"))
        assert created is not None
        assert str(created.amount) == "50.00"
        assert created.status == GiftCardStatus.ACTIVE

    _nav(at, "nav_client.rewards")
    at.button(key="catalog_reward_1").click().run()
    _check(at, "détail récompense")
    at.button(key="reward_use").click().run()
    _check(at, "confirmation rédemption")
    at.button(key="confirm_redeem").click().run()
    _check(at, "succès rédemption")
    with database.session() as session:
        redeemed = session.scalar(
            select(RewardRedemption).where(
                RewardRedemption.user_id == 2,
                RewardRedemption.status == RedemptionStatus.PENDING,
            )
        )
        assert redeemed is not None

    # --- Bascule arabe / RTL ---------------------------------------------
    selector = next(s for s in at.selectbox if (s.key or "").startswith("lang_app"))
    selector.set_value("العربية").run()
    _check(at, "passage en arabe")
    assert any("direction: rtl" in markdown.value for markdown in at.markdown)

    for page in (
        "client.dashboard",
        "client.card",
        "client.points",
        "client.rewards",
        "client.gift_cards",
        "client.settings",
        "client.help",
    ):
        _nav(at, f"nav_{page}")

    at.button(key="logout").click().run()
    _check(at, "déconnexion cliente")

    # --- Administration ---------------------------------------------------
    _login_demo(at, "admin")
    _nav(at, "nav_admin.merchants")
    at.button(key="toggle_merchant_5").click().run()
    _check(at, "désactivation commerce")
    with database.session() as session:
        merchant = session.get(Merchant, 5)
        assert merchant.is_active is False
    at.button(key="toggle_merchant_5").click().run()
    _check(at, "réactivation commerce")
    with database.session() as session:
        merchant = session.get(Merchant, 5)
        assert merchant.is_active is True


def test_back_button_returns_through_page_history(app_test):
    at, _ = app_test
    _login_demo(at, "client")
    assert not at.button(key="page_back").disabled
    at.button(key="page_back").click().run()
    _check(at, "retour à la connexion")
    assert at.session_state["view"] == "auth"

    at.button(key="demo_client").click().run()
    _check(at, "retour au tableau de bord")
    at.session_state["page_history"] = None

    _nav(at, "nav_client.rewards")
    assert at.session_state["page"] == "client.rewards"
    at.button(key="catalog_reward_1").click().run()
    _check(at, "détail récompense")
    assert at.session_state["page"] == "client.reward_detail"

    at.button(key="page_back").click().run()
    _check(at, "retour au catalogue")
    assert at.session_state["page"] == "client.rewards"

    at.button(key="page_back").click().run()
    _check(at, "retour au tableau de bord")
    assert at.session_state["page"] == "client.dashboard"
