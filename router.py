"""Routeur Streamlit, navigation latérale et garde d'accès."""

from __future__ import annotations

import streamlit as st

from ..access import can_access, default_page
from ..db import database
from ..i18n import t
from ..models import UserRole
from ..services import merchants, notifications
from . import admin as admin_pages
from . import client as client_pages
from . import components as ui
from . import merchant as merchant_pages
from .icons import esc
from .state import SS, SessionUser, current_lang, go_back, language_selector, logout, navigate_to, show_flash

NAV_ITEMS: dict[UserRole, list[tuple[str, str]]] = {
    UserRole.CLIENT: [
        ("client.dashboard", "home"),
        ("client.card", "🎫"),
        ("client.points", "⭐"),
        ("client.rewards", "🎁"),
        ("client.my_rewards", "🏷️"),
        ("client.promotions", "📍"),
        ("client.merchants", "🏪"),
        ("client.gift_cards", "💳"),
        ("client.notifications", "🔔"),
        ("client.profile", "👤"),
        ("client.settings", "⚙️"),
        ("client.help", "❓"),
    ],
    UserRole.MERCHANT: [
        ("merchant.dashboard", "home"),
        ("merchant.add_points", "➕"),
        ("merchant.validate_reward", "📷"),
        ("merchant.clients", "👥"),
        ("merchant.transactions", "🧾"),
        ("merchant.rewards", "🎁"),
        ("merchant.gift_cards", "💳"),
        ("merchant.promotions", "📍"),
        ("merchant.stats", "📊"),
        ("merchant.notifications", "🔔"),
        ("merchant.profile", "👤"),
        ("merchant.settings", "⚙️"),
    ],
    UserRole.ADMIN: [
        ("admin.dashboard", "home"),
        ("admin.users", "👥"),
        ("admin.merchants", "🏪"),
        ("admin.transactions", "🧾"),
        ("admin.gift_cards", "💳"),
        ("admin.promotions", "📍"),
    ],
}

PAGE_PARENT = {
    "client.reward_detail": "client.rewards",
    "client.reward_confirm": "client.rewards",
    "client.reward_success": "client.rewards",
    "client.promotion_detail": "client.promotions",
    "client.merchant_detail": "client.merchants",
    "client.gift_create": "client.gift_cards",
    "client.gift_confirm": "client.gift_cards",
    "client.gift_success": "client.gift_cards",
    "merchant.reward_form": "merchant.rewards",
    "merchant.promotion_form": "merchant.promotions",
}


def _nav_label(page: str, lang: str) -> str:
    return t(f"nav.{page}", lang)


def _unread_badge(user: SessionUser) -> int:
    try:
        with database.session() as session:
            return notifications.unread_count(session, user.id)
    except Exception:
        return 0


def _sidebar_user_card(user: SessionUser, lang: str) -> None:
    st.markdown(
        f"""
<div class="wafa-sidebar-user">
  <div class="wafa-avatar">{esc(user.initials)}</div>
  <div>
    <strong>{esc(user.full_name)}</strong>
    <span>{esc(t(f"role.{user.role.value}", lang))} · {esc(user.city)}</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _merchant_selector(user: SessionUser, lang: str) -> None:
    if user.role != UserRole.MERCHANT:
        return
    try:
        with database.session() as session:
            owned = merchants.owned_merchants(session, user.id)
            options = [(merchant.id, merchant.business_name) for merchant in owned]
    except Exception:
        options = []
    if not options:
        SS["merchant_id"] = None
        st.sidebar.warning(t("errors.merchant_not_found", lang))
        return
    ids = [item[0] for item in options]
    names = dict(options)
    current = SS.get("merchant_id")
    if current not in ids:
        current = ids[0]
        SS["merchant_id"] = current
    selected = st.sidebar.selectbox(
        t("nav.active_business", lang),
        ids,
        index=ids.index(current),
        format_func=lambda value: names.get(value, "—"),
        key="active_business",
    )
    if selected != SS.get("merchant_id"):
        SS["merchant_id"] = selected
        st.rerun()


def _sidebar_nav(user: SessionUser, lang: str, unread: int) -> None:
    st.sidebar.markdown(
        f'<div class="wafa-sidebar-section">{esc(t(f"nav.section.{user.role.value.lower()}", lang))}</div>',
        unsafe_allow_html=True,
    )
    page = SS.get("page") or default_page(user.role)
    parent = PAGE_PARENT.get(page, page)
    for item, icon in NAV_ITEMS[user.role]:
        label = _nav_label(item, lang)
        if item.endswith("notifications") and unread:
            label = f"{label} ({unread})"
        if st.sidebar.button(
            f"{icon}  {label}" if icon != "home" else f"🏠  {label}",
            key=f"nav_{item}",
            width="stretch",
            type="primary" if item == parent else "secondary",
        ):
            navigate_to(item)
            st.rerun()


def _sidebar_footer(user: SessionUser, lang: str) -> None:
    st.sidebar.markdown("<div class='wafa-divider'></div>", unsafe_allow_html=True)
    language_selector(key="lang_app", user_id=user.id)
    if st.sidebar.button(f"🚪  {t('common.logout', lang)}", width="stretch", key="logout"):
        logout()
        st.rerun()
    st.sidebar.markdown(
        f"""
<div class="wafa-sidebar-foot">
  <strong style="color:#D9E9F7">WafaClub</strong> · {esc(t("app.version", lang))}<br/>
  {esc(t("app.prototype", lang))} · {esc(t("app.simulated", lang))}<br/>
  {esc(t("common.legal_note", lang))}
</div>
""",
        unsafe_allow_html=True,
    )


def render(user: SessionUser) -> None:
    lang = current_lang()
    page = SS.get("page") or default_page(user.role)
    if not can_access(user.role, page):
        st.warning(t("errors.page_forbidden", lang))
        page = default_page(user.role)
        SS["page"] = page
        SS["ctx"] = {}
        SS["page_history"] = []
    SS["page"] = page

    unread = _unread_badge(user)
    with st.sidebar:
        ui.logo(dark=True, compact=True)
        _sidebar_user_card(user, lang)
        _merchant_selector(user, lang)
        _sidebar_nav(user, lang, unread)
        _sidebar_footer(user, lang)

    show_flash()
    if st.button(
        f"←  {t('common.back', lang)}",
        key="page_back",
        disabled=not SS.get("page_history"),
    ):
        go_back(default_page(user.role))
        st.rerun()

    if user.role == UserRole.CLIENT:
        client_pages.render(page, user)
    elif user.role == UserRole.MERCHANT:
        merchant_pages.render(page, user)
    else:
        admin_pages.render(page, user)
