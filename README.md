# DSI 360

Plateforme de gouvernance, pilotage et gestion des activités de la **Direction des Systèmes
d'Information** — AFG Bank Mali. Source de vérité : [`CLAUDE.md`](CLAUDE.md). Docs : [`docs/`](docs/).

> **État** : squelette de fondations posé (structure, design system, API d'amorçage, infra, 1re
> migration). **Pas encore exécuté de bout en bout** : la mise en route ci-dessous reste à lancer
> (installation des dépendances, build des images). Aucun module métier n'est encore implémenté.

## Stack

FastAPI (Python 3.12) · PostgreSQL 16 · React 18 + TS strict + Vite + **design system maison** ·
Celery + Redis · auth AD/LDAP/Microsoft 365 (OIDC) · Docker + Nginx + TLS. Cf.
[ADR-0001](docs/adr/0001-choix-de-la-stack.md).

## Mise en route (dev)

```bash
cp infra/env/.env.example infra/env/.env   # puis renseigner les secrets
make certs                                   # certificat TLS auto-signé de dev
make up                                       # démarre la stack (build)
```

- Application : https://localhost:8453 (certificat auto-signé : avertissement navigateur normal)
- API : https://localhost:8453/api/v1 — santé : `/healthz`, `/readyz`
- Front en dev rapide (hors Docker) : `make front-dev` → http://localhost:5290

## Structure

`backend/` (FastAPI, couches DDD) · `frontend/` (React + design system) · `db/migrations/` ·
`infra/` (compose, nginx, env) · `docs/` (architecture, domaine, sécurité, design system, ADR).

> Les documents internes de la banque (cahier des charges, procédures ITIL, rapport d'incident) ne
> sont **pas** versionnés (confidentialité) ; ils restent en local sous `docs/_sources-conception/`.
