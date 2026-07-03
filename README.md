# DSI 360

Plateforme de gouvernance, pilotage et gestion des activités de la **Direction des Systèmes
d'Information** — AFG Bank Mali. Source de vérité : [`CLAUDE.md`](CLAUDE.md). Docs : [`docs/`](docs/).

## Stack

FastAPI (Python 3.12) · PostgreSQL 16+ · React 18 + TS strict + Vite + **design system maison** ·
auth AD/LDAP/Microsoft 365 (OIDC). **Exécution native, sans Docker** (cf.
[ADR-0002](docs/adr/0002-execution-native-sans-docker.md)) — Celery/Redis différés.
Choix de stack : [ADR-0001](docs/adr/0001-choix-de-la-stack.md).

## Mise en route (dev, natif)

Prérequis : **PostgreSQL 16+**, **Python 3.12+**, **Node 20+**. Détails et scripts :
[`infra/local/README.md`](infra/local/README.md).

```powershell
# 1) base : rôle + base applicative (en superuser postgres)
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -f infra\local\provisionner-db.sql
# 2) config : copier le modèle puis renseigner les secrets
Copy-Item infra\local\.env.example infra\local\.env
# 3) venv backend + dépendances
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
# 4) migrations + seed
infra\local\migrer.ps1
# 5) démarrer API + frontend
infra\local\demarrer-dev.ps1
```

- Application (dev) : http://localhost:5290 (Vite, HMR) — proxifie `/api` vers l'API
- API : http://127.0.0.1:8011/api/v1 — santé : `/healthz`, `/readyz`
- Prod native : `infra\local\front-build.ps1` puis `DSI360_SERVIR_FRONTEND=true` → l'API sert la SPA

## Structure

`backend/` (FastAPI, couches DDD) · `frontend/` (React + design system) · `db/migrations/` ·
`infra/local/` (scripts natifs + config) · `docs/` (architecture, domaine, sécurité, design system, ADR).

> Les documents internes de la banque (cahier des charges, procédures ITIL, rapport d'incident) ne
> sont **pas** versionnés (confidentialité) ; ils restent en local sous `docs/_sources-conception/`.
