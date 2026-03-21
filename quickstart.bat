@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
title JLTSQL Setup

REM Move to batch file directory
cd /d "%~dp0"

echo ============================================================
echo   JLTSQL Quickstart
echo ============================================================
echo.

REM Store exit code for later
set SCRIPT_EXIT_CODE=0
set "VENV_DIR=%~dp0venv32"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

REM ============================================================
REM   Step 1: Determine Python interpreter
REM ============================================================

REM First try: explicit PYTHON environment variable
if defined PYTHON (
    echo Using PYTHON environment variable: %PYTHON%
    set "PYTHON_CMD=%PYTHON%"
    goto :check_venv
)

REM Check if venv32 already exists with a valid Python
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" --version >nul 2>&1
    if !errorlevel!==0 (
        echo Using: venv32 Python
        set "PYTHON_CMD=%VENV_PYTHON%"
        goto :ensure_deps
    )
)

REM Detect system Python (32-bit preferred)
set "PYTHON_CMD="

py -3.12-32 --version >nul 2>&1
if !errorlevel!==0 (
    echo Detected: Python 3.12 ^(32-bit^)
    set "PYTHON_CMD=py -3.12-32"
    goto :check_venv
)

py -32 --version >nul 2>&1
if !errorlevel!==0 (
    echo Detected: Python ^(32-bit^)
    set "PYTHON_CMD=py -32"
    goto :check_venv
)

py --version >nul 2>&1
if !errorlevel!==0 (
    echo Detected: Python ^(py launcher^)
    echo [WARNING] 64-bit Python may not support NAR/UmaConn
    set "PYTHON_CMD=py"
    goto :check_venv
)

python --version >nul 2>&1
if !errorlevel!==0 (
    echo Detected: Python ^(PATH^)
    echo [WARNING] 64-bit Python may not support NAR/UmaConn
    set "PYTHON_CMD=python"
    goto :check_venv
)

REM No Python found
echo ERROR: Python not found
echo Please install Python 3.12 (32-bit) for full NAR/UmaConn support
echo Download: https://www.python.org/downloads/
pause
exit /b 1

REM ============================================================
REM   Step 2: Create venv if needed
REM ============================================================
:check_venv
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" --version >nul 2>&1
    if !errorlevel!==0 (
        set "PYTHON_CMD=%VENV_PYTHON%"
        goto :ensure_deps
    )
)

echo.
echo Creating virtual environment...
%PYTHON_CMD% -m venv "%VENV_DIR%"
if !errorlevel! neq 0 (
    echo [WARNING] Could not create venv, using system Python directly
    goto :run_script
)
echo [OK] Virtual environment created
set "PYTHON_CMD=%VENV_PYTHON%"

REM ============================================================
REM   Step 3: Ensure dependencies are installed
REM ============================================================
:ensure_deps
"%PYTHON_CMD%" -c "import tenacity, yaml, click, rich, structlog" >nul 2>&1
if !errorlevel!==0 (
    goto :run_script
)

echo.
echo Installing dependencies...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
"%VENV_DIR%\Scripts\pip.exe" install -e . >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARNING] pip install -e . failed, trying pip install directly...
    "%VENV_DIR%\Scripts\pip.exe" install pyyaml python-dateutil click rich structlog tenacity pywin32 >nul 2>&1
)
echo [OK] Dependencies installed

REM ============================================================
REM   Run quickstart script
REM ============================================================
:run_script
echo.
for /f "tokens=*" %%v in ('"%PYTHON_CMD%" --version 2^>^&1') do echo Using: %%v
echo.

"%PYTHON_CMD%" scripts/quickstart.py %*
set SCRIPT_EXIT_CODE=!errorlevel!

echo.
if !SCRIPT_EXIT_CODE! neq 0 (
    echo ============================================================
    echo   Setup Failed (Exit Code: !SCRIPT_EXIT_CODE!)
    echo ============================================================
    echo.
    echo   Please check the error messages above.
    echo   Common issues:
    echo     - Missing config/config.yaml
    echo     - Invalid service key
    echo     - No data available for the specified date range
    echo.
    echo   Press Enter to close...
    set /p dummy=
    endlocal & exit /b 1
)

echo ============================================================
echo   Setup Complete
echo ============================================================
echo.
echo   Database file: data\keiba.db (SQLite)
echo.
echo   To view data:
echo     - Use DB Browser for SQLite
echo     - Python: sqlite3.connect('data/keiba.db')
echo.
echo   CLI commands:
echo     jltsql status   - Check database status
echo     jltsql fetch    - Fetch additional data
echo     jltsql --help   - Other commands
echo.
echo   For Claude Code / Claude Desktop users:
echo     Install MCP Server to access DB directly from AI
echo     https://github.com/miyamamoto/jvlink-mcp-server
echo.
echo   Press Enter to close...
set /p dummy=
endlocal
exit /b 0
