# Sauvegarde native de la base DSI 360 (pg_dump, format custom -Fc, compressé et restaurable).
# Aucune dépendance Docker. À planifier (tâche « DSI360-Sauvegarde ») sur le serveur.
#
#   infra\local\sauvegarde-db.ps1
#   infra\local\sauvegarde-db.ps1 -Destination C:\MY_APPS\logs\DSI360\backups -RetentionJours 30
#
# La cible (-Destination) doit être HORS git et, idéalement, sur un volume sauvegardé/chiffré.
param(
    [string]$Destination = '',
    [int]$RetentionJours = 30,
    [string]$PgBin = ''
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"

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

# Retention : purger les sauvegardes plus vieilles que -RetentionJours.
$limite = (Get-Date).AddDays(-$RetentionJours)
$purges = Get-ChildItem $Destination -Filter 'dsi360_*.dump' |
    Where-Object { $_.LastWriteTime -lt $limite }
foreach ($p in $purges) {
    Remove-Item $p.FullName -Force
    Write-Host "  purge (> $RetentionJours j) : $($p.Name)" -ForegroundColor DarkGray
}
