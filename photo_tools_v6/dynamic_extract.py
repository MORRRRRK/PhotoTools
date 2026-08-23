"""dynamic_extract.py - 动态照片提取引擎 (V6)"""

import os
import shutil
from typing import Callable, Dict, List, Optional

JPG_EXTS = {".jpg", ".jpeg"}
VIDEO_EXTS = {".mp4"}
VIDEO_FOLDER_NAME = "动态视频存储"


def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def list_media(directory: str):
    """返回文件夹内的 JPG 与 MP4 文件列表（均已排序）。"""
    jpgs, mp4s = [], []
    try:
        for name in os.listdir(directory):
            full = os.path.join(directory, name)
            if not os.path.isfile(full):
                continue
            ext = _ext(name)
            if ext in JPG_EXTS:
                jpgs.append(full)
            elif ext in VIDEO_EXTS:
                mp4s.append(full)
    except OSError:
        pass
    return sorted(jpgs), sorted(mp4s)


def is_dynamic_folder(directory: str) -> bool:
    """判断文件夹内是否同时存在 JPG 与 MP4（手机动态照片特征）。"""
    jpgs, mp4s = list_media(directory)
    return bool(jpgs and mp4s)


def collect_dynamic_folders(parent: str) -> List[str]:
    """批量收集父目录下所有符合动态照片特征的子文件夹。"""
    folders = []
    try:
        for name in sorted(os.listdir(parent)):
            full = os.path.join(parent, name)
            if os.path.isdir(full) and is_dynamic_folder(full):
                folders.append(full)
    except OSError:
        pass
    return folders


def _make_dest(source: str, dest_dir: str) -> str:
    return os.path.join(dest_dir, os.path.basename(source))


def extract_folder(folder: str, video_dir: str, move: bool = True):
    """提取单个动态照片文件夹中的 JPG 与 MP4。

    返回 (items, counts)，items 为逐文件结果字典，
    counts 为 {"ok": n, "skip": n, "error": n}。
    """
    items = []
    counts = {"ok": 0, "skip": 0, "error": 0}
    jpgs, mp4s = list_media(folder)
    jpg_dest_dir = os.path.dirname(os.path.abspath(folder))

    def process(src, dest, kind, counts, items):
        if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dest)):
            counts["skip"] += 1
            items.append({"kind": kind, "source": src, "dest": dest,
                          "status": "跳过", "message": "目标位置与源文件相同"})
            return
        if os.path.exists(dest):
            counts["skip"] += 1
            items.append({"kind": kind, "source": src, "dest": dest,
                          "status": "跳过", "message": "目标文件已存在"})
            return
        try:
            if move:
                shutil.move(src, dest)
            else:
                shutil.copy2(src, dest)
            counts["ok"] += 1
            items.append({"kind": kind, "source": src, "dest": dest,
                          "status": "成功", "message": ""})
        except Exception as e:
            counts["error"] += 1
            items.append({"kind": kind, "source": src, "dest": dest,
                          "status": "失败", "message": str(e)})

    for src in jpgs:
        process(src, _make_dest(src, jpg_dest_dir), "照片", counts, items)
    for src in mp4s:
        process(src, _make_dest(src, video_dir), "视频", counts, items)
    return items, counts


def extract_dynamic_batch(folders: List[str], video_dir: str, move: bool = True,
                          progress_callback: Optional[Callable] = None) -> dict:
    """批量提取动态照片文件夹，返回汇总结果。"""
    os.makedirs(video_dir, exist_ok=True)
    results = []
    total = len(folders)
    ok = skip = error = 0
    for i, folder in enumerate(folders):
        items, counts = extract_folder(folder, video_dir, move=move)
        results.append({"folder": folder, "items": items})
        ok += counts["ok"]
        skip += counts["skip"]
        error += counts["error"]
        if progress_callback:
            try:
                progress_callback(i + 1, total, folder)
            except Exception:
                pass
    return {
        "results": results,
        "video_dir": video_dir,
        "ok": ok,
        "skip": skip,
        "error": error,
        "folders": total,
    }
