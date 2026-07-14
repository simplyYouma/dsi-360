#!/usr/bin/env bash
# Demarre l'API DSI 360 en PRODUCTION : un seul processus sert l'API + la SPA compilee.
# Lanceur de reference du serveur : c'est lui que lance la tache planifiee DSI360 (via Git Bash),
# au demarrage de Windows. Remplace l'ancien start-prod.ps1.
#
# Conforme au standard serveur AFG (docs/06-DEPLOIEMENT) :
#   - TLS termine par l'app (uvicorn --ssl-*), acces par IP:port, sans reverse-proxy obligatoire ;
#   - banniere serveur masquee (--no-server-header) : pas de « server: uvicorn » ;
#   - PAS de --reload, PAS de --workers : l'ordonnanceur SLA/notifications tourne EN PROCESSUS ;
#     plusieurs workers = plusieurs ordonnanceurs = notifications en double. Un seul process.
#
# Prerequis : build du frontend (front-build.ps1) et infra/local/.env renseigne
# (DSI360_ENVIRONNEMENT=recette|prod pour activer HSTS, DSI360_JWT_SECRET_KEY fort).
#
#   infra/local/start-prod.sh --port 8453 --cert /c/MY_APPS/dsi-360/cert/cert.pem \
#                             --key /c/MY_APPS/dsi-360/cert/key.pem
#
# Sans --cert : demarre en HTTP (a reserver au cas « derriere un reverse-proxy qui fait le TLS »).
#
# ENCODAGE : fins de ligne LF obligatoires. Un CRLF ferait echouer le shebang (« bad interpreter »).
set -euo pipefail

port=8453
ecouter='0.0.0.0'
certificat=''
cle_certificat=''

while [ $# -gt 0 ]; do
    case "$1" in
        --port)   port="$2";           shift 2 ;;
        --host)   ecouter="$2";        shift 2 ;;
        --cert)   certificat="$2";     shift 2 ;;
        --key)    cle_certificat="$2"; shift 2 ;;
        *) echo "Argument inconnu : $1" >&2; exit 2 ;;
    esac
done

ici="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
racine="$(cd "$ici/../.." && pwd)"
py="$racine/backend/.venv/Scripts/python.exe"
fichier_env="$ici/.env"

[ -x "$py" ]           || { echo "venv introuvable : $py — cf. infra/local/README.md" >&2; exit 1; }
[ -f "$fichier_env" ]  || { echo "Config absente : $fichier_env — copiez .env.example en .env." >&2; exit 1; }

# --- Configuration : chaque KEY=VALUE du .env devient une variable d'environnement du process.
# On ne « source » pas le fichier : un `source` executerait tout ce qu'il contient, et une valeur
# contenant $(...) ou ` ` deviendrait du code. On lit ligne a ligne. Le \r final est retire : sans
# cela, un .env enregistre sous Windows (CRLF) collerait un retour chariot au bout de chaque valeur
# — le mot de passe de la base ne passerait plus, et l'erreur serait indechiffrable.
while IFS= read -r ligne || [ -n "$ligne" ]; do
    ligne="${ligne%$'\r'}"
    case "$ligne" in ''|'#'*) continue ;; esac
    [ "${ligne#*=}" = "$ligne" ] && continue     # pas de '=' : ligne ignoree
    cle="${ligne%%=*}"
    valeur="${ligne#*=}"
    export "$cle=$valeur"
done < "$fichier_env"

# Chemins passes a Python : ils doivent etre au format Windows (C:/...). Un chemin MSYS (/c/...)
# ne veut rien dire pour python.exe, qui est un binaire Windows natif.
export DSI360_MIGRATIONS_DIR="$(cygpath -m "$racine/db/migrations")"
# L'API doit publier la SPA en prod (le front n'a pas de serveur Vite ici).
export DSI360_SERVIR_FRONTEND=true

dist="$racine/frontend/dist/index.html"
[ -f "$dist" ] || { echo "Build du frontend absent ($dist). Lancez d'abord : infra\\local\\front-build.ps1" >&2; exit 1; }

case "${DSI360_ENVIRONNEMENT:-}" in
    recette|prod) ;;
    *) echo "AVERTISSEMENT : DSI360_ENVIRONNEMENT='${DSI360_ENVIRONNEMENT:-}' — HSTS restera desactive." >&2
       echo "                Mettez 'recette' ou 'prod' dans infra/local/.env pour une vraie mise en ligne." >&2 ;;
esac

# --- Port deja pris ? Un second uvicorn sur le meme port n'echoue pas franchement : il perd la
# course, et c'est le survivant — potentiellement du code perime — qui repond. On refuse plutot.
# Le test se fait en Python (une connexion qui aboutit = quelqu'un ecoute) : `netstat` afficherait
# ses etats dans la langue du systeme, et ce serveur est en francais.
if "$py" -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1', $port))==0 else 1)"; then
    echo "Le port $port est deja en ecoute. Arretez l'instance en cours avant de relancer." >&2
    echo "  Stop-ScheduledTask -TaskName DSI360        (ou liberez le port)" >&2
    exit 1
fi

args=(-m uvicorn dsi360.interface.app:app --host "$ecouter" --port "$port" --no-server-header)

if [ -n "$certificat" ]; then
    # La tache planifiee passe des chemins Windows (C:\...). cygpath -u les ramene au format MSYS
    # attendu par `test -f` ; sur un chemin deja MSYS il ne change rien.
    certificat="$(cygpath -u "$certificat")"
    cle_certificat="$(cygpath -u "$cle_certificat")"
    [ -f "$certificat" ]     || { echo "Certificat introuvable : $certificat" >&2; exit 1; }
    [ -f "$cle_certificat" ] || { echo "Cle du certificat introuvable : $cle_certificat" >&2; exit 1; }
    args+=(--ssl-certfile "$(cygpath -m "$certificat")" --ssl-keyfile "$(cygpath -m "$cle_certificat")")
    echo "TLS direct : https://$ecouter:$port"
else
    echo "AVERTISSEMENT : aucun certificat : demarrage en HTTP." >&2
    echo "                A reserver a un deploiement derriere un reverse-proxy TLS." >&2
fi

echo "Demarrage DSI 360 (prod) sur le port $port…"
cd "$racine"
# `exec` : python REMPLACE ce shell au lieu de tourner dessous. Sans lui, la tache planifiee
# surveillerait le bash et non l'API — et l'arret de la tache pourrait laisser un uvicorn orphelin
# accroche au port 8453.
exec "$py" "${args[@]}"
