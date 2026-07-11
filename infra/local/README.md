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

5. *(optionnel, dev)* **Données de démonstration** — jeu réaliste pour tester tous les écrans
   (remet à zéro les données puis régénère ; refuse de tourner hors `dev`) :
   ```powershell
   infra\local\donnees-demo.ps1
   ```

## Encodage des scripts (à ne pas casser)

Les `.ps1` de ce dossier sont en **UTF-8 avec BOM**, et doivent le rester. Un double-clic ouvre
**Windows PowerShell 5.1**, qui lit un `.ps1` sans BOM comme du Windows-1252 : les accents
deviennent du charabia et le script ne compile plus. `demarrer-dev.ps1` se relance de lui-même
sous **pwsh 7** ; il doit d'abord pouvoir être lu par 5.1 pour y parvenir.

Corollaire : **jamais d'accent dans un nom de variable** PowerShell.

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

Les commandes se lancent **depuis `backend\`** : c'est là que vit `pyproject.toml`, donc la
configuration de ruff, mypy (mode strict) et pytest. Lancées depuis la racine, mypy et pytest ne
trouvent aucune configuration et vérifient bien moins qu'il n'y paraît.

```powershell
. infra\local\env.ps1
Set-Location backend
& $DSI360_PY -m ruff check src tests
& $DSI360_PY -m mypy src\dsi360 tests
& $DSI360_PY -m pytest tests -q
```

### Base de test (une seule fois)

Les tests d'intégration tournent sur une base dédiée `dsi360_test`, jamais sur celle de
développement. La créer une fois, en superuser :

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -f infra\local\provisionner-db-test.sql
```

Ensuite `pytest tests` s'en occupe seul : migrations, seed, puis chaque test dans une transaction
annulée à la fin. Les tests unitaires (`pytest tests\unit`) ne demandent aucune base.

### Test d'intrusion (avant chaque mise en production)

L'API doit tourner (via `api.ps1` ou `demarrer-dev.ps1`). Le script se connecte avec un compte à
faible privilège et tente de forcer 21 gardes ; chacune doit refuser. À lancer contre une instance
de recette, jamais en production.

```powershell
infra\local\pentest.ps1
```

Sortie attendue : `21 contrôles franchis, 0 faille(s)`. Toute faille fait sortir le script en
erreur. Détail des contrôles : `docs/04-SECURITY.md` §6.
