@echo off
REM ===========================================================================
REM  DSI 360 - Arret de l'environnement de developpement (double-cliquez)
REM ---------------------------------------------------------------------------
REM  Ce fichier ne contient volontairement aucune logique : il prepare une
REM  console correcte puis delegue a infra\local\exploitation\arreter-dev.ps1.
REM
REM  Ce qu'il traite, propre a Windows :
REM   - la console demarre en page de code 850 : les accents seraient illisibles ;
REM   - un double-clic depuis l'Explorateur place parfois le repertoire courant
REM     sur C:\Windows\System32 : on force celui du script ;
REM   - la strategie d'execution bloque les .ps1 : on la contourne pour cette
REM     invocation seulement, sans toucher a la configuration du poste ;
REM   - la fenetre ne doit jamais se refermer sur une erreur sans etre lue.
REM
REM  Les arguments sont transmis tels quels :  ARRETER-DSI360.bat
REM ===========================================================================

setlocal
chcp 65001 >nul 2>&1
title DSI 360 - Arret du developpement
cd /d "%~dp0"

REM PowerShell 7 si disponible (c'est ce que visent les scripts du projet),
REM sinon Windows PowerShell 5.1 : arreter-dev.ps1 se relance lui-meme sous pwsh.
set "PS_EXE="
where pwsh.exe >nul 2>&1 && set "PS_EXE=pwsh.exe"
if not defined PS_EXE (
    where powershell.exe >nul 2>&1 && set "PS_EXE=powershell.exe"
)

if not defined PS_EXE (
    echo.
    echo   [ECHEC] PowerShell est introuvable sur ce poste.
    echo   DSI 360 ne peut pas etre arrete sans PowerShell.
    echo.
    pause
    exit /b 1
)

"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0infra\local\exploitation\arreter-dev.ps1" %*
set "CODE=%ERRORLEVEL%"

if not "%CODE%"=="0" (
    echo.
    echo   L'arret s'est termine avec le code %CODE%.
    echo   Le detail est dans infra\local\logs\.
    echo.
    echo   Appuyez sur une touche pour fermer cette fenetre...
    pause >nul
)

endlocal
exit /b %CODE%
