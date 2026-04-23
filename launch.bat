@echo off
setlocal enabledelayedexpansion
title FloMind Budget Dashboard

cd /d "%~dp0"

echo.
echo  ============================================================
echo   FloMind Budget Dashboard  -  v1.0
echo   CDG x Data x IA pour PME
echo  ============================================================
echo.

set VENV=.venv
set PY="%VENV%\Scripts\python.exe"
set PIP="%VENV%\Scripts\pip.exe"
set ST="%VENV%\Scripts\streamlit.exe"

:: [1/4] Python
echo  [1/4] Verification Python...
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERREUR] Python introuvable. Installez Python 3.11+ depuis python.org
    echo  Cochez "Add Python to PATH" lors de l installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo         %%v detecte

:: [2/4] Environnement virtuel
echo  [2/4] Environnement virtuel...
if not exist ".venv\Scripts\python.exe" (
    echo         Creation du venv...
    python -m venv .venv
    if errorlevel 1 (
        echo  [ERREUR] Creation du venv echouee.
        pause & exit /b 1
    )
    echo         Venv cree
) else (
    echo         Venv existant
)

:: [3/4] Dependances
echo  [3/4] Dependances...
%PY% -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo         Installation en cours (2-3 min)...
    %PIP% install -r requirements.txt --quiet --disable-pip-version-check
    if errorlevel 1 (
        echo  [ERREUR] Installation echouee.
        pause & exit /b 1
    )
    echo         Dependances OK
) else (
    echo         Dependances OK
)

:: [4/4] Donnees
echo  [4/4] Donnees...
if not exist "data\sample_budget_v2.xlsx" (
    echo         Generation des donnees...
    %PY% generators\generate_sample_v3.py
    if errorlevel 1 (
        echo  [ERREUR] Generation echouee.
        pause & exit /b 1
    )
    echo         Donnees OK
) else (
    echo         Donnees OK
)

:: Port
set PORT=8501
netstat -ano 2>nul | findstr /C:":8501" | findstr /C:"LISTENING" >nul 2>&1
if not errorlevel 1 set PORT=8502

echo.
echo  ============================================================
echo   Lancement sur http://localhost:%PORT%
echo  ============================================================
echo.

:: Lancer Streamlit dans une fenetre separee
echo   Ouverture de Streamlit...
start "FloMind - Streamlit" %ST% run app.py ^
    --server.port=%PORT% ^
    --browser.gatherUsageStats=false ^
    --server.fileWatcherType=none

:: Attendre que Streamlit soit pret (6 secondes)
echo   Demarrage en cours (6 secondes)...
timeout /t 6 /nobreak >nul

:: Ouvrir le navigateur depuis cette fenetre
echo   Ouverture du navigateur...
start http://localhost:%PORT%

echo.
echo  Dashboard ouvert sur http://localhost:%PORT%
echo.
echo  Pour arreter Streamlit : fermez la fenetre "FloMind - Streamlit"
echo  (Cette fenetre peut etre fermee)
echo.
pause >nul
endlocal
