"""Moteur de fidélité : calcul des points et journal append-only."""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..errors import ConflictError, NotFoundError, ValidationError
from ..models import (
    LoyaltyAccount,
    Merchant,
    NotificationType,
    PointTransaction,
    TransactionType,
    User,
    UserRole,
)
from ..qrcodes import QR_PREFIX, extract_qr_token
from ..security import generate_reference, normalize_moroccan_phone, to_decimal
from . import audit, notifications

MAX_PURCHASE_AMOUNT = Decimal("100000.00")
_PHONE_INPUT_RE = re.compile(r"^[\d+\s.\-()/]+$")


def calculate_points(amount: Decimal | str | float, points_per_amount: Decimal | str | float) -> int:
    """1 point par tranche complète de `points_per_amount` MAD.

    95 MAD / 10 = 9 points ; 100 MAD / 10 = 10 points.
    """
    purchase = to_decimal(amount)
    rule = to_decimal(points_per_amount)
    if purchase <= 0:
        raise ValidationError("Le montant doit être supérieur à 0 MAD.", code="invalid_amount")
    if rule <= 0:
        raise ValidationError("La règle de points du commerce est invalide.", code="invalid_points_rule")
    return int((purchase / rule).to_integral_value(rounding=ROUND_FLOOR))


def get_account(session: Session, user_id: int, *, lock: bool = False) -> LoyaltyAccount:
    stmt = select(LoyaltyAccount).where(LoyaltyAccount.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    account = session.scalar(stmt)
    if not account:
        raise NotFoundError("Carte de fidélité introuvable.", code="loyalty_account_not_found")
    return account


def find_client(session: Session, identifier: str) -> User:
    """Retrouve un client par téléphone ou par jeton QR."""
    raw = (identifier or "").strip()
    if not raw:
        raise ValidationError("Saisissez un téléphone ou scannez un QR code.", code="client_identifier_required")

    if raw.startswith(QR_PREFIX) or raw.startswith("wafaclub://") or not _PHONE_INPUT_RE.fullmatch(raw):
        try:
            token = extract_qr_token(raw)
        except ValueError as exc:
            raise ValidationError("QR code invalide.", code="invalid_qr") from exc
        user = session.scalar(
            select(User)
            .join(LoyaltyAccount, LoyaltyAccount.user_id == User.id)
            .where(LoyaltyAccount.qr_code_token == token)
        )
    else:
        try:
            phone = normalize_moroccan_phone(raw)
        except ValidationError as exc:
            raise ValidationError("Numéro de téléphone invalide.", code="invalid_phone") from exc
        user = session.scalar(
            select(User).join(LoyaltyAccount, LoyaltyAccount.user_id == User.id).where(User.phone == phone)
        )

    if not user or user.role != UserRole.CLIENT:
        raise NotFoundError("Aucun client WafaClub trouvé.", code="client_not_found")
    if not user.is_active:
        raise ValidationError("Le compte de ce client est désactivé.", code="client_inactive")
    return user


def add_purchase(
    session: Session,
    *,
    client_id: int,
    merchant_id: int,
    amount: Decimal | str | float,
    actor_id: int,
) -> PointTransaction:
    client = session.get(User, client_id)
    if not client or client.role != UserRole.CLIENT:
        raise NotFoundError("Client introuvable.", code="client_not_found")
    if not client.is_active:
        raise ValidationError("Le compte de ce client est désactivé.", code="client_inactive")
    merchant = session.get(Merchant, merchant_id)
    if not merchant:
        raise NotFoundError("Commerce introuvable.", code="merchant_not_found")
    if not merchant.is_active:
        raise ValidationError("Ce commerce est désactivé.", code="merchant_inactive")

    purchase = to_decimal(amount)
    if purchase <= 0:
        raise ValidationError("Le montant doit être supérieur à 0 MAD.", code="invalid_amount")
    if purchase > MAX_PURCHASE_AMOUNT:
        raise ValidationError("Le montant dépasse la limite de démonstration.", code="amount_too_high")

    points = calculate_points(purchase, merchant.points_per_amount)
    if points <= 0:
        raise ValidationError(
            f"Ce montant ne génère aucun point (minimum {merchant.points_per_amount} MAD).",
            code="no_points_earned",
        )

    account = get_account(session, client.id, lock=True)
    new_balance = account.total_points + points
    account.total_points = new_balance
    transaction = PointTransaction(
        user_id=client.id,
        merchant_id=merchant.id,
        type=TransactionType.EARNED,
        points=points,
        purchase_amount=purchase,
        description=f"Achat de {purchase} MAD chez {merchant.business_name}",
        reference=generate_reference("PUR"),
        balance_after=new_balance,
    )
    session.add(transaction)
    session.flush()

    notifications.notify(
        session,
        client.id,
        type=NotificationType.POINTS_EARNED,
        title=f"+{points} points WafaClub",
        message=(
            f"Votre achat de {purchase} MAD chez {merchant.business_name} vous a rapporté {points} points. "
            f"Nouveau solde : {new_balance} points."
        ),
        link_page="client.points",
    )
    audit.record(
        session,
        actor_id=actor_id,
        action="POINTS_EARNED",
        entity_type="PointTransaction",
        entity_id=transaction.id,
        metadata={
            "client_id": client.id,
            "merchant_id": merchant.id,
            "amount": str(purchase),
            "points": points,
            "balance_after": new_balance,
        },
    )
    session.flush()
    return transaction


def list_transactions(
    session: Session,
    user_id: int,
    *,
    merchant_id: int | None = None,
    types: Sequence[TransactionType] | None = None,
    limit: int = 100,
) -> list[PointTransaction]:
    stmt = select(PointTransaction).where(PointTransaction.user_id == user_id)
    if merchant_id:
        stmt = stmt.where(PointTransaction.merchant_id == merchant_id)
    if types:
        stmt = stmt.where(PointTransaction.type.in_(list(types)))
    stmt = stmt.order_by(PointTransaction.created_at.desc(), PointTransaction.id.desc()).limit(limit)
    return list(session.scalars(stmt))


def summary(session: Session, user_id: int) -> dict[str, int]:
    earned = session.scalar(
        select(func.coalesce(func.sum(PointTransaction.points), 0)).where(
            PointTransaction.user_id == user_id, PointTransaction.points > 0
        )
    )
    spent = session.scalar(
        select(func.coalesce(func.sum(PointTransaction.points), 0)).where(
            PointTransaction.user_id == user_id, PointTransaction.points < 0
        )
    )
    tx_count = session.scalar(select(func.count(PointTransaction.id)).where(PointTransaction.user_id == user_id))
    balance = get_account(session, user_id).total_points
    return {
        "balance": int(balance),
        "earned": int(earned or 0),
        "spent": abs(int(spent or 0)),
        "transactions": int(tx_count or 0),
    }


def refund_purchase(
    session: Session,
    *,
    original_transaction_id: int,
    actor_id: int,
    description: str = "Remboursement simulé",
) -> PointTransaction:
    """Prépare le remboursement d'un achat en créant une contre-écriture REFUND."""
    original = session.get(PointTransaction, original_transaction_id)
    if not original:
        raise NotFoundError("Transaction introuvable.", code="transaction_not_found")
    if original.type != TransactionType.EARNED or original.points <= 0:
        raise ValidationError("Seul un gain de points peut être remboursé.", code="refund_not_allowed")
    already = session.scalar(select(PointTransaction.id).where(PointTransaction.reference == f"REF-{original.id}"))
    if already:
        raise ConflictError("Cette transaction a déjà été remboursée.", code="already_refunded")

    account = get_account(session, original.user_id, lock=True)
    reversible = min(original.points, account.total_points)
    if reversible <= 0:
        raise ValidationError("Le solde ne permet pas ce remboursement.", code="insufficient_points")
    new_balance = account.total_points - reversible
    account.total_points = new_balance
    transaction = PointTransaction(
        user_id=original.user_id,
        merchant_id=original.merchant_id,
        type=TransactionType.REFUND,
        points=-reversible,
        purchase_amount=original.purchase_amount,
        description=description,
        reference=f"REF-{original.id}",
        balance_after=new_balance,
    )
    session.add(transaction)
    notifications.notify(
        session,
        original.user_id,
        type=NotificationType.POINTS_EXPIRING,
        title="Remboursement simulé",
        message=f"Un remboursement a retiré {reversible} points. Nouveau solde : {new_balance} points.",
        link_page="client.points",
    )
    audit.record(
        session,
        actor_id=actor_id,
        action="POINTS_REFUNDED",
        entity_type="PointTransaction",
        entity_id=transaction.id,
        metadata={"original_id": original.id, "points": -reversible},
    )
    session.flush()
    return transaction


def adjust_points(
    session: Session,
    *,
    user_id: int,
    points_delta: int,
    actor_id: int,
    description: str,
) -> PointTransaction:
    if points_delta == 0:
        raise ValidationError("L'ajustement doit être différent de zéro.", code="invalid_adjustment")
    account = get_account(session, user_id, lock=True)
    new_balance = account.total_points + points_delta
    if new_balance < 0:
        raise ValidationError("Le solde ne peut pas devenir négatif.", code="insufficient_points")
    account.total_points = new_balance
    transaction = PointTransaction(
        user_id=user_id,
        merchant_id=None,
        type=TransactionType.ADJUSTMENT,
        points=points_delta,
        purchase_amount=None,
        description=description,
        reference=generate_reference("ADJ"),
        balance_after=new_balance,
    )
    session.add(transaction)
    audit.record(
        session,
        actor_id=actor_id,
        action="POINTS_ADJUSTED",
        entity_type="PointTransaction",
        entity_id=transaction.id,
        metadata={"points": points_delta, "balance_after": new_balance},
    )
    session.flush()
    return transaction


def expire_points(
    session: Session,
    *,
    user_id: int,
    points: int,
    actor_id: int,
    description: str = "Expiration de points simulée",
) -> PointTransaction:
    if points <= 0:
        raise ValidationError("Le nombre de points à expirer doit être positif.", code="invalid_amount")
    account = get_account(session, user_id, lock=True)
    to_expire = min(points, account.total_points)
    if to_expire <= 0:
        raise ValidationError("Aucun point à expirer.", code="insufficient_points")
    new_balance = account.total_points - to_expire
    account.total_points = new_balance
    transaction = PointTransaction(
        user_id=user_id,
        merchant_id=None,
        type=TransactionType.EXPIRED,
        points=-to_expire,
        purchase_amount=None,
        description=description,
        reference=generate_reference("EXP"),
        balance_after=new_balance,
    )
    session.add(transaction)
    notifications.notify(
        session,
        user_id,
        type=NotificationType.POINTS_EXPIRING,
        title="Points expirés",
        message=f"{to_expire} points ont expiré. Nouveau solde : {new_balance} points.",
        link_page="client.points",
    )
    audit.record(
        session,
        actor_id=actor_id,
        action="POINTS_EXPIRED",
        entity_type="PointTransaction",
        entity_id=transaction.id,
        metadata={"points": -to_expire},
    )
    session.flush()
    return transaction


def ledger_is_consistent(session: Session, user_id: int) -> bool:
    total = session.scalar(
        select(func.coalesce(func.sum(PointTransaction.points), 0)).where(PointTransaction.user_id == user_id)
    )
    balance = session.scalar(select(LoyaltyAccount.total_points).where(LoyaltyAccount.user_id == user_id))
    return int(total or 0) == int(balance or 0)
