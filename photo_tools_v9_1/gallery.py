"""gallery.py - 作品展示：EXIF、缩略图与本地缓存 (V9)"""

import hashlib
import os
import shutil
import sys
from pathlib import Path
from typing import List

import exifread
from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
UNSUPPORTED_IMAGE_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2",
    ".dng", ".raf", ".orf", ".rw2", ".pef", ".srw", ".x3f",
    ".3fr", ".kdc", ".dcr", ".mef", ".mos", ".mrw", ".tif",
    ".tiff", ".bmp", ".heic", ".heif", ".avif", ".gif",
}
ALL_IMAGE_EXTENSIONS = SUPPORTED_EXTENSIONS | UNSUPPORTED_IMAGE_EXTENSIONS

APP_DIR = "PhotoTools"
CACHE_DIR = "preview_cache"
THUMB_SIZE = (240, 240)
PREVIEW_MAX_SIZE = (1600, 1600)


def get_install_path() -> str:
    """已安装时返回安装目录，否则返回空字符串。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\PhotoTools") as key:
            path = winreg.QueryValueEx(key, "InstallPath")[0]
        return str(path) if path else ""
    except Exception:
        return ""


def get_cache_dir() -> str:
    install = get_install_path()
    if install:
        return os.path.join(install, APP_DIR, CACHE_DIR)
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_DIR, CACHE_DIR)


def clean_cache() -> None:
    """清空预览缓存目录内容，不删除目录本身。"""
    cache = get_cache_dir()
    try:
        if os.path.isdir(cache):
            for name in os.listdir(cache):
                p = os.path.join(cache, name)
                try:
                    if os.path.isfile(p) or os.path.islink(p):
                        os.remove(p)
                    elif os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                except OSError:
                    pass
    except OSError:
        pass


def clean_install_dir_cache() -> None:
    """首次启动时删除安装/解包目录中可能残留的预览缓存。"""
    roots = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass))
    else:
        roots.append(Path(__file__).resolve().parent.parent)
    for root in roots:
        candidates = [
            root / CACHE_DIR,
            root / "_gallery_cache",
        ]
        for p in candidates:
            try:
                if p.exists():
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        p.unlink(missing_ok=True)
            except OSError:
                pass


def _hash_path(path: str) -> str:
    return hashlib.md5(
        os.path.abspath(path).encode("utf-8", errors="replace")
    ).hexdigest()


def _ratio_text(value) -> str:
    text = str(value).strip()
    try:
        if "/" in text:
            num, _, den = text.partition("/")
            num = float(num.strip())
            den = float(den.strip() or "1")
        else:
            num = float(text)
            den = 1.0
        if den == 0:
            return text
        val = num / den
        return f"{val:.1f}".rstrip("0").rstrip(".")
    except Exception:
        return text


def _shutter_text(value) -> str:
    text = str(value).strip()
    try:
        if "/" in text:
            num, _, den = text.partition("/")
            num = float(num.strip())
            den = float(den.strip() or "1")
        else:
            num = float(text)
            den = 1.0
        if den == 0:
            return text
        sec = num / den
        if sec >= 1.0:
            return f"{sec:.1f}s"
        if sec > 0:
            return f"1/{int(round(1.0 / sec))}s"
        return text
    except Exception:
        return text


def collect_image_files(folder: str) -> List[str]:
    found = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if os.path.splitext(name)[1].lower() in ALL_IMAGE_EXTENSIONS:
                found.append(os.path.join(root, name))
    return sorted(found)


def read_image_info(path: str) -> dict:
    info = {
        "path": str(path),
        "width": 0,
        "height": 0,
        "size_bytes": 0,
        "format": "",
        "aperture": "未知",
        "shutter": "未知",
        "iso": "未知",
        "focal": "未知",
        "device": "未知",
        "datetime": "未知",
        "supported": True,
        "error": "",
    }
    try:
        info["size_bytes"] = os.path.getsize(path)
    except OSError:
        pass
    ext = os.path.splitext(path)[1].lower()
    info["format"] = ext.lstrip(".").upper() or "未知"
    if ext not in SUPPORTED_EXTENSIONS:
        info["supported"] = False
        info["error"] = "不支持"
        return info

    tags = {}
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
    except Exception:
        tags = {}

    try:
        with Image.open(path) as img:
            info["width"], info["height"] = img.size
    except Exception as e:
        info["supported"] = False
        info["error"] = f"无法读取: {e}"
        return info

    def get(*keys):
        for key in keys:
            if key in tags:
                return str(tags[key]).strip()
        return None

    aperture = get("EXIF FNumber", "FNumber")
    if aperture:
        info["aperture"] = f"f/{_ratio_text(aperture)}"
    shutter = get("EXIF ExposureTime", "ExposureTime")
    if shutter:
        info["shutter"] = _shutter_text(shutter)
    iso = get("EXIF ISOSpeedRatings", "ISOSpeedRatings",
              "EXIF PhotographicSensitivity", "PhotographicSensitivity")
    if iso:
        info["iso"] = iso
    focal = get("EXIF FocalLength", "FocalLength")
    if focal:
        info["focal"] = f"{_ratio_text(focal)}mm"
    make = get("Image Make")
    model = get("Image Model")
    if make or model:
        info["device"] = f"{make or ''} {model or ''}".strip()
    taken = get("EXIF DateTimeOriginal", "DateTimeOriginal",
                "Image DateTime", "EXIF DateTimeDigitized")
    if taken:
        info["datetime"] = taken.replace("\x00", "").strip()
    return info


def make_thumbnail(path: str, cache_dir: str = None) -> str:
    cache_dir = cache_dir or get_cache_dir()
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((THUMB_SIZE[0] * 2, THUMB_SIZE[1] * 2), Image.LANCZOS)
            thumb = img.convert("RGB")
            out = os.path.join(cache_dir, _hash_path(path) + "_thumb.jpg")
            thumb.save(out, "JPEG", quality=85)
            return out
    except Exception:
        return ""


def make_preview(path: str, cache_dir: str = None) -> str:
    cache_dir = cache_dir or get_cache_dir()
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(PREVIEW_MAX_SIZE, Image.LANCZOS)
            preview = img.convert("RGB")
            out = os.path.join(cache_dir, _hash_path(path) + "_preview.jpg")
            preview.save(out, "JPEG", quality=92)
            return out
    except Exception:
        return ""
