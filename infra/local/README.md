# Exécution native (sans Docker) — DSI 360

Le projet tourne directement sur la machine : **PostgreSQL** natif, **Python** (venv) + uvicorn
pour l'API, **Vite** pour le frontend en dev. Aucune dépendance Docker/Redis.
Décision tracée : [ADR-0002](../../docs/adr/0002-execution-native-sans-docker.md).

## Prérequis (déjà présents sur le poste de dev)

- **PostgreSQL 16+** (service Windows), client `psql` dans le PATH ou sous
  `C:\Program Files\PostgreSQL\<version>\bin`.
- **Python 3.12+**.
- **Node 20+** (npm).

## Installation (une seule fois)

1. **Provisionner la base** (en superuser postgres) :
   ```powershell
   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -f infra\local\provisionner-db.sql
   ```
   Crée le rôle applicatif `dsi360` (privilèges limités) et la base `dsi360`.

2. **Configurer** : copier le modèle puis renseigner les secrets.
   ```powershell
   Copy-Item infra\local\.env.example infra\local\.env
   # puis éditer infra\local\.env (mot de passe DB, secret JWT, SMTP…)
   ```

3. **Créer le venv backend + dépendances** :
   ```powershell
   python -m venv backend\.venv
   backend\.venv\Scripts\python.exe -m pip install -U pip
   backend\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
   ```

4. **Migrer + seed** :
   ```powershell
   infra\local\migrer.ps1
   ```

## Lancer en développement

**Une seule commande** (démarre l'API + le frontend dans le même terminal, Ctrl+C arrête les deux) :

```powershell
cd frontend
npm run dev
```

Ouvrir **http://localhost:5290** (le front proxifie `/api` vers l'API sur 8011).

> `npm run dev` exécute `frontend/dev.mjs`, qui lance uvicorn (avec `infra/local/.env`) et Vite.
> Besoin de ne lancer qu'une brique ? `npm run web` (front seul) ou `infra\local\api.ps1` (API seule).

## Production (poste/serveur)

Un seul processus sert tout : l'API FastAPI publie aussi le build du frontend.

```powershell
infra\local\front-build.ps1                     # génère frontend/dist
# dans infra\local\.env : DSI360_SERVIR_FRONTEND=true
infra\local\api.ps1                             # sert l'API + la SPA sur le même port
```

Derrière un reverse-proxy (IIS/Nginx) pour le TLS. Aucune image ni conteneur requis.

## Vérifications qualité

```powershell
. infra\local\env.ps1
& $DSI360_PY -m ruff check backend\src
& $DSI360_PY -m mypy backend\src\dsi360
& $DSI360_PY -m pytest backend\tests -q
```
