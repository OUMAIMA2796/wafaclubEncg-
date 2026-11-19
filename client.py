"""Pages de l'espace client WafaClub."""

from __future__ import annotations

import base64
from collections.abc import Callable
from decimal import Decimal

import streamlit as st

from ..config import GIFT_CARD_MAX_AMOUNT, GIFT_CARD_MIN_AMOUNT, GIFT_CARD_PRESETS
from ..db import database
from ..i18n import format_date, format_datetime, format_mad, format_points, reward_type_key, t
from ..models import GiftCardStatus, RedemptionStatus
from ..qrcodes import qr_payload, qr_png_bytes
from ..services import giftcards, loyalty, merchants, notifications, promotions, rewards
from . import components as ui
from .icons import esc, icon_svg
from .state import SS, SessionUser, context, current_lang, flash, goto

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _points(value: int) -> str:
    return ui.points(int(value), current_lang())


def _tx_snapshot(transaction) -> dict:
    return {
        "created_at": transaction.created_at,
        "type": transaction.type,
        "points": transaction.points,
        "amount": transaction.purchase_amount,
        "description": transaction.description,
        "balance_after": transaction.balance_after,
        "merchant": transaction.merchant.business_name if transaction.merchant else None,
    }


def _reward_snapshot(reward) -> dict:
    merchant = reward.merchant
    return {
        "id": reward.id,
        "title": reward.title,
        "description": reward.description,
        "type": reward.type,
        "points_cost": reward.points_cost,
        "value": reward.value,
        "icon": reward.icon,
        "stock": reward.stock,
        "starts_at": reward.starts_at,
        "expires_at": reward.expires_at,
        "merchant_id": reward.merchant_id,
        "merchant_name": merchant.business_name if merchant else None,
        "merchant_city": merchant.city if merchant else None,
        "merchant_neighborhood": merchant.neighborhood if merchant else None,
        "merchant_category": merchant.category if merchant else None,
    }


def _gift_snapshot(card) -> dict:
    return {
        "id": card.id,
        "code": card.code,
        "amount": card.amount,
        "status": card.status,
        "recipient_name": card.recipient_name,
        "recipient_phone": card.recipient_phone,
        "sender_name": card.sender.full_name if card.sender else "—",
        "merchant_name": card.merchant.business_name if card.merchant else None,
        "message": card.message,
        "expires_at": card.expires_at,
        "redeemed_at": card.redeemed_at,
        "created_at": card.created_at,
    }


def _reward_card_html(reward: dict, lang: str) -> str:
    scope = reward["merchant_name"] or t("client.rewards.network_scope", lang)
    stock = ""
    if reward["stock"] is not None:
        stock = ui.badge(t("client.rewards.stock", lang, stock=reward["stock"]), "gray")
    return f"""
<div class="wafa-card" style="height:100%;display:flex;flex-direction:column;gap:.45rem">
  <div class="wafa-row">
    <div class="wafa-reward-icon">{esc(reward["icon"])}</div>
    {ui.badge(t(reward_type_key(reward["type"]), lang), "gold")}
  </div>
  <div style="font-weight:800;font-size:.98rem;line-height:1.3">{esc(reward["title"])}</div>
  <div class="wafa-muted">{esc(scope)}</div>
  <div class="wafa-row" style="margin-top:auto;padding-top:.55rem">
    <strong style="color:#0B3C6E">{esc(t("client.rewards.points_required", lang, points=format_points(reward["points_cost"], lang)))}</strong>
    <span class="wafa-small">{esc(format_date(reward["expires_at"], lang))}</span>
  </div>
  <div>{stock}</div>
</div>
"""


def _promotion_card_html_for_dict(promotion: dict, lang: str) -> str:
    return f"""
<div class="wafa-card gold" style="height:100%">
  <div class="wafa-row"><div class="wafa-reward-icon">{esc(promotion["icon"])}</div>{ui.badge(promotion["city"], "gold")}</div>
  <div style="font-weight:800;font-size:1rem;margin:.55rem 0 .2rem">{esc(promotion["title"])}</div>
  <div class="wafa-muted" style="line-height:1.5">{esc(promotion["description"])}</div>
  <div class="wafa-row" style="margin-top:.8rem">
    <span class="wafa-small">{esc(promotion["merchant_name"])}</span>
    <span class="wafa-small">{esc(format_date(promotion["expires_at"], lang))}</span>
  </div>
</div>
"""


def _merchant_card_html(merchant: dict, lang: str) -> str:
    return f"""
<div class="wafa-card" style="height:100%">
  <div class="wafa-row">
    <div class="wafa-icon blue">{icon_svg("store", 20)}</div>
    {ui.badge(merchant["category"], "blue")}
  </div>
  <div style="font-weight:800;font-size:1rem;margin:.6rem 0 .2rem">{esc(merchant["name"])}</div>
  <div class="wafa-muted">{esc(merchant["neighborhood"])} · {esc(merchant["city"])}</div>
  <div class="wafa-small" style="margin-top:.6rem">
    {esc(t("client.merchants.rule", lang, points=format_mad(merchant["rule"], lang)))}
  </div>
</div>
"""


def _render_transactions(rows: list[dict], lang: str, *, limit: int = 8) -> None:
    if not rows:
        ui.empty_state(
            t("client.points.empty", lang),
            t("common.no_data", lang),
            icon="receipt",
        )
        return
    for row in rows[:limit]:
        positive = row["points"] > 0
        amount = f"+{row['points']}" if positive else str(row["points"])
        color = "#12805C" if positive else "#B5413A"
        merchant = f" · {esc(row['merchant'])}" if row["merchant"] else ""
        st.markdown(
            f"""
<div class="wafa-line">
  <div style="flex:1">
    <div><strong style="font-size:.84rem">{esc(row["description"])}</strong></div>
    <div class="wafa-small">{esc(format_datetime(row["created_at"], lang))}{merchant}</div>
  </div>
  <div style="text-align:right">
    <div style="font-weight:800;color:{color}">{amount} {esc(t("common.points", lang))}</div>
    <div class="wafa-small">{esc(t("client.points.balance_after", lang))} {row["balance_after"]}</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def render_dashboard(user: SessionUser) -> None:
    lang = current_lang()
    with database.session() as session:
        summary = loyalty.summary(session, user.id)
        catalog = [_reward_snapshot(reward) for reward in rewards.list_catalog(session, limit=30)]
        transactions = [_tx_snapshot(tx) for tx in loyalty.list_transactions(session, user.id, limit=5)]
        active_promotions = len(promotions.list_promotions(session, limit=20))
        gift_cards = len(giftcards.list_user_gift_cards(session, user.id))

    unlocked = [reward for reward in catalog if reward["points_cost"] <= summary["balance"]]
    next_reward = next((reward for reward in catalog if reward["points_cost"] > summary["balance"]), None)
    progress = (
        min(1.0, summary["balance"] / next_reward["points_cost"]) if next_reward and next_reward["points_cost"] else 1.0
    )

    st.markdown(f"### {esc(t('client.dashboard.greeting', lang, name=user.first_name))}")
    st.caption(t("client.dashboard.subtitle", lang))

    hero_left, hero_right = st.columns([1.55, 1], gap="large")
    with hero_left:
        next_line = ""
        if next_reward:
            next_line = t(
                "client.dashboard.to_go",
                lang,
                points=max(0, next_reward["points_cost"] - summary["balance"]),
                reward=next_reward["title"],
            )
        elif catalog:
            next_line = t("client.dashboard.ready", lang)
        st.markdown(
            f"""
<div class="wafa-points-hero">
  <div class="label">{esc(t("client.dashboard.balance_label", lang))}</div>
  <div class="value">{esc(format_mad(summary["balance"]).replace(" MAD", ""))} <small>{esc(t("common.points", lang))}</small></div>
  <div class="caption">{esc(next_line or t("client.dashboard.card_title", lang))}</div>
  {ui.progress_bar(progress)}
  <div class="wafa-small" style="color:#C9DDF2;margin-top:.55rem">{esc(t("client.dashboard.progress_label", lang))} · {int(progress * 100)}%</div>
</div>
""",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button(
                f"🎁 {t('client.dashboard.use_points', lang)}",
                type="primary",
                width="stretch",
                key="dash_rewards",
            ):
                goto("client.rewards")
        with c2:
            if st.button(
                f"🎫 {t('client.dashboard.show_card', lang)}",
                width="stretch",
                key="dash_card",
            ):
                goto("client.card")

    with hero_right:
        st.markdown(
            f"""
<div class="wafa-card navy" style="height:100%">
  <div class="wafa-row">
    <div>
      <div class="wafa-eyebrow" style="color:#F4C66A">{esc(t("client.card.member", lang))}</div>
      <div style="font-weight:800;font-size:1.05rem">{esc(user.full_name)}</div>
    </div>
    <div class="wafa-logo-mark" style="width:44px;height:44px">W</div>
  </div>
  <div style="display:flex;gap:1.2rem;margin-top:1rem">
    <div><div style="font-size:1.35rem;font-weight:800">{summary["earned"]}</div><div class="wafa-small" style="color:#C9DDF2">{esc(t("client.points.earned", lang))}</div></div>
    <div><div style="font-size:1.35rem;font-weight:800">{summary["spent"]}</div><div class="wafa-small" style="color:#C9DDF2">{esc(t("client.points.spent", lang))}</div></div>
    <div><div style="font-size:1.35rem;font-weight:800">{len(unlocked)}</div><div class="wafa-small" style="color:#C9DDF2">{esc(t("client.dashboard.available_rewards", lang))}</div></div>
  </div>
  <div class="wafa-code light" style="font-size:.77rem;letter-spacing:.05em">{esc(user.phone)}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.write("")
    ui.section_title(t("client.dashboard.quick_actions", lang))
    actions = [
        ("star", "client.dashboard.use_points", "client.rewards", "gold"),
        ("gift", "client.dashboard.buy_gift", "client.gift_create", "green"),
        ("map-pin", "client.promotions.title", "client.promotions", "blue"),
        ("bell", "common.notifications", "client.notifications", "navy"),
    ]
    cols = st.columns(4, gap="medium")
    for column, (icon, label, page, tone) in zip(cols, actions, strict=True):
        with column:
            st.markdown(
                f"""<div class="wafa-card tight" style="text-align:center">
                <div class="wafa-icon {tone}" style="margin:0 auto .5rem">{icon_svg(icon, 19)}</div>
                <div style="font-size:.78rem;font-weight:750">{esc(t(label, lang))}</div></div>""",
                unsafe_allow_html=True,
            )
            if st.button(t(label, lang), key=f"quick_{page}", width="stretch"):
                goto(page)

    left, right = st.columns([1.25, 1], gap="large")
    with left:
        st.write("")
        ui.section_title(t("client.dashboard.last_activity", lang))
        with st.container():
            _render_transactions(transactions, lang, limit=5)
        if st.button(t("common.see_all", lang), key="see_all_tx"):
            goto("client.points")

    with right:
        st.write("")
        ui.section_title(t("client.dashboard.recommended", lang))
        if catalog:
            for reward in catalog[:3]:
                with st.container():
                    st.markdown(_reward_card_html(reward, lang), unsafe_allow_html=True)
                    if st.button(
                        t("common.see_details", lang),
                        key=f"dash_reward_{reward['id']}",
                        width="stretch",
                    ):
                        goto("client.reward_detail", reward_id=reward["id"])
                    st.write("")
        else:
            ui.empty_state(t("client.rewards.empty", lang), t("common.no_data", lang), icon="gift")

    st.write("")
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        ui.stat_card(
            t("client.dashboard.available_rewards", lang),
            str(len(unlocked)),
            hint=t("client.rewards.title", lang),
            icon="gift",
            tone="gold",
        )
    with c2:
        ui.stat_card(
            t("common.promotions", lang),
            str(active_promotions),
            hint=t("client.promotions.subtitle", lang),
            icon="map-pin",
            tone="blue",
        )
    with c3:
        ui.stat_card(
            t("client.gift.my_cards", lang),
            str(gift_cards),
            hint=t("client.gift.subtitle", lang),
            icon="wallet",
            tone="green",
        )

    if st.button(t("client.dashboard.see_catalog", lang), key="dash_catalog", type="primary"):
        goto("client.rewards")


# ---------------------------------------------------------------------------
# Carte & QR
# ---------------------------------------------------------------------------


def render_card(user: SessionUser) -> None:
    lang = current_lang()
    with database.session() as session:
        account = loyalty.get_account(session, user.id)
        balance = account.total_points
        token = account.qr_code_token

    ui.page_header(t("client.card.title", lang), t("client.card.subtitle", lang), eyebrow=t("nav.client.card", lang))

    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown(
            f"""
<div class="wafa-card navy" style="padding:1.6rem">
  <div class="wafa-row">
    <div>
      <div class="wafa-eyebrow" style="color:#F4C66A">{esc(t("client.card.member", lang))}</div>
      <div style="font-size:1.2rem;font-weight:800">{esc(user.full_name)}</div>
      <div class="wafa-small" style="color:#C9DDF2;margin-top:.2rem">{esc(user.phone)}</div>
    </div>
    <div class="wafa-logo-mark" style="width:48px;height:48px;font-size:1.25rem">W</div>
  </div>
  <div style="margin-top:1.5rem;display:flex;align-items:flex-end;justify-content:space-between">
    <div>
      <div class="wafa-small" style="color:#C9DDF2">{esc(t("client.dashboard.balance_label", lang))}</div>
      <div style="font-size:2.25rem;font-weight:800;line-height:1">{balance} <small style="font-size:.8rem;font-weight:600">{esc(t("common.points", lang))}</small></div>
    </div>
    <div style="font-size:.7rem;color:#C9DDF2;text-align:right">
      {esc(user.city)}<br/>{esc(t("common.member_since", lang))} {esc(format_date(user.created_at, lang))}
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.write("")
        ui.info_banner(
            t("client.card.tip_title", lang),
            t("client.card.tip_text", lang),
            tone="gold",
            icon="shield",
        )

    with right:
        png = qr_png_bytes(qr_payload(token))
        encoded = base64.b64encode(png).decode("ascii")
        st.markdown(
            f"""
<div class="wafa-qr-frame" style="text-align:center">
  <div class="wafa-eyebrow">{esc(t("client.card.qr_title", lang))}</div>
  <img src="data:image/png;base64,{encoded}" alt="QR WafaClub"
       style="width:100%;max-width:235px;margin:.4rem auto;display:block"/>
</div>
""",
            unsafe_allow_html=True,
        )
        st.caption(t("client.card.qr_help", lang))
        st.download_button(
            f"⬇️ {t('client.card.download', lang)}",
            data=png,
            file_name="wafaclub-carte-qr.png",
            mime="image/png",
            width="stretch",
            key="download_qr",
        )
        st.markdown(f"**{t('client.card.show_phone', lang)}**")
        ui.code_box(user.phone)
        st.caption(t("client.card.token_notice", lang))
        st.caption(t("client.card.simulated_notice", lang))


# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------


def render_points(user: SessionUser) -> None:
    lang = current_lang()
    with database.session() as session:
        summary = loyalty.summary(session, user.id)
        transactions = [_tx_snapshot(tx) for tx in loyalty.list_transactions(session, user.id, limit=200)]

    ui.page_header(t("client.points.title", lang), t("client.points.subtitle", lang), eyebrow=t("common.history", lang))
    cols = st.columns(4, gap="medium")
    with cols[0]:
        ui.stat_card(t("client.points.balance", lang), _points(summary["balance"]), icon="wallet", tone="navy")
    with cols[1]:
        ui.stat_card(t("client.points.earned", lang), _points(summary["earned"]), icon="trending", tone="green")
    with cols[2]:
        ui.stat_card(t("client.points.spent", lang), _points(summary["spent"]), icon="star", tone="gold")
    with cols[3]:
        ui.stat_card(t("client.points.count", lang), str(summary["transactions"]), icon="receipt", tone="blue")

    st.write("")
    ui.section_title(t("client.points.chart_title", lang))
    chart_rows = [
        {
            "Date": format_date(row["created_at"], lang),
            "Points": row["points"],
        }
        for row in transactions
    ]
    if chart_rows:
        st.bar_chart(chart_rows, x="Date", y="Points", color="#1E6FA8", height=220)
    else:
        st.caption(t("common.no_data", lang))

    st.write("")
    ui.section_title(t("client.points.journal_title", lang), t("client.points.rule", lang))
    if transactions:
        rows = [
            {
                t("common.date", lang): format_datetime(row["created_at"], lang),
                t("common.type", lang): t(f"transaction.{row['type'].value}", lang),
                t("common.details", lang): row["description"],
                t("common.merchant", lang): row["merchant"] or "—",
                t("common.points", lang): row["points"],
                t("client.points.balance_after", lang): row["balance_after"],
            }
            for row in transactions
        ]
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        ui.empty_state(t("client.points.empty", lang), t("common.no_data", lang), icon="receipt")

    ui.legal_note(lang)


# ---------------------------------------------------------------------------
# Catalogue de récompenses
# ---------------------------------------------------------------------------


def render_rewards(user: SessionUser) -> None:
    lang = current_lang()
    with database.session() as session:
        catalog = [_reward_snapshot(reward) for reward in rewards.list_catalog(session, limit=100)]
        summary = loyalty.summary(session, user.id)

    ui.page_header(
        t("client.rewards.title", lang),
        t("client.rewards.subtitle", lang),
        eyebrow=t("client.dashboard.use_points", lang),
    )
    st.markdown(
        f"""
<div class="wafa-card tight" style="margin-bottom:1rem">
  <div class="wafa-row">
    <div><div class="wafa-small">{esc(t("client.points.balance", lang))}</div>
    <div style="font-weight:800;font-size:1.3rem">{summary["balance"]} {esc(t("common.points", lang))}</div></div>
    {ui.badge(t("client.dashboard.available_rewards", lang, count=sum(1 for r in catalog if r["points_cost"] <= summary["balance"])), "green")}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([2, 1.4, 1.4], gap="medium")
    with c1:
        search = st.text_input(
            t("common.search", lang), placeholder=t("client.rewards.title", lang), key="reward_search"
        )
    with c2:
        city = st.selectbox(
            t("common.city", lang), [t("common.all", lang), *merchants.MOROCCAN_CITIES], key="reward_city"
        )
    with c3:
        category = st.selectbox(
            t("common.category", lang), [t("common.all", lang), *merchants.BUSINESS_CATEGORIES], key="reward_category"
        )

    filtered = catalog
    if search:
        needle = search.lower()
        filtered = [
            reward
            for reward in filtered
            if needle in reward["title"].lower() or needle in (reward["merchant_name"] or "").lower()
        ]
    if city != t("common.all", lang):
        filtered = [r for r in filtered if r["merchant_city"] == city or r["merchant_id"] is None]
    if category != t("common.all", lang):
        filtered = [r for r in filtered if r["merchant_category"] == category or r["merchant_id"] is None]

    if not filtered:
        ui.empty_state(t("client.rewards.empty", lang), t("common.no_data", lang), icon="gift")
        return

    cols = st.columns(3, gap="medium")
    for index, reward in enumerate(filtered):
        with cols[index % 3]:
            st.markdown(_reward_card_html(reward, lang), unsafe_allow_html=True)
            can_afford = summary["balance"] >= reward["points_cost"]
            if st.button(
                t("common.see_details", lang),
                key=f"catalog_reward_{reward['id']}",
                width="stretch",
                type="primary" if can_afford else "secondary",
            ):
                goto("client.reward_detail", reward_id=reward["id"])
            if not can_afford:
                st.caption(t("client.rewards.not_enough", lang, missing=reward["points_cost"] - summary["balance"]))
            st.write("")


def render_reward_detail(user: SessionUser) -> None:
    lang = current_lang()
    reward_id = context("reward_id")
    try:
        with database.session() as session:
            reward = _reward_snapshot(rewards.get_reward(session, int(reward_id)))
            summary = loyalty.summary(session, user.id)
    except Exception as error:
        ui.show_error(error, lang)
        if st.button(t("client.rewards.back_catalog", lang), key="detail_back_error"):
            goto("client.rewards")
        return

    scope = reward["merchant_name"] or t("client.rewards.network_scope", lang)
    can_afford = summary["balance"] >= reward["points_cost"]
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        ui.page_header(reward["title"], reward["description"], eyebrow=t("common.reward", lang))
        st.markdown(
            f"""
<div class="wafa-card">
  <div class="wafa-row">
    <div class="wafa-reward-icon" style="width:64px;height:64px;font-size:2rem">{esc(reward["icon"])}</div>
    <div style="text-align:right">
      {ui.badge(t(reward_type_key(reward["type"]), lang), "gold")}<br/>
      <span class="wafa-small">{esc(scope)}</span>
    </div>
  </div>
  <div class="wafa-line" style="margin-top:.8rem"><span>{esc(t("client.rewards.points_required", lang, points=format_points(reward["points_cost"], lang)))}</span><strong>{reward["points_cost"]} {esc(t("common.points", lang))}</strong></div>
  <div class="wafa-line"><span>{esc(t("client.rewards.valid_until", lang, date=format_date(reward["expires_at"], lang)))}</span><strong>{esc(format_date(reward["expires_at"], lang))}</strong></div>
  <div class="wafa-line"><span>{esc(t("client.rewards.stock", lang, stock=reward["stock"] if reward["stock"] is not None else t("client.rewards.unlimited", lang)))}</span><strong>{reward["stock"] if reward["stock"] is not None else esc(t("client.rewards.unlimited", lang))}</strong></div>
  <div class="wafa-line"><span>{esc(t("common.merchant", lang))}</span><strong>{esc(scope)}</strong></div>
  <div class="wafa-line"><span>{esc(t("merchant.rewards.value", lang))}</span><strong>{esc(format_mad(reward["value"], lang)) if reward["value"] is not None else "—"}</strong></div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.write("")
        ui.section_title(t("client.rewards.conditions", lang))
        st.write(reward["description"] or t("client.rewards.confirm_warning", lang))

    with right:
        st.markdown(
            f"""
<div class="wafa-card {"green" if can_afford else "gold"}">
  <div class="wafa-small">{esc(t("client.points.balance", lang))}</div>
  <div style="font-size:1.8rem;font-weight:800">{summary["balance"]} <small style="font-size:.8rem">{esc(t("common.points", lang))}</small></div>
  <div class="wafa-small" style="margin-top:.4rem">{esc(t("client.rewards.confirm_cost", lang))} · {reward["points_cost"]} {esc(t("common.points", lang))}</div>
  <div class="wafa-small">{esc(t("client.rewards.confirm_after", lang))} · {max(0, summary["balance"] - reward["points_cost"])} {esc(t("common.points", lang))}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.write("")
        if can_afford:
            if st.button(
                t("client.rewards.use", lang),
                type="primary",
                width="stretch",
                key="reward_use",
            ):
                goto("client.reward_confirm", reward_id=reward["id"])
        else:
            st.warning(t("client.rewards.not_enough", lang, missing=reward["points_cost"] - summary["balance"]))
        if st.button(t("client.rewards.back_catalog", lang), width="stretch", key="reward_back"):
            goto("client.rewards")
        ui.info_banner(
            t("client.rewards.confirm_warning", lang),
            t("client.card.simulated_notice", lang),
            tone="blue",
            icon="shield",
        )


def render_reward_confirm(user: SessionUser) -> None:
    lang = current_lang()
    reward_id = int(context("reward_id") or 0)
    try:
        with database.session() as session:
            reward = _reward_snapshot(rewards.get_reward(session, reward_id))
            summary = loyalty.summary(session, user.id)
    except Exception as error:
        ui.show_error(error, lang)
        return

    ui.page_header(t("client.rewards.confirm_title", lang), t("client.rewards.confirm_subtitle", lang))
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        scope = reward["merchant_name"] or t("client.rewards.network_scope", lang)
        st.markdown(
            f"""
<div class="wafa-card">
  <div class="wafa-row"><div class="wafa-reward-icon">{esc(reward["icon"])}</div>{ui.badge(scope, "blue")}</div>
  <div style="font-weight:800;font-size:1.1rem;margin:.7rem 0 .2rem">{esc(reward["title"])}</div>
  <div class="wafa-muted">{esc(reward["description"])}</div>
  <div class="wafa-review" style="margin-top:1rem">
    {ui.review_line(t("client.rewards.confirm_balance", lang), f"{summary['balance']} {t('common.points', lang)}")}
    {ui.review_line(t("client.rewards.confirm_cost", lang), f"{reward['points_cost']} {t('common.points', lang)}")}
    {ui.review_line(t("client.rewards.confirm_after", lang), f"{max(0, summary['balance'] - reward['points_cost'])} {t('common.points', lang)}")}
    {ui.review_line(t("common.expires_at", lang), format_date(reward["expires_at"], lang))}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    with right:
        st.warning(t("client.rewards.confirm_warning", lang))
        if st.button(
            t("client.rewards.confirm_button", lang),
            type="primary",
            width="stretch",
            key="confirm_redeem",
        ):
            try:
                with database.session() as session:
                    redemption = rewards.redeem_reward(session, user_id=user.id, reward_id=reward_id)
                    code = redemption.code
                    expires = redemption.expires_at
            except Exception as error:
                ui.show_error(error, lang)
            else:
                flash(t("client.rewards.success_text", lang))
                goto(
                    "client.reward_success",
                    code=code,
                    reward=reward["title"],
                    merchant=reward["merchant_name"],
                    expires=str(expires),
                )
        if st.button(t("common.cancel", lang), width="stretch", key="cancel_redeem"):
            goto("client.reward_detail", reward_id=reward_id)


def render_reward_success(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    code = context("code", "")
    reward = context("reward", "")
    merchant = context("merchant")
    expires = context("expires")
    ui.page_header(t("client.rewards.success_title", lang), t("client.rewards.success_text", lang))
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown(
            f"""
<div class="wafa-card gold" style="text-align:center">
  <div class="wafa-reward-icon" style="margin:0 auto;width:66px;height:66px;font-size:2rem">🎁</div>
  <div style="font-weight:800;font-size:1.1rem;margin-top:.8rem">{esc(reward)}</div>
  <div class="wafa-muted">{esc(merchant or t("client.rewards.network_scope", lang))}</div>
  <div class="wafa-small" style="margin-top:.5rem">{esc(t("client.rewards.code_hint", lang))}</div>
</div>
""",
            unsafe_allow_html=True,
        )
    with right:
        ui.code_box(str(code))
        if expires and expires != "None":
            st.caption(f"{t('client.rewards.valid_until', lang)} {expires[:10]}")
        ui.info_banner(
            t("client.rewards.success_title", lang),
            t("client.rewards.code_hint", lang),
            tone="green",
            icon="check-circle",
        )
        st.write("")
        if st.button(
            t("client.rewards.see_mine", lang),
            type="primary",
            width="stretch",
            key="success_my_rewards",
        ):
            goto("client.my_rewards")
        if st.button(t("client.rewards.back_catalog", lang), width="stretch", key="success_catalog"):
            goto("client.rewards")


def render_my_rewards(user: SessionUser) -> None:
    lang = current_lang()
    with database.session() as session:
        redemptions = rewards.list_user_redemptions(session, user.id)
        rows = [
            {
                "id": redemption.id,
                "code": redemption.code,
                "title": redemption.reward.title,
                "icon": redemption.reward.icon,
                "status": redemption.status,
                "merchant": redemption.merchant.business_name if redemption.merchant else None,
                "created_at": redemption.created_at,
                "expires_at": redemption.expires_at,
                "redeemed_at": redemption.redeemed_at,
            }
            for redemption in redemptions
        ]

    ui.page_header(
        t("client.my_rewards.title", lang), t("client.my_rewards.subtitle", lang), eyebrow=t("common.rewards", lang)
    )
    if not rows:
        ui.empty_state(t("client.my_rewards.empty", lang), t("client.rewards.subtitle", lang), icon="ticket")
        if st.button(t("client.rewards.back_catalog", lang), key="my_rewards_catalog", type="primary"):
            goto("client.rewards")
        return

    for reward in rows:
        left, right = st.columns([1.5, 1], gap="medium")
        with left:
            st.markdown(
                f"""
<div class="wafa-card">
  <div class="wafa-row">
    <div style="display:flex;gap:.8rem;align-items:center">
      <div class="wafa-reward-icon">{esc(reward["icon"])}</div>
      <div><div style="font-weight:800">{esc(reward["title"])}</div>
      <div class="wafa-small">{esc(reward["merchant"] or t("client.rewards.network_scope", lang))}</div></div>
    </div>
    {ui.status_badge(reward["status"], lang)}
  </div>
  <div class="wafa-line" style="margin-top:.5rem"><span>{esc(t("client.my_rewards.expires", lang))}</span><strong>{esc(format_date(reward["expires_at"], lang))}</strong></div>
  <div class="wafa-line"><span>{esc(t("common.created_at", lang))}</span><strong>{esc(format_date(reward["created_at"], lang))}</strong></div>
  {f'<div class="wafa-line"><span>{esc(t("client.my_rewards.validated_at", lang))}</span><strong>{esc(format_datetime(reward["redeemed_at"], lang))}</strong></div>' if reward["redeemed_at"] else ""}
</div>
""",
                unsafe_allow_html=True,
            )
        with right:
            if reward["status"] == RedemptionStatus.PENDING:
                st.markdown(f"**{esc(t('client.my_rewards.show_code', lang))}**")
                ui.code_box(reward["code"])
                st.caption(t("client.rewards.code_hint", lang))
            elif reward["status"] == RedemptionStatus.USED:
                st.success(t("status.USED", lang))
            else:
                st.info(t(f"status.{reward['status'].value}", lang))
        st.write("")

    if st.button(t("client.rewards.back_catalog", lang), key="my_rewards_catalog_bottom"):
        goto("client.rewards")


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------


def render_promotions(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    with database.session() as session:
        promotion_rows = promotions.list_promotions(session, limit=100)
        rows = [
            {
                "id": promotion.id,
                "title": promotion.title,
                "description": promotion.description,
                "icon": promotion.icon,
                "merchant_id": promotion.merchant_id,
                "merchant_name": promotion.merchant.business_name,
                "city": promotion.city,
                "neighborhood": promotion.neighborhood,
                "category": promotion.merchant.category,
                "expires_at": promotion.expires_at,
            }
            for promotion in promotion_rows
        ]

    ui.page_header(
        t("client.promotions.title", lang), t("client.promotions.subtitle", lang), eyebrow=t("common.promotions", lang)
    )
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        city = st.selectbox(
            t("client.promotions.filter_city", lang),
            [t("common.all", lang), *merchants.MOROCCAN_CITIES],
            key="promo_city",
        )
    with c2:
        category = st.selectbox(
            t("client.promotions.filter_category", lang),
            [t("common.all", lang), *merchants.BUSINESS_CATEGORIES],
            key="promo_category",
        )
    filtered = [
        row
        for row in rows
        if (city == t("common.all", lang) or row["city"] == city)
        and (category == t("common.all", lang) or row["category"] == category)
    ]
    if not filtered:
        ui.empty_state(t("client.promotions.empty", lang), t("common.no_data", lang), icon="map-pin")
        return
    cols = st.columns(2, gap="medium")
    for index, promotion in enumerate(filtered):
        with cols[index % 2]:
            st.markdown(_promotion_card_html_for_dict(promotion, lang), unsafe_allow_html=True)
            if st.button(t("common.see_details", lang), key=f"promo_detail_{promotion['id']}", width="stretch"):
                goto("client.promotion_detail", promotion_id=promotion["id"])
            st.write("")


def render_promotion_detail(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    promotion_id = int(context("promotion_id") or 0)
    try:
        with database.session() as session:
            promotion = promotions.get_promotion(session, promotion_id)
            data = {
                "id": promotion.id,
                "title": promotion.title,
                "description": promotion.description,
                "icon": promotion.icon,
                "merchant_id": promotion.merchant_id,
                "merchant_name": promotion.merchant.business_name,
                "merchant_phone": promotion.merchant.phone,
                "merchant_address": promotion.merchant.address,
                "city": promotion.city,
                "neighborhood": promotion.neighborhood,
                "starts_at": promotion.starts_at,
                "expires_at": promotion.expires_at,
            }
    except Exception as error:
        ui.show_error(error, lang)
        return

    ui.page_header(data["title"], data["description"], eyebrow=t("client.promotions.detail_title", lang))
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        st.markdown(
            f"""
<div class="wafa-card gold">
  <div class="wafa-row">
    <div class="wafa-reward-icon" style="width:62px;height:62px;font-size:1.9rem">{esc(data["icon"])}</div>
    {ui.badge(t("common.promotion", lang), "gold")}
  </div>
  <div class="wafa-review" style="margin-top:1rem">
    {ui.review_line(t("common.merchant", lang), data["merchant_name"])}
    {ui.review_line(t("client.merchants.address", lang), data["merchant_address"])}
    {ui.review_line(t("client.promotions.at", lang), f"{data['neighborhood']} · {data['city']}")}
    {ui.review_line(t("common.from", lang), format_date(data["starts_at"], lang))}
    {ui.review_line(t("client.promotions.expires", lang), format_date(data["expires_at"], lang))}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        ui.info_banner(
            t("client.promotions.no_gps", lang), t("client.card.simulated_notice", lang), tone="blue", icon="map-pin"
        )
    with right:
        st.markdown(f"**{t('client.merchants.detail_title', lang)}**")
        st.write(f"{data['merchant_name']}\n\n{data['merchant_address']}\n\n📞 {data['merchant_phone']}")
        if st.button(t("client.promotions.see_merchant", lang), type="primary", width="stretch", key="promo_merchant"):
            goto("client.merchant_detail", merchant_id=data["merchant_id"])
        if st.button(t("common.back", lang), width="stretch", key="promo_back"):
            goto("client.promotions")


# ---------------------------------------------------------------------------
# Commerces
# ---------------------------------------------------------------------------


def render_merchants(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    with database.session() as session:
        list_ = merchants.list_merchants(session)
        rows = [
            {
                "id": merchant.id,
                "name": merchant.business_name,
                "category": merchant.category,
                "city": merchant.city,
                "neighborhood": merchant.neighborhood,
                "rule": merchant.points_per_amount,
            }
            for merchant in list_
        ]
    ui.page_header(
        t("client.merchants.title", lang), t("client.merchants.subtitle", lang), eyebrow=t("common.merchant", lang)
    )
    c1, c2 = st.columns([1.4, 1], gap="medium")
    with c1:
        search = st.text_input(t("common.search", lang), placeholder=t("common.merchant", lang), key="merchant_search")
    with c2:
        city = st.selectbox(
            t("common.city", lang), [t("common.all", lang), *merchants.MOROCCAN_CITIES], key="merchant_city"
        )
    filtered = [
        row
        for row in rows
        if (not search or search.lower() in row["name"].lower() or search.lower() in row["category"].lower())
        and (city == t("common.all", lang) or row["city"] == city)
    ]
    if not filtered:
        ui.empty_state(t("client.merchants.empty", lang), t("common.no_data", lang), icon="store")
        return
    cols = st.columns(3, gap="medium")
    for index, merchant in enumerate(filtered):
        with cols[index % 3]:
            st.markdown(_merchant_card_html(merchant, lang), unsafe_allow_html=True)
            if st.button(t("common.see_details", lang), key=f"merchant_detail_{merchant['id']}", width="stretch"):
                goto("client.merchant_detail", merchant_id=merchant["id"])
            st.write("")


def render_merchant_detail(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    merchant_id = int(context("merchant_id") or 0)
    try:
        with database.session() as session:
            merchant = merchants.get_merchant(session, merchant_id)
            data = {
                "id": merchant.id,
                "name": merchant.business_name,
                "description": merchant.description,
                "category": merchant.category,
                "city": merchant.city,
                "neighborhood": merchant.neighborhood,
                "address": merchant.address,
                "phone": merchant.phone,
                "rule": merchant.points_per_amount,
                "active": merchant.is_active,
            }
            reward_rows = [
                _reward_snapshot(reward) for reward in rewards.list_catalog(session, merchant_id=merchant_id)
            ]
            promotion_rows = [
                {
                    "id": promotion.id,
                    "title": promotion.title,
                    "description": promotion.description,
                    "icon": promotion.icon,
                    "merchant_name": merchant.business_name,
                    "city": promotion.city,
                    "expires_at": promotion.expires_at,
                }
                for promotion in promotions.list_promotions(session, merchant_id=merchant_id)
            ]
    except Exception as error:
        ui.show_error(error, lang)
        return

    ui.page_header(data["name"], data["description"], eyebrow=f"{data['category']} · {data['city']}")
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown(
            f"""
<div class="wafa-card">
  <div class="wafa-row"><div class="wafa-icon blue">{icon_svg("store", 21)}</div>{ui.badge(data["category"], "blue")}</div>
  <div class="wafa-review" style="margin-top:.9rem">
    {ui.review_line(t("client.merchants.address", lang), f"{data['address']}, {data['neighborhood']}")}
    {ui.review_line(t("common.city", lang), data["city"])}
    {ui.review_line(t("common.phone", lang), data["phone"])}
    {ui.review_line(t("client.merchants.rule", lang, points=format_mad(data["rule"], lang)), format_mad(data["rule"], lang))}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    with right:
        ui.info_banner(
            t("client.merchants.rule", lang, points=format_mad(data["rule"], lang)),
            t("client.card.tip_text", lang),
            tone="gold",
            icon="star",
        )
    st.write("")
    ui.section_title(t("client.merchants.rewards", lang))
    if reward_rows:
        cols = st.columns(3, gap="medium")
        for index, reward in enumerate(reward_rows):
            with cols[index % 3]:
                st.markdown(_reward_card_html(reward, lang), unsafe_allow_html=True)
                if st.button(t("common.see_details", lang), key=f"mdetail_reward_{reward['id']}", width="stretch"):
                    goto("client.reward_detail", reward_id=reward["id"])
                st.write("")
    else:
        ui.empty_state(t("client.merchants.no_rewards", lang), t("common.no_data", lang), icon="gift")

    st.write("")
    ui.section_title(t("client.merchants.promotions", lang))
    if promotion_rows:
        cols = st.columns(2, gap="medium")
        for index, promotion in enumerate(promotion_rows):
            with cols[index % 2]:
                st.markdown(_promotion_card_html_for_dict(promotion, lang), unsafe_allow_html=True)
                if st.button(
                    t("common.see_details", lang),
                    key=f"mdetail_promo_{promotion['id']}",
                    width="stretch",
                ):
                    goto("client.promotion_detail", promotion_id=promotion["id"])
                st.write("")
    else:
        st.caption(t("client.dashboard.no_activity", lang))


# ---------------------------------------------------------------------------
# Cartes cadeaux
# ---------------------------------------------------------------------------


def render_gift_cards(user: SessionUser) -> None:
    lang = current_lang()
    with database.session() as session:
        cards = [_gift_snapshot(card) for card in giftcards.list_user_gift_cards(session, user.id)]

    header_left, header_right = st.columns([2, 1])
    with header_left:
        ui.page_header(
            t("client.gift.title", lang), t("client.gift.subtitle", lang), eyebrow=t("nav.client.gift_cards", lang)
        )
    with header_right:
        st.write("")
        if st.button(f"➕ {t('client.gift.create', lang)}", type="primary", width="stretch", key="new_gift"):
            goto("client.gift_create")

    if not cards:
        ui.empty_state(t("client.gift.empty", lang), t("client.gift.subtitle", lang), icon="gift")
        return

    sent = [card for card in cards if card["sender_name"] == user.full_name]
    received = [card for card in cards if card["sender_name"] != user.full_name]
    tab_sent, tab_received = st.tabs(
        [f"{t('client.gift.sent', lang)} ({len(sent)})", f"{t('client.gift.received', lang)} ({len(received)})"]
    )
    for tab, group in ((tab_sent, sent), (tab_received, received)):
        with tab:
            if not group:
                ui.empty_state(t("client.gift.empty", lang), t("client.gift.subtitle", lang), icon="gift")
                continue
            for card in group:
                _render_gift_card(card, lang)


def _render_gift_card(card: dict, lang: str) -> None:
    scope = card["merchant_name"] or t("client.gift.network", lang)
    left, right = st.columns([1.5, 1], gap="medium")
    with left:
        st.markdown(
            f"""
<div class="wafa-card gold">
  <div class="wafa-row">
    <div class="wafa-reward-icon" style="width:60px;height:60px;font-size:1.7rem">🎁</div>
    <div style="text-align:right">
      {ui.status_badge(card["status"], lang)}<br/>
      <span style="font-weight:800;font-size:1.15rem">{esc(format_mad(card["amount"], lang))}</span>
    </div>
  </div>
  <div class="wafa-line" style="margin-top:.7rem"><span>{esc(t("client.gift.to", lang))}</span><strong>{esc(card["recipient_name"])}</strong></div>
  <div class="wafa-line"><span>{esc(t("client.gift.scope", lang))}</span><strong>{esc(scope)}</strong></div>
  <div class="wafa-line"><span>{esc(t("client.gift.from", lang))}</span><strong>{esc(card["sender_name"])}</strong></div>
  <div class="wafa-line"><span>{esc(t("client.gift.expires", lang))}</span><strong>{esc(format_date(card["expires_at"], lang))}</strong></div>
  {f'<div class="wafa-muted" style="margin-top:.5rem">« {esc(card["message"])} »</div>' if card["message"] else ""}
</div>
""",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(f"**{t('client.gift.code', lang)}**")
        ui.code_box(card["code"])
        if card["status"] == GiftCardStatus.USED:
            st.caption(f"{t('client.gift.used_at', lang)} {format_datetime(card['redeemed_at'], lang)}")
        elif card["status"] == GiftCardStatus.ACTIVE:
            st.caption(t("client.gift.payment_text", lang))
        else:
            st.caption(t(f"status.{card['status'].value}", lang))
    st.write("")


def _gift_merchant_options(session) -> tuple[list[int | None], dict[int | None, str]]:
    names = {None: t("client.gift.scope_network", current_lang())}
    ids: list[int | None] = [None]
    for merchant in merchants.list_merchants(session):
        ids.append(merchant.id)
        names[merchant.id] = merchant.business_name
    return ids, names


def render_gift_create(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    with database.session() as session:
        merchant_ids, merchant_names = _gift_merchant_options(session)

    ui.page_header(
        t("client.gift.create", lang), t("client.gift.subtitle", lang), eyebrow=t("nav.client.gift_cards", lang)
    )
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        with st.form("gift_create_form"):
            st.markdown(f"**{t('client.gift.choose_amount', lang)}**")
            preset_labels = [f"{amount} MAD" for amount in GIFT_CARD_PRESETS] + [t("client.gift.custom_amount", lang)]
            preset = st.radio(
                t("common.amount", lang),
                preset_labels,
                horizontal=True,
                label_visibility="collapsed",
            )
            custom_amount = GIFT_CARD_PRESETS[1]
            if preset == preset_labels[-1]:
                custom_amount = st.number_input(
                    t("client.gift.custom_amount", lang),
                    min_value=float(GIFT_CARD_MIN_AMOUNT),
                    max_value=float(GIFT_CARD_MAX_AMOUNT),
                    value=150.0,
                    step=10.0,
                )

            recipient_mode = st.radio(
                t("common.client", lang),
                [t("client.gift.for_someone", lang), t("client.gift.for_me", lang)],
                horizontal=True,
            )
            recipient_name = ""
            recipient_phone = ""
            if recipient_mode == t("client.gift.for_someone", lang):
                c1, c2 = st.columns(2)
                with c1:
                    recipient_name = st.text_input(t("client.gift.recipient_name", lang))
                with c2:
                    recipient_phone = st.text_input(t("client.gift.recipient_phone", lang), placeholder="+212 6...")

            scope = st.selectbox(
                t("client.gift.scope", lang),
                merchant_ids,
                format_func=lambda value: merchant_names.get(value, "—"),
            )
            message = st.text_area(t("client.gift.message", lang), max_chars=255, height=80)
            st.markdown(f"**{t('client.gift.payment_title', lang)}**")
            accepted = st.checkbox(t("client.gift.payment_check", lang))
            submitted = st.form_submit_button(t("common.continue", lang), type="primary", width="stretch")
        if submitted:
            amount = custom_amount if preset == preset_labels[-1] else float(preset.replace(" MAD", ""))
            if not accepted:
                st.error(t("client.gift.payment_required", lang))
            elif recipient_mode == t("client.gift.for_someone", lang) and len(recipient_name.strip()) < 2:
                st.error(t("errors.recipient_required", lang))
            else:
                SS["pending_gift"] = {
                    "amount": str(amount),
                    "recipient_name": recipient_name.strip(),
                    "recipient_phone": recipient_phone.strip(),
                    "merchant_id": scope,
                    "merchant_name": merchant_names.get(scope),
                    "message": message.strip(),
                    "recipient_is_self": recipient_mode == t("client.gift.for_me", lang),
                }
                goto("client.gift_confirm")
    with right:
        st.markdown(
            f"""
<div class="wafa-card navy">
  <div class="wafa-eyebrow" style="color:#F4C66A">{esc(t("client.gift.payment_title", lang))}</div>
  <div style="font-size:1.55rem;font-weight:800;margin:.3rem 0">{esc(t("common.simulated_payment", lang))}</div>
  <div class="wafa-small" style="color:#C9DDF2;line-height:1.6">{esc(t("client.gift.payment_text", lang))}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.write("")
        ui.info_banner(
            t("client.gift.confirm_title", lang),
            t("client.gift.confirm_text", lang),
            tone="gold",
            icon="shield",
        )


def render_gift_confirm(user: SessionUser) -> None:
    lang = current_lang()
    pending = SS.get("pending_gift")
    if not pending:
        goto("client.gift_create")
        return
    amount = Decimal(pending["amount"])
    scope = pending.get("merchant_name") or t("client.gift.scope_network", lang)
    recipient = t("client.gift.for_me", lang) if pending["recipient_is_self"] else pending["recipient_name"]
    ui.page_header(t("client.gift.confirm_title", lang), t("client.gift.confirm_text", lang))
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.markdown(
            f"""
<div class="wafa-card gold">
  <div class="wafa-row"><div class="wafa-reward-icon" style="width:60px;height:60px;font-size:1.8rem">🎁</div>
  <div style="font-weight:800;font-size:1.45rem">{esc(format_mad(amount, lang))}</div></div>
  <div class="wafa-review" style="margin-top:.9rem">
    {ui.review_line(t("client.gift.to", lang), recipient)}
    {ui.review_line(t("client.gift.scope", lang), scope)}
    {ui.review_line(t("client.gift.message", lang), pending["message"] or "—")}
    {ui.review_line(t("client.gift.payment_title", lang), t("common.simulated_payment", lang))}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    with right:
        if st.button(
            t("client.gift.confirm_button", lang),
            type="primary",
            width="stretch",
            key="confirm_gift",
        ):
            try:
                with database.session() as session:
                    card = giftcards.create_gift_card(
                        session,
                        sender_id=user.id,
                        amount=amount,
                        recipient_name=pending["recipient_name"],
                        recipient_phone=pending["recipient_phone"] or None,
                        merchant_id=pending["merchant_id"],
                        message=pending["message"],
                        recipient_is_self=pending["recipient_is_self"],
                    )
                    code = card.code
                    card_amount = format_mad(card.amount, lang)
                    card_recipient = card.recipient_name
                    card_scope = card.merchant.business_name if card.merchant else t("client.gift.scope_network", lang)
            except Exception as error:
                ui.show_error(error, lang)
            else:
                SS["pending_gift"] = None
                flash(t("client.gift.success_text", lang))
                goto(
                    "client.gift_success",
                    code=code,
                    amount=card_amount,
                    recipient=card_recipient,
                    scope=card_scope,
                )
        if st.button(t("common.cancel", lang), width="stretch", key="cancel_gift"):
            SS["pending_gift"] = None
            goto("client.gift_cards")


def render_gift_success(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    ui.page_header(t("client.gift.success_title", lang), t("client.gift.success_text", lang))
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown(
            f"""
<div class="wafa-card gold" style="text-align:center">
  <div class="wafa-reward-icon" style="margin:0 auto;width:68px;height:68px;font-size:2rem">🎁</div>
  <div style="font-weight:800;font-size:1.6rem;margin-top:.7rem">{esc(context("amount", ""))}</div>
  <div class="wafa-muted">{esc(context("recipient", ""))} · {esc(context("scope", ""))}</div>
</div>
""",
            unsafe_allow_html=True,
        )
    with right:
        ui.code_box(context("code", ""))
        st.caption(t("client.gift.payment_text", lang))
        if st.button(t("client.gift.see_cards", lang), type="primary", width="stretch", key="gift_success_cards"):
            goto("client.gift_cards")
        if st.button(t("nav.client.dashboard", lang), width="stretch", key="gift_success_home"):
            goto("client.dashboard")


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def render_notifications(user: SessionUser) -> None:
    lang = current_lang()
    with database.session() as session:
        items = [
            {
                "id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "is_read": notification.is_read,
                "created_at": notification.created_at,
                "link_page": notification.link_page,
            }
            for notification in notifications.list_notifications(session, user.id)
        ]
        unread = notifications.unread_count(session, user.id)

    header_left, header_right = st.columns([2, 1])
    with header_left:
        ui.page_header(
            t("client.notifications.title", lang),
            t("client.notifications.subtitle", lang),
            eyebrow=f"{unread} {t('common.unread', lang)}",
        )
    with header_right:
        st.write("")
        if st.button(t("client.notifications.mark_all", lang), width="stretch", key="mark_all"):
            with database.session() as session:
                notifications.mark_all_read(session, user.id)
            st.rerun()

    if not items:
        ui.empty_state(t("client.notifications.empty", lang), t("common.no_data", lang), icon="bell")
        return

    for item in items:
        css = "wafa-notification unread" if not item["is_read"] else "wafa-notification"
        dot = '<span class="dot"></span>' if not item["is_read"] else ""
        st.markdown(
            f"""
<div class="{css}">
  {dot}
  <div style="flex:1">
    <div class="wafa-row" style="align-items:flex-start">
      <strong style="font-size:.88rem">{esc(item["title"])}</strong>
      <span class="wafa-small">{esc(format_datetime(item["created_at"], lang))}</span>
    </div>
    <div class="wafa-muted" style="margin-top:.25rem;line-height:1.55">{esc(item["message"])}</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns([1, 4])
        with c1:
            if not item["is_read"] and st.button(t("common.read", lang), key=f"read_{item['id']}"):
                with database.session() as session:
                    notifications.mark_read(session, user.id, item["id"])
                st.rerun()
        with c2:
            if item["link_page"] and st.button(t("client.notifications.open", lang), key=f"open_{item['id']}"):
                if not item["is_read"]:
                    with database.session() as session:
                        notifications.mark_read(session, user.id, item["id"])
                goto(item["link_page"])


# ---------------------------------------------------------------------------
# Profil & paramètres
# ---------------------------------------------------------------------------


def render_profile(user: SessionUser) -> None:
    lang = current_lang()
    ui.page_header(
        t("client.profile.title", lang), t("client.profile.subtitle", lang), eyebrow=t("nav.client.profile", lang)
    )
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown(
            f"""
<div class="wafa-card navy" style="text-align:center">
  <div class="wafa-avatar" style="width:70px;height:70px;font-size:1.2rem;margin:0 auto .7rem;border-radius:20px">{esc(user.initials)}</div>
  <div style="font-weight:800;font-size:1.15rem">{esc(user.full_name)}</div>
  <div class="wafa-small" style="color:#C9DDF2">{esc(user.phone)}</div>
  <div class="wafa-pill-row" style="justify-content:center;margin-top:.7rem">
    {ui.badge(t("role.CLIENT", lang), "navy")}
    {ui.badge(f"{user.city} · {user.neighborhood}", "navy")}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.write("")
        ui.info_banner(
            t("client.profile.phone_locked", lang),
            t("client.settings.security_hint", lang),
            tone="blue",
            icon="lock",
        )
    with right:
        with st.form("client_profile_form"):
            c1, c2 = st.columns(2)
            with c1:
                first_name = st.text_input(t("common.first_name", lang), value=user.first_name)
            with c2:
                last_name = st.text_input(t("common.last_name", lang), value=user.last_name)
            phone = st.text_input(t("common.phone", lang), value=user.phone, disabled=True)
            email = st.text_input(t("common.email", lang), value=user.email or "")
            c1, c2 = st.columns(2)
            with c1:
                city = st.selectbox(
                    t("common.city", lang),
                    merchants.MOROCCAN_CITIES,
                    index=merchants.MOROCCAN_CITIES.index(user.city) if user.city in merchants.MOROCCAN_CITIES else 0,
                )
            with c2:
                neighborhood = st.selectbox(
                    t("common.neighborhood", lang),
                    merchants.AGADIR_NEIGHBORHOODS,
                    index=merchants.AGADIR_NEIGHBORHOODS.index(user.neighborhood)
                    if user.neighborhood in merchants.AGADIR_NEIGHBORHOODS
                    else 0,
                )
            submitted = st.form_submit_button(t("common.save", lang), type="primary", width="stretch")
        if submitted:
            try:
                from ..services import auth

                with database.session() as session:
                    auth.update_client_profile(
                        session,
                        user.id,
                        first_name=first_name,
                        last_name=last_name,
                        email=email or None,
                        city=city,
                        neighborhood=neighborhood,
                    )
            except Exception as error:
                ui.show_error(error, lang)
            else:
                flash(t("client.profile.saved", lang))
                st.rerun()
        st.caption(f"{t('client.profile.member', lang)} · {format_date(user.created_at, lang)} · {phone}")


def render_settings(user: SessionUser) -> None:
    lang = current_lang()
    ui.page_header(
        t("client.settings.title", lang), t("client.settings.subtitle", lang), eyebrow=t("nav.client.settings", lang)
    )
    left, right = st.columns([1, 1], gap="large")
    with left:
        ui.section_title(t("client.settings.language", lang), t("client.settings.language_hint", lang))
        labels = {"fr": "Français", "ar": "العربية"}
        current = current_lang()
        selected_label = st.radio(
            t("common.language", lang),
            list(labels.values()),
            index=list(labels.keys()).index(current),
            key="settings_language",
        )
        selected = next((code for code, label in labels.items() if label == selected_label), current)
        if selected != current:
            from .state import set_language

            set_language(selected, user.id)
            flash(t("client.settings.saved", lang))
            st.rerun()

        st.write("")
        ui.section_title(t("client.settings.notifications", lang), t("client.settings.notifications_hint", lang))
        st.toggle(t("common.notifications", lang), value=True, disabled=True)
        st.caption(t("client.settings.coming_soon", lang))
    with right:
        ui.section_title(t("client.settings.security", lang), t("client.settings.security_hint", lang))
        st.markdown(
            f"""
<div class="wafa-card">
  <div class="wafa-line"><span>{esc(t("common.phone", lang))}</span><strong>{esc(user.phone)}</strong></div>
  <div class="wafa-line"><span>{esc(t("common.role", lang))}</span><strong>{esc(t("role.CLIENT", lang))}</strong></div>
  <div class="wafa-line"><span>{esc(t("common.member_since", lang))}</span><strong>{esc(format_date(user.created_at, lang))}</strong></div>
  <div class="wafa-line"><span>{esc(t("common.status", lang))}</span><strong>{esc(t("common.active", lang))}</strong></div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.write("")
        ui.info_banner(
            t("help.security_title", lang),
            t("help.security_text", lang),
            tone="green",
            icon="shield",
        )
    ui.legal_note(lang)


def render_help(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    ui.page_header(t("help.title", lang), t("help.subtitle", lang), eyebrow=t("common.help", lang))
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        ui.section_title(t("help.faq_title", lang))
        for index in range(1, 5):
            with st.expander(t(f"help.q{index}", lang)):
                st.write(t(f"help.a{index}", lang))
    with right:
        ui.info_banner(t("help.security_title", lang), t("help.security_text", lang), tone="green", icon="shield")
        st.write("")
        ui.info_banner(t("help.privacy_title", lang), t("help.privacy_text", lang), tone="blue", icon="lock")
        st.write("")
        ui.info_banner(t("help.payments_title", lang), t("help.payments_text", lang), tone="gold", icon="card")
    st.write("")
    ui.section_title(t("help.cndp_title", lang))
    st.write(t("help.cndp_text", lang))
    st.write("")
    ui.section_title(t("help.legal_title", lang))
    st.write(t("help.legal_text", lang))
    ui.legal_note(lang)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

PAGES: dict[str, Callable[[SessionUser], None]] = {
    "client.dashboard": render_dashboard,
    "client.card": render_card,
    "client.points": render_points,
    "client.rewards": render_rewards,
    "client.reward_detail": render_reward_detail,
    "client.reward_confirm": render_reward_confirm,
    "client.reward_success": render_reward_success,
    "client.my_rewards": render_my_rewards,
    "client.promotions": render_promotions,
    "client.promotion_detail": render_promotion_detail,
    "client.merchants": render_merchants,
    "client.merchant_detail": render_merchant_detail,
    "client.gift_cards": render_gift_cards,
    "client.gift_create": render_gift_create,
    "client.gift_confirm": render_gift_confirm,
    "client.gift_success": render_gift_success,
    "client.notifications": render_notifications,
    "client.profile": render_profile,
    "client.settings": render_settings,
    "client.help": render_help,
}


def render(page: str, user: SessionUser) -> None:
    handler = PAGES.get(page)
    if not handler:
        ui.empty_state(t("common.no_data", current_lang()), t("errors.not_found", current_lang()))
        return
    handler(user)
