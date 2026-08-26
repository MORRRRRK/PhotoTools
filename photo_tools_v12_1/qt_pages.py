import logging
logger = logging.getLogger(__name__)

"""qt_pages.py - V10 各功能页面（Qt 实现）"""

import os
import threading
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .qt_widgets import (
    CollapsiblePanel,
    PhotoCardWidget,
    RingProgressWidget,
    Toast,
)
from .scanner import scan_folders_parallel
from .quality import evaluate_photos_batch
from .proxy import FPS_OPTIONS as PROXY_FPS
from .proxy import generate_proxy_batch
from .audio_extract import AUDIO_EXTENSIONS, extract_audio_batch
from .convert import CONVERT_EXTENSIONS, DEFAULT_OUTPUT_DIR, convert_batch
from .dynamic_extract import collect_dynamic_targets, extract_dynamic_batch
from .timelapse import FPS_OPTIONS as TL_FPS
from .timelapse import generate_timelapse
from .utils import format_size, send_to_trash


class EngineThread(QThread):
    """后台执行引擎并回调进度。"""
    progress = Signal(dict)
    done = Signal(list)

    def __init__(self, paths, engine, kwargs, cancel_event, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.engine = engine
        self.kwargs = kwargs
        self.cancel_event = cancel_event

    def run(self):
        def cb(event):
            self.progress.emit(event)
        try:
            results = self.engine(
                self.paths, **self.kwargs,
                cancel_event=self.cancel_event, progress_cb=cb)
        except TypeError:
            results = self.engine(self.paths, **self.kwargs)
        self.done.emit(results)


class BatchPage(QWidget):
    """通用批处理页：文件/文件夹列表 + 参数区 + 结果表。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.thread = None
        self.cancel_event = threading.Event()
        self.engine = None
        self.engine_kwargs = {}
        self.result_headers = ["文件", "状态", "输出", "说明"]
        self.pick_folders = False
        self.file_filter = ""
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        self.add_btn = QPushButton("添加文件" if not self.pick_folders else "添加文件夹")
        self.add_btn.setProperty("accent", True)
        self.folder_btn = QPushButton("添加文件夹")
        self.sel_all_btn = QPushButton("全选")
        self.clear_btn = QPushButton("清空")
        self.count_lb = QLabel("未添加")
        top.addWidget(self.add_btn)
        top.addWidget(self.folder_btn)
        top.addWidget(self.sel_all_btn)
        top.addWidget(self.clear_btn)
        top.addWidget(self.count_lb)
        top.addStretch(1)
        self.start_btn = QPushButton("开始")
        self.start_btn.setProperty("accent", True)
        self.cancel_btn = QPushButton("停止")
        self.cancel_btn.setProperty("danger", True)
        self.cancel_btn.setEnabled(False)
        top.addWidget(self.start_btn)
        top.addWidget(self.cancel_btn)
        root.addLayout(top)

        self.config_widget = QWidget()
        self.config_lay = QFormLayout(self.config_widget)
        self.config_lay.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.config_widget)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setFixedHeight(150)
        root.addWidget(self.list)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.status_lb = QLabel("就绪")
        root.addWidget(self.status_lb)

        self.table = QTableWidget(0, len(self.result_headers))
        self.table.setHorizontalHeaderLabels(self.result_headers)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        root.addWidget(self.table, 1)

        self.add_btn.clicked.connect(self._add_files)
        self.folder_btn.clicked.connect(self._add_folder)
        self.sel_all_btn.clicked.connect(self._select_all)
        self.clear_btn.clicked.connect(self._clear)
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn.clicked.connect(self._cancel)

    def _configure(self):
        pass

    def _add_files(self):
        if self.pick_folders:
            self._add_folder()
            return
        exts = self.file_filter or "*.*"
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", "", f"支持格式 ({exts})")
        if paths:
            self._append(paths)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if not folder:
            return
        if self.pick_folders:
            self._append([folder])
            return
        found = []
        patterns = [
            p.strip().lstrip("*").lower()
            for p in self.file_filter.replace(";", " ").split()
            if p.strip()
        ]
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if any(Path(f).suffix.lower() == p for p in patterns):
                    found.append(os.path.join(root, f))
        if not found:
            QMessageBox.information(self, "提示", "文件夹中没有找到支持的文件")
            return
        self._append(found)

    def _append(self, paths):
        existing = set()
        for i in range(self.list.count()):
            existing.add(self.list.item(i).data(Qt.UserRole))
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
        self._update_count()

    def _selected_paths(self):
        return [
            self.list.item(i).data(Qt.UserRole)
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.Checked
        ]

    def _update_count(self):
        self.count_lb.setText(f"共 {self.list.count()} 项，已选 {len(self._selected_paths())} 项")

    def _select_all(self):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.Checked)
        self._update_count()

    def _clear(self):
        if self.thread and self.thread.isRunning():
            return
        self.list.clear()
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.status_lb.setText("就绪")
        self._update_count()

    def _start(self):
        if self.thread and self.thread.isRunning():
            return
        paths = self._selected_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先勾选要处理的项目")
            return
        self._configure()
        self.cancel_event = threading.Event()
        self.thread = EngineThread(
            paths, self.engine, self.engine_kwargs, self.cancel_event, self)
        self.thread.progress.connect(self._on_progress)
        self.thread.done.connect(self._on_done)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.status_lb.setText(f"队列：{len(paths)} 项")
        self.thread.start()

    def _cancel(self):
        self.cancel_event.set()
        self.cancel_btn.setEnabled(False)
        self.status_lb.setText("正在停止...")

    def _on_progress(self, event):
        kind = event.get("type", "")
        index = event.get("index", 0) + 1
        total = max(1, event.get("total", 1))
        self.progress.setValue(int(index / total * 100))
        path = event.get("path", "")
        if path:
            self.status_lb.setText(f"处理中：{os.path.basename(str(path))}")

    def _on_done(self, results):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100)
        self._fill_results(results)

    def _fill_results(self, results):
        self.table.setRowCount(len(results))
        for row, res in enumerate(results):
            values = self._row_values(res)
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.status_lb.setText("完成")

    def _row_values(self, res) -> list:
        return [
            os.path.basename(str(res.get("original", res.get("folder", "")))),
            res.get("status", ""),
            res.get("output", res.get("proxy", "")),
            res.get("error", ""),
        ]


class ScannerPage(BatchPage):
    def __init__(self, parent=None):
        self.pick_folders = True
        super().__init__(parent)
        self.add_btn.setText("添加文件夹")
        self.folder_btn.hide()
        self.engine = scan_folders_parallel
        self.result_headers = ["文件夹", "孤儿数量", "大小", "说明"]
        self.table.setColumnCount(len(self.result_headers))
        self.table.setHorizontalHeaderLabels(self.result_headers)

    def _configure(self):
        self.engine_kwargs = {"max_workers": 4}

    def _row_values(self, res):
        orphans = res.get("orphans", []) if isinstance(res, dict) else res.orphans
        total = res.get("total_size_bytes", 0) if isinstance(res, dict) else res.total_size_bytes
        folder = res.get("folder", "") if isinstance(res, dict) else res.folder
        error = res.get("error", "") if isinstance(res, dict) else res.error
        return [os.path.basename(folder), len(orphans), format_size(total), error or "完成"]


class QualityPage(BatchPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = evaluate_photos_batch
        self.result_headers = ["文件", "综合", "构图", "曝光", "清晰度", "色彩", "噪点", "建议"]
        self.table.setColumnCount(len(self.result_headers))
        self.table.setHorizontalHeaderLabels(self.result_headers)
        self.scale_opt = QComboBox()
        self.scale_opt.addItems(["严格", "普通", "宽松"])
        self.config_lay.addRow("评分尺度", self.scale_opt)
        self.ring = RingProgressWidget()
        self.ring_lb = QLabel("当前总分")
        self.ring_wrap = QWidget()
        ring_lay = QVBoxLayout(self.ring_wrap)
        ring_lay.addWidget(self.ring_lb, 0, Qt.AlignCenter)
        ring_lay.addWidget(self.ring, 0, Qt.AlignCenter)
        self.config_lay.addRow(self.ring_wrap)
        self.file_filter = "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"

    def _configure(self):
        scale_map = {"严格": "strict", "普通": "normal", "宽松": "loose"}
        self.engine_kwargs = {
            "scale": scale_map.get(self.scale_opt.currentText(), "normal")}

    def _on_done(self, results):
        super()._on_done(results)
        if results:
            last = results[-1]
            score = getattr(last, "total_score", 0)
            self.ring.animate_to(float(score))
            self.ring_lb.setText(f"总分：{score:.1f} / 100")

    def _row_values(self, res):
        return [
            getattr(res, "filename", ""),
            f"{getattr(res, 'total_score', 0):.1f}",
            f"{getattr(res, 'composition', 0):.1f}",
            f"{getattr(res, 'exposure', 0):.1f}",
            f"{getattr(res, 'sharpness', 0):.1f}",
            f"{getattr(res, 'color_score', 0):.1f}",
            f"{getattr(res, 'noise_score', 0):.1f}",
            getattr(res, "recommendation", ""),
        ]


class ProxyPage(BatchPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = generate_proxy_batch
        self.file_filter = "*.mp4 *.mov *.mkv *.avi *.m4v *.wmv *.flv *.webm *.mts *.m2ts *.3gp"
        self.res_opt = QComboBox()
        self.res_opt.addItems(["1080p", "2.7K", "4K"])
        self.fps_opt = QComboBox()
        self.fps_opt.addItems(PROXY_FPS)
        self.config_lay.addRow("分辨率", self.res_opt)
        self.config_lay.addRow("帧率", self.fps_opt)
        self.result_headers = ["文件", "状态", "代理文件", "说明"]
        self.table.setColumnCount(len(self.result_headers))
        self.table.setHorizontalHeaderLabels(self.result_headers)

    def _configure(self):
        self.engine_kwargs = {
            "resolution": self.res_opt.currentText(),
            "fps": self.fps_opt.currentText(),
            "cfg": {},
        }

    def _row_values(self, res):
        return [
            os.path.basename(str(res.get("original", ""))),
            res.get("status", ""),
            os.path.basename(str(res.get("proxy", ""))),
            res.get("error", ""),
        ]


class AudioPage(BatchPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = extract_audio_batch
        self.file_filter = " ".join(f"*{e}" for e in sorted(AUDIO_EXTENSIONS))
        self.result_headers = ["文件", "状态", "输出 WAV", "提示"]
        self.table.setColumnCount(len(self.result_headers))
        self.table.setHorizontalHeaderLabels(self.result_headers)

    def _configure(self):
        self.engine_kwargs = {"cfg": {}}

    def _row_values(self, res):
        return [
            os.path.basename(str(res.get("original", ""))),
            res.get("status", ""),
            os.path.basename(str(res.get("output", ""))),
            res.get("hint", res.get("error", "")),
        ]


class ConvertPage(BatchPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = convert_batch
        self.file_filter = " ".join(f"*{e}" for e in sorted(CONVERT_EXTENSIONS))
        self.quality_slider = QSlider()
        self.quality_slider.setOrientation(Qt.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(95)
        self.quality_lb = QLabel("95")
        self.config_lay.addRow("JPG 质量", self.quality_slider)
        self.config_lay.addRow("", self.quality_lb)
        self.quality_slider.valueChanged.connect(
            lambda v: self.quality_lb.setText(str(v)))
        self.result_headers = ["文件", "状态", "生成 JPG", "说明"]
        self.table.setColumnCount(len(self.result_headers))
        self.table.setHorizontalHeaderLabels(self.result_headers)

    def _configure(self):
        self.engine_kwargs = {
            "output_dir": DEFAULT_OUTPUT_DIR,
            "quality": self.quality_slider.value(),
        }

    def _row_values(self, res):
        return [
            os.path.basename(str(res.get("original", ""))),
            res.get("status", ""),
            res.get("output", ""),
            res.get("error", ""),
        ]


class DynamicPage(BatchPage):
    def __init__(self, parent=None):
        self.pick_folders = True
        super().__init__(parent)
        self.add_btn.setText("添加动态图文件夹")
        self.folder_btn.hide()
        self.engine = extract_dynamic_batch
        self.result_headers = ["文件夹", "状态", "说明"]
        self.table.setColumnCount(len(self.result_headers))
        self.table.setHorizontalHeaderLabels(self.result_headers)

    def _configure(self):
        paths = self._selected_paths()
        video_dir = ""
        if paths:
            video_dir = os.path.join(os.path.dirname(os.path.abspath(paths[0])), "动态视频存储")
        self.engine_kwargs = {
            "video_dir": video_dir, "move": True, "delete_originals": True}

    def _row_values(self, res):
        folder = res.get("folder", "") if isinstance(res, dict) else ""
        deletion = res.get("deletion", {}) if isinstance(res, dict) else {}
        return [
            os.path.basename(folder),
            "已删除" if deletion.get("deleted") else "保留",
            deletion.get("message", ""),
        ]


class TimelapsePage(BatchPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = generate_timelapse
        self.file_filter = "*.jpg *.jpeg"
        self.res_opt = QComboBox()
        self.res_opt.addItems(["1080P", "2K", "4K"])
        self.fps_opt = QComboBox()
        self.fps_opt.addItems(TL_FPS)
        self.crf_opt = QComboBox()
        self.crf_opt.addItems(["标准 CRF14", "高 CRF12", "最高 CRF10"])
        self.stab_cb = QCheckBox("启用增稳")
        self.out_entry = QLineEdit()
        self.out_btn = QPushButton("浏览")
        self.config_lay.addRow("分辨率", self.res_opt)
        self.config_lay.addRow("帧率", self.fps_opt)
        self.config_lay.addRow("画质", self.crf_opt)
        self.config_lay.addRow("", self.stab_cb)
        self.config_lay.addRow("输出", self.out_entry)
        self.config_lay.addRow("", self.out_btn)
        self.out_btn.clicked.connect(self._browse_out)
        self.result_headers = ["项目", "输出文件", "说明"]
        self.table.setColumnCount(len(self.result_headers))
        self.table.setHorizontalHeaderLabels(self.result_headers)

    def _browse_out(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存延时视频", "延时摄影.mp4", "MP4 (*.mp4)")
        if path:
            self.out_entry.setText(path)

    def _configure(self):
        out = self.out_entry.text().strip()
        if not out:
            out = os.path.join(os.path.expanduser("~"), "Desktop", "延时摄影.mp4")
            self.out_entry.setText(out)
        crf_text = self.crf_opt.currentText()
        crf = 14 if "标准" in crf_text else (12 if "高" in crf_text else 10)
        self.engine_kwargs = {
            "output_path": out,
            "resolution": self.res_opt.currentText(),
            "fps": int(self.fps_opt.currentText()),
            "crf": crf,
            "stabilize": self.stab_cb.isChecked(),
            "strength": "中",
        }

    def _row_values(self, res):
        return [
            "延时视频",
            res.get("output", res.get("output_path", "")),
            res.get("error", res.get("status", "")),
        ]

    def _on_done(self, results):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100)
        if isinstance(results, dict):
            results = [results]
        self._fill_results(results)


class GalleryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.paths = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        top = QHBoxLayout()
        self.add_btn = QPushButton("添加图片")
        self.add_btn.setProperty("accent", True)
        self.folder_btn = QPushButton("添加文件夹")
        self.clear_btn = QPushButton("清空")
        self.count_lb = QLabel("0 张")
        top.addWidget(self.add_btn)
        top.addWidget(self.folder_btn)
        top.addWidget(self.clear_btn)
        top.addWidget(self.count_lb)
        top.addStretch(1)
        root.addLayout(top)

        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.IconMode)
        self.grid.setIconSize(QSize(128, 128))
        self.grid.setResizeMode(QListWidget.Adjust)
        self.grid.setMovement(QListWidget.Static)
        self.grid.setSpacing(8)
        self.grid.setSelectionMode(QAbstractItemView.SingleSelection)
        self.grid.itemDoubleClicked.connect(self._show_lightbox)
        root.addWidget(self.grid, 1)

        self.add_btn.clicked.connect(self._add_files)
        self.folder_btn.clicked.connect(self._add_folder)
        self.clear_btn.clicked.connect(self._clear)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "", "图片 (*.jpg *.jpeg *.png *.webp)")
        self._add_paths(paths)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if not folder:
            return
        found = []
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    found.append(os.path.join(root, f))
        self._add_paths(found)

    def _add_paths(self, paths):
        existing = set(self.paths)
        added = 0
        for p in paths:
            key = os.path.normcase(os.path.abspath(p))
            if key in existing:
                continue
            existing.add(key)
            self.paths.append(p)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, p)
            card = PhotoCardWidget()
            card.set_meta(os.path.basename(p), Path(p).suffix.lstrip(".").upper())
            card.zoom_btn.clicked.connect(lambda _, pi=p: self._show_lightbox_for(pi))
            item.setSizeHint(card.sizeHint())
            self.grid.addItem(item)
            self.grid.setItemWidget(item, card)
            added += 1
            threading.Thread(target=self._load_thumb, args=(item, p), daemon=True).start()
        self.count_lb.setText(f"{len(self.paths)} 张")
        if not added:
            QMessageBox.information(self, "提示", "没有新增图片")

    def _load_thumb(self, item, path):
        try:
            from .gallery import make_thumbnail
            thumb = make_thumbnail(path)
            if thumb:
                pix = QPixmap(thumb)
                self.grid.itemWidget(item).set_photo(pix)
        except Exception as _exc: logger.warning("handled exception", exc_info=True)

    def _clear(self):
        self.grid.clear()
        self.paths.clear()
        self.count_lb.setText("0 张")

    def _show_lightbox(self, item):
        path = item.data(Qt.UserRole)
        self._show_lightbox_for(path)

    def _show_lightbox_for(self, path):
        dlg = LightboxDialog(self, path, self.paths)
        dlg.exec()


class LightboxDialog(QDialog):
    def __init__(self, parent, path, paths):
        super().__init__(parent)
        self.setWindowTitle("灯箱预览")
        self.resize(1000, 700)
        self.setStyleSheet("background: #000000;")
        lay = QVBoxLayout(self)
        self.lb = QLabel("加载中...")
        self.lb.setAlignment(Qt.AlignCenter)
        self.lb.setStyleSheet("color: white; border: none;")
        lay.addWidget(self.lb, 1)
        info = QLabel("")
        info.setStyleSheet("color: white; border: none; padding: 8px;")
        info.setAlignment(Qt.AlignCenter)
        lay.addWidget(info)
        self._paths = paths
        self._index = paths.index(path) if path in paths else 0
        QTimer.singleShot(0, self._load)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self._step(-1)
        elif event.key() == Qt.Key_Right:
            self._step(1)
        elif event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def _step(self, delta):
        if not self._paths:
            return
        self._index = (self._index + delta) % len(self._paths)
        self._load()

    def _load(self):
        if not self._paths:
            return
        path = self._paths[self._index]
        try:
            from .gallery import make_preview
            preview = make_preview(path)
            pix = QPixmap(preview) if preview else QPixmap(path)
            self.lb.setPixmap(pix.scaled(
                self.lb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as _exc:
            self.lb.setText("无法预览")


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        group = QGroupBox("设置")
        form = QFormLayout(group)
        self.theme_opt = QComboBox()
        self.theme_opt.addItems(["blue", "dark-blue", "gold", "green"])
        self.size_opt = QComboBox()
        self.size_opt.addItems(["小", "中", "大", "特大"])
        form.addRow("主题颜色", self.theme_opt)
        form.addRow("字体大小", self.size_opt)
        root.addWidget(group)
        root.addStretch(1)
        save = QPushButton("保存设置")
        save.setProperty("accent", True)
        save.clicked.connect(lambda: Toast(self, "设置已保存"))
        root.addWidget(save)
