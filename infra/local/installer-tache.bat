@echo off
REM ==========================================================================
REM  DSI 360 - Installe le demarrage automatique de l'application avec Windows.
REM  Cree la tache planifiee 'DSI360' (declencheur : demarrage de la machine,
REM  compte SYSTEM), ouvre le port au pare-feu, demarre l'app et controle sa
REM  sante. S'eleve en administrateur tout seul. Rejouable sans risque.
REM
REM  A lancer UNE FOIS, apres le deploiement (docs/06-DEPLOIEMENT, section 3).
REM ==========================================================================
title DSI 360 - Demarrage automatique (tache planifiee)

REM --- Elevation administrateur si necessaire ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Demande des privileges administrateur...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer-tache.ps1" %*
set CODE=%errorlevel%
echo.
if %CODE% neq 0 (
    echo [ECHEC] La tache n'a pas ete installee. Lisez le message ci-dessus.
) else (
    echo [OK] DSI 360 demarrera automatiquement avec Windows.
)
echo.
pause
exit /b %CODE%
