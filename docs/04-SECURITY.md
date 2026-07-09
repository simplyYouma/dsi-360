# 04 — Sécurité

> Sécurité par défaut (CLAUDE.md §6). Toute entrée est hostile ; **tout accès est vérifié côté
> serveur**, jamais seulement à l'écran. Réutilise les briques éprouvées de **DORIS**.

## 1. Authentification — AD / LDAP / Microsoft 365

- **Source d'identité** : annuaire de la banque via **OIDC (Microsoft Entra ID)** en priorité, LDAP/AD
  en repli. L'application **ne stocke pas** les mots de passe des comptes annuaire.
- **Flux** : connexion → jeton **OIDC** validé → création/rafraîchissement du profil applicatif →
  **JWT d'accès court** + **refresh**. Déconnexion = révocation du refresh.
- **Comptes locaux** : uniquement pour des cas techniques/exceptionnels (compte de service,
  bootstrap), avec mot de passe **haché (argon2)** et changement imposé à la 1re connexion.
- **MFA** : délégué à Entra ID / M365 (conforme au cahier, module Cybersécurité).
- **Préparation** : `source_auth` (LDAP / OIDC / LOCAL) porté par le compte, pour basculer sans refonte.

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

## 6. Disponibilité

Objectif **> 99 %** : réplication applicative (plusieurs workers API), Postgres avec sauvegardes,
supervision, et plan de reprise (PRA — Phase 3). À cadrer avec la DSI/exploitation.
