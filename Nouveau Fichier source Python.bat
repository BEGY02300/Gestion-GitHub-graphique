@echo off
setlocal
cd /d "%~dp0"
title GitHub Desk - demarrage

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
            "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" -m venv .venv
        ) else (
            where python >nul 2>nul
            if errorlevel 1 (
                echo Python est introuvable. Installe Python 3 depuis python.org puis relance.
                pause
                exit /b 1
            )
            python -m venv .venv
        )
    )
    if errorlevel 1 (
        echo Impossible de preparer l'environnement Python.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import pip" >nul 2>nul
if errorlevel 1 (
    echo Preparation de pip dans l'environnement Python...
    ".venv\Scripts\python.exe" -m ensurepip --upgrade
    if errorlevel 1 (
        echo Impossible d'initialiser pip avec ensurepip.
        echo Verifie que ton installation Python inclut le module ensurepip.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import webview" >nul 2>nul
if errorlevel 1 (
    echo Installation des composants de l'application...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo Installation impossible. Verifie ta connexion Internet et relance.
        pause
        exit /b 1
    )
)

where gh >nul 2>nul
if errorlevel 1 (
    where winget >nul 2>nul
    if not errorlevel 1 (
        echo Installation de GitHub CLI...
        winget install --id GitHub.cli --exact --silent --accept-source-agreements --accept-package-agreements
    ) else (
        where choco >nul 2>nul
        if not errorlevel 1 (
            echo Installation de GitHub CLI...
            choco install gh -y --no-progress
        )
    )
)

where git >nul 2>nul
if errorlevel 1 (
    where winget >nul 2>nul
    if not errorlevel 1 (
        echo Installation de Git...
        winget install --id Git.Git --exact --silent --accept-source-agreements --accept-package-agreements
    ) else (
        where choco >nul 2>nul
        if not errorlevel 1 (
            echo Installation de Git...
            choco install git -y --no-progress
        )
    )
)

if exist "%LOCALAPPDATA%\Programs\GitHub CLI\gh.exe" set "PATH=%LOCALAPPDATA%\Programs\GitHub CLI;%PATH%"
if exist "%ProgramFiles%\GitHub CLI\gh.exe" set "PATH=%ProgramFiles%\GitHub CLI;%PATH%"
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\gh.exe" set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
if exist "%ProgramData%\chocolatey\bin\gh.exe" set "PATH=%ProgramData%\chocolatey\bin;%PATH%"
if exist "%ProgramFiles%\Git\cmd\git.exe" set "PATH=%ProgramFiles%\Git\cmd;%PATH%"
if exist "%ProgramData%\chocolatey\bin\git.exe" set "PATH=%ProgramData%\chocolatey\bin;%PATH%"

if not exist ".venv\Scripts\pythonw.exe" (
    ".venv\Scripts\python.exe" "1.py"
    exit /b %errorlevel%
)
start "" ".venv\Scripts\pythonw.exe" "1.py"
exit /b 0
