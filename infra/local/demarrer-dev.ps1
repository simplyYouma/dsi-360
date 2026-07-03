# Démarre l'environnement de dev complet : API + frontend dans deux fenêtres PowerShell.
# Ouvrez ensuite http://localhost:5290.
$ErrorActionPreference = 'Stop'
Start-Process pwsh -ArgumentList '-NoExit', '-File', (Join-Path $PSScriptRoot 'api.ps1')
Start-Process pwsh -ArgumentList '-NoExit', '-File', (Join-Path $PSScriptRoot 'front-dev.ps1')
Write-Host "API (8011) et frontend (5290) démarrés dans deux fenêtres. Ouvrez http://localhost:5290" -ForegroundColor Green
