"""État de session Streamlit et helpers d'authentification UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import streamlit as st

from ..access import default_page
from ..db import database
from ..i18n import SUPPORTED_LANGUAGES, language_label, normalize_language
from ..models import Language, User, UserRole
from ..services import auth, merchants

SS = st.session_state


@dataclass(frozen=True)
class SessionUser:
    id: int
    first_name: str
    last_name: str
    phone: str
    email: str | None
    role: UserRole
    preferred_language: str
    city: str
    neighborhood: str
    created_at: datetime
    is_active: bool

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def initials(self) -> str:
        return f"{self.first_name[:1]}{self.last_name[:1]}".upper()

    @property
    def is_client(self) -> bool:
        return self.role == UserRole.CLIENT

    @property
    def is_merchant(self) -> bool:
        return self.role == UserRole.MERCHANT

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN


def init_state() -> None:
    defaults: dict[str, Any] = {
        "lang": "fr",
        "view": "landing",
        "user_id": None,
        "merchant_id": None,
        "page": None,
        "ctx": {},
        "page_history": [],
        "flash": None,
        "auth_mode": "login",
        "auth_role": "CLIENT",
        "pending_reward_id": None,
        "pending_gift": None,
        "last_redemption_code": None,
        "last_gift_code": None,
        "target_client_id": None,
        "scan_message": None,
        "last_purchase": None,
        "last_validation": None,
        "last_gift_validation": None,
        "verified_gift": None,
    }
    for key, value in defaults.items():
        if key not in SS:
            SS[key] = value
    if not isinstance(SS.get("page_history"), list):
        SS["page_history"] = []
    if SS.get("view") == "app" and SS.get("user_id") and not SS["page_history"]:
        SS["page_history"].append(
            {
                "view": "auth",
                "auth_mode": "login",
                "auth_role": "CLIENT",
                "page": None,
                "ctx": {},
            }
        )


def current_lang() -> str:
    return normalize_language(SS.get("lang", "fr"))


def set_language(lang: str, user_id: int | None = None) -> None:
    language = normalize_language(lang)
    SS["lang"] = language
    if user_id:
        try:
            with database.session() as session:
                auth.set_language(session, user_id, Language(language))
        except Exception:
            # Le changement de langue ne doit jamais bloquer la navigation.
            pass


def language_selector(*, key: str, user_id: int | None = None, label: str | None = None) -> None:
    current = current_lang()
    options = list(SUPPORTED_LANGUAGES)
    labels = {code: language_label(code) for code in options}
    selected_label = st.selectbox(
        label or t_lang("nav.language"),
        options=[labels[code] for code in options],
        index=options.index(current),
        key=f"{key}_{current}",
        label_visibility="visible" if label else "collapsed",
    )
    selected = next((code for code, label_value in labels.items() if label_value == selected_label), current)
    if selected != current:
        set_language(selected, user_id)
        st.rerun()


def t_lang(key: str, **kwargs: object) -> str:
    from ..i18n import t

    return t(key, current_lang(), **kwargs)


def load_current_user() -> SessionUser | None:
    user_id = SS.get("user_id")
    if not user_id:
        return None
    try:
        with database.session() as session:
            user = session.get(User, user_id)
            if not user or not user.is_active:
                SS["user_id"] = None
                return None
            return SessionUser(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                phone=user.phone,
                email=user.email,
                role=user.role,
                preferred_language=user.preferred_language.value,
                city=user.city,
                neighborhood=user.neighborhood,
                created_at=user.created_at,
                is_active=user.is_active,
            )
    except Exception:
        return None


def login_user(user: User) -> None:
    previous_view = SS.get("view", "auth")
    previous_mode = SS.get("auth_mode", "login")
    SS["user_id"] = user.id
    SS["lang"] = user.preferred_language.value
    SS["view"] = "app"
    SS["page"] = default_page(user.role)
    SS["merchant_id"] = None
    SS["flash"] = None
    SS["ctx"] = {}
    SS["page_history"] = [
        {
            "view": previous_view if previous_view in {"landing", "auth"} else "auth",
            "auth_mode": previous_mode,
            "auth_role": user.role.value if user.role in {UserRole.CLIENT, UserRole.MERCHANT} else "CLIENT",
            "page": None,
            "ctx": {},
        }
    ]
    if user.role == UserRole.MERCHANT:
        try:
            with database.session() as session:
                owned = merchants.owned_merchants(session, user.id)
                SS["merchant_id"] = owned[0].id if owned else None
        except Exception:
            SS["merchant_id"] = None
    elif user.role == UserRole.CLIENT:
        SS["page"] = "client.dashboard"


def logout() -> None:
    for key in (
        "user_id",
        "merchant_id",
        "page",
        "page_history",
        "ctx",
        "flash",
        "pending_reward_id",
        "pending_gift",
        "last_redemption_code",
        "last_gift_code",
        "target_client_id",
        "scan_message",
        "last_purchase",
        "last_validation",
        "last_gift_validation",
        "verified_gift",
    ):
        SS[key] = [] if key == "page_history" else {} if key == "ctx" else None
    SS["view"] = "landing"
    SS["auth_mode"] = "login"
    SS["auth_role"] = "CLIENT"


def goto(page: str, **context: Any) -> None:
    navigate_to(page, context)
    st.rerun()


def navigate_to(page: str, context: dict[str, Any] | None = None) -> None:
    next_context = context or {}
    current_page = SS.get("page")
    current_context = dict(SS.get("ctx") or {})
    if current_page and (current_page != page or current_context != next_context):
        history = SS.get("page_history")
        if not isinstance(history, list):
            history = []
            SS["page_history"] = history
        history.append({"view": "app", "page": current_page, "ctx": current_context})
        del history[:-50]
    SS["page"] = page
    SS["ctx"] = next_context


def go_back(fallback_page: str) -> None:
    history = SS.get("page_history", [])
    if not isinstance(history, list):
        history = []
        SS["page_history"] = history
    if history:
        previous = history.pop()
        previous_view = previous.get("view", "app")
        SS["view"] = previous_view
        if previous_view == "app":
            SS["page"] = previous["page"]
            SS["ctx"] = previous["ctx"]
        else:
            SS["auth_mode"] = previous.get("auth_mode", "login")
            SS["auth_role"] = previous.get("auth_role", "CLIENT")
            SS["ctx"] = {}
    else:
        SS["page"] = fallback_page
        SS["ctx"] = {}


def context(key: str, default: Any = None) -> Any:
    return SS.get("ctx", {}).get(key, default)


def flash(message: str, kind: str = "success") -> None:
    SS["flash"] = {"kind": kind, "message": message}


def show_flash() -> None:
    payload = SS.get("flash")
    if not payload:
        return
    SS["flash"] = None
    kind = payload.get("kind", "success")
    message = payload.get("message", "")
    if kind == "success":
        st.success(message)
    elif kind == "warning":
        st.warning(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)


def merchant_name(merchant_id: int) -> str | None:
    try:
        with database.session() as session:
            merchant = session.get(merchants.Merchant, merchant_id)
            return merchant.business_name if merchant else None
    except Exception:
        return None
