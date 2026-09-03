# Bibliothèque commune aux scripts d'exploitation DSI 360 (démarrage, mise à jour, sauvegarde).
#
# Elle ne fait rien d'elle-même : elle donne aux scripts une console lisible, un journal de
# session, un affichage régulier, et quelques contrôles système qu'on refaisait à chaque fois.
#
# Pourquoi une bibliothèque plutôt que du copier-coller : les scripts d'exploitation sont lus
# dans l'urgence, souvent par quelqu'un qui ne les a pas écrits. Un déroulé identique d'un script
# à l'autre — mêmes étapes numérotées, mêmes symboles, même journal — vaut mieux que trois mises
# en page qui disent la même chose de trois façons.
#
# ATTENTION, encodage : ce fichier doit rester en UTF-8 **avec BOM**. Windows PowerShell 5.1 lit
# un .ps1 sans BOM comme du Windows-1252 : les accents deviennent illisibles et le script ne
# compile plus. Le double-clic passe par 5.1.

# --- État interne (jamais lu directement : tout passe par les fonctions) ----------------------
$script:Glyphes    = @{}
$script:EnCouleur  = $true
$script:AvecConsole = $false
$script:Journal    = $null
$script:EtapeIndex = 0
$script:EtapeTotal = 0
$script:Debut      = Get-Date


# =============================================================================================
#  Console et journal
# =============================================================================================

function Initialize-Dsi360Console {
    <#
      .SYNOPSIS
        Prépare la console : encodage UTF-8, jeu de symboles, titre de la fenêtre.
      .DESCRIPTION
        Les consoles Windows anciennes ne savent pas rendre les symboles Unicode. On détecte la
        capacité et l'on retombe sur un jeu ASCII : un « + » lisible vaut mieux qu'un losange noir.
    #>
    param([string] $Titre = 'DSI 360')

    try {
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $script:Glyphes = @{
            Ok = [char]0x2714; Echec = [char]0x2716; Alerte = [char]0x26A0
            Puce = [char]0x2022; Fleche = [char]0x25B8; Point = [char]0x00B7
            HG = [char]0x256D; HD = [char]0x256E; BG = [char]0x2570; BD = [char]0x256F
            H = [char]0x2500; V = [char]0x2502
        }
    } catch {
        $script:Glyphes = @{
            Ok = '+'; Echec = 'x'; Alerte = '!'; Puce = '*'; Fleche = '>'; Point = '-'
            HG = '+'; HD = '+'; BG = '+'; BD = '+'; H = '-'; V = '|'
        }
    }

    try { $Host.UI.RawUI.WindowTitle = $Titre } catch { }

    # Une sortie redirigée (fichier, CI, tâche planifiée) ne doit pas recevoir de couleurs.
    $script:EnCouleur = -not [Console]::IsOutputRedirected

    # Présence d'un vrai tampon console. La redirection ne suffit pas à le savoir : un processus
    # lancé sans console attachée (tâche planifiée, service) a une sortie non redirigée mais
    # aucun tampon — toute manipulation du curseur y échoue sur « Descripteur non valide ».
    $script:AvecConsole = $false
    try {
        $null = [Console]::CursorTop
        $script:AvecConsole = -not [Console]::IsOutputRedirected
    } catch {
        $script:AvecConsole = $false
    }

    $script:Debut = Get-Date
}

function Initialize-Dsi360Journal {
    <#
      .SYNOPSIS
        Ouvre le journal horodaté de la session et purge les plus anciens.
      .DESCRIPTION
        Tout ce qui s'affiche est aussi écrit ici. C'est ce qu'on relit quand la fenêtre s'est
        refermée, ou quand le script tourne en tâche planifiée sans personne devant.
    #>
    param(
        [Parameter(Mandatory = $true)][string] $Dossier,
        [string] $Prefixe = 'session',
        [int] $Retention = 15
    )

    if (-not (Test-Path -LiteralPath $Dossier)) {
        New-Item -ItemType Directory -Path $Dossier -Force | Out-Null
    }
    $horodatage = Get-Date -Format 'yyyyMMdd-HHmmss'
    $script:Journal = Join-Path $Dossier "$Prefixe-$horodatage.log"
    "=== DSI 360 - $Prefixe du $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" |
        Out-File -FilePath $script:Journal -Encoding UTF8

    # Rétention bornée : un dossier de journaux qui grossit sans fin finit par être l'incident.
    Get-ChildItem -LiteralPath $Dossier -Filter "$Prefixe-*.log" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $Retention |
        Remove-Item -Force -ErrorAction SilentlyContinue

    return $script:Journal
}

function Get-Dsi360Journal { return $script:Journal }

function Write-Dsi360Journal {
    <# .SYNOPSIS Écrit une ligne horodatée dans le journal (jamais à l'écran). #>
    param(
        [Parameter(Mandatory = $true)][AllowEmptyString()][string] $Message,
        [ValidateSet('INFO', 'ALERTE', 'ERREUR', 'DEBUG')][string] $Niveau = 'INFO'
    )
    if (-not $script:Journal) { return }
    $ligne = '{0} [{1}] {2}' -f (Get-Date -Format 'HH:mm:ss.fff'), $Niveau, $Message
    Add-Content -LiteralPath $script:Journal -Value $ligne -Encoding UTF8
}


# =============================================================================================
#  Affichage
# =============================================================================================

function Write-Dsi360Ligne {
    param([AllowEmptyString()][string] $Texte = '', [string] $Couleur = 'Gray')
    if ($script:EnCouleur) { Write-Host $Texte -ForegroundColor $Couleur } else { Write-Host $Texte }
}

#: Le vert de marque en couleurs vraies : --secondary #7fc81f, --secondary-hover #6fb314.
$script:MarqueVert      = "$([char]27)[38;2;127;200;31m"
$script:MarqueVertFonce = "$([char]27)[38;2;111;179;20m"
$script:MarqueFin       = "$([char]27)[0m"

function Write-Dsi360Marque {
    <# .SYNOPSIS Une ligne du logo, au vert exact de la charte quand la console le permet. #>
    param([AllowEmptyString()][string] $Texte = '', [switch] $Foncee)
    if (-not $script:EnCouleur) { Write-Host $Texte; return }
    # $PSStyle n'existe qu'en PowerShell 7 : sa présence dit que l'hôte interprète l'ANSI. En 5.1
    # on retombe sur les seize couleurs, où seul Green approche le vert du logo.
    if ($null -ne $PSStyle -and $PSStyle.OutputRendering -ne 'PlainText') {
        $ton = if ($Foncee) { $script:MarqueVertFonce } else { $script:MarqueVert }
        Write-Host "$ton$Texte$($script:MarqueFin)"
    } else {
        Write-Host $Texte -ForegroundColor $(if ($Foncee) { 'DarkGreen' } else { 'Green' })
    }
}

function Show-Dsi360Banniere {
    <# .SYNOPSIS En-tête de session : ce qu'on lance, où, et dans quel environnement. #>
    param(
        [Parameter(Mandatory = $true)][string] $Titre,
        [string] $Sous = '',
        [string] $Racine = ''
    )
    if ($script:AvecConsole) { try { Clear-Host } catch { } }
    $g = $script:Glyphes
    # Le vert de la marque (--secondary #7fc81f). En couleurs vraies quand la console les
    # gère — les seize couleurs héritées n'ont rien à ce ton — et repli sur Green sinon. Les
    # deux dernières lignes prennent le ton foncé (--secondary-hover) : le logo a du relief,
    # pas un aplat.
    Write-Dsi360Ligne ''
    Write-Dsi360Marque '    ____    ____   ___     _____   __     ___  '
    Write-Dsi360Marque '  |  _ \   / ___| |_ _|   |___ /  / /_   / _ \ '
    Write-Dsi360Marque '  | | | |  \___ \  | |      |_ \ | ''_ \ | | | |'
    Write-Dsi360Marque '  | |_| |   ___) | | |     ___) || (_) || |_| |' -Foncee
    Write-Dsi360Marque '  |____/   |____/ |___|   |____/  \___/  \___/ ' -Foncee
    Write-Dsi360Ligne ''
    Write-Dsi360Ligne "  $Titre" 'White'
    if ($Sous) { Write-Dsi360Ligne "  $Sous" 'DarkGray' }
    if ($Racine) { Write-Dsi360Ligne "  $($g.Point) $Racine" 'DarkGray' }
    Write-Dsi360Ligne ("  " + ($g.H.ToString() * 64)) 'DarkGray'
    Write-Dsi360Journal "DEMARRAGE : $Titre"
}

function Set-Dsi360EtapeTotal {
    param([Parameter(Mandatory = $true)][int] $Total)
    $script:EtapeTotal = $Total
    $script:EtapeIndex = 0
}

function Write-Dsi360Etape {
    <# .SYNOPSIS Ouvre une étape numérotée : on sait toujours où l'on en est, et combien il reste. #>
    param([Parameter(Mandatory = $true)][string] $Titre)
    $script:EtapeIndex++
    $compteur = if ($script:EtapeTotal -gt 0) { '[{0}/{1}]' -f $script:EtapeIndex, $script:EtapeTotal }
                else { '[{0}]' -f $script:EtapeIndex }
    Write-Dsi360Ligne ''
    Write-Dsi360Ligne ("  {0} {1} {2}" -f $compteur, $script:Glyphes.Fleche, $Titre) 'Cyan'
    Write-Dsi360Journal "ETAPE $($script:EtapeIndex)/$($script:EtapeTotal) : $Titre"
}

function Write-Dsi360Ok {
    param([Parameter(Mandatory = $true)][string] $Message)
    Write-Dsi360Ligne ("        {0} {1}" -f $script:Glyphes.Ok, $Message) 'Green'
    Write-Dsi360Journal "OK : $Message"
}

function Write-Dsi360Info {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string] $Message)
    Write-Dsi360Ligne ("        {0} {1}" -f $script:Glyphes.Point, $Message) 'DarkGray'
    Write-Dsi360Journal "INFO : $Message"
}

function Write-Dsi360Alerte {
    param([Parameter(Mandatory = $true)][string] $Message)
    Write-Dsi360Ligne ("        {0} {1}" -f $script:Glyphes.Alerte, $Message) 'Yellow'
    Write-Dsi360Journal $Message 'ALERTE'
}

function Write-Dsi360Echec {
    param([Parameter(Mandatory = $true)][string] $Message)
    Write-Dsi360Ligne ("        {0} {1}" -f $script:Glyphes.Echec, $Message) 'Red'
    Write-Dsi360Journal $Message 'ERREUR'
}

function Write-Dsi360Cadre {
    <# .SYNOPSIS Encadre un bloc (récapitulatif, diagnostic, marche à suivre). #>
    param(
        [Parameter(Mandatory = $true)][string] $Titre,
        [AllowEmptyCollection()][AllowEmptyString()][string[]] $Lignes = @(),
        [string] $Couleur = 'Green'
    )
    $largeur = 68
    $g = $script:Glyphes
    Write-Dsi360Ligne ''
    Write-Dsi360Ligne ("  {0}{1}{2}" -f $g.HG, ($g.H.ToString() * $largeur), $g.HD) $Couleur
    Write-Dsi360Ligne ("  {0} {1}{2}" -f $g.V, $Titre.PadRight($largeur - 2), ' ' + $g.V) $Couleur
    Write-Dsi360Ligne ("  {0}{1}{2}" -f $g.V, (' ' * $largeur), $g.V) $Couleur
    foreach ($ligne in $Lignes) {
        # On tronque plutôt que de casser le cadre : un encadré déformé se lit plus mal qu'un
        # texte abrégé, et le journal garde la ligne entière de toute façon.
        $sur = $ligne
        if ($sur.Length -gt ($largeur - 3)) { $sur = $sur.Substring(0, $largeur - 6) + '...' }
        Write-Dsi360Ligne ("  {0} {1}{2}" -f $g.V, $sur.PadRight($largeur - 2), ' ' + $g.V) $Couleur
        Write-Dsi360Journal "  | $ligne"
    }
    Write-Dsi360Ligne ("  {0}{1}{2}" -f $g.BG, ($g.H.ToString() * $largeur), $g.BD) $Couleur
    Write-Dsi360Ligne ''
}

function Write-Dsi360Bilan {
    <# .SYNOPSIS Clôture de session : durée écoulée et chemin du journal. #>
    param(
        [Parameter(Mandatory = $true)][string] $Titre,
        [AllowEmptyCollection()][string[]] $Lignes = @(),
        [string] $Couleur = 'Green'
    )
    $duree = (Get-Date) - $script:Debut
    $suite = @($Lignes)
    $suite += ''
    $suite += ('Duree : {0:mm\:ss}' -f $duree)
    if ($script:Journal) { $suite += "Journal : $($script:Journal)" }
    Write-Dsi360Cadre -Titre $Titre -Lignes $suite -Couleur $Couleur
}

function Wait-Dsi360Fermeture {
    <#
      .SYNOPSIS
        Retient la fenêtre pour qu'on puisse lire avant qu'elle ne se referme.
      .DESCRIPTION
        Sans effet quand l'entrée est redirigée ou la console absente (tâche planifiée, CI) :
        y attendre une touche bloquerait le poste indéfiniment.
    #>
    param([string] $Message = 'Entree pour fermer')
    if ([Console]::IsInputRedirected) { return }
    try { Read-Host "`n$Message" | Out-Null } catch { }
}


# =============================================================================================
#  Exécution contrôlée
# =============================================================================================

function Invoke-Dsi360Verifie {
    <#
      .SYNOPSIS
        Exécute une commande, capture sa sortie, et échoue en disant quoi faire.
      .DESCRIPTION
        Une commande qui échoue en silence est le pire cas : le script continue sur des bases
        fausses. Ici la sortie part au journal ; à l'écran on ne montre les dernières lignes que
        si ça a raté — le reste du temps, elles n'apprennent rien.
      .PARAMETER Remede
        Ce que la personne devant l'écran doit faire. Un message d'erreur sans marche à suivre
        oblige à ouvrir le code pour comprendre.
    #>
    param(
        [Parameter(Mandatory = $true)][string] $Quoi,
        [Parameter(Mandatory = $true)][scriptblock] $Action,
        [string[]] $Remede = @(),
        [switch] $NonBloquant
    )

    Write-Dsi360Journal "COMMANDE : $Quoi"
    $sortie = @()
    $code = 0

    # `$ErrorActionPreference = 'Stop'` — que posent les scripts appelants — transforme la
    # redirection `2>&1` de la sortie d'erreur d'un programme externe en erreur TERMINANTE.
    # On tombait alors dans le `catch` avec un message souvent vide : le journal ne gardait
    # qu'une ligne blanche là où pip expliquait précisément ce qui n'allait pas. On neutralise
    # la préférence le temps de l'appel, puis on la restaure.
    $prefPrecedente = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $sortie = & $Action 2>&1
        $code = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 0 }
    } catch {
        $sortie = @("$($_.Exception.GetType().Name) : $($_.Exception.Message)")
        $code = 1
    } finally {
        $ErrorActionPreference = $prefPrecedente
    }

    # Une sortie vide n'est pas une explication : on le dit, plutôt que d'aligner des blancs.
    $sortie = @($sortie | Where-Object { "$_".Trim() -ne '' })
    foreach ($ligne in $sortie) { Write-Dsi360Journal "    $ligne" }

    if ($code -eq 0) {
        Write-Dsi360Ok $Quoi
        return $true
    }

    Write-Dsi360Echec "$Quoi (code $code)"
    if ($sortie.Count -eq 0) {
        $muet = 'La commande a echoue sans rien ecrire - relancez-la a la main pour voir.'
        Write-Dsi360Ligne "          $muet" 'DarkRed'
        Write-Dsi360Journal $muet 'ERREUR'
    } else {
        foreach ($ligne in @($sortie | Select-Object -Last 12)) {
            Write-Dsi360Ligne ("          $ligne") 'DarkRed'
        }
    }
    if ($Remede.Count -gt 0) {
        Write-Dsi360Cadre -Titre 'Que faire' -Lignes $Remede -Couleur 'Yellow'
    }
    if (-not $NonBloquant) {
        throw "$Quoi a echoue (code $code)."
    }
    return $false
}

function Resolve-Dsi360Executable {
    <# .SYNOPSIS Chemin d'un exécutable, ou $null s'il est absent du PATH. #>
    param([Parameter(Mandatory = $true)][string] $Nom)
    $cmd = Get-Command $Nom -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}


# =============================================================================================
#  Réseau
# =============================================================================================

function Get-Dsi360PortOccupant {
    <#
      .SYNOPSIS
        Qui écoute sur ce port ? Renvoie $null s'il est libre.
      .DESCRIPTION
        On rend le nom du processus, pas seulement son PID : « port 8011 occupé par python.exe
        (PID 1234) » se comprend tout de suite, un numéro seul demande une recherche de plus.
    #>
    param([Parameter(Mandatory = $true)][int] $Port)

    $ecoute = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $ecoute) { return $null }

    $details = foreach ($pid_ in ($ecoute.OwningProcess | Sort-Object -Unique)) {
        $p = Get-Process -Id $pid_ -ErrorAction SilentlyContinue
        if ($p) { "$($p.ProcessName).exe (PID $pid_)" } else { "PID $pid_" }
    }
    return ($details -join ', ')
}

function Test-Dsi360Http {
    <#
      .SYNOPSIS
        Attend qu'une URL réponde 200, jusqu'à expiration. Vrai si elle a répondu.
      .DESCRIPTION
        `-SansVerifierCertificat` accepte l'auto-signé : en production le service se contrôle
        depuis la machine elle-même, sur un certificat qu'elle ne peut pas valider.
    #>
    param(
        [Parameter(Mandatory = $true)][string] $Url,
        [int] $Secondes = 30,
        [switch] $SansVerifierCertificat
    )

    $curl = Resolve-Dsi360Executable 'curl.exe'
    $limite = (Get-Date).AddSeconds($Secondes)
    while ((Get-Date) -lt $limite) {
        if ($curl) {
            $args_ = @('-s', '--max-time', '5', '-o', 'NUL', '-w', '%{http_code}', $Url)
            if ($SansVerifierCertificat) { $args_ = @('-k') + $args_ }
            $code = & $curl @args_ 2>$null
            if ($code -eq '200') { return $true }
        } else {
            try {
                $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
                if ($r.StatusCode -eq 200) { return $true }
            } catch { }
        }
        Start-Sleep -Milliseconds 800
    }
    return $false
}
