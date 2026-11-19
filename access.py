"""Contrôle d'accès centralisé aux pages Streamlit (testable sans interface)."""

from __future__ import annotations

from .errors import AccessDenied
from .models import User, UserRole

CLIENT_PAGES = frozenset(
    {
        "client.dashboard",
        "client.card",
        "client.points",
        "client.rewards",
        "client.reward_detail",
        "client.reward_confirm",
        "client.reward_success",
        "client.my_rewards",
        "client.promotions",
        "client.promotion_detail",
        "client.merchants",
        "client.merchant_detail",
        "client.gift_cards",
        "client.gift_create",
        "client.gift_confirm",
        "client.gift_success",
        "client.notifications",
        "client.profile",
        "client.settings",
        "client.help",
    }
)

MERCHANT_PAGES = frozenset(
    {
        "merchant.dashboard",
        "merchant.add_points",
        "merchant.validate_reward",
        "merchant.clients",
        "merchant.transactions",
        "merchant.rewards",
        "merchant.reward_form",
        "merchant.gift_cards",
        "merchant.promotions",
        "merchant.promotion_form",
        "merchant.stats",
        "merchant.profile",
        "merchant.settings",
        "merchant.notifications",
    }
)

ADMIN_PAGES = frozenset(
    {
        "admin.dashboard",
        "admin.users",
        "admin.merchants",
        "admin.transactions",
        "admin.gift_cards",
        "admin.promotions",
    }
)

PAGE_ROLES: dict[str, frozenset[UserRole]] = {
    **{page: frozenset({UserRole.CLIENT}) for page in CLIENT_PAGES},
    **{page: frozenset({UserRole.MERCHANT}) for page in MERCHANT_PAGES},
    **{page: frozenset({UserRole.ADMIN}) for page in ADMIN_PAGES},
}


def can_access(role: UserRole | str, page_key: str) -> bool:
    try:
        normalized = role if isinstance(role, UserRole) else UserRole(str(role))
    except ValueError:
        return False
    return normalized in PAGE_ROLES.get(page_key, frozenset())


def require_page_access(user: User, page_key: str) -> None:
    if not user.is_active:
        raise AccessDenied("Ce compte est désactivé.", code="account_disabled")
    if not can_access(user.role, page_key):
        raise AccessDenied(
            "Cette page est réservée à un autre type de compte.",
            code="page_forbidden",
        )


def default_page(role: UserRole) -> str:
    return {
        UserRole.CLIENT: "client.dashboard",
        UserRole.MERCHANT: "merchant.dashboard",
        UserRole.ADMIN: "admin.dashboard",
    }[role]
