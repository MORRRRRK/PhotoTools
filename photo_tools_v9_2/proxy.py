"""proxy.py - 视频代理生成模块 (V5.1)"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv",
    ".webm", ".mts", ".m2ts", ".3gp",
}
PROJECT_ROOT = Path(__file__).resolve().parent
PROXY_MAP_FILE = PROJECT_ROOT / "proxy_map.json"
RESOLUTION_SHORT_SIDE = {"1080p": 1080, "2.7K": 1520, "4K": 2160}
FPS_OPTIONS = ["60", "30", "24"]
PROXY_BITRATE_TABLE = {
    ("1080p", "60"): 12_000_000,
    ("1080p", "30"): 8_000_000,
    ("1080p", "24"): 7_000_000,
    ("2.7K", "60"): 24_000_000,
    ("2.7K", "30"): 16_000_000,
    ("2.7K", "24"): 14_000_000,
    ("4K", "60"): 45_000_000,
    ("4K", "30"): 30_000_000,
    ("4K", "24"): 26_000_000,
}

_map_lock = threading.Lock()
CREATE_NO_WINDOW = 0x08000000


def find_ffmpeg() -> Optional[str]:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
        p = base / "assets" / "ffmpeg.exe"
        if p.exists():
            return str(p)
    p = PROJECT_ROOT / "assets" / "ffmpeg.exe"
    if p.exists():
        return str(p)
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return str(exe)
    except Exception:
        pass
    return None


def _runtime_config() -> dict:
    try:
        if PROJECT_ROOT.joinpath("config.json").exists():
            return json.loads(PROJECT_ROOT.joinpath("config.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _norm_path(path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def load_proxy_map() -> dict:
    if PROXY_MAP_FILE.exists():
        try:
            return json.loads(PROXY_MAP_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_proxy_map(mapping: dict):
    try:
        PROXY_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROXY_MAP_FILE.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def register_proxy(original: str, proxy: str, status: str, error: str = ""):
    with _map_lock:
        mapping = load_proxy_map()
        key = _norm_path(original)
        old = mapping.get(key, {})
        old.update({
            "original": str(original),
            "proxy": str(proxy),
            "status": status,
            "error": error,
            "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        mapping[key] = old
        save_proxy_map(mapping)


def remove_proxy_record(proxy_path: str):
    with _map_lock:
        mapping = load_proxy_map()
        target = _norm_path(proxy_path)
        for key, rec in list(mapping.items()):
            if rec.get("proxy") and _norm_path(rec["proxy"]) == target:
                mapping.pop(key, None)
        save_proxy_map(mapping)


def get_proxy_output_dir(original: str, cfg: Optional[dict] = None) -> Path:
    cfg = cfg or _runtime_config()
    custom = str(cfg.get("proxy_output_dir") or "").strip()
    if custom:
        return Path(custom)
    return Path(original).parent / "_proxies"


def get_proxy_path(original: str, resolution: str, fps: str,
                   cfg: Optional[dict] = None) -> Path:
    orig = Path(original)
    safe_res = resolution.replace(" ", "").replace(".", "p").replace("K", "k")
    out_dir = get_proxy_output_dir(original, cfg)
    return out_dir / f"{orig.stem}_proxy_{safe_res}_{fps}fps.mp4"


def _probe_with_ffmpeg(path: str, ffmpeg: str) -> dict:
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, creationflags=CREATE_NO_WINDOW,
        )
        text = proc.stderr or ""
    except Exception:
        return {}
    info = {"width": 0, "height": 0, "fps": 0.0, "duration": 0.0}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if m:
        info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"(\d{3,5})x(\d{3,5})", text)
    if m:
        info["width"] = int(m.group(1))
        info["height"] = int(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?)\s*fps", text)
    if m:
        info["fps"] = float(m.group(1))
    return info


def get_source_info(path: str, ffmpeg: Optional[str] = None) -> dict:
    info = {"width": 0, "height": 0, "fps": 0.0, "duration": 0.0}
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            info["fps"] = fps if fps > 0 else 0.0
            info["duration"] = frames / fps if fps > 0 and frames > 0 else 0.0
            cap.release()
    except Exception:
        pass
    if (info["width"] <= 0 or info["duration"] <= 0) and ffmpeg:
        probe = _probe_with_ffmpeg(path, ffmpeg)
        info.update({k: v for k, v in probe.items() if v})
    return info


def estimate_proxy_size(original: str, resolution: str, fps: str,
                        cfg: Optional[dict] = None) -> int:
    """根据分辨率/帧率与片长估算代理文件大小，返回字节数。"""
    ffmpeg = find_ffmpeg()
    info = get_source_info(original, ffmpeg)
    duration = float(info.get("duration") or 0)
    if duration <= 0:
        return 0
    source_fps = float(info.get("fps") or 0)
    eff_fps = float(fps)
    if source_fps and source_fps < eff_fps:
        eff_fps = source_fps
    fps_key = "24"
    if eff_fps >= 55:
        fps_key = "60"
    elif eff_fps >= 27:
        fps_key = "30"
    bps = PROXY_BITRATE_TABLE.get((resolution, fps_key), 8_000_000)
    return int(bps / 8.0 * duration * 1.05)


def build_ffmpeg_cmd(original: str, proxy: str, resolution: str, fps: str,
                     cfg: dict, ffmpeg: str) -> tuple:
    info = get_source_info(original, ffmpeg)
    source_w = max(int(info.get("width") or 0), 2)
    source_h = max(int(info.get("height") or 0), 2)
    target_short = int(RESOLUTION_SHORT_SIDE.get(resolution, 1080))

    if source_h > source_w:
        target_short = min(target_short, source_w)
        if target_short % 2:
            target_short -= 1
        vf = f"scale={target_short}:-2"
    else:
        target_short = min(target_short, source_h)
        if target_short % 2:
            target_short -= 1
        vf = f"scale=-2:{target_short}"

    source_fps = float(info.get("fps") or 0)
    target_fps = float(fps)
    if source_fps and source_fps < target_fps:
        target_fps = source_fps
    fps_text = f"{target_fps:.6f}".rstrip("0").rstrip(".")
    if not fps_text:
        fps_text = "30"

    lut = str(cfg.get("proxy_lut") or "")
    if lut and Path(lut).exists():
        lut_filter = str(Path(lut).resolve()).replace("\\", "/")
        vf += f",lut3d=file='{lut_filter}'"

    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", original,
        "-vf", vf,
        "-r", fps_text,
        "-c:v", "libx264",
        "-preset", str(cfg.get("proxy_preset", "veryfast")),
        "-crf", str(int(cfg.get("proxy_crf", 23))),
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k",
        "-progress", "pipe:1", "-nostats",
        proxy,
    ]
    return cmd, info.get("duration", 0.0)


def _parse_progress_value(value: str) -> float:
    try:
        return float(value) / 1_000_000.0
    except Exception:
        return 0.0


def _run_ffmpeg(cmd: List[str], duration: float, cancel_event: threading.Event,
                progress_cb: Optional[Callable[[float, str, str], None]],
                original: str, proxy: str, cwd: Optional[str] = None) -> tuple:
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
        creationflags=CREATE_NO_WINDOW, cwd=cwd,
    )
    stderr_tail = []

    def read_stderr():
        nonlocal stderr_tail
        for line in proc.stderr:
            line = line.rstrip()
            stderr_tail.append(line)
            if len(stderr_tail) > 40:
                del stderr_tail[:-40]

    def read_progress():
        out_us = 0.0
        for line in proc.stdout:
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key in ("out_time_us", "out_time_ms"):
                try:
                    out_us = float(value)
                    if key == "out_time_ms":
                        out_us *= 1000.0
                except Exception:
                    continue
            if duration > 0 and progress_cb:
                progress_cb(min(1.0, out_us / (duration * 1_000_000.0)), original, proxy)

    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    progress_thread = threading.Thread(target=read_progress, daemon=True)
    stderr_thread.start()
    progress_thread.start()

    while proc.poll() is None:
        if cancel_event.is_set():
            proc.terminate()
            break
        time.sleep(0.15)
    proc.wait(timeout=10)
    stderr_thread.join(timeout=5)
    progress_thread.join(timeout=5)
    ok = proc.returncode == 0
    return ok, "\n".join(stderr_tail[-20:])


def generate_proxy_one(original: str, resolution: str, fps: str, cfg: dict,
                       cancel_event: Optional[threading.Event] = None,
                       progress_cb: Optional[Callable[[float, str, str], None]] = None) -> dict:
    cancel_event = cancel_event or threading.Event()
    orig = Path(original)
    result = {"original": str(orig), "status": "failed", "proxy": "", "error": ""}
    if not orig.exists():
        result["error"] = "原片不存在"
        return result

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        result["error"] = "未找到 ffmpeg，请先确认 assets/ffmpeg.exe 存在"
        return result

    proxy = get_proxy_path(original, resolution, fps, cfg)
    result["proxy"] = str(proxy)
    if proxy.exists() and proxy.stat().st_size > 0:
        register_proxy(original, str(proxy), "done")
        result["status"] = "done"
        result["error"] = "已存在"
        return result

    try:
        proxy.parent.mkdir(parents=True, exist_ok=True)
        tmp = proxy.with_name(proxy.name + ".tmp.mp4")
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        cmd, duration = build_ffmpeg_cmd(original, str(tmp), resolution, fps, cfg, ffmpeg)
        register_proxy(original, str(proxy), "running")
        ok, err = _run_ffmpeg(cmd, duration, cancel_event, progress_cb, original, str(tmp))

        if cancel_event.is_set():
            tmp.unlink(missing_ok=True)
            register_proxy(original, str(proxy), "cancelled", "已取消")
            result["status"] = "cancelled"
            return result

        if ok and tmp.exists() and tmp.stat().st_size > 0:
            os.replace(tmp, proxy)
            register_proxy(original, str(proxy), "done")
            result["status"] = "done"
        else:
            tmp.unlink(missing_ok=True)
            register_proxy(original, str(proxy), "failed", err)
            result["status"] = "failed"
            result["error"] = err or "ffmpeg 生成失败"
    except Exception as e:
        register_proxy(original, str(proxy), "failed", str(e))
        result["error"] = str(e)
    return result


def generate_proxy_batch(paths: List[str], resolution: str, fps: str, cfg: dict,
                         cancel_event: Optional[threading.Event] = None,
                         progress_cb: Optional[Callable[[dict], None]] = None) -> List[dict]:
    cancel_event = cancel_event or threading.Event()
    max_workers = max(1, min(int(cfg.get("proxy_max_workers", 1)), 2))
    results = []

    def run_one(index: int, path: str) -> dict:
        if cancel_event.is_set():
            return {"original": path, "status": "cancelled", "proxy": "", "error": "已取消"}
        if progress_cb:
            progress_cb({"type": "start", "index": index, "total": len(paths), "path": path})
        res = generate_proxy_one(path, resolution, fps, cfg, cancel_event,
                                 lambda p, o, pr: progress_cb({
                                     "type": "progress", "index": index,
                                     "total": len(paths), "path": o, "proxy": pr,
                                     "percent": p,
                                 }) if progress_cb else None)
        if progress_cb:
            progress_cb({"type": "done", "index": index, "total": len(paths),
                         "path": path, "result": res})
        return res

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(run_one, i, p) for i, p in enumerate(paths)]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({"status": "failed", "error": str(e)})
    return results


def find_proxy(original: str, cfg: Optional[dict] = None) -> Optional[str]:
    mapping = load_proxy_map()
    rec = mapping.get(_norm_path(original))
    if rec and rec.get("status") == "done" and rec.get("proxy"):
        p = Path(rec["proxy"])
        if p.exists() and p.stat().st_size > 0:
            return str(p)

    orig = Path(original)
    proxy_dir = get_proxy_output_dir(original, cfg)
    if not proxy_dir.exists():
        return None
    pattern = f"{orig.stem}_proxy_*.mp4"
    candidates = sorted(proxy_dir.glob(pattern))
    if not candidates:
        return None
    candidates.sort(key=lambda p: (
        0 if "_1080p_60fps" in p.name else 1,
        -p.stat().st_size if p.exists() else 0,
    ))
    return str(candidates[0]) if candidates[0].exists() else None


def collect_proxy_files() -> List[Path]:
    seen = set()
    result = []
    for rec in load_proxy_map().values():
        p = rec.get("proxy")
        if p and Path(p).exists():
            key = _norm_path(p)
            if key not in seen:
                seen.add(key)
                result.append(Path(p))
    return result


def delete_proxies(paths: List[str]) -> tuple:
    from .utils import send_to_trash
    ok, fail = 0, 0
    fails = []
    for p in paths:
        try:
            if Path(p).exists() and send_to_trash(str(p)):
                remove_proxy_record(p)
                ok += 1
            else:
                fail += 1
                fails.append(str(p))
        except Exception as e:
            fail += 1
            fails.append(f"{p}: {e}")
    return ok, fail, fails
