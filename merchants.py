"""Gestion des commerces partenaires."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..errors import AccessDenied, NotFoundError, ValidationError
from ..models import Merchant, User, UserRole
from ..security import normalize_moroccan_phone, to_decimal
from . import audit

MOROCCAN_CITIES = ("Agadir",)
AGADIR_NEIGHBORHOODS = (
    "Talborjt",
    "Founty",
    "Haut Founty",
    "Hay Mohammadi",
    "Dakhla",
    "Al Houda",
    "Salam",
    "Charaf",
    "Bensergao",
    "Tikiouine",
    "Anza",
    "Tilila",
)
BUSINESS_CATEGORIES = (
    "Café",
    "Épicerie",
    "Supérette",
    "Pâtisserie",
    "Restaurant",
    "Traiteur",
    "Librairie",
    "Beauté",
    "Autre",
)


def get_merchant(session: Session, merchant_id: int) -> Merchant:
    merchant = session.get(Merchant, merchant_id)
    if not merchant:
        raise NotFoundError("Commerce introuvable.", code="merchant_not_found")
    return merchant


def owned_merchants(session: Session, owner_id: int) -> list[Merchant]:
    stmt = select(Merchant).where(Merchant.owner_id == owner_id).order_by(Merchant.business_name)
    return list(session.scalars(stmt))


def list_merchants(
    session: Session,
    *,
    city: str | None = None,
    category: str | None = None,
    search: str | None = None,
    active_only: bool = True,
) -> list[Merchant]:
    stmt = select(Merchant)
    if active_only:
        stmt = stmt.where(Merchant.is_active.is_(True))
    if city:
        stmt = stmt.where(Merchant.city == city)
    if category:
        stmt = stmt.where(Merchant.category == category)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Merchant.business_name.ilike(like),
                Merchant.neighborhood.ilike(like),
                Merchant.city.ilike(like),
                Merchant.category.ilike(like),
            )
        )
    stmt = stmt.order_by(Merchant.business_name)
    return list(session.scalars(stmt))


def assert_manage_access(session: Session, merchant_id: int, actor: User) -> Merchant:
    merchant = get_merchant(session, merchant_id)
    if actor.role == UserRole.ADMIN:
        return merchant
    if actor.role != UserRole.MERCHANT or merchant.owner_id != actor.id:
        raise AccessDenied("Vous ne gérez pas ce commerce.", code="merchant_access_denied")
    return merchant


def create_merchant(
    session: Session,
    *,
    owner_id: int,
    business_name: str,
    description: str,
    phone: str,
    address: str,
    city: str,
    neighborhood: str,
    category: str,
    points_per_amount: Decimal | str | float | int = Decimal("10.00"),
) -> Merchant:
    name = (business_name or "").strip()
    if len(name) < 2:
        raise ValidationError("Le nom du commerce est obligatoire.", code="merchant_name_required")
    if not (city or "").strip():
        raise ValidationError("La ville est obligatoire.", code="city_required")
    if not (category or "").strip():
        raise ValidationError("La catégorie est obligatoire.", code="category_required")
    rule = to_decimal(points_per_amount)
    if rule <= 0:
        raise ValidationError(
            "Le montant nécessaire pour gagner 1 point doit être supérieur à 0.",
            code="invalid_points_rule",
        )
    merchant = Merchant(
        owner_id=owner_id,
        business_name=name,
        description=(description or "").strip(),
        phone=normalize_moroccan_phone(phone),
        address=(address or "").strip(),
        city=city.strip(),
        neighborhood=(neighborhood or "").strip(),
        category=category.strip(),
        points_per_amount=rule,
    )
    session.add(merchant)
    session.flush()
    return merchant


def update_profile(
    session: Session,
    merchant_id: int,
    actor: User,
    *,
    business_name: str,
    description: str,
    phone: str,
    address: str,
    city: str,
    neighborhood: str,
    category: str,
    points_per_amount: Decimal | str | float | int,
) -> Merchant:
    merchant = assert_manage_access(session, merchant_id, actor)
    name = (business_name or "").strip()
    if len(name) < 2:
        raise ValidationError("Le nom du commerce est obligatoire.", code="merchant_name_required")
    if not (city or "").strip():
        raise ValidationError("La ville est obligatoire.", code="city_required")
    rule = to_decimal(points_per_amount)
    if rule <= 0:
        raise ValidationError(
            "Le montant nécessaire pour gagner 1 point doit être supérieur à 0.",
            code="invalid_points_rule",
        )
    merchant.business_name = name
    merchant.description = (description or "").strip()
    merchant.phone = normalize_moroccan_phone(phone)
    merchant.address = (address or "").strip()
    merchant.city = city.strip()
    merchant.neighborhood = (neighborhood or "").strip()
    merchant.category = category.strip()
    merchant.points_per_amount = rule
    audit.record(
        session,
        actor_id=actor.id,
        action="MERCHANT_PROFILE_UPDATED",
        entity_type="Merchant",
        entity_id=merchant.id,
        metadata={"business_name": merchant.business_name},
    )
    return merchant


def set_active(session: Session, merchant_id: int, *, active: bool, actor: User) -> Merchant:
    if actor.role != UserRole.ADMIN:
        raise AccessDenied("Seul un administrateur peut modifier l'état d'un commerce.", code="admin_only")
    merchant = get_merchant(session, merchant_id)
    merchant.is_active = active
    audit.record(
        session,
        actor_id=actor.id,
        action="MERCHANT_ACTIVATED" if active else "MERCHANT_DEACTIVATED",
        entity_type="Merchant",
        entity_id=merchant.id,
        metadata={"business_name": merchant.business_name},
    )
    return merchant
