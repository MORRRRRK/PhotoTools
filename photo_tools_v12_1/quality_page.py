"""quality_page.py - V12.0 照片质量评估页（专业工作站三栏式）"""

import os
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QConicalGradient, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .quality import evaluate_photos_batch
from .gallery import make_preview, make_thumbnail, read_image_info


class ScoreRingWidget(QWidget):
    """渐变总分圆环，中心显示大号分数。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 180)
        self._value = 0.0

    def set_value(self, value: float):
        self._value = max(0.0, min(100.0, float(value)))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#2e2e36"), 10, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawEllipse(18, 18, 144, 144)
        if self._value > 0:
            gradient = QConicalGradient(90, 90, 90)
            gradient.setColorAt(0.0, QColor("#818cf8"))
            gradient.setColorAt(0.6, QColor("#6366f1"))
            gradient.setColorAt(1.0, QColor("#4f46e5"))
            pen = QPen(QColor("#6366f1"), 10, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            span = int(-360 * self._value / 100.0)
            p.drawArc(18, 18, 144, 144, 90 * 16, span * 16)
        p.setPen(QColor("#e8e8ed"))
        font = p.font()
        font.setPixelSize(36)
        font.setBold(True)
        p.setFont(font)
        p.drawText(0, 30, self.width(), 70, Qt.AlignCenter, f"{self._value:.1f}")
        p.setPen(QColor("#9a9aa5"))
        font.setPixelSize(11)
        font.setBold(False)
        p.setFont(font)
        p.drawText(0, 100, self.width(), 24, Qt.AlignCenter, "总分 / 100")
        p.end()


class TagLabel(QLabel):
    def __init__(self, text, kind="warn", parent=None):
        super().__init__(text, parent)
        self.setObjectName({"ok": "tagOk", "warn": "tagWarn", "danger": "tagDanger"}.get(kind, "tagWarn"))


class DimensionBar(QWidget):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.name_lb = QLabel(name)
        self.name_lb.setObjectName("mutedLabel")
        self.name_lb.setFixedWidth(60)
        self.bar = QProgressBar()
        self.bar.setFixedHeight(6)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(
            "QProgressBar { background: #2e2e36; border: none; border-radius: 3px; }"
            "QProgressBar::chunk { border-radius: 3px; }")
        self.value_lb = QLabel("—")
        self.value_lb.setFixedWidth(48)
        self.value_lb.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_lb.setStyleSheet("color: #e8e8ed; font-family: 'Consolas';")
        lay.addWidget(self.name_lb)
        lay.addWidget(self.bar, 1)
        lay.addWidget(self.value_lb)

    def set_value(self, value, color="#6366f1"):
        if value is None:
            self.bar.setValue(0)
            self.value_lb.setText("—")
            return
        v = max(0.0, min(100.0, float(value)))
        self.bar.setValue(int(v))
        self.value_lb.setText(f"{v:.1f}")
        self.bar.setStyleSheet(
            f"QProgressBar {{ background: #2e2e36; border: none; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}")
        self.value_lb.setStyleSheet(
            f"color: {color}; font-family: 'Consolas';")


class QualityPageV101(QWidget):
    """照片质量评估页。"""

    resultsReady = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.paths = []
        self.scores = {}
        self.thread = None
        self.current_index = -1
        self.resultsReady.connect(self._on_results)
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        center = QWidget()
        center.setContentsMargins(24, 16, 24, 24)
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(16)
        center_lay.addLayout(self._build_topbar())
        center_lay.addWidget(self._build_overview(), 0)
        center_lay.addWidget(self._build_table(), 1)
        center_lay.addLayout(self._build_bottom())
        root.addWidget(center, 1)

        self.info_panel = self._build_info_panel()
        root.addWidget(self.info_panel)

    def _build_topbar(self):
        top = QHBoxLayout()
        top.setSpacing(8)
        self.add_file_btn = QPushButton("添加文件")
        self.add_file_btn.setProperty("accent", True)
        self.add_folder_btn = QPushButton("添加文件夹")
        self.select_all_btn = QPushButton("全选")
        self.clear_btn = QPushButton("清空")
        self.count_lb = QLabel("共 0 项，已选 0 项")
        self.count_lb.setObjectName("mutedLabel")
        for b in (self.add_file_btn, self.add_folder_btn,
                  self.select_all_btn, self.clear_btn):
            b.setFixedHeight(32)
            b.setCursor(Qt.PointingHandCursor)
        top.addWidget(self.add_file_btn)
        top.addWidget(self.add_folder_btn)
        top.addWidget(self.select_all_btn)
        top.addWidget(self.clear_btn)
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #2e2e36;")
        top.addWidget(sep)
        top.addWidget(self.count_lb)
        top.addStretch(1)

        scale_lb = QLabel("评分尺度")
        scale_lb.setObjectName("mutedLabel")
        self.scale_opt = QComboBox()
        self.scale_opt.addItems(["严格", "普通", "宽松"])
        self.scale_opt.setFixedSize(120, 32)
        top.addWidget(scale_lb)
        top.addWidget(self.scale_opt)
        top.addSpacing(16)

        self.start_btn = QPushButton("开始")
        self.start_btn.setProperty("accent", True)
        self.start_btn.setFixedHeight(36)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.setFixedHeight(36)
        self.stop_btn.setEnabled(False)
        top.addWidget(self.start_btn)
        top.addWidget(self.stop_btn)

        self.add_file_btn.clicked.connect(self._add_files)
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.select_all_btn.clicked.connect(self._select_all)
        self.clear_btn.clicked.connect(self._clear)
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        return top

    def _build_overview(self):
        card = QFrame()
        card.setObjectName("overviewCard")
        card.setFixedHeight(210)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(24)

        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setAlignment(Qt.AlignCenter)
        self.scale_tag = QLabel("评分尺度：普通")
        self.scale_tag.setObjectName("mutedLabel")
        self.ring = ScoreRingWidget()
        left_lay.addWidget(self.scale_tag, 0, Qt.AlignLeft)
        left_lay.addWidget(self.ring, 0, Qt.AlignCenter)
        lay.addWidget(left, 2)

        right = QWidget()
        grid = QVBoxLayout(right)
        grid.setSpacing(12)
        dims = [
            ("构图", "#6366f1"),
            ("曝光", "#ef4444"),
            ("清晰度", "#f59e0b"),
            ("色彩", "#10b981"),
            ("噪点", "#9a9aa5"),
            ("AI 评分", "#6366f1"),
            ("综合", "#6366f1"),
        ]
        self.dim_bars = {}
        for name, color in dims:
            bar = DimensionBar(name)
            self.dim_bars[name] = (bar, color)
            grid.addWidget(bar)
        lay.addWidget(right, 3)
        return card

    def _build_table(self):
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["", "文件", "综合", "构图", "曝光", "清晰度", "色彩", "噪点", "AI"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, 40)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(2, 9):
            header.setSectionResizeMode(i, QHeaderView.Fixed)
            header.resizeSection(i, 90)
        self.table.setColumnWidth(0, 40)
        self.table.itemSelectionChanged.connect(self._on_selection)
        lay.addWidget(self.table)
        return wrap

    def _build_bottom(self):
        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        self.status_lb = QLabel("就绪")
        self.status_lb.setObjectName("mutedLabel")
        self.percent_lb = QLabel("0%")
        self.percent_lb.setStyleSheet("color: #e8e8ed;")
        self.progress = QProgressBar()
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(
            "QProgressBar { background: #222228; border: none; border-radius: 4px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6366f1, stop:1 #818cf8); border-radius: 4px; }")
        bottom.addWidget(self.status_lb)
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.percent_lb)
        return bottom

    def _build_info_panel(self):
        panel = QFrame()
        panel.setObjectName("infoPanel")
        panel.setFixedWidth(320)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        title = QLabel("信息面板")
        title.setObjectName("panelTitle")
        lay.addWidget(title)

        self.preview_lb = QLabel("选择照片后显示预览")
        self.preview_lb.setAlignment(Qt.AlignCenter)
        self.preview_lb.setFixedHeight(200)
        self.preview_lb.setStyleSheet(
            "background: #0a0a0c; border-radius: 6px; color: #5a5a66;")
        lay.addWidget(self.preview_lb)

        self.file_name_lb = QLabel("—")
        self.file_name_lb.setAlignment(Qt.AlignCenter)
        self.file_name_lb.setStyleSheet("color: #e8e8ed;")
        lay.addWidget(self.file_name_lb)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(12)

        meta_title = QLabel("元数据")
        meta_title.setStyleSheet("color: #9a9aa5; font-weight: 600;")
        body_lay.addWidget(meta_title)
        self.meta_widget = QWidget()
        self.meta_lay = QVBoxLayout(self.meta_widget)
        self.meta_lay.setContentsMargins(0, 0, 0, 0)
        self.meta_lay.setSpacing(4)
        self.meta_labels = {}
        for key in ("相机", "焦距", "光圈", "快门", "ISO", "尺寸"):
            row = QHBoxLayout()
            k = QLabel(key)
            k.setStyleSheet("color: #9a9aa5; font-size: 11px;")
            v = QLabel("—")
            v.setStyleSheet("color: #e8e8ed; font-size: 11px;")
            row.addWidget(k)
            row.addStretch(1)
            row.addWidget(v)
            self.meta_lay.addLayout(row)
            self.meta_labels[key] = v
        body_lay.addWidget(self.meta_widget)

        analysis_title = QLabel("评分分析")
        analysis_title.setStyleSheet("color: #9a9aa5; font-weight: 600;")
        body_lay.addWidget(analysis_title)
        self.analysis_lb = QLabel("尚未评估")
        self.analysis_lb.setWordWrap(True)
        self.analysis_lb.setStyleSheet("color: #9a9aa5; font-size: 11px;")
        body_lay.addWidget(self.analysis_lb)

        adv_title = QLabel("改进建议")
        adv_title.setStyleSheet("color: #9a9aa5; font-weight: 600;")
        body_lay.addWidget(adv_title)
        self.advice_lb = QLabel("尚未评估")
        self.advice_lb.setWordWrap(True)
        self.advice_lb.setStyleSheet(
            "color: #9a9aa5; font-size: 11px; line-height: 1.6;")
        body_lay.addWidget(self.advice_lb)
        body_lay.addStretch(1)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)
        return panel

    # ---------- 文件管理 ----------
    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择照片", "",
            "图片 (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)")
        self._append(paths)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择照片文件夹")
        if not folder:
            return
        found = []
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if os.path.splitext(f)[1].lower() in {
                        ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
                    found.append(os.path.join(root, f))
        self._append(found)

    def _append(self, paths):
        existing = set(self.paths)
        for p in paths:
            key = os.path.normcase(os.path.abspath(p))
            if key in existing:
                continue
            existing.add(key)
            self.paths.append(p)
            row = self.table.rowCount()
            self.table.insertRow(row)
            check = QTableWidgetItem()
            check.setCheckState(Qt.Checked)
            self.table.setItem(row, 0, check)
            name_item = QTableWidgetItem(os.path.basename(p))
            thumb = make_thumbnail(p)
            if thumb:
                name_item.setIcon(QIcon(QPixmap(thumb)))
            name_item.setToolTip(p)
            self.table.setItem(row, 1, name_item)
            for col in range(2, 9):
                self.table.setItem(row, col, QTableWidgetItem("—"))
        self._update_count()

    def _selected_paths(self):
        return [
            self.paths[i]
            for i in range(self.table.rowCount())
            if self.table.item(i, 0) and self.table.item(i, 0).checkState() == Qt.Checked
        ]

    def _update_count(self):
        self.count_lb.setText(
            f"共 {self.table.rowCount()} 项，已选 {len(self._selected_paths())} 项")

    def _select_all(self):
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item:
                item.setCheckState(Qt.Checked)
        self._update_count()

    def _clear(self):
        if self.thread and self.thread.isRunning():
            return
        self.table.setRowCount(0)
        self.paths.clear()
        self.scores.clear()
        self.current_index = -1
        self._update_count()
        self.ring.set_value(0)
        self._reset_info()

    # ---------- 评估 ----------
    def _start(self):
        if self.thread and self.thread.isRunning():
            return
        paths = self._selected_paths()
        if not paths:
            return
        scale_map = {"严格": "strict", "普通": "normal", "宽松": "loose"}
        scale = scale_map.get(self.scale_opt.currentText(), "normal")
        self.scale_tag.setText(f"评分尺度：{self.scale_opt.currentText()}")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setValue(0)
        self.percent_lb.setText("0%")
        self.status_lb.setText("正在评估...")

        def worker():
            scores = evaluate_photos_batch(paths, scale=scale)
            self.resultsReady.emit(scores)

        threading.Thread(target=worker, daemon=True).start()

    def _on_results(self, scores):
        self.scores = {os.path.normcase(os.path.abspath(s.file)): s for s in scores}
        self._fill_scores(scores)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setValue(100)
        self.percent_lb.setText("100%")
        self.status_lb.setText("完成")
        if scores:
            self._show_score(0)

    def _stop(self):
        self.status_lb.setText("正在停止...")
        self.stop_btn.setEnabled(False)

    def _fill_scores(self, scores):
        for i, score in enumerate(scores):
            if i >= self.table.rowCount():
                break
            vals = {
                2: score.total_score,
                3: score.composition,
                4: score.exposure,
                5: score.sharpness,
                6: score.color_score,
                7: score.noise_score,
                8: score.ai_score,
            }
            for col, val in vals.items():
                item = QTableWidgetItem("—" if val is None else f"{val:.1f}")
                if col == 2:
                    item.setText(f"{val:.1f}")
                    item.setData(Qt.UserRole, val)
                    item.setTextAlignment(Qt.AlignCenter)
                elif col == 4 and val is not None and val < 40:
                    item.setForeground(QColor("#ef4444"))
                elif col == 6 and val is not None and val > 80:
                    item.setForeground(QColor("#10b981"))
                elif val is not None:
                    item.setText(f"{val:.1f}")
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, col, item)
            if i == 0:
                self._show_score(0)

    def _on_selection(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self._show_score(rows[0].row())

    def _show_score(self, row):
        if row < 0 or row >= len(self.paths):
            return
        path = self.paths[row]
        score = self.scores.get(os.path.normcase(os.path.abspath(path)))
        self.current_index = row
        self.file_name_lb.setText(os.path.basename(path))
        if score is None:
            self.ring.set_value(0)
            return
        self.ring.set_value(score.total_score)
        self.dim_bars["构图"][0].set_value(score.composition, "#6366f1")
        self.dim_bars["曝光"][0].set_value(score.exposure, "#ef4444" if score.exposure < 40 else "#6366f1")
        self.dim_bars["清晰度"][0].set_value(score.sharpness, "#f59e0b" if score.sharpness < 70 else "#10b981")
        self.dim_bars["色彩"][0].set_value(score.color_score, "#10b981" if score.color_score > 80 else "#f59e0b")
        self.dim_bars["噪点"][0].set_value(score.noise_score, "#9a9aa5")
        self.dim_bars["AI 评分"][0].set_value(score.ai_score, "#6366f1")
        self.dim_bars["综合"][0].set_value(score.total_score, "#6366f1")
        self._update_meta(path)
        self._update_analysis(score)

    def _update_meta(self, path):
        info = read_image_info(path)
        values = {
            "相机": info.get("device", "未知"),
            "焦距": info.get("focal", "未知"),
            "光圈": info.get("aperture", "未知"),
            "快门": info.get("shutter", "未知"),
            "ISO": info.get("iso", "未知"),
            "尺寸": f"{info.get('width', 0)}×{info.get('height', 0)}",
        }
        for key, val in values.items():
            self.meta_labels[key].setText(str(val))
        preview = make_preview(path)
        if preview:
            pix = QPixmap(preview)
            self.preview_lb.setPixmap(pix.scaled(
                self.preview_lb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.preview_lb.setText("无法预览")

    def _update_analysis(self, score):
        lines = []
        advice = []
        if score.color_score > 80:
            lines.append("色彩优秀（绿色）：色彩还原准确，饱和度适中")
        elif score.color_score < 60:
            lines.append("色彩偏弱（橙色）：建议检查白平衡")
        if score.sharpness < 70:
            lines.append("清晰度不足（橙色）：画面锐度偏低")
            advice.append("1. 建议检查对焦或提升快门速度")
        if score.exposure < 40:
            lines.append("曝光异常（红色）：曝光严重不足，画面偏暗")
            advice.append("2. 建议增加曝光补偿或后期提亮")
        if score.noise_score and score.noise_score < 60:
            lines.append("噪点偏高（橙色）：高感光度导致")
            advice.append("3. 建议降低 ISO 或后期降噪")
        if not lines:
            lines.append("整体表现良好")
        self.analysis_lb.setText("\n".join(lines))
        self.advice_lb.setText("\n".join(advice) if advice else "无需额外处理")

    def _reset_info(self):
        self.preview_lb.clear()
        self.preview_lb.setText("选择照片后显示预览")
        self.file_name_lb.setText("—")
        for key in self.meta_labels:
            self.meta_labels[key].setText("—")
        self.analysis_lb.setText("尚未评估")
        self.advice_lb.setText("尚未评估")
