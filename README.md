# WafaClub

> **Une seule carte, plusieurs commerces, plus de récompenses.**

WafaClub est un MVP fonctionnel de **fidélité de proximité et de cartes cadeaux** pour le marché marocain.
Un client cumule des points chez plusieurs commerces avec une seule carte numérique, les échange contre des
récompenses et offre des cartes cadeaux utilisables dans le réseau. Les commerçants disposent d'un espace de
gestion complet, et l'administration d'une vue consolidée.

Le projet est une **démonstration fintech** : les paiements sont entièrement simulés, aucune donnée bancaire
réelle n'est demandée et aucune somme réelle n'est débitée.

---

## Sommaire

- [Le problème et la réponse WafaClub](#le-problème-et-la-réponse-wafaclub)
- [Fonctionnalités](#fonctionnalités)
- [Stack technique](#stack-technique)
- [Démarrage rapide](#démarrage-rapide)
- [Comptes et codes de démonstration](#comptes-et-codes-de-démonstration)
- [Règles métier](#règles-métier)
- [Structure du projet](#structure-du-projet)
- [Configuration](#configuration)
- [Tests et qualité](#tests-et-qualité)
- [Docker](#docker)
- [Documentation](#documentation)
- [Limites et passage en production](#limites-et-passage-en-production)

---

## Le problème et la réponse WafaClub

Au Maroc, les commerces de proximité (cafés, épiceries, pâtisseries, hanouts, supérettes) fidélisent
difficilement leurs clients : les cartes papier se perdent, les programmes sont cloisonnés par enseigne et les
petits commerces n'ont pas d'outil numérique abordable.

WafaClub propose :

- **une carte unique** par client, matérialisée par un QR code ;
- **un réseau de commerces** où les points sont cumulés et dépensés ;
- **des récompenses locales** créées par chaque commerce ;
- **des cartes cadeaux** simples à offrir et à valider ;
- **des promotions géolocalisées** par ville et quartier ;
- une expérience **mobile-first**, en **français** et en **arabe (RTL)**.

---

## Fonctionnalités

### Espace client

- Tableau de bord avec solde, progression, commerces favoris et activité récente.
- Carte de fidélité numérique avec QR code téléchargeable.
- Journal des points filtrable (`EARNED`, `REDEEMED`, `ADJUSTMENT`, `EXPIRED`, `REFUND`).
- Catalogue de récompenses avec recherche, filtres ville/catégorie, détail et confirmation.
- Récompense générée sous forme de **code unique non réutilisable**.
- Mes récompenses : codes en attente, utilisés, expirés.
- Promotions locales et fiches commerces.
- Cartes cadeaux : montants prédéfinis (50/100/200/500 MAD) ou personnalisés (20 à 2 000 MAD),
  pour un commerce ou tout le réseau, code unique, historique.
- Notifications internes, profil, paramètres, aide et mentions légales.

### Espace commerçant

- Tableau de bord : chiffre d'affaires simulé, points distribués, clients, récompenses validées.
- Ajout de points par **téléphone**, **QR code** (import d'image ou contenu collé) ou **client de démonstration**.
- Validation d'une récompense par code, avec contrôle du commerce et de l'expiration.
- Validation d'une carte cadeau par code, avec contrôle du périmètre et du statut.
- Liste et recherche des clients, historique des transactions, export CSV.
- CRUD des récompenses (titre, type, coût, valeur, stock, dates, activation).
- CRUD des promotions (ville, quartier, dates, activation).
- Statistiques : activité quotidienne, top clients, répartition.
- Profil du commerce et règle de points personnalisable (1 point par X MAD).

### Espace administration

- Vue consolidée : clients, commerçants, commerces, transactions, volume de cartes cadeaux.
- Recherche et filtres des utilisateurs et commerces.
- Activation / désactivation d'un commerce.
- Consultation des transactions et export CSV.
- Consultation des cartes cadeaux et promotions.

### Transverse

- Authentification par téléphone marocain normalisé (`+212…`).
- Mots de passe hachés avec **scrypt**, limitation des tentatives de connexion.
- Contrôle d'accès centralisé par rôle et garde sur chaque page.
- Journal des points **append-only** protégé par des écouteurs ORM.
- Journal d'audit des actions sensibles.
- Interface en français et en arabe (RTL).
- Design system bleu profond, or et vert, composants arrondis, responsive.
- Données de démonstration situées à Agadir et dans ses quartiers.
- Tests backend et test d'intégration UI de bout en bout.

---

## Stack technique

| Brique | Choix |
|---|---|
| Interface | **Streamlit 1.66** |
| Base de données | **SQLite** en local, **PostgreSQL** supporté via `DATABASE_URL` |
| ORM | **SQLAlchemy 2.0** |
| Validation / sécurité | Python 3.11, `hashlib.scrypt`, `secrets` |
| QR codes | `qrcode[pil]`, décodage optionnel `opencv-python-headless` |
| Tests | `pytest`, `streamlit.testing.v1.AppTest` |
| Qualité | `ruff` (lint + format) |
| Déploiement | Streamlit Cloud, Render, Docker / Docker Compose |

Aucun framework JavaScript, aucun service externe, aucun paiement réel : le MVP se lance avec deux commandes.

---

## Démarrage rapide

### Prérequis

- Python **3.11+**
- `pip`
- Facultatif : Docker Desktop

### Installation locale

```bash
python -m venv .venv
```

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux**

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Lancer l'application

```bash
streamlit run app.py
```

Ouvrir <http://localhost:8501>. Au premier démarrage, la base SQLite `data/wafaclub.db` est créée et remplie
automatiquement avec les données de démonstration.

### Réinitialiser les données

```bash
python -m wafaclub.seed --reset
```

Cette commande supprime puis recrée les tables et recharge le jeu de démonstration. Elle est destructive :
à n'utiliser que sur une base de démonstration.

---

## Comptes et codes de démonstration

**Mot de passe commun : `Demo2026!`**

| Rôle | Nom | Téléphone | Périmètre |
|---|---|---|---|
| Client | Yasmine El Amrani | `+212661234567` | Agadir, Founty |
| Client | Omar Benjelloun | `+212662345678` | Agadir, Hay Mohammadi |
| Client | Salma Ait Lahcen | `+212663456789` | Agadir, Dakhla |
| Commerçant | Hamza Alaoui | `+212664567890` | Café Argana, Épicerie Al Baraka |
| Commerçante | Imane Bennani | `+212665678901` | Pâtisserie Tazi, Supérette Dakhla |
| Commerçant | Youssef Tazi | `+212666789012` | Hanout Anza |
| Admin | Nadia Amrani | `+212660000000` | Administration |

Depuis l'écran de connexion, les boutons **Client démo**, **Commerçant démo** et **Admin démo** ouvrent
directement le compte correspondant.

### Codes utiles

| Code | Type | Usage |
|---|---|---|
| `RWD-DEMO-7K2M` | Récompense en attente | À valider par Hamza (Café Argana) |
| `RWD-DEMO-3N8P` | Récompense en attente | À valider par Imane (Pâtisserie Tazi) |
| `WFC-DEMO-4Q7N-9TX2` | Carte cadeau active | Réseau WafaClub, 100 MAD |
| `WFC-DEMO-8M2K-6RP4` | Carte cadeau active | Pâtisserie Tazi, 200 MAD |

> Un code déjà validé ne peut pas être réutilisé. Pour retrouver l'état initial, relancer
> `python -m wafaclub.seed --reset`.

---

## Règles métier

| Règle | Valeur par défaut |
|---|---|
| Conversion des points | **1 point par tranche complète de 10 MAD** (paramétrable par commerce) |
| Calcul | `floor(montant / points_per_amount)` ; 95 MAD → 9 points |
| Solde | Jamais négatif, contrôlé en base et dans les services |
| Journal | **Append-only** : aucune mise à jour ni suppression |
| Types de transaction | `EARNED`, `REDEEMED`, `ADJUSTMENT`, `EXPIRED`, `REFUND` |
| Code récompense | Aléatoire, unique, non réutilisable, valable **30 jours** |
| Carte cadeau | Montant **20 à 2 000 MAD**, validité **365 jours** |
| Paiement carte cadeau | **Simulé** (`PAID_SIMULATED`), aucun prestataire réel |
| Périmètre carte cadeau | Un commerce précis ou tout le réseau |
| Règle de points | Modifiable par le commerçant, strictement positive |
| Langues | Français par défaut et arabe RTL |

Le solde du compte et la somme du journal sont vérifiés par les tests (`ledger_is_consistent`).

---

## Structure du projet

```text
wafaclub/
├── app.py                      # point d'entrée Streamlit, bootstrap, routage public/app
├── .streamlit/config.toml      # thème et configuration Streamlit
├── wafaclub/
│   ├── config.py               # settings, constantes métier
│   ├── base.py                 # Base déclarative SQLAlchemy
│   ├── db.py                   # moteur, sessions, SQLite/PostgreSQL
│   ├── models.py               # modèle de données et enums
│   ├── access.py               # contrôle d'accès par rôle
│   ├── security.py             # scrypt, téléphones, codes aléatoires
│   ├── errors.py               # exceptions métier et codes
│   ├── qrcodes.py              # génération / décodage QR
│   ├── seed.py                 # données de démonstration
│   ├── services/               # logique métier testable
│   │   ├── auth.py
│   │   ├── loyalty.py
│   │   ├── rewards.py
│   │   ├── giftcards.py
│   │   ├── promotions.py
│   │   ├── merchants.py
│   │   ├── stats.py
│   │   ├── admin.py
│   │   ├── notifications.py
│   │   └── audit.py
│   ├── i18n/                   # fr.json, ar.json
│   └── ui/
│       ├── router.py           # sidebar, garde d'accès, navigation
│       ├── state.py            # session, langue, flash, logout
│       ├── theme.py            # CSS, RTL, design system
│       ├── components.py       # composants HTML réutilisables
│       ├── icons.py            # icônes SVG
│       ├── public.py           # landing, connexion, inscription
│       ├── client.py           # espace client
│       ├── merchant.py         # espace commerçant
│       └── admin.py            # espace administration
├── tests/                      # tests backend + intégration UI
├── docs/                       # architecture, API, sécurité, démo
├── data/                       # base SQLite locale (non versionnée)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── pyproject.toml
```

---

## Configuration

Copier `.env.example` vers `.env` et adapter les valeurs.

| Variable | Défaut | Rôle |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/wafaclub.db` | URL SQLAlchemy (SQLite ou PostgreSQL) |
| `WAFACLUB_ENV` | `development` | `development`, `staging`, `production` |
| `WAFACLUB_AUTO_SEED` | `true` | Charge les données de démo au démarrage |
| `WAFACLUB_LOGIN_MAX_ATTEMPTS` | `5` | Tentatives échouées avant blocage temporaire |
| `WAFACLUB_LOGIN_WINDOW_MINUTES` | `15` | Fenêtre de limitation |
| `WAFACLUB_APP_SECRET` | valeur locale | Secret applicatif (à remplacer en production) |
| `WAFACLUB_PAYMENTS_MODE` | `simulated` | Mode de paiement simulé |

Exemple PostgreSQL :

```bash
DATABASE_URL=postgresql+psycopg://wafaclub:mot_de_passe@localhost:5432/wafaclub
```

### Déploiement Streamlit Cloud / Render

- **Streamlit Cloud** : pointer le dépôt sur `app.py`; ajouter les secrets dans l'interface.
- **Render** : commande de démarrage
  `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true`.
- Pour un pilote réel : PostgreSQL managé, `WAFACLUB_AUTO_SEED=false`, sauvegardes et HTTPS obligatoires.

---

## Tests et qualité

```bash
# Lint
ruff check .

# Vérification du formatage
ruff format --check .

# Tests (backend + intégration UI)
pytest -q
```

Le test d'intégration UI démarre l'application réelle sur une base SQLite temporaire et vérifie :
ajout de points, création de récompense et de promotion, validation de récompense et de carte cadeau,
création de carte cadeau client, rédemption, bascule arabe/RTL et activation/désactivation d'un commerce.

**État actuel : 45 tests passent, lint et formatage conformes.**

---

## Docker

### Démarrage rapide avec SQLite

```bash
docker compose up --build
```

Application : <http://localhost:8501>. Les données sont conservées dans le volume `wafaclub_data`.

### Variante PostgreSQL

```bash
docker compose --profile postgres up --build
```

Application PostgreSQL : <http://localhost:8502> — base exposée en interne sur le service `db`.
Les identifiants de démonstration PostgreSQL sont définis dans `docker-compose.yml` et doivent être
remplacés avant tout déploiement.

### Commandes utiles

```bash
docker compose down            # arrêter
docker compose down -v         # arrêter et supprimer les volumes (destructif)
docker compose logs -f         # suivre les logs
```

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — couches, flux, modèle de données, invariants.
- [API interne](docs/API.md) — services Python, signatures, erreurs et codes de page.
- [Sécurité](docs/SECURITY.md) — contrôles, limites du MVP, conformité Maroc, checklist production.
- [Scénario de démonstration](docs/DEMO.md) — parcours de 7 minutes pour le jury.
- [Contribution](CONTRIBUTING.md) — installation, conventions, qualité, ajout de fonctionnalité.

---

## Limites et passage en production

Ce MVP est conçu pour **démontrer un produit**, pas pour encaisser de l'argent réel.

- **Paiements simulés** : aucune carte bancaire, aucun prestataire, aucun débit réel. Un futur pilote devra
  passer par un **établissement de paiement agréé** par Bank Al-Maghrib ou un partenaire conforme.
- **Authentification maison** : adaptée à la démo, à remplacer par un fournisseur d'identité, une vérification
  SMS et une gestion de sessions côté serveur pour la production.
- **SQLite** : parfait pour la démo locale, à remplacer par PostgreSQL avec migrations Alembic et sauvegardes.
- **Données personnelles** : le traitement doit être déclaré auprès de la **CNDP** et encadré par la
  **loi 09-08** (consentement, finalité, minimisation, droits d'accès et de rectification).
- **Cartes cadeaux** : leur qualification juridique (bon prépayé, avantage commercial, monnaie électronique)
  doit être validée par un conseil juridique avant lancement.
- **Pages légales** : conditions générales, politique de confidentialité, mentions légales et consentement
  cookies restent à finaliser avant une mise en ligne réelle.

Voir [docs/SECURITY.md](docs/SECURITY.md) pour la checklist complète.

---

## Crédits

Projet réalisé pour une compétition fintech. Design et développement : équipe WafaClub.
Les noms, commerces, numéros et transactions de démonstration sont fictifs.
