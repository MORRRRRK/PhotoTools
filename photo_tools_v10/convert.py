"""convert.py - RAW/PNG 快速转 JPG 引擎 (V9.2)"""

import os
import threading
from pathlib import Path
from typing import Callable, List, Optional

import exifread
from PIL import Image, ImageOps

from .utils import RAW_EXTENSIONS

CONVERT_EXTENSIONS = {".png", ".tif", ".tiff"} | RAW_EXTENSIONS
# .tif/.tiff 用 Pillow 解码，只有相机 RAW 才交给 rawpy
RAWPY_EXTENSIONS = RAW_EXTENSIONS - {".tif", ".tiff"}
DEFAULT_OUTPUT_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
    "PhotoTools", "jpg_review")


def _apply_raw_orientation(img: Image.Image, path: str) -> Image.Image:
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        text = str(tags.get("Image Orientation", "")).strip()
        if not text:
            return img
        num = int(text.split()[0])
    except Exception:
        return img
    try:
        if num == 2:
            return ImageOps.mirror(img)
        if num == 3:
            return img.rotate(180, expand=True)
        if num == 4:
            return ImageOps.flip(img)
        if num == 5:
            return img.transpose(Image.Transpose.TRANSPOSE).transpose(
                Image.Transpose.FLIP_LEFT_RIGHT)
        if num == 6:
            return img.rotate(-90, expand=True)
        if num == 7:
            return img.transpose(Image.Transpose.TRANSPOSE).transpose(
                Image.Transpose.FLIP_TOP_BOTTOM)
        if num == 8:
            return img.rotate(90, expand=True)
    except Exception:
        pass
    return img


def _open_image(path: str) -> Image.Image:
    ext = os.path.splitext(path)[1].lower()
    if ext in RAWPY_EXTENSIONS:
        import rawpy
        with rawpy.imread(path) as raw:
            rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
        img = Image.fromarray(rgb)
        return _apply_raw_orientation(img, path)
    img = Image.open(path)
    return ImageOps.exif_transpose(img)


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def get_output_path(src: str, output_dir: str) -> str:
    return os.path.join(output_dir, Path(src).stem + ".jpg")


def convert_one(src: str, output_dir: str, quality: int = 95) -> dict:
    result = {"original": str(src), "status": "failed", "output": "", "error": ""}
    if not os.path.exists(src):
        result["error"] = "源文件不存在"
        return result
    output = get_output_path(src, output_dir)
    result["output"] = output
    if os.path.exists(output) and os.path.getsize(output) > 0:
        result["status"] = "skipped"
        result["error"] = "已存在"
        return result
    try:
        os.makedirs(output_dir, exist_ok=True)
        img = _open_image(src)
        img = _to_rgb(img)
        img.save(output, "JPEG", quality=quality, optimize=True)
        if os.path.exists(output) and os.path.getsize(output) > 0:
            result["status"] = "done"
        else:
            result["error"] = "生成失败"
    except Exception as e:
        result["error"] = str(e)
    return result


def convert_batch(paths: List[str], output_dir: str,
                  cancel_event: Optional[threading.Event] = None,
                  progress_cb: Optional[Callable[[dict], None]] = None) -> List[dict]:
    cancel_event = cancel_event or threading.Event()
    results = []
    total = len(paths)
    for index, path in enumerate(paths):
        if cancel_event.is_set():
            results.append({
                "original": str(path), "status": "cancelled",
                "output": "", "error": "已取消",
            })
            break
        if progress_cb:
            progress_cb({"type": "start", "index": index, "total": total, "path": path})
        res = convert_one(path, output_dir)
        if progress_cb:
            progress_cb({"type": "done", "index": index, "total": total,
                         "path": path, "result": res})
        results.append(res)
    return results
