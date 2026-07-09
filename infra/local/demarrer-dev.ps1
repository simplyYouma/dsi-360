# Démarre l'environnement de dev complet (API + frontend) dans UNE fenêtre.
#
# Ce script n'est qu'un lanceur : tout le travail est fait par `npm run dev` (frontend/dev.mjs),
# seul point d'entrée qui démarre l'API et Vite. Il les supervise (relance celui qui tombe) et
# Ctrl+C les arrête proprement tous les deux.
#
# Ne jamais lancer d'uvicorn en plus d'ici : deux serveurs se disputeraient le port 8011 et
# c'est le survivant — pas forcément le bon — qui répondrait.
$ErrorActionPreference = 'Stop'

$racine   = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$frontend = Join-Path $racine 'frontend'

Set-Location $frontend
if (-not (Test-Path 'node_modules')) { npm install }

Write-Host "API (8011) + frontend (5290). Ouvrez http://localhost:5290 — Ctrl+C arrete les deux." -ForegroundColor Green
npm run dev
