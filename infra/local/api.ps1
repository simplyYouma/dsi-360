# Lance l'API FastAPI (uvicorn) en local, avec rechargement à chaud.
# Écoute sur 127.0.0.1:8011 — le serveur Vite y proxifie /api (cf. vite.config.ts).
. "$PSScriptRoot\env.ps1"
& $DSI360_PY -m uvicorn dsi360.interface.app:app --host 127.0.0.1 --port 8011 --reload
