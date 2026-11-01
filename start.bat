@echo off
setlocal
title Companion

REM Always run from the directory containing this launcher.
cd /d "%~dp0"

echo.
echo ========================================
echo          Companion Launcher
echo ========================================
echo.

REM Prefer the repository-local virtual environment.
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if exist "%VENV_PY%" (
    echo Using project virtual environment...
) else (
    echo Project virtual environment not found.
    echo Looking for Python 3...

    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 --version >nul 2>&1
        if not errorlevel 1 (
            py -3 -m venv "%~dp0.venv"
        )
    ) else (
        where python >nul 2>&1
        if not errorlevel 1 (
            python -m venv "%~dp0.venv"
        ) else (
            echo ERROR: Python 3 was not found.
            echo Install Python 3 and enable the "Add Python to PATH" option.
            pause
            exit /b 1
        )
    )

    if errorlevel 1 (
        echo ERROR: Could not create the project virtual environment.
        pause
        exit /b 1
    )
)

if not exist "%VENV_PY%" (
    echo ERROR: The virtual environment's Python executable was not created.
    pause
    exit /b 1
)

REM Install requirements on first launch, or if an import is missing.
"%VENV_PY%" -c "import openai, dotenv, PIL" >nul 2>&1
if errorlevel 1 (
    echo Installing project dependencies...
    "%VENV_PY%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo ERROR: Dependency installation failed.
        pause
        exit /b 1
    )
)

REM Companion reads OPENROUTER_API_KEY from .env or the process environment.
if not exist "%~dp0.env" (
    echo WARNING: No .env file was found.
    echo Copy .env.example to .env and add your OPENROUTER_API_KEY.
    echo.
)

echo Starting Companion...
echo Close the Companion window to shut it down.
echo.

"%VENV_PY%" "%~dp0companion.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Companion exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
