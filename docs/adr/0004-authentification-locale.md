# ADR-0004 — Authentification locale, mot de passe défini par l'agent

- **Statut** : **Accepté** — la plateforme gère ses propres identifiants. L'annuaire de la banque
  (Active Directory / LDAP / Microsoft 365) **n'est pas** la source d'identité. Remplace le volet
  « Authentification AD / LDAP / M365 » de `CLAUDE.md` §4 et §5, et de
  [ADR-0001](0001-choix-de-la-stack.md).
- **Date** : 10 juillet 2026.
- **Décideurs** : porteur du projet (DSI AFG Bank Mali).

## Contexte

Le cahier des charges annonçait une authentification adossée à l'annuaire de la banque. Le code n'a
jamais eu cette plomberie : `settings.auth_mode` était déclaré mais **lu nulle part**, et
`application.auth.authentifier` refuse tout ce qui n'est pas `source_auth = 'LOCAL'`. Un compte
`OIDC` n'aurait pu se connecter par aucun moyen.

Le circuit local, lui, est complet et éprouvé :

1. L'administrateur crée le compte. **Aucun mot de passe n'y est fixé.**
2. Un e-mail part avec un lien d'activation expirable (`activation_validite_minutes`, 1 h), porteur
   d'un jeton haché à usage unique (`core.reinitialisation_mdp`).
3. L'agent définit son mot de passe. Le compte est inutilisable avant.

S'y ajoutent le mot de passe oublié (réponse identique que le compte existe ou non — aucune
énumération), le blocage et l'expiration appliqués à chaque requête, et le contrôle du domaine
e-mail (`domaines_email_autorises`).

Brancher OIDC aujourd'hui serait un lot à part entière — redirection Entra ID, validation de jeton,
provisionnement au premier login, chemin de secours en cas de panne d'annuaire — pour un besoin qui
n'est pas exprimé.

## Décision

**L'authentification reste locale.** Chaque agent définit son mot de passe pour DSI 360, via le lien
d'activation reçu par e-mail.

Le réglage `settings.auth_mode` est **supprimé** : un bouton qui ne commande rien est un mensonge de
configuration. La colonne `core.utilisateur.source_auth` est **conservée** avec sa contrainte
`CHECK (LOCAL, OIDC, LDAP)` — elle ne coûte rien et marque la porte par laquelle une source
d'identité externe entrerait un jour, sans prétendre qu'elle existe déjà.

## Conséquences

- ➕ Aucune dépendance à l'annuaire : la plateforme démarre et fonctionne seule.
- ➕ Le circuit est déjà en place, testé, et sans mot de passe transmis par un tiers.
- ➖ **Un mot de passe de plus** pour chaque agent, hors du référentiel de la banque : pas de MFA,
  pas de révocation centralisée quand un agent quitte l'entreprise. Le blocage et l'expiration de
  compte (`actif`, `expire_le`) restent le seul levier, et ils sont manuels.
- ➖ Le module **Cybersécurité** du cahier prévoit MFA et revue des accès : ces exigences ne sont
  pas couvertes par l'authentification. Elles restent à traiter, ou à retirer du périmètre.
- `CLAUDE.md` §4 et §5, `docs/01-ARCHITECTURE.md`, `docs/03-API-CONTRACTS.md`,
  `docs/04-SECURITY.md` et `docs/07-ROADMAP.md` sont mis en accord.

## Si l'on revient sur cette décision

`source_auth` distingue déjà les comptes. Il faudrait : un endpoint de redirection vers Entra ID,
la validation du jeton d'identité, le provisionnement au premier login (avec un profil **sans aucun
accès** par défaut, l'administrateur ouvrant ensuite les modules), et **conserver `LOCAL` pour le
compte d'amorçage** — sans quoi une panne d'annuaire ferme la porte à tout le monde.
