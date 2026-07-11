# Démarre l'API DSI 360 en PRODUCTION : un seul processus sert l'API + la SPA compilée.
#
# Conforme au standard serveur AFG :
#   - TLS terminé par l'app (uvicorn --ssl-*), accès par IP:port, sans reverse-proxy obligatoire ;
#   - bannière serveur masquée (--no-server-header) : pas de « server: uvicorn » ;
#   - PAS de --reload, PAS de --workers : l'ordonnanceur SLA/notifications tourne EN PROCESSUS ;
#     plusieurs workers = plusieurs ordonnanceurs = notifications en double. Un seul process.
#
# Prérequis : build du frontend fait (infra\local\front-build.ps1) et infra\local\.env renseigné
# avec DSI360_ENVIRONNEMENT=recette|prod (active HSTS) et un DSI360_JWT_SECRET_KEY fort.
#
#   infra\local\start-prod.ps1 -Port 8453 -Certificat C:\MY_APPS\DSI360\cert\cert.pem -CleCertificat C:\MY_APPS\DSI360\cert\key.pem
#
# Sans -Certificat : démarre en HTTP (à réserver au cas « derrière un reverse-proxy qui fait le TLS »).
param(
    [int]$Port = 8453,
    [string]$Ecouter = '0.0.0.0',
    [string]$Certificat = '',
    [string]$CleCertificat = ''
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"

# L'API doit publier la SPA en prod (le front n'a pas de serveur Vite ici).
$env:DSI360_SERVIR_FRONTEND = 'true'

$dist = Join-Path $DSI360_RACINE 'frontend\dist'
if (-not (Test-Path (Join-Path $dist 'index.html'))) {
    throw "Build du frontend absent ($dist). Lancez d'abord : infra\local\front-build.ps1"
}

if ($env:DSI360_ENVIRONNEMENT -eq 'dev' -or [string]::IsNullOrWhiteSpace($env:DSI360_ENVIRONNEMENT)) {
    Write-Warning ("DSI360_ENVIRONNEMENT=$($env:DSI360_ENVIRONNEMENT) : HSTS restera desactive. " +
        "Mettez 'recette' ou 'prod' dans infra\local\.env pour une vraie mise en ligne.")
}

# Un second uvicorn sur le meme port perd la course silencieusement : on refuse plutot.
$occupe = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($occupe) {
    $pids = ($occupe.OwningProcess | Sort-Object -Unique) -join ', '
    throw "Le port $Port est deja en ecoute (PID $pids). Arretez l'instance en cours avant de relancer."
}

$args = @(
    '-m', 'uvicorn', 'dsi360.interface.app:app',
    '--host', $Ecouter, '--port', $Port,
    '--no-server-header'
)
if (-not [string]::IsNullOrWhiteSpace($Certificat)) {
    if (-not (Test-Path $Certificat))    { throw "Certificat introuvable : $Certificat" }
    if (-not (Test-Path $CleCertificat)) { throw "Cle du certificat introuvable : $CleCertificat" }
    $args += @('--ssl-certfile', $Certificat, '--ssl-keyfile', $CleCertificat)
    Write-Host "TLS direct : https://$($Ecouter):$Port" -ForegroundColor Green
} else {
    Write-Warning "Aucun certificat : demarrage en HTTP. A reserver a un deploiement derriere un reverse-proxy TLS."
}

Write-Host "Demarrage DSI 360 (prod) sur le port $Port…" -ForegroundColor Cyan
& $DSI360_PY @args
