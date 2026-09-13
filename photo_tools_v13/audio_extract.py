import logging
logger = logging.getLogger(__name__)

"""audio_extract.py - 视频无损音频提取引擎 (V7)"""

import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

from .proxy import CREATE_NO_WINDOW, find_ffmpeg

AUDIO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".m4v", ".wmv", ".flv",
    ".webm", ".mts", ".m2ts", ".3gp",
}
AUDIO_FOLDER_NAME = "_audio"
LOSSY_AUDIO_CODECS = {
    "aac", "mp3", "mp2", "ac3", "eac3", "opus", "vorbis",
    "wma", "dts", "dts-hd", "amr_nb", "amr_wb",
}


def get_audio_output_dir(original: str, cfg: Optional[dict] = None) -> Path:
    cfg = cfg or {}
    custom = str(cfg.get("audio_output_dir") or "").strip()
    if custom:
        return Path(custom)
    return Path(original).parent / AUDIO_FOLDER_NAME


def _probe_audio(path: str, ffmpeg: str) -> dict:
    result = {"has_audio": False, "codec": "", "duration": 0.0, "error": ""}
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, creationflags=CREATE_NO_WINDOW,
        )
        text = proc.stderr or ""
    except Exception as e:
        result["error"] = str(e)
        return result
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if m:
        result["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"Stream #\d+:\d+.*?Audio:\s*([a-zA-Z0-9_]+)", text)
    if m:
        result["has_audio"] = True
        result["codec"] = m.group(1).lower()
    return result


def _run_ffmpeg(cmd: List[str], duration: float, cancel_event: threading.Event,
                progress_cb: Optional[Callable[[float, str, str], None]],
                original: str, output: str) -> tuple:
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
        creationflags=CREATE_NO_WINDOW,
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
                except Exception as _exc:
                    continue
            if duration > 0 and progress_cb:
                progress_cb(min(1.0, out_us / (duration * 1_000_000.0)), original, output)

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


def extract_audio_one(original: str, cfg: Optional[dict] = None,
                      cancel_event: Optional[threading.Event] = None,
                      progress_cb: Optional[Callable[[float, str, str], None]] = None) -> dict:
    cancel_event = cancel_event or threading.Event()
    orig = Path(original)
    result = {"original": str(orig), "status": "failed", "output": "", "error": "", "hint": ""}
    if not orig.exists():
        result["error"] = "源文件不存在"
        return result

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        result["error"] = "未找到 ffmpeg，请先确认 assets/ffmpeg.exe 存在"
        return result

    out_dir = get_audio_output_dir(original, cfg)
    output = out_dir / f"{orig.stem}.wav"
    result["output"] = str(output)

    probe = _probe_audio(str(orig), ffmpeg)
    if probe.get("error"):
        result["error"] = f"无法读取源文件: {probe['error']}"
        return result
    if not probe["has_audio"]:
        result["status"] = "no_audio"
        result["error"] = "无音轨"
        return result

    codec = probe["codec"]
    if codec in LOSSY_AUDIO_CODECS:
        result["hint"] = (
            f"源音轨为 {codec}（有损），输出 WAV 只能避免二次压缩，"
            "无法恢复已丢失的细节"
        )

    if output.exists() and output.stat().st_size > 0:
        result["status"] = "skipped"
        result["error"] = "已存在"
        return result

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        tmp = output.with_name(output.name + ".tmp.wav")
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(orig),
            "-vn", "-acodec", "pcm_s24le", "-ar", "48000",
            "-progress", "pipe:1", "-nostats",
            str(tmp),
        ]
        ok, err = _run_ffmpeg(
            cmd, float(probe.get("duration") or 0), cancel_event,
            progress_cb, str(orig), str(tmp))

        if cancel_event.is_set():
            tmp.unlink(missing_ok=True)
            result["status"] = "cancelled"
            result["error"] = "已取消"
            return result

        if ok and tmp.exists() and tmp.stat().st_size > 0:
            os.replace(tmp, output)
            result["status"] = "done"
        else:
            tmp.unlink(missing_ok=True)
            result["status"] = "failed"
            result["error"] = err or "ffmpeg 提取失败"
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
    return result


def extract_audio_batch(paths: List[str], cfg: Optional[dict] = None,
                        cancel_event: Optional[threading.Event] = None,
                        progress_cb: Optional[Callable[[dict], None]] = None) -> List[dict]:
    cfg = cfg or {}
    cancel_event = cancel_event or threading.Event()
    results = []
    total = len(paths)
    for index, path in enumerate(paths):
        if cancel_event.is_set():
            results.append({
                "original": str(path), "status": "cancelled",
                "output": "", "error": "已取消", "hint": "",
            })
            break
        if progress_cb:
            progress_cb({"type": "start", "index": index, "total": total, "path": path})
        res = extract_audio_one(
            path, cfg, cancel_event,
            lambda p, o, out: progress_cb({
                "type": "progress", "index": index, "total": total,
                "path": o, "output": out, "percent": p,
            }) if progress_cb else None)
        if progress_cb:
            progress_cb({"type": "done", "index": index, "total": total,
                         "path": path, "result": res})
        results.append(res)
    return results
