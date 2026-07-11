# Démarre l'environnement de dev complet (API + frontend) dans UNE fenêtre.
#
# Ce script n'est qu'un lanceur : tout le travail est fait par `npm run dev` (frontend/dev.mjs),
# seul point d'entrée qui démarre l'API et Vite. Il les supervise (relance celui qui tombe) et
# Ctrl+C les arrête proprement tous les deux.
#
# Ne jamais lancer d'uvicorn en plus d'ici : deux serveurs se disputeraient le port 8011 et
# c'est le survivant — pas forcément le bon — qui répondrait.
#
# ATTENTION, encodage : ce fichier doit rester en UTF-8 **avec BOM**. Un double-clic ouvre Windows
# PowerShell 5.1, qui lit un .ps1 sans BOM comme du Windows-1252 : les accents deviennent du
# charabia et le script ne compile plus.
$ErrorActionPreference = 'Stop'

# Les scripts du projet visent PowerShell 7 (pwsh). Le double-clic lance 5.1 : on se relance nous-
# mêmes sous pwsh plutôt que d'imposer à chacun d'ouvrir le bon terminal.
if ($PSVersionTable.PSVersion.Major -lt 6) {
    $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) {
        Write-Host "PowerShell 7 (pwsh) est requis et introuvable." -ForegroundColor Red
        Write-Host "Installez-le :  winget install Microsoft.PowerShell" -ForegroundColor Yellow
        try { Read-Host "`nEntree pour fermer" | Out-Null } catch { }
        exit 1
    }
    & $pwsh -NoProfile -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$racine   = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$frontend = Join-Path $racine 'frontend'

# Retient la fenêtre pour qu'on puisse lire l'erreur avant qu'elle ne se referme (double-clic).
# Sans effet quand l'entrée est redirigée ou la console non interactive (CI, tâche planifiée).
function Wait-Fermeture {
    try { Read-Host "`nEntree pour fermer" | Out-Null } catch { }
}

# Un port déjà pris fait mourir l'enfant correspondant en boucle : le superviseur abandonne, la
# fenêtre se referme, et l'on n'a rien pu lire. On vérifie donc avant de lancer.
$occupes = @()
foreach ($port in 8011, 5290) {
    $ecoute = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($ecoute) {
        $pids = ($ecoute.OwningProcess | Sort-Object -Unique) -join ', '
        $occupes += "  port $port occupe (PID $pids)"
    }
}
if ($occupes.Count -gt 0) {
    Write-Host "Impossible de demarrer : un environnement tourne deja." -ForegroundColor Red
    $occupes | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    Write-Host ""
    Write-Host "Fermez-le (Ctrl+C dans sa fenetre), ou liberez les ports :" -ForegroundColor Yellow
    Write-Host '  Get-NetTCPConnection -LocalPort 8011,5290 -State Listen |' -ForegroundColor Yellow
    Write-Host '    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }' -ForegroundColor Yellow
    Wait-Fermeture
    exit 1
}

Set-Location $frontend
if (-not (Test-Path 'node_modules')) { npm install }

Write-Host "API (8011) + frontend (5290). Ouvrez http://localhost:5290 - Ctrl+C arrete les deux." -ForegroundColor Green
npm run dev

# `npm run dev` ne rend la main que si les deux services se sont arretes. En double-clic, la fenetre
# se refermerait aussitot sur le message d'erreur : on la retient.
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nL'environnement s'est arrete (code $LASTEXITCODE)." -ForegroundColor Red
    Wait-Fermeture
}
