# Met à jour DSI 360 sur le serveur, d'un seul geste, de façon sûre et rejouable :
#   avant-vol -> sauvegarde -> git pull -> dépendances -> migrations -> build -> redémarrage
#   -> contrôle de santé.
#
# Pensé pour être lancé par maj-prod.bat (double-clic + élévation administrateur). Idempotent :
# le relancer après un échec reprend depuis le début sans rien casser.
#
# Ce que l'avant-vol regarde, et pourquoi : chacune de ces vérifications correspond à une panne
# réellement rencontrée en exploitation, où le message d'origine n'indiquait pas quoi faire —
# un verrou git oublié par un process mort, une branche divergente, un éditeur qui tient un
# fichier ouvert. Le script les nomme maintenant, avec la marche à suivre.
#
#   infra\local\maj-prod.ps1 [-Tache DSI360] [-UrlSante https://127.0.0.1:8453/healthz]
#                            [-SansRedemarrage] [-SansSauvegarde]
#
# ATTENTION, encodage : UTF-8 **avec BOM** obligatoire (cf. lib/DSI360.Common.ps1).
param(
    [string] $Tache = 'DSI360',
    [string] $UrlSante = 'https://127.0.0.1:8453/healthz',
    [switch] $SansRedemarrage,
    [switch] $SansSauvegarde
)

$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\lib\DSI360.Common.ps1"
. "$PSScriptRoot\env.ps1"

Initialize-Dsi360Console -Titre 'DSI 360 - Mise a jour du serveur'
$null = Initialize-Dsi360Journal -Dossier (Join-Path $PSScriptRoot 'logs') -Prefixe 'maj-prod'
Show-Dsi360Banniere -Titre 'Mise a jour de la production' `
                    -Sous "Tache $Tache  |  Sante $UrlSante" -Racine $DSI360_RACINE

$versionAvant = ''
$versionApres = ''

try {
    Set-Dsi360EtapeTotal 8
    Set-Location $DSI360_RACINE

    # === 1. Avant-vol =========================================================================
    Write-Dsi360Etape 'Controles d''avant-vol'

    if (-not (Resolve-Dsi360Executable 'git')) { throw 'git est introuvable sur ce serveur.' }

    # Verrou git resté d'un process mort. Sans ce contrôle, le pull échoue sur « Unable to create
    # .git/index.lock: File exists », message qui n'indique ni la cause ni le remède.
    $verrou = Join-Path $DSI360_RACINE '.git\index.lock'
    if (Test-Path $verrou) {
        $age = [int]((Get-Date) - (Get-Item $verrou).LastWriteTime).TotalMinutes
        $gitVivants = @(Get-Process git -ErrorAction SilentlyContinue)
        if ($gitVivants.Count -gt 0) {
            Write-Dsi360Echec "Un git est en cours (PID $($gitVivants.Id -join ', ')) et tient le verrou."
            Write-Dsi360Cadre -Titre 'Que faire' -Couleur 'Yellow' -Lignes @(
                'Attendez qu''il finisse, puis relancez cette mise a jour.',
                'S''il est bloque : Stop-Process -Name git -Force'
            )
            throw 'Verrou git tenu par un process vivant.'
        }
        # Aucun git vivant : le verrou est orphelin, on peut le retirer sans risque.
        Write-Dsi360Alerte "Verrou git orphelin ($age min, aucun git en cours) - retire"
        Remove-Item $verrou -Force
    }

    # Un éditeur ouvert sur le dépôt empêche git de remplacer certains fichiers (« unlink failed »).
    $editeurs = @(Get-Process Code, Cursor, devenv -ErrorAction SilentlyContinue)
    if ($editeurs.Count -gt 0) {
        $noms = ($editeurs.ProcessName | Sort-Object -Unique) -join ', '
        Write-Dsi360Alerte "Editeur ouvert sur ce poste : $noms"
        Write-Dsi360Info 'Fermez-le si la mise a jour echoue sur un fichier verrouille.'
    }

    # Le code du serveur ne se modifie que par git. Une retouche sur place serait écrasée ici,
    # ou ferait échouer le pull — dans les deux cas sans que personne l'ait voulu.
    $modifs = & git status --porcelain
    if ($modifs) {
        Write-Dsi360Echec 'Le depot porte des modifications locales.'
        foreach ($m in ($modifs | Select-Object -First 10)) { Write-Dsi360Ligne "          $m" 'DarkRed' }
        Write-Dsi360Cadre -Titre 'Que faire' -Couleur 'Yellow' -Lignes @(
            'Le code du serveur ne se modifie que par git.',
            '',
            'Pour repartir de ce qui est publie (ATTENTION : annule les retouches locales) :',
            '   git reset --hard origin/main',
            '   git clean -fd'
        )
        throw 'Modifications locales sur le serveur.'
    }
    Write-Dsi360Ok 'Depot propre, aucun verrou'

    $versionAvant = (& git rev-parse --short HEAD).Trim()
    Write-Dsi360Info "Version en place : $versionAvant"

    # === 2. Divergence ========================================================================
    Write-Dsi360Etape 'Etat par rapport au depot distant'
    $null = Invoke-Dsi360Verifie -Quoi 'git fetch' -Action { & git fetch --prune 2>&1 } -Remede @(
        'Verifiez l''acces reseau au depot (proxy, identifiants).'
    )
    $branche = (& git rev-parse --abbrev-ref HEAD).Trim()
    $compte = (& git rev-list --left-right --count "origin/$branche...HEAD") -split '\s+'
    $retard = [int]$compte[0]
    $avance = [int]$compte[1]

    if ($avance -gt 0) {
        Write-Dsi360Echec "La branche locale a $avance commit(s) que le depot distant n'a pas."
        Write-Dsi360Cadre -Titre 'Branche divergente' -Couleur 'Yellow' -Lignes @(
            'Du travail a ete commite ici, sur le serveur. Ce n''est pas prevu :',
            'le serveur consomme le code, il ne le produit pas.',
            '',
            'Pour aligner le serveur sur ce qui est publie (les commits locaux',
            'seront PERDUS - verifiez d''abord qu''ils ne valent rien) :',
            "   git reset --hard origin/$branche",
            '   git clean -fd'
        )
        throw 'Branche locale divergente.'
    }
    if ($retard -eq 0) {
        Write-Dsi360Ok 'Deja a jour - la mise a jour va tout de meme revalider l''installation'
    } else {
        Write-Dsi360Ok "$retard commit(s) a recuperer"
    }

    # === 3. Sauvegarde ========================================================================
    Write-Dsi360Etape 'Sauvegarde de la base'
    if ($SansSauvegarde) {
        Write-Dsi360Alerte 'Sauvegarde ignoree (-SansSauvegarde)'
    } else {
        # Avant toute migration : une migration ne se defait pas, une sauvegarde se restaure.
        $sauvegarde = Join-Path $PSScriptRoot 'sauvegarde-db.ps1'
        if (Test-Path $sauvegarde) {
            $null = Invoke-Dsi360Verifie -Quoi 'Sauvegarde avant migration' `
                -Action { & $sauvegarde 2>&1 } -NonBloquant -Remede @(
                    'La mise a jour peut continuer, mais sans filet en cas de migration ratee.',
                    'Verifiez pg_dump et le dossier de sauvegarde.'
                )
        } else {
            Write-Dsi360Alerte 'Script de sauvegarde introuvable - on continue sans filet'
        }
    }

    # === 4. Code ==============================================================================
    Write-Dsi360Etape 'Recuperation du code'
    $null = Invoke-Dsi360Verifie -Quoi 'git pull (fast-forward seulement)' `
        -Action { & git pull --ff-only 2>&1 } -Remede @(
            'Le pull refuse de fusionner : la branche a diverge depuis le fetch.',
            "   git reset --hard origin/$branche"
        )
    $versionApres = (& git rev-parse --short HEAD).Trim()
    Write-Dsi360Info "Version deployee : $versionApres"

    # === 5. Dependances =======================================================================
    Write-Dsi360Etape 'Dependances du backend'
    # L'installation est « editable » : le code source est lu en place, une modification de .py
    # est donc prise en compte sans rien reinstaller. Reinstaller a chaque mise a jour ne servait
    # qu'a exiger un acces sortant vers PyPI — et c'est exactement ce qui a fait echouer la mise
    # a jour du 02/09/2026, alors qu'aucune dependance n'avait bouge. On ne reinstalle donc que si
    # la DECLARATION des dependances a change, ou si le paquet n'est pas importable.
    $fichiersChanges = @(& git diff --name-only "$versionAvant..$versionApres")
    $declarationChangee = @(
        $fichiersChanges | Where-Object {
            $_ -match '^backend/(pyproject\.toml|requirements.*\.txt)$'
        }
    )
    & $DSI360_PY -c 'import dsi360' 2>$null | Out-Null
    $paquetPresent = ($LASTEXITCODE -eq 0)

    if ($declarationChangee.Count -gt 0 -or -not $paquetPresent) {
        $pourquoi = if ($declarationChangee.Count -gt 0) {
            "declaration modifiee ($($declarationChangee -join ', '))"
        } else {
            'paquet dsi360 non importable'
        }
        Write-Dsi360Info "Reinstallation necessaire : $pourquoi"
        $null = Invoke-Dsi360Verifie -Quoi 'pip install -e backend' `
            -Action { & $DSI360_PY -m pip install -e ".\backend" --no-input 2>&1 } -Remede @(
                'Verifiez l''acces reseau a PyPI (proxy) et l''environnement Python.',
                '',
                'Sans acces sortant, installez depuis un cache local de roues :',
                '   pip install -e .\backend --no-index --find-links <dossier-des-roues>'
            )
    } else {
        Write-Dsi360Ok 'Inchangees - installation editable, rien a reinstaller'
    }

    # === 6. Migrations ========================================================================
    Write-Dsi360Etape 'Migrations de la base'
    $null = Invoke-Dsi360Verifie -Quoi 'Application des migrations' `
        -Action { & $DSI360_PY -m dsi360.infrastructure.db.migrate 2>&1 } -Remede @(
            'Une migration a echoue : la base est restee dans son etat d''avant.',
            'Lisez le message ci-dessus - il nomme la migration fautive.',
            'Le code est deja a jour : corrigez la cause, puis relancez cette mise a jour.'
        )

    # === 7. Frontend ==========================================================================
    Write-Dsi360Etape 'Construction du frontend'
    Set-Location (Join-Path $DSI360_RACINE 'frontend')
    $null = Invoke-Dsi360Verifie -Quoi 'npm ci' -Action { & npm ci 2>&1 } -Remede @(
        'Verifiez Node.js et l''acces au registre npm.'
    )
    $null = Invoke-Dsi360Verifie -Quoi 'npm run build' -Action { & npm run build 2>&1 } -Remede @(
        'La compilation a echoue : le code publie ne compile pas.',
        'L''ancienne version est toujours en ligne - ne redemarrez pas la tache.'
    )
    Set-Location $DSI360_RACINE

    # === 8. Redemarrage et sante ==============================================================
    Write-Dsi360Etape 'Redemarrage et controle de sante'
    if ($SansRedemarrage) {
        Write-Dsi360Alerte 'Tache NON redemarree (-SansRedemarrage)'
        Write-Dsi360Info 'L''ancien code tourne encore : redemarrez la tache pour appliquer.'
        Write-Dsi360Bilan -Titre 'Mise a jour appliquee, service inchange' -Couleur 'Yellow' -Lignes @(
            "Version : $versionAvant -> $versionApres"
        )
        exit 0
    }

    if (-not (Get-ScheduledTask -TaskName $Tache -ErrorAction SilentlyContinue)) {
        Write-Dsi360Echec "Tache planifiee '$Tache' introuvable."
        Write-Dsi360Cadre -Titre 'Que faire' -Couleur 'Yellow' -Lignes @(
            'Creez-la une fois (cf. docs/06-DEPLOIEMENT §3.7), ou passez le bon nom :',
            "   infra\local\maj-prod.ps1 -Tache LeNomExact"
        )
        throw "Tache '$Tache' introuvable."
    }

    # Sans redémarrage, l'ancien code — et l'ancien certificat — restent en mémoire.
    Stop-ScheduledTask -TaskName $Tache
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskName $Tache
    Write-Dsi360Ok "Tache $Tache redemarree"

    if (Test-Dsi360Http -Url $UrlSante -Secondes 40 -SansVerifierCertificat) {
        Write-Dsi360Ok "L'API repond sur $UrlSante"
        Write-Dsi360Bilan -Titre 'DSI 360 est a jour et en ligne' -Lignes @(
            "Version : $versionAvant -> $versionApres",
            "Sante   : $UrlSante"
        )
    } else {
        Write-Dsi360Echec "L'API ne repond pas apres 40 s."
        Write-Dsi360Bilan -Titre 'Deploye, mais le service ne repond pas' -Couleur 'Red' -Lignes @(
            "Version : $versionAvant -> $versionApres",
            '',
            'Consultez les journaux de la tache planifiee, puis :',
            "   Get-ScheduledTaskInfo -TaskName $Tache"
        )
        Wait-Dsi360Fermeture
        exit 1
    }
} catch {
    Write-Dsi360Echec $_.Exception.Message
    $lignes = @('La mise a jour a ete interrompue.')
    # On relit HEAD au lieu de le supposer : apres un pull reussi, le code EST a jour meme si une
    # etape suivante a echoue. Annoncer « le serveur est reste en <ancienne version> » etait alors
    # faux — et c'est le genre de phrase sur laquelle on prend ensuite de mauvaises decisions.
    $versionCourante = ''
    try {
        $versionCourante = (& git -C $DSI360_RACINE rev-parse --short HEAD 2>$null).Trim()
    } catch { }
    if ($versionCourante -and $versionAvant -and $versionCourante -ne $versionAvant) {
        $lignes += "Le code est deja recupere ($versionAvant -> $versionCourante), mais"
        $lignes += "l'installation n'est pas terminee et le service n'a PAS ete redemarre :"
        $lignes += "il tourne encore sur l'ancien code charge en memoire."
    } elseif ($versionCourante) {
        $lignes += "Le serveur est reste en $versionCourante."
    }
    $lignes += 'Corrigez la cause indiquee ci-dessus, puis relancez : le script est rejouable.'
    Write-Dsi360Bilan -Titre 'Mise a jour interrompue' -Couleur 'Red' -Lignes $lignes
    Wait-Dsi360Fermeture
    exit 1
}
