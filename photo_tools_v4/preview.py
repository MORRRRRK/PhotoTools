"""preview.py - 图片预览模块，支持 RAW 解码 + EXIF 元数据显示"""

import os
import threading
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS
import customtkinter as ctk

from .utils import format_size, open_file_in_explorer
import exifread

# rawpy 延迟导入
_has_rawpy = None
def _get_rawpy():
    global _has_rawpy
    if _has_rawpy is None:
        try:
            import rawpy as _rp
            _has_rawpy = _rp
        except ImportError:
            _has_rawpy = False
    return _has_rawpy if _has_rawpy else None


# ===== EXIF 提取 =====

def get_exif_info(path):
    """提取照片 EXIF 信息（exifread 主力，支持所有 RAW 格式）。"""
    info = {
        "date": "-", "make": "-", "model": "-",
        "iso": "-", "fnumber": "-", "exposure": "-",
        "focal": "-", "artist": "-",
        "width": "-", "height": "-", "filesize": "-",
    }
    try:
        info["filesize"] = format_size(os.path.getsize(path))
    except: pass

    # 1. exifread 从文件字节流直接读 EXIF（任何格式皆可）
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        for key, tag in tags.items():
            val = str(tag.printable) if hasattr(tag, "printable") else str(tag)
            if key == "Image Make": info["make"] = val.strip()
            elif key == "Image Model": info["model"] = val.strip()
            elif key == "EXIF DateTimeOriginal": info["date"] = val
            elif key == "EXIF ISOSpeedRatings": info["iso"] = val
            elif key == "EXIF FNumber":
                try:
                    info["fnumber"] = f"f/{float(val):.1f}"
                except:
                    info["fnumber"] = f"f/{val}"
            elif key == "EXIF ExposureTime":
                try:
                    if "/" in str(val):
                        parts = str(val).split("/")
                        exp = float(parts[0]) / float(parts[1])
                    else:
                        exp = float(val)
                    info["exposure"] = f"1/{1/exp:.0f}s" if exp < 1 else f"{exp:.1f}s"
                except:
                    info["exposure"] = str(val)
            elif key == "EXIF FocalLength":
                try:
                    fl = str(val).replace(" mm", "").strip()
                    info["focal"] = f"{float(fl):.0f}mm"
                except:
                    info["focal"] = str(val)
            elif key == "Image Artist":
                info["artist"] = val.strip() if val.strip() else "-"
            elif key == "EXIF PixelXDimension":
                info["width"] = val.split()[0] if " " in str(val) else str(val)
            elif key == "EXIF PixelYDimension":
                info["height"] = val.split()[0] if " " in str(val) else str(val)
    except:
        pass

    # 2. Pillow EXIF 补充
    try:
        img = Image.open(path)
        exif = img._getexif()
        if exif and not any(info[k] != "-" for k in ["make","model","date","iso","fnumber","exposure","focal"]):
            pass  # exifread 已经有数据，不用再覆盖
        if info["width"] == "-" or info["height"] == "-":
            info["width"] = str(img.width)
            info["height"] = str(img.height)
    except:
        pass

    # 3. rawpy 尺寸补充
    if info["width"] == "-" or info["height"] == "-":
        rp = _get_rawpy()
        if rp:
            try:
                with rp.imread(path) as raw:
                    info["width"] = str(raw.sizes.width)
                    info["height"] = str(raw.sizes.height)
            except:
                pass

    return info


def format_exif_info(info):
    """格式化 EXIF 信息为多行文本。"""
    lines = []

    # 相机信息
    camera = f"{info['make']} {info['model']}".strip().replace("- -", "-")
    if camera and camera != "-":
        lines.append(f"相机: {camera}")

    # 拍照日期
    if info["date"] != "-":
        lines.append(f"日期: {info['date']}")

    # 曝光参数
    params = []
    if info["iso"] != "-": params.append(f"ISO {info['iso']}")
    if info["fnumber"] != "-": params.append(info["fnumber"])
    if info["exposure"] != "-": params.append(info["exposure"])
    if info["focal"] != "-": params.append(info["focal"])
    if params:
        lines.append("  ".join(params))

    # 分辨率 + 文件大小
    if info["width"] != "-" and info["height"] != "-":
        lines.append(f"分辨率: {info['width']}\u00d7{info['height']}")
    if info["filesize"] != "-":
        lines.append(f"大小: {info['filesize']}")

    # 作者
    if info["artist"] != "-" and info["artist"]:
        lines.append(f"\u00a9 {info['artist']}")

    return "\n".join(lines) if lines else "无可用元数据"


# ===== 图片加载 =====

def load_image(path, max_size=(1400, 1000)):
    """加载图片，支持 RAW 解码，返回 (PIL.Image, info_dict)。"""
    ext = os.path.splitext(path)[1].lower()
    exif_info = get_exif_info(path)

    # 1. Pillow
    try:
        img = Image.open(path)
        try:
            img = ImageOps.exif_transpose(img)
        except: pass
        info = {
            "format": img.format or ext.upper(),
            "width": img.width, "height": img.height,
            "mode": img.mode,
        }
        img.thumbnail(max_size, Image.LANCZOS)
        return img, info, exif_info
    except:
        pass

    # 2. rawpy
    rp = _get_rawpy()
    if rp:
        try:
            with rp.imread(path) as raw:
                rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
            img = Image.fromarray(rgb)
            info = {"format": ext.upper(), "width": exif_info["width"],
                    "height": exif_info["height"], "mode": "RGB"}
            img.thumbnail(max_size, Image.LANCZOS)
            return img, info, exif_info
        except:
            pass

    return None, None, exif_info


# ===== 预览窗口 =====

class PreviewWindow(ctk.CTkToplevel):
    def __init__(self, parent, path):
        super().__init__(parent)
        self.path = path
        self.filename = os.path.basename(path)
        self.title(self.filename)
        self.geometry("960x720")
        self.minsize(600, 450)

        # 顶部：文件名
        self.name_lb = ctk.CTkLabel(self, text=self.filename,
                                     font=("", 14, "bold"), anchor="w")
        self.name_lb.pack(fill="x", padx=12, pady=(8, 2))

        # 元数据展示区
        self.meta_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.meta_frame.pack(fill="x", padx=12, pady=(0, 4))

        self.meta_text = ctk.CTkTextbox(self.meta_frame, height=100,
                                         font=("Consolas", 11), wrap="word")
        self.meta_text.pack(fill="x")
        self.meta_text.insert("0.0", "加载元数据...")
        self.meta_text.configure(state="disabled")

        # 操作按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkButton(btn_frame, text="打开位置", width=100, height=28,
                       command=self._open_location).pack(side="left", padx=2)
        self.loading_lb = ctk.CTkLabel(btn_frame, text="", font=("", 11))
        self.loading_lb.pack(side="left", padx=10)

        # 图片展示区
        self.img_frame = ctk.CTkScrollableFrame(self)
        self.img_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.img_label = ctk.CTkLabel(self.img_frame, text="")
        self.img_label.pack(expand=True)

        # 异步加载
        self.loading_lb.configure(text="加载中...")
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            img, info, exif = load_image(self.path)
            if img:
                meta_str = format_exif_info(exif)
                self.after(0, lambda: self._show(img, meta_str, info))
            else:
                meta_str = format_exif_info(exif)
                self.after(0, lambda: self._fail(meta_str))
        except Exception as e:
            self.after(0, lambda: self.loading_lb.configure(text=f"加载失败: {e}"))

    def _show(self, img, meta_str, info):
        from PIL import ImageTk
        self.photo = ImageTk.PhotoImage(img)
        self.img_label.configure(image=self.photo, text="")
        self._set_meta(meta_str)
        status = f"显示完成 ({img.width}\u00d7{img.height})"
        self.loading_lb.configure(text=status)

    def _fail(self, meta_str):
        self.img_label.configure(text="无法打开此文件")
        self._set_meta(meta_str)
        self.loading_lb.configure(text="不支持此格式")

    def _set_meta(self, text):
        self.meta_text.configure(state="normal")
        self.meta_text.delete("0.0", "end")
        self.meta_text.insert("0.0", text)
        self.meta_text.configure(state="disabled")

    def _open_location(self):
        open_file_in_explorer(self.path)


def show_preview(parent, paths):
    for p in paths:
        PreviewWindow(parent, p)
