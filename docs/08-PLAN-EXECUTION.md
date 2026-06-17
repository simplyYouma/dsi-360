# 08 — Plan d'exécution

> Plan de réalisation **intégrale**, par incréments **vérifiés** (lint/types/tests + build) et
> **commités**. Ordre : socle transverse d'abord, puis modules en tranches verticales (API + UI +
> tests), du plus structurant au plus périphérique. Référence fonctionnelle : docs/02 & 07.

## Principe d'exécution

- Chaque incrément est **livré complètement** (back + front + tests) puis commité/poussé.
- **Tranche verticale** par module : domaine → migration → repository → cas d'usage → API → UI → tests.
- On **vérifie** systématiquement (`tsc`/`eslint` front ; `ruff`/`mypy`/`pytest` back ; build).

## Lot P1-0 — Socle transverse (en cours)

1. **Shell UI premium** — sidebar repliable + topbar. ✅
2. **Backend opérationnel** — engine async, runner de migrations, `/healthz` + `/readyz` (DB), stack Docker qui tourne.
3. **Référentiels & seed** — profils (7), directions, catégories, matrices priorité/SLA, compte admin (LOCAL).
4. **Authentification** — mode LOCAL (argon2 + JWT) maintenant, **OIDC Entra ID** branché plus tard ; refresh + logout.
5. **RBAC & cloisonnement** — dépendances de garde côté API ; matrice profil→modules paramétrable ; garde de routes UI ; page login premium.
6. **Audit append-only** — journal chaîné, acteur figé, middleware d'enregistrement.
7. **Domaine Activité** — entité + machines à états + **moteur SLA** (priorité P1–P5, échéances) + ordonnanceur Celery (approche/dépassement).
8. **Notifications** — e-mail + interne (socle ; Teams/WhatsApp en P2).

## Phase 1 — Cœur opérationnel (tranches verticales)

9. **Incidents** (tranche de référence : valide tout le socle de bout en bout).
10. **Demandes de service** (catégories, workflow de validation).
11. **Projets** (jalons, budget, % avancement, COPIL).
12. **Tableau de bord exécutif** — vrais indicateurs + graphiques premium (composition, donut, sparklines) + exports PDF/Excel/CSV.

## Phase 2 — Gouvernance & maîtrise

13. **Changements (ITIL)** — RFC, CAB/ECAB, impact/risque, déploiement & retour arrière.
14. **Audit & Recommandations** — sources, plan d'action, validation de clôture.
15. **Risques IT** — criticité (proba × impact), traitement, revue.
16. **Notifications Teams/WhatsApp** + reporting avancé.

## Phase 3 — Sécurité & extension

17. **Cybersécurité** (habilitations, comptes admin, vulnérabilités, MFA, IAM).
18. **Gouvernance DSI** (COPIL, comités, décisions DG, engagements).
19. **PRA · Budget DSI · mobile**.
20. **Durcissement + recette sécurité RSSI** → mise en production.

## Décisions externes (n'arrêtent pas le chantier — paramétrage le moment venu)

Stack validée DSI (info) · tenant **Entra ID** + comptes de service · hébergement/HA · **SLA réels**
et catégories par module · exigences **RSSI** (rétention, recette).
