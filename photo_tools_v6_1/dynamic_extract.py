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


def _dest_for_src(source: str, folder: str, video_dir: str) -> str:
    if _ext(source) in JPG_EXTS:
        return _make_dest(source, os.path.dirname(os.path.abspath(folder)))
    return _make_dest(source, video_dir)


def _verify_extracted(jpgs_before: List[str], mp4s_before: List[str],
                      folder: str, video_dir: str, source_sizes: Dict[str, int]):
    """校验所有 JPG/MP4 是否已正确生成到目标位置（存在且大小一致）。"""
    missing = []
    for src in jpgs_before + mp4s_before:
        dest = _dest_for_src(src, folder, video_dir)
        dest_ok = os.path.exists(dest)
        if dest_ok and source_sizes.get(os.path.abspath(src), 0) > 0:
            try:
                dest_ok = os.path.getsize(dest) == source_sizes[os.path.abspath(src)]
            except OSError:
                dest_ok = False
        if not dest_ok:
            missing.append(dest)
    return not missing, missing


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
            size = os.path.getsize(src)
            if move:
                shutil.move(src, dest)
            else:
                shutil.copy2(src, dest)
            if not os.path.exists(dest) or (size > 0 and os.path.getsize(dest) != size):
                raise IOError("目标文件缺失或大小校验不一致")
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


def _folder_empty(folder: str) -> bool:
    jpgs, mp4s = list_media(folder)
    return not jpgs and not mp4s


def extract_dynamic_batch(folders: List[str], video_dir: str, move: bool = True,
                          delete_originals: bool = False,
                          progress_callback: Optional[Callable] = None) -> dict:
    """批量提取动态照片文件夹，返回汇总结果。

    delete_originals=True 时，仅当文件夹内文件已全部提取成功且不再
    残留 JPG/MP4，才把原始动态图文件夹移入回收站；失败即停止并提示。
    """
    os.makedirs(video_dir, exist_ok=True)
    results = []
    total = len(folders)
    ok = skip = error = 0
    aborted = False
    abort_message = ""
    for i, folder in enumerate(folders):
        jpgs_before, mp4s_before = list_media(folder)
        source_sizes = {}
        for src in jpgs_before + mp4s_before:
            try:
                source_sizes[os.path.abspath(src)] = os.path.getsize(src)
            except OSError:
                source_sizes[os.path.abspath(src)] = 0
        items, counts = extract_folder(folder, video_dir, move=move)
        deletion = {"attempted": False, "deleted": False, "message": ""}
        if delete_originals:
            if counts["error"]:
                deletion["message"] = "存在失败文件，原始文件夹未删除"
            elif not _folder_empty(folder):
                deletion["message"] = "文件夹中仍有文件，原始文件夹未删除"
            else:
                verified, missing = _verify_extracted(
                    jpgs_before, mp4s_before, folder, video_dir, source_sizes)
                if not verified:
                    deletion["message"] = (
                        f"提取后校验未通过（{len(missing)} 个目标文件缺失或大小不一致），"
                        "原始文件夹未删除")
                else:
                    from .utils import send_to_trash
                    deletion["attempted"] = True
                    if send_to_trash(folder):
                        deletion["deleted"] = True
                    else:
                        deletion["deleted"] = False
                        deletion["message"] = "原始文件夹移入回收站失败，已停止后续删除"
        results.append({"folder": folder, "items": items, "deletion": deletion})
        ok += counts["ok"]
        skip += counts["skip"]
        error += counts["error"]
        if progress_callback:
            try:
                progress_callback(i + 1, total, folder)
            except Exception:
                pass
        if (deletion["attempted"] and not deletion["deleted"]) or deletion["message"].startswith("提取后校验未通过"):
            aborted = True
            abort_message = deletion["message"]
            break
    return {
        "results": results,
        "video_dir": video_dir,
        "ok": ok,
        "skip": skip,
        "error": error,
        "folders": total,
        "aborted": aborted,
        "abort_message": abort_message,
    }
