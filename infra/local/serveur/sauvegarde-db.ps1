# Sauvegarde native de la base DSI 360 (pg_dump, format custom -Fc, compressé et restaurable).
# Aucune dépendance Docker. À planifier (tâche « DSI360-Sauvegarde ») sur le serveur.
#
#   infra\local\serveur\sauvegarde-db.ps1
#   infra\local\serveur\sauvegarde-db.ps1 -Destination C:\MY_APPS\logs\DSI360\backups -RetentionJours 30
#   infra\local\serveur\sauvegarde-db.ps1 -Copie \\nas-afg\dsi360\backups
#
# La cible (-Destination) doit être HORS git et, idéalement, sur un volume sauvegardé/chiffré.
#
# `-Copie` recopie la sauvegarde AILLEURS QUE SUR CETTE MACHINE. Sans elle, la sauvegarde vit sur
# le même disque que la base qu'elle protège : le jour où ce disque lâche, on perd les deux d'un
# coup, et trente jours de rétention n'auront servi à rien. Un échec de copie ne fait pas échouer
# la sauvegarde — le dump local, lui, est bien écrit — mais il est signalé sans détour.
param(
    [string]$Destination = '',
    [string]$Copie = '',
    [int]$RetentionJours = 30,
    [string]$PgBin = ''
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\env.ps1"

if ([string]::IsNullOrWhiteSpace($Destination)) {
    $Destination = Join-Path $DSI360_RACINE 'data\backups'   # /data est gitignore
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null

# Localiser pg_dump : parametre explicite, sinon PATH, sinon installation standard PostgreSQL.
if ($PgBin) {
    $pgDump = Join-Path $PgBin 'pg_dump.exe'
} else {
    $cmd = Get-Command pg_dump.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $pgDump = $cmd.Source
    } else {
        $pgDump = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\pg_dump.exe' -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | Select-Object -First 1 -Expand FullName
    }
}
if (-not $pgDump -or -not (Test-Path $pgDump)) {
    throw "pg_dump introuvable. Precisez -PgBin 'C:\Program Files\PostgreSQL\17\bin'."
}

# Extraire hote/port/user/mdp/base du DSN asyncpg (postgresql+asyncpg://user:pass@hote:port/base).
$dsn = $env:DSI360_DATABASE_URL
if ([string]::IsNullOrWhiteSpace($dsn)) { throw "DSI360_DATABASE_URL absent de infra\local\.env." }
$u = [uri]($dsn -replace '\+asyncpg', '')
$infos = $u.UserInfo.Split(':', 2)
$utilisateur = [uri]::UnescapeDataString($infos[0])
$motDePasse = if ($infos.Count -gt 1) { [uri]::UnescapeDataString($infos[1]) } else { '' }
$base = $u.AbsolutePath.TrimStart('/')
$portDb = if ($u.Port -gt 0) { $u.Port } else { 5432 }

$horodatage = Get-Date -Format 'yyyyMMdd_HHmmss'
$fichier = Join-Path $Destination "dsi360_${base}_$horodatage.dump"

$env:PGPASSWORD = $motDePasse   # transmis a pg_dump sans l'ecrire sur la ligne de commande
try {
    & $pgDump --host $u.Host --port $portDb --username $utilisateur --dbname $base `
        --format=custom --no-owner --no-privileges --file $fichier
    if ($LASTEXITCODE -ne 0) { throw "pg_dump a echoue (code $LASTEXITCODE)." }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

$taille = [math]::Round((Get-Item $fichier).Length / 1MB, 1)
Write-Host "Sauvegarde OK : $fichier ($taille Mo)" -ForegroundColor Green

# Une sauvegarde de taille nulle passerait le controle de pg_dump et ne se decouvrirait qu'au jour
# de la restauration. On le dit tout de suite.
if ((Get-Item $fichier).Length -lt 1024) {
    throw "La sauvegarde fait moins de 1 Ko : elle est vide ou tronquee ($fichier)."
}

# --- Copie hors machine ------------------------------------------------------------------------
$copieFaite = $null
if ($Copie) {
    try {
        if (-not (Test-Path $Copie)) { New-Item -ItemType Directory -Force -Path $Copie | Out-Null }
        $cible = Join-Path $Copie (Split-Path $fichier -Leaf)
        Copy-Item $fichier $cible -Force
        # Verifier la taille a l'arrivee : une copie interrompue sur un partage reseau laisse un
        # fichier plus court, et personne ne s'en apercoit avant d'en avoir besoin.
        $arrivee = (Get-Item $cible).Length
        if ($arrivee -ne (Get-Item $fichier).Length) {
            throw "copie incomplete ($arrivee octets recus)"
        }
        $copieFaite = $cible
        Write-Host "Copie hors machine OK : $cible" -ForegroundColor Green
    } catch {
        # La sauvegarde locale existe : on ne fait pas echouer la tache, mais on ne masque rien.
        Write-Host "ALERTE - copie hors machine impossible : $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "  La sauvegarde locale ($fichier) est valide, mais elle reste sur le meme" -ForegroundColor Yellow
        Write-Host "  disque que la base. Retablissez l'acces a $Copie." -ForegroundColor Yellow
    }
}

# --- Retention ---------------------------------------------------------------------------------
# Purger les sauvegardes plus vieilles que -RetentionJours, ici comme sur la copie.
$limite = (Get-Date).AddDays(-$RetentionJours)
$dossiers = @($Destination)
if ($copieFaite) { $dossiers += $Copie }
foreach ($dossier in $dossiers) {
    $purges = Get-ChildItem $dossier -Filter 'dsi360_*.dump' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $limite }
    foreach ($p in $purges) {
        Remove-Item $p.FullName -Force
        Write-Host "  purge (> $RetentionJours j) : $($p.FullName)" -ForegroundColor DarkGray
    }
}
