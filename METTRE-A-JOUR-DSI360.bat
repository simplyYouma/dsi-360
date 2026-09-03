@echo off
REM ===========================================================================
REM  DSI 360 - Mise a jour du serveur (double-cliquez sur ce fichier)
REM ---------------------------------------------------------------------------
REM  Ce fichier ne contient volontairement aucune logique : il prepare une
REM  console correcte, s'assure des droits administrateur, puis delegue a
REM  infra\local\exploitation\maj-prod.ps1.
REM
REM  Il vit a la RACINE du depot, et non au fond de infra\local : on ne doit
REM  pas avoir a connaitre l'arborescence pour mettre le serveur a jour.
REM
REM  Les droits administrateur sont necessaires pour arreter et relancer la
REM  tache planifiee qui porte le service. Sans eux, la mise a jour irait
REM  jusqu'au bout puis echouerait sur la derniere etape - le pire moment.
REM
REM  Arguments transmis tels quels :  METTRE-A-JOUR-DSI360.bat -SansRedemarrage
REM ===========================================================================

setlocal
chcp 65001 >nul 2>&1
title DSI 360 - Mise a jour du serveur
cd /d "%~dp0"

net session >nul 2>&1
if not "%ERRORLEVEL%"=="0" (
    echo.
    echo   [ECHEC] Droits administrateur requis.
    echo.
    echo   Faites un clic droit sur ce fichier, puis
    echo   "Executer en tant qu'administrateur".
    echo.
    pause
    exit /b 1
)

set "PS_EXE="
where pwsh.exe >nul 2>&1 && set "PS_EXE=pwsh.exe"
if not defined PS_EXE (
    where powershell.exe >nul 2>&1 && set "PS_EXE=powershell.exe"
)

if not defined PS_EXE (
    echo.
    echo   [ECHEC] PowerShell est introuvable sur ce serveur.
    echo.
    pause
    exit /b 1
)

"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0infra\local\exploitation\maj-prod.ps1" %*
set "CODE=%ERRORLEVEL%"

echo.
if "%CODE%"=="0" (
    echo   Mise a jour terminee.
) else (
    echo   La mise a jour s'est arretee avec le code %CODE%.
    echo   Le detail est dans infra\local\logs\.
)
echo   Appuyez sur une touche pour fermer cette fenetre...
pause >nul

endlocal
exit /b %CODE%
