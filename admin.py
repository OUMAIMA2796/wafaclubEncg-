"""Pages d'administration WafaClub."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from datetime import datetime, time, timedelta

import streamlit as st

from ..db import database
from ..i18n import format_date, format_datetime, format_mad, format_points, t
from ..models import GiftCardStatus, TransactionType, UserRole
from ..services import admin, merchants, stats
from . import components as ui
from .icons import esc
from .state import SessionUser, current_lang, flash, goto


def _type_options(lang: str) -> dict[str, TransactionType | None]:
    return {
        t("common.all", lang): None,
        **{t(f"transaction.{member.value}", lang): member for member in TransactionType},
    }


def _status_options(lang: str) -> dict[str, GiftCardStatus | None]:
    return {
        t("common.all", lang): None,
        **{t(f"status.{member.value}", lang): member for member in GiftCardStatus},
    }


def _role_options(lang: str) -> dict[str, UserRole | None]:
    return {
        t("common.all", lang): None,
        t("role.CLIENT", lang): UserRole.CLIENT,
        t("role.MERCHANT", lang): UserRole.MERCHANT,
        t("role.ADMIN", lang): UserRole.ADMIN,
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def render_dashboard(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    with database.session() as session:
        data = stats.admin_overview(session, days=30)
        recent_users = admin.list_users(session)[:6]
        recent_merchants = admin.list_merchants(session)[:6]
        users_rows = [
            {
                "name": item.full_name,
                "phone": item.phone,
                "role": t(f"role.{item.role.value}", lang),
                "city": item.city,
                "created_at": item.created_at,
                "active": item.is_active,
            }
            for item in recent_users
        ]
        merchant_rows = [
            {
                "name": item.business_name,
                "category": item.category,
                "city": item.city,
                "active": item.is_active,
                "owner": item.owner.full_name if item.owner else "—",
            }
            for item in recent_merchants
        ]

    ui.page_header(t("admin.dashboard.title", lang), t("admin.dashboard.subtitle", lang), eyebrow=t("role.ADMIN", lang))
    cols = st.columns(4, gap="medium")
    with cols[0]:
        ui.stat_card(t("admin.dashboard.clients", lang), str(data["clients"]), icon="users", tone="blue")
    with cols[1]:
        ui.stat_card(
            t("admin.dashboard.merchants", lang),
            str(data["merchants"]),
            hint=f"{data['active_merchants']} {t('common.active', lang)}",
            icon="store",
            tone="gold",
        )
    with cols[2]:
        ui.stat_card(t("admin.dashboard.transactions", lang), str(data["transactions"]), icon="receipt", tone="green")
    with cols[3]:
        ui.stat_card(
            t("admin.dashboard.points", lang), format_points(data["points_distributed"], lang), icon="star", tone="navy"
        )

    st.write("")
    cols = st.columns(4, gap="medium")
    with cols[0]:
        ui.stat_card(t("admin.dashboard.redemptions", lang), str(data["redemptions_used"]), icon="gift", tone="green")
    with cols[1]:
        ui.stat_card(t("admin.dashboard.gift_cards", lang), str(data["gift_cards"]), icon="wallet", tone="blue")
    with cols[2]:
        ui.stat_card(
            t("admin.dashboard.volume", lang), format_mad(data["gift_card_volume"], lang), icon="coins", tone="gold"
        )
    with cols[3]:
        ui.stat_card(
            t("admin.dashboard.users_table", lang),
            str(data["merchant_owners"]),
            hint=t("role.MERCHANT", lang),
            icon="user",
            tone="navy",
        )

    st.write("")
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        ui.section_title(t("admin.dashboard.chart", lang))
        chart = [{"Date": format_date(point["date"], lang), "Points": point["points"]} for point in data["series"]]
        if chart:
            st.bar_chart(chart, x="Date", y="Points", color="#1E6FA8", height=250)
        else:
            st.caption(t("common.no_data", lang))
    with right:
        ui.section_title(t("admin.dashboard.cities", lang))
        if data["cities"]:
            for item in data["cities"]:
                st.markdown(
                    f"""
<div class="wafa-line"><span>{esc(item["city"])}</span><strong>{item["merchants"]} {esc(t("common.merchant", lang))}</strong></div>
""",
                    unsafe_allow_html=True,
                )
        else:
            st.caption(t("common.no_data", lang))

    st.write("")
    ui.section_title(t("admin.dashboard.users_table", lang))
    if users_rows:
        st.dataframe(
            [
                {
                    t("common.name", lang): row["name"],
                    t("common.phone", lang): row["phone"],
                    t("common.role", lang): row["role"],
                    t("common.city", lang): row["city"],
                    t("common.created_at", lang): format_date(row["created_at"], lang),
                }
                for row in users_rows
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption(t("common.no_data", lang))

    if st.button(t("admin.dashboard.see_users", lang), width="stretch", key="admin_users_link"):
        goto("admin.users")

    st.write("")
    ui.section_title(t("admin.dashboard.merchants_table", lang))
    if merchant_rows:
        st.dataframe(
            [
                {
                    t("common.name", lang): row["name"],
                    t("common.category", lang): row["category"],
                    t("common.city", lang): row["city"],
                    t("common.status", lang): t("common.active", lang) if row["active"] else t("common.inactive", lang),
                    t("role.MERCHANT", lang): row["owner"],
                }
                for row in merchant_rows
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption(t("common.no_data", lang))


# ---------------------------------------------------------------------------
# Utilisateurs
# ---------------------------------------------------------------------------


def render_users(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    ui.page_header(t("admin.users.title", lang), t("admin.users.subtitle", lang), eyebrow=t("common.clients", lang))
    c1, c2, c3 = st.columns([1.6, 1, 1], gap="medium")
    with c1:
        search = st.text_input(
            t("admin.users.search", lang), placeholder=t("common.name", lang), key="admin_user_search"
        )
    with c2:
        role_label = st.selectbox(t("common.role", lang), list(_role_options(lang).keys()), key="admin_user_role")
    with c3:
        city = st.selectbox(
            t("common.city", lang), [t("common.all", lang), *merchants.MOROCCAN_CITIES], key="admin_user_city"
        )
    with database.session() as session:
        users = admin.list_users(
            session,
            role=_role_options(lang)[role_label],
            city=city if city != t("common.all", lang) else None,
            search=search or None,
        )
        rows = [
            {
                "id": item.id,
                "name": item.full_name,
                "phone": item.phone,
                "email": item.email or "—",
                "role": item.role,
                "city": item.city,
                "neighborhood": item.neighborhood,
                "active": item.is_active,
                "created_at": item.created_at,
                "last_login_at": item.last_login_at,
            }
            for item in users
        ]
    if not rows:
        ui.empty_state(t("admin.users.empty", lang), t("common.no_data", lang), icon="users")
        return
    st.caption(f"{len(rows)} {t('common.total', lang).lower()}")
    st.dataframe(
        [
            {
                t("common.name", lang): row["name"],
                t("common.phone", lang): row["phone"],
                t("common.email", lang): row["email"],
                t("common.role", lang): t(f"role.{row['role'].value}", lang),
                t("common.city", lang): f"{row['city']} · {row['neighborhood']}",
                t("common.status", lang): t("common.active", lang) if row["active"] else t("common.inactive", lang),
                t("common.created_at", lang): format_date(row["created_at"], lang),
                t("common.history", lang): format_datetime(row["last_login_at"], lang),
            }
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )


# ---------------------------------------------------------------------------
# Commerces
# ---------------------------------------------------------------------------


def render_merchants(user: SessionUser) -> None:
    lang = current_lang()
    ui.page_header(
        t("admin.merchants.title", lang), t("admin.merchants.subtitle", lang), eyebrow=t("common.merchant", lang)
    )
    c1, c2, c3 = st.columns([1.6, 1, 1], gap="medium")
    with c1:
        search = st.text_input(
            t("common.search", lang), placeholder=t("common.merchant", lang), key="admin_merchant_search"
        )
    with c2:
        city = st.selectbox(
            t("common.city", lang), [t("common.all", lang), *merchants.MOROCCAN_CITIES], key="admin_merchant_city"
        )
    with c3:
        status_label = st.selectbox(
            t("common.status", lang),
            [t("common.all", lang), t("common.active", lang), t("common.inactive", lang)],
            key="admin_merchant_status",
        )
    active_filter = None
    if status_label == t("common.active", lang):
        active_filter = True
    elif status_label == t("common.inactive", lang):
        active_filter = False
    with database.session() as session:
        list_ = admin.list_merchants(
            session,
            city=city if city != t("common.all", lang) else None,
            active=active_filter,
            search=search or None,
        )
        rows = [
            {
                "id": merchant.id,
                "name": merchant.business_name,
                "category": merchant.category,
                "city": merchant.city,
                "neighborhood": merchant.neighborhood,
                "address": merchant.address,
                "phone": merchant.phone,
                "owner": merchant.owner.full_name if merchant.owner else "—",
                "owner_phone": merchant.owner.phone if merchant.owner else "—",
                "active": merchant.is_active,
                "rule": merchant.points_per_amount,
                "created_at": merchant.created_at,
            }
            for merchant in list_
        ]
    if not rows:
        ui.empty_state(t("admin.merchants.empty", lang), t("common.no_data", lang), icon="store")
        return
    st.caption(f"{len(rows)} {t('common.total', lang).lower()}")
    st.dataframe(
        [
            {
                t("common.name", lang): row["name"],
                t("common.category", lang): row["category"],
                t("common.city", lang): f"{row['city']} · {row['neighborhood']}",
                t("common.phone", lang): row["phone"],
                t("role.MERCHANT", lang): row["owner"],
                t("common.status", lang): t("common.active", lang) if row["active"] else t("common.inactive", lang),
                t("common.created_at", lang): format_date(row["created_at"], lang),
            }
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )
    st.write("")
    ui.section_title(t("admin.merchants.toggle", lang))
    for row in rows:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(
                f"""
<div class="wafa-card tight" style="margin-bottom:.5rem">
  <div class="wafa-row">
    <div><strong style="font-size:.86rem">{esc(row["name"])}</strong>
    <div class="wafa-small">{esc(row["address"])} · {esc(row["owner"])} · {esc(row["owner_phone"])}</div></div>
    {ui.badge(t("common.active", lang) if row["active"] else t("common.inactive", lang), "green" if row["active"] else "gray")}
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
        with c2:
            if st.button(
                t("admin.merchants.toggle", lang),
                key=f"toggle_merchant_{row['id']}",
                width="stretch",
            ):
                try:
                    with database.session() as session:
                        admin.toggle_merchant(session, merchant_id=row["id"], active=not row["active"], actor=user)
                except Exception as error:
                    ui.show_error(error, lang)
                else:
                    flash(t("admin.merchants.status_updated", lang))
                    st.rerun()


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


def render_transactions(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    ui.page_header(
        t("admin.transactions.title", lang),
        t("admin.transactions.subtitle", lang),
        eyebrow=t("common.transactions", lang),
    )
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        type_label = st.selectbox(t("common.type", lang), list(_type_options(lang).keys()), key="admin_tx_type")
    with c2:
        city = st.selectbox(
            t("common.city", lang), [t("common.all", lang), *merchants.MOROCCAN_CITIES], key="admin_tx_city"
        )
    with c3:
        days = st.selectbox(t("common.range", lang), [7, 30, 90, 365], index=1, key="admin_tx_days")
    since = datetime.combine(datetime.now().date() - timedelta(days=days), time.min)
    with database.session() as session:
        transactions = admin.list_transactions(
            session,
            date_from=since,
            city=city if city != t("common.all", lang) else None,
            type_filter=_type_options(lang)[type_label],
            limit=1000,
        )
        rows = [
            {
                "created_at": transaction.created_at,
                "client": transaction.user.full_name if transaction.user else "—",
                "merchant": transaction.merchant.business_name if transaction.merchant else "—",
                "type": transaction.type,
                "points": transaction.points,
                "amount": transaction.purchase_amount,
                "balance_after": transaction.balance_after,
                "description": transaction.description,
            }
            for transaction in transactions
        ]
    if not rows:
        ui.empty_state(t("admin.transactions.empty", lang), t("common.no_data", lang), icon="receipt")
        return
    st.caption(f"{len(rows)} {t('common.transactions', lang).lower()}")
    table = [
        {
            t("common.date", lang): format_datetime(row["created_at"], lang),
            t("common.client", lang): row["client"],
            t("common.merchant", lang): row["merchant"],
            t("common.type", lang): t(f"transaction.{row['type'].value}", lang),
            t("common.amount", lang): str(row["amount"]) if row["amount"] is not None else "—",
            t("common.points", lang): row["points"],
            t("client.points.balance_after", lang): row["balance_after"],
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
        file_name="wafaclub-admin-transactions.csv",
        mime="text/csv",
        key="admin_export_tx",
    )


# ---------------------------------------------------------------------------
# Cartes cadeaux
# ---------------------------------------------------------------------------


def render_gift_cards(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    ui.page_header(t("admin.gift.title", lang), t("admin.gift.subtitle", lang), eyebrow=t("nav.admin.gift_cards", lang))
    status_label = st.selectbox(t("common.status", lang), list(_status_options(lang).keys()), key="admin_gift_status")
    with database.session() as session:
        cards = admin.list_gift_cards(session, status=_status_options(lang)[status_label])
        rows = [
            {
                "code": card.code,
                "amount": card.amount,
                "status": card.status,
                "sender": card.sender.full_name if card.sender else "—",
                "recipient": card.recipient_name,
                "merchant": card.merchant.business_name if card.merchant else "—",
                "created_at": card.created_at,
                "expires_at": card.expires_at,
                "redeemed_at": card.redeemed_at,
            }
            for card in cards
        ]
    if not rows:
        ui.empty_state(t("admin.gift.empty", lang), t("common.no_data", lang), icon="gift")
        return
    st.caption(f"{len(rows)} {t('common.total', lang).lower()}")
    st.dataframe(
        [
            {
                t("client.gift.code", lang): row["code"],
                t("common.amount", lang): format_mad(row["amount"], lang),
                t("common.status", lang): t(f"status.{row['status'].value}", lang),
                t("client.gift.from", lang): row["sender"],
                t("client.gift.to", lang): row["recipient"],
                t("common.merchant", lang): row["merchant"],
                t("common.created_at", lang): format_date(row["created_at"], lang),
                t("common.expires_at", lang): format_date(row["expires_at"], lang),
            }
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------


def render_promotions(user: SessionUser) -> None:  # noqa: ARG001
    lang = current_lang()
    ui.page_header(
        t("admin.promotions.title", lang), t("admin.promotions.subtitle", lang), eyebrow=t("common.promotions", lang)
    )
    c1, c2 = st.columns(2)
    with c1:
        city = st.selectbox(
            t("common.city", lang), [t("common.all", lang), *merchants.MOROCCAN_CITIES], key="admin_promo_city"
        )
    with c2:
        status_label = st.selectbox(
            t("common.status", lang),
            [t("common.all", lang), t("common.active", lang), t("common.inactive", lang)],
            key="admin_promo_status",
        )
    active_filter = (
        True
        if status_label == t("common.active", lang)
        else False
        if status_label == t("common.inactive", lang)
        else None
    )
    with database.session() as session:
        promotions_list = admin.list_promotions(
            session,
            city=city if city != t("common.all", lang) else None,
            active=active_filter,
        )
        rows = [
            {
                "title": promotion.title,
                "merchant": promotion.merchant.business_name if promotion.merchant else "—",
                "city": promotion.city,
                "neighborhood": promotion.neighborhood,
                "starts_at": promotion.starts_at,
                "expires_at": promotion.expires_at,
                "active": promotion.is_active,
            }
            for promotion in promotions_list
        ]
    if not rows:
        ui.empty_state(t("admin.promotions.empty", lang), t("common.no_data", lang), icon="map-pin")
        return
    st.caption(f"{len(rows)} {t('common.total', lang).lower()}")
    st.dataframe(
        [
            {
                t("common.title", lang): row["title"],
                t("common.merchant", lang): row["merchant"],
                t("common.city", lang): f"{row['city']} · {row['neighborhood']}",
                t("common.from", lang): format_date(row["starts_at"], lang),
                t("client.promotions.expires", lang): format_date(row["expires_at"], lang),
                t("common.status", lang): t("common.active", lang) if row["active"] else t("common.inactive", lang),
            }
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

PAGES: dict[str, Callable[[SessionUser], None]] = {
    "admin.dashboard": render_dashboard,
    "admin.users": render_users,
    "admin.merchants": render_merchants,
    "admin.transactions": render_transactions,
    "admin.gift_cards": render_gift_cards,
    "admin.promotions": render_promotions,
}


def render(page: str, user: SessionUser) -> None:
    handler = PAGES.get(page)
    if not handler:
        ui.empty_state(t("common.no_data", current_lang()), t("errors.not_found", current_lang()))
        return
    handler(user)
