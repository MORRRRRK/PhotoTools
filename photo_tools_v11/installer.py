import logging
logger = logging.getLogger(__name__)

"""installer.py - 安装状态识别与安装/卸载器定位 (V11.0)"""

import os
import sys
import winreg
from pathlib import Path

APP_NAME = "PhotoTools"
APP_VERSION = "11.0.0"
EXE_NAME = "PhotoTools.exe"
UNINSTALL_EXE = "PhotoToolsUninstall.exe"
SETUP_EXE = "PhotoToolsSetup.exe"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PhotoTools"
MARKER_KEY = r"Software\PhotoTools"


def get_install_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Programs", APP_NAME)


def get_install_path() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MARKER_KEY) as key:
            return winreg.QueryValueEx(key, "InstallPath")[0] or ""
    except Exception as _exc:
        return ""


def is_installed() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY):
            return True
    except OSError:
        pass
    return os.path.exists(os.path.join(get_install_path() or get_install_dir(), EXE_NAME))


def _dist_file(name: str) -> str:
    p = Path(__file__).resolve().parent / "dist" / name
    return str(p) if p.exists() else ""


def current_exe() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return _dist_file(EXE_NAME)


def get_uninstaller_exe() -> str:
    install = get_install_path()
    if install:
        p = os.path.join(install, UNINSTALL_EXE)
        if os.path.exists(p):
            return p
    if getattr(sys, "frozen", False):
        p = os.path.join(os.path.dirname(sys.executable), UNINSTALL_EXE)
        if os.path.exists(p):
            return p
    return _dist_file(UNINSTALL_EXE)


def get_setup_exe() -> str:
    return _dist_file(SETUP_EXE)


def detect_first_install() -> bool:
    return not is_installed()
