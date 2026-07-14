# Crée ou promeut un compte administrateur, mot de passe défini directement (sans e-mail).
# Utile au premier accès, ou tant que le relais SMTP n'est pas branché (pas de lien d'activation).
#
#   infra\local\promouvoir-admin.ps1 -Email prenom.nom@afgbank.ml
#
# Le mot de passe est demandé sans écho si -MotDePasse n'est pas fourni.
param(
    [Parameter(Mandatory = $true)][string]$Email,
    [string]$MotDePasse
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"

$env:PYTHONIOENCODING = 'utf-8'
$arguments = @('-m', 'dsi360.infrastructure.db.promouvoir_admin', '--email', $Email)
if ($MotDePasse) { $arguments += @('--mot-de-passe', $MotDePasse) }
& $DSI360_PY @arguments
exit $LASTEXITCODE
