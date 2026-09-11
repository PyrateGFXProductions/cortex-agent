@echo off
REM Smart LLM Stack Installer - Windows wrapper

set SCRIPT_DIR=%~dp0
set PYTHON_SCRIPT=%SCRIPT_DIR%smart_installer\smart_install.py

REM Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found. Please install Python 3.10+ from https://python.org
    exit /b 1
)

REM Run installer
python "%PYTHON_SCRIPT%" %*