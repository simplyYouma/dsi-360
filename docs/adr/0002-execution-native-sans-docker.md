# ADR-0002 — Exécution native, sans Docker

- **Statut** : **Accepté** — décision projet : le projet s'exécute **directement sur la machine
  hôte** (PostgreSQL natif, venv Python + uvicorn, Vite/StaticFiles), **sans Docker ni Redis**.
  Remplace le volet « Infra : Docker Compose + Nginx » de [ADR-0001](0001-choix-de-la-stack.md).
- **Date** : 3 juillet 2026.
- **Décideurs** : équipe projet, à la demande du porteur (retours d'expérience de déploiement).

## Contexte

L'infra initiale ([ADR-0001](0001-choix-de-la-stack.md), §5 de `CLAUDE.md`) reposait sur **Docker
Compose** (postgres, redis, api, worker/scheduler Celery, nginx). À l'usage :

1. **Déploiement douloureux** : sur un autre projet AFG, la mise en production via Docker a posé de
   nombreux problèmes (moteur, réseau, volumes, TLS). Le porteur demande explicitement de **retirer
   la dépendance Docker**.
2. **Instabilité locale** : Docker Desktop tombe régulièrement sur le poste de dev (moteur qui ne
   répond plus), bloquant migrations, tests et API.
3. **Dépendances superflues à ce stade** : **Redis/Celery** ne servent qu'aux tâches planifiées SLA,
   **différées** (profil `full`, non actives). L'API n'en dépend pas au runtime.
4. **Actifs déjà présents** sur le poste/serveur : **PostgreSQL 16+** (service Windows), **Python
   3.12+**, **Node 20+**. Rien de plus n'est requis pour faire tourner l'application.

## Décision

Exécution **native** :

| Couche | Avant (Docker) | Après (natif) |
|---|---|---|
| Base | conteneur `postgres:16` | **PostgreSQL 16+** natif + rôle/base applicatifs dédiés (moindre privilège) |
| API | conteneur uvicorn | **venv** `backend/.venv` + `uvicorn` (127.0.0.1:8011) |
| Migrations / seed | `exec` dans le conteneur | `python -m dsi360.infrastructure.db.{migrate,seed}` |
| Frontend (dev) | build → nginx conteneur | **Vite** (HMR) sur :5290, proxy `/api` → API |
| Frontend (prod) | nginx conteneur | **FastAPI sert `frontend/dist`** (StaticFiles + fallback SPA), même origine |
| Files / tâches SLA | Celery + Redis | **supprimés** ; réintroduits plus tard via APScheduler in-process ou tâche planifiée Windows |
| TLS | nginx conteneur | reverse-proxy natif (IIS/Nginx) **en prod uniquement** |
| Secrets | `infra/env/.env` | `infra/local/.env` (git-ignoré) chargé par `infra/local/env.ps1` |

Scripts natifs et procédure : [`infra/local/README.md`](../../infra/local/README.md).
Provisionnement DB à privilèges limités : `infra/local/provisionner-db.sql` (rôle applicatif
distinct du superuser, propriétaire de sa seule base).

**Fichiers Docker supprimés** : `infra/docker-compose.yml`, `backend/Dockerfile`,
`frontend/Dockerfile`, `infra/nginx/`, `Makefile` (docker), `infra/env/`. L'historique git les
conserve si un retour en arrière s'imposait.

## Conséquences

- ➕ **Zéro dépendance Docker/Redis** ; démarrage plus simple et robuste sur poste et serveur.
- ➕ **Sécurité préservée** : rôle DB dédié à privilèges limités, secrets hors dépôt, TLS assuré par
  un reverse-proxy en prod, même-origine front/API (pas de CORS à ouvrir).
- ➖ **Haute disponibilité** : à assurer autrement qu'avec la réplication de conteneurs (service
  Windows + reverse-proxy, ou hébergement dédié) — à cadrer au moment de la prod.
- ➖ **Tâches planifiées SLA** : à réintroduire sans Celery (APScheduler intégré à l'API, ou tâche
  planifiée Windows appelant une commande de scan). À traiter dans le lot Notifications/SLA.
- La section **§5 de `CLAUDE.md`** est mise à jour en conséquence (infra native).

## À confirmer / suites

1. Cible de **production** (serveur Windows ? Linux ?) et reverse-proxy TLS retenu (IIS, Nginx natif).
2. Stratégie **haute disponibilité** et sauvegarde PostgreSQL (pg_dump planifié, réplication).
3. Réintroduction des **scans SLA** (APScheduler vs tâche planifiée) — décision au lot SLA.
