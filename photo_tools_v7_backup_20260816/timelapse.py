"""timelapse.py - 一键生成延时视频 (V5.1)"""

import os
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from PIL import Image, ImageOps

from .proxy import _run_ffmpeg, find_ffmpeg

IMAGE_EXTENSIONS = {".jpg", ".jpeg"}
RESOLUTION_LANDSCAPE = {
    "1080P": (1920, 1080),
    "2K": (2560, 1440),
    "4K": (3840, 2160),
}
QUALITY_CRF = {"标准 CRF14": 14, "高 CRF12": 12, "最高 CRF10": 10}
FPS_OPTIONS = ["24", "25", "30", "60"]
STAB_SMOOTHING = {"低": 30, "中": 20, "高": 10}


def natural_key(name: str):
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", name)]


def collect_jpgs(paths: List[str]) -> List[str]:
    files = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for root, _dirs, names in os.walk(path):
                for name in names:
                    if Path(name).suffix.lower() in IMAGE_EXTENSIONS:
                        files.append(os.path.join(root, name))
        elif path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            files.append(str(path))
    files.sort(key=lambda p: natural_key(os.path.basename(p)))
    if not files:
        raise ValueError("未找到可用的 JPG 文件，请检查文件夹是否为空或格式是否正确")
    return files


def _orient_image(path: str) -> Image.Image:
    img = Image.open(path)
    return ImageOps.exif_transpose(img)


def _output_size(first_img: Image.Image, resolution: str) -> tuple:
    target = RESOLUTION_LANDSCAPE.get(resolution, (1920, 1080))
    w, h = first_img.size
    if h > w:
        target = (target[1], target[0])
        if max(w, h) < max(target):
            return (w, h)
    elif max(w, h) < max(target):
        return (w, h)
    return target


def _save_scaled(img: Image.Image, out_size: tuple, dest: Path):
    img.thumbnail(out_size, Image.LANCZOS)
    canvas = Image.new("RGB", out_size, (0, 0, 0))
    canvas.paste(img, ((out_size[0] - img.width) // 2,
                       (out_size[1] - img.height) // 2))
    canvas.save(dest, "PNG")


def _ensure_unique_output(output_path: str) -> Path:
    p = Path(output_path)
    if not p.exists():
        return p
    stem = p.stem
    suffix = p.suffix
    idx = 1
    while True:
        candidate = p.with_name(f"{stem}_{idx}{suffix}")
        if not candidate.exists():
            return candidate
        idx += 1


def _discard_output(output_path: str):
    try:
        Path(output_path).unlink(missing_ok=True)
    except Exception:
        pass


def _ff_filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _probe_frames(path: str, ffmpeg: str) -> dict:
    info = {"frames": 0, "width": 0, "height": 0, "fps": 0.0, "duration": 0.0}
    try:
        proc = _run_silent([ffmpeg, "-i", path, "-map", "0:v:0", "-f", "null", "NUL"])
        text = proc or ""
        frames = re.findall(r"frame=\s*(\d+)", text)
        if frames:
            info["frames"] = int(frames[-1])
        m = re.search(r"(\d{3,5})x(\d{3,5})", text)
        if m:
            info["width"] = int(m.group(1))
            info["height"] = int(m.group(2))
        m = re.search(r"(\d+(?:\.\d+)?)\s*fps", text)
        if m:
            info["fps"] = float(m.group(1))
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
        if m:
            info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return info


def _run_silent(cmd: List[str]) -> str:
    import subprocess
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300, creationflags=0x08000000,
        )
        return (proc.stderr or "") + (proc.stdout or "")
    except Exception:
        return ""


def _run_stage(cmd: List[str], duration: float, cancel_event: threading.Event,
               progress_cb: Optional[Callable[[dict], None]], phase: str,
               cwd: Optional[str] = None) -> tuple:
    def cb(percent, _orig, _proxy):
        if progress_cb:
            progress_cb({"phase": phase, "percent": percent})
    return _run_ffmpeg(cmd, duration, cancel_event, cb, "", "", cwd)


def generate_timelapse(
    paths: List[str],
    output_path: str,
    resolution: str,
    fps: int,
    crf: int,
    stabilize: bool,
    strength: str,
    cancel_event: Optional[threading.Event] = None,
    progress_cb: Optional[Callable[[dict], None]] = None,
) -> dict:
    cancel_event = cancel_event or threading.Event()
    files = collect_jpgs(paths)
    total = len(files)
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return {"status": "failed", "error": "未找到 ffmpeg"}

    output_path = str(_ensure_unique_output(output_path))
    out_dir = Path(output_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / f".phototools_timelapse_{int(time.time() * 1000)}"
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        first = _orient_image(files[0])
        out_size = _output_size(first, resolution)
        frame_dir = work_dir / ("orig_frames" if stabilize else "scaled_frames")
        frame_dir.mkdir(parents=True, exist_ok=True)

        start = time.time()
        for idx, fp in enumerate(files, 1):
            if cancel_event.is_set():
                _discard_output(output_path)
                return {"status": "cancelled", "output": output_path}
            img = _orient_image(fp)
            dest = frame_dir / f"frame_{idx:06d}.png"
            if stabilize:
                img.save(dest, "PNG")
            else:
                _save_scaled(img, out_size, dest)
            elapsed = time.time() - start
            eta = elapsed / idx * (total - idx) if idx else 0
            if progress_cb:
                progress_cb({
                    "phase": "处理帧", "current": idx, "total": total,
                    "percent": idx / total, "eta": eta,
                })

        duration = total / float(fps)
        pattern = str(frame_dir / "frame_%06d.png")
        trf = work_dir / "transforms.trf"

        if stabilize:
            smooth = STAB_SMOOTHING.get(strength, 20)
            detect_cmd = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-framerate", str(fps), "-i", pattern,
                "-vf", "deflicker=size=11:mode=median,vidstabdetect=result=transforms.trf:tripod=1:shakiness=8:accuracy=12:stepsize=6:mincontrast=0.3",
                "-f", "null", "NUL",
                "-progress", "pipe:1", "-nostats",
            ]
            ok, err = _run_stage(detect_cmd, duration, cancel_event, progress_cb, "分析中", str(work_dir))
            if cancel_event.is_set():
                return {"status": "cancelled", "output": output_path}
            if not ok:
                _discard_output(output_path)
                return {"status": "failed", "error": err or "增稳分析失败", "output": output_path}

            vf = (
                "deflicker=size=11:mode=median,"
                "vidstabtransform=input=transforms.trf:tripod=1:zoom=1:optzoom=0:interpol=bicubic:smoothing="
                f"{smooth},"
                f"scale={out_size[0]}:{out_size[1]}:force_original_aspect_ratio=decrease,"
                f"pad={out_size[0]}:{out_size[1]}:(ow-iw)/2:(oh-ih)/2:color=black,"
                "format=yuv420p"
            )
        else:
            vf = "deflicker=size=11:mode=median,format=yuv420p"

        encode_cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", str(fps), "-i", pattern,
        ]
        if vf:
            encode_cmd += ["-vf", vf]
        encode_cmd += [
            "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-crf", str(crf), "-preset", "slow", "-tune", "stillimage",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", output_path,
        ]
        cwd = str(work_dir) if stabilize else None
        ok, err = _run_stage(encode_cmd, duration, cancel_event, progress_cb, "编码中", cwd)
        if cancel_event.is_set():
            _discard_output(output_path)
            return {"status": "cancelled", "output": output_path}
        if not ok or not Path(output_path).exists():
            _discard_output(output_path)
            return {"status": "failed", "error": err or "视频编码失败", "output": output_path}

        info = _probe_frames(output_path, ffmpeg)
        size = Path(output_path).stat().st_size
        return {
            "status": "done",
            "output": output_path,
            "frames": info.get("frames") or total,
            "width": info.get("width") or out_size[0],
            "height": info.get("height") or out_size[1],
            "fps": info.get("fps") or fps,
            "duration": info.get("duration") or duration,
            "size": size,
            "stabilized": stabilize,
        }
    except Exception as e:
        _discard_output(output_path)
        return {"status": "failed", "error": str(e), "output": output_path}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def default_output_name(resolution: str, fps: int, stabilize: bool) -> str:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "_增稳" if stabilize else ""
    return f"延时摄影_{now}_{resolution}_{fps}fps{suffix}.mp4"
