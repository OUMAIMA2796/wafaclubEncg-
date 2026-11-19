"""Pages de l'espace commerçant WafaClub."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from datetime import datetime, time, timedelta
from decimal import Decimal

import streamlit as st
from sqlalchemy import select

from ..db import database
from ..i18n import format_date, format_datetime, format_mad, format_points, reward_type_key, t
from ..models import RewardType, TransactionType, User, UserRole
from ..qrcodes import decode_qr_image
from ..services import giftcards, loyalty, merchants, notifications, promotions, rewards, stats
from . import components as ui
from .icons import esc, icon_svg
from .state import SS, SessionUser, context, current_lang, flash, goto

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _merchant_id() -> int | None:
    return SS.get("merchant_id")


def _require_merchant_id(lang: str) -> int | None:
    merchant_id = _merchant_id()
    if not merchant_id:
        ui.empty_state(t("merchant.dashboard.title", lang), t("errors.merchant_not_found", lang), icon="store")
        return None
    return int(merchant_id)


def _client_snapshot(session, client_id: int) -> dict:
    client = session.get(User, client_id)
    if not client:
        return {}
    account = loyalty.get_account(session, client.id)
    return {
        "id": client.id,
        "name": client.full_name,
        "phone": client.phone,
        "city": client.city,
        "neighborhood": client.neighborhood,
        "balance": account.total_points,
    }


def _reset_target() -> None:
    SS["target_client_id"] = None


def _merchant_snapshot(session, merchant_id: int) -> dict:
    merchant = merchants.get_merchant(session, merchant_id)
    return {
        "id": merchant.id,
        "name": merchant.business_name,
        "description": merchant.description,
        "phone": merchant.phone,
        "address": merchant.address,
        "city": merchant.city,
        "neighborhood": merchant.neighborhood,
        "category": merchant.category,
        "rule": merchant.points_per_amount,
        "active": merchant.is_active,
    }


def _tx_snapshot(transaction) -> dict:
    return {
        "id": transaction.id,
        "created_at": transaction.created_at,
        "type": transaction.type,
        "points": transaction.points,
        "amount": transaction.purchase_amount,
        "description": transaction.description,
        "balance_after": transaction.balance_after,
        "client": transaction.user.full_name if transaction.user else "—",
    }


def _type_options(lang: str) -> dict[str, TransactionType | None]:
    return {
        t("common.all", lang): None,
        **{t(f"transaction.{member.value}", lang): member for member in TransactionType},
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def render_dashboard(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    with database.session() as session:
        data = stats.merchant_dashboard(session, merchant_id, days=14)
        merchant = data.get("merchant")
        if merchant:
            merchant_data = {
                "name": merchant.business_name,
                "city": merchant.city,
                "category": merchant.category,
                "rule": merchant.points_per_amount,
                "active": merchant.is_active,
            }
        else:
            merchant_data = {"name": "", "city": "", "category": "", "rule": Decimal("10"), "active": False}
        series = data.get("series", [])
        recent = data.get("recent", [])
        top_clients = data.get("top_clients", [])

    ui.page_header(
        t("merchant.dashboard.title", lang),
        t("merchant.dashboard.subtitle", lang, business=merchant_data["name"]),
        eyebrow=f"{merchant_data['category']} · {merchant_data['city']}",
    )
    if not merchant_data["active"]:
        ui.info_banner(
            t("common.inactive", lang),
            t("errors.merchant_inactive", lang),
            tone="gold",
            icon="shield",
        )
        st.write("")

    cols = st.columns(4, gap="medium")
    with cols[0]:
        ui.stat_card(
            t("merchant.dashboard.clients", lang),
            str(data.get("clients", 0)),
            hint=f"+{data.get('new_clients', 0)} {t('merchant.dashboard.new_clients', lang)}",
            icon="users",
            tone="blue",
        )
    with cols[1]:
        ui.stat_card(
            t("merchant.dashboard.points", lang),
            format_points(data.get("points_distributed", 0), lang),
            hint=f"{data.get('purchases', 0)} {t('merchant.dashboard.purchases', lang)}",
            icon="star",
            tone="gold",
        )
    with cols[2]:
        ui.stat_card(
            t("merchant.dashboard.rewards_used", lang),
            str(data.get("rewards_used", 0)),
            hint=t("merchant.rewards.title", lang),
            icon="gift",
            tone="green",
        )
    with cols[3]:
        ui.stat_card(
            t("merchant.dashboard.gift_cards", lang),
            str(data.get("gift_cards", 0)),
            hint=t("merchant.gift.subtitle", lang),
            icon="wallet",
            tone="navy",
        )

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        if st.button(f"➕ {t('merchant.dashboard.add_points', lang)}", type="primary", width="stretch", key="dash_add"):
            _reset_target()
            goto("merchant.add_points")
    with c2:
        if st.button(f"🎫 {t('merchant.validate.title', lang)}", width="stretch", key="dash_validate"):
            goto("merchant.validate_reward")

    st.write("")
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        ui.section_title(t("merchant.dashboard.loyalty_chart", lang))
        chart_rows = [
            {
                "Date": format_date(point["date"], lang),
                "Points": point["points"],
            }
            for point in series
        ]
        if chart_rows:
            st.bar_chart(chart_rows, x="Date", y="Points", color="#D99A2B", height=230)
        else:
            st.caption(t("common.no_data", lang))

        st.write("")
        ui.section_title(t("merchant.dashboard.activity_title", lang))
        if recent:
            for item in recent:
                positive = item["points"] > 0
                color = "#12805C" if positive else "#B5413A"
                st.markdown(
                    f"""
<div class="wafa-line">
  <div style="flex:1">
    <div><strong style="font-size:.84rem">{esc(item["client"])}</strong></div>
    <div class="wafa-small">{esc(item["description"])}</div>
  </div>
  <div style="text-align:right">
    <div style="font-weight:800;color:{color}">{"+" if positive else ""}{item["points"]}</div>
    <div class="wafa-small">{esc(format_datetime(item["created_at"], lang))}</div>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )
        else:
            st.caption(t("merchant.dashboard.no_activity", lang))

    with right:
        ui.section_title(t("merchant.dashboard.top_clients", lang))
        if top_clients:
            for client in top_clients:
                st.markdown(
                    f"""
<div class="wafa-card tight" style="margin-bottom:.55rem">
  <div class="wafa-row">
    <div>
      <div style="font-weight:750;font-size:.85rem">{esc(client["name"])}</div>
      <div class="wafa-small">{esc(client["phone"])} · {esc(client["city"])}</div>
    </div>
    <div style="text-align:right">
      <div style="font-weight:800;color:#12805C">+{client["earned_here"]}</div>
      <div class="wafa-small">{client["purchases"]} {esc(t("merchant.dashboard.purchases", lang))}</div>
    </div>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )
        else:
            ui.empty_state(t("common.no_data", lang), t("merchant.dashboard.no_activity", lang), icon="users")
        if st.button(t("merchant.dashboard.see_clients", lang), width="stretch", key="dash_clients"):
            goto("merchant.clients")
        st.markdown(
            f"""
<div class="wafa-card gold" style="margin-top:.8rem">
  <div class="wafa-small">{esc(t("merchant.stats.rule", lang))}</div>
  <div style="font-weight:800;font-size:1.15rem">{esc(t("client.merchants.rule", lang, points=format_mad(merchant_data["rule"], lang)))}</div>
  <div class="wafa-small" style="margin-top:.35rem">{esc(t("merchant.stats.category", lang))} · {esc(merchant_data["category"])}</div>
</div>
""",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Ajout de points
# ---------------------------------------------------------------------------


def render_add_points(user: SessionUser) -> None:
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    with database.session() as session:
        merchant = _merchant_snapshot(session, merchant_id)
        demo_clients = [
            _client_snapshot(session, client.id)
            for client in session.scalars(
                select(User).where(User.role == UserRole.CLIENT, User.is_active.is_(True)).order_by(User.first_name)
            )
        ]

    ui.page_header(
        t("merchant.add_points.title", lang),
        t("merchant.add_points.subtitle", lang),
        eyebrow=t("nav.merchant.add_points", lang),
    )
    ui.info_banner(
        t("merchant.add_points.rule", lang),
        t("client.merchants.rule", lang, points=format_mad(merchant["rule"], lang)),
        tone="gold",
        icon="star",
    )
    st.write("")

    purchase = SS.get("last_purchase")
    if purchase:
        _render_purchase_success(purchase, lang)
        return

    target_id = SS.get("target_client_id")
    if target_id:
        try:
            with database.session() as session:
                client = _client_snapshot(session, int(target_id))
        except Exception as error:
            ui.show_error(error, lang)
            _reset_target()
            return
        _render_purchase_form(user, merchant, client, lang)
        return

    tab_phone, tab_qr, tab_demo = st.tabs(
        [
            f"📱 {t('merchant.add_points.tab_phone', lang)}",
            f"📷 {t('merchant.add_points.tab_qr', lang)}",
            f"🧪 {t('merchant.add_points.tab_demo', lang)}",
        ]
    )
    with tab_phone:
        st.caption(t("merchant.add_points.phone_label", lang))
        with st.form("find_by_phone"):
            phone = st.text_input(t("common.phone", lang), placeholder="+212 6...")
            submitted = st.form_submit_button(t("merchant.add_points.search", lang), type="primary", width="stretch")
        if submitted:
            try:
                with database.session() as session:
                    client = loyalty.find_client(session, phone)
                    SS["target_client_id"] = client.id
                st.rerun()
            except Exception as error:
                ui.show_error(error, lang)

    with tab_qr:
        st.caption(t("merchant.add_points.qr_manual", lang))
        uploaded = st.file_uploader(
            t("merchant.add_points.qr_upload", lang), type=["png", "jpg", "jpeg", "webp"], key="qr_upload"
        )
        manual = st.text_input(t("merchant.add_points.qr_manual", lang), placeholder="WAFACLUB:QR:...")
        c1, c2 = st.columns(2)
        with c1:
            if st.button(t("merchant.add_points.qr_decode", lang), type="primary", width="stretch"):
                payload = None
                if uploaded is not None:
                    payload = decode_qr_image(uploaded.getvalue())
                if not payload:
                    payload = manual.strip() or None
                if not payload:
                    st.error(t("merchant.add_points.qr_failed", lang))
                else:
                    try:
                        with database.session() as session:
                            client = loyalty.find_client(session, payload)
                            SS["target_client_id"] = client.id
                        st.rerun()
                    except Exception as error:
                        ui.show_error(error, lang)
        with c2:
            st.caption(t("merchant.add_points.qr_camera", lang))

    with tab_demo:
        st.caption(t("merchant.add_points.demo_select", lang))
        if demo_clients:
            labels = {
                client["id"]: f"{client['name']} · {client['phone']} · {client['balance']} pts"
                for client in demo_clients
            }
            selected = st.selectbox(
                t("merchant.add_points.choose_client", lang),
                list(labels.keys()),
                format_func=lambda value: labels[value],
                key="demo_client",
            )
            if st.button(t("merchant.add_points.client_found", lang), type="primary", width="stretch"):
                SS["target_client_id"] = selected
                st.rerun()
        else:
            st.caption(t("common.no_data", lang))


def _render_purchase_form(user: SessionUser, merchant: dict, client: dict, lang: str) -> None:
    ui.section_title(t("merchant.add_points.client_found", lang), t("merchant.add_points.amount_hint", lang))
    left, right = st.columns([1, 1.2], gap="large")
    with left:
        st.markdown(
            f"""
<div class="wafa-card">
  <div class="wafa-row">
    <div style="display:flex;gap:.7rem;align-items:center">
      <div class="wafa-avatar">{esc(client["name"][:2].upper())}</div>
      <div><div style="font-weight:800">{esc(client["name"])}</div>
      <div class="wafa-small">{esc(client["phone"])}</div></div>
    </div>
    {ui.badge(t("common.client", lang), "blue")}
  </div>
  <div class="wafa-line" style="margin-top:.6rem"><span>{esc(t("client.points.balance", lang))}</span><strong>{client["balance"]} {esc(t("common.points", lang))}</strong></div>
  <div class="wafa-line"><span>{esc(t("common.city", lang))}</span><strong>{esc(client["city"])}</strong></div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button(t("merchant.add_points.change_client", lang), width="stretch", key="change_client"):
            _reset_target()
            st.rerun()

    with right:
        with st.form("add_points_form"):
            amount = st.number_input(
                t("merchant.add_points.purchase_amount", lang),
                min_value=1.0,
                max_value=100000.0,
                value=100.0,
                step=10.0,
                help=t("merchant.add_points.amount_hint", lang),
            )
            try:
                preview = loyalty.calculate_points(amount, merchant["rule"])
            except Exception:
                preview = 0
            st.markdown(
                f"""
<div class="wafa-card green tight">
  <div class="wafa-row"><span class="wafa-small">{esc(t("merchant.add_points.points_preview", lang))}</span>
  <strong style="font-size:1.25rem">+{preview} {esc(t("common.points", lang))}</strong></div>
</div>
""",
                unsafe_allow_html=True,
            )
            submitted = st.form_submit_button(t("merchant.add_points.submit", lang), type="primary", width="stretch")
        if submitted:
            if preview <= 0:
                st.error(t("merchant.add_points.no_points", lang))
            else:
                try:
                    with database.session() as session:
                        transaction = loyalty.add_purchase(
                            session,
                            client_id=client["id"],
                            merchant_id=merchant["id"],
                            amount=amount,
                            actor_id=user.id,
                        )
                        SS["last_purchase"] = {
                            "client": client["name"],
                            "phone": client["phone"],
                            "amount": format_mad(transaction.purchase_amount, lang),
                            "points": transaction.points,
                            "balance": transaction.balance_after,
                        }
                        SS["target_client_id"] = None
                except Exception as error:
                    ui.show_error(error, lang)
                else:
                    st.rerun()


def _render_purchase_success(purchase: dict, lang: str) -> None:
    st.markdown(
        f"""
<div class="wafa-card green" style="text-align:center;padding:2rem">
  <div class="wafa-icon green" style="margin:0 auto .8rem;width:64px;height:64px;border-radius:20px">{icon_svg("check-circle", 32)}</div>
  <div style="font-weight:800;font-size:1.25rem">{esc(t("merchant.add_points.success_title", lang))}</div>
  <div class="wafa-muted" style="margin:.35rem 0 1rem">{esc(t("merchant.add_points.confirm_text", lang, points=purchase["points"], name=purchase["client"]))}</div>
  <div style="font-size:2rem;font-weight:800;color:#12805C">+{purchase["points"]} <small style="font-size:.8rem">{esc(t("common.points", lang))}</small></div>
  <div class="wafa-line" style="max-width:420px;margin:.8rem auto 0"><span>{esc(t("merchant.add_points.purchase_amount", lang))}</span><strong>{esc(purchase["amount"])}</strong></div>
  <div class="wafa-line" style="max-width:420px;margin:0 auto"><span>{esc(t("merchant.add_points.new_balance", lang))}</span><strong>{purchase["balance"]} {esc(t("common.points", lang))}</strong></div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.caption(t("merchant.add_points.journal_notice", lang))
    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("merchant.add_points.change_client", lang), type="primary", width="stretch", key="success_new"):
            SS["last_purchase"] = None
            _reset_target()
            st.rerun()
    with c2:
        if st.button(t("common.see_all", lang), width="stretch", key="success_tx"):
            SS["last_purchase"] = None
            goto("merchant.transactions")


# ---------------------------------------------------------------------------
# Validation des récompenses
# ---------------------------------------------------------------------------


def render_validate_reward(user: SessionUser) -> None:
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    ui.page_header(
        t("merchant.validate.title", lang),
        t("merchant.validate.subtitle", lang),
        eyebrow=t("nav.merchant.validate_reward", lang),
    )

    validation = SS.get("last_validation")
    if validation:
        st.markdown(
            f"""
<div class="wafa-card green" style="text-align:center">
  <div class="wafa-icon green" style="margin:0 auto .7rem;width:60px;height:60px">{icon_svg("check-circle", 30)}</div>
  <div style="font-weight:800;font-size:1.15rem">{esc(t("merchant.validate.success_title", lang))}</div>
  <div class="wafa-muted" style="margin:.4rem 0 1rem">{esc(t("merchant.validate.success_text", lang, reward=validation["reward"], client=validation["client"]))}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button(t("merchant.validate.other", lang), type="primary", width="stretch", key="validate_other"):
            SS["last_validation"] = None
            st.rerun()
        return

    left, right = st.columns([1.3, 1], gap="large")
    with left:
        with st.form("validate_reward_form"):
            code = st.text_input(t("merchant.validate.code_label", lang), placeholder="RWD-XXXX-XXXX")
            submitted = st.form_submit_button(t("merchant.validate.submit", lang), type="primary", width="stretch")
        if submitted:
            try:
                with database.session() as session:
                    redemption = rewards.validate_redemption(
                        session, code=code, merchant_id=merchant_id, actor_id=user.id
                    )
                    SS["last_validation"] = {
                        "reward": redemption.reward.title,
                        "client": redemption.user.full_name,
                        "code": redemption.code,
                    }
            except Exception as error:
                ui.show_error(error, lang)
            else:
                st.rerun()
        st.caption(t("merchant.validate.scope_hint", lang))
    with right:
        ui.info_banner(
            t("merchant.validate.title", lang),
            t("client.rewards.code_hint", lang),
            tone="blue",
            icon="qr",
        )
        st.write("")
        ui.info_banner(
            t("merchant.validate.empty", lang),
            t("merchant.validate.scope_hint", lang),
            tone="gold",
            icon="ticket",
        )


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


def render_clients(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    search = st.text_input(t("merchant.clients.search", lang), placeholder=t("common.name", lang), key="clients_search")
    with database.session() as session:
        clients = stats.merchant_clients(session, merchant_id, search=search or None)
    ui.page_header(
        t("merchant.clients.title", lang), t("merchant.clients.subtitle", lang), eyebrow=t("common.clients", lang)
    )
    if not clients:
        ui.empty_state(t("merchant.clients.empty", lang), t("common.no_data", lang), icon="users")
        return
    st.caption(f"{t('merchant.clients.total', lang)} · {len(clients)}")
    rows = [
        {
            t("common.name", lang): client["name"],
            t("common.phone", lang): client["phone"],
            t("common.city", lang): f"{client['city']} · {client['neighborhood']}",
            t("merchant.clients.balance", lang): client["balance"],
            t("merchant.clients.earned_here", lang): client["earned_here"],
            t("merchant.clients.purchases", lang): client["purchases"],
            t("merchant.clients.last_visit", lang): format_date(client["last_visit"], lang),
        }
        for client in clients
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
    st.write("")
    cols = st.columns(3, gap="medium")
    for index, client in enumerate(clients[:6]):
        with cols[index % 3]:
            st.markdown(
                f"""
<div class="wafa-card tight">
  <div style="font-weight:800;font-size:.88rem">{esc(client["name"])}</div>
  <div class="wafa-small">{esc(client["phone"])}</div>
  <div class="wafa-row" style="margin-top:.5rem">
    <span class="wafa-small">{esc(t("merchant.clients.earned_here", lang))}</span>
    <strong style="color:#12805C">+{client["earned_here"]}</strong>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


def render_transactions(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    ui.page_header(
        t("merchant.transactions.title", lang),
        t("merchant.transactions.subtitle", lang),
        eyebrow=t("common.transactions", lang),
    )
    options = _type_options(lang)
    selected_label = st.selectbox(
        t("merchant.transactions.filter_type", lang), list(options.keys()), key="tx_type_filter"
    )
    with database.session() as session:
        transactions = stats.merchant_transactions(session, merchant_id, type_filter=options[selected_label], limit=500)
        rows = [_tx_snapshot(transaction) for transaction in transactions]
    if not rows:
        ui.empty_state(t("merchant.transactions.empty", lang), t("common.no_data", lang), icon="receipt")
        return
    table = [
        {
            t("common.date", lang): format_datetime(row["created_at"], lang),
            t("merchant.transactions.client", lang): row["client"],
            t("common.type", lang): t(f"transaction.{row['type'].value}", lang),
            t("common.details", lang): row["description"],
            t("common.amount", lang): str(row["amount"]) if row["amount"] is not None else "—",
            t("common.points", lang): row["points"],
            t("merchant.transactions.balance_after", lang): row["balance_after"],
        }
        for row in rows
    ]
    st.dataframe(table, hide_index=True, width="stretch")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(table[0].keys()))
    writer.writeheader()
    writer.writerows(table)
    st.download_button(
        f"⬇️ {t('merchant.transactions.export', lang)}",
        data=buffer.getvalue().encode("utf-8-sig"),
        file_name="wafaclub-transactions.csv",
        mime="text/csv",
        key="export_tx",
    )


# ---------------------------------------------------------------------------
# Récompenses
# ---------------------------------------------------------------------------


def render_rewards(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    header_left, header_right = st.columns([2, 1])
    with header_left:
        ui.page_header(
            t("merchant.rewards.title", lang), t("merchant.rewards.subtitle", lang), eyebrow=t("common.rewards", lang)
        )
    with header_right:
        st.write("")
        if st.button(f"➕ {t('merchant.rewards.create', lang)}", type="primary", width="stretch", key="new_reward"):
            goto("merchant.reward_form", reward_id=None)
    with database.session() as session:
        reward_rows = [
            {
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
                "is_active": reward.is_active,
            }
            for reward in rewards.list_merchant_rewards(session, merchant_id)
        ]
    if not reward_rows:
        ui.empty_state(t("merchant.rewards.empty", lang), t("merchant.rewards.form_subtitle", lang), icon="gift")
        return
    for reward in reward_rows:
        left, right = st.columns([1.6, 1], gap="medium")
        with left:
            st.markdown(
                f"""
<div class="wafa-card">
  <div class="wafa-row">
    <div style="display:flex;gap:.7rem;align-items:center">
      <div class="wafa-reward-icon">{esc(reward["icon"])}</div>
      <div><div style="font-weight:800">{esc(reward["title"])}</div>
      <div class="wafa-small">{esc(t(reward_type_key(reward["type"]), lang))} · {reward["points_cost"]} {esc(t("common.points", lang))}</div></div>
    </div>
    {ui.badge(t("common.active", lang) if reward["is_active"] else t("common.inactive", lang), "green" if reward["is_active"] else "gray")}
  </div>
  <div class="wafa-line" style="margin-top:.5rem"><span>{esc(t("merchant.rewards.stock", lang))}</span><strong>{reward["stock"] if reward["stock"] is not None else "∞"}</strong></div>
  <div class="wafa-line"><span>{esc(t("merchant.rewards.ends", lang))}</span><strong>{esc(format_date(reward["expires_at"], lang))}</strong></div>
  <div class="wafa-line"><span>{esc(t("merchant.rewards.value", lang))}</span><strong>{esc(format_mad(reward["value"], lang)) if reward["value"] is not None else "—"}</strong></div>
</div>
""",
                unsafe_allow_html=True,
            )
        with right:
            if st.button(t("merchant.rewards.edit", lang), width="stretch", key=f"edit_reward_{reward['id']}"):
                goto("merchant.reward_form", reward_id=reward["id"])
            if st.button(
                t("merchant.rewards.deactivate", lang) if reward["is_active"] else t("merchant.rewards.activate", lang),
                width="stretch",
                key=f"toggle_reward_{reward['id']}",
            ):
                try:
                    with database.session() as session:
                        rewards.set_reward_active(
                            session,
                            reward_id=reward["id"],
                            actor_id=user.id,
                            active=not reward["is_active"],
                        )
                except Exception as error:
                    ui.show_error(error, lang)
                else:
                    flash(t("merchant.rewards.toggled", lang))
                    st.rerun()
        st.write("")


def render_reward_form(user: SessionUser) -> None:
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    reward_id = context("reward_id")
    editing = reward_id is not None
    existing = None
    if editing:
        try:
            with database.session() as session:
                reward = rewards.get_reward(session, int(reward_id))
                existing = {
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
                    "is_active": reward.is_active,
                }
        except Exception as error:
            ui.show_error(error, lang)
            return
    ui.page_header(
        t("merchant.rewards.form_edit_title" if editing else "merchant.rewards.form_create_title", lang),
        t("merchant.rewards.form_subtitle", lang),
        eyebrow=t("common.rewards", lang),
    )
    type_labels = {t(f"reward_type.{member.value}", lang): member for member in RewardType}
    current_type_label = t(f"reward_type.{existing['type'].value}", lang) if existing else next(iter(type_labels))
    with st.form("reward_form"):
        c1, c2 = st.columns([2, 1])
        with c1:
            title = st.text_input(t("common.title", lang), value=existing["title"] if existing else "")
            description = st.text_area(
                t("common.details", lang), value=existing["description"] if existing else "", height=90
            )
        with c2:
            icon = st.text_input(t("merchant.rewards.icon", lang), value=existing["icon"] if existing else "🎁")
            type_label = st.selectbox(
                t("common.type", lang),
                list(type_labels.keys()),
                index=list(type_labels.keys()).index(current_type_label),
            )
        c1, c2, c3 = st.columns(3)
        with c1:
            points_cost = st.number_input(
                t("merchant.rewards.points_cost", lang),
                min_value=1,
                max_value=100000,
                value=int(existing["points_cost"]) if existing else 100,
                step=10,
            )
        with c2:
            value = st.number_input(
                t("merchant.rewards.value", lang),
                min_value=0.0,
                max_value=100000.0,
                value=float(existing["value"]) if existing and existing["value"] is not None else 0.0,
                step=10.0,
            )
        with c3:
            stock_unlimited = st.checkbox(
                t("client.rewards.unlimited", lang),
                value=existing["stock"] is None if existing else True,
            )
            stock = st.number_input(
                t("merchant.rewards.stock", lang),
                min_value=0,
                max_value=100000,
                value=int(existing["stock"]) if existing and existing["stock"] is not None else 50,
                step=1,
                disabled=stock_unlimited,
            )
        c1, c2 = st.columns(2)
        with c1:
            starts = st.date_input(
                t("merchant.rewards.starts", lang),
                value=existing["starts_at"].date() if existing else datetime.now().date(),
            )
        with c2:
            expires = st.date_input(
                t("merchant.rewards.ends", lang),
                value=existing["expires_at"].date() if existing else datetime.now().date() + timedelta(days=365),
            )
        is_active = st.checkbox(
            t("common.active", lang), value=existing["is_active"] if existing else True, disabled=not editing
        )
        submitted = st.form_submit_button(t("common.save", lang), type="primary", width="stretch")
    if submitted:
        starts_at = datetime.combine(starts, time.min)
        expires_at = datetime.combine(expires, time(23, 59))
        payload = {
            "title": title,
            "description": description,
            "type": type_labels[type_label],
            "points_cost": int(points_cost),
            "value": Decimal(str(value)) if value > 0 else None,
            "icon": icon,
            "starts_at": starts_at,
            "expires_at": expires_at,
            "stock": None if stock_unlimited else int(stock),
        }
        try:
            with database.session() as session:
                if editing:
                    rewards.update_reward(
                        session,
                        reward_id=int(reward_id),
                        actor_id=user.id,
                        is_active=is_active,
                        **payload,
                    )
                else:
                    rewards.create_reward(session, merchant_id=merchant_id, actor_id=user.id, **payload)
        except Exception as error:
            ui.show_error(error, lang)
        else:
            flash(t("merchant.rewards.saved", lang))
            goto("merchant.rewards")
    if st.button(t("common.cancel", lang), width="stretch", key="cancel_reward_form"):
        goto("merchant.rewards")


def render_gift_cards(user: SessionUser) -> None:
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    ui.page_header(
        t("merchant.gift.title", lang), t("merchant.gift.subtitle", lang), eyebrow=t("nav.merchant.gift_cards", lang)
    )

    validation = SS.get("last_gift_validation")
    if validation:
        st.markdown(
            f"""
<div class="wafa-card green" style="text-align:center">
  <div class="wafa-icon green" style="margin:0 auto .7rem;width:60px;height:60px">{icon_svg("check-circle", 30)}</div>
  <div style="font-weight:800;font-size:1.15rem">{esc(t("merchant.gift.success_title", lang))}</div>
  <div class="wafa-muted" style="margin:.4rem 0 1rem">{esc(t("merchant.gift.success_text", lang, amount=validation["amount"], business=validation["business"]))}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button(t("merchant.gift.other", lang), type="primary", width="stretch", key="gift_other"):
            SS["last_gift_validation"] = None
            st.rerun()
        return

    verified = SS.get("verified_gift")
    if verified:
        left, right = st.columns([1.3, 1], gap="large")
        with left:
            st.markdown(
                f"""
<div class="wafa-card gold">
  <div class="wafa-row"><div class="wafa-reward-icon" style="width:60px;height:60px;font-size:1.8rem">🎁</div>
  <div style="text-align:right">{ui.status_badge(verified["status"], lang)}<br/>
  <span style="font-weight:800;font-size:1.35rem">{esc(verified["amount"])}</span></div></div>
  <div class="wafa-review" style="margin-top:.8rem">
    {ui.review_line(t("merchant.gift.scope", lang), verified["scope"])}
    {ui.review_line(t("merchant.gift.sender", lang), verified["sender"])}
    {ui.review_line(t("merchant.gift.expires", lang), verified["expires"])}
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
        with right:
            ui.code_box(verified["code"])
            st.caption(t("merchant.gift.simulated", lang))
            if st.button(
                t("merchant.gift.confirm", lang), type="primary", width="stretch", key="confirm_gift_merchant"
            ):
                try:
                    with database.session() as session:
                        card = giftcards.validate_gift_card(
                            session, code=verified["code"], merchant_id=merchant_id, actor_id=user.id
                        )
                        SS["last_gift_validation"] = {
                            "amount": format_mad(card.amount, lang),
                            "business": card.redeemed_by_merchant.business_name if card.redeemed_by_merchant else "",
                            "code": card.code,
                        }
                        SS["verified_gift"] = None
                except Exception as error:
                    ui.show_error(error, lang)
                else:
                    st.rerun()
            if st.button(t("common.cancel", lang), width="stretch", key="cancel_gift_merchant"):
                SS["verified_gift"] = None
                st.rerun()
        return

    left, right = st.columns([1.3, 1], gap="large")
    with left:
        with st.form("verify_gift_form"):
            code = st.text_input(t("merchant.gift.code_label", lang), placeholder="WFC-XXXX-XXXX-XXXX")
            submitted = st.form_submit_button(t("merchant.gift.verify", lang), type="primary", width="stretch")
        if submitted:
            try:
                with database.session() as session:
                    card = giftcards.verify_gift_card(session, code=code, merchant_id=merchant_id)
                    SS["verified_gift"] = {
                        "code": card.code,
                        "amount": format_mad(card.amount, lang),
                        "status": card.status,
                        "scope": card.merchant.business_name if card.merchant else t("client.gift.scope_network", lang),
                        "sender": card.sender.full_name,
                        "expires": format_date(card.expires_at, lang),
                    }
            except Exception as error:
                ui.show_error(error, lang)
            else:
                st.rerun()
    with right:
        ui.info_banner(
            t("merchant.gift.verify_title", lang),
            t("merchant.gift.simulated", lang),
            tone="gold",
            icon="gift",
        )
        st.write("")
        if st.button(t("nav.merchant.dashboard", lang), width="stretch", key="gift_empty_action"):
            goto("merchant.dashboard")


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------


def render_promotions(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    header_left, header_right = st.columns([2, 1])
    with header_left:
        ui.page_header(
            t("merchant.promotions.title", lang),
            t("merchant.promotions.subtitle", lang),
            eyebrow=t("common.promotions", lang),
        )
    with header_right:
        st.write("")
        if st.button(f"➕ {t('merchant.promotions.create', lang)}", type="primary", width="stretch", key="new_promo"):
            goto("merchant.promotion_form", promotion_id=None)
    with database.session() as session:
        rows = [
            {
                "id": promotion.id,
                "title": promotion.title,
                "description": promotion.description,
                "icon": promotion.icon,
                "city": promotion.city,
                "neighborhood": promotion.neighborhood,
                "starts_at": promotion.starts_at,
                "expires_at": promotion.expires_at,
                "is_active": promotion.is_active,
            }
            for promotion in promotions.list_merchant_promotions(session, merchant_id)
        ]
    if not rows:
        ui.empty_state(
            t("merchant.promotions.empty", lang), t("merchant.promotions.form_subtitle", lang), icon="map-pin"
        )
        return
    for promotion in rows:
        left, right = st.columns([1.6, 1], gap="medium")
        with left:
            st.markdown(
                f"""
<div class="wafa-card gold">
  <div class="wafa-row"><div style="display:flex;gap:.7rem;align-items:center">
    <div class="wafa-reward-icon">{esc(promotion["icon"])}</div>
    <div><div style="font-weight:800">{esc(promotion["title"])}</div>
    <div class="wafa-small">{esc(promotion["neighborhood"])} · {esc(promotion["city"])}</div></div>
  </div>{ui.badge(t("common.active", lang) if promotion["is_active"] else t("common.inactive", lang), "green" if promotion["is_active"] else "gray")}</div>
  <div class="wafa-muted" style="margin-top:.4rem">{esc(promotion["description"])}</div>
  <div class="wafa-line" style="margin-top:.4rem"><span>{esc(t("common.from", lang))}</span><strong>{esc(format_date(promotion["starts_at"], lang))}</strong></div>
  <div class="wafa-line"><span>{esc(t("client.promotions.expires", lang))}</span><strong>{esc(format_date(promotion["expires_at"], lang))}</strong></div>
</div>
""",
                unsafe_allow_html=True,
            )
        with right:
            if st.button(t("merchant.promotions.edit", lang), width="stretch", key=f"edit_promo_{promotion['id']}"):
                goto("merchant.promotion_form", promotion_id=promotion["id"])
            if st.button(
                t("merchant.promotions.deactivate", lang)
                if promotion["is_active"]
                else t("merchant.promotions.activate", lang),
                width="stretch",
                key=f"toggle_promo_{promotion['id']}",
            ):
                try:
                    with database.session() as session:
                        promotions.set_promotion_active(
                            session,
                            promotion_id=promotion["id"],
                            actor_id=user.id,
                            active=not promotion["is_active"],
                        )
                except Exception as error:
                    ui.show_error(error, lang)
                else:
                    flash(t("merchant.promotions.toggled", lang))
                    st.rerun()
        st.write("")


def render_promotion_form(user: SessionUser) -> None:
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    promotion_id = context("promotion_id")
    editing = promotion_id is not None
    existing = None
    with database.session() as session:
        merchant = _merchant_snapshot(session, merchant_id)
        if editing:
            try:
                promotion = promotions.get_promotion(session, int(promotion_id))
                existing = {
                    "title": promotion.title,
                    "description": promotion.description,
                    "icon": promotion.icon,
                    "city": promotion.city,
                    "neighborhood": promotion.neighborhood,
                    "starts_at": promotion.starts_at,
                    "expires_at": promotion.expires_at,
                    "is_active": promotion.is_active,
                }
            except Exception as error:
                ui.show_error(error, lang)
                return
    ui.page_header(
        t("merchant.promotions.form_edit_title" if editing else "merchant.promotions.form_create_title", lang),
        t("merchant.promotions.form_subtitle", lang),
        eyebrow=t("common.promotions", lang),
    )
    with st.form("promotion_form"):
        c1, c2 = st.columns([2, 1])
        with c1:
            title = st.text_input(t("common.title", lang), value=existing["title"] if existing else "")
            description = st.text_area(
                t("common.details", lang), value=existing["description"] if existing else "", height=90
            )
        with c2:
            icon = st.text_input(t("merchant.rewards.icon", lang), value=existing["icon"] if existing else "🏷️")
            city = st.selectbox(
                t("common.city", lang),
                merchants.MOROCCAN_CITIES,
                index=merchants.MOROCCAN_CITIES.index(existing["city"])
                if existing and existing["city"] in merchants.MOROCCAN_CITIES
                else merchants.MOROCCAN_CITIES.index(merchant["city"])
                if merchant["city"] in merchants.MOROCCAN_CITIES
                else 0,
            )
            neighborhood = st.selectbox(
                t("common.neighborhood", lang),
                merchants.AGADIR_NEIGHBORHOODS,
                index=merchants.AGADIR_NEIGHBORHOODS.index(
                    existing["neighborhood"] if existing else merchant["neighborhood"]
                )
                if (existing["neighborhood"] if existing else merchant["neighborhood"])
                in merchants.AGADIR_NEIGHBORHOODS
                else 0,
            )
        c1, c2 = st.columns(2)
        with c1:
            starts = st.date_input(
                t("merchant.rewards.starts", lang),
                value=existing["starts_at"].date() if existing else datetime.now().date(),
            )
        with c2:
            expires = st.date_input(
                t("merchant.rewards.ends", lang),
                value=existing["expires_at"].date() if existing else datetime.now().date() + timedelta(days=365),
            )
        is_active = st.checkbox(
            t("common.active", lang), value=existing["is_active"] if existing else True, disabled=not editing
        )
        submitted = st.form_submit_button(t("common.save", lang), type="primary", width="stretch")
    if submitted:
        payload = {
            "title": title,
            "description": description,
            "icon": icon,
            "city": city,
            "neighborhood": neighborhood,
            "starts_at": datetime.combine(starts, time.min),
            "expires_at": datetime.combine(expires, time(23, 59)),
        }
        try:
            with database.session() as session:
                if editing:
                    promotions.update_promotion(
                        session,
                        promotion_id=int(promotion_id),
                        actor_id=user.id,
                        is_active=is_active,
                        **payload,
                    )
                else:
                    promotions.create_promotion(session, merchant_id=merchant_id, actor_id=user.id, **payload)
        except Exception as error:
            ui.show_error(error, lang)
        else:
            flash(t("merchant.promotions.saved", lang))
            goto("merchant.promotions")
    if st.button(t("common.cancel", lang), width="stretch", key="cancel_promo_form"):
        goto("merchant.promotions")


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------


def render_stats(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    with database.session() as session:
        data = stats.merchant_dashboard(session, merchant_id, days=30)
        merchant = _merchant_snapshot(session, merchant_id)
    ui.page_header(
        t("merchant.stats.title", lang), t("merchant.stats.subtitle", lang), eyebrow=t("common.dashboard", lang)
    )
    cols = st.columns(3, gap="medium")
    with cols[0]:
        ui.stat_card(
            t("merchant.stats.city", lang), merchant["city"], hint=merchant["neighborhood"], icon="map-pin", tone="blue"
        )
    with cols[1]:
        ui.stat_card(t("merchant.stats.category", lang), merchant["category"], icon="store", tone="gold")
    with cols[2]:
        ui.stat_card(
            t("merchant.stats.rule", lang),
            format_mad(merchant["rule"], lang),
            hint=t("merchant.profile.rule_hint", lang),
            icon="star",
            tone="green",
        )
    st.write("")
    left, right = st.columns(2, gap="large")
    with left:
        ui.section_title(t("merchant.stats.loyalty_chart", lang))
        chart = [
            {"Date": format_date(point["date"], lang), "Points": point["points"]} for point in data.get("series", [])
        ]
        if chart:
            st.bar_chart(chart, x="Date", y="Points", color="#1E6FA8", height=260)
        else:
            st.caption(t("common.no_data", lang))
    with right:
        ui.section_title(t("merchant.stats.points_chart", lang))
        counts = [
            {"Date": format_date(point["date"], lang), "Transactions": point["count"]}
            for point in data.get("series", [])
        ]
        if counts:
            st.bar_chart(counts, x="Date", y="Transactions", color="#D99A2B", height=260)
        else:
            st.caption(t("common.no_data", lang))
    st.write("")
    ui.section_title(t("merchant.stats.top_clients", lang))
    top = data.get("top_clients", [])
    if top:
        st.dataframe(
            [
                {
                    t("common.name", lang): client["name"],
                    t("common.phone", lang): client["phone"],
                    t("client.points.balance", lang): client["balance"],
                    t("merchant.clients.earned_here", lang): client["earned_here"],
                    t("merchant.clients.purchases", lang): client["purchases"],
                }
                for client in top
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        ui.empty_state(t("common.no_data", lang), t("merchant.dashboard.no_activity", lang), icon="users")


# ---------------------------------------------------------------------------
# Profil, paramètres, notifications
# ---------------------------------------------------------------------------


def render_profile(user: SessionUser) -> None:
    lang = current_lang()
    merchant_id = _require_merchant_id(lang)
    if merchant_id is None:
        return
    with database.session() as session:
        merchant = _merchant_snapshot(session, merchant_id)
    ui.page_header(
        t("merchant.profile.title", lang), t("merchant.profile.subtitle", lang), eyebrow=t("nav.merchant.profile", lang)
    )
    left, right = st.columns([1, 1.2], gap="large")
    with left:
        st.markdown(
            f"""
<div class="wafa-card navy">
  <div class="wafa-row"><div class="wafa-icon navy" style="background:rgba(255,255,255,.12)">{icon_svg("store", 21)}</div>
  {ui.badge(t("common.active", lang) if merchant["active"] else t("common.inactive", lang), "navy")}</div>
  <div style="font-weight:800;font-size:1.2rem;margin-top:.8rem">{esc(merchant["name"])}</div>
  <div class="wafa-small" style="color:#C9DDF2">{esc(merchant["category"])} · {esc(merchant["city"])}</div>
  <div class="wafa-line" style="border-color:rgba(255,255,255,.15);margin-top:.7rem"><span style="color:#C9DDF2">{esc(t("common.phone", lang))}</span><strong>{esc(merchant["phone"])}</strong></div>
  <div class="wafa-line" style="border-color:rgba(255,255,255,.15)"><span style="color:#C9DDF2">{esc(t("common.city", lang))}</span><strong>{esc(merchant["city"])}</strong></div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.write("")
        ui.info_banner(
            t("merchant.profile.points_rule", lang), t("merchant.profile.rule_hint", lang), tone="gold", icon="star"
        )
    with right:
        with st.form("merchant_profile_form"):
            st.markdown(f"**{t('merchant.profile.identity', lang)}**")
            business_name = st.text_input(t("auth.business_name", lang), value=merchant["name"])
            description = st.text_area(t("auth.business_description", lang), value=merchant["description"], height=80)
            c1, c2 = st.columns(2)
            with c1:
                category = st.selectbox(
                    t("common.category", lang),
                    merchants.BUSINESS_CATEGORIES,
                    index=merchants.BUSINESS_CATEGORIES.index(merchant["category"])
                    if merchant["category"] in merchants.BUSINESS_CATEGORIES
                    else 0,
                )
            with c2:
                points_rule = st.number_input(
                    t("merchant.profile.points_rule", lang),
                    min_value=1.0,
                    max_value=1000.0,
                    value=float(merchant["rule"]),
                    step=1.0,
                    help=t("merchant.profile.rule_hint", lang),
                )
            st.markdown(f"**{t('merchant.profile.contact', lang)}**")
            c1, c2 = st.columns(2)
            with c1:
                business_phone = st.text_input(t("common.phone", lang), value=merchant["phone"])
            with c2:
                city = st.selectbox(
                    t("common.city", lang),
                    merchants.MOROCCAN_CITIES,
                    index=merchants.MOROCCAN_CITIES.index(merchant["city"])
                    if merchant["city"] in merchants.MOROCCAN_CITIES
                    else 0,
                )
            c1, c2 = st.columns(2)
            with c1:
                neighborhood = st.selectbox(
                    t("common.neighborhood", lang),
                    merchants.AGADIR_NEIGHBORHOODS,
                    index=merchants.AGADIR_NEIGHBORHOODS.index(merchant["neighborhood"])
                    if merchant["neighborhood"] in merchants.AGADIR_NEIGHBORHOODS
                    else 0,
                )
            with c2:
                address = st.text_input(t("auth.business_address", lang), value=merchant["address"])
            submitted = st.form_submit_button(t("common.save", lang), type="primary", width="stretch")
        if submitted:
            try:
                with database.session() as session:
                    merchants.update_profile(
                        session,
                        merchant_id,
                        user,
                        business_name=business_name,
                        description=description,
                        phone=business_phone,
                        address=address,
                        city=city,
                        neighborhood=neighborhood,
                        category=category,
                        points_per_amount=points_rule,
                    )
            except Exception as error:
                ui.show_error(error, lang)
            else:
                flash(t("merchant.profile.saved", lang))
                st.rerun()


def render_settings(user: SessionUser) -> None:
    lang = current_lang()
    ui.page_header(
        t("merchant.settings.title", lang),
        t("merchant.settings.subtitle", lang),
        eyebrow=t("nav.merchant.settings", lang),
    )
    left, right = st.columns([1, 1], gap="large")
    with left:
        ui.section_title(t("common.language", lang))
        labels = {"fr": "Français", "ar": "العربية"}
        current = current_lang()
        selected_label = st.radio(
            t("common.language", lang),
            list(labels.values()),
            index=list(labels.keys()).index(current),
            key="merchant_language",
        )
        selected = next((code for code, label in labels.items() if label == selected_label), current)
        if selected != current:
            from .state import set_language

            set_language(selected, user.id)
            flash(t("client.settings.saved", lang))
            st.rerun()
        st.write("")
        ui.section_title(t("client.settings.notifications", lang))
        st.toggle(t("common.notifications", lang), value=True, disabled=True)
        st.caption(t("client.settings.coming_soon", lang))
    with right:
        ui.info_banner(t("help.security_title", lang), t("help.security_text", lang), tone="green", icon="shield")
        st.write("")
        ui.info_banner(t("help.payments_title", lang), t("help.payments_text", lang), tone="gold", icon="card")
    ui.legal_note(lang)


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
            t("merchant.notifications.title", lang),
            t("merchant.notifications.subtitle", lang),
            eyebrow=f"{unread} {t('common.unread', lang)}",
        )
    with header_right:
        st.write("")
        if st.button(t("client.notifications.mark_all", lang), width="stretch", key="merchant_mark_all"):
            with database.session() as session:
                notifications.mark_all_read(session, user.id)
            st.rerun()
    if not items:
        ui.empty_state(t("merchant.notifications.empty", lang), t("common.no_data", lang), icon="bell")
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
            if not item["is_read"] and st.button(t("common.read", lang), key=f"merchant_read_{item['id']}"):
                with database.session() as session:
                    notifications.mark_read(session, user.id, item["id"])
                st.rerun()
        with c2:
            if item["link_page"] and st.button(t("client.notifications.open", lang), key=f"merchant_open_{item['id']}"):
                if not item["is_read"]:
                    with database.session() as session:
                        notifications.mark_read(session, user.id, item["id"])
                goto(item["link_page"])


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

PAGES: dict[str, Callable[[SessionUser], None]] = {
    "merchant.dashboard": render_dashboard,
    "merchant.add_points": render_add_points,
    "merchant.validate_reward": render_validate_reward,
    "merchant.clients": render_clients,
    "merchant.transactions": render_transactions,
    "merchant.rewards": render_rewards,
    "merchant.reward_form": render_reward_form,
    "merchant.gift_cards": render_gift_cards,
    "merchant.promotions": render_promotions,
    "merchant.promotion_form": render_promotion_form,
    "merchant.stats": render_stats,
    "merchant.profile": render_profile,
    "merchant.settings": render_settings,
    "merchant.notifications": render_notifications,
}


def render(page: str, user: SessionUser) -> None:
    handler = PAGES.get(page)
    if not handler:
        ui.empty_state(t("common.no_data", current_lang()), t("errors.not_found", current_lang()))
        return
    handler(user)
