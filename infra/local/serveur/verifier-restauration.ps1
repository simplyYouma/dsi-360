# Prouve qu'une sauvegarde de DSI 360 est restaurable — sur une base jetable, jamais sur la vraie.
#
# Une sauvegarde qu'on n'a jamais restaurée n'est pas une sauvegarde : c'est un fichier dont on
# espère quelque chose. `pg_dump` peut réussir tous les jours et produire un dump inexploitable —
# version de PostgreSQL incompatible, écriture tronquée, disque plein en fin de course. On ne le
# découvre alors que le jour de l'incident, au pire moment.
#
# Ce script prend la sauvegarde la plus récente, la restaure dans une base **temporaire**, compte
# ce qui en sort, puis supprime cette base. La base de production n'est ni lue ni touchée.
#
#   infra\local\serveur\verifier-restauration.ps1
#   infra\local\serveur\verifier-restauration.ps1 -Dossier \\nas-afg\dsi360\backups
#   infra\local\serveur\verifier-restauration.ps1 -Fichier C:\...\dsi360_dsi360_20260903_020000.dump
#
# À planifier une fois par semaine (tâche « DSI360-VerifSauvegarde »). Prévoir de la place : la
# base temporaire pèse le poids de la vraie, le temps du contrôle.
#
# ATTENTION, encodage : UTF-8 **avec BOM** obligatoire (cf. lib/DSI360.Common.ps1).
param(
    [string] $Dossier    = '',              # où chercher la sauvegarde la plus récente
    [string] $Fichier    = '',              # ou bien une sauvegarde précise
    [string] $BaseTest   = 'dsi360_verif',  # base jetable, créée puis supprimée
    [string] $PgBin      = '',
    [int]    $AgeMaxHeures = 36,            # au-delà, la sauvegarde n'est plus quotidienne
    [switch] $Garder                        # ne pas supprimer la base à la fin (diagnostic)
)

$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\..\lib\DSI360.Common.ps1"
. "$PSScriptRoot\..\env.ps1"

# Vider la base de contrôle. « public » en fait partie : `schema_migrations` y vit, et pg_restore
# s'arrête sec sur une table déjà présente — la vérification aurait échoué chaque semaine sans que
# la sauvegarde y soit pour rien. On recrée le schéma aussitôt : la restauration en a besoin.
$SQL_VIDER = @'
DROP SCHEMA IF EXISTS core CASCADE;
DROP SCHEMA IF EXISTS audit CASCADE;
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
'@

Initialize-Dsi360Console -Titre 'DSI 360 - Verification de sauvegarde'
$null = Initialize-Dsi360Journal -Dossier (Join-Path $PSScriptRoot '..\logs') -Prefixe 'verif-sauvegarde'
Show-Dsi360Banniere -Titre 'Preuve de restauration' `
                    -Sous 'La sauvegarde est-elle vraiment exploitable ?' -Racine $DSI360_RACINE

# --- Outils PostgreSQL -------------------------------------------------------------------------
function Resolve-OutilPg {
    param([string] $Nom)
    if ($PgBin) { return (Join-Path $PgBin "$Nom.exe") }
    $cmd = Get-Command "$Nom.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\$Nom.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}

try {
    Set-Dsi360EtapeTotal 5

    # --- 1. Les outils -------------------------------------------------------------------------
    Write-Dsi360Etape 'Outils PostgreSQL'
    $pgRestore = Resolve-OutilPg 'pg_restore'
    $psql      = Resolve-OutilPg 'psql'
    foreach ($paire in @(@{ n = 'pg_restore'; p = $pgRestore }, @{ n = 'psql'; p = $psql })) {
        if (-not $paire.p -or -not (Test-Path $paire.p)) {
            Write-Dsi360Echec "$($paire.n) introuvable."
            Write-Dsi360Cadre -Titre 'Que faire' -Couleur 'Yellow' -Lignes @(
                'Indiquez le dossier des binaires PostgreSQL :',
                "   verifier-restauration.ps1 -PgBin 'C:\Program Files\PostgreSQL\17\bin'"
            )
            throw "$($paire.n) introuvable."
        }
    }
    Write-Dsi360Ok 'pg_restore et psql presents'

    # --- 2. La sauvegarde à éprouver -------------------------------------------------------------
    Write-Dsi360Etape 'Choix de la sauvegarde'
    if (-not $Fichier) {
        if (-not $Dossier) { $Dossier = Join-Path $DSI360_RACINE 'data\backups' }
        if (-not (Test-Path $Dossier)) { throw "Dossier de sauvegardes introuvable : $Dossier" }
        $recente = Get-ChildItem $Dossier -Filter 'dsi360_*.dump' -ErrorAction SilentlyContinue |
                   Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $recente) { throw "Aucune sauvegarde dans $Dossier." }
        $Fichier = $recente.FullName
    }
    if (-not (Test-Path $Fichier)) { throw "Sauvegarde introuvable : $Fichier" }

    $item = Get-Item $Fichier
    $age = [int]((Get-Date) - $item.LastWriteTime).TotalHours
    Write-Dsi360Info "Fichier : $($item.Name)"
    Write-Dsi360Info "Taille  : $([math]::Round($item.Length / 1MB, 1)) Mo   -   Age : $age h"

    # Une sauvegarde restaurable mais vieille de trois jours veut dire que la tache quotidienne ne
    # tourne plus. Le controle serait vert et la protection, absente.
    if ($age -gt $AgeMaxHeures) {
        Write-Dsi360Alerte "La derniere sauvegarde a $age h (seuil : $AgeMaxHeures h)."
        Write-Dsi360Info 'La tache quotidienne « DSI360-Sauvegarde » tourne-t-elle encore ?'
    } else {
        Write-Dsi360Ok 'Sauvegarde recente'
    }

    # --- 3. La base jetable ----------------------------------------------------------------------
    # On se connecte avec le compte applicatif, sur la base « postgres » : creer et supprimer la
    # base de test ne doit rien devoir a un superuser de plus.
    $dsn = $env:DSI360_DATABASE_URL
    if ([string]::IsNullOrWhiteSpace($dsn)) { throw 'DSI360_DATABASE_URL absent de infra\local\.env.' }
    $u = [uri]($dsn -replace '\+asyncpg', '')
    $infos = $u.UserInfo.Split(':', 2)
    $utilisateur = [uri]::UnescapeDataString($infos[0])
    $motDePasse  = if ($infos.Count -gt 1) { [uri]::UnescapeDataString($infos[1]) } else { '' }
    $baseReelle  = $u.AbsolutePath.TrimStart('/')
    $portDb      = if ($u.Port -gt 0) { $u.Port } else { 5432 }

    # Garde-fou : on ne restaure JAMAIS par-dessus la base de production, quoi qu'on ait tape.
    if ($BaseTest -eq $baseReelle) {
        throw "La base de test porte le nom de la base de production ($baseReelle). Refus."
    }

    $env:PGPASSWORD = $motDePasse
    $commun = @('--host', $u.Host, '--port', $portDb, '--username', $utilisateur)

    Write-Dsi360Etape "Base jetable $BaseTest"
    # La base existe deja, creee une fois par le superuser (provisionner-db-verif.sql). On ne la
    # cree pas ici : il faudrait donner CREATEDB au compte applicatif, c'est-a-dire elargir les
    # droits du compte qui sert la production pour le confort d'un controle hebdomadaire.
    $existe = & $psql @commun --dbname postgres -t -A `
        -c "SELECT 1 FROM pg_database WHERE datname = '$BaseTest';" 2>&1
    if ("$existe".Trim() -ne '1') {
        Write-Dsi360Echec "La base de verification '$BaseTest' n'existe pas."
        Write-Dsi360Cadre -Titre 'Que faire' -Couleur 'Yellow' -Lignes @(
            'A creer une seule fois, en superuser postgres. Le numero de version de',
            'PostgreSQL varie d''un serveur a l''autre : on le laisse chercher.',
            '',
            '   $psql = (Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" |',
            '            Sort-Object FullName -Descending | Select-Object -First 1).FullName',
            '   & $psql -U postgres -f infra\local\base\provisionner-db-verif.sql',
            '',
            'Le compte applicatif en sera proprietaire, sans gagner le moindre privilege.'
        )
        throw "Base '$BaseTest' absente."
    }

    # On la vide avant de restaurer : le controle precedent y a laisse ses tables, et pg_restore
    # s'arreterait sur des objets deja presents. Le proprietaire de la base a le droit de le faire
    # sans etre superuser.
    $null = Invoke-Dsi360Verifie -Quoi "remise a blanc de $BaseTest" -Action {
        & $psql @commun --dbname $BaseTest -v ON_ERROR_STOP=1 -q -c $SQL_VIDER 2>&1
    } -Remede @(
        "Le compte $utilisateur est-il bien proprietaire de $BaseTest ?",
        "   ALTER DATABASE $BaseTest OWNER TO $utilisateur;"
    )

    # --- 4. La restauration ----------------------------------------------------------------------
    Write-Dsi360Etape 'Restauration'
    # `--exit-on-error` : sans lui, pg_restore signale les erreurs et sort quand meme en succes —
    # on croirait la sauvegarde bonne alors que la moitie des tables manque.
    $ok = Invoke-Dsi360Verifie -Quoi 'pg_restore' -NonBloquant -Action {
        & $pgRestore @commun --dbname $BaseTest --no-owner --no-privileges --exit-on-error $Fichier 2>&1
    }
    if (-not $ok) {
        Write-Dsi360Cadre -Titre 'Sauvegarde inexploitable' -Couleur 'Red' -Lignes @(
            'Ce fichier ne se restaure pas. Ce n''est PAS un incident de ce script :',
            'c''est la sauvegarde du serveur qui ne protege rien.',
            '',
            "Fichier : $Fichier",
            '',
            'A verifier : la version de PostgreSQL, l''espace disque au moment du dump,',
            'et les journaux de la tache DSI360-Sauvegarde.'
        )
        throw 'Restauration en echec.'
    }

    # --- 5. Le contenu ---------------------------------------------------------------------------
    # Une base restaurée mais vide passerait pg_restore sans broncher. On compte ce qui compte.
    Write-Dsi360Etape 'Controle du contenu'
    $requete = @"
SELECT (SELECT count(*) FROM core.utilisateur)
    || '|' || (SELECT count(*) FROM core.activite)
    || '|' || (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'core');
"@
    $brut = & $psql @commun --dbname $BaseTest -t -A -c $requete 2>&1
    $chiffres = ("$brut".Trim() -split '\|')
    if ($chiffres.Count -lt 3) { throw "Contenu illisible apres restauration : $brut" }
    $utilisateurs = [int]$chiffres[0]
    $activites    = [int]$chiffres[1]
    $tables       = [int]$chiffres[2]

    Write-Dsi360Info "Tables du schema core : $tables"
    Write-Dsi360Info "Comptes utilisateurs  : $utilisateurs"
    Write-Dsi360Info "Activites             : $activites"

    # Sans compte, personne ne peut se connecter : la restauration serait inutilisable.
    if ($tables -lt 10 -or $utilisateurs -lt 1) {
        throw "Restauration suspecte : $tables tables, $utilisateurs compte(s). La sauvegarde est incomplete."
    }
    Write-Dsi360Ok 'La sauvegarde est exploitable'

    Write-Dsi360Bilan -Titre 'Sauvegarde verifiee' -Lignes @(
        "Fichier   : $($item.Name)  ($([math]::Round($item.Length / 1MB, 1)) Mo, $age h)",
        "Restauree : $tables tables, $utilisateurs comptes, $activites activites",
        '',
        'Cette sauvegarde a ete restauree pour de vrai, pas seulement lue.'
    )
    exit 0
} catch {
    Write-Dsi360Echec $_.Exception.Message
    Write-Dsi360Bilan -Titre 'Verification en echec' -Couleur 'Red' -Lignes @(
        'La sauvegarde n''a pas pu etre prouvee. Le detail est dans le journal.'
    )
    exit 1
} finally {
    # Le contenu ne doit pas survivre au controle : il pese le poids de la base de production. La
    # base, elle, reste — la recreer demanderait un superuser a chaque passage.
    if (-not $Garder -and $psql -and (Test-Path $psql)) {
        & $psql @commun --dbname $BaseTest -q -c $SQL_VIDER 2>&1 | Out-Null
    }
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
