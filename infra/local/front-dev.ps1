# Serveur de développement du frontend (Vite, HMR) sur http://localhost:5290.
# Proxifie /api vers l'API uvicorn (127.0.0.1:8011).
$ErrorActionPreference = 'Stop'
$racine = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location (Join-Path $racine 'frontend')
if (-not (Test-Path 'node_modules')) { npm install }
npm run dev
