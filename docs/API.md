# API interne WafaClub

WafaClub est un **monolithe Streamlit**. Il n'expose pas d'API HTTP publique dans ce MVP : l'« API » est
constituée des **services Python** de `wafaclub/services/`. Ce document décrit leurs contrats, les règles de
transaction, les erreurs et les clés de pages utilisées par le routeur.

## 1. Conventions

### Sessions et transactions

Toutes les fonctions de service reçoivent une `Session` SQLAlchemy ouverte par l'appelant :

```python
from wafaclub.db import database
from wafaclub.services import loyalty

with database.session() as session:
    transaction = loyalty.add_purchase(
        session,
        client_id=2,
        merchant_id=1,
        amount="150.00",
        actor_id=5,
    )
    # commit automatique à la sortie du contexte
```

Règles :

- un service **ne crée pas** de session et **ne commit pas** ;
- `database.session()` commit en cas de succès, rollback en cas d'exception ;
- les services utilisent `session.flush()` pour obtenir les identifiants nécessaires ;
- les objets retournés peuvent être lus après la fermeture de la session uniquement si leurs relations
  ont été chargées (`joinedload`) ; dans l'UI, on préfère des snapshots `dict`.

### Types

| Concept | Type |
|---|---|
| Montants | `Decimal` quantifié à 2 décimales, ou `str`/`float` convertis par `to_decimal` |
| Dates | `datetime` UTC naïf (`utcnow()`) |
| Identifiants | `int` |
| Langues disponibles | Français (`Language.FR`) et arabe (`Language.AR`) |
| Rôles | `UserRole.CLIENT`, `UserRole.MERCHANT`, `UserRole.ADMIN` |

### Erreurs

Toutes les erreurs métier héritent de `WafaClubError` et possèdent un `code` stable, utilisé par l'i18n.

```python
from wafaclub.errors import ValidationError

try:
    loyalty.calculate_points(0, 10)
except ValidationError as exc:
    assert exc.code == "invalid_amount"
```

L'UI convertit l'erreur avec `wafaclub.ui.components.show_error(error, lang)`, qui cherche
`errors.<code>` dans les traductions puis retombe sur le message.

## 2. Authentification — `services/auth.py`

### `register_client`

```python
register_client(
    session,
    *,
    first_name: str,
    last_name: str,
    phone: str,
    password: str,
    city: str,
    neighborhood: str = "",
    email: str | None = None,
    preferred_language: str | Language = Language.FR,
) -> User
```

- Normalise le téléphone marocain (`06…`, `00212…`, `+212…` → `+212…`).
- Vérifie la disponibilité du téléphone et de l'e-mail.
- Valide la force du mot de passe (8 caractères, au moins une lettre et un chiffre).
- Crée le `User`, son `LoyaltyAccount` avec QR token unique et une notification de bienvenue.
- Codes d'erreur : `invalid_phone`, `phone_exists`, `email_exists`, `password_too_short`,
  `password_too_weak`, `city_required`, `name_required`.

### `register_merchant_owner`

```python
register_merchant_owner(
    session,
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
) -> tuple[User, Merchant]
```

Crée le compte propriétaire **et** son premier commerce. Un propriétaire peut posséder plusieurs commerces.

### `authenticate`

```python
authenticate(
    session,
    *,
    phone: str,
    password: str,
    expected_role: UserRole | str | None = None,
) -> User
```

- Limite les échecs à `WAFACLUB_LOGIN_MAX_ATTEMPTS` sur `WAFACLUB_LOGIN_WINDOW_MINUTES`.
- Journalise chaque tentative dans `login_attempts`.
- Commit explicitement les tentatives pour que le verrouillage survive à l'erreur.
- Codes : `invalid_credentials`, `account_locked`, `account_disabled`.

### Autres fonctions

| Fonction | Retour | Rôle |
|---|---|---|
| `get_user(session, user_id)` | `User` | Lecture, `user_not_found` |
| `update_client_profile(...)` | `User` | Mise à jour prénom, nom, e-mail, ville, quartier |
| `set_language(session, user_id, language)` | `User` | Langue préférée |
| `require_active(user)` | `User` | Vérifie `is_active` |

## 3. Fidélité — `services/loyalty.py`

### `calculate_points`

```python
calculate_points(amount: Decimal | str | float, points_per_amount: Decimal | str | float) -> int
```

`floor(montant / règle)`. Exemple : `95 / 10 = 9`. Lève `invalid_amount` ou `invalid_points_rule`.

### `find_client`

```python
find_client(session, identifier: str) -> User
```

Retrouve un client par téléphone **ou** par QR code (`WAFACLUB:QR:…`, deep link `wafaclub://loyalty/…`).
Erreurs : `client_identifier_required`, `invalid_phone`, `invalid_qr`, `client_not_found`, `client_inactive`.

### `add_purchase`

```python
add_purchase(
    session,
    *,
    client_id: int,
    merchant_id: int,
    amount: Decimal | str | float,
    actor_id: int,
) -> PointTransaction
```

- Vérifie client et commerce actifs.
- Refuse un montant ≤ 0, > 100 000 MAD ou ne générant aucun point.
- Verrouille le compte, crédite les points, écrit une ligne `EARNED` avec `balance_after`.
- Envoie une notification et une entrée d'audit `POINTS_EARNED`.
- Erreurs : `client_not_found`, `client_inactive`, `merchant_not_found`, `merchant_inactive`,
  `invalid_amount`, `amount_too_high`, `no_points_earned`, `loyalty_account_not_found`.

### `summary` et `list_transactions`

```python
summary(session, user_id) -> dict[str, int]
# {"balance": ..., "earned": ..., "spent": ..., "transactions": ...}

list_transactions(
    session,
    user_id,
    *,
    merchant_id: int | None = None,
    types: Sequence[TransactionType] | None = None,
    limit: int = 100,
) -> list[PointTransaction]
```

### Corrections et cycle de vie

| Fonction | Écriture | Usage |
|---|---|---|
| `refund_purchase(original_transaction_id, actor_id)` | `REFUND` négatif | Remboursement simulé |
| `adjust_points(user_id, points_delta, actor_id, description)` | `ADJUSTMENT` | Correction manuelle |
| `expire_points(user_id, points, actor_id)` | `EXPIRED` négatif | Expiration simulée |
| `ledger_is_consistent(session, user_id)` | lecture | Vérifie `solde == somme(journal)` |

Aucun service ne met à jour ou supprime une ligne existante du journal.

## 4. Récompenses — `services/rewards.py`

### Catalogue

```python
get_reward(session, reward_id) -> Reward
list_catalog(session, *, city=None, category=None, merchant_id=None, limit=100) -> list[Reward]
list_merchant_rewards(session, merchant_id, *, active_only=False) -> list[Reward]
```

`list_catalog` ne retourne que les récompenses actives, dans leur fenêtre de dates, avec stock disponible
et commerce actif.

### Gestion commerçant

```python
create_reward(
    session,
    *,
    merchant_id: int,
    actor_id: int,
    title: str,
    description: str,
    type: RewardType,
    points_cost: int,
    value: Decimal | str | float | None,
    icon: str,
    starts_at: datetime,
    expires_at: datetime,
    stock: int | None,
) -> Reward
```

`update_reward(...)` et `set_reward_active(...)` vérifient que le commerce appartient à `actor_id`.
Les récompenses réseau (`merchant_id is None`) ne sont pas modifiables depuis un commerce.

### `redeem_reward`

```python
redeem_reward(session, *, user_id: int, reward_id: int) -> RewardRedemption
```

- Vérifie l'activation, les dates, le stock, le commerce et le solde.
- Débite le compte et écrit une ligne `REDEEMED`.
- Crée un code `RWD-XXXX-XXXX` unique, valable `REWARD_CODE_TTL_DAYS` (30 jours).
- Décrémente le stock et notifie le client.
- Erreurs : `reward_unavailable`, `reward_out_of_stock`, `insufficient_points`, `client_inactive`.

### `validate_redemption`

```python
validate_redemption(session, *, code: str, merchant_id: int, actor_id: int) -> RewardRedemption
```

- Recherche le code (insensible à la casse), verrouille la ligne.
- Refuse un code utilisé, annulé, expiré ou appartenant à un autre commerce.
- Passe le statut à `USED`, renseigne `redeemed_at` et `validated_by_merchant_id`.
- Erreurs : `code_required`, `reward_code_not_found`, `reward_already_used`, `reward_cancelled`,
  `reward_code_expired`, `reward_wrong_merchant`, `merchant_inactive`.

### `list_user_redemptions`

Rafraîchit les récompenses `PENDING` expirées vers `EXPIRED`, puis retourne l'historique du client.

## 5. Cartes cadeaux — `services/giftcards.py`

### `create_gift_card`

```python
create_gift_card(
    session,
    *,
    sender_id: int,
    amount: Decimal | str | float,
    recipient_name: str,
    recipient_phone: str | None = None,
    merchant_id: int | None = None,
    message: str = "",
    recipient_is_self: bool = False,
) -> GiftCard
```

- Montant entre `GIFT_CARD_MIN_AMOUNT` (20) et `GIFT_CARD_MAX_AMOUNT` (2 000).
- `merchant_id=None` : carte réseau ; sinon le commerce doit être actif.
- Si le téléphone correspond à un client connu, la carte lui est rattachée et il est notifié.
- Génère un code `WFC-XXXX-XXXX-XXXX` unique.
- **Paiement simulé** : statut `ACTIVE`, `simulated_payment_status="PAID_SIMULATED"`.
- Erreurs : `client_inactive`, `giftcard_amount_too_low`, `giftcard_amount_too_high`,
  `merchant_inactive`, `recipient_required`, `invalid_phone`, `code_generation_failed`.

### Lecture et validation

| Fonction | Rôle |
|---|---|
| `get_gift_card(session, card_id)` | Détail avec expéditeur, destinataire et commerce |
| `list_user_gift_cards(session, user_id)` | Cartes envoyées ou reçues, expiration rafraîchie |
| `refresh_expired_cards(session)` | Passe les cartes actives expirées à `EXPIRED` |
| `verify_gift_card(session, code, merchant_id)` | Contrôle sans consommation |
| `validate_gift_card(session, code, merchant_id, actor_id)` | Consomme la carte (`USED`) |

`validate_gift_card` vérifie le statut, la date, le périmètre et l'activation du commerce, puis notifie
l'expéditeur et le destinataire. Erreurs : `giftcard_not_found`, `giftcard_already_used`,
`giftcard_cancelled`, `giftcard_expired`, `giftcard_wrong_merchant`, `merchant_inactive`.

## 6. Promotions — `services/promotions.py`

```python
list_promotions(
    session,
    *,
    city=None,
    neighborhood=None,
    category=None,
    merchant_id=None,
    search=None,
    active_only=True,
    limit=100,
) -> list[Promotion]
```

Fonctions d'écriture :

- `create_promotion(...)`, `update_promotion(...)`, `set_promotion_active(...)` ;
- contrôle du propriétaire (`merchant_access_denied`) et des dates (`invalid_dates`) ;
- une promotion n'est visible que si son commerce est actif et si elle est dans sa fenêtre de dates.

## 7. Commerces — `services/merchants.py`

| Fonction | Rôle |
|---|---|
| `get_merchant(session, merchant_id)` | Lecture, `merchant_not_found` |
| `owned_merchants(session, owner_id)` | Commerces d'un propriétaire, triés par nom |
| `list_merchants(...)` | Filtres ville, catégorie, recherche, actifs |
| `assert_manage_access(session, merchant_id, actor)` | Admin autorisé, ou propriétaire du commerce |
| `create_merchant(...)` | Validation du nom, de la ville, de la catégorie et de la règle |
| `update_profile(...)` | Mise à jour du profil commerce |
| `set_active(...)` | **Admin uniquement**, audit `MERCHANT_ACTIVATED` / `MERCHANT_DEACTIVATED` |

Constantes exposées : `MOROCCAN_CITIES`, `BUSINESS_CATEGORIES`.

## 8. Statistiques — `services/stats.py`

```python
merchant_dashboard(session, merchant_id, *, days=14) -> dict
merchant_clients(session, merchant_id, *, search=None) -> list[dict]
merchant_transactions(session, merchant_id, *, type_filter=None, limit=200) -> list[PointTransaction]
admin_overview(session, *, days=30) -> dict
```

`merchant_dashboard` retourne : nombre de clients, nouveaux clients sur 30 jours, points distribués,
récompenses validées, cartes cadeaux, achats, série quotidienne, transactions récentes et top clients.

`admin_overview` retourne : clients, propriétaires, commerces, commerces actifs, transactions,
points distribués, récompenses utilisées, cartes cadeaux, volume, série quotidienne et répartition par ville.

## 9. Administration — `services/admin.py`

| Fonction | Filtres |
|---|---|
| `list_users` | rôle, ville, recherche (nom, téléphone, e-mail) |
| `list_merchants` | ville, actif/inactif, recherche |
| `toggle_merchant` | délègue à `merchants.set_active` |
| `list_transactions` | dates, ville, type, limite |
| `list_gift_cards` | statut, limite |
| `list_promotions` | ville, actif/inactif, limite |

Ces fonctions sont en lecture seule, sauf `toggle_merchant`, qui exige un `User` admin.

## 10. Notifications et audit

### Notifications

```python
notify(session, user_id, *, type, title, message, link_page=None) -> Notification
list_notifications(session, user_id, limit=60) -> list[Notification]
unread_count(session, user_id) -> int
mark_read(session, user_id, notification_id) -> Notification
mark_all_read(session, user_id) -> int
```

`mark_read` vérifie que la notification appartient à l'utilisateur (`notification_not_found`).

### Audit

```python
record(
    session,
    *,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    metadata: dict | None = None,
) -> AuditLog
```

Actions journalisées : connexion, inscriptions, points, remboursements, récompenses, cartes cadeaux,
promotions, profils commerces, activation/désactivation.

## 11. Clés de pages et navigation

Les pages sont des clés stables utilisées par `SS["page"]` et `wafaclub/access.py`.

### Client

`client.dashboard`, `client.card`, `client.points`, `client.rewards`, `client.reward_detail`,
`client.reward_confirm`, `client.reward_success`, `client.my_rewards`, `client.promotions`,
`client.promotion_detail`, `client.merchants`, `client.merchant_detail`, `client.gift_cards`,
`client.gift_create`, `client.gift_confirm`, `client.gift_success`, `client.notifications`,
`client.profile`, `client.settings`, `client.help`.

### Commerçant

`merchant.dashboard`, `merchant.add_points`, `merchant.validate_reward`, `merchant.clients`,
`merchant.transactions`, `merchant.rewards`, `merchant.reward_form`, `merchant.gift_cards`,
`merchant.promotions`, `merchant.promotion_form`, `merchant.stats`, `merchant.profile`,
`merchant.settings`, `merchant.notifications`.

### Administration

`admin.dashboard`, `admin.users`, `admin.merchants`, `admin.transactions`, `admin.gift_cards`,
`admin.promotions`.

L'API de navigation interne est :

```python
from wafaclub.ui.state import goto, flash

flash("Message affiché au prochain rendu", "success")
goto("client.reward_detail", reward_id=12)
```

`goto` écrit `page` et `ctx` puis déclenche `st.rerun()`.

## 12. Codes d'erreur principaux

| Domaine | Codes |
|---|---|
| Authentification | `invalid_credentials`, `account_locked`, `account_disabled`, `phone_exists`, `email_exists`, `password_too_short`, `password_too_weak` |
| Accès | `page_forbidden`, `merchant_access_denied`, `admin_only` |
| Fidélité | `invalid_amount`, `amount_too_high`, `invalid_points_rule`, `no_points_earned`, `insufficient_points`, `already_refunded`, `refund_not_allowed` |
| Récompenses | `reward_not_found`, `reward_unavailable`, `reward_out_of_stock`, `reward_code_not_found`, `reward_already_used`, `reward_cancelled`, `reward_code_expired`, `reward_wrong_merchant` |
| Cartes cadeaux | `giftcard_not_found`, `giftcard_amount_too_low`, `giftcard_amount_too_high`, `giftcard_already_used`, `giftcard_cancelled`, `giftcard_expired`, `giftcard_wrong_merchant` |
| Promotions / commerces | `promotion_not_found`, `promotion_title_required`, `merchant_not_found`, `merchant_inactive`, `merchant_name_required`, `invalid_dates` |
| Notifications | `notification_not_found` |
| Journal | `immutable_ledger` |

> La liste exhaustive est maintenue dans le code (`code="…"`). Ce tableau couvre les codes exposés
> directement à l'utilisateur.

## 13. Exemple complet

```python
from decimal import Decimal

from wafaclub.db import database
from wafaclub.models import UserRole
from wafaclub.services import auth, loyalty, rewards

with database.session() as session:
    client = auth.register_client(
        session,
        first_name="Nadia",
        last_name="Exemple",
        phone="0661998877",
        password="Exemple2026!",
        city="Agadir",
        neighborhood="Talborjt",
    )
    transaction = loyalty.add_purchase(
        session,
        client_id=client.id,
        merchant_id=1,
        amount=Decimal("180.00"),
        actor_id=5,
    )
    print(transaction.points, transaction.balance_after)
    assert loyalty.ledger_is_consistent(session, client.id)
```

Cet exemple crée un client et un achat, puis vérifie l'invariant du journal. En production, l'appelant
doit fournir un `actor_id` authentifié et ne jamais exposer ces fonctions directement à un utilisateur
non autorisé.
