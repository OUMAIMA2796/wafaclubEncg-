# Sécurité WafaClub

Ce document décrit le modèle de menace du MVP, les contrôles déjà en place, ses limites et la checklist de
mise en production. Il doit être lu avec [ARCHITECTURE.md](ARCHITECTURE.md) et [API.md](API.md).

## 1. Périmètre

WafaClub est une **application de démonstration** :

- aucun argent réel n'est débité ;
- aucun prestataire de paiement n'est connecté ;
- les données de démonstration sont fictives ;
- aucune promesse de conformité PCI-DSS, SOC 2 ou ISO 27001 n'est faite.

Les contrôles ci-dessous visent à protéger les comptes, le journal des points et les données personnelles
pendant la démonstration et à préparer un futur pilote.

## 2. Actifs à protéger

| Actif | Valeur | Impact si compromis |
|---|---|---|
| Mots de passe | Identifiants de comptes | Prise de compte |
| Téléphones / e-mails | Données personnelles | Usurpation, spam |
| Solde de points | Valeur fidélité | Fraude, perte de confiance |
| Journal des points | Preuve et audit | Altération de l'historique |
| Codes récompense / cartes cadeaux | Valeur monétaire simulée | Fraude interne ou externe |
| Notifications et audit | Traçabilité | Perte d'auditabilité |
| Configuration | Secrets, URL de base | Accès à la base |

## 3. Frontières de confiance

```text
Navigateur (non fiable)
   │ HTTPS attendu en production
   ▼
Streamlit / UI (semi-fiable : rendu + session)
   │ appels Python internes
   ▼
Services (confiance applicative)
   │ SQL paramétré
   ▼
Base de données (confiance stockage)
```

- Le navigateur n'est jamais considéré comme fiable pour une décision de sécurité.
- Les formulaires Streamlit sont revalidés côté serveur par les services.
- La session Streamlit est côté serveur (`st.session_state`), pas dans un cookie signé par le client.
- La base est accessible uniquement par le processus applicatif (pas d'API publique directe).

## 4. Contrôles en place

### Authentification

- Mots de passe hachés avec **scrypt** (`n=2^14`, `r=8`, `p=1`, sel aléatoire de 16 octets) dans
  `wafaclub/security.py`.
- Vérification en temps constant (`hmac.compare_digest`).
- Hash factice (`DUMMY_PASSWORD_HASH`) pour égaliser le temps de réponse d'un compte absent.
- Validation de la force : au moins 8 caractères, une lettre et un chiffre.
- Téléphones marocains normalisés vers `+212…` (formats acceptés : `06…`, `00212…`, `+212…`).
- Limitation des tentatives : 5 échecs sur 15 minutes par téléphone, journalisés dans `login_attempts`.
- Dernière connexion enregistrée (`last_login_at`).
- Comptes désactivables (`is_active`), vérifiés à l'authentification et à l'accès.

### Autorisation

- Matrice centralisée dans `wafaclub/access.py` : `CLIENT_PAGES`, `MERCHANT_PAGES`, `ADMIN_PAGES`, `PAGE_ROLES`.
- `router.render(user)` vérifie `can_access(user.role, page)` avant d'afficher quoi que ce soit.
- Les services re-vérifient les droits :
  - `merchants.assert_manage_access` : propriétaire ou admin ;
  - `merchants.set_active` : admin uniquement ;
  - `rewards._assert_owner` : propriétaire du commerce ;
  - `promotions._assert_owner` : propriétaire du commerce ;
  - `auth.require_active` : compte actif.
- Un utilisateur ne voit que ses propres données (points, récompenses, notifications, cartes cadeaux).

### Protection du journal des points

- `PointTransaction` est **append-only** via des écouteurs ORM `before_update` et `before_delete`.
- Toute correction crée une contre-écriture (`REFUND`, `ADJUSTMENT`, `EXPIRED`, `REDEEMED`).
- `ledger_is_consistent` permet de vérifier qu'un solde égale la somme du journal.
- Les écritures verrouillent le compte (`with_for_update`) avant mise à jour du solde.
- Contraintes de base : solde non négatif, points non nuls, montant non négatif.

### Codes et références

- Générés avec `secrets.choice` sur un alphabet de 32 caractères sans ambiguïté (`O/0`, `I/1` exclus).
- Longueur suffisante (8 à 12 caractères selon le type).
- Unicité vérifiée en base avant insertion, avec plusieurs tentatives.
- Non séquentiels et non prédictibles.

### Validation et injection

- Toutes les entrées utilisateur sont validées dans les services (longueur, format, bornes).
- Les montants utilisent `Decimal` quantifié à 2 décimales (`to_decimal`).
- Les requêtes SQL passent par l'ORM SQLAlchemy (pas de SQL brut avec interpolation).
- Le contenu utilisateur rendu en HTML est échappé avec `esc()` avant injection dans
  `unsafe_allow_html=True`.
- Les formulaires Streamlit sont revalidés côté serveur.

### Audit et traçabilité

- `audit_logs` enregistre les actions sensibles avec acteur, entité, métadonnées et horodatage.
- `login_attempts` conserve les tentatives de connexion.
- Aucun mot de passe ni hash n'est journalisé.

### RGPD / données personnelles (principes appliqués)

- Minimisation : seuls les champs nécessaires sont collectés (prénom, nom, téléphone, ville, quartier,
  e-mail optionnel).
- Finalité : fidélité, récompenses, cartes cadeaux, promotions.
- Droit d'accès / rectification : profil modifiable par le client, lecture par l'admin.
- Suppression en cascade pour les comptes supprimés (`ondelete="CASCADE"` sur `loyalty_accounts`,
  `notifications`).
- Pas de cookie tiers ni de tracker dans l'application.

## 5. Limites et risques connus

### Authentification et sessions

- **Pas de MFA**, pas de vérification SMS, pas de réinitialisation de mot de passe.
- **Session en mémoire serveur** (`st.session_state`) : perte si le processus redémarre, non portable
  entre plusieurs instances sans sticky sessions.
- **Pas de verrouillage par IP** : la limitation est par numéro de téléphone uniquement.
- **Pas de gestion de durée de session** ni de déconnexion automatique par inactivité.
- Les comptes de démonstration partagent un mot de passe connu (`Demo2026!`) : à désactiver avant
  toute mise en ligne.

### Stockage et données

- **SQLite** par défaut : pas de haute disponibilité, pas de réplication, écritures sérialisées.
- **Pas de chiffrement au repos** des bases SQLite/PostgreSQL.
- **Pas de sauvegarde automatique** ni de plan de restauration testé.
- **Pas de migrations versionnées** : `create_all()` crée les tables si absentes mais ne modifie pas
  un schéma existant.
- **Pas de purge** ni de politique de rétention automatisée.
- L'export CSV n'est pas chiffré et peut contenir des données personnelles.

### Paiements et valeur monétaire

- Les cartes cadeaux sont **simulées** : aucune monnaie réelle ne circule.
- Aucune qualification juridique des cartes cadeaux (bon prépayé, monnaie électronique, avantage commercial).
- Aucun contrôle anti-blanchiment, KYC ni détection de fraude.

### Infrastructure

- **Pas de HTTPS** dans la configuration par défaut : obligatoire en production.
- **Pas de WAF**, pas de limitation de débit HTTP, pas de protection CSRF explicite au-delà de Streamlit.
- **Pas de journalisation centralisée** ni de supervision.
- **Pas de tests de charge** ni de tests de sécurité offensifs.
- **Pas d'analyse de dépendances** automatisée (SCA) dans ce dépôt.

### Conformité Maroc

- **Loi 09-08** (protection des données personnelles) : le traitement doit être déclaré / autorisé
  auprès de la CNDP, avec information des personnes concernées et respect des droits d'accès, de
  rectification et d'opposition.
- **Établissement de paiement** : toute encaisse réelle nécessite un agrément de Bank Al-Maghrib
  (loi bancaire 103-12) ou le passage par un partenaire agréé.
- **Protection du consommateur** (loi 31-08) : conditions générales, information sur les prix,
  rétractation le cas échéant.
- **Échanges électroniques** (loi 53-05) : validité des transactions et preuves électroniques.
- **Comptabilité et fiscalité** : aucune gestion comptable, TVA ou facturation n'est prévue.

## 6. Checklist de mise en production

### Authentification et accès

- [ ] Remplacer l'authentification maison par un fournisseur d'identité (OAuth2/OIDC) ou une vérification
      SMS robuste.
- [ ] Ajouter la réinitialisation de mot de passe et la MFA.
- [ ] Gérer la durée de session et la déconnexion par inactivité.
- [ ] Ajouter une limitation de débit par IP et par compte.
- [ ] Supprimer ou désactiver les comptes de démonstration.
- [ ] Revoir les droits d'administration (least privilege).

### Données et stockage

- [ ] Passer à PostgreSQL avec pool de connexions et migrations Alembic.
- [ ] Activer le chiffrement au repos et le chiffrement des sauvegardes.
- [ ] Mettre en place des sauvegardes quotidiennes testées et un plan de restauration.
- [ ] Définir une politique de rétention et de purge.
- [ ] Chiffrer les exports contenant des données personnelles.

### Infrastructure

- [ ] HTTPS obligatoire (certificat valide, HSTS).
- [ ] Reverse proxy avec WAF et limitation de débit.
- [ ] Secrets managés (pas de `.env` en production).
- [ ] Supervision, alertes et journalisation centralisée.
- [ ] Analyse automatique des dépendances (SCA) et mises à jour de sécurité.
- [ ] Tests de charge et de sécurité (pentest).

### Conformité

- [ ] Déclaration / autorisation CNDP pour le traitement des données.
- [ ] Conditions générales, politique de confidentialité, mentions légales.
- [ ] Consentement explicite et traçable.
- [ ] Validation juridique de la qualification des cartes cadeaux.
- [ ] Agrément ou partenariat avec un établissement de paiement agréé avant tout encaissement réel.
- [ ] DPIA (analyse d'impact) pour le traitement des données clients.

### Produit

- [ ] Remplacer les paiements simulés par un flux réel et audité.
- [ ] Ajouter KYC/AML si nécessaire selon le volume et le modèle.
- [ ] Tests d'accessibilité et d'expérience mobile.
- [ ] Documentation utilisateur et support.

## 7. Signalement

Toute vulnérabilité doit être signalée de façon **privée** au mainteneur du projet, sans ouvrir d'issue
publique. Inclure les étapes de reproduction, l'impact estimé et, si possible, une proposition de
correctif. Le projet s'engage à répondre dans un délai raisonnable.

## 8. Références

- Loi 09-08 relative à la protection des personnes physiques à l'égard du traitement des données à
  caractère personnel (Maroc) et CNDP.
- Loi 103-12 relative aux établissements de crédit et organismes assimilés (agrément des prestataires
  de services de paiement).
- Loi 31-08 édictant des mesures de protection du consommateur.
- Loi 53-05 relative à l'échange électronique de données juridiques.
- Recommandations OWASP pour les applications web (Top 10).
