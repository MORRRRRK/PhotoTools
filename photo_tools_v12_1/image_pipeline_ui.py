"""image_pipeline_ui.py - AI 图像增强模块化流水线界面 (V12.1)"""

import os
import shutil
import threading

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .auto_color_ui import CompareView
from .image_pipeline import (
    ASPECT_LABELS,
    BUILTIN_PRESETS,
    ImagePipeline,
    PipelineConfig,
    default_extra_luts_dir,
    default_presets_path,
    delete_custom_preset,
    load_custom_presets,
    save_custom_preset,
)


class ModuleRow(QFrame):
    """左侧流水线面板中的模块行：开关 + 可点击模块名。"""
    clicked = Signal(str)

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.module_name = name
        self.setObjectName("moduleRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)
        self.check = QCheckBox()
        lay.addWidget(self.check)
        self.label = QLabel(name)
        self.label.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(self.label)
        lay.addStretch(1)

    def mousePressEvent(self, event):
        self.clicked.emit(self.module_name)
        super().mousePressEvent(event)


class CropPreview(QWidget):
    """裁剪框预览：显示结果图、三分线、可拖拽的裁剪框。"""
    crop_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.pixmap = None
        self.image_size = (1, 1)
        self.crop = None
        self.editable = False
        self._drag_mode = None
        self._drag_start = None
        self._drag_orig = None

    def set_content(self, pixmap, image_size, crop, editable):
        self.pixmap = pixmap
        self.image_size = image_size
        self.crop = crop
        self.editable = bool(editable)
        self._drag_mode = None
        self.update()

    def _rect(self):
        if self.pixmap is None or self.pixmap.isNull():
            return None
        scaled = self.pixmap.scaled(
            self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return (x, y, scaled.width(), scaled.height())

    def _crop_rect_px(self, disp):
        if not self.crop or not disp:
            return None
        x, y, w, h = disp
        return (x + int(self.crop["x"] * w), y + int(self.crop["y"] * h),
                int(self.crop["w"] * w), int(self.crop["h"] * h))

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0a0a0c"))
        disp = self._rect()
        if self.pixmap and disp:
            x, y, w, h = disp
            p.drawPixmap(x, y, w, h, self.pixmap)
            p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.DashLine))
            for i in (1, 2):
                px = x + w * i / 3.0
                py = y + h * i / 3.0
                p.drawLine(int(px), y, int(px), y + h)
                p.drawLine(x, int(py), x + w, int(py))
            crop = self._crop_rect_px(disp)
            if crop:
                cx, cy, cw, ch = crop
                p.setPen(QPen(QColor("#6366f1"), 2))
                p.drawRect(cx, cy, cw, ch)
                p.setBrush(QColor("#6366f1"))
                p.setPen(Qt.NoPen)
                for hx, hy in ((cx, cy), (cx + cw, cy), (cx, cy + ch), (cx + cw, cy + ch)):
                    p.drawRect(hx - 4, hy - 4, 8, 8)
        p.end()

    def _hit_mode(self, pos):
        disp = self._rect()
        crop = self._crop_rect_px(disp)
        if not crop or not disp:
            return None
        cx, cy, cw, ch = crop
        x, y = pos.x(), pos.y()
        for hx, hy in ((cx, cy), (cx + cw, cy), (cx, cy + ch), (cx + cw, cy + ch)):
            if abs(x - hx) <= 8 and abs(y - hy) <= 8:
                return "resize"
        if cx <= x <= cx + cw and cy <= y <= cy + ch:
            return "move"
        return None

    def mousePressEvent(self, event):
        if not self.editable or event.button() != Qt.LeftButton:
            return
        self._drag_mode = self._hit_mode(event.position().toPoint())
        if self._drag_mode:
            self._drag_start = event.position().toPoint()
            self._drag_orig = dict(self.crop)

    def mouseMoveEvent(self, event):
        if not self._drag_mode or not self._drag_orig:
            return
        disp = self._rect()
        if not disp:
            return
        _, _, w, h = disp
        dx = (event.position().x() - self._drag_start.x()) / max(w, 1)
        dy = (event.position().y() - self._drag_start.y()) / max(h, 1)
        crop = dict(self._drag_orig)
        if self._drag_mode == "move":
            crop["x"] = float(min(max(0.0, crop["x"] + dx), 1.0 - crop["w"]))
            crop["y"] = float(min(max(0.0, crop["y"] + dy), 1.0 - crop["h"]))
        else:
            crop["w"] = float(min(max(0.1, crop["w"] + dx), 1.0 - crop["x"]))
            crop["h"] = float(min(max(0.1, crop["h"] + dy), 1.0 - crop["y"]))
        self.crop = crop
        self.crop_changed.emit(crop)
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag_mode = None
        self._drag_start = None
        self._drag_orig = None


class PipelineWorker(QThread):
    progress = Signal(dict)
    done = Signal(dict)

    def __init__(self, pipeline, paths, output_dir, config, cancel, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.paths = paths
        self.output_dir = output_dir
        self.config = config
        self.cancel = cancel

    def run(self):
        def cb(event):
            self.progress.emit(event)
        result = self.pipeline.process_batch(
            self.paths, self.output_dir, self.config,
            cancel_event=self.cancel, progress_cb=cb)
        self.done.emit(result)


class PreviewWorker(QThread):
    finished_preview = Signal(dict)

    def __init__(self, pipeline, path, config, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.path = path
        self.config = config

    def run(self):
        try:
            from .image_pipeline import load_image_bgr, read_exif_info
            import cv2
            img = load_image_bgr(self.path)
            h, w = img.shape[:2]
            if max(h, w) > 1280:
                scale = 1280 / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)),
                                 interpolation=cv2.INTER_AREA)
            result = self.pipeline.process(img, self.config, read_exif_info(self.path))
            self.finished_preview.emit({"orig": img, "result": result})
        except Exception as e:
            self.finished_preview.emit({"error": str(e)})


class ImagePipelinePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.paths = []
        self.pipeline = None
        self.worker = None
        self.preview_worker = None
        self.cancel_event = threading.Event()
        self.preview_img_size = (1, 1)
        self._output_map = {}
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._refresh_preview)
        self._build_ui()
        self._reload_presets()

    def _ensure_pipeline(self):
        if self.pipeline is not None:
            return
        base = os.path.dirname(os.path.abspath(__file__))
        self.pipeline = ImagePipeline(
            models_dir=os.path.join(base, "models"),
            luts_dir=os.path.join(base, "luts"),
            extra_luts_dir=default_extra_luts_dir())
        if self.lut_combo.count() == 0:
            self.lut_combo.addItems(self.pipeline.get_lut_names())

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("AI 图像增强")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e8e8ed;")
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(140)
        self.save_preset_btn = QPushButton("保存预设")
        self.del_preset_btn = QPushButton("删除预设")
        top.addWidget(title)
        top.addSpacing(16)
        top.addWidget(QLabel("预设:"))
        top.addWidget(self.preset_combo)
        top.addWidget(self.save_preset_btn)
        top.addWidget(self.del_preset_btn)
        top.addStretch(1)
        root.addLayout(top)

        bar = QHBoxLayout()
        self.add_btn = QPushButton("添加图片")
        self.add_btn.setProperty("accent", True)
        self.folder_btn = QPushButton("添加文件夹")
        self.clear_btn = QPushButton("清空")
        self.count_lb = QLabel("共 0 张")
        bar.addWidget(self.add_btn)
        bar.addWidget(self.folder_btn)
        bar.addWidget(self.clear_btn)
        bar.addWidget(self.count_lb)
        bar.addStretch(1)
        root.addLayout(bar)

        split = QHBoxLayout()
        split.setSpacing(10)
        left = self._build_pipeline_panel()
        split.addWidget(left, 0)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setFixedWidth(230)
        self.list.currentRowChanged.connect(self._refresh_preview)
        split.addWidget(self.list, 0)

        right = QVBoxLayout()
        right.setSpacing(8)
        preview_row = QHBoxLayout()
        self.compare = CompareView()
        self.compare.setMinimumHeight(260)
        self.crop_preview = CropPreview()
        self.crop_preview.setMinimumWidth(260)
        preview_row.addWidget(self.compare, 3)
        preview_row.addWidget(self.crop_preview, 2)
        right.addLayout(preview_row, 1)
        self.param_stack = QStackedWidget()
        self.param_stack.setMinimumHeight(150)
        right.addWidget(self.param_stack, 0)
        right_widget = QWidget()
        right_widget.setLayout(right)
        split.addWidget(right_widget, 1)
        root.addLayout(split, 1)

        bottom = QHBoxLayout()
        self.out_entry = QLineEdit()
        self.out_entry.setPlaceholderText("输出目录，留空则输出到第一张图片所在目录")
        self.out_btn = QPushButton("浏览")
        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.status_lb = QLabel("就绪")
        self.run_btn = QPushButton("运行流水线")
        self.run_btn.setProperty("accent", True)
        self.cancel_btn = QPushButton("停止")
        self.cancel_btn.setProperty("danger", True)
        self.cancel_btn.setEnabled(False)
        bottom.addWidget(QLabel("输出:"))
        bottom.addWidget(self.out_entry, 1)
        bottom.addWidget(self.out_btn)
        bottom.addWidget(self.progress)
        bottom.addWidget(self.status_lb)
        bottom.addWidget(self.run_btn)
        bottom.addWidget(self.cancel_btn)
        root.addLayout(bottom)

        self.add_btn.clicked.connect(self._add_files)
        self.folder_btn.clicked.connect(self._add_folder)
        self.clear_btn.clicked.connect(self._clear)
        self.out_btn.clicked.connect(self._browse_out)
        self.run_btn.clicked.connect(self._start)
        self.cancel_btn.clicked.connect(self._cancel)
        self.save_preset_btn.clicked.connect(self._save_preset)
        self.del_preset_btn.clicked.connect(self._delete_preset)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self.crop_preview.crop_changed.connect(self._on_manual_crop)
        self._build_params()
        self._apply_config(PipelineConfig())

    def _build_pipeline_panel(self):
        panel = QScrollArea()
        panel.setFixedWidth(270)
        panel.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        self.module_checks = {}
        self.module_rows = {}

        def add_header(text):
            h = QLabel(text)
            h.setStyleSheet("color: #8a8a96; font-size: 11px; font-weight: 700;"
                            "padding: 8px 4px 2px 4px;")
            lay.addWidget(h)

        def add_row(name, checked=True):
            row = ModuleRow(name)
            row.check.setChecked(checked)
            row.clicked.connect(self._on_module_clicked)
            lay.addWidget(row)
            self.module_checks[name] = row.check
            self.module_rows[name] = row
            row.check.toggled.connect(self._on_config_changed)

        add_header("阶段一：几何校正")
        add_row("镜头畸变校正")
        add_row("透视校正")
        add_row("水平校正")

        add_header("阶段二：调色增强")
        add_row("曝光校正")
        add_row("综合调色")
        add_row("风格化 LUT")

        add_header("阶段三：构图裁剪")
        crop_box = QFrame()
        crop_lay = QHBoxLayout(crop_box)
        crop_lay.setContentsMargins(10, 6, 10, 6)
        self.crop_group = QButtonGroup(self)
        self.crop_radios = {}
        for text in ("不裁剪", "GAIC", "人像", "手动"):
            rb = QRadioButton(text)
            self.crop_group.addButton(rb)
            self.crop_radios[text] = rb
            crop_lay.addWidget(rb)
            rb.toggled.connect(self._on_crop_radio)
        self.crop_radios["不裁剪"].setChecked(True)
        lay.addWidget(crop_box)

        ratio_row = QFrame()
        ratio_lay = QHBoxLayout(ratio_row)
        ratio_lay.setContentsMargins(10, 6, 10, 6)
        ratio_lay.addWidget(QLabel("裁剪比例"))
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(list(ASPECT_LABELS.keys()))
        ratio_lay.addWidget(self.aspect_combo, 1)
        lay.addWidget(ratio_row)
        self.aspect_combo.currentTextChanged.connect(self._on_config_changed)

        fill_row = ModuleRow("内容感知填充")
        fill_row.check.setChecked(True)
        fill_row.clicked.connect(self._on_module_clicked)
        lay.addWidget(fill_row)
        self.module_checks["内容感知填充"] = fill_row.check
        self.module_rows["内容感知填充"] = fill_row
        fill_row.check.toggled.connect(self._on_config_changed)

        lay.addStretch(1)
        panel.setWidget(inner)
        return panel

    def _build_params(self):
        self.param_pages = {}

        def page():
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(8, 8, 8, 8)
            return w, lay

        hint, hint_lay = page()
        hint_lay.addWidget(QLabel("点击左侧模块查看参数"))
        self.param_stack.addWidget(hint)

        def add_slider(lay, label, lo, hi, val):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(lo, hi)
            slider.setValue(val)
            value_lb = QLabel(f"{val}%")
            slider.valueChanged.connect(
                lambda v, lb=value_lb: lb.setText(f"{v}%"))
            slider.valueChanged.connect(self._on_config_changed)
            row.addWidget(slider, 1)
            row.addWidget(value_lb)
            lay.addLayout(row)
            return slider

        def add_combo(lay, label, items, current=None):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            combo = QComboBox()
            combo.addItems(items)
            if current in items:
                combo.setCurrentText(current)
            combo.currentTextChanged.connect(self._on_config_changed)
            row.addWidget(combo, 1)
            lay.addLayout(row)
            return combo

        lens_w, lens_lay = page()
        lens_lay.addWidget(QLabel("自动读取 EXIF 相机/镜头信息并匹配 LensFun 数据库；无镜头数据时自动跳过。"))
        self.lens_strength = add_slider(lens_lay, "校正强度", 0, 100, 100)
        self.param_pages["镜头畸变校正"] = lens_w
        self.param_stack.addWidget(lens_w)

        persp_w, persp_lay = page()
        self.persp_mode = add_combo(persp_lay, "校正模式", ["仅垂直", "垂直+水平"])
        self.persp_strength = add_slider(persp_lay, "校正强度", 0, 100, 100)
        self.param_pages["透视校正"] = persp_w
        self.param_stack.addWidget(persp_w)

        horiz_w, horiz_lay = page()
        horiz_lay.addWidget(QLabel("自动检测地平线角度；角度小于 0.1° 时不旋转。"))
        self.horizon_angle_lb = QLabel("自动检测角度：--")
        horiz_lay.addWidget(self.horizon_angle_lb)
        row = QHBoxLayout()
        row.addWidget(QLabel("手动微调"))
        self.horizon_manual = QSlider(Qt.Horizontal)
        self.horizon_manual.setRange(-150, 150)
        self.horizon_manual.setValue(0)
        self.horizon_manual.valueChanged.connect(self._on_config_changed)
        self.horizon_manual_lb = QLabel("0.0°")
        self.horizon_manual.valueChanged.connect(
            lambda v: self.horizon_manual_lb.setText(f"{v / 10.0:.1f}°"))
        row.addWidget(self.horizon_manual, 1)
        row.addWidget(self.horizon_manual_lb)
        horiz_lay.addLayout(row)
        self.param_pages["水平校正"] = horiz_w
        self.param_stack.addWidget(horiz_w)

        sci_w, sci_lay = page()
        self.sci_mode = add_combo(sci_lay, "增强范围", ["全局增强", "仅暗部增强"])
        self.sci_strength = add_slider(sci_lay, "增强强度", 0, 100, 100)
        self.param_pages["曝光校正"] = sci_w
        self.param_stack.addWidget(sci_w)

        hdr_w, hdr_lay = page()
        self.hdr_style = add_combo(hdr_lay, "风格", ["自然", "鲜艳", "柔和"])
        self.hdr_strength = add_slider(hdr_lay, "调色强度", 0, 100, 100)
        self.param_pages["综合调色"] = hdr_w
        self.param_stack.addWidget(hdr_w)

        lut_w, lut_lay = page()
        self.lut_combo = QComboBox()
        self.lut_combo.currentTextChanged.connect(self._on_config_changed)
        row = QHBoxLayout()
        row.addWidget(QLabel("LUT 预设"))
        row.addWidget(self.lut_combo, 1)
        lut_lay.addLayout(row)
        self.lut_strength = add_slider(lut_lay, "强度", 0, 100, 70)
        import_btn = QPushButton("导入自定义 .cube")
        import_btn.clicked.connect(self._import_lut)
        lut_lay.addWidget(import_btn)
        self.param_pages["风格化 LUT"] = lut_w
        self.param_stack.addWidget(lut_w)

        gaic_w, gaic_lay = page()
        self.gaic_topk = add_combo(gaic_lay, "候选数量", ["1", "3", "5"], "3")
        self.gaic_idx_lb = QLabel("候选 1/3")
        gaic_lay.addWidget(self.gaic_idx_lb)
        nav = QHBoxLayout()
        prev_btn = QPushButton("上一候选")
        next_btn = QPushButton("下一候选")
        prev_btn.clicked.connect(lambda: self._step_gaic(-1))
        next_btn.clicked.connect(lambda: self._step_gaic(1))
        nav.addWidget(prev_btn)
        nav.addWidget(next_btn)
        gaic_lay.addLayout(nav)
        self.param_pages["GAIC 自动裁剪"] = gaic_w
        self.param_stack.addWidget(gaic_w)

        port_w, port_lay = page()
        port_lay.addWidget(QLabel("检测最大人脸，将眼睛落在上三分线；无人脸时回退中心裁剪。"))
        self.param_pages["人像构图"] = port_w
        self.param_stack.addWidget(port_w)

        ratio_w, ratio_lay = page()
        ratio_lay.addWidget(QLabel("裁剪比例配合 GAIC、人像或手动裁剪使用。"))
        self.param_pages["裁剪比例"] = ratio_w
        self.param_stack.addWidget(ratio_w)

        manual_w, manual_lay = page()
        manual_lay.addWidget(QLabel("在右侧裁剪框预览中拖拽移动，拖动四角缩放。"))
        reset_btn = QPushButton("重置裁剪框")
        reset_btn.clicked.connect(self._reset_manual_crop)
        manual_lay.addWidget(reset_btn)
        self.param_pages["手动裁剪"] = manual_w
        self.param_stack.addWidget(manual_w)

        fill_w, fill_lay = page()
        self.fill_quality = add_combo(fill_lay, "填充质量", ["快速", "高质量"])
        fill_lay.addWidget(QLabel("当前版本使用 OpenCV inpaint；LaMa 模型存在时自动启用高质量档。"))
        self.param_pages["内容感知填充"] = fill_w
        self.param_stack.addWidget(fill_w)

        self._current_module = None

    def _on_module_clicked(self, name):
        self._current_module = name
        page = self.param_pages.get(name)
        if page is not None:
            self.param_stack.setCurrentWidget(page)

    def _on_crop_radio(self):
        self._on_config_changed()
        if not hasattr(self, "param_pages"):
            return
        for text, rb in self.crop_radios.items():
            if rb.isChecked() and text in self.param_pages:
                self._on_module_clicked(text)

    def _on_config_changed(self, *_args):
        self._output_map = {}
        self._debounce.start()

    def _on_manual_crop(self, crop):
        self._debounce.start()

    def _current_config(self):
        cfg = PipelineConfig()
        cfg.lens_correction_enabled = self.module_checks["镜头畸变校正"].isChecked()
        cfg.lens_correction_strength = self.lens_strength.value() / 100.0
        cfg.perspective_correction_enabled = self.module_checks["透视校正"].isChecked()
        cfg.perspective_correction_mode = "both" if self.persp_mode.currentText() == "垂直+水平" else "vertical"
        cfg.perspective_correction_strength = self.persp_strength.value() / 100.0
        cfg.horizon_correction_enabled = self.module_checks["水平校正"].isChecked()
        cfg.horizon_correction_angle = self.horizon_manual.value() / 10.0
        cfg.sci_enabled = self.module_checks["曝光校正"].isChecked()
        cfg.sci_strength = self.sci_strength.value() / 100.0
        cfg.sci_shadow_only = self.sci_mode.currentText() == "仅暗部增强"
        cfg.hdrnet_enabled = self.module_checks["综合调色"].isChecked()
        cfg.hdrnet_strength = self.hdr_strength.value() / 100.0
        cfg.hdrnet_style = self.hdr_style.currentText()
        cfg.lut_enabled = self.module_checks["风格化 LUT"].isChecked()
        cfg.lut_name = self.lut_combo.currentText()
        cfg.lut_strength = self.lut_strength.value() / 100.0
        for text, rb in self.crop_radios.items():
            if rb.isChecked():
                cfg.crop_mode = {"不裁剪": "none", "GAIC": "gaic",
                                 "人像": "portrait", "手动": "manual"}[text]
                break
        selected_aspect = self.aspect_combo.currentText()
        cfg.crop_aspect_ratio = ASPECT_LABELS.get(selected_aspect)
        if cfg.crop_aspect_ratio == "original":
            cfg.crop_aspect_ratio = None
        cfg.gaic_top_k = int(self.gaic_topk.currentText())
        cfg.gaic_selected_idx = getattr(self, "_gaic_idx", 0)
        if cfg.crop_mode == "manual":
            crop = getattr(self, "_manual_crop_norm", None)
            w, h = self.preview_img_size
            if crop is None and w > 1 and h > 1:
                bw, bh = int(w * 0.8), int(h * 0.8)
                bx, by = (w - bw) // 2, (h - bh) // 2
                crop = {"x": bx / w, "y": by / h, "w": bw / w, "h": bh / h}
                self._manual_crop_norm = crop
            if crop:
                cfg.manual_crop = {
                    "x": int(crop["x"] * w), "y": int(crop["y"] * h),
                    "w": int(crop["w"] * w), "h": int(crop["h"] * h)}
        cfg.content_aware_fill_enabled = self.module_checks["内容感知填充"].isChecked()
        cfg.fill_quality = "high" if self.fill_quality.currentText() == "高质量" else "fast"
        return cfg

    def _apply_config(self, cfg):
        self.module_checks["镜头畸变校正"].setChecked(cfg.lens_correction_enabled)
        self.lens_strength.setValue(int(cfg.lens_correction_strength * 100))
        self.module_checks["透视校正"].setChecked(cfg.perspective_correction_enabled)
        self.persp_mode.setCurrentText("垂直+水平" if cfg.perspective_correction_mode == "both" else "仅垂直")
        self.persp_strength.setValue(int(cfg.perspective_correction_strength * 100))
        self.module_checks["水平校正"].setChecked(cfg.horizon_correction_enabled)
        self.horizon_manual.setValue(int(cfg.horizon_correction_angle * 10))
        self.module_checks["曝光校正"].setChecked(cfg.sci_enabled)
        self.sci_strength.setValue(int(cfg.sci_strength * 100))
        self.sci_mode.setCurrentText("仅暗部增强" if cfg.sci_shadow_only else "全局增强")
        self.module_checks["综合调色"].setChecked(cfg.hdrnet_enabled)
        self.hdr_strength.setValue(int(cfg.hdrnet_strength * 100))
        if cfg.hdrnet_style in ("自然", "鲜艳", "柔和"):
            self.hdr_style.setCurrentText(cfg.hdrnet_style)
        self.module_checks["风格化 LUT"].setChecked(cfg.lut_enabled)
        if self.lut_combo.findText(cfg.lut_name) >= 0:
            self.lut_combo.setCurrentText(cfg.lut_name)
        self.lut_strength.setValue(int(cfg.lut_strength * 100))
        mode_map = {"none": "不裁剪", "gaic": "GAIC", "portrait": "人像", "manual": "手动"}
        self.crop_radios[mode_map.get(cfg.crop_mode, "不裁剪")].setChecked(True)
        aspect_label = "自由"
        for label, value in ASPECT_LABELS.items():
            if value == cfg.crop_aspect_ratio:
                aspect_label = label
                break
        self.aspect_combo.setCurrentText(aspect_label)
        self.gaic_topk.setCurrentText(str(cfg.gaic_top_k))
        self.module_checks["内容感知填充"].setChecked(cfg.content_aware_fill_enabled)
        self.fill_quality.setCurrentText("高质量" if cfg.fill_quality == "high" else "快速")

    def _reload_presets(self):
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItems(list(BUILTIN_PRESETS.keys()))
        custom = load_custom_presets()
        self.preset_combo.addItems(list(custom.keys()))
        self.preset_combo.blockSignals(False)

    def _on_preset_changed(self, name):
        if not name:
            return
        cfg = None
        if name in BUILTIN_PRESETS:
            cfg = BUILTIN_PRESETS[name]
        else:
            data = load_custom_presets().get(name)
            if data:
                cfg = PipelineConfig(**data)
        if cfg is not None:
            self._apply_config(cfg)
            self._refresh_preview()

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "保存预设", "预设名称：")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in BUILTIN_PRESETS:
            QMessageBox.information(self, "提示", "不能覆盖内置预设，请换一个名称")
            return
        save_custom_preset(name, self._current_config())
        self._reload_presets()
        self.preset_combo.setCurrentText(name)

    def _delete_preset(self):
        name = self.preset_combo.currentText()
        if not name or name in BUILTIN_PRESETS:
            QMessageBox.information(self, "提示", "内置预设不可删除")
            return
        if QMessageBox.question(self, "删除预设", f"确认删除预设“{name}”？") == QMessageBox.Yes:
            delete_custom_preset(name)
            self._reload_presets()

    def _import_lut(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 .cube 文件", "", "LUT 文件 (*.cube)")
        if not path:
            return
        try:
            target = os.path.join(default_extra_luts_dir(), os.path.basename(path))
            shutil.copyfile(path, target)
            self._ensure_pipeline()
            self.lut_combo.clear()
            self.lut_combo.addItems(self.pipeline.get_lut_names())
            QMessageBox.information(self, "完成", "LUT 已导入，可在“风格化 LUT”中选择")
        except Exception as e:
            QMessageBox.warning(self, "导入失败", str(e))

    def _step_gaic(self, delta):
        idx = getattr(self, "_gaic_idx", 0)
        top = int(self.gaic_topk.currentText())
        idx = max(0, min(top - 1, idx + delta))
        self._gaic_idx = idx
        self.gaic_idx_lb.setText(f"候选 {idx + 1}/{top}")
        self._refresh_preview()

    def _reset_manual_crop(self):
        self._manual_crop_norm = None
        self.crop_preview.set_content(None, (1, 1), None, False)
        self._refresh_preview()

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "", "图片 (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp)")
        self._append(paths)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if not folder:
            return
        found = []
        from .image_pipeline import SUPPORTED_EXTS
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS:
                    found.append(os.path.join(root, f))
        self._append(found)

    def _append(self, paths):
        existing = {self.list.item(i).data(Qt.UserRole)
                    for i in range(self.list.count())}
        for p in paths:
            key = os.path.normcase(os.path.abspath(p))
            if key in existing:
                continue
            existing.add(key)
            item = QListWidgetItem(os.path.basename(p))
            item.setData(Qt.UserRole, p)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.list.addItem(item)
        self.count_lb.setText(f"共 {self.list.count()} 张")

    def _clear(self):
        if self.worker and self.worker.isRunning():
            return
        if hasattr(self, "list"):
            self.list.clear()
        self.compare.set_images(None, None)
        self.crop_preview.set_content(None, (1, 1), None, False)
        self.progress.setValue(0)
        self.status_lb.setText("就绪")
        self.count_lb.setText("共 0 张")

    def _browse_out(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.out_entry.setText(folder)

    def _selected_paths(self):
        return [
            self.list.item(i).data(Qt.UserRole)
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.Checked
        ]

    def _start(self):
        if self.worker and self.worker.isRunning():
            return
        paths = self._selected_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先勾选要处理的图片")
            return
        self._ensure_pipeline()
        output_dir = self.out_entry.text().strip()
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(paths[0])), "_enhanced")
            self.out_entry.setText(output_dir)
        self.cancel_event = threading.Event()
        config = self._current_config()
        self.worker = PipelineWorker(
            self.pipeline, paths, output_dir, config, self.cancel_event, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_done)
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setValue(0)
        self.status_lb.setText(f"队列：{len(paths)} 张")
        self.worker.start()

    def _cancel(self):
        self.cancel_event.set()
        self.cancel_btn.setEnabled(False)
        self.status_lb.setText("正在停止...")

    def _on_progress(self, event):
        index = event.get("index", 0) + 1
        total = max(1, event.get("total", 1))
        self.progress.setValue(int(index / total * 100))
        self.status_lb.setText(
            f"当前：{os.path.basename(str(event.get('path', '')))}  {index}/{total}")

    def _on_done(self, result):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100)
        ok = result.get("ok", 0)
        failed = result.get("failed", 0)
        self._output_map = result.get("outputs", {}) or {}
        self.status_lb.setText(f"完成：成功 {ok}，失败 {failed}（已生成版本文件，不覆盖）")
        if result.get("error"):
            QMessageBox.warning(self, "处理失败", result["error"])
        elif failed:
            reasons = []
            for path, reason in result.get("failed_files", [])[:5]:
                reasons.append(f"{os.path.basename(str(path))}: {reason}")
            detail = "\n".join(reasons) if reasons else "失败原因未记录"
            QMessageBox.warning(
                self, "部分失败",
                f"成功 {ok}，失败 {failed}\n失败示例：\n{detail}\n\n"
                f"输出目录：{result.get('output_dir', '')}")
        else:
            QMessageBox.information(
                self, "完成", f"成功 {ok} 张\n输出目录：{result.get('output_dir', '')}")
        self._refresh_preview()

    def _refresh_preview(self):
        if not hasattr(self, "list") or self.list.currentRow() < 0:
            return
        path = self.list.currentItem().data(Qt.UserRole)
        out_path = self._output_map.get(path)
        if out_path and os.path.exists(out_path):
            self._show_generated_pair(path, out_path)
            return
        self._ensure_pipeline()
        config = self._current_config()
        self.preview_worker = PreviewWorker(self.pipeline, path, config, self)
        self.preview_worker.finished_preview.connect(self._on_preview)
        self.preview_worker.start()

    def _show_generated_pair(self, path, out_path):
        try:
            from .image_pipeline import load_image_bgr
            import cv2
            orig = load_image_bgr(path)
            generated = load_image_bgr(out_path)

            def downscale(img):
                h, w = img.shape[:2]
                if max(h, w) > 1280:
                    scale = 1280 / max(h, w)
                    img = cv2.resize(img, (int(w * scale), int(h * scale)),
                                     interpolation=cv2.INTER_AREA)
                return img

            orig = downscale(orig)
            generated = downscale(generated)
            self.preview_img_size = (orig.shape[1], orig.shape[0])
            orig_pix = self._to_pixmap(orig)
            result_pix = self._to_pixmap(generated)
            self.compare.set_images(orig_pix, result_pix)
            self.crop_preview.set_content(result_pix, (orig.shape[1], orig.shape[0]),
                                          None, False)
            self.status_lb.setText(f"原片 + 本次生成：{os.path.basename(out_path)}")
        except Exception as e:
            self.status_lb.setText(f"加载生成照片失败：{e}")

    def _on_preview(self, data):
        if data.get("error"):
            self.status_lb.setText(f"预览失败：{data['error']}")
            return
        try:
            import cv2
            orig = data["orig"]
            result = data["result"]
            h, w = orig.shape[:2]
            self.preview_img_size = (w, h)
            orig_pix = self._to_pixmap(orig)
            result_pix = self._to_pixmap(result.image)
            self.compare.set_images(orig_pix, result_pix)
            crop = result.crop_box
            editable = self._current_config().crop_mode == "manual"
            if editable and crop is None:
                bw, bh = int(w * 0.8), int(h * 0.8)
                norm = {"x": (w - bw) / 2 / max(w, 1), "y": (h - bh) / 2 / max(h, 1),
                        "w": bw / max(w, 1), "h": bh / max(h, 1)}
                self._manual_crop_norm = norm
                self.crop_preview.set_content(result_pix, (w, h), norm, True)
            elif crop and result.image.shape[:2] != orig.shape[:2]:
                norm = {"x": crop["x"] / max(w, 1), "y": crop["y"] / max(h, 1),
                        "w": crop["w"] / max(w, 1), "h": crop["h"] / max(h, 1)}
                self._manual_crop_norm = norm
                self.crop_preview.set_content(result_pix, (w, h), norm, editable)
            else:
                self._manual_crop_norm = None
                self.crop_preview.set_content(result_pix, (w, h), None, editable)
            self.status_lb.setText(
                f"预览完成 · {len(result.modules_applied)} 个模块 · {result.elapsed_ms}ms")
            if hasattr(self, "horizon_angle_lb"):
                angle = next((n for n in result.notes if "水平校正完成" in n), None)
                self.horizon_angle_lb.setText(f"自动检测角度：{angle or '--'}")
        except Exception as e:
            self.status_lb.setText(f"预览失败：{e}")

    @staticmethod
    def _to_pixmap(bgr):
        import cv2
        from PySide6.QtGui import QImage
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        data = rgb.tobytes()
        qimg = QImage(data, rgb.shape[1], rgb.shape[0], rgb.shape[1] * 3,
                      QImage.Format_RGB888).copy()
        return QPixmap.fromImage(qimg)
