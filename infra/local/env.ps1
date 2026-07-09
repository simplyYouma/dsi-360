# Charge la configuration native dans l'environnement du process courant.
# À dot-sourcer :  . .\env.ps1
$ErrorActionPreference = 'Stop'

$racine  = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$envFile = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path $envFile)) {
    throw "Config absente : $envFile — copiez .env.example en .env et renseignez-le."
}

# Injecte chaque KEY=VALUE du .env comme variable d'environnement du process.
foreach ($ligne in Get-Content $envFile) {
    $t = $ligne.Trim()
    if ($t -eq '' -or $t.StartsWith('#')) { continue }
    $i = $t.IndexOf('=')
    if ($i -lt 1) { continue }
    $cle = $t.Substring(0, $i).Trim()
    $val = $t.Substring($i + 1).Trim()
    Set-Item -Path "Env:$cle" -Value $val
}

# Chemins dérivés du dépôt (robustes, indépendants de la machine).
$env:DSI360_MIGRATIONS_DIR = Join-Path $racine 'db\migrations'

$global:DSI360_RACINE = $racine
$global:DSI360_PY     = Join-Path $racine 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $global:DSI360_PY)) {
    throw "venv introuvable : $($global:DSI360_PY) — cf. infra/local/README.md (création du venv)."
}
