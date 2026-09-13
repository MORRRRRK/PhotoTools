"""platform_utils.py - 跨平台文件、回收站与进程工具 (V13)"""

import os
import shutil
import subprocess
import sys
from typing import List, Tuple

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def subprocess_flags() -> int:
    return CREATE_NO_WINDOW


def open_path(path: str) -> bool:
    """用系统默认程序打开文件或目录。"""
    target = os.path.abspath(path)
    try:
        if sys.platform == "win32":
            os.startfile(target)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
        return True
    except Exception as e:
        print(f"[ERROR] 打开失败: {e}")
        return False


def reveal_in_file_manager(path: str) -> bool:
    """在系统文件管理器中定位该文件。"""
    target = os.path.abspath(path)
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", target])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", target])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(target) or target])
        return True
    except Exception as e:
        print(f"[ERROR] 定位失败: {e}")
        return False


def _trash_windows(path: str) -> bool:
    escaped = path.replace("'", "''")
    method = "DeleteDirectory" if os.path.isdir(path) else "DeleteFile"
    script = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        f"[Microsoft.VisualBasic.FileIO.FileSystem]::{method}"
        f"('{escaped}','OnlyErrorDialogs','SendToRecycleBin')"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        capture_output=True, text=True, timeout=60, creationflags=CREATE_NO_WINDOW)
    return result.returncode == 0 and not os.path.exists(path)


def _trash_macos(path: str) -> bool:
    escaped = path.replace('"', '\\"')
    script = f'tell application "Finder" to delete POSIX file "{escaped}"'
    result = subprocess.run(["osascript", "-e", script],
                            capture_output=True, text=True, timeout=60)
    return result.returncode == 0


def _trash_linux(path: str) -> bool:
    for cmd in (["gio", "trash", path], ["trash-put", path]):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            continue
    return False


def send_to_trash(path: str) -> bool:
    """把文件或目录移入系统回收站。"""
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return False
    try:
        if sys.platform == "win32":
            return _trash_windows(target)
        if sys.platform == "darwin":
            return _trash_macos(target)
        return _trash_linux(target)
    except Exception as e:
        print(f"[ERROR] 移入回收站失败: {e}")
        return False


def send_to_trash_many(paths: List[str]) -> Tuple[List[str], List[str]]:
    ok: List[str] = []
    failed: List[str] = []
    for p in paths:
        (ok if send_to_trash(p) else failed).append(p)
    return ok, failed


def find_ffmpeg() -> str:
    """按平台查找随包 ffmpeg，找不到再回退系统 ffmpeg。"""
    base = os.path.dirname(os.path.abspath(__file__))
    names = ["ffmpeg.exe", "ffmpeg"] if sys.platform == "win32" else ["ffmpeg", "ffmpeg.exe"]
    for name in names:
        for folder in (os.path.join(base, "assets"), base):
            candidate = os.path.join(folder, name)
            if os.path.exists(candidate):
                return candidate
    return shutil.which("ffmpeg") or ""
