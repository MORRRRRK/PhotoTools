import logging
logger = logging.getLogger(__name__)

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
CREATE_NO_WINDOW = 0x08000000


def send_to_trash(path: str) -> bool:
    """将文件移入系统回收站（跨平台）。"""
    from .platform_utils import send_to_trash as _trash
    return _trash(path)


def send_to_trash_many(paths: List[str]):
    """批量移入回收站，返回 (成功列表, 失败列表)。"""
    from .platform_utils import send_to_trash_many as _trash_many
    return _trash_many(paths)


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
    """扫描文件夹，按目录分组找出 JPG 已删除但 RAW/PNG 残留的孤儿文件。"""
    orphans = []
    for root, _dirs, files in os.walk(folder):
        jpg_stems = set()
        candidates = []
        for f in files:
            ext = get_extension(f)
            stem = get_stem(f)
            if ext in {".jpg", ".jpeg"}:
                jpg_stems.add(stem)
            elif ext in ORPHAN_EXTENSIONS:
                rel = os.path.relpath(os.path.join(root, f), folder)
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
    """用系统默认程序打开文件（跨平台）。"""
    from .platform_utils import open_path
    return open_path(path)


def reveal_in_file_manager(path: str) -> bool:
    """在系统文件管理器中定位文件（跨平台）。"""
    from .platform_utils import reveal_in_file_manager as _reveal
    return _reveal(path)


def format_datetime(timestamp: float) -> str:
    """时间戳 → 可读时间字符串。"""
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
