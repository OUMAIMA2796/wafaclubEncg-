from __future__ import annotations

import pytest

from wafaclub.errors import AuthError
from wafaclub.models import LoginAttempt, Notification, UserRole, utcnow
from wafaclub.security import normalize_moroccan_phone, verify_password
from wafaclub.services import auth

from .conftest import make_client, make_merchant


def test_register_client_generates_qr_and_hashes_password(session):
    user = make_client(session)
    assert user.phone == "+212661000001"
    assert user.role == UserRole.CLIENT
    assert user.password_hash.startswith("scrypt$")
    assert user.password_hash != "Test2026!"
    assert verify_password("Test2026!", user.password_hash)
    assert user.loyalty_account is not None
    assert len(user.loyalty_account.qr_code_token) >= 20
    assert session.query(Notification).filter_by(user_id=user.id).count() == 1


def test_phone_normalization_accepts_moroccan_formats():
    assert normalize_moroccan_phone("06 61 23 45 67") == "+212661234567"
    assert normalize_moroccan_phone("00212661234567") == "+212661234567"
    assert normalize_moroccan_phone("+212 661 234 567") == "+212661234567"


def test_login_and_role_control(session):
    client = make_client(session)
    _, _ = make_merchant(session)

    logged = auth.authenticate(session, phone=client.phone, password="Test2026!", expected_role=UserRole.CLIENT)
    assert logged.id == client.id

    with pytest.raises(AuthError) as error:
        auth.authenticate(session, phone=client.phone, password="Test2026!", expected_role=UserRole.MERCHANT)
    assert error.value.code == "invalid_credentials"


def test_login_is_rate_limited_after_failures(session):
    client = make_client(session)
    for _ in range(5):
        with pytest.raises(AuthError):
            auth.authenticate(session, phone=client.phone, password="Wrong2026!", expected_role=UserRole.CLIENT)
    with pytest.raises(AuthError) as error:
        auth.authenticate(session, phone=client.phone, password="Test2026!", expected_role=UserRole.CLIENT)
    assert error.value.code == "account_locked"
    assert session.query(LoginAttempt).filter_by(phone=client.phone, success=False).count() == 5


def test_duplicate_phone_is_rejected(session):
    make_client(session)
    from wafaclub.errors import ConflictError

    with pytest.raises(ConflictError) as error:
        make_client(session)
    assert error.value.code == "phone_exists"


def test_merchant_registration_creates_business(session):
    owner, merchant = make_merchant(session, points_per_amount=12)
    assert owner.role == UserRole.MERCHANT
    assert merchant.owner_id == owner.id
    assert float(merchant.points_per_amount) == 12
    assert merchant.is_active is True
    assert utcnow() >= merchant.created_at
