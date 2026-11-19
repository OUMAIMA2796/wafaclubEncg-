# Contribuer à WafaClub

Merci de votre intérêt pour WafaClub. Ce guide décrit l'environnement de développement, les conventions et
les contrôles à passer avant toute contribution.

## Prérequis

- Python 3.11+
- Git
- Facultatif : Docker Desktop

## Installation

```bash
git clone <url-du-depot>
cd wafaclub
python -m venv .venv
```

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

Puis :

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env   # Windows : Copy-Item .env.example .env
python -m wafaclub.seed --reset
streamlit run app.py
```

## Avant de proposer une modification

Exécuter les trois contrôles suivants :

```bash
ruff check .
ruff format --check .
pytest -q
```

Le projet applique :

- `ruff` pour le lint et le formatage (largeur 120, quotes doubles) ;
- `pytest` pour les tests backend et le test d'intégration UI ;
- `compileall` peut être utilisé en complément :
  `python -m compileall -q app.py wafaclub tests`.

Une contribution n'est acceptée que si **lint, format et tests passent**.

## Conventions de code

- Python 3.11, annotations de type systématiques sur les fonctions publiques.
- Pas de logique métier dans les pages Streamlit : les pages appellent les services de `wafaclub/services/`.
- Les services reçoivent une `Session` SQLAlchemy et ne créent jamais de session eux-mêmes.
- Les erreurs métier utilisent les exceptions de `wafaclub/errors.py` avec un `code` stable.
- Aucune donnée sensible, aucun secret et aucun identifiant réel dans le dépôt.
- Les montants utilisent `Decimal` et les dates sont stockées en UTC naïf (`utcnow()`).
- Les codes (récompenses, cartes cadeaux, références) sont générés avec `secrets`, jamais de façon séquentielle.

### Nommage

- Modules et fonctions : `snake_case`.
- Classes : `PascalCase`.
- Enums métier : valeurs en `UPPER_SNAKE_CASE`.
- Clés i18n : `domaine.sous_domaine.element` (ex. `client.gift.confirm_title`).

## Ajouter ou modifier une page

1. Créer la fonction `render_*` dans le module UI concerné (`client.py`, `merchant.py`, `admin.py`).
2. Ajouter la clé de page dans `wafaclub/access.py` (`CLIENT_PAGES`, `MERCHANT_PAGES` ou `ADMIN_PAGES`).
3. Ajouter l'entrée de navigation dans `wafaclub/ui/router.py` si la page est accessible depuis la sidebar.
4. Ajouter les traductions dans `wafaclub/i18n/fr.json` et `wafaclub/i18n/ar.json`.
   Les deux fichiers doivent rester strictement à parité.
5. Vérifier que les textes dynamiques injectés en HTML passent par `esc()`.
6. Ajouter un test de service et, si le parcours est critique, l'inclure dans `tests/test_ui_smoke.py`.

## Modifier le modèle de données

Le MVP utilise `Base.metadata.create_all()` au démarrage. Pour une évolution :

1. Modifier `wafaclub/models.py`.
2. Mettre à jour `wafaclub/seed.py` et les tests concernés.
3. Documenter la migration dans la description de la contribution.
4. En production, ne pas compter sur `create_all()` : introduire **Alembic** et des migrations versionnées.

Toute modification du journal `PointTransaction` doit préserver son caractère **append-only**.
Ne jamais mettre à jour ni supprimer une ligne existante : créer une contre-écriture
(`REFUND`, `ADJUSTMENT`, `EXPIRED`, etc.).

## Traductions

- Le français est la langue de référence.
- L'arabe doit rester à parité de clés avec le français et conserver les mêmes placeholders.
- Les anciennes préférences darija retombent sur le français.
- Tester le rendu arabe (RTL) après toute modification de mise en page.
- Ne pas concaténer des fragments de phrase traduits : utiliser des placeholders (`{name}`, `{points}`).

Le test `tests/test_i18n_qr.py` vérifie la parité FR/AR, les placeholders et le repli des anciennes préférences.

## Sécurité

- Ne jamais journaliser un mot de passe, un hash ou un code de carte cadeau complet.
- Ne pas exposer `password_hash` dans une page ou un export.
- Vérifier les droits dans le service, même si l'UI a déjà filtré l'accès.
- Utiliser `esc()` pour tout contenu utilisateur rendu avec `unsafe_allow_html=True`.
- Les paiements restent **simulés** : ne pas intégrer de prestataire réel sans validation juridique et
  conformité Bank Al-Maghrib / CNDP.
- Signaler toute faille de sécurité de façon privée au mainteneur, sans ouvrir d'issue publique.

## Tests

- Tests backend : `tests/test_auth.py`, `test_loyalty.py`, `test_rewards.py`, `test_giftcards.py`,
  `test_access.py`, `test_seed_stats.py`, `test_i18n_qr.py`.
- Test d'intégration UI : `tests/test_ui_smoke.py` (base SQLite temporaire, parcours réels via `AppTest`).
- Les fixtures de `tests/conftest.py` créent une base isolée par test.
- Un test doit être déterministe, indépendant de l'ordre d'exécution et ne jamais toucher `data/wafaclub.db`.

## Commits et pull requests

Format de commit suggéré :

```text
type(scope): résumé court

Corps optionnel : contexte, décision, impact.
```

Types : `feat`, `fix`, `test`, `docs`, `refactor`, `style`, `chore`, `security`.

Une pull request doit contenir :

- [ ] un résumé du changement et de la motivation ;
- [ ] les captures ou le parcours de démonstration si l'UI change ;
- [ ] les tests ajoutés ou mis à jour ;
- [ ] `ruff check .`, `ruff format --check .` et `pytest -q` verts ;
- [ ] la documentation mise à jour si nécessaire ;
- [ ] aucune donnée personnelle réelle, aucun secret, aucune base `data/*.db` versionnée.

## Licence et données de démonstration

Les données de démonstration (noms, téléphones, commerces, transactions) sont fictives. Ne pas les remplacer
par des données réelles de clients ou de commerçants sans base légale et mesures de sécurité adaptées.
