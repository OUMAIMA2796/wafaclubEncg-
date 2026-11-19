"""Données de démonstration WafaClub (Maroc).

Exécution :
    python -m wafaclub.seed
    python -m wafaclub.seed --reset
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import BASE_DIR, settings
from .db import database
from .models import (
    GiftCard,
    GiftCardStatus,
    Language,
    LoyaltyAccount,
    Merchant,
    Notification,
    NotificationType,
    PointTransaction,
    Promotion,
    RedemptionStatus,
    Reward,
    RewardRedemption,
    RewardType,
    TransactionType,
    User,
    UserRole,
    utcnow,
)
from .security import generate_qr_token, hash_password
from .services.loyalty import calculate_points

DEMO_PASSWORD = "Demo2026!"
NOW = utcnow()


def _days_ago(days: int, hours: int = 0) -> datetime:
    return NOW - timedelta(days=days, hours=hours)


def _days_ahead(days: int) -> datetime:
    return NOW + timedelta(days=days)


def _user(
    *,
    first_name: str,
    last_name: str,
    phone: str,
    role: UserRole,
    city: str,
    neighborhood: str,
    language: Language,
    email: str | None = None,
    created_days_ago: int = 120,
) -> User:
    return User(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        password_hash=hash_password(DEMO_PASSWORD),
        role=role,
        preferred_language=language,
        city=city,
        neighborhood=neighborhood,
        created_at=_days_ago(created_days_ago),
        updated_at=_days_ago(created_days_ago),
    )


def _merchant(
    owner: User,
    *,
    name: str,
    description: str,
    phone: str,
    address: str,
    city: str,
    neighborhood: str,
    category: str,
    latitude: str,
    longitude: str,
    points_per_amount: str,
    created_days_ago: int = 110,
) -> Merchant:
    return Merchant(
        owner_id=owner.id,
        business_name=name,
        description=description,
        phone=phone,
        address=address,
        city=city,
        neighborhood=neighborhood,
        category=category,
        latitude=Decimal(latitude),
        longitude=Decimal(longitude),
        points_per_amount=Decimal(points_per_amount),
        is_active=True,
        created_at=_days_ago(created_days_ago),
        updated_at=_days_ago(created_days_ago),
    )


def _reward(
    merchant: Merchant | None,
    *,
    title: str,
    description: str,
    reward_type: RewardType,
    points_cost: int,
    value: str | None,
    icon: str,
    stock: int | None,
    starts_days_ago: int = 40,
    expires_in_days: int = 180,
) -> Reward:
    return Reward(
        merchant_id=merchant.id if merchant else None,
        title=title,
        description=description,
        type=reward_type,
        points_cost=points_cost,
        value=Decimal(value) if value is not None else None,
        icon=icon,
        is_active=True,
        stock=stock,
        starts_at=_days_ago(starts_days_ago),
        expires_at=_days_ahead(expires_in_days),
        created_at=_days_ago(starts_days_ago),
        updated_at=_days_ago(starts_days_ago),
    )


def _promotion(
    merchant: Merchant,
    *,
    title: str,
    description: str,
    icon: str,
    starts_days_ago: int,
    expires_in_days: int,
    city: str | None = None,
    neighborhood: str | None = None,
    active: bool = True,
) -> Promotion:
    return Promotion(
        merchant_id=merchant.id,
        title=title,
        description=description,
        icon=icon,
        city=city or merchant.city,
        neighborhood=neighborhood or merchant.neighborhood,
        starts_at=_days_ago(starts_days_ago),
        expires_at=_days_ahead(expires_in_days),
        is_active=active,
        created_at=_days_ago(starts_days_ago),
    )


def _notification(
    user: User,
    *,
    type: NotificationType,
    title: str,
    message: str,
    link_page: str | None,
    days_ago: int,
    is_read: bool = False,
) -> Notification:
    return Notification(
        user_id=user.id,
        type=type,
        title=title,
        message=message,
        link_page=link_page,
        is_read=is_read,
        created_at=_days_ago(days_ago, hours=2),
    )


def seed_demo_data(session: Session) -> dict[str, int]:
    """Crée un jeu de données réaliste. Suppose une base vide (ou sans utilisateurs)."""
    existing = session.scalar(select(func.count(User.id))) or 0
    if existing:
        return {"skipped": 1}

    # --- Comptes -----------------------------------------------------------
    admin = _user(
        first_name="Nadia",
        last_name="El Fassi",
        phone="+212660000000",
        email="admin@wafaclub.ma",
        role=UserRole.ADMIN,
        city="Agadir",
        neighborhood="Talborjt",
        language=Language.FR,
        created_days_ago=140,
    )
    yasmine = _user(
        first_name="Yasmine",
        last_name="El Amrani",
        phone="+212661234567",
        email="yasmine@example.ma",
        role=UserRole.CLIENT,
        city="Agadir",
        neighborhood="Founty",
        language=Language.FR,
        created_days_ago=100,
    )
    omar = _user(
        first_name="Omar",
        last_name="Benjelloun",
        phone="+212662345678",
        email="omar@example.ma",
        role=UserRole.CLIENT,
        city="Agadir",
        neighborhood="Hay Mohammadi",
        language=Language.AR,
        created_days_ago=95,
    )
    salma = _user(
        first_name="Salma",
        last_name="Ait Lahcen",
        phone="+212663456789",
        email="salma@example.ma",
        role=UserRole.CLIENT,
        city="Agadir",
        neighborhood="Dakhla",
        language=Language.FR,
        created_days_ago=90,
    )
    hamza = _user(
        first_name="Hamza",
        last_name="Alaoui",
        phone="+212664567890",
        email="hamza@example.ma",
        role=UserRole.MERCHANT,
        city="Agadir",
        neighborhood="Founty",
        language=Language.FR,
        created_days_ago=115,
    )
    imane = _user(
        first_name="Imane",
        last_name="Bennani",
        phone="+212665678901",
        email="imane@example.ma",
        role=UserRole.MERCHANT,
        city="Agadir",
        neighborhood="Talborjt",
        language=Language.FR,
        created_days_ago=112,
    )
    youssef = _user(
        first_name="Youssef",
        last_name="Tazi",
        phone="+212666789012",
        email="youssef@example.ma",
        role=UserRole.MERCHANT,
        city="Agadir",
        neighborhood="Anza",
        language=Language.FR,
        created_days_ago=108,
    )
    clients = [yasmine, omar, salma]
    owners = [hamza, imane, youssef]
    session.add_all([admin, *clients, *owners])
    session.flush()

    accounts: dict[int, LoyaltyAccount] = {}
    for client in clients:
        account = LoyaltyAccount(
            user_id=client.id,
            total_points=0,
            qr_code_token=generate_qr_token(),
            created_at=client.created_at,
        )
        session.add(account)
        accounts[client.id] = account

    # --- Commerces ---------------------------------------------------------
    cafe = _merchant(
        hamza,
        name="Café Argana",
        description=(
            "Café de quartier au cœur de Founty : petit-déjeuner marocain, café de spécialité et pâtisseries maison."
        ),
        phone="+212528123456",
        address="12 avenue des FAR, Founty",
        city="Agadir",
        neighborhood="Founty",
        category="Café",
        latitude="30.4004",
        longitude="-9.5746",
        points_per_amount="10",
    )
    epicerie = _merchant(
        hamza,
        name="Épicerie Al Baraka",
        description=(
            "Épicerie de proximité avec produits frais, épices marocaines et produits du quotidien, "
            "au service des familles de Hay Mohammadi."
        ),
        phone="+212528123457",
        address="45 avenue de Hay Mohammadi",
        city="Agadir",
        neighborhood="Hay Mohammadi",
        category="Épicerie",
        latitude="30.4394",
        longitude="-9.5642",
        points_per_amount="10",
    )
    patisserie = _merchant(
        imane,
        name="Pâtisserie Tazi",
        description=(
            "Pâtisserie artisanale marocaine et française : cornes de gazelle, chebakia, "
            "gâteaux de fête et commandes personnalisées."
        ),
        phone="+212528123458",
        address="8 avenue Hassan II, Talborjt",
        city="Agadir",
        neighborhood="Talborjt",
        category="Pâtisserie",
        latitude="30.4190",
        longitude="-9.5981",
        points_per_amount="12",
    )
    superette = _merchant(
        imane,
        name="Supérette Dakhla",
        description=(
            "Supérette conviviale à Dakhla : produits locaux, boissons, épicerie fine et dépannage du quotidien."
        ),
        phone="+212528123459",
        address="3 avenue de Dakhla",
        city="Agadir",
        neighborhood="Dakhla",
        category="Supérette",
        latitude="30.4132",
        longitude="-9.5729",
        points_per_amount="10",
    )
    hanout = _merchant(
        youssef,
        name="Hanout Anza",
        description=(
            "Hanout de quartier à Anza : fruits secs, épices, huiles d'olive et spécialités "
            "marocaines sélectionnées avec soin."
        ),
        phone="+212528123460",
        address="22 avenue Mohammed V, Anza",
        city="Agadir",
        neighborhood="Anza",
        category="Épicerie",
        latitude="30.4450",
        longitude="-9.6520",
        points_per_amount="15",
    )
    merchants = [cafe, epicerie, patisserie, superette, hanout]
    session.add_all(merchants)
    session.flush()

    # --- Récompenses -------------------------------------------------------
    rewards = [
        _reward(
            cafe,
            title="10 MAD de réduction",
            description="Valable sur une consommation sur place, sans minimum d'achat.",
            reward_type=RewardType.DISCOUNT,
            points_cost=100,
            value="10",
            icon="☕",
            stock=50,
        ),
        _reward(
            cafe,
            title="Thé à la menthe offert",
            description="Un thé à la menthe traditionnel offert avec la formule de votre choix.",
            reward_type=RewardType.PRODUCT,
            points_cost=150,
            value="15",
            icon="🍵",
            stock=30,
        ),
        _reward(
            cafe,
            title="Formule petit-déjeuner -15%",
            description="Sur la formule petit-déjeuner marocain, du lundi au vendredi.",
            reward_type=RewardType.DISCOUNT,
            points_cost=250,
            value="15",
            icon="🥐",
            stock=25,
        ),
        _reward(
            cafe,
            title="Bon d'achat de 25 MAD",
            description="Bon d'achat utilisable sur tout le menu, hors offre happy hour.",
            reward_type=RewardType.VOUCHER,
            points_cost=500,
            value="25",
            icon="🎟️",
            stock=20,
        ),
        _reward(
            epicerie,
            title="10 MAD de réduction",
            description="Réduction immédiate dès 50 MAD d'achat.",
            reward_type=RewardType.DISCOUNT,
            points_cost=100,
            value="10",
            icon="🛒",
            stock=100,
        ),
        _reward(
            epicerie,
            title="Sac réutilisable offert",
            description="Un sac en toile WafaClub pour vos courses de quartier.",
            reward_type=RewardType.PRODUCT,
            points_cost=80,
            value="12",
            icon="👜",
            stock=40,
        ),
        _reward(
            epicerie,
            title="Bon d'achat de 50 MAD",
            description="Valable sans minimum d'achat sur les produits du quotidien.",
            reward_type=RewardType.VOUCHER,
            points_cost=600,
            value="50",
            icon="🎟️",
            stock=15,
        ),
        _reward(
            patisserie,
            title="Corne de gazelle offerte",
            description="Une corne de gazelle artisanale, à déguster sur place ou à emporter.",
            reward_type=RewardType.PRODUCT,
            points_cost=120,
            value="8",
            icon="🍮",
            stock=60,
        ),
        _reward(
            patisserie,
            title="5 % de réduction",
            description="5 % de réduction sur vos commandes de pâtisseries, hors livraison.",
            reward_type=RewardType.DISCOUNT,
            points_cost=250,
            value="5",
            icon="🎂",
            stock=35,
        ),
        _reward(
            patisserie,
            title="Coffret pâtisseries 50 MAD",
            description="Un assortiment de pâtisseries marocaines préparé par notre cheffe.",
            reward_type=RewardType.VOUCHER,
            points_cost=500,
            value="50",
            icon="🎁",
            stock=12,
        ),
        _reward(
            superette,
            title="5 MAD de réduction",
            description="Sur vos achats de produits frais et boissons.",
            reward_type=RewardType.DISCOUNT,
            points_cost=60,
            value="5",
            icon="🧺",
            stock=120,
        ),
        _reward(
            superette,
            title="Pack thé & msemen offert",
            description="Pack convivial à retirer en boutique, disponible le matin.",
            reward_type=RewardType.PRODUCT,
            points_cost=180,
            value="18",
            icon="🫖",
            stock=25,
        ),
        _reward(
            superette,
            title="Bon d'achat de 30 MAD",
            description="Valable sur tout le magasin, une utilisation par client.",
            reward_type=RewardType.VOUCHER,
            points_cost=350,
            value="30",
            icon="🎟️",
            stock=30,
        ),
        _reward(
            hanout,
            title="10 MAD de réduction",
            description="Dès 80 MAD d'achat d'épices et fruits secs.",
            reward_type=RewardType.DISCOUNT,
            points_cost=90,
            value="10",
            icon="🌿",
            stock=80,
        ),
        _reward(
            hanout,
            title="Épices du chef offertes",
            description="Un sachet d'épices maison sélectionné par Youssef.",
            reward_type=RewardType.PRODUCT,
            points_cost=200,
            value="20",
            icon="🌶️",
            stock=20,
        ),
        _reward(
            None,
            title="Cadeau surprise WafaClub",
            description=(
                "Une récompense réseau offerte par WafaClub, à retirer chez le commerce partenaire de votre choix."
            ),
            reward_type=RewardType.VOUCHER,
            points_cost=400,
            value="30",
            icon="🎁",
            stock=10,
        ),
    ]
    session.add_all(rewards)
    session.flush()

    # --- Promotions --------------------------------------------------------
    promotions = [
        _promotion(
            cafe,
            title="Petit-déjeuner -20%",
            description="La formule petit-déjeuner marocain à prix doux, tous les matins jusqu'à 11h.",
            icon="🥐",
            starts_days_ago=10,
            expires_in_days=20,
        ),
        _promotion(
            cafe,
            title="Happy hour 17h-19h",
            description="Un café ou un jus pressé à -30 % pendant l'heure du goûter.",
            icon="☕",
            starts_days_ago=5,
            expires_in_days=30,
        ),
        _promotion(
            epicerie,
            title="2e produit frais -50%",
            description="Sur les fruits et légumes du jour, du mardi au jeudi.",
            icon="🥕",
            starts_days_ago=2,
            expires_in_days=14,
        ),
        _promotion(
            patisserie,
            title="Coffret Ramadan -15%",
            description="Commandez votre coffret de pâtisseries à l'avance et économisez 15 %.",
            icon="🌙",
            starts_days_ago=7,
            expires_in_days=25,
        ),
        _promotion(
            superette,
            title="Panier local -10%",
            description="10 % sur un panier de produits locaux sélectionnés (minimum 100 MAD).",
            icon="🧺",
            starts_days_ago=1,
            expires_in_days=18,
        ),
        _promotion(
            hanout,
            title="Épices -15%",
            description="Sur tout le rayon épices, vrac et sachets, jusqu'à dimanche.",
            icon="🌶️",
            starts_days_ago=3,
            expires_in_days=21,
        ),
        _promotion(
            cafe,
            title="Offre de printemps",
            description="Ancienne offre de démonstration, expirée pour illustrer les filtres.",
            icon="🌸",
            starts_days_ago=70,
            expires_in_days=-45,
            active=True,
        ),
    ]
    session.add_all(promotions)

    # --- Achats simulés ----------------------------------------------------
    purchase_specs = [
        (yasmine, cafe, "95", 2),
        (yasmine, epicerie, "240", 9),
        (yasmine, patisserie, "620", 20),
        (yasmine, cafe, "130", 30),
        (yasmine, hanout, "300", 45),
        (yasmine, superette, "180", 60),
        (yasmine, epicerie, "950", 75),
        (yasmine, epicerie, "1250", 90),
        (yasmine, patisserie, "480", 105),
        (omar, epicerie, "100", 1),
        (omar, patisserie, "450", 5),
        (omar, cafe, "260", 12),
        (omar, hanout, "700", 25),
        (omar, superette, "150", 40),
        (omar, epicerie, "800", 55),
        (omar, patisserie, "960", 70),
        (omar, cafe, "320", 85),
        (salma, cafe, "80", 3),
        (salma, epicerie, "320", 7),
        (salma, patisserie, "500", 16),
        (salma, hanout, "120", 28),
        (salma, superette, "280", 50),
        (salma, cafe, "190", 65),
        (salma, patisserie, "720", 80),
        (salma, epicerie, "1500", 95),
    ]
    ledger: list[PointTransaction] = []
    for client, merchant, amount, days in purchase_specs:
        value = Decimal(amount)
        points = calculate_points(value, merchant.points_per_amount)
        ledger.append(
            PointTransaction(
                user_id=client.id,
                merchant_id=merchant.id,
                type=TransactionType.EARNED,
                points=points,
                purchase_amount=value,
                description=f"Achat de {value} MAD chez {merchant.business_name}",
                reference=f"PUR-SEED-{client.id}-{merchant.id}-{days}",
                balance_after=0,
                created_at=_days_ago(days, hours=3),
            )
        )

    # --- Récompenses déjà utilisées / en attente ---------------------------
    reward_by_key = {(r.merchant_id, r.title): r for r in rewards}
    redemption_specs = [
        (yasmine, cafe, "10 MAD de réduction", "RWD-DEMO-USED1", RedemptionStatus.USED, 6, 4),
        (yasmine, cafe, "Thé à la menthe offert", "RWD-DEMO-7K2M", RedemptionStatus.PENDING, 1, None),
        (omar, epicerie, "10 MAD de réduction", "RWD-DEMO-USED2", RedemptionStatus.USED, 8, 7),
        (salma, patisserie, "Corne de gazelle offerte", "RWD-DEMO-3N8P", RedemptionStatus.PENDING, 2, None),
    ]
    redemptions: list[RewardRedemption] = []
    for index, (client, merchant, title, code, status, created_days, used_days) in enumerate(redemption_specs):
        reward = reward_by_key[(merchant.id, title)]
        redemption = RewardRedemption(
            reward_id=reward.id,
            user_id=client.id,
            merchant_id=merchant.id,
            validated_by_merchant_id=merchant.id if status == RedemptionStatus.USED else None,
            code=code,
            status=status,
            redeemed_at=_days_ago(used_days, hours=1) if used_days is not None else None,
            expires_at=_days_ahead(30 - created_days),
            created_at=_days_ago(created_days, hours=1),
        )
        redemptions.append(redemption)
        if reward.stock is not None:
            reward.stock = max(0, reward.stock - 1)
        ledger.append(
            PointTransaction(
                user_id=client.id,
                merchant_id=merchant.id,
                type=TransactionType.REDEEMED,
                points=-reward.points_cost,
                purchase_amount=None,
                description=f"Récompense : {reward.title}",
                reference=f"RDM-SEED-{index + 1}-{code[-4:]}",
                balance_after=0,
                created_at=_days_ago(created_days, hours=1),
            )
        )
    session.add_all(redemptions)

    # Soldes reconstitués chronologiquement : le solde ne change jamais sans transaction.
    for client in clients:
        running = 0
        entries = sorted(
            [entry for entry in ledger if entry.user_id == client.id],
            key=lambda entry: entry.created_at,
        )
        for entry in entries:
            running += entry.points
            if running < 0:
                raise RuntimeError(f"Seed incohérent : solde négatif pour {client.phone}")
            entry.balance_after = running
        accounts[client.id].total_points = running
    session.add_all(ledger)
    session.flush()

    # --- Cartes cadeaux ----------------------------------------------------
    cards = [
        GiftCard(
            sender_id=yasmine.id,
            recipient_user_id=yasmine.id,
            recipient_name="Yasmine El Amrani",
            recipient_phone=yasmine.phone,
            merchant_id=None,
            amount=Decimal("100"),
            code="WFC-DEMO-4Q7N-9TX2",
            status=GiftCardStatus.ACTIVE,
            message="Pour mes prochains achats de quartier.",
            expires_at=_days_ahead(365),
            simulated_payment_status="PAID_SIMULATED",
            created_at=_days_ago(12),
        ),
        GiftCard(
            sender_id=omar.id,
            recipient_user_id=salma.id,
            recipient_name="Salma Ait Lahcen",
            recipient_phone=salma.phone,
            merchant_id=patisserie.id,
            amount=Decimal("200"),
            code="WFC-DEMO-8M2K-6RP4",
            status=GiftCardStatus.ACTIVE,
            message="Joyeux anniversaire Salma ! Profite d'un coffret de pâtisseries.",
            expires_at=_days_ahead(365),
            simulated_payment_status="PAID_SIMULATED",
            created_at=_days_ago(8),
        ),
        GiftCard(
            sender_id=yasmine.id,
            recipient_user_id=None,
            recipient_name="Nadia Amrani",
            recipient_phone="+212677889900",
            merchant_id=cafe.id,
            amount=Decimal("50"),
            code="WFC-DEMO-6J3V-2LQ9",
            status=GiftCardStatus.USED,
            message="Un café entre amies.",
            expires_at=_days_ahead(300),
            simulated_payment_status="PAID_SIMULATED",
            redeemed_at=_days_ago(4),
            redeemed_by_merchant_id=cafe.id,
            created_at=_days_ago(15),
        ),
        GiftCard(
            sender_id=omar.id,
            recipient_user_id=omar.id,
            recipient_name="Omar Benjelloun",
            recipient_phone=omar.phone,
            merchant_id=hanout.id,
            amount=Decimal("50"),
            code="WFC-DEMO-2T7X-5NQ8",
            status=GiftCardStatus.EXPIRED,
            message="Carte de démonstration expirée.",
            expires_at=_days_ago(10),
            simulated_payment_status="PAID_SIMULATED",
            created_at=_days_ago(380),
        ),
    ]
    session.add_all(cards)

    # --- Notifications -----------------------------------------------------
    notification_rows = [
        _notification(
            yasmine,
            type=NotificationType.WELCOME,
            title="Bienvenue dans WafaClub",
            message="Votre carte de fidélité numérique est prête. Une seule carte, plusieurs commerces.",
            link_page="client.card",
            days_ago=100,
            is_read=True,
        ),
        _notification(
            yasmine,
            type=NotificationType.POINTS_EARNED,
            title="+9 points chez Café Argana",
            message="Votre achat de 95 MAD vous a rapporté 9 points. Nouveau solde : 145 points.",
            link_page="client.points",
            days_ago=2,
        ),
        _notification(
            yasmine,
            type=NotificationType.NEARBY_PROMOTION,
            title="Nouvelle promo à Founty",
            message="Café Argana : petit-déjeuner -20% jusqu'à 11h. Découvrez l'offre avant le 30.",
            link_page="client.promotions",
            days_ago=1,
        ),
        _notification(
            yasmine,
            type=NotificationType.GIFT_CARD_EXPIRING,
            title="Pensez à utiliser vos cartes cadeaux",
            message="Votre carte cadeau de 100 MAD est valable un an. Retrouvez son code dans vos cartes.",
            link_page="client.gift_cards",
            days_ago=3,
        ),
        _notification(
            yasmine,
            type=NotificationType.POINTS_EXPIRING,
            title="Vos points sont précieux",
            message="50 points de démonstration arriveront à expiration dans 30 jours.",
            link_page="client.points",
            days_ago=4,
        ),
        _notification(
            omar,
            type=NotificationType.WELCOME,
            title="Bienvenue dans WafaClub",
            message="Votre carte de fidélité est active. Présentez votre QR code chez vos commerçants.",
            link_page="client.card",
            days_ago=95,
            is_read=True,
        ),
        _notification(
            omar,
            type=NotificationType.GIFT_CARD_EXPIRING,
            title="Carte cadeau expirée",
            message="Votre carte de démonstration de 50 MAD chez Hanout Anza a expiré.",
            link_page="client.gift_cards",
            days_ago=9,
        ),
        _notification(
            omar,
            type=NotificationType.NEARBY_PROMOTION,
            title="Promo à Hay Mohammadi",
            message="Épicerie Al Baraka : le 2e produit frais est à -50% cette semaine.",
            link_page="client.promotions",
            days_ago=2,
        ),
        _notification(
            salma,
            type=NotificationType.WELCOME,
            title="مرحبا بك في WafaClub",
            message="بطاقتك الرقمية جاهزة. اجمعي النقاط وأعيدي استعمالها عند شركائنا.",
            link_page="client.card",
            days_ago=90,
            is_read=True,
        ),
        _notification(
            salma,
            type=NotificationType.GIFT_CARD_RECEIVED,
            title="Une carte cadeau vous attend",
            message="Omar vous offre une carte cadeau de 200 MAD chez Pâtisserie Tazi.",
            link_page="client.gift_cards",
            days_ago=8,
        ),
        _notification(
            salma,
            type=NotificationType.NEARBY_PROMOTION,
            title="Coffret Ramadan -15%",
            message="Pâtisserie Tazi à Talborjt : commandez votre coffret de pâtisseries à l'avance.",
            link_page="client.promotions",
            days_ago=1,
        ),
    ]
    for owner in owners:
        notification_rows.append(
            _notification(
                owner,
                type=NotificationType.WELCOME,
                title="Bienvenue dans WafaClub Pro",
                message="Votre espace commerçant est prêt. Ajoutez votre premier client dès maintenant.",
                link_page="merchant.dashboard",
                days_ago=110,
                is_read=True,
            )
        )
    session.add_all(notification_rows)

    session.flush()
    return {
        "users": 7,
        "clients": len(clients),
        "merchants": len(merchants),
        "rewards": len(rewards),
        "promotions": len(promotions),
        "transactions": len(ledger),
        "gift_cards": len(cards),
        "redemptions": len(redemptions),
        "notifications": len(notification_rows),
    }


def ensure_seed(session: Session) -> bool:
    """Remplit la base uniquement si elle est vide. Retourne True si un seed a eu lieu."""
    if session.scalar(select(func.count(User.id))) or 0:
        return False
    seed_demo_data(session)
    return True


def main() -> None:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Seed de démonstration WafaClub")
    parser.add_argument("--reset", action="store_true", help="Supprime et recrée toutes les tables")
    args = parser.parse_args()

    if args.reset:
        database.reset()
    else:
        database.create_all()

    with database.session() as session:
        summary = seed_demo_data(session)

    if summary.get("skipped"):
        print("Info : base déjà remplie, seed ignoré. Utilisez --reset pour repartir de zéro.")
    else:
        print("Données de démonstration WafaClub créées :")
        for key, value in summary.items():
            print(f"   - {key}: {value}")
    print(f"\nBase locale : {settings.database_url}")
    print(f"Dossier projet : {BASE_DIR}")
    print(f"Mot de passe de démonstration : {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
