@echo off
cd /d "%~dp0"
set "PYEXE=C:\Users\49212\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYEXE%" (
    echo PhotoTools Python runtime not found.
    pause
    exit /b 1
)
"%PYEXE%" run.py
