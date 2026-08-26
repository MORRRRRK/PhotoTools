"""auto_color_ui.py - AI 自动调色界面 (V12)"""

import os
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .auto_color import SUPPORTED_EXTS, AutoColorEngine, imread_unicode


class CompareView(QWidget):
    """原图 / 调色后左右拖动对比视图。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.orig = None
        self.result = None
        self.split = 0.5
        self.setMinimumHeight(260)
        self.setStyleSheet("background: #0a0a0c; border-radius: 6px;")

    def set_images(self, orig: QPixmap, result: QPixmap):
        self.orig = orig
        self.result = result
        self.update()

    def mousePressEvent(self, event):
        self._update_split(event.position().x())

    def mouseMoveEvent(self, event):
        self._update_split(event.position().x())

    def _update_split(self, x):
        if self.width() > 0:
            self.split = max(0.0, min(1.0, x / self.width()))
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0a0a0c"))
        w, h = self.width(), self.height()
        if self.result:
            p.drawPixmap(self.rect(), self.result)
        if self.orig:
            cut = int(w * self.split)
            p.save()
            p.setClipRect(0, 0, cut, h)
            p.drawPixmap(self.rect(), self.orig)
            p.restore()
            p.setPen(QPen(QColor("#e8e8ed"), 2))
            p.drawLine(cut, 0, cut, h)
            p.setBrush(QColor("#6366f1"))
            p.setPen(Qt.NoPen)
            p.drawRect(cut - 5, h // 2 - 12, 10, 24)
        p.end()


class AutoColorWorker(QThread):
    progress = Signal(dict)
    done = Signal(dict)

    def __init__(self, engine, paths, output_dir, params, cancel, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.paths = paths
        self.output_dir = output_dir
        self.params = params
        self.cancel = cancel

    def run(self):
        def cb(event):
            self.progress.emit(event)
        result = self.engine.process_batch(
            self.paths, self.output_dir, cancel_event=self.cancel,
            progress_cb=cb, **self.params)
        self.done.emit(result)


class AutoColorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.paths = []
        self.engine = None
        self.worker = None
        self.cancel_event = threading.Event()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.add_btn = QPushButton("添加图片")
        self.add_btn.setProperty("accent", True)
        self.folder_btn = QPushButton("添加文件夹")
        self.clear_btn = QPushButton("清空")
        self.count_lb = QLabel("共 0 张")
        top.addWidget(self.add_btn)
        top.addWidget(self.folder_btn)
        top.addWidget(self.clear_btn)
        top.addWidget(self.count_lb)
        top.addStretch(1)
        root.addLayout(top)

        params = QFrame()
        params.setObjectName("overviewCard")
        form = QFormLayout(params)
        form.setContentsMargins(16, 12, 16, 12)
        self.mode_opt = QComboBox()
        self.mode_opt.addItems(["快速增强（传统算法）", "AI 专业调色"])
        self.sci_cb = QCheckBox("曝光校正 (SCI)")
        self.sci_cb.setChecked(True)
        self.hdr_cb = QCheckBox("综合调色 (HDRNet)")
        self.hdr_cb.setChecked(True)
        self.lut_opt = QComboBox()
        self.lut_opt.addItem("none")
        self.intensity_slider = QSlider(Qt.Horizontal)
        self.intensity_slider.setRange(0, 100)
        self.intensity_slider.setValue(70)
        self.intensity_lb = QLabel("70%")
        self.out_entry = QLineEdit()
        self.out_btn = QPushButton("浏览")
        form.addRow("调色模式", self.mode_opt)
        form.addRow("", self.sci_cb)
        form.addRow("", self.hdr_cb)
        form.addRow("风格预设", self.lut_opt)
        form.addRow("强度", self.intensity_slider)
        form.addRow("", self.intensity_lb)
        form.addRow("输出目录", self.out_entry)
        form.addRow("", self.out_btn)
        root.addWidget(params)
        self.intensity_slider.valueChanged.connect(
            lambda v: self.intensity_lb.setText(f"{v}%"))
        self.out_btn.clicked.connect(self._browse_out)

        split = QHBoxLayout()
        split.setSpacing(10)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setFixedWidth(260)
        split.addWidget(self.list)
        self.compare = CompareView()
        split.addWidget(self.compare, 1)
        root.addLayout(split, 1)

        bottom = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setFixedHeight(8)
        self.status_lb = QLabel("就绪")
        self.start_btn = QPushButton("开始调色")
        self.start_btn.setProperty("accent", True)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.setEnabled(False)
        bottom.addWidget(self.status_lb)
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.start_btn)
        bottom.addWidget(self.stop_btn)
        root.addLayout(bottom)

        self.add_btn.clicked.connect(self._add_files)
        self.folder_btn.clicked.connect(self._add_folder)
        self.clear_btn.clicked.connect(self._clear)
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._cancel)
        self.list.currentRowChanged.connect(self._preview_row)

    def _ensure_engine(self):
        if self.engine is not None:
            return
        base = Path(__file__).resolve().parent
        self.engine = AutoColorEngine(
            sci_model_path=str(base / "models" / "sci.onnx"),
            hdrnet_model_path=str(base / "models" / "hdrnet.onnx"),
            lut_dir=str(base / "luts"),
            use_gpu=False)
        self.lut_opt.clear()
        self.lut_opt.addItems(self.engine.get_lut_names())
        if self.lut_opt.count() > 0:
            self.lut_opt.setCurrentText(
                "none" if self.lut_opt.findText("none") >= 0 else self.lut_opt.itemText(0))

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "", "图片 (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp)")
        self._append(paths)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if not folder:
            return
        found = []
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in SUPPORTED_EXTS:
                    found.append(os.path.join(root, f))
        self._append(found)

    def _append(self, paths):
        existing = {self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())}
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

    def _selected_paths(self):
        return [
            self.list.item(i).data(Qt.UserRole)
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.Checked
        ]

    def _clear(self):
        if self.worker and self.worker.isRunning():
            return
        self.list.clear()
        self.compare.set_images(None, None)
        self.progress.setValue(0)
        self.status_lb.setText("就绪")
        self.count_lb.setText("共 0 张")

    def _browse_out(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.out_entry.setText(folder)

    def _preview_row(self, row):
        if row < 0 or row >= self.list.count():
            return
        path = self.list.item(row).data(Qt.UserRole)
        self._ensure_engine()
        mode = self.mode_opt.currentIndex()
        params = self._params()
        engine = self.engine
        threading.Thread(
            target=self._do_preview, args=(path, mode, params, engine),
            daemon=True).start()

    def _do_preview(self, path, mode, params, engine):
        try:
            import cv2
            img = imread_unicode(path)
            if img is None:
                return
            h, w = img.shape[:2]
            if max(h, w) > 720:
                scale = 720 / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)),
                                 interpolation=cv2.INTER_AREA)
            if mode == 0:
                result = AutoColorEngine._traditional_enhance(img)
            else:
                result = engine.process_image(
                    img, use_sci=params["use_sci"], use_hdrnet=params["use_hdrnet"],
                    lut_name=params["lut_name"], lut_intensity=params["lut_intensity"])
            def to_pixmap(bgr):
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                data = rgb.tobytes()
                qimg = self._qimage(data, rgb.shape[1], rgb.shape[0])
                return QPixmap.fromImage(qimg)
            orig_pix = to_pixmap(img)
            result_pix = to_pixmap(result)
            self.compare.set_images(orig_pix, result_pix)
        except Exception:
            pass

    @staticmethod
    def _qimage(data, w, h):
        from PySide6.QtGui import QImage
        return QImage(data, w, h, w * 3, QImage.Format_RGB888).copy()

    def _params(self):
        return {
            "use_sci": self.sci_cb.isChecked(),
            "use_hdrnet": self.hdr_cb.isChecked(),
            "lut_name": self.lut_opt.currentText(),
            "lut_intensity": self.intensity_slider.value() / 100.0,
        }

    def _start(self):
        if self.worker and self.worker.isRunning():
            return
        paths = self._selected_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先勾选要调色的图片")
            return
        self._ensure_engine()
        output_dir = self.out_entry.text().strip()
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(paths[0])), "_autocolor")
            self.out_entry.setText(output_dir)
        self.cancel_event = threading.Event()
        params = self._params()
        self.worker = AutoColorWorker(
            self.engine, paths, output_dir, params, self.cancel_event, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_done)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setValue(0)
        self.status_lb.setText(f"队列：{len(paths)} 张")
        self.worker.start()

    def _cancel(self):
        self.cancel_event.set()
        self.stop_btn.setEnabled(False)
        self.status_lb.setText("正在停止...")

    def _on_progress(self, event):
        index = event.get("index", 0) + 1
        total = max(1, event.get("total", 1))
        self.progress.setValue(int(index / total * 100))
        self.status_lb.setText(f"当前：{os.path.basename(str(event.get('path', '')))}  {index}/{total}")

    def _on_done(self, result):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setValue(100)
        ok = result.get("ok", 0)
        failed = result.get("failed", 0)
        self.status_lb.setText(f"完成：成功 {ok}，失败 {failed}")
        if result.get("error"):
            QMessageBox.warning(self, "调色失败", result["error"])
        elif failed:
            reasons = []
            for path, reason in result.get("failed_files", [])[:5]:
                reasons.append(f"{os.path.basename(str(path))}: {reason}")
            detail = "\n".join(reasons) if reasons else "失败原因未记录"
            QMessageBox.warning(
                self, "部分失败",
                f"成功 {ok}，失败 {failed}\n"
                f"失败示例：\n{detail}\n\n输出目录：{result.get('output_dir', '')}")
        else:
            QMessageBox.information(self, "完成", f"成功 {ok} 张\n输出目录：{result.get('output_dir', '')}")
