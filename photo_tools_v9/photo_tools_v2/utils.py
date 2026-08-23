"""utils.py - 工具函数：文件操作、回收站、配置等"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


RAW_EXTENSIONS = {
    # Canon
    ".cr2", ".cr3", ".crw",
    # Nikon
    ".nef", ".nrw",
    # Sony
    ".arw", ".srf", ".sr2",
    # Fujifilm
    ".raf",
    # Olympus / OM System
    ".orf",
    # Panasonic / Leica
    ".rw2",
    # Pentax
    ".pef", ".ptx",
    # Samsung
    ".srw",
    # Sigma / Foveon
    ".x3f",
    # Hasselblad
    ".3fr", ".fff",
    # Kodak
    ".kdc", ".dcr",
    # Leica
    ".mef", ".mos", ".dng",
    # Minolta
    ".mrw",
    # Phase One
    ".iiq",
    # Epson
    ".erf",
    # Casio
    ".bay",
    # Contax
    ".cin",
    # Ricoh
    ".dc3",
    # DJI / generic
    ".dng",
    # Generic RAW / TIFF
    ".tif", ".tiff",
}

ORPHAN_EXTENSIONS = RAW_EXTENSIONS | {".png", ".tiff", ".bmp"}
PREVIEW_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def send_to_trash(path: str) -> bool:
    """将文件移入回收站。"""
    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return False
        ps_script = f"""
$path = '{abs_path}'
$shell = New-Object -ComObject Shell.Application
$item = $shell.NameSpace(0).ParseName($path)
if ($item) {{ $item.InvokeVerb('delete') }}
"""
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[ERROR] 移入回收站失败: {e}")
        return False


def get_stem(path: str) -> str:
    return Path(path).stem.lower()

def get_extension(path: str) -> str:
    return Path(path).suffix.lower()

def group_files_by_stem(files: List[str]) -> dict:
    groups = {}
    for f in files:
        stem = get_stem(f)
        groups.setdefault(stem, []).append(f)
    return groups

def find_jpg_orphans(folder: str) -> List[dict]:
    """扫描文件夹，找出 JPG 已删除但 RAW/PNG 残留的孤儿文件。"""
    orphans = []
    jpg_stems = set()
    candidates = []

    for root, dirs, files in os.walk(folder):
        for f in files:
            ext = get_extension(f)
            stem = get_stem(f)
            rel = os.path.relpath(os.path.join(root, f), folder)
            if ext in {".jpg", ".jpeg"}:
                jpg_stems.add(stem)
            elif ext in ORPHAN_EXTENSIONS:
                candidates.append((stem, os.path.join(root, f), ext, rel))

    for stem, fullpath, ext, rel in candidates:
        if stem not in jpg_stems:
            st = os.stat(fullpath)
            orphans.append({
                "path": fullpath,
                "ext": ext,
                "size_bytes": st.st_size,
                "modified": st.st_mtime,
                "relative_path": rel,
            })
    return orphans


def format_size(bytes_val: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def open_file_in_explorer(path: str) -> bool:
    """在资源管理器中选中该文件（所有格式皆可）。"""
    try:
        abs_path = os.path.abspath(path)
        if sys.platform == "win32":
            # 直接用 explorer /select 打开所在文件夹并选中文件
            # 这种方式支持所有文件格式，包括无默认打开程序的 RAW
            subprocess.run(["explorer", "/select,", abs_path], check=False)
            return True
        else:
            subprocess.run(["xdg-open", os.path.dirname(abs_path)], check=False)
            return True
    except Exception as e:
        print(f"[ERROR] 打开文件失败: {e}")
        return False


def format_datetime(timestamp: float) -> str:
    """时间戳 → 可读时间字符串。"""
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
