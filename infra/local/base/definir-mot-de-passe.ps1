# Définit le mot de passe d'un compte — DÉVELOPPEMENT SEULEMENT.
#
# Régénérer le jeu de démonstration (`donnees-demo.ps1`) supprime et recrée les comptes de démo :
# leurs mots de passe repartent à la valeur du script, et l'on se retrouve devant un 401 sans
# comprendre pourquoi. Ce script remet la main dessus sans passer par la base à la main.
#
#   infra\local\base\definir-mot-de-passe.ps1 -Email mady-mariam.wague@afgbank.ml
#   infra\local\base\definir-mot-de-passe.ps1 -Email … -MotDePasse 'MonMotDePasse1!'
#
# REFUSE de tourner hors développement. En production, un mot de passe ne se pose pas depuis un
# script : l'agent le définit lui-même par le lien d'activation reçu par e-mail (ADR-0004). Contourner
# cela ferait de ce fichier une porte dérobée — et le journal d'audit ne saurait même pas le dire.
#
# ATTENTION, encodage : UTF-8 **avec BOM** obligatoire (cf. lib/DSI360.Common.ps1).
param(
    [Parameter(Mandatory = $true)][string] $Email,
    [string] $MotDePasse = ''
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\env.ps1"

if ($env:DSI360_ENVIRONNEMENT -notin @('dev', 'test')) {
    Write-Host ''
    Write-Host "  Refus : environnement « $($env:DSI360_ENVIRONNEMENT) »." -ForegroundColor Red
    Write-Host '  Ce script ne sert qu''au developpement. En production, l''agent definit son mot' -ForegroundColor Yellow
    Write-Host '  de passe par le lien d''activation recu par e-mail (ADR-0004).' -ForegroundColor Yellow
    Write-Host ''
    exit 1
}

if ($MotDePasse -eq '') {
    # Saisie masquée : un mot de passe n'a pas à rester dans l'historique du terminal.
    $secret = Read-Host -AsSecureString "Nouveau mot de passe pour $Email"
    $MotDePasse = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    )
}
if ($MotDePasse.Length -lt 8) {
    Write-Host '  Refus : huit caracteres au minimum.' -ForegroundColor Red
    exit 1
}

$env:DSI360_EMAIL_CIBLE = $Email
$env:DSI360_MDP_CIBLE = $MotDePasse
$env:PYTHONPATH = Join-Path $DSI360_RACINE 'backend\src'

$script = @'
import asyncio, os, sys
from sqlalchemy import text
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.securite import hacher_mot_de_passe

async def main() -> None:
    email = os.environ["DSI360_EMAIL_CIBLE"]
    async for s in session_scope():
        n = await s.execute(
            text(
                "UPDATE core.utilisateur SET mot_de_passe_hash = :h, doit_changer_mdp = false, "
                # On lève aussi le frein anti-force-brute : sinon le compte reste bloqué malgré
                # le nouveau mot de passe, et l'on croirait que le script n'a rien fait.
                "    echecs_connexion = 0, verrouille_jusqu_a = NULL "
                "WHERE lower(email) = lower(:e)"
            ),
            {"h": hacher_mot_de_passe(os.environ["DSI360_MDP_CIBLE"]), "e": email},
        )
        await s.commit()
        if n.rowcount == 0:
            print(f"Aucun compte pour {email}.")
            sys.exit(1)
        print(f"Mot de passe defini pour {email}.")
        break

asyncio.run(main())
'@

try {
    & $DSI360_PY -c $script
    $code = $LASTEXITCODE
} finally {
    Remove-Item Env:DSI360_MDP_CIBLE -ErrorAction SilentlyContinue
    Remove-Item Env:DSI360_EMAIL_CIBLE -ErrorAction SilentlyContinue
}
exit $code
