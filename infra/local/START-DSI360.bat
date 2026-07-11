@echo off
REM ==========================================================================
REM  DSI 360 - Demarrer le service (tache planifiee "DSI360").
REM  S'eleve en administrateur. Double-cliquable depuis le bureau du serveur.
REM ==========================================================================
title DSI 360 - Demarrage

net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

schtasks /Run /TN "DSI360"
echo.
echo Service DSI 360 demarre (tache DSI360).
echo.
pause
