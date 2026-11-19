# Scénario de démonstration WafaClub (7 minutes)

Ce parcours est conçu pour un jury fintech. Il montre le problème, la réponse produit et la robustesse
technique sans dépendre d'Internet ni de services externes.

## Préparation (30 secondes)

```bash
python -m wafaclub.seed --reset
streamlit run app.py
```

Ouvrir <http://localhost:8501>. Vérifier que la page d'accueil affiche le slogan
« Une seule carte, plusieurs commerces, plus de récompenses. ».

## 1. Problème et solution (1 minute)

- Présenter la landing page : problème (cartes papier perdues, programmes cloisonnés), solution (carte unique
  numérique, réseau de commerces), sécurité (paiements simulés).
- Montrer les badges **Paiement simulé**, **QR**, **MAD**.
- Cliquer sur **Découvrir les cartes cadeaux** ou **Client démo**.

## 2. Parcours client — fidélité (1,5 minute)

Se connecter avec le bouton **Client démo** (Yasmine).

1. **Tableau de bord** : solde, progression, commerces favoris, activité récente.
2. **Ma carte & QR** : carte numérique, QR code à télécharger.
3. **Mes points** : journal filtrable, solde cohérent.
4. **Récompenses** : catalogue avec recherche et filtres.
   - Ouvrir une récompense abordable, cliquer **Utiliser mes points**, confirmer.
   - Montrer le code généré (`RWD-…`) et sa validité.
5. **Mes récompenses** : code en attente.
6. **Promotions** et **Commerces** : fiches locales.

Points à mentionner : **1 point par tranche de 10 MAD**, journal **append-only**, code **non réutilisable**.

## 3. Parcours commerçant — valeur créée (2 minutes)

Se déconnecter, puis **Commerçant démo** (Hamza, Café Argana + Épicerie Al Baraka).

1. **Tableau de bord** : clients, points distribués, récompenses validées.
2. **Ajouter des points** :
   - onglet **Client démo** → choisir un client → montant 250 MAD → **Enregistrer** ;
   - montrer le calcul `+25 points` et le nouveau solde.
   - onglet **Téléphone** : rechercher `+212661234567`.
   - onglet **QR code** : coller `WAFACLUB:QR:…` (ou importer une photo).
3. **Valider une récompense** : saisir `RWD-DEMO-7K2M` → validation.
4. **Clients** : tableau + export CSV.
5. **Récompenses** : créer une récompense (titre, coût, valeur, stock, dates).
6. **Promotions** : créer une promotion locale.
7. **Statistiques** : activité quotidienne, top clients.

Points à mentionner : **contrôle du commerçant sur ses propres données**, **audit**, **multi-commerce**
pour un même propriétaire.

## 4. Cartes cadeaux et administration (1,5 minute)

### Client

Se reconnecter en **Client démo**.

1. **Cartes cadeaux** → **Créer une carte cadeau**.
2. Choisir 50 MAD, destinataire « Nadia », confirmer le paiement simulé.
3. Montrer le code `WFC-…`, la validité et l'historique.

### Commerçant

Se reconnecter en **Commerçant démo**.

1. **Cartes cadeaux** → saisir `WFC-DEMO-4Q7N-9TX2` → vérifier → valider.
2. Montrer la confirmation et le statut `UTILISÉE`.

### Administration

Se reconnecter en **Admin démo**.

1. **Tableau de bord** : indicateurs réseau.
2. **Commerces** : filtrer, désactiver puis réactiver un commerce.
3. **Transactions** : filtres et export CSV.
4. **Cartes cadeaux** et **Promotions** : vue consolidée.

## 5. Multilingue et mobile (1 minute)

- Depuis n'importe quelle page, changer la langue en **العربية**.
- Montrer le passage en **RTL** (direction droite-à-gauche) et les libellés arabes.
- Redimensionner la fenêtre pour montrer le rendu mobile (layout responsive).

## 6. Clôture technique (30 secondes)

- Lancer les tests devant le jury :

```bash
ruff check .
ruff format --check .
pytest -q
```

- Mentionner : **45 tests verts**, journal **append-only protégé**, **paiements simulés**, **aucune donnée bancaire**.
- Indiquer la documentation : `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/SECURITY.md`.

## Messages clés pour le jury

1. **Valeur utilisateur** : une seule carte pour plusieurs commerces, récompenses locales, cadeaux simples.
2. **Valeur commerçant** : outil numérique accessible, statistiques, fidélisation mesurable.
3. **Robustesse** : règles métier testées, journal immuable, codes sécurisés.
4. **Conformité** : paiements simulés, avertissements juridiques marocains, aucune donnée bancaire.
5. **Exécution** : MVP complet, démontrable en 7 minutes, déployable en Docker.
