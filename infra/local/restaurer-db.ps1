# Restaure une sauvegarde DSI 360 (produite par sauvegarde-db.ps1) dans la base configurée.
# ATTENTION : écrase les données existantes (pg_restore --clean --if-exists). Demande confirmation.
#
#   infra\local\restaurer-db.ps1 -Fichier C:\MY_APPS\logs\DSI360\backups\dsi360_dsi360_20260711_020000.dump
param(
    [Parameter(Mandatory = $true)][string]$Fichier,
    [string]$PgBin = '',
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"

if (-not (Test-Path $Fichier)) { throw "Sauvegarde introuvable : $Fichier" }

if ($PgBin) {
    $pgRestore = Join-Path $PgBin 'pg_restore.exe'
} else {
    $cmd = Get-Command pg_restore.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $pgRestore = $cmd.Source
    } else {
        $pgRestore = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\pg_restore.exe' -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | Select-Object -First 1 -Expand FullName
    }
}
if (-not $pgRestore -or -not (Test-Path $pgRestore)) {
    throw "pg_restore introuvable. Precisez -PgBin 'C:\Program Files\PostgreSQL\17\bin'."
}

$dsn = $env:DSI360_DATABASE_URL
if ([string]::IsNullOrWhiteSpace($dsn)) { throw "DSI360_DATABASE_URL absent de infra\local\.env." }
$u = [uri]($dsn -replace '\+asyncpg', '')
$infos = $u.UserInfo.Split(':', 2)
$utilisateur = [uri]::UnescapeDataString($infos[0])
$motDePasse = if ($infos.Count -gt 1) { [uri]::UnescapeDataString($infos[1]) } else { '' }
$base = $u.AbsolutePath.TrimStart('/')
$portDb = if ($u.Port -gt 0) { $u.Port } else { 5432 }

if (-not $Force) {
    $rep = Read-Host "Ceci ECRASE la base '$base' avec '$([IO.Path]::GetFileName($Fichier))'. Taper OUI pour continuer"
    if ($rep -ne 'OUI') { Write-Host 'Annule.' -ForegroundColor Yellow; return }
}

$env:PGPASSWORD = $motDePasse
try {
    & $pgRestore --host $u.Host --port $portDb --username $utilisateur --dbname $base `
        --clean --if-exists --no-owner --no-privileges $Fichier
    if ($LASTEXITCODE -ne 0) { throw "pg_restore a echoue (code $LASTEXITCODE)." }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
Write-Host "Restauration OK dans la base '$base'." -ForegroundColor Green
