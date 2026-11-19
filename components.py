"""Composants visuels réutilisables."""

from __future__ import annotations

from collections.abc import Iterable
from html import escape

import streamlit as st

from ..errors import WafaClubError
from ..i18n import format_date, format_datetime, format_mad, format_points, has_translation, status_key, t
from .icons import esc, icon_svg

TONE_MAP = {
    "blue": "blue",
    "green": "green",
    "gold": "gold",
    "red": "red",
    "navy": "navy",
    "gray": "gray",
}


def logo(*, dark: bool = False, slogan: bool = False, compact: bool = False) -> None:
    slogan_html = f'<div class="wafa-logo-slogan">{esc(t("app.slogan_short"))}</div>' if slogan and not compact else ""
    classes = "wafa-logo on-dark" if dark else "wafa-logo"
    st.markdown(
        f"""
<div class="wafa-logo-wrap">
  <div class="{classes}">
    <div class="wafa-logo-mark">W</div>
    <div>
      <div class="wafa-logo-text">Wafa<span>Club</span></div>
      {slogan_html}
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str | None = None, eyebrow: str | None = None) -> None:
    if eyebrow:
        st.markdown(f'<div class="wafa-eyebrow">{esc(eyebrow)}</div>', unsafe_allow_html=True)
    st.markdown(f'<h1 class="wafa-page-title">{esc(title)}</h1>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<p class="wafa-page-subtitle">{esc(subtitle)}</p>', unsafe_allow_html=True)


def section_title(title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<div class="wafa-section-title">{esc(title)}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="wafa-section-subtitle">{esc(subtitle)}</div>', unsafe_allow_html=True)


def badge(label: str, tone: str = "blue") -> str:
    tone = TONE_MAP.get(tone, "blue")
    return f'<span class="wafa-badge {tone}">{esc(label)}</span>'


def status_badge(status: object, lang: str = "fr") -> str:
    value = getattr(status, "value", status)
    tone = {
        "ACTIVE": "green",
        "PENDING": "gold",
        "USED": "blue",
        "EXPIRED": "gray",
        "CANCELLED": "red",
    }.get(str(value).upper(), "gray")
    return badge(t(status_key(status), lang), tone)


def stat_card(
    label: str,
    value: str,
    *,
    hint: str | None = None,
    icon: str = "sparkles",
    tone: str = "blue",
) -> None:
    hint_html = f'<div class="wafa-stat-hint">{esc(hint)}</div>' if hint else ""
    st.markdown(
        f"""
<div class="wafa-card wafa-stat">
  <div class="wafa-stat-top">
    <div class="wafa-stat-label">{esc(label)}</div>
    <div class="wafa-icon {esc(tone)}">{icon_svg(icon, 19)}</div>
  </div>
  <div class="wafa-stat-value">{esc(value)}</div>
  {hint_html}
</div>
""",
        unsafe_allow_html=True,
    )


def feature_card(icon: str, title: str, text: str, *, tone: str = "blue") -> None:
    st.markdown(
        f"""
<div class="wafa-card wafa-feature">
  <div class="wafa-icon {esc(tone)}" style="margin-bottom:.7rem">{icon_svg(icon, 20)}</div>
  <h4>{esc(title)}</h4>
  <p>{esc(text)}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def empty_state(title: str, text: str, icon: str = "sparkles") -> None:
    st.markdown(
        f"""
<div class="wafa-empty">
  <div class="icon">{icon_svg(icon, 23)}</div>
  <h4>{esc(title)}</h4>
  <p>{esc(text)}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def progress_bar(value: float, *, dark: bool = False) -> str:
    pct = max(0.0, min(1.0, validity(value))) * 100
    cls = "wafa-progress dark" if dark else "wafa-progress"
    return f'<div class="{cls}"><span style="width:{pct:.1f}%"></span></div>'


def validity(value: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def code_box(code: str, *, light: bool = False) -> None:
    cls = "wafa-code light" if light else "wafa-code"
    st.markdown(f'<div class="{cls}">{esc(code)}</div>', unsafe_allow_html=True)


def review_line(label: str, value: str) -> str:
    return f'<div class="wafa-line"><span>{esc(label)}</span><strong>{esc(value)}</strong></div>'


def money(amount: object, lang: str = "fr") -> str:
    return format_mad(amount, lang)


def points(points_value: int, lang: str = "fr") -> str:
    return f"{format_points(points_value, lang)} {t('common.points', lang)}"


def error_text(error: Exception, lang: str = "fr") -> str:
    if isinstance(error, WafaClubError):
        key = f"errors.{error.code}"
        if has_translation(key, lang):
            return t(key, lang)
        return error.message
    key = "errors.generic"
    return t(key, lang) if has_translation(key, lang) else str(error)


def show_error(error: Exception, lang: str = "fr") -> None:
    st.error(error_text(error, lang))


def type_badge(transaction_type: object, lang: str = "fr") -> str:
    value = getattr(transaction_type, "value", transaction_type)
    label = t(f"transaction.{str(value).upper()}", lang)
    tone = {
        "EARNED": "green",
        "REDEEMED": "gold",
        "ADJUSTMENT": "blue",
        "EXPIRED": "gray",
        "REFUND": "red",
    }.get(str(value).upper(), "gray")
    return badge(label, tone)


def date_label(value, lang: str = "fr") -> str:
    return format_date(value, lang)


def datetime_label(value, lang: str = "fr") -> str:
    return format_datetime(value, lang)


def legal_note(lang: str = "fr") -> None:
    st.markdown(
        f"""
<div class="wafa-legal">
  <strong>{esc(t("app.prototype", lang))} · {esc(t("app.simulated", lang))} · {esc(t("app.version", lang))}</strong><br/>
  {esc(t("common.legal_note", lang))}
</div>
""",
        unsafe_allow_html=True,
    )


def notification_card(notification, lang: str = "fr") -> None:
    unread = not notification.is_read
    css = "wafa-notification unread" if unread else "wafa-notification"
    dot = '<span class="dot"></span>' if unread else ""
    st.markdown(
        f"""
<div class="{css}">
  {dot}
  <div style="flex:1">
    <div class="wafa-row" style="align-items:flex-start">
      <strong style="font-size:.86rem">{esc(notification.title)}</strong>
      <span class="wafa-small">{esc(format_datetime(notification.created_at, lang))}</span>
    </div>
    <div class="wafa-muted" style="margin-top:.25rem;line-height:1.55">{esc(notification.message)}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def info_banner(title: str, text: str, *, tone: str = "blue", icon: str = "shield") -> None:
    st.markdown(
        f"""
<div class="wafa-card tight" style="border-left:4px solid {"#1E6FA8" if tone == "blue" else "#D99A2B"}">
  <div style="display:flex;gap:.75rem;align-items:flex-start">
    <div class="wafa-icon {esc(tone)}" style="width:34px;height:34px;border-radius:11px">{icon_svg(icon, 17)}</div>
    <div>
      <strong style="font-size:.83rem">{esc(title)}</strong>
      <div class="wafa-muted" style="margin-top:.15rem;line-height:1.55">{esc(text)}</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def cards_grid(items: Iterable[str], columns: int = 3) -> None:
    cols = st.columns(columns, gap="medium")
    for index, html in enumerate(items):
        with cols[index % columns]:
            st.markdown(html, unsafe_allow_html=True)


def escape_html(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)
