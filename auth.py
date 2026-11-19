"""Authentification, inscription et gestion de profil."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..errors import AuthError, ConflictError, NotFoundError, ValidationError
from ..models import Language, LoginAttempt, LoyaltyAccount, NotificationType, User, UserRole, utcnow
from ..security import (
    DUMMY_PASSWORD_HASH,
    generate_qr_token,
    hash_password,
    normalize_moroccan_phone,
    validate_email,
    validate_password_strength,
    verify_password,
)
from . import audit, merchants, notifications


def _clean_name(value: str, field: str) -> str:
    cleaned = (value or "").strip()
    if len(cleaned) < 2:
        raise ValidationError(f"Le {field} est obligatoire.", code="name_required")
    if len(cleaned) > 80:
        raise ValidationError(f"Le {field} est trop long.", code="name_too_long")
    return cleaned


def _unique_qr_token(session: Session) -> str:
    for _ in range(8):
        token = generate_qr_token()
        exists = session.scalar(select(LoyaltyAccount.id).where(LoyaltyAccount.qr_code_token == token))
        if not exists:
            return token
    raise ConflictError("Impossible de générer un QR code unique.", code="qr_generation_failed")


def _ensure_phone_available(session: Session, phone: str) -> None:
    existing = session.scalar(select(User.id).where(User.phone == phone))
    if existing:
        raise ConflictError("Un compte existe déjà avec ce numéro.", code="phone_exists")


def _ensure_email_available(session: Session, email: str | None) -> None:
    if not email:
        return
    existing = session.scalar(select(User.id).where(User.email == email))
    if existing:
        raise ConflictError("Un compte existe déjà avec cet e-mail.", code="email_exists")


def register_client(
    session: Session,
    *,
    first_name: str,
    last_name: str,
    phone: str,
    password: str,
    city: str,
    neighborhood: str = "",
    email: str | None = None,
    preferred_language: str | Language = Language.FR,
) -> User:
    first = _clean_name(first_name, "prénom")
    last = _clean_name(last_name, "nom")
    normalized_phone = normalize_moroccan_phone(phone)
    validate_password_strength(password)
    clean_email = validate_email(email)
    _ensure_phone_available(session, normalized_phone)
    _ensure_email_available(session, clean_email)
    if not (city or "").strip():
        raise ValidationError("La ville est obligatoire.", code="city_required")

    user = User(
        first_name=first,
        last_name=last,
        phone=normalized_phone,
        email=clean_email,
        password_hash=hash_password(password),
        role=UserRole.CLIENT,
        preferred_language=Language(preferred_language),
        city=city.strip(),
        neighborhood=(neighborhood or "").strip(),
    )
    session.add(user)
    session.flush()
    session.add(
        LoyaltyAccount(
            user_id=user.id,
            total_points=0,
            qr_code_token=_unique_qr_token(session),
        )
    )
    notifications.notify(
        session,
        user.id,
        type=NotificationType.WELCOME,
        title="Bienvenue dans WafaClub",
        message=(
            "Votre carte de fidélité numérique est prête. Présentez votre QR code "
            "chez les commerces partenaires pour cumuler vos premiers points."
        ),
        link_page="client.card",
    )
    audit.record(
        session,
        actor_id=user.id,
        action="CLIENT_REGISTERED",
        entity_type="User",
        entity_id=user.id,
        metadata={"city": user.city},
    )
    session.flush()
    return user


def register_merchant_owner(
    session: Session,
    *,
    first_name: str,
    last_name: str,
    phone: str,
    password: str,
    city: str,
    neighborhood: str,
    email: str | None = None,
    preferred_language: str | Language = Language.FR,
    business_name: str,
    business_phone: str,
    address: str,
    category: str,
    description: str = "",
    points_per_amount: float | str = 10,
) -> tuple[User, merchants.Merchant]:
    first = _clean_name(first_name, "prénom")
    last = _clean_name(last_name, "nom")
    normalized_phone = normalize_moroccan_phone(phone)
    validate_password_strength(password)
    clean_email = validate_email(email)
    _ensure_phone_available(session, normalized_phone)
    _ensure_email_available(session, clean_email)
    if not (city or "").strip():
        raise ValidationError("La ville est obligatoire.", code="city_required")

    owner = User(
        first_name=first,
        last_name=last,
        phone=normalized_phone,
        email=clean_email,
        password_hash=hash_password(password),
        role=UserRole.MERCHANT,
        preferred_language=Language(preferred_language),
        city=city.strip(),
        neighborhood=(neighborhood or "").strip(),
    )
    session.add(owner)
    session.flush()
    business = merchants.create_merchant(
        session,
        owner_id=owner.id,
        business_name=business_name,
        description=description,
        phone=business_phone,
        address=address,
        city=city,
        neighborhood=neighborhood,
        category=category,
        points_per_amount=points_per_amount,
    )
    notifications.notify(
        session,
        owner.id,
        type=NotificationType.WELCOME,
        title="Bienvenue dans WafaClub Pro",
        message=(
            f"Votre espace {business.business_name} est prêt. Ajoutez des points à vos clients "
            "et créez vos premières récompenses."
        ),
        link_page="merchant.dashboard",
    )
    audit.record(
        session,
        actor_id=owner.id,
        action="MERCHANT_REGISTERED",
        entity_type="Merchant",
        entity_id=business.id,
        metadata={"business_name": business.business_name, "city": business.city},
    )
    session.flush()
    return owner, business


def _recent_failures(session: Session, phone: str) -> int:
    since = utcnow() - timedelta(minutes=settings.login_window_minutes)
    last_success = session.scalar(
        select(func.max(LoginAttempt.created_at)).where(
            LoginAttempt.phone == phone,
            LoginAttempt.success.is_(True),
            LoginAttempt.created_at >= since,
        )
    )
    start = last_success or since
    return int(
        session.scalar(
            select(func.count(LoginAttempt.id)).where(
                LoginAttempt.phone == phone,
                LoginAttempt.success.is_(False),
                LoginAttempt.created_at > start,
            )
        )
        or 0
    )


def authenticate(
    session: Session,
    *,
    phone: str,
    password: str,
    expected_role: UserRole | str | None = None,
) -> User:
    """Authentifie un utilisateur et journalise la tentative.

    Cette fonction commit elle-même les tentatives afin que la limitation de débit
    reste effective même lorsque l'erreur est présentée à l'utilisateur.
    """
    normalized_phone = normalize_moroccan_phone(phone)
    if _recent_failures(session, normalized_phone) >= settings.login_max_attempts:
        raise AuthError(
            "Trop de tentatives. Réessayez dans quelques minutes.",
            code="account_locked",
        )

    user = session.scalar(select(User).where(User.phone == normalized_phone))
    password_ok = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)

    role_value = None
    if expected_role is not None:
        role_value = expected_role.value if isinstance(expected_role, UserRole) else str(expected_role)

    valid = bool(user and password_ok)
    if valid and role_value and user.role.value != role_value.upper():
        valid = False
    if valid and not user.is_active:
        session.add(LoginAttempt(phone=normalized_phone, success=False))
        session.commit()
        raise AuthError("Ce compte est désactivé.", code="account_disabled")

    if not valid:
        session.add(LoginAttempt(phone=normalized_phone, success=False))
        session.commit()
        raise AuthError("Numéro ou mot de passe incorrect.", code="invalid_credentials")

    user.last_login_at = utcnow()
    session.add(LoginAttempt(phone=normalized_phone, success=True))
    audit.record(
        session,
        actor_id=user.id,
        action="LOGIN_SUCCESS",
        entity_type="User",
        entity_id=user.id,
        metadata={"role": user.role.value},
    )
    session.commit()
    return user


def get_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if not user:
        raise NotFoundError("Utilisateur introuvable.", code="user_not_found")
    return user


def update_client_profile(
    session: Session,
    user_id: int,
    *,
    first_name: str,
    last_name: str,
    email: str | None,
    city: str,
    neighborhood: str,
) -> User:
    user = get_user(session, user_id)
    if user.role != UserRole.CLIENT:
        raise ValidationError("Profil client attendu.", code="client_only")
    clean_email = validate_email(email)
    if clean_email != user.email:
        _ensure_email_available(session, clean_email)
    user.first_name = _clean_name(first_name, "prénom")
    user.last_name = _clean_name(last_name, "nom")
    user.email = clean_email
    user.city = (city or "").strip() or user.city
    user.neighborhood = (neighborhood or "").strip()
    audit.record(
        session,
        actor_id=user.id,
        action="CLIENT_PROFILE_UPDATED",
        entity_type="User",
        entity_id=user.id,
    )
    return user


def set_language(session: Session, user_id: int, language: str | Language) -> User:
    user = get_user(session, user_id)
    user.preferred_language = Language(language)
    return user


def require_active(user: User) -> User:
    if not user.is_active:
        raise AuthError("Ce compte est désactivé.", code="account_disabled")
    return user
