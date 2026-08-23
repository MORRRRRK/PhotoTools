@echo off
cd /d "%~dp0\site"
set "PYEXE=C:\Users\49212\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYEXE%" (
    echo Codex Python runtime not found.
    pause
    exit /b 1
)
"%PYEXE%" -m http.server 8000
pause
