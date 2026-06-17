# ADR-0001 — Choix de la stack technique

- **Statut** : **Accepté** — décision projet : on retient la **meilleure stack moderne** (option C),
  la stack du cahier (Laravel/MySQL/Blade/AdminLTE) **n'est pas retenue**. À présenter à la DSI pour
  information ; ajustable seulement si une contrainte d'exploitation forte l'impose (cf. repli option B).
- **Date** : 17 juin 2026.
- **Décideurs** : équipe projet (maîtrise technique) ; DSI informée.

## Contexte

Le cahier des charges impose une stack : **Laravel 12 (PHP) + MySQL 8 + Blade + AdminLTE**,
authentification **AD / LDAP / Microsoft 365**, **ChartJS**, exports PDF/Excel, multi-utilisateurs,
haute disponibilité.

Deux tensions justifient de réexaminer ce choix **avant** de poser les fondations :

1. **AdminLTE est un template d'administration standard** (Bootstrap prêt à l'emploi). Il va à
   l'encontre de l'exigence de qualité du projet : interface **premium, originale, design system
   maison, zéro composant natif**. Repartir d'un template figé limite la cohérence et l'évolutivité visuelle.
2. **AFG dispose déjà d'un actif** : la plateforme **DORIS** (pilotage des indicateurs DO) est bâtie
   sur **FastAPI + PostgreSQL + React/TypeScript + design system maison**, avec sécurité, RBAC,
   audit append-only, cloisonnement, et un design system éprouvé. Construire DSI 360 sur la **même
   famille technologique** permettrait une **mutualisation** forte (composants, design system,
   conventions, compétences, sécurité) et une **cohérence Groupe**.

## Options

### Option A — Cahier à la lettre : Laravel 12 + Blade + AdminLTE
- ➕ Strictement conforme ; rapide à démarrer ; AdminLTE fournit des écrans tout faits.
- ➖ Rendu **standard** (loin du « premium maison ») ; design peu différenciant ; **aucune
  mutualisation** avec DORIS ; deux écosystèmes distincts à maintenir au sein d'AFG.

### Option B — Compromis : Laravel 12 + Inertia + UI maison (Tailwind), sans AdminLTE
- ➕ Conserve le **backend imposé** (rassure si l'équipe DSI est PHP) ; permet une **UI maison
  premium** (on abandonne AdminLTE).
- ➖ Mutualisation **partielle** seulement avec DORIS (front réutilisable, back non) ; deux langages
  back dans le Groupe (PHP ici, Python pour DORIS).

### Option C — **Recommandée** : API REST + SPA + design system maison (famille DORIS)
- **Backend** : FastAPI (Python 3.12) + Pydantic v2, SQLAlchemy async.
- **Base de données** : PostgreSQL 16 (JSONB pour les attributs d'activité variables, robustesse,
  audit) — *MySQL 8 reste acceptable si la DSI l'impose pour des raisons d'exploitation*.
- **Frontend** : React 18 + TypeScript strict + Vite + **design system maison** (tokens, composants),
  graphiques maîtrisés (ex. Recharts).
- **Files / tâches** : Celery + Redis — indispensable pour les **alertes d'échéance et dépassements
  SLA**, notifications et **synthèses programmées**.
- **Auth** : AD / LDAP / Microsoft 365 via **OIDC (Entra ID)** + JWT court + RBAC (7 profils).
- **Exports** : Excel (openpyxl), PDF (WeasyPrint/ReportLab), CSV.
- **Infra** : Docker Compose + Nginx + TLS (haute disponibilité par réplication applicative).
- ➕ **Mutualisation maximale avec DORIS** (design system, sécurité, conventions, compétences) ;
  qualité **premium maison** ; typage strict de bout en bout ; cohérence Groupe.
- ➖ S'écarte du cahier (langage back **Python** au lieu de PHP) → **nécessite l'accord de la DSI**,
  surtout si l'équipe d'exploitation est PHP/MySQL.

## Décision

**Option C retenue** (meilleure stack moderne, bonnes pratiques, mutualisation avec DORIS). La stack
imposée par le cahier **n'est pas suivie** : on privilégie la modernité, la maîtrise et la cohérence
Groupe. L'**option B** (Laravel + UI maison) reste un **repli** documenté si — et seulement si — une
contrainte d'exploitation PHP/MySQL s'avère bloquante côté DSI. Dans tous les cas : **pas d'AdminLTE**,
**design system maison** (exigence non négociable de qualité).

**Stack figée (option C)** : FastAPI (Python 3.12) + Pydantic v2 · PostgreSQL 16 · React 18 + TS strict
+ Vite + design system maison · Celery + Redis · auth AD/LDAP/M365 (OIDC Entra ID) + JWT + RBAC ·
exports Excel/PDF/CSV · Docker + Nginx + TLS.

Les exigences **fonctionnelles et non fonctionnelles du cahier restent intégralement honorées**
quelle que soit l'option retenue (modules, SLA, notifications, audit, reporting, AD/LDAP/M365,
haute dispo, exports).

## Conséquences

- Tant que la DSI n'a pas tranché, **aucun code applicatif** n'est écrit (on évite le jetable).
- Une fois la stack validée, cet ADR passe en *Accepté* et la section §5 de `CLAUDE.md` est **figée**.
- Si la DSI maintient l'option A (AdminLTE), on le tracera ici et on adaptera les principes de design
  en conséquence (avec la perte de différenciation assumée et documentée).

## Points à confirmer avec la DSI
1. Compétences et préférences de l'équipe d'exploitation (PHP/MySQL vs Python/PostgreSQL).
2. Contraintes d'hébergement / haute disponibilité (serveur interne, sauvegarde, supervision).
3. Modalités d'intégration **AD / Microsoft 365** (Entra ID, SAML/OIDC, comptes de service).
4. Politique de sécurité (RSSI) et exigences de journalisation/rétention.
