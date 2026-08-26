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
    """将文件移入回收站。"""
    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return False
        escaped = abs_path.replace("'", "''")
        method = "DeleteDirectory" if os.path.isdir(abs_path) else "DeleteFile"
        ps_script = (
            "Add-Type -AssemblyName Microsoft.VisualBasic; "
            f"[Microsoft.VisualBasic.FileIO.FileSystem]::{method}"
            f"('{escaped}','OnlyErrorDialogs','SendToRecycleBin')"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
            capture_output=True, text=True, timeout=30,
            creationflags=CREATE_NO_WINDOW
        )
        return result.returncode == 0 and not os.path.exists(abs_path)
    except Exception as e:
        print(f"[ERROR] 移入回收站失败: {e}")
        return False


def send_to_trash_many(paths: List[str]):
    """批量把文件移入回收站，返回 (成功列表, 失败列表)。"""
    ok_paths: List[str] = []
    failed_paths: List[str] = []

    def run_chunk(chunk):
        try:
            lines = ["Add-Type -AssemblyName Microsoft.VisualBasic"]
            for p in chunk:
                escaped = p.replace("'", "''")
                lines.append(
                    f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile"
                    f"('{escaped}','OnlyErrorDialogs','SendToRecycleBin')"
                )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", "; ".join(lines)],
                capture_output=True, text=True, timeout=180,
                creationflags=CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception as _exc:
            return False

    for i in range(0, len(paths), 40):
        chunk = paths[i:i + 40]
        if run_chunk(chunk):
            ok_paths.extend(chunk)
        else:
            for p in chunk:
                if send_to_trash(p):
                    ok_paths.append(p)
                else:
                    failed_paths.append(p)
    return ok_paths, failed_paths


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
    """在资源管理器中选中该文件（预览）。"""
    try:
        abs_path = os.path.abspath(path)
        if sys.platform == "win32":
            os.startfile(abs_path)
            return True
        else:
            subprocess.run(["xdg-open", abs_path], check=False)
            return True
    except Exception as e:
        print(f"[ERROR] 打开文件失败: {e}")
        return False


def format_datetime(timestamp: float) -> str:
    """时间戳 → 可读时间字符串。"""
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
