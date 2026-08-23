@echo off
cd /d "%~dp0"
set "PYEXE=C:\Users\49212\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYEXE%" (
    echo Codex Python runtime not found.
    echo Please install Python 3.10+ and Pillow, then run: python build_gallery.py
    pause
    exit /b 1
)
"%PYEXE%" build_gallery.py %*
pause
