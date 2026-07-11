# 04 — Sécurité

> Sécurité par défaut (CLAUDE.md §6). Toute entrée est hostile ; **tout accès est vérifié côté
> serveur**, jamais seulement à l'écran. Réutilise les briques éprouvées de **DORIS**.

## 1. Authentification — locale (cf. [ADR-0004](adr/0004-authentification-locale.md))

La plateforme gère ses propres identifiants. L'annuaire de la banque (AD / LDAP / Microsoft 365)
n'est **pas** la source d'identité : cette plomberie n'existe pas, et le besoin n'est pas exprimé.

- **Création d'un compte** : l'administrateur le crée, **sans y fixer de mot de passe**. Un e-mail
  part avec un lien d'activation expirable (1 h), porteur d'un jeton **haché à usage unique**
  (`core.reinitialisation_mdp`). L'agent définit son mot de passe ; le compte est inutilisable avant.
- **Mot de passe** : haché en **argon2**. Jamais transmis par un tiers, jamais stocké en clair.
- **Mot de passe oublié** : réponse identique que le compte existe ou non — aucune énumération de
  comptes possible. Même mécanisme de jeton haché, à usage unique.
- **Frein sur les tentatives** : après `login_echecs_max` échecs consécutifs (5 par défaut), le
  compte est verrouillé `login_verrou_minutes` (15 par défaut). Le verrou **prime sur le mot de
  passe** — sinon un attaquant saurait, en tombant juste, qu'il a trouvé le bon. Réponse **429** avec
  `Retry-After`. Le verrou est **temporaire** : définitif, il permettrait d'exclure n'importe quel
  agent du système en se trompant exprès à sa place. Un e-mail inconnu ne fait rien écrire, et reçoit
  le même 401 générique. Chaque tentative est journalisée (`CONNEXION_ECHOUEE`, `CONNEXION_BLOQUEE`).
- **Session** : **JWT d'accès court** (15 min) + refresh. Déconnexion = oubli des jetons côté client.
- **Compte coupé immédiatement** : `actif` et `expire_le` sont vérifiés **à chaque requête** — un
  jeton encore valide ne survit pas au blocage.
- **Domaine e-mail** contrôlé à la création (`domaines_email_autorises`).
- `core.utilisateur.source_auth` (`LOCAL` / `OIDC` / `LDAP`) est conservé : il marque la porte par
  laquelle une source externe entrerait un jour, sans prétendre qu'elle existe.

**Limite assumée** : un mot de passe de plus pour chaque agent, hors du référentiel de la banque —
donc pas de révocation centralisée au départ d'un collaborateur. Le blocage et l'expiration de
compte restent le levier, et ils sont manuels.

**MFA — décidé, non implémenté.** DSI 360 n'a aujourd'hui **aucun second facteur**. Le MFA qui
apparaît dans le module Cybersécurité est un *sujet suivi* (le déploiement MFA de la banque), pas un
mécanisme d'authentification de la plateforme. Décision : un **TOTP réservé aux administrateurs**,
qui créent les comptes, distribuent le travail et lisent le journal d'audit — c'est là qu'est le
risque. À construire après le frein ci-dessus, qui le précède : un second facteur posé sur une porte
qu'on peut marteler indéfiniment protégerait moins bien qu'un simple frein.

## 2. Autorisation — RBAC (profils métier) + cloisonnement

- **Profils métier paramétrables** (cf. domaine §5 et [ADR-0003](adr/0003-profils-metier-et-perimetre-dsi.md)) :
  Administrateur, IT Support Applicatif et HelpDesk, Réseau télécom, Système et Réseau télécom,
  IT Support Applicatif. Créables/renommables/supprimables depuis l'administration.
  - Deux garde-fous **côté serveur** : un profil porté par des comptes ne se supprime pas, et
    `ADMIN` ne se supprime pas et reste transverse (anti-verrouillage).
  - Un profil créé n'ouvre **aucun** module tant qu'on ne lui en donne pas (sécurité par défaut).
- **Deux niveaux** :
  1. **Accès aux modules et aux actions** : matrice **profil → module → action**, **paramétrable**.
  2. **Cloisonnement par direction** : un profil non transverse ne voit que les activités de sa
     direction (ou celles sans direction). La plateforme ne servant que la DSI, ce cloisonnement
     est neutre aujourd'hui ; le mécanisme et ses tests restent en place.
- **Actions sensibles gardées en dur** (séparation des tâches, non paramétrable) : validation
  **CAB/ECAB**, clôture d'activité, validation de clôture d'audit, paramétrage, gestion des comptes.
- Vérification **systématiquement côté API** (dépendances de garde), jamais seulement dans l'UI.

## 3. Traçabilité / audit (append-only)

- Journalisation de **toute** action : `utilisateur, date/heure, module, action, ancienne valeur →
  nouvelle valeur, adresse IP` (exigence cahier §7).
- **Append-only**, **chaînage par empreinte** (toute altération devient détectable), jamais de
  suppression. L'acteur est **figé à l'écriture** (survit à la suppression du compte).
- Consultable par les administrateurs ; rétention et archivage (> N jours) à cadrer avec le RSSI.

## 4. Données & secrets

- **Secrets jamais commités** (`.env` hors dépôt, `.env.example` fourni) ; rotation possible.
- **TLS** partout (reverse proxy) ; cookies/jetons sécurisés ; en-têtes de sécurité (HSTS, etc.).
- **Validation stricte** des entrées (schémas), requêtes paramétrées (pas d'injection), tailles de
  fichiers bornées, types de pièces jointes contrôlés.
- **Cloisonnement filiale/périmètre** appliqué au niveau des requêtes (jamais de fuite inter-périmètre).

## 5. Conformité (références du cahier / procédures)

Circulaires **BCEAO** (n°03-2017 contrôle interne, n°04-2017 gestion des risques), ordonnance TIC.
Le module **Cybersécurité** (habilitations sensibles, comptes admin, revue d'accès, vulnérabilités,
correctifs, MFA, IAM) outille ces obligations. **Recette sécurité RSSI** prévue avant mise en production.

## 6. Durcissement HTTP

- **En-têtes de sécurité** posés sur chaque réponse (middleware global) : `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`
  (géoloc/micro/caméra coupés), et `Strict-Transport-Security` **hors dev** (TLS présent).
- **Frein sur les connexions** (cf. §1), **jetons courts**, **cloisonnement** vérifié côté serveur.
- Tests de non-régression : `tests/integration/test_securite.py` (en-têtes, 401 sans jeton, jeton
  falsifié rejeté, journal append-only).
- **Test d'intrusion rejouable** (`backend/scripts/pentest.py`, lanceur `infra\local\pentest.ps1`) :
  boîte grise, un agent à faible privilège tente de franchir 21 gardes (auth & jetons, élévation de
  privilège, incarnation, écriture sur incident importé, auto-désignation sur activité, injection
  SQL, fuite d'erreur, en-têtes). Chaque tentative doit être refusée ; le script sort en erreur à la
  première faille. À dérouler avant chaque mise en production, contre une instance de recette.

## 7. Résilience — survivre à une base qui tombe

Le serveur d'hébergement tombe souvent : l'application **ne doit pas tomber avec lui**.

- **Moteur de base réglé pour l'instabilité** (`infrastructure/db/base.py`) : `pool_pre_ping` (une
  base redémarrée ne renvoie plus une connexion morte), `pool_recycle` 30 min, pool borné, et
  surtout des **délais** — connexion 10 s, requête 30 s (`command_timeout` asyncpg +
  `statement_timeout` Postgres). Une requête ne pend plus indéfiniment ; sans quoi les connexions
  s'accumulent jusqu'à faire tomber l'app avec la base.
- **Base injoignable → 503 propre** (gestionnaire global), jamais un 500 qui fuit des détails ;
  l'app se rétablit seule dès que la base revient.
- **Migrations au démarrage** enveloppées : leur échec est journalisé, il ne bloque pas le boot.
- **Ordonnanceur SLA isolé** : un scan raté ne tue jamais la boucle.
- **Disjoncteur SMTP** : une panne d'e-mail n'interrompt jamais une action ; l'app reste utilisable
  hors ligne (cf. §1).
- **Client web** : serveur injoignable → message clair (« Service injoignable… »), pas un
  « Failed to fetch » cryptique.

## 8. Disponibilité (exploitation)

Objectif **> 99 %** : réplication applicative (plusieurs workers API), Postgres avec sauvegardes,
supervision, et plan de reprise (PRA — Phase 3). **Reste côté exploitation** : TLS au reverse-proxy,
sauvegardes régulières de PostgreSQL, et — pour ouvrir les e-mails — un SMTP AFG et
`DSI360_NOTIF_EMAIL_ACTIVE=true`. À cadrer avec la DSI/exploitation.
