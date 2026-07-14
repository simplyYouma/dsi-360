@echo off
REM ==========================================================================
REM  DSI 360 - Demarrage de l'application (developpement), en un clic.
REM  Lance l'API (port 8011) + le frontend (port 5290) dans cette fenetre, et
REM  ouvre l'application des qu'elle repond. Ctrl+C arrete les deux.
REM
REM  Ce fichier n'est qu'un lanceur : tout le travail est fait par start-dev.ps1.
REM  Il existe parce qu'un .ps1 double-clique s'ouvre dans l'editeur au lieu de
REM  s'executer. Placez un raccourci de ce fichier sur le bureau.
REM
REM  Les arguments sont transmis tels quels :  start-dev.bat -SansOuvrir
REM ==========================================================================
title DSI 360 - Application (dev)

REM PowerShell 7 (pwsh) si disponible : c'est ce que visent les scripts du projet.
REM Sinon 5.1, qui suffit a demarrer : start-dev.ps1 se relance lui-meme sous pwsh.
where pwsh >nul 2>&1
if %errorlevel% equ 0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1" %*
)
set CODE=%errorlevel%

REM Sans ceci, la fenetre ouverte par double-clic se refermerait sur le message
REM d'erreur (venv absent, .env manquant, port deja pris...) sans qu'on le lise.
if %CODE% neq 0 (
    echo.
    echo [ECHEC] L'application ne s'est pas lancee ^(code %CODE%^). Lisez le message ci-dessus.
    echo.
    pause
)
exit /b %CODE%
