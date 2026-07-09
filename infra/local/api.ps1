# Lance l'API FastAPI (uvicorn) SEULE, avec rechargement à chaud, sur 127.0.0.1:8011.
# Le serveur Vite y proxifie /api (cf. vite.config.ts).
# Pour démarrer l'API + le frontend d'un coup : infra\local\demarrer-dev.ps1
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"

$port = 8011

# Un second uvicorn sur le même port n'échoue pas franchement : il perd la course, et c'est le
# survivant qui répond — potentiellement du code périmé. On refuse plutôt que de laisser faire.
$occupe = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($occupe) {
    $pids = ($occupe.OwningProcess | Sort-Object -Unique) -join ', '
    throw "Le port $port est deja en ecoute (PID $pids). Une API tourne deja " +
          "(peut-etre via 'npm run dev'). Arretez-la avant de relancer celle-ci."
}

# --reload-dir est indispensable : sans lui uvicorn surveille le repertoire courant
# (souvent infra\local) et ne voit jamais une modification du code de l'API.
& $DSI360_PY -m uvicorn dsi360.interface.app:app --host 127.0.0.1 --port $port `
    --reload --reload-dir (Join-Path $DSI360_RACINE 'backend\src')
