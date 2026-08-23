"""installer.py - PhotoTools 本机安装识别、一键安装与一键卸载 (V9)"""

import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

APP_NAME = "PhotoTools"
APP_VERSION = "9.0.0"
PUBLISHER = "PhotoTools"
EXE_NAME = "PhotoTools.exe"
INSTALL_SUBDIR = os.path.join("Programs", APP_NAME)
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PhotoTools"
MARKER_KEY = r"Software\PhotoTools"
CREATE_NO_WINDOW = 0x08000000


def get_install_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, INSTALL_SUBDIR)


def get_cache_root() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def current_exe() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    p = Path(__file__).resolve().parent.parent / "photo_tools_v9" / "dist" / EXE_NAME
    if p.exists():
        return str(p)
    return ""


def is_installed() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY):
            return True
    except OSError:
        pass
    return os.path.exists(os.path.join(get_install_dir(), EXE_NAME))


def _set_marker(install_path: str):
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, MARKER_KEY) as key:
            winreg.SetValueEx(key, "InstallPath", 0, winreg.REG_SZ, install_path)
            winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, APP_VERSION)
    except Exception:
        pass


def _write_uninstall_entry(install_path: str):
    exe = os.path.join(install_path, EXE_NAME)
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ,
                              "PhotoTools 摄影素材管理工具箱")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_path)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, exe)
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                              f'"{exe}" --uninstall')
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    except Exception:
        pass


def _remove_registry():
    for key_path in (UNINSTALL_KEY, MARKER_KEY):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        except OSError:
            pass


def _create_desktop_shortcut(exe: str):
    try:
        folder = os.path.dirname(exe)
        exe_q = exe.replace("'", "''")
        folder_q = folder.replace("'", "''")
        ps = (
            "$ws = New-Object -ComObject WScript.Shell; "
            "$lnk = [Environment]::GetFolderPath('Desktop') + '\\PhotoTools.lnk'; "
            f"$s = $ws.CreateShortcut($lnk); "
            f"$s.TargetPath = '{exe_q}'; "
            f"$s.WorkingDirectory = '{folder_q}'; "
            "$s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        pass


def _remove_desktop_shortcut():
    try:
        ps = (
            "$lnk = [Environment]::GetFolderPath('Desktop') + '\\PhotoTools.lnk'; "
            "if (Test-Path $lnk) { Remove-Item $lnk -Force }"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        pass


def clean_cache_root():
    root = get_cache_root()
    try:
        if os.path.isdir(root):
            shutil.rmtree(root, ignore_errors=True)
    except Exception:
        pass


def detect_first_install() -> bool:
    """本机没有安装记录时，清空旧缓存并写入安装标记，返回 True。"""
    if is_installed():
        return False
    clean_cache_root()
    _set_marker(get_install_dir())
    return True


def install_app(dest_dir: str = None, create_shortcut: bool = True) -> tuple:
    src = current_exe()
    if not src or not os.path.exists(src):
        return False, "找不到可安装的 PhotoTools.exe，请先运行 build.py 打包"
    dest = dest_dir or get_install_dir()
    try:
        os.makedirs(dest, exist_ok=True)
        target = os.path.join(dest, EXE_NAME)
        shutil.copy2(src, target)
        _write_uninstall_entry(dest)
        _set_marker(dest)
        if create_shortcut:
            _create_desktop_shortcut(target)
        return True, dest
    except Exception as e:
        return False, str(e)


def uninstall_app() -> list:
    errors = []
    _remove_registry()
    _remove_desktop_shortcut()
    clean_cache_root()
    install_dir = get_install_dir()
    try:
        if os.path.isdir(install_dir):
            shutil.rmtree(install_dir, ignore_errors=True)
    except Exception as e:
        errors.append(str(e))
    return errors
