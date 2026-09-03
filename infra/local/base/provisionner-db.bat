@echo off
REM ==========================================================================
REM  DSI 360 - Creation de la base de donnees, en un clic.
REM
REM  1. cree le role applicatif 'dsi360' et la base 'dsi360'  (demande le mot
REM     de passe du superuser postgres -- la saisie reste invisible, c'est normal) ;
REM  2. applique les migrations SQL ;
REM  3. cree les referentiels et le compte administrateur initial.
REM
REM  Rejouable sans risque : ne recree pas ce qui existe deja.
REM  Aucun droit administrateur Windows requis.
REM ==========================================================================
title DSI 360 - Creation de la base

REM --- Localiser psql (PostgreSQL 18 sur ce serveur ; on tente les versions voisines) ---
set "PSQL="
for %%V in (18 17 16) do (
    if not defined PSQL if exist "C:\Program Files\PostgreSQL\%%V\bin\psql.exe" (
        set "PSQL=C:\Program Files\PostgreSQL\%%V\bin\psql.exe"
    )
)
if not defined PSQL (
    echo [ECHEC] psql.exe introuvable sous C:\Program Files\PostgreSQL\.
    echo         Installez le client PostgreSQL ou corrigez le chemin dans ce fichier.
    echo.
    pause
    exit /b 1
)
echo Client PostgreSQL : %PSQL%
echo.

echo === 1/2 - Creation du role et de la base (mot de passe du superuser 'postgres' demande)
"%PSQL%" -U postgres -v ON_ERROR_STOP=1 -f "%~dp0provisionner-db.sql"
if %errorlevel% neq 0 (
    echo.
    echo [ECHEC] La base n'a pas ete creee. Mot de passe 'postgres' errone, ou service arrete.
    echo.
    pause
    exit /b 1
)

echo.
echo === 2/2 - Migrations + referentiels + compte administrateur
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0migrer.ps1"
if %errorlevel% neq 0 (
    echo.
    echo [ECHEC] Les migrations ont echoue. Lisez le message ci-dessus.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Base prete. Redemarrez la tache pour que l'application la voie :
echo        Stop-ScheduledTask -TaskName DSI360 ; Start-ScheduledTask -TaskName DSI360
echo      (PowerShell administrateur)
echo.
pause
