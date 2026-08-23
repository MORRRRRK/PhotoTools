from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageOps


BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = BASE_DIR.parent / "陈大可照片"
SITE_DIR = BASE_DIR / "site"
PHOTO_DIR = SITE_DIR / "photos"
THUMB_DIR = SITE_DIR / "thumbs"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
FULL_MAX_SIDE = 1920
THUMB_MAX_SIDE = 640
FULL_QUALITY = 82
THUMB_QUALITY = 80
HASH_NAME_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


def exif_date(path: Path) -> str:
    try:
        with Image.open(path) as im:
            raw = im.getexif().get(36867) or im.getexif().get(306) or ""
        match = re.search(r"(\d{4}):(\d{2}):(\d{2})", str(raw))
        if match:
            return "-".join(match.groups())
    except Exception:
        pass
    return ""


def resize_to(im: Image.Image, max_side: int) -> Image.Image:
    if max(im.size) <= max_side:
        return im.copy()
    ratio = max_side / max(im.size)
    size = (max(1, round(im.width * ratio)), max(1, round(im.height * ratio)))
    return im.resize(size, Image.LANCZOS)


def image_metadata(path: Path) -> tuple[Image.Image, int, int]:
    with Image.open(path) as im:
        transposed = ImageOps.exif_transpose(im)
        if transposed.mode in ("RGBA", "LA") or (
            transposed.mode == "P" and "transparency" in transposed.info
        ):
            background = Image.new("RGB", transposed.size, (255, 255, 255))
            background.paste(transposed, mask=transposed.convert("RGBA").getchannel("A"))
            transposed = background
        elif transposed.mode != "RGB":
            transposed = transposed.convert("RGB")
        return transposed, transposed.width, transposed.height


def make_id(relative_path: Path) -> str:
    return hashlib.md5(relative_path.as_posix().encode("utf-8")).hexdigest()[:16]


def build(force: bool = False) -> None:
    if not SOURCE_DIR.is_dir():
        raise SystemExit(f"未找到照片目录: {SOURCE_DIR}")

    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(
        (
            p
            for p in SOURCE_DIR.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS and not any(
                part.startswith(".") for part in p.relative_to(SOURCE_DIR).parts
            )
        ),
        key=lambda p: (exif_date(p) or "9999", p.relative_to(SOURCE_DIR).as_posix().lower()),
    )

    photos = []
    for index, path in enumerate(files, start=1):
        relative = path.relative_to(SOURCE_DIR)
        photo_id = make_id(relative)
        full_path = PHOTO_DIR / f"{photo_id}.webp"
        thumb_path = THUMB_DIR / f"{photo_id}.webp"

        needs_rebuild = (
            force
            or not full_path.exists()
            or not thumb_path.exists()
            or full_path.stat().st_mtime < path.stat().st_mtime
            or thumb_path.stat().st_mtime < path.stat().st_mtime
        )

        if needs_rebuild:
            image, width, height = image_metadata(path)
            full = resize_to(image, FULL_MAX_SIDE)
            thumb = resize_to(image, THUMB_MAX_SIDE)
            full.save(full_path, "WEBP", quality=FULL_QUALITY, method=6)
            thumb.save(thumb_path, "WEBP", quality=THUMB_QUALITY, method=6)
            image.close()
        else:
            image, width, height = image_metadata(path)
            image.close()

        parent = relative.parent
        album = parent.as_posix() if parent != Path(".") else SOURCE_DIR.name
        stem = relative.stem
        title = f"作品 {index:03d}" if HASH_NAME_RE.match(stem) else stem

        photos.append(
            {
                "id": photo_id,
                "title": title,
                "album": album,
                "date": exif_date(path),
                "full": f"photos/{photo_id}.webp",
                "thumb": f"thumbs/{photo_id}.webp",
                "width": width,
                "height": height,
            }
        )

    payload = {
        "title": "陈大可摄影作品",
        "subtitle": "光影记录",
        "count": len(photos),
        "photos": photos,
    }
    (SITE_DIR / "photos.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"完成: {len(photos)} 张照片 -> {SITE_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成摄影相册静态站点")
    parser.add_argument("--force", action="store_true", help="忽略缓存，重新生成全部图片")
    args = parser.parse_args()
    build(force=args.force)
