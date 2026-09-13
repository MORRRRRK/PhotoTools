"""scanner_ui.py - V13 单一文件类型筛选：文件夹列表 + 结果明细 + 等比预览"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .image_view import AspectImageView
from .platform_utils import open_path, reveal_in_file_manager, send_to_trash_many
from .scanner import ScanResult, scan_single_folder
from .utils import format_datetime, format_size


class ScanWorker(QThread):
    progress = Signal(dict)
    done = Signal(list)

    def __init__(self, folders, cancel_event, parent=None):
        super().__init__(parent)
        self.folders = list(folders)
        self.cancel_event = cancel_event

    def run(self):
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(scan_single_folder, f): f for f in self.folders}
            for index, future in enumerate(as_completed(futures)):
                if self.cancel_event.is_set():
                    break
                folder = futures[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    results.append(ScanResult(folder=folder, success=False, error=str(e)))
                self.progress.emit({"done": index + 1, "total": len(self.folders),
                                    "current": folder})
        self.done.emit(results)


def _card(title: str, subtitle: str = "") -> tuple:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(8)
    head = QHBoxLayout()
    head.setSpacing(8)
    title_lb = QLabel(title)
    title_lb.setObjectName("cardTitle")
    head.addWidget(title_lb)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("cardSub")
        head.addWidget(sub)
    head.addStretch(1)
    lay.addLayout(head)
    return frame, lay, head


class ScannerPage(QWidget):
    """扫描文件夹、列出未配对文件、逐条预览并删除。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folders = []
        self.worker = None
        self.cancel_event = threading.Event()
        self.results = []
        self._rows = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("单一文件类型筛选")
        title.setObjectName("pageTitle")
        desc = QLabel("批量扫描多个素材文件夹，找出 JPG 已删除但同名 RAW / PNG 残留的文件，确认后移入回收站。")
        desc.setObjectName("pageDesc")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        head.addLayout(title_box)
        head.addStretch(1)
        self.add_btn = QPushButton("添加文件夹")
        self.batch_btn = QPushButton("批量添加")
        self.batch_btn.setProperty("accent", True)
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setProperty("accent", True)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.setEnabled(False)
        head.addWidget(self.add_btn)
        head.addWidget(self.batch_btn)
        head.addWidget(self.scan_btn)
        head.addWidget(self.stop_btn)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(12)

        folders_card, flay, fhead = _card("扫描文件夹列表")
        self.folder_count_lb = QLabel("0 个文件夹")
        self.folder_count_lb.setObjectName("cardSub")
        fhead.addWidget(self.folder_count_lb)
        self.folder_table = QTableWidget(0, 3)
        self.folder_table.setHorizontalHeaderLabels(["选择", "文件夹名称", "完整路径"])
        self.folder_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.folder_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.folder_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.folder_table.horizontalHeader().resizeSection(0, 56)
        self.folder_table.horizontalHeader().resizeSection(1, 150)
        flay.addWidget(self.folder_table, 1)
        fbtns = QHBoxLayout()
        self.folder_all_btn = QPushButton("全选")
        self.folder_uncheck_btn = QPushButton("全不选")
        self.remove_folder_btn = QPushButton("移除选中")
        self.clear_btn = QPushButton("清空列表")
        for btn in (self.folder_all_btn, self.folder_uncheck_btn,
                    self.remove_folder_btn, self.clear_btn):
            fbtns.addWidget(btn)
        fbtns.addStretch(1)
        flay.addLayout(fbtns)
        folders_card.setFixedWidth(300)
        body.addWidget(folders_card, 0)

        results_card, rlay, rhead = _card("扫描结果", "按文件夹分别扫描并汇总")
        self.result_info_lb = QLabel("尚未扫描")
        self.result_info_lb.setObjectName("cardSub")
        rhead.addWidget(self.result_info_lb)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        rlay.addWidget(self.progress)
        self.result_table = QTableWidget(0, 5)
        self.result_table.setHorizontalHeaderLabels(
            ["选择", "文件路径", "类型", "大小", "来源文件夹"])
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.result_table.horizontalHeader().resizeSection(0, 56)
        self.result_table.horizontalHeader().resizeSection(1, 320)
        self.result_table.horizontalHeader().resizeSection(2, 64)
        self.result_table.horizontalHeader().resizeSection(3, 84)
        rlay.addWidget(self.result_table, 1)
        rbtns = QHBoxLayout()
        self.sel_all_btn = QPushButton("全选")
        self.uncheck_btn = QPushButton("全不选")
        self.preview_btn = QPushButton("打开选中文件预览")
        self.reveal_btn = QPushButton("在文件夹中显示")
        self.delete_btn = QPushButton("删除选中 (移入回收站)")
        self.delete_btn.setProperty("danger", True)
        for btn in (self.sel_all_btn, self.uncheck_btn, self.preview_btn,
                    self.reveal_btn):
            rbtns.addWidget(btn)
        rbtns.addStretch(1)
        rbtns.addWidget(self.delete_btn)
        rlay.addLayout(rbtns)
        body.addWidget(results_card, 1)

        preview_card, play, phead = _card("文件预览")
        self.preview_tag = QLabel("未选择")
        self.preview_tag.setObjectName("cardSub")
        phead.addWidget(self.preview_tag)
        self.preview = AspectImageView(placeholder="点击结果行预览")
        self.preview.setMinimumHeight(220)
        play.addWidget(self.preview, 1)
        self.preview_name_lb = QLabel("—")
        self.preview_name_lb.setObjectName("cardSub")
        self.preview_name_lb.setWordWrap(True)
        play.addWidget(self.preview_name_lb)
        self.preview_meta = {}
        for key in ("文件类型", "文件大小", "修改时间", "来源文件夹"):
            row = QHBoxLayout()
            k = QLabel(key)
            k.setObjectName("fieldLabel")
            v = QLabel("—")
            v.setObjectName("metricValue")
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(k)
            row.addStretch(1)
            row.addWidget(v)
            play.addLayout(row)
            self.preview_meta[key] = v
        pbtns = QHBoxLayout()
        self.open_btn = QPushButton("系统程序打开")
        self.reveal_one_btn = QPushButton("定位文件")
        for btn in (self.open_btn, self.reveal_one_btn):
            pbtns.addWidget(btn)
        play.addLayout(pbtns)
        preview_card.setFixedWidth(320)
        body.addWidget(preview_card, 0)

        root.addLayout(body, 1)

        self.status_lb = QLabel("就绪")
        self.status_lb.setObjectName("pageDesc")
        root.addWidget(self.status_lb)

        self.add_btn.clicked.connect(self._add_folder)
        self.batch_btn.clicked.connect(self._add_batch)
        self.folder_all_btn.clicked.connect(lambda: self._set_folder_checks(True))
        self.folder_uncheck_btn.clicked.connect(lambda: self._set_folder_checks(False))
        self.remove_folder_btn.clicked.connect(self._remove_selected_folders)
        self.clear_btn.clicked.connect(self._clear_folders)
        self.scan_btn.clicked.connect(self._start_scan)
        self.stop_btn.clicked.connect(self._stop_scan)
        self.sel_all_btn.clicked.connect(lambda: self._set_result_checks(True))
        self.uncheck_btn.clicked.connect(lambda: self._set_result_checks(False))
        self.preview_btn.clicked.connect(self._open_selected)
        self.reveal_btn.clicked.connect(self._reveal_selected)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.open_btn.clicked.connect(self._open_current)
        self.reveal_one_btn.clicked.connect(self._reveal_current)
        self.result_table.itemSelectionChanged.connect(self._on_row_selected)

    # ---------- 文件夹列表 ----------
    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择素材文件夹")
        if folder:
            self._append_folders([folder])

    def _add_batch(self):
        root = QFileDialog.getExistingDirectory(
            self, "选择父目录（会加入该目录及其一级子文件夹）")
        if not root:
            return
        folders = [root]
        try:
            for name in sorted(os.listdir(root)):
                child = os.path.join(root, name)
                if os.path.isdir(child):
                    folders.append(child)
        except OSError as e:
            print(f"[WARN] 读取子文件夹失败: {e}")
        self._append_folders(folders)

    def _append_folders(self, folders):
        existing = {os.path.normcase(f) for f in self.folders}
        added = 0
        for folder in folders:
            key = os.path.normcase(os.path.abspath(folder))
            if key in existing:
                continue
            existing.add(key)
            self.folders.append(folder)
            row = self.folder_table.rowCount()
            self.folder_table.insertRow(row)
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(Qt.Checked)
            self.folder_table.setItem(row, 0, check)
            self.folder_table.setItem(row, 1, QTableWidgetItem(os.path.basename(folder)))
            path_item = QTableWidgetItem(folder)
            path_item.setToolTip(folder)
            self.folder_table.setItem(row, 2, path_item)
            added += 1
        self._update_folder_count()
        self.status_lb.setText(f"已添加 {added} 个文件夹" if added else "没有新增文件夹（可能已存在）")

    def _set_folder_checks(self, checked):
        for row in range(self.folder_table.rowCount()):
            item = self.folder_table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self._update_folder_count()

    def _remove_selected_folders(self):
        rows = [row for row in range(self.folder_table.rowCount())
                if self.folder_table.item(row, 0)
                and self.folder_table.item(row, 0).checkState() == Qt.Checked]
        for row in reversed(rows):
            self.folder_table.removeRow(row)
            self.folders.pop(row)
        self._update_folder_count()
        self.status_lb.setText(f"已移除 {len(rows)} 个文件夹")

    def _clear_folders(self):
        self.folder_table.setRowCount(0)
        self.folders.clear()
        self._update_folder_count()

    def _update_folder_count(self):
        checked = sum(
            1 for row in range(self.folder_table.rowCount())
            if self.folder_table.item(row, 0)
            and self.folder_table.item(row, 0).checkState() == Qt.Checked)
        self.folder_count_lb.setText(
            f"{self.folder_table.rowCount()} 个文件夹，已勾选 {checked} 个")

    def _checked_folders(self):
        result = []
        for row in range(self.folder_table.rowCount()):
            item = self.folder_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                path_item = self.folder_table.item(row, 2)
                if path_item:
                    result.append(path_item.text())
        return result

    # ---------- 扫描 ----------
    def _start_scan(self):
        if self.worker and self.worker.isRunning():
            return
        folders = self._checked_folders()
        if not folders:
            QMessageBox.information(self, "提示", "请先勾选要扫描的文件夹")
            return
        self.cancel_event = threading.Event()
        self.result_table.setRowCount(0)
        self._rows = []
        self.result_info_lb.setText("扫描中...")
        self.worker = ScanWorker(folders, self.cancel_event, self)
        self.worker.progress.connect(self._on_scan_progress)
        self.worker.done.connect(self._on_scan_done)
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setValue(0)
        self.status_lb.setText(f"扫描中：0/{len(folders)}")
        self.worker.start()

    def _stop_scan(self):
        self.cancel_event.set()
        self.stop_btn.setEnabled(False)
        self.status_lb.setText("正在停止...")

    def _on_scan_progress(self, event):
        done = event.get("done", 0)
        total = max(1, event.get("total", 1))
        self.progress.setValue(int(done / total * 100))
        self.status_lb.setText(
            f"扫描中：{done}/{total}  {os.path.basename(str(event.get('current', '')))}")

    def _on_scan_done(self, results):
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setValue(100)
        self.results = results
        self._populate_results()

    def _populate_results(self):
        self.result_table.setRowCount(0)
        self._rows = []
        total_size = 0
        folder_count = 0
        errors = []
        for result in self.results:
            if not result.success:
                errors.append(f"{os.path.basename(result.folder)}: {result.error}")
                continue
            folder_count += 1
            for orphan in result.orphans:
                self._rows.append((result.folder, orphan))
                total_size += orphan["size_bytes"]
        self.result_table.setRowCount(len(self._rows))
        for index, (folder, orphan) in enumerate(self._rows):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(Qt.Unchecked)
            self.result_table.setItem(index, 0, check)
            path_item = QTableWidgetItem(orphan["path"])
            path_item.setToolTip(orphan["path"])
            self.result_table.setItem(index, 1, path_item)
            type_item = QTableWidgetItem(orphan["ext"].lstrip("."))
            type_item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(index, 2, type_item)
            size_item = QTableWidgetItem(format_size(orphan["size_bytes"]))
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.result_table.setItem(index, 3, size_item)
            folder_item = QTableWidgetItem(folder)
            folder_item.setToolTip(folder)
            self.result_table.setItem(index, 4, folder_item)
        self.result_info_lb.setText(
            f"共 {len(self._rows)} 个未配对文件 · {format_size(total_size)} · "
            f"来自 {folder_count} 个文件夹")
        self.status_lb.setText("扫描完成")
        if errors:
            QMessageBox.warning(self, "部分文件夹扫描失败", "\n".join(errors[:8]))

    # ---------- 结果操作 ----------
    def _checked_result_rows(self):
        return [row for row in range(self.result_table.rowCount())
                if self.result_table.item(row, 0)
                and self.result_table.item(row, 0).checkState() == Qt.Checked]

    def _selected_file_paths(self):
        paths = []
        for row in self._checked_result_rows():
            item = self.result_table.item(row, 1)
            if item:
                paths.append(item.text())
        return paths

    def _set_result_checks(self, checked):
        for row in range(self.result_table.rowCount()):
            item = self.result_table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def _current_path(self):
        row = self.result_table.currentRow()
        if row < 0 or row >= len(self._rows):
            return ""
        return self._rows[row][1]["path"]

    def _on_row_selected(self):
        row = self.result_table.currentRow()
        if row < 0 or row >= len(self._rows):
            return
        folder, orphan = self._rows[row]
        self.preview_name_lb.setText(orphan["path"])
        if not self.preview.set_image_path(orphan["path"]):
            self.preview.clear_image("该格式暂不支持内嵌预览")
        self.preview_tag.setText(orphan["ext"].lstrip(".").upper() + " · 未配对")
        self.preview_meta["文件类型"].setText(orphan["ext"].lstrip(".").upper())
        self.preview_meta["文件大小"].setText(format_size(orphan["size_bytes"]))
        self.preview_meta["修改时间"].setText(format_datetime(orphan.get("modified", 0)))
        self.preview_meta["来源文件夹"].setText(folder)

    def _open_selected(self):
        paths = self._selected_file_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先勾选要预览的文件")
            return
        for path in paths[:8]:
            open_path(path)

    def _reveal_selected(self):
        paths = self._selected_file_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先勾选文件")
            return
        reveal_in_file_manager(paths[0])

    def _open_current(self):
        path = self._current_path()
        if path:
            open_path(path)

    def _reveal_current(self):
        path = self._current_path()
        if path:
            reveal_in_file_manager(path)

    def _delete_selected(self):
        rows = self._checked_result_rows()
        if not rows:
            QMessageBox.information(self, "提示", "请先勾选要删除的文件")
            return
        paths = [self.result_table.item(row, 1).text() for row in rows]
        if QMessageBox.question(
                self, "确认删除",
                f"确认将 {len(paths)} 个文件移入回收站？") != QMessageBox.Yes:
            return
        ok_paths, failed_paths = send_to_trash_many(paths)
        ok_set = set(ok_paths)
        keep_rows = []
        for row in range(self.result_table.rowCount()):
            item = self.result_table.item(row, 1)
            if item and item.text() in ok_set:
                continue
            keep_rows.append(self._rows[row])
        self._rows = keep_rows
        self._populate_rows_only()
        if failed_paths:
            QMessageBox.warning(self, "部分失败",
                                f"成功 {len(ok_paths)} 个，失败 {len(failed_paths)} 个")
        else:
            QMessageBox.information(self, "完成",
                                    f"已将 {len(ok_paths)} 个文件移入回收站")
        self.status_lb.setText(f"已删除 {len(ok_paths)} 个文件")

    def _populate_rows_only(self):
        rows = self._rows
        self.result_table.setRowCount(len(rows))
        for index, (folder, orphan) in enumerate(rows):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(Qt.Unchecked)
            self.result_table.setItem(index, 0, check)
            path_item = QTableWidgetItem(orphan["path"])
            path_item.setToolTip(orphan["path"])
            self.result_table.setItem(index, 1, path_item)
            type_item = QTableWidgetItem(orphan["ext"].lstrip("."))
            type_item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(index, 2, type_item)
            size_item = QTableWidgetItem(format_size(orphan["size_bytes"]))
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.result_table.setItem(index, 3, size_item)
            folder_item = QTableWidgetItem(folder)
            folder_item.setToolTip(folder)
            self.result_table.setItem(index, 4, folder_item)
