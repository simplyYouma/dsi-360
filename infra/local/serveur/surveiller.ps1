# Surveillance de DSI 360 — relance le service quand il ne répond plus, alerte quand il ne peut pas
# être relancé. Prévu pour la tâche planifiée « DSI360-Surveillance », toutes les 5 minutes.
#
# Pourquoi ce script existe. La tâche « DSI360 » démarre au boot et Windows la relance trois fois en
# cas d'échec. Passé ces trois essais, elle abandonne — définitivement, jusqu'au prochain
# redémarrage de la machine — et personne n'en est averti. Un incident de nuit se découvrait donc le
# matin, par un utilisateur.
#
# Ce qu'il fait, et ce qu'il ne fait pas :
#   - `/healthz` muet          -> le processus est mort ou bloqué : on RELANCE la tâche.
#   - `/readyz` « degrade »    -> l'API vit, c'est PostgreSQL qui ne répond pas. On ALERTE sans
#                                 relancer : redémarrer l'API ne ramènerait pas la base, et
#                                 masquerait la vraie panne derrière un service qui claque.
#   - trop de relances d'affilée -> on ARRÊTE de relancer et on alerte. Une panne qui revient
#                                 toutes les cinq minutes n'est pas un incident passager : la
#                                 relancer en boucle efface les traces au lieu de les livrer.
#
# L'alerte va toujours dans le **journal d'événements Windows** (source « DSI 360 ») : c'est le seul
# canal qui ne dépend d'aucune configuration. L'e-mail n'est qu'un bonus, quand un relais SMTP et un
# destinataire sont renseignés.
#
# ATTENTION, encodage : UTF-8 **avec BOM** obligatoire (cf. lib/DSI360.Common.ps1).
param(
    [string] $Tache              = 'DSI360',
    [string] $UrlSante           = 'https://127.0.0.1:8453/healthz',
    [string] $UrlPret            = 'https://127.0.0.1:8453/readyz',
    [int]    $RelancesMax        = 3,     # au-delà, sur la fenêtre ci-dessous, on n'insiste plus
    [int]    $FenetreMinutes     = 60,
    [int]    $ToleranceDegradeMn = 10,    # base absente : on alerte passé ce délai, pas avant
    [string] $Destinataire       = '',    # e-mail d'alerte (vide = journal Windows seul)
    [switch] $Simuler                     # diagnostique sans relancer ni alerter
)

$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\..\lib\DSI360.Common.ps1"
. "$PSScriptRoot\..\env.ps1"

Initialize-Dsi360Console -Titre 'DSI 360 - Surveillance'
$null = Initialize-Dsi360Journal -Dossier (Join-Path $PSScriptRoot '..\logs') -Prefixe 'surveillance'

# --- Mémoire entre deux passages ---------------------------------------------------------------
# La tâche lance un processus neuf toutes les cinq minutes : sans ce fichier, chaque passage
# croirait être le premier et relancerait indéfiniment.
$fichierEtat = Join-Path $PSScriptRoot '..\logs\surveillance-etat.json'
$etat = [ordered]@{ relances = @(); degradeDepuis = $null; alerteEnvoyee = $false }
if (Test-Path $fichierEtat) {
    try {
        $lu = Get-Content $fichierEtat -Raw | ConvertFrom-Json
        if ($lu.relances)      { $etat.relances      = @($lu.relances) }
        if ($lu.degradeDepuis) { $etat.degradeDepuis = $lu.degradeDepuis }
        if ($null -ne $lu.alerteEnvoyee) { $etat.alerteEnvoyee = [bool]$lu.alerteEnvoyee }
    } catch {
        # Un état illisible ne doit pas empêcher de surveiller : on repart d'une page blanche.
        Write-Dsi360Alerte "Etat precedent illisible, on repart a zero : $($_.Exception.Message)"
    }
}

function Save-Etat {
    $etat | ConvertTo-Json -Depth 4 | Set-Content $fichierEtat -Encoding UTF8
}

# --- Alerte ------------------------------------------------------------------------------------
function Send-Alerte {
    param([string] $Sujet, [string[]] $Lignes)

    $corps = ($Lignes -join [Environment]::NewLine)
    Write-Dsi360Echec $Sujet
    foreach ($l in $Lignes) { Write-Dsi360Info "   $l" }

    if ($Simuler) { Write-Dsi360Info '(simulation : aucune alerte envoyee)'; return }

    # 1. Journal d'evenements Windows — toujours, sans configuration.
    try {
        if (-not [System.Diagnostics.EventLog]::SourceExists('DSI 360')) {
            New-EventLog -LogName Application -Source 'DSI 360'
        }
        Write-EventLog -LogName Application -Source 'DSI 360' -EntryType Error -EventId 1360 `
                       -Message "$Sujet`r`n`r`n$corps"
        Write-Dsi360Ok 'Alerte inscrite au journal d''evenements Windows'
    } catch {
        # Creer la source demande les droits administrateur au premier passage seulement.
        Write-Dsi360Alerte "Journal d'evenements indisponible : $($_.Exception.Message)"
    }

    # 2. E-mail — seulement si un relais ET un destinataire sont connus.
    $hote = $env:SMTP_HOTE
    if ([string]::IsNullOrWhiteSpace($hote) -or [string]::IsNullOrWhiteSpace($Destinataire)) {
        Write-Dsi360Info 'Pas d''e-mail : relais SMTP ou destinataire non renseigne.'
        return
    }
    try {
        $expediteur = if ($env:SMTP_EXPEDITEUR) { $env:SMTP_EXPEDITEUR } else { "dsi360@$env:COMPUTERNAME" }
        $parametres = @{
            SmtpServer = $hote
            Port       = if ($env:SMTP_PORT) { [int]$env:SMTP_PORT } else { 587 }
            From       = $expediteur
            To         = $Destinataire
            Subject    = "[DSI 360] $Sujet"
            Body       = $corps
            UseSsl     = ($env:SMTP_TLS -ne 'false')
        }
        if ($env:SMTP_UTILISATEUR) {
            $motDePasse = ConvertTo-SecureString $env:SMTP_MOT_DE_PASSE -AsPlainText -Force
            $parametres.Credential = New-Object System.Management.Automation.PSCredential(
                $env:SMTP_UTILISATEUR, $motDePasse)
        }
        # Send-MailMessage est deprecie mais reste le seul envoi natif sans dependance : le
        # serveur n'a pas d'acces sortant pour en installer une.
        Send-MailMessage @parametres -WarningAction SilentlyContinue
        Write-Dsi360Ok "Alerte envoyee a $Destinataire"
    } catch {
        Write-Dsi360Alerte "E-mail d'alerte non parti : $($_.Exception.Message)"
    }
}

# --- Sondes ------------------------------------------------------------------------------------
# On interroge par `curl.exe`, livré avec Windows, et non par Invoke-WebRequest : `-SkipCertificateCheck`
# n'existe qu'en PowerShell 7, alors qu'une surveillance doit tourner même si le serveur n'a que
# 5.1. Le certificat du serveur est auto-signé et l'on s'adresse à 127.0.0.1 : le vérifier ferait
# échouer la sonde à coup sûr sans rien prouver.
$curl = Resolve-Dsi360Executable 'curl.exe'

function Get-Sonde {
    param([string] $Url)
    if ($curl) {
        # Le corps puis, sur la dernière ligne, le code HTTP : une seule requête dit les deux.
        # PowerShell rend déjà la sortie d'un programme externe ligne par ligne — d'où le tableau,
        # et surtout PAS une interpolation "$sortie", qui recollerait tout avec des espaces et
        # ferait passer le code HTTP pour un morceau de la réponse.
        $lignes = @(& $curl -k -s --max-time 10 -w "`n%{http_code}" $Url 2>&1 | ForEach-Object { "$_" })
        if ($lignes.Count -eq 0) { return @{ Ok = $false; Contenu = 'aucune reponse de curl' } }
        $code = $lignes[-1].Trim()
        # Le corps, c'est tout sauf cette dernière ligne. Quand curl n'a rien reçu il n'y a QUE le
        # code : sans ce test, on l'afficherait une seconde fois en guise de réponse du serveur.
        $corps = if ($lignes.Count -gt 1) { ($lignes[0..($lignes.Count - 2)] -join ' ').Trim() } else { '' }
        if ($code -eq '200') { return @{ Ok = $true; Contenu = $corps } }
        return @{ Ok = $false; Contenu = "code HTTP '$code' - $corps" }
    }
    try {
        $r = Invoke-WebRequest -Uri $Url -TimeoutSec 10 -UseBasicParsing
        return @{ Ok = ($r.StatusCode -eq 200); Contenu = $r.Content }
    } catch {
        return @{ Ok = $false; Contenu = $_.Exception.Message }
    }
}

$maintenant = Get-Date
Write-Dsi360Etape 'Controle de vie'
$sante = Get-Sonde -Url $UrlSante

if ($sante.Ok) {
    Write-Dsi360Ok "L'API repond sur $UrlSante"

    # L'API vit : toute alerte de mort precedente est close, et l'historique de relances s'efface
    # des qu'il sort de la fenetre - sinon un incident d'il y a un mois bloquerait la relance
    # d'aujourd'hui.
    $limite = $maintenant.AddMinutes(-$FenetreMinutes)
    $etat.relances = @($etat.relances | Where-Object { [datetime]$_ -gt $limite })

    Write-Dsi360Etape 'Controle de la base'
    $pret = Get-Sonde -Url $UrlPret
    $degrade = (-not $pret.Ok) -or ($pret.Contenu -match 'degrade')

    if (-not $degrade) {
        Write-Dsi360Ok 'La base repond'
        $etat.degradeDepuis = $null
        $etat.alerteEnvoyee = $false
        Save-Etat
        Write-Dsi360Bilan -Titre 'DSI 360 est en ligne' -Lignes @('Service et base repondent.')
        exit 0
    }

    # Base absente. On ne relance PAS : l'API n'y est pour rien, et pool_pre_ping la rattachera
    # d'elle-meme des que PostgreSQL reviendra. On laisse passer un creux court (redemarrage du
    # service PostgreSQL, bascule de sauvegarde) avant de deranger quelqu'un.
    if (-not $etat.degradeDepuis) { $etat.degradeDepuis = $maintenant.ToString('o') }
    $depuis = [datetime]$etat.degradeDepuis
    $minutes = [int]($maintenant - $depuis).TotalMinutes
    Write-Dsi360Alerte "Base injoignable depuis $minutes min"

    if ($minutes -ge $ToleranceDegradeMn -and -not $etat.alerteEnvoyee) {
        Send-Alerte -Sujet "Base de donnees injoignable depuis $minutes minutes" -Lignes @(
            "Serveur : $env:COMPUTERNAME",
            "Sonde   : $UrlPret",
            "Reponse : $($pret.Contenu)",
            '',
            'L''API repond mais ne joint pas PostgreSQL. Le service n''a PAS ete relance :',
            'le redemarrer ne ramenerait pas la base et effacerait le diagnostic.',
            '',
            'A verifier : le service PostgreSQL, l''espace disque, les journaux de la base.'
        )
        $etat.alerteEnvoyee = $true
    }
    Save-Etat
    Write-Dsi360Bilan -Titre 'Service en ligne, base injoignable' -Couleur 'Yellow' -Lignes @(
        "Degrade depuis $minutes min - aucun redemarrage, c'est PostgreSQL qu'il faut regarder."
    )
    exit 1
}

# --- L'API ne repond plus ----------------------------------------------------------------------
Write-Dsi360Echec "Aucune reponse sur $UrlSante"
Write-Dsi360Info "Detail : $($sante.Contenu)"

$limite = $maintenant.AddMinutes(-$FenetreMinutes)
$recentes = @($etat.relances | Where-Object { [datetime]$_ -gt $limite })

if ($recentes.Count -ge $RelancesMax) {
    # Relancer une quatrieme fois ferait tourner la panne en rond et ecraserait les traces.
    Send-Alerte -Sujet 'DSI 360 ne redemarre pas' -Lignes @(
        "Serveur : $env:COMPUTERNAME",
        "Tache   : $Tache",
        "Sonde   : $UrlSante",
        "Detail  : $($sante.Contenu)",
        '',
        "$($recentes.Count) redemarrages en $FenetreMinutes minutes n'ont pas suffi.",
        'La surveillance cesse de relancer : la panne est permanente, une intervention est requise.',
        '',
        "Journaux : $(Join-Path $DSI360_RACINE 'infra\local\logs')"
    )
    $etat.relances = $recentes
    Save-Etat
    Write-Dsi360Bilan -Titre 'Panne persistante - intervention requise' -Couleur 'Red' -Lignes @(
        "$($recentes.Count) relances en $FenetreMinutes min sans succes. Plus de relance automatique."
    )
    exit 2
}

Write-Dsi360Etape 'Relance du service'
if ($Simuler) {
    Write-Dsi360Info "(simulation : la tache '$Tache' aurait ete relancee)"
    exit 0
}

if (-not (Get-ScheduledTask -TaskName $Tache -ErrorAction SilentlyContinue)) {
    Send-Alerte -Sujet "Tache planifiee '$Tache' introuvable" -Lignes @(
        "Serveur : $env:COMPUTERNAME",
        'La surveillance ne peut rien relancer : la tache qui porte le service n''existe pas.',
        'Reinstallez-la : infra\local\serveur\installer-tache.bat'
    )
    exit 2
}

try {
    Stop-ScheduledTask -TaskName $Tache -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskName $Tache
    $etat.relances = @($recentes) + @($maintenant.ToString('o'))
    Save-Etat
    Write-Dsi360Ok "Tache $Tache relancee (essai $($etat.relances.Count)/$RelancesMax)"
} catch {
    Send-Alerte -Sujet 'Relance impossible' -Lignes @(
        "Serveur : $env:COMPUTERNAME",
        "Tache   : $Tache",
        "Erreur  : $($_.Exception.Message)",
        '',
        'La surveillance tourne-t-elle bien avec des droits administrateur ?'
    )
    exit 2
}

# Verifier que la relance a servi a quelque chose : annoncer « relance » sans le controler
# reviendrait a se rassurer soi-meme.
if (Test-Dsi360Http -Url $UrlSante -Secondes 60 -SansVerifierCertificat) {
    Write-Dsi360Ok 'Le service repond de nouveau'
    Write-Dsi360Bilan -Titre 'Service relance et de nouveau en ligne' -Lignes @(
        "Relance $($etat.relances.Count) sur les $FenetreMinutes dernieres minutes.",
        'Une relance reussie reste un incident : regardez pourquoi il est tombe.'
    )
    exit 0
}

Send-Alerte -Sujet 'DSI 360 ne repond pas apres relance' -Lignes @(
    "Serveur : $env:COMPUTERNAME",
    "Tache   : $Tache",
    'Le service a ete relance mais ne repond toujours pas au bout de 60 secondes.',
    '',
    "Journaux : $(Join-Path $DSI360_RACINE 'infra\local\logs')"
)
Write-Dsi360Bilan -Titre 'Relance sans effet' -Couleur 'Red' -Lignes @(
    'Le service ne repond pas 60 s apres sa relance.'
)
exit 2
