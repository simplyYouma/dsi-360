# Serveur de développement du frontend SEUL (Vite, HMR) sur http://localhost:5290.
# Proxifie /api vers l'API uvicorn (127.0.0.1:8011), qu'il faut donc démarrer à côté (api.ps1).
#
# `npm run web` = Vite seul. Surtout pas `npm run dev`, qui démarre aussi une API et ferait
# doublon avec celle du terminal voisin (course sur le port 8011).
# Pour tout lancer d'un coup : infra\local\demarrer-dev.ps1
$ErrorActionPreference = 'Stop'
$racine = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location (Join-Path $racine 'frontend')
if (-not (Test-Path 'node_modules')) { npm install }
npm run web
