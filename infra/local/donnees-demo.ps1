# Recrée un jeu de données de démonstration réaliste — DÉVELOPPEMENT UNIQUEMENT.
# Remet à zéro les activités/tâches/documents/commentaires + utilisateurs de démo, puis régénère.
# Refuse de tourner hors environnement 'dev'. Le compte admin et les référentiels ne sont pas touchés.
. "$PSScriptRoot\env.ps1"
Write-Host "==> Génération des données de démonstration (dev)…" -ForegroundColor Cyan
& $DSI360_PY -m dsi360.infrastructure.db.donnees_demo
