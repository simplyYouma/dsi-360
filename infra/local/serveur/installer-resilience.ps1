# Installe les trois tâches qui rendent DSI 360 résistant aux pannes du serveur.
#
#   DSI360-Surveillance     toutes les 5 min   relance le service s'il ne répond plus, alerte sinon
#   DSI360-Sauvegarde       chaque jour 02:00  pg_dump + copie hors machine + rétention
#   DSI360-VerifSauvegarde  dimanche 03:00     restaure la dernière sauvegarde pour la prouver
#
# Ces trois-là ne servent à rien séparément. Une sauvegarde sans copie hors machine disparaît avec
# le disque qu'elle protège. Une copie jamais restaurée n'est qu'un fichier dont on espère quelque
# chose. Et un service qui tombe la nuit sans surveillance se découvre au matin, par un utilisateur.
#
#   infra\local\serveur\installer-resilience.ps1
#   infra\local\serveur\installer-resilience.ps1 -Copie \\nas-afg\dsi360 -Alerte dsi@afgbank.ml
#
# À lancer EN ADMINISTRATEUR, une fois. Relançable sans risque : les tâches sont remplacées.
#
# ATTENTION, encodage : UTF-8 **avec BOM** obligatoire (cf. lib/DSI360.Common.ps1).
param(
    [string] $Copie          = '',    # partage réseau où recopier les sauvegardes (fortement conseillé)
    [string] $Destination    = '',    # dossier local des sauvegardes (défaut : <racine>\data\backups)
    [string] $Alerte         = '',    # e-mail prévenu quand le service ne repart pas
    [int]    $RetentionJours = 30,
    [int]    $Port           = 8453,
    [string] $Tache          = 'DSI360',
    [switch] $SansVerif                # ne pas installer la preuve de restauration hebdomadaire
)

$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\..\lib\DSI360.Common.ps1"
. "$PSScriptRoot\..\env.ps1"

Initialize-Dsi360Console -Titre 'DSI 360 - Installation de la resilience'
$null = Initialize-Dsi360Journal -Dossier (Join-Path $PSScriptRoot '..\logs') -Prefixe 'installer-resilience'
Show-Dsi360Banniere -Titre 'Resilience : surveillance, sauvegarde, preuve' `
                    -Sous 'Trois taches planifiees' -Racine $DSI360_RACINE

try {
    Set-Dsi360EtapeTotal 5

    # --- 1. Droits ---------------------------------------------------------------------------
    Write-Dsi360Etape 'Droits administrateur'
    $identite = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $identite.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Dsi360Echec 'Droits administrateur requis.'
        Write-Dsi360Cadre -Titre 'Que faire' -Couleur 'Yellow' -Lignes @(
            'Ouvrez PowerShell en administrateur, puis relancez :',
            '   infra\local\serveur\installer-resilience.ps1'
        )
        throw 'Droits insuffisants.'
    }
    Write-Dsi360Ok 'Session administrateur'

    # --- 2. Ce qui doit exister ----------------------------------------------------------------
    # Installer une tâche qui pointe vers un script absent, c'est programmer une panne pour plus
    # tard : elle échouerait en silence, et la surveillance elle-même serait aveugle.
    Write-Dsi360Etape 'Scripts et prerequis'
    $surveiller = Join-Path $PSScriptRoot 'surveiller.ps1'
    $sauvegarde = Join-Path $PSScriptRoot 'sauvegarde-db.ps1'
    $verifier   = Join-Path $PSScriptRoot 'verifier-restauration.ps1'
    foreach ($p in @($surveiller, $sauvegarde, $verifier)) {
        if (-not (Test-Path $p)) { throw "Script introuvable : $p" }
    }
    $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command powershell -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) { throw 'Ni pwsh ni powershell dans le PATH.' }
    Write-Dsi360Ok "Scripts presents, hote $([IO.Path]::GetFileName($pwsh))"

    if (-not $Destination) { $Destination = Join-Path $DSI360_RACINE 'data\backups' }
    if (-not $Copie) {
        Write-Dsi360Alerte 'Aucune copie hors machine (-Copie) : les sauvegardes resteront sur ce disque.'
        Write-Dsi360Info 'Le jour ou ce disque lache, la base ET ses sauvegardes partent ensemble.'
    }
    if (-not $Alerte) {
        Write-Dsi360Alerte 'Aucun destinataire d''alerte (-Alerte) : seul le journal Windows sera ecrit.'
    }

    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

    # Un contrôle qui traîne doit rendre la main : sans limite, une tâche bloquée empêcherait
    # toutes les suivantes (MultipleInstances IgnoreNew).
    function New-Reglages {
        param([int] $LimiteMinutes)
        New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -StartWhenAvailable -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (New-TimeSpan -Minutes $LimiteMinutes)
    }
    function Arguments {
        param([string] $Script, [string] $Suite = '')
        "-NoProfile -ExecutionPolicy Bypass -File `"$Script`" $Suite".TrimEnd()
    }

    # --- 3. Surveillance -----------------------------------------------------------------------
    Write-Dsi360Etape 'Tache DSI360-Surveillance (toutes les 5 min)'
    $suite = "-Tache $Tache -UrlSante https://127.0.0.1:$Port/healthz -UrlPret https://127.0.0.1:$Port/readyz"
    if ($Alerte) { $suite += " -Destinataire $Alerte" }
    # Répétition « pour toujours » à partir de maintenant : un déclencheur quotidien ne surveillerait
    # que quelques minutes par jour.
    $decl = New-ScheduledTaskTrigger -Once -At (Get-Date) `
                -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::MaxValue)
    Register-ScheduledTask -TaskName 'DSI360-Surveillance' -Force -Principal $principal `
        -Trigger $decl -Settings (New-Reglages 10) `
        -Action (New-ScheduledTaskAction -Execute $pwsh -Argument (Arguments $surveiller $suite)) |
        Out-Null
    Write-Dsi360Ok 'Installee'

    # --- 4. Sauvegarde -------------------------------------------------------------------------
    Write-Dsi360Etape 'Tache DSI360-Sauvegarde (chaque jour a 02:00)'
    $suite = "-Destination `"$Destination`" -RetentionJours $RetentionJours"
    if ($Copie) { $suite += " -Copie `"$Copie`"" }
    Register-ScheduledTask -TaskName 'DSI360-Sauvegarde' -Force -Principal $principal `
        -Trigger (New-ScheduledTaskTrigger -Daily -At '02:00') -Settings (New-Reglages 120) `
        -Action (New-ScheduledTaskAction -Execute $pwsh -Argument (Arguments $sauvegarde $suite)) |
        Out-Null
    Write-Dsi360Ok "Installee - vers $Destination$(if ($Copie) { " puis $Copie" })"

    # --- 5. Preuve de restauration -------------------------------------------------------------
    Write-Dsi360Etape 'Tache DSI360-VerifSauvegarde (dimanche 03:00)'
    if ($SansVerif) {
        Write-Dsi360Alerte 'Ignoree (-SansVerif). Vos sauvegardes ne seront jamais eprouvees.'
    } else {
        # On éprouve la copie hors machine quand elle existe : c'est celle dont on se servira
        # vraiment le jour où la machine aura brûlé.
        $ou = if ($Copie) { $Copie } else { $Destination }
        Register-ScheduledTask -TaskName 'DSI360-VerifSauvegarde' -Force -Principal $principal `
            -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '03:00') `
            -Settings (New-Reglages 120) `
            -Action (New-ScheduledTaskAction -Execute $pwsh `
                        -Argument (Arguments $verifier "-Dossier `"$ou`"")) | Out-Null
        Write-Dsi360Ok "Installee - eprouve les sauvegardes de $ou"
    }

    $lignes = @(
        'DSI360-Surveillance     toutes les 5 min',
        "DSI360-Sauvegarde       02:00 -> $Destination",
        $(if ($SansVerif) { 'DSI360-VerifSauvegarde  NON installee' }
          else { 'DSI360-VerifSauvegarde  dimanche 03:00' }),
        ''
    )
    if (-not $SansVerif) {
        $lignes += @(
            'Reste a faire UNE fois, en superuser postgres, sans quoi la preuve de',
            'restauration echouera faute de base ou la travailler :',
            '   psql -U postgres -f infra\local\base\provisionner-db-verif.sql',
            ''
        )
    }
    $lignes += 'Verifiez tout de suite : Start-ScheduledTask -TaskName DSI360-Surveillance'
    Write-Dsi360Bilan -Titre 'Resilience installee' -Lignes $lignes
    exit 0
} catch {
    Write-Dsi360Echec $_.Exception.Message
    Write-Dsi360Bilan -Titre 'Installation interrompue' -Couleur 'Red' -Lignes @(
        'Aucune tache partiellement installee ne tourne : reprenez apres correction.'
    )
    Wait-Dsi360Fermeture
    exit 1
}
