# Applique les migrations SQL puis (ré)initialise les référentiels + le compte admin.
# Idempotent : réexécutable sans risque.
. "$PSScriptRoot\env.ps1"
Write-Host "==> Migrations…" -ForegroundColor Cyan
& $DSI360_PY -m dsi360.infrastructure.db.migrate
Write-Host "==> Seed (référentiels + admin)…" -ForegroundColor Cyan
& $DSI360_PY -m dsi360.infrastructure.db.seed
Write-Host "OK — base à jour." -ForegroundColor Green
