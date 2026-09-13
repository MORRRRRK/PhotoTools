"""image_view.py - 等比自适应图片预览控件 (V13)"""

import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

RAW_EXTS = {".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".dng",
            ".raf", ".orf", ".rw2", ".pef", ".srw", ".x3f", ".3fr", ".kdc",
            ".dcr", ".mef", ".mos", ".mrw"}


def theme_color(key: str, fallback: str):
    """读取当前主题中的颜色 token（用于自绘控件背景）。"""
    from PySide6.QtGui import QColor
    try:
        from .theme import ThemeManager, tokens
        manager = ThemeManager.instance()
        return QColor(tokens(manager.resolved(), manager.accent).get(key, fallback))
    except Exception:
        return QColor(fallback)


def _pixmap_from_array(arr) -> QPixmap:
    import cv2
    rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    image = QImage(rgb.data, width, height, width * 3, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(image)


def load_preview_pixmap(path: str, max_side: int = 2600) -> QPixmap:
    """读取用于预览的 QPixmap：RAW 走内嵌缩略图，普通图片走 EXIF 方向校正后降采样。"""
    ext = os.path.splitext(path)[1].lower()
    pixmap = QPixmap()
    if ext in RAW_EXTS:
        try:
            import rawpy
            with rawpy.imread(path) as raw:
                thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                pixmap.loadFromData(thumb.data)
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                pixmap = _pixmap_from_array(thumb.data)
        except Exception:
            pixmap = QPixmap()
    if pixmap.isNull():
        try:
            from PIL import Image, ImageOps
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                rgb = img.convert("RGB")
                if max(rgb.size) > max_side:
                    scale = max_side / max(rgb.size)
                    rgb = rgb.resize((int(rgb.size[0] * scale), int(rgb.size[1] * scale)),
                                     Image.LANCZOS)
                data = rgb.tobytes("raw", "RGB")
                image = QImage(data, rgb.size[0], rgb.size[1], rgb.size[0] * 3,
                               QImage.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(image)
        except Exception:
            pixmap = QPixmap(path)
    return pixmap


class AspectImageView(QLabel):
    """按窗口尺寸等比缩放显示图片，始终保持完整、不变形。"""

    def __init__(self, parent=None, placeholder: str = "选择文件后在此预览"):
        super().__init__(parent)
        self.setObjectName("imageCanvas")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(140, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setText(placeholder)
        self._source = QPixmap()

    def set_image_path(self, path: str) -> bool:
        pixmap = load_preview_pixmap(path)
        if pixmap.isNull():
            self.clear_image()
            return False
        self._source = pixmap
        self._rescale()
        return True

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._source = pixmap or QPixmap()
        self._rescale()

    def clear_image(self, placeholder: str = "无法预览该文件") -> None:
        self._source = QPixmap()
        self.setPixmap(QPixmap())
        self.setText(placeholder)

    def source_pixmap(self) -> QPixmap:
        return self._source

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._source.isNull():
            return
        target = QSize(max(1, self.width() - 8), max(1, self.height() - 8))
        scaled = self._source.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)
