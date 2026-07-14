# Installe (ou réinstalle) la tâche planifiée qui démarre DSI 360 AVEC WINDOWS.
#
# La tâche lance `start-prod.sh` (via Git Bash) : un seul uvicorn, TLS terminé par l'app, bannière
# masquée, ni --reload ni --workers (cf. docs/06-DEPLOIEMENT §1 et §3.7). Elle tourne sous le compte
# SYSTEM, au démarrage de la machine, sans session ouverte.
#
# Idempotent : réexécutable, remplace la tâche existante. À lancer EN ADMINISTRATEUR
# (double-clic sur installer-tache.bat, qui élève tout seul).
#
#   infra\local\installer-tache.ps1 [-Tache DSI360] [-Port 8453] [-SansPareFeu] [-SansDemarrer]
#
# ATTENTION, encodage : UTF-8 **avec BOM** (cf. infra/local/README.md).
param(
    [string]$Tache = 'DSI360',
    [int]$Port = 8453,
    [switch]$SansPareFeu,     # ne pas créer la règle de pare-feu entrante
    [switch]$SansDemarrer     # installer la tâche sans la démarrer tout de suite
)
$ErrorActionPreference = 'Stop'

function Etape($texte) { Write-Host "==> $texte" -ForegroundColor Cyan }

# 1. Droits : Register-ScheduledTask sous SYSTEM exige une élévation. Sans elle, on échouerait
#    plus loin avec un « Accès refusé » obscur — on le dit tout de suite.
$estAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $estAdmin) {
    throw "Ce script doit tourner en administrateur. Double-cliquez plutot infra\local\installer-tache.bat."
}

$racine  = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$script  = Join-Path $PSScriptRoot 'start-prod.sh'
$cert    = Join-Path $racine 'cert\cert.pem'
$cle     = Join-Path $racine 'cert\key.pem'

# Le lanceur de production est un script shell : il lui faut Git Bash. Git est un prérequis serveur
# (docs/06-DEPLOIEMENT §2), mais on le vérifie — sans lui, la tâche échouerait à chaque démarrage.
$bash = 'C:\Program Files\Git\bin\bash.exe'
if (-not (Test-Path $bash)) {
    $bash = (Get-Command bash.exe -ErrorAction SilentlyContinue).Source
    if (-not $bash) { throw "Git Bash introuvable (bash.exe). Installez Git pour Windows : winget install Git.Git" }
}

# 2. Une tâche qui démarre au boot sur un déploiement incomplet échouerait en silence à chaque
#    redémarrage. On vérifie ce dont start-prod.sh a besoin AVANT de l'installer.
Etape 'Controle des prerequis du deploiement'
$manquants = @()
foreach ($p in @(
    @{ Chemin = $script;                                              Quoi = 'lanceur de production start-prod.sh' },
    @{ Chemin = Join-Path $racine 'backend\.venv\Scripts\python.exe'; Quoi = 'venv backend (cf. README infra/local)' },
    @{ Chemin = Join-Path $PSScriptRoot '.env';                       Quoi = 'configuration infra\local\.env' },
    @{ Chemin = Join-Path $racine 'frontend\dist\index.html';         Quoi = 'build du frontend (front-build.ps1)' },
    @{ Chemin = $cert;                                                Quoi = 'certificat TLS (docs/06-DEPLOIEMENT §3.5)' },
    @{ Chemin = $cle;                                                 Quoi = 'cle du certificat TLS' }
)) {
    if (-not (Test-Path $p.Chemin)) { $manquants += "  - $($p.Quoi) : $($p.Chemin)" }
}
if ($manquants.Count -gt 0) {
    throw ("Deploiement incomplet — la tache echouerait a chaque demarrage :`n" + ($manquants -join "`n"))
}

# 3. La tâche : au démarrage de Windows, sous SYSTEM, sans session ouverte.
Etape "Installation de la tache planifiee '$Tache'"
# Git Bash lance le script shell, qui `exec` uvicorn : python REMPLACE le bash, si bien que la tache
# surveille bien l'API elle-meme et non un shell intermediaire.
$argument = "`"$script`" --port $Port --cert `"$cert`" --key `"$cle`""
$action = New-ScheduledTaskAction -Execute $bash -Argument $argument

# Délai d'1 minute : au boot, PostgreSQL (service) n'écoute pas forcément encore. L'API applique
# ses migrations au démarrage et s'arrêterait si la base était injoignable. Le délai — et les
# relances ci-dessous — évitent cette course.
$declencheur = New-ScheduledTaskTrigger -AtStartup
$declencheur.Delay = 'PT1M'

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

# ExecutionTimeLimit = 0 : SANS CELA, le planificateur TUE la tache au bout de 3 jours (valeur par
# defaut) — l'application s'arreterait toute seule au bout de 72 h. C'est un service : pas de limite.
$reglages = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $Tache -Action $action -Trigger $declencheur `
    -Principal $principal -Settings $reglages -Force | Out-Null

# 4. Pare-feu : sans règle entrante, l'app ne répond qu'en local et personne ne s'en aperçoit
#    avant les tests depuis un poste utilisateur.
if (-not $SansPareFeu) {
    $regle = "DSI360 - HTTPS $Port"
    if (Get-NetFirewallRule -DisplayName $regle -ErrorAction SilentlyContinue) {
        Write-Host "Regle de pare-feu deja presente : $regle" -ForegroundColor DarkGray
    } else {
        Etape "Ouverture du port $Port (pare-feu, entrant)"
        New-NetFirewallRule -DisplayName $regle -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort $Port -Profile Any | Out-Null
    }
}

# 5. Démarrer tout de suite : une tâche « installée mais jamais testée » est une panne différée.
if ($SansDemarrer) {
    Write-Host "Tache '$Tache' installee (non demarree)." -ForegroundColor Yellow
    return
}
Etape "Demarrage de la tache '$Tache'"
Start-ScheduledTask -TaskName $Tache

# Deux controles distincts, volontairement : /healthz dit que le PROCESSUS repond (donc que la tache,
# Git Bash, uvicorn et le TLS sont bons) ; /readyz dit que la BASE repond. Confondre les deux ferait
# passer pour un echec d'installation ce qui n'est qu'une base non provisionnee.
$vivant = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $code = & curl.exe -s -k --max-time 5 -o NUL -w '%{http_code}' "https://127.0.0.1:$Port/healthz" 2>$null
    if ($code -eq '200') { $vivant = $true; break }
}
if (-not $vivant) {
    Write-Warning ("La tache est installee mais l'API ne repond pas sur https://127.0.0.1:$Port/healthz.`n" +
        "Diagnostic :  Get-ScheduledTaskInfo -TaskName $Tache   |   journal : Observateur d'evenements > Planificateur de taches")
    return
}
Write-Host "OK — DSI 360 ecoute en HTTPS sur le port $Port, et repondra a chaque demarrage de Windows." -ForegroundColor Green

$pret = & curl.exe -s -k --max-time 5 "https://127.0.0.1:$Port/readyz" 2>$null
if ($pret -match '"db"\s*:\s*"ok"') {
    Write-Host "OK — base joignable : $pret" -ForegroundColor Green
} else {
    Write-Warning ("L'application tourne mais la BASE ne repond pas : $pret`n" +
        "Provisionnez-la puis relancez la tache :`n" +
        "  psql -U postgres -f infra\local\provisionner-db.sql   puis   infra\local\migrer.ps1`n" +
        "  Stop-ScheduledTask -TaskName $Tache ; Start-ScheduledTask -TaskName $Tache")
}
