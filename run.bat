@echo off
cd /d "%~dp0"
set "PYEXE="
if exist "%~dp0.venv\Scripts\python.exe" set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not defined PYEXE if exist "C:\Users\49212\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set "PYEXE=C:\Users\49212\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not defined PYEXE set "PYEXE=python"
"%PYEXE%" "%~dp0run.py"
if errorlevel 1 pause
