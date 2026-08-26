"""preview.py - 图片预览模块，支持 RAW 格式解码"""

import os
import threading
from PIL import Image, ImageOps
import customtkinter as ctk

from .utils import format_size, open_file_in_explorer

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


def load_image(path, max_size=(1400, 1000)):
    """加载图片，支持 RAW 解码，返回 (PIL.Image, info_dict)。"""
    ext = os.path.splitext(path)[1].lower()

    # 1. Pillow 直接打开（JPEG/PNG/TIFF/DNG 等）
    try:
        img = Image.open(path)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        info = {
            "format": img.format or ext.upper(),
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
        }
        # 对于 DNG 等 TIFF-based RAW，Pillow 可能显示颜色不对
        # 如果看起来有问题，fallthrough 到 rawpy
        img.thumbnail(max_size, Image.LANCZOS)
        return img, info
    except Exception:
        pass

    # 2. rawpy 解码（RW2/CR2/NEF/ARW 等相机 RAW）
    rp = _get_rawpy()
    if rp:
        try:
            with rp.imread(path) as raw:
                rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
            img = Image.fromarray(rgb)
            info = {
                "format": ext.upper(),
                "width": raw.sizes.width,
                "height": raw.sizes.height,
                "mode": "RGB",
            }
            img.thumbnail(max_size, Image.LANCZOS)
            return img, info
        except Exception:
            pass

    return None, None


class PreviewWindow(ctk.CTkToplevel):
    """单张图片预览窗口。"""

    def __init__(self, parent, path):
        super().__init__(parent)
        self.path = path
        self.filename = os.path.basename(path)
        self.title(self.filename)
        self.geometry("960x700")
        self.minsize(600, 400)

        # 信息栏
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=10, pady=(8, 0))

        self.name_lb = ctk.CTkLabel(info_frame, text=self.filename,
                                     font=("", 14, "bold"), anchor="w")
        self.name_lb.pack(anchor="w")

        self.detail_lb = ctk.CTkLabel(info_frame, text="", font=("", 11), anchor="w")
        self.detail_lb.pack(anchor="w", pady=(2, 4))

        # 操作按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10)
        ctk.CTkButton(btn_frame, text="打开位置", width=100, height=28,
                       command=self._open_location).pack(side="left", padx=2)
        self.loading_lb = ctk.CTkLabel(btn_frame, text="", font=("", 11))
        self.loading_lb.pack(side="left", padx=10)

        # 图片显示区
        self.img_frame = ctk.CTkScrollableFrame(self)
        self.img_frame.pack(fill="both", expand=True, padx=10, pady=8)
        self.img_label = ctk.CTkLabel(self.img_frame, text="")
        self.img_label.pack(expand=True)

        # 异步加载
        self.loading_lb.configure(text="加载中...")
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            img, info = load_image(self.path)
            if img:
                self.after(0, lambda: self._show(img, info))
            else:
                self.after(0, lambda: self.loading_lb.configure(
                    text="无法打开此文件（rawpy 未安装或不支持此格式）"))
        except Exception as e:
            self.after(0, lambda: self.loading_lb.configure(text=f"加载失败: {e}"))

    def _show(self, img, info):
        from PIL import ImageTk
        self.photo = ImageTk.PhotoImage(img)
        self.img_label.configure(image=self.photo, text="")
        self.detail_lb.configure(
            text=f"{info.get('format', '')} | {info.get('width', '?')}\u00d7{info.get('height', '?')} | {info.get('mode', '')} | {format_size(os.path.getsize(self.path))} | {self.path}"
        )
        self.loading_lb.configure(text=f"\u663e\u793a\u5b8c\u6210 ({img.width}\u00d7{img.height})"
                                         if img.width < info.get("width", 0) or img.height < info.get("height", 0)
                                         else "")

    def _open_location(self):
        open_file_in_explorer(self.path)


def show_preview(parent, paths):
    """对一组文件路径打开预览窗口（每个文件一个窗口）。"""
    for p in paths:
        PreviewWindow(parent, p)
