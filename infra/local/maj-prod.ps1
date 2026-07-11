# Met à jour DSI 360 sur le serveur, d'un seul geste, de façon sûre et rejouable :
#   contrôle du dépôt -> git pull (fast-forward) -> dépendances -> migrations -> build front
#   -> redémarrage de la tâche -> contrôle de santé.
# Pensé pour être lancé par maj-prod.bat (double-clic + élévation admin). Idempotent.
#
#   infra\local\maj-prod.ps1 [-Tache DSI360] [-UrlSante https://127.0.0.1:8453/healthz]
#                            [-SansRedemarrage]
param(
    [string]$Tache = 'DSI360',
    [string]$UrlSante = 'https://127.0.0.1:8453/healthz',
    [switch]$SansRedemarrage
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"

function Etape($texte) { Write-Host "==> $texte" -ForegroundColor Cyan }

Set-Location $DSI360_RACINE

# 1. Refuser si le dépôt porte des modifications locales : un pull les écraserait ou échouerait.
#    La règle du serveur : le code ne se modifie que par git, jamais à la main sur place.
Etape 'Contrôle du dépôt (aucune modification locale)'
$modifs = git status --porcelain
if ($modifs) {
    throw "Modifications locales détectées : committez ou annulez avant la mise à jour.`n$modifs"
}

# 2. Récupérer le code — fast-forward seulement : jamais de fusion surprise sur le serveur.
Etape 'git pull (fast-forward seulement)'
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "git pull a échoué (branche divergente ?)." }

# 3. Dépendances backend (idempotent : ne réinstalle que ce qui a changé).
Etape 'Dépendances backend'
& $DSI360_PY -m pip install -e ".\backend" --quiet

# 4. Migrations (idempotentes, verrouillées). On les applique ici pour échouer tôt si besoin.
Etape 'Migrations base de données'
& $DSI360_PY -m dsi360.infrastructure.db.migrate

# 5. Build du frontend (reproductible via package-lock).
Etape 'Build du frontend'
Set-Location (Join-Path $DSI360_RACINE 'frontend')
npm ci
npm run build
Set-Location $DSI360_RACINE

# 6. Redémarrer la tâche : sinon l'ancien code — et l'ancien certificat — reste en mémoire.
if ($SansRedemarrage) {
    Write-Host 'Mise à jour appliquée. Tâche NON redémarrée (-SansRedemarrage).' -ForegroundColor Yellow
    return
}
Etape "Redémarrage de la tâche $Tache"
if (-not (Get-ScheduledTask -TaskName $Tache -ErrorAction SilentlyContinue)) {
    throw "Tâche planifiée '$Tache' introuvable. Créez-la d'abord (cf. docs/06-DEPLOIEMENT §3.7)."
}
Stop-ScheduledTask -TaskName $Tache
Start-ScheduledTask -TaskName $Tache

# 7. Contrôle de santé : l'API répond-elle après redémarrage ? (curl -k : accepte l'auto-signé.)
Etape 'Contrôle de santé'
$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    $code = & curl.exe -s -k --max-time 5 -o NUL -w '%{http_code}' $UrlSante 2>$null
    if ($code -eq '200') { $ok = $true; break }
}
if ($ok) {
    Write-Host "OK - DSI 360 est a jour et repond ($UrlSante)." -ForegroundColor Green
} else {
    Write-Warning "L'API ne repond pas encore sur $UrlSante. Consultez les journaux de la tache $Tache."
}
