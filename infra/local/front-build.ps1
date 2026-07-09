# Build de production du frontend → frontend/dist.
# En prod, l'API FastAPI sert ce dossier (DSI360_SERVIR_FRONTEND=true).
$ErrorActionPreference = 'Stop'
$racine = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location (Join-Path $racine 'frontend')
if (-not (Test-Path 'node_modules')) { npm install }
npm run build
Write-Host "Build prêt : frontend/dist" -ForegroundColor Green
