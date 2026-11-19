from __future__ import annotations

import pytest

from wafaclub.access import PAGE_ROLES, can_access, default_page, require_page_access
from wafaclub.errors import AccessDenied
from wafaclub.models import UserRole
from wafaclub.services import merchants

from .conftest import make_client, make_merchant


def test_client_cannot_access_merchant_page(session):
    client = make_client(session)
    with pytest.raises(AccessDenied) as error:
        require_page_access(client, "merchant.dashboard")
    assert error.value.code == "page_forbidden"


def test_merchant_cannot_access_client_or_admin_pages(session):
    owner, _ = make_merchant(session)
    assert can_access(owner.role, "merchant.dashboard")
    assert not can_access(owner.role, "client.dashboard")
    assert not can_access(owner.role, "admin.dashboard")


def test_admin_access_is_separate(session):
    assert can_access(UserRole.ADMIN, "admin.dashboard")
    assert not can_access(UserRole.ADMIN, "client.dashboard")
    assert default_page(UserRole.ADMIN) == "admin.dashboard"


def test_unknown_page_is_denied():
    assert not can_access(UserRole.CLIENT, "admin.secret")
    assert "admin.dashboard" in PAGE_ROLES


def test_only_admin_can_toggle_merchant(session):
    client = make_client(session)
    owner, merchant = make_merchant(session)
    with pytest.raises(AccessDenied) as error:
        merchants.set_active(session, merchant.id, active=False, actor=client)
    assert error.value.code == "admin_only"
    with pytest.raises(AccessDenied):
        merchants.set_active(session, merchant.id, active=False, actor=owner)


def test_merchant_profile_cannot_be_edited_by_another_merchant(session):
    owner, merchant = make_merchant(session)
    other_owner, _ = make_merchant(session, owner_phone="+212661000096", business_name="Autre")
    with pytest.raises(AccessDenied):
        merchants.update_profile(
            session,
            merchant.id,
            other_owner,
            business_name="Piraté",
            description="",
            phone="+212522000000",
            address="",
            city="Rabat",
            neighborhood="Agdal",
            category="Café",
            points_per_amount=10,
        )
