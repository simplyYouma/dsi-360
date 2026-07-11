@echo off
REM ==========================================================================
REM  DSI 360 - Mise a jour du serveur en un clic.
REM  Recupere le code, installe, migre, reconstruit le front, redemarre la tache,
REM  puis controle la sante. S'eleve en administrateur (redemarrage de la tache
REM  SYSTEM). Placez un raccourci de ce fichier sur le bureau du serveur.
REM ==========================================================================
title DSI 360 - Mise a jour

REM --- Elevation administrateur si necessaire ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Demande des privileges administrateur...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0maj-serveur.ps1"
set CODE=%errorlevel%
echo.
if %CODE% neq 0 (
    echo [ECHEC] La mise a jour s'est arretee. Lisez le message ci-dessus.
) else (
    echo [OK] Mise a jour terminee.
)
echo.
pause
