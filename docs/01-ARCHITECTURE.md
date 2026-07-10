# 01 — Architecture

> Stack figée en [ADR-0001](adr/0001-choix-de-la-stack.md). Architecture en couches (DDD léger),
> mutualisée avec **DORIS** (mêmes conventions, design system et briques de sécurité réutilisés).

## 1. Vue d'ensemble

```
Navigateur (SPA React + design system maison)
        │  HTTPS
   Reverse proxy IIS/Nginx (TLS) — en production
        │
   API REST FastAPI (uvicorn)  ──►  PostgreSQL 17 (données + audit)
        │  ordonnanceur in-process (asyncio, cf. ADR-0002)
        └──►  SLA (échéances, dépassements), notifications
        │
   Serveur SMTP (liens d'activation et de réinitialisation de mot de passe)
```

## 2. Couches (backend)

- **domain/** — règles métier pures, **zéro dépendance infra** : entité `Activité` et
  spécialisations, machines à états (transitions ITIL), calcul **priorité (impact × urgence)** et
  **statut SLA** (à l'heure / en approche / dépassé), criticité des risques.
- **application/** — cas d'usage : créer/affecter/valider/clôturer une activité, **autorisations**
  (rôles sur une activité), **ingestion** du rapport quotidien, workflows CAB/ECAB, calcul des
  indicateurs, génération des exports.
- **infrastructure/** — PostgreSQL (repositories), audit chaîné, envoi e-mail,
  fabrication PDF/Excel/CSV.
- **interface/** — API REST v1, schémas d'entrée/sortie (Pydantic), middlewares (auth, RBAC, audit,
  corrélation d'erreurs).

## 3. Flux d'une activité (exemple incident)

1. Création (UI ou e-mail/Service Desk) → `Activité` en `Nouveau`, **référence** générée.
2. Qualification : catégorie, impact, urgence → **priorité P1…P5** → **échéances SLA** calculées.
3. Affectation d'un responsable. Le **niveau de support** (N1, N2, ou N3 = DBS) se **déduit** du
   gestionnaire ; pour les incidents et demandes, celui-ci vient du rapport quotidien (ADR-0005).
4. L'**ordonnanceur** surveille les échéances → **notifications** (approche, dépassement).
5. Résolution → validation → **clôture** ; chaque étape **journalisée** (audit append-only).
6. Les indicateurs du **tableau de bord** se recalculent ; exports disponibles.

## 4. Sécurité (cf. `docs/04-SECURITY.md` à venir)

Auth **locale** (mot de passe défini par l'agent, cf. ADR-0004) → JWT court + refresh ; **RBAC par profil métier et par action** + cloisonnement par
périmètre, vérifié **côté serveur** ; audit append-only (ancienne/nouvelle valeur, IP) ; secrets
hors du code ; TLS partout.

## 5. Déploiement

**Exécution native, sans Docker** ([ADR-0002](adr/0002-execution-native-sans-docker.md)) :
PostgreSQL natif · venv + uvicorn · Vite (dev) ou FastAPI-StaticFiles (prod). TLS au
reverse proxy (IIS/Nginx). Haute disponibilité (> 99 %) par réplication applicative + sauvegardes (à cadrer avec
la DSI). Migrations SQL versionnées `YYYYMMDDHHmmss_description.sql`.

## 6. Structure du dépôt (cible, monorepo)

```
DSI_360/
├── CLAUDE.md                  ← SSOT
├── docs/                      ← architecture, ADR, domaine, sécurité, design system
│   └── _sources-conception/   ← cahier, procédures ITIL, images d'inspi
├── backend/
│   └── src/dsi360/
│       ├── domain/            ← Activité, états, SLA, priorité (pur)
│       ├── application/       ← cas d'usage / workflows
│       ├── infrastructure/    ← postgres, audit, email, exports
│       └── interface/         ← API REST v1, schémas, middlewares
│   └── tests/                 ← unit / integration / security / e2e
├── frontend/
│   └── src/
│       ├── design-system/     ← tokens, ThemeProvider, primitives (zéro natif)
│       ├── features/          ← dashboard, incidents, demandes, projets, changements, audit, risques, admin
│       ├── lib/               ← client API, auth, i18n
│       └── common/            ← composants/logique partagés
├── db/migrations/
└── infra/local/               ← scripts de lancement natifs (PowerShell 7), env.ps1
```

## 7. Conventions

Backend : fonctions atomiques, typage explicite, guard clauses, erreurs centralisées avec
`correlation_id`, logs JSON. Frontend : TypeScript strict, `any` interdit, **zéro composant natif**,
design system en tokens. Migrations jamais modifiées rétroactivement. Qualité (lint/types/tests/e2e)
au vert à chaque livraison.
