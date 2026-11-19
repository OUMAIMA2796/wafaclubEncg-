"""Pages publiques : accueil marketing et authentification."""

from __future__ import annotations

import streamlit as st

from ..db import database
from ..i18n import t
from ..models import Language, UserRole
from ..services import auth, merchants
from . import components as ui
from .icons import esc, icon_svg
from .state import (
    SS,
    current_lang,
    language_selector,
    login_user,
)

DEMO_ACCOUNTS = {
    "client": ("+212661234567", UserRole.CLIENT),
    "merchant": ("+212664567890", UserRole.MERCHANT),
    "admin": ("+212660000000", UserRole.ADMIN),
}
DEMO_PASSWORD = "Demo2026!"


def _start_auth(mode: str, role: str = "CLIENT") -> None:
    SS["view"] = "auth"
    SS["auth_mode"] = mode
    SS["auth_role"] = role
    st.rerun()


def _landing_header(lang: str) -> None:
    spacer, lang_col, login_col, signup_col = st.columns([5, 1.35, 1.35, 1.55])
    with spacer:
        ui.logo(slogan=True)
    with lang_col:
        language_selector(key="lang_public")
    with login_col:
        if st.button(t("common.login", lang), width="stretch", key="public_login"):
            _start_auth("login")
    with signup_col:
        if st.button(
            t("common.signup", lang),
            type="primary",
            width="stretch",
            key="public_signup",
        ):
            _start_auth("signup")


def render_landing() -> None:
    lang = current_lang()
    _landing_header(lang)

    st.markdown(
        f"""
<div class="wafa-hero">
  <div class="wafa-hero-grid">
    <div>
      <div class="wafa-chip">{icon_svg("sparkles", 14)} {esc(t("landing.hero.eyebrow", lang))}</div>
      <h1>{esc(t("landing.hero.title", lang))}<br/><span class="gold">{esc(t("landing.hero.title_accent", lang))}</span></h1>
      <p>{esc(t("landing.hero.subtitle", lang))}</p>
      <div class="wafa-slogan">{esc(t("app.slogan", lang))}</div>
      <div class="wafa-hero-chips">
        <span>{icon_svg("card", 15)} {esc(t("landing.hero.trust_cards", lang))}</span>
        <span>{icon_svg("star", 15)} {esc(t("landing.hero.trust_points", lang))}</span>
        <span>{icon_svg("map-pin", 15)} {esc(t("landing.hero.trust_local", lang))}</span>
      </div>
    </div>
    <div class="wafa-hero-visual">
      <div class="wafa-demo-card">
        <div class="wafa-demo-card-top">
          <span>{esc(t("client.dashboard.card_title", lang))}</span>
          <span class="wafa-demo-dot"></span>
        </div>
        <div class="wafa-demo-points">329 <small>{esc(t("common.points", lang))}</small></div>
        <div class="wafa-demo-name">{esc(t("client.card.member", lang))} · Yasmine</div>
        <div class="wafa-demo-progress"><span></span></div>
        <div class="wafa-demo-foot">
          <div class="wafa-demo-qr">{icon_svg("qr", 24)}</div>
          <div>
            <strong>Café Argana</strong><br/>
            <span>Talborjt · Agadir</span>
          </div>
          <div class="wafa-demo-badge">+9</div>
        </div>
      </div>
      <div class="wafa-hero-float float-a">{icon_svg("gift", 16)} {esc(t("landing.gift.title", lang))}</div>
      <div class="wafa-hero-float float-b">{icon_svg("shield", 16)} {esc(t("app.simulated", lang))}</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1, 2.5])
    with c1:
        if st.button(
            f"☕ {t('landing.hero.cta_client', lang)}",
            type="primary",
            width="stretch",
            key="hero_client",
        ):
            _start_auth("signup", "CLIENT")
    with c2:
        if st.button(
            f"🏪 {t('landing.hero.cta_merchant', lang)}",
            width="stretch",
            key="hero_merchant",
        ):
            _start_auth("signup", "MERCHANT")

    st.write("")
    ui.page_header(
        t("landing.problem.title", lang),
        t("landing.solution.text", lang),
        eyebrow=t("landing.problem.eyebrow", lang),
    )
    cols = st.columns(3, gap="medium")
    problem_cards = [
        ("card", "landing.problem.card1_title", "landing.problem.card1_text", "gold"),
        ("users", "landing.problem.card2_title", "landing.problem.card2_text", "blue"),
        ("map-pin", "landing.problem.card3_title", "landing.problem.card3_text", "green"),
    ]
    for column, (icon, title, text, tone) in zip(cols, problem_cards, strict=True):
        with column:
            ui.feature_card(icon, t(title, lang), t(text, lang), tone=tone)

    st.write("")
    st.markdown(
        f"""
<div class="wafa-card navy" style="padding:1.5rem 1.7rem">
  <div class="wafa-row" style="align-items:center;flex-wrap:wrap">
    <div>
      <div class="wafa-eyebrow" style="color:#F4C66A">{esc(t("landing.solution.eyebrow", lang))}</div>
      <h2 style="margin:.1rem 0 .3rem;font-size:1.35rem">{esc(t("landing.solution.title", lang))}</h2>
      <div style="font-size:.83rem;opacity:.8;max-width:760px">{esc(t("landing.solution.text", lang))}</div>
    </div>
    <div class="wafa-pill-row" style="margin-top:.8rem">
      {ui.badge(t("common.simulated_payment", lang), "gold")}
      {ui.badge("QR", "blue")}
      {ui.badge("MAD", "green")}
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.write("")
    ui.page_header(t("landing.features.title", lang), eyebrow=t("landing.solution.eyebrow", lang))
    features = [
        ("qr", "landing.features.card1_title", "landing.features.card1_text", "blue"),
        ("star", "landing.features.card2_title", "landing.features.card2_text", "gold"),
        ("ticket", "landing.features.card3_title", "landing.features.card3_text", "green"),
        ("gift", "landing.features.card4_title", "landing.features.card4_text", "gold"),
        ("map-pin", "landing.features.card5_title", "landing.features.card5_text", "blue"),
        ("chart", "landing.features.card6_title", "landing.features.card6_text", "green"),
    ]
    for start in range(0, len(features), 3):
        cols = st.columns(3, gap="medium")
        for column, (icon, title, text, tone) in zip(cols, features[start : start + 3], strict=True):
            with column:
                ui.feature_card(icon, t(title, lang), t(text, lang), tone=tone)

    st.write("")
    ui.page_header(t("landing.benefits.title", lang))
    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown(
            f"""
<div class="wafa-card green" style="min-height:230px">
  <div class="wafa-row"><span class="wafa-eyebrow">{esc(t("landing.benefits.client_title", lang))}</span><div class="wafa-icon green">{icon_svg("user", 19)}</div></div>
  <ul style="margin:.8rem 0 0 1rem;padding:0;font-size:.85rem;line-height:1.9">
    <li>{esc(t("landing.benefits.client1", lang))}</li>
    <li>{esc(t("landing.benefits.client2", lang))}</li>
    <li>{esc(t("landing.benefits.client3", lang))}</li>
  </ul>
</div>
""",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f"""
<div class="wafa-card gold" style="min-height:230px">
  <div class="wafa-row"><span class="wafa-eyebrow">{esc(t("landing.benefits.merchant_title", lang))}</span><div class="wafa-icon gold">{icon_svg("store", 19)}</div></div>
  <ul style="margin:.8rem 0 0 1rem;padding:0;font-size:.85rem;line-height:1.9">
    <li>{esc(t("landing.benefits.merchant1", lang))}</li>
    <li>{esc(t("landing.benefits.merchant2", lang))}</li>
    <li>{esc(t("landing.benefits.merchant3", lang))}</li>
  </ul>
</div>
""",
            unsafe_allow_html=True,
        )

    st.write("")
    ui.page_header(t("landing.how.title", lang), eyebrow=t("landing.how.eyebrow", lang))
    steps = [
        ("1", "landing.how.step1_title", "landing.how.step1_text"),
        ("2", "landing.how.step2_title", "landing.how.step2_text"),
        ("3", "landing.how.step3_title", "landing.how.step3_text"),
        ("4", "landing.how.step4_title", "landing.how.step4_text"),
    ]
    cols = st.columns(4, gap="medium")
    for column, (number, title, text) in zip(cols, steps, strict=True):
        with column:
            st.markdown(
                f"""
<div class="wafa-card" style="height:100%">
  <div class="wafa-step-num">{number}</div>
  <h4 style="font-size:.92rem;margin:.75rem 0 .3rem">{esc(t(title, lang))}</h4>
  <p style="font-size:.78rem;color:#64748B;line-height:1.55;margin:0">{esc(t(text, lang))}</p>
</div>
""",
                unsafe_allow_html=True,
            )

    st.write("")
    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown(
            f"""
<div class="wafa-card gold" style="height:100%;padding:1.6rem">
  <div class="wafa-reward-icon" style="font-size:1.6rem">🎁</div>
  <h3 style="margin:.9rem 0 .35rem;font-size:1.12rem">{esc(t("landing.gift.title", lang))}</h3>
  <p style="color:#64748B;font-size:.84rem;line-height:1.6">{esc(t("landing.gift.text", lang))}</p>
  {ui.badge(t("common.simulated_payment", lang), "gold")}
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button(
            t("landing.gift.cta", lang),
            key="landing_gift_cta",
            width="stretch",
        ):
            _start_auth("signup", "CLIENT")
    with right:
        st.markdown(
            f"""
<div class="wafa-card blue" style="height:100%;padding:1.6rem">
  <div class="wafa-reward-icon" style="background:#E8F2FB;border-color:#D6E7F5;font-size:1.6rem">📍</div>
  <h3 style="margin:.9rem 0 .35rem;font-size:1.12rem">{esc(t("landing.promotions.title", lang))}</h3>
  <p style="color:#64748B;font-size:.84rem;line-height:1.6">{esc(t("landing.promotions.text", lang))}</p>
  {ui.badge("Agadir · Talborjt · Founty", "blue")}
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button(
            t("landing.promotions.cta", lang),
            key="landing_promo_cta",
            width="stretch",
        ):
            _start_auth("login", "CLIENT")

    st.write("")
    st.markdown(
        f"""
<div class="wafa-card" style="border-left:4px solid #12805C;background:linear-gradient(135deg,#FFFFFF,#F5FCF9)">
  <div style="display:flex;gap:1rem;align-items:flex-start">
    <div class="wafa-icon green" style="width:46px;height:46px">{icon_svg("shield", 23)}</div>
    <div>
      <h3 style="margin:0 0 .35rem;font-size:1.05rem">{esc(t("landing.security.title", lang))}</h3>
      <p style="margin:0;color:#64748B;font-size:.84rem;line-height:1.65;max-width:900px">{esc(t("landing.security.text", lang))}</p>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown(
        f"""
<div class="wafa-cta-band">
  <h2>{esc(t("landing.cta.title", lang))}</h2>
  <p>{esc(t("landing.cta.text", lang))}</p>
</div>
""",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button(
            f"👤 {t('landing.hero.cta_client', lang)}",
            type="primary",
            width="stretch",
            key="bottom_client",
        ):
            _start_auth("signup", "CLIENT")
    with c2:
        if st.button(
            f"🏪 {t('landing.hero.cta_merchant', lang)}",
            width="stretch",
            key="bottom_merchant",
        ):
            _start_auth("signup", "MERCHANT")
    with c3:
        if st.button(
            t("landing.cta.demo", lang),
            width="stretch",
            key="bottom_demo",
        ):
            _start_auth("login", "CLIENT")

    st.markdown(
        f"""
<div class="wafa-legal">
  <strong>{esc(t("landing.footer.legal", lang))}</strong><br/>
  {esc(t("landing.footer.legal_note", lang))}<br/><br/>
  WafaClub · {esc(t("app.slogan", lang))}
</div>
""",
        unsafe_allow_html=True,
    )


def _auth_header(lang: str) -> None:
    left, right = st.columns([4, 1.1])
    with left:
        ui.logo(dark=False, slogan=True)
    with right:
        if st.button(t("nav.back_home", lang), width="stretch", key="auth_back"):
            SS["view"] = "landing"
            st.rerun()
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)


def _demo_login(account: str) -> None:
    phone, role = DEMO_ACCOUNTS[account]
    try:
        with database.session() as session:
            user = auth.authenticate(session, phone=phone, password=DEMO_PASSWORD, expected_role=role)
            login_user(user)
        st.rerun()
    except Exception as error:
        st.error(ui.error_text(error, current_lang()))


def _demo_box(lang: str) -> None:
    st.markdown(
        f"""
<div class="wafa-demo">
  <strong style="font-size:.88rem">{esc(t("auth.demo_title", lang))}</strong>
  <div class="wafa-small" style="margin:.25rem 0 .75rem">{esc(t("auth.demo_subtitle", lang))}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button(t("auth.demo_client", lang), width="stretch", key="demo_client"):
            _demo_login("client")
    with c2:
        if st.button(t("auth.demo_merchant", lang), width="stretch", key="demo_merchant"):
            _demo_login("merchant")
    with c3:
        if st.button(t("auth.demo_admin", lang), width="stretch", key="demo_admin"):
            _demo_login("admin")


def _role_selector(lang: str, mode: str) -> str:
    current = SS.get("auth_role", "CLIENT")
    options = ["CLIENT", "MERCHANT"]
    if current not in options:
        current = "CLIENT"
    labels = {
        "CLIENT": f"👤 {t('auth.role_client', lang)}",
        "MERCHANT": f"🏪 {t('auth.role_merchant', lang)}",
    }
    selected_label = st.radio(
        t("auth.role_title", lang),
        options=[labels[role] for role in options],
        index=options.index(current),
        horizontal=True,
        key=f"auth_role_{mode}_{current}",
        label_visibility="collapsed",
    )
    selected = "CLIENT" if selected_label == labels["CLIENT"] else "MERCHANT"
    if selected != current:
        SS["auth_role"] = selected
        st.rerun()
    return selected


def _login_form(lang: str, role: str) -> None:
    st.markdown(f"#### {t('auth.login_title', lang)}")
    st.caption(t("auth.login_subtitle", lang))
    with st.form(f"login_form_{role}"):
        phone = st.text_input(t("common.phone", lang), placeholder=t("auth.phone_placeholder", lang))
        password = st.text_input(
            t("common.password", lang),
            type="password",
            placeholder=t("auth.password_placeholder", lang),
        )
        submitted = st.form_submit_button(t("auth.login_submit", lang), type="primary", width="stretch")
    if submitted:
        try:
            with database.session() as session:
                user = auth.authenticate(
                    session,
                    phone=phone,
                    password=password,
                    expected_role=UserRole.CLIENT if role == "CLIENT" else UserRole.MERCHANT,
                )
            login_user(user)
            st.rerun()
        except Exception as error:
            ui.show_error(error, lang)
    st.caption(t("auth.forgot", lang))


def _signup_form(lang: str, role: str) -> None:
    is_client = role == "CLIENT"
    title_key = "auth.signup_title" if is_client else "auth.merchant_signup_title"
    subtitle_key = "auth.signup_subtitle" if is_client else "auth.merchant_signup_subtitle"
    st.markdown(f"#### {t(title_key, lang)}")
    st.caption(t(subtitle_key, lang))

    with st.form(f"signup_form_{role}"):
        st.markdown(f"**{t('client.profile.account', lang)}**")
        c1, c2 = st.columns(2)
        with c1:
            first_name = st.text_input(t("common.first_name", lang))
        with c2:
            last_name = st.text_input(t("common.last_name", lang))
        c1, c2 = st.columns(2)
        with c1:
            phone = st.text_input(t("common.phone", lang), placeholder=t("auth.phone_placeholder", lang))
        with c2:
            email = st.text_input(
                f"{t('common.email', lang)} ({t('common.optional', lang)})",
                placeholder=t("auth.email_placeholder", lang),
            )
        password = st.text_input(
            t("common.password", lang),
            type="password",
            placeholder=t("auth.password_placeholder", lang),
            help=t("auth.password_hint", lang),
        )
        c1, c2 = st.columns(2)
        with c1:
            city = st.selectbox(t("common.city", lang), merchants.MOROCCAN_CITIES)
        with c2:
            neighborhood = st.selectbox(t("common.neighborhood", lang), merchants.AGADIR_NEIGHBORHOODS)

        business_name = business_phone = address = category = description = ""
        points_rule = 10
        if not is_client:
            st.markdown(f"**{t('auth.business_section', lang)}**")
            business_name = st.text_input(t("auth.business_name", lang))
            c1, c2 = st.columns(2)
            with c1:
                business_phone = st.text_input(
                    t("auth.business_phone", lang), value=phone, placeholder=t("auth.phone_placeholder", lang)
                )
            with c2:
                category = st.selectbox(t("auth.business_category", lang), merchants.BUSINESS_CATEGORIES)
            address = st.text_input(t("auth.business_address", lang))
            description = st.text_area(t("auth.business_description", lang), height=80)
            points_rule = st.number_input(
                t("auth.points_rule", lang),
                min_value=1.0,
                max_value=1000.0,
                value=10.0,
                step=1.0,
                help=t("auth.points_rule_hint", lang),
            )

        accepted = st.checkbox(t("auth.accept_terms", lang))
        submitted = st.form_submit_button(
            t("auth.submit_client" if is_client else "auth.submit_merchant", lang),
            type="primary",
            width="stretch",
        )

    if submitted and not accepted:
        st.error(t("auth.terms_required", lang))
    elif submitted:
        try:
            with database.session() as session:
                if is_client:
                    user = auth.register_client(
                        session,
                        first_name=first_name,
                        last_name=last_name,
                        phone=phone,
                        password=password,
                        city=city,
                        neighborhood=neighborhood,
                        email=email or None,
                        preferred_language=Language(current_lang()),
                    )
                else:
                    user, _merchant = auth.register_merchant_owner(
                        session,
                        first_name=first_name,
                        last_name=last_name,
                        phone=phone,
                        password=password,
                        city=city,
                        neighborhood=neighborhood,
                        email=email or None,
                        preferred_language=Language(current_lang()),
                        business_name=business_name,
                        business_phone=business_phone or phone,
                        address=address,
                        category=category,
                        description=description,
                        points_per_amount=points_rule,
                    )
            login_user(user)
            st.rerun()
        except Exception as error:
            ui.show_error(error, lang)


def render_auth() -> None:
    lang = current_lang()
    _auth_header(lang)
    mode = SS.get("auth_mode", "login")
    role = SS.get("auth_role", "CLIENT")

    aside, form = st.columns([1.02, 1.15], gap="large")
    with aside:
        st.markdown(
            f"""
<div class="wafa-auth-aside">
  <div class="wafa-chip">{icon_svg("sparkles", 14)} {esc(t("landing.hero.eyebrow", lang))}</div>
  <h2 style="margin:1rem 0 .7rem">{esc(t("auth.title", lang))}</h2>
  <p>{esc(t("auth.subtitle", lang))}</p>
  <div style="height:1rem"></div>
  <div style="display:flex;gap:.65rem;align-items:flex-start;margin:.7rem 0">
    <div style="color:#F4C66A">{icon_svg("check-circle", 20)}</div>
    <div style="font-size:.83rem;color:#D7E6F4">{esc(t("landing.features.card1_text", lang))}</div>
  </div>
  <div style="display:flex;gap:.65rem;align-items:flex-start;margin:.7rem 0">
    <div style="color:#F4C66A">{icon_svg("check-circle", 20)}</div>
    <div style="font-size:.83rem;color:#D7E6F4">{esc(t("landing.features.card2_text", lang))}</div>
  </div>
  <div style="display:flex;gap:.65rem;align-items:flex-start;margin:.7rem 0">
    <div style="color:#F4C66A">{icon_svg("check-circle", 20)}</div>
    <div style="font-size:.83rem;color:#D7E6F4">{esc(t("landing.features.card3_text", lang))}</div>
  </div>
  <div style="margin-top:1.4rem;padding-top:1rem;border-top:1px solid rgba(255,255,255,.16);font-size:.73rem;color:#B9D2EA">
    {esc(t("app.slogan", lang))}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    with form:
        mode_cols = st.columns(2)
        with mode_cols[0]:
            if st.button(
                t("common.login", lang),
                type="primary" if mode == "login" else "secondary",
                width="stretch",
                key="mode_login",
            ):
                SS["auth_mode"] = "login"
                st.rerun()
        with mode_cols[1]:
            if st.button(
                t("common.signup", lang),
                type="primary" if mode == "signup" else "secondary",
                width="stretch",
                key="mode_signup",
            ):
                SS["auth_mode"] = "signup"
                st.rerun()

        role = _role_selector(lang, mode)

        if mode == "login":
            _login_form(lang, role)
        else:
            _signup_form(lang, role)

        st.markdown("<div class='wafa-divider'></div>", unsafe_allow_html=True)
        _demo_box(lang)
        st.markdown(
            f'<div class="wafa-small" style="margin-top:.8rem">{esc(t("common.legal_note", lang))}</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="wafa-legal">{esc(t("landing.footer.legal", lang))} · WafaClub</div>',
        unsafe_allow_html=True,
    )
