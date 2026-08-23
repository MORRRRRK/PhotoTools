"""utils.py - 工具函数：文件操作、回收站、配置等"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2",
    ".dng", ".raf", ".orf", ".rw2", ".pef", ".srw", ".x3f",
    ".3fr", ".kdc", ".dcr", ".mef", ".mos", ".mrw", ".tif",
}

ORPHAN_EXTENSIONS = RAW_EXTENSIONS | {".png", ".tiff", ".bmp"}
PREVIEW_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def send_to_trash(path: str) -> bool:
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
        groups.setdefault(get_stem(f), []).append(f)
    return groups

def find_jpg_orphans(folder: str) -> List[dict]:
    orphans = []
    jpg_stems = set()
    candidates = []
    for root, dirs, files in os.walk(folder):
        for f in files:
            ext = get_extension(f)
            stem = get_stem(f)
            if ext in {".jpg", ".jpeg"}:
                jpg_stems.add(stem)
            elif ext in ORPHAN_EXTENSIONS:
                candidates.append((stem, os.path.join(root, f), ext))
    for stem, fullpath, ext in candidates:
        if stem not in jpg_stems:
            st = os.stat(fullpath)
            orphans.append({
                "path": fullpath, "ext": ext,
                "size_bytes": st.st_size, "modified": st.st_mtime,
            })
    return orphans

def format_size(bytes_val: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"
