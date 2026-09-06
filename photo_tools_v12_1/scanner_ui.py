"""scanner_ui.py - 单一文件类型筛选完整界面 (V12.1)"""

import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
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

from .scanner import ScanResult, scan_single_folder
from .utils import format_size, send_to_trash_many


def _reveal_in_explorer(path: str):
    abs_path = os.path.abspath(path)
    subprocess.Popen(["explorer", "/select,", abs_path])


def _open_with_default(path: str):
    try:
        os.startfile(os.path.abspath(path))
    except Exception as e:
        print(f"[ERROR] 打开文件失败: {e}")


def _open_folder(path: str):
    try:
        os.startfile(os.path.abspath(path))
    except Exception as e:
        print(f"[ERROR] 打开文件夹失败: {e}")


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
            futures = {executor.submit(scan_single_folder, f): f
                       for f in self.folders}
            for i, future in enumerate(as_completed(futures)):
                if self.cancel_event.is_set():
                    break
                folder = futures[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    results.append(ScanResult(folder=folder, success=False,
                                              error=str(e)))
                self.progress.emit({
                    "done": i + 1,
                    "total": len(self.folders),
                    "current": folder,
                })
        self.done.emit(results)


class ScannerPage(QWidget):
    """扫描文件夹列表 + 孤儿文件明细 + 逐文件操作。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folders = []
        self.worker = None
        self.cancel_event = threading.Event()
        self.results = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        self.add_btn = QPushButton("+ 添加文件夹")
        self.add_btn.setProperty("accent", True)
        self.batch_btn = QPushButton("+ 批量添加")
        self.folder_all_btn = QPushButton("全选")
        self.folder_uncheck_btn = QPushButton("全不选")
        self.remove_folder_btn = QPushButton("− 移除选中文件夹")
        self.clear_btn = QPushButton("清空列表")
        self.folder_count_lb = QLabel("0 个文件夹")
        top.addWidget(self.add_btn)
        top.addWidget(self.batch_btn)
        top.addWidget(self.folder_all_btn)
        top.addWidget(self.folder_uncheck_btn)
        top.addWidget(self.remove_folder_btn)
        top.addWidget(self.clear_btn)
        top.addWidget(self.folder_count_lb)
        top.addStretch(1)
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setProperty("accent", True)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.setEnabled(False)
        top.addWidget(self.scan_btn)
        top.addWidget(self.stop_btn)
        root.addLayout(top)

        self.folder_table = QTableWidget(0, 3)
        self.folder_table.setHorizontalHeaderLabels(["选择", "文件夹名称", "完整路径"])
        self.folder_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.folder_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.folder_table.setFixedHeight(150)
        self.folder_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.folder_table.horizontalHeader().resizeSection(0, 70)
        self.folder_table.horizontalHeader().resizeSection(1, 220)
        root.addWidget(self.folder_table)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.status_lb = QLabel("就绪")
        root.addWidget(self.status_lb)

        op = QHBoxLayout()
        self.sel_all_btn = QPushButton("全选")
        self.uncheck_btn = QPushButton("全不选")
        self.preview_btn = QPushButton("打开选中文件预览")
        self.reveal_btn = QPushButton("在文件夹中显示")
        self.delete_btn = QPushButton("删除选中 (移入回收站)")
        self.delete_btn.setProperty("danger", True)
        self.result_info_lb = QLabel("尚未扫描")
        op.addWidget(self.sel_all_btn)
        op.addWidget(self.uncheck_btn)
        op.addWidget(self.preview_btn)
        op.addWidget(self.reveal_btn)
        op.addWidget(self.delete_btn)
        op.addStretch(1)
        op.addWidget(self.result_info_lb)
        root.addLayout(op)

        self.result_table = QTableWidget(0, 5)
        self.result_table.setHorizontalHeaderLabels(
            ["选择", "文件路径", "类型", "大小", "来源文件夹"])
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.result_table.horizontalHeader().resizeSection(0, 60)
        self.result_table.horizontalHeader().resizeSection(1, 360)
        self.result_table.horizontalHeader().resizeSection(2, 70)
        self.result_table.horizontalHeader().resizeSection(3, 90)
        root.addWidget(self.result_table, 1)

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
        self.result_table.cellClicked.connect(self._on_result_cell_clicked)
        self.result_table.cellDoubleClicked.connect(self._on_result_double_clicked)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择素材文件夹")
        if folder:
            self._append_folders([folder])

    def _add_batch(self):
        """选择一个父目录，将父目录及其一级子文件夹批量加入扫描列表。"""
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
        for f in folders:
            key = os.path.normcase(os.path.abspath(f))
            if key in existing:
                continue
            existing.add(key)
            self.folders.append(f)
            row = self.folder_table.rowCount()
            self.folder_table.insertRow(row)
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(Qt.Checked)
            self.folder_table.setItem(row, 0, check)
            self.folder_table.setItem(row, 1, QTableWidgetItem(os.path.basename(f)))
            self.folder_table.setItem(row, 2, QTableWidgetItem(f))
            added += 1
        if added:
            self.status_lb.setText(f"已添加 {added} 个文件夹")
        else:
            self.status_lb.setText("没有新增文件夹（可能已存在）")
        self._update_folder_count()

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
        self.status_lb.setText(f"已移除 {len(rows)} 个文件夹")
        self._update_folder_count()

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

    def _start_scan(self):
        if self.worker and self.worker.isRunning():
            return
        folders = self._checked_folders()
        if not folders:
            QMessageBox.information(self, "提示", "请先勾选要扫描的文件夹")
            return
        self.cancel_event = threading.Event()
        self.result_table.setRowCount(0)
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
        rows = []
        total_size = 0
        folder_count = 0
        errors = []
        for r in self.results:
            if not r.success:
                errors.append(f"{os.path.basename(r.folder)}: {r.error}")
                continue
            folder_count += 1
            for orphan in r.orphans:
                rows.append((r.folder, orphan))
                total_size += orphan["size_bytes"]
        self.result_table.setRowCount(len(rows))
        for i, (folder, orphan) in enumerate(rows):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(Qt.Unchecked)
            self.result_table.setItem(i, 0, check)
            path_item = QTableWidgetItem(orphan["path"])
            path_item.setToolTip(orphan["path"])
            self.result_table.setItem(i, 1, path_item)
            type_item = QTableWidgetItem(orphan["ext"].lstrip("."))
            type_item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(i, 2, type_item)
            size_item = QTableWidgetItem(format_size(orphan["size_bytes"]))
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.result_table.setItem(i, 3, size_item)
            folder_item = QTableWidgetItem(folder)
            folder_item.setToolTip(folder)
            self.result_table.setItem(i, 4, folder_item)
        self.result_info_lb.setText(
            f"共 {len(rows)} 个孤儿文件，总计 {format_size(total_size)}，"
            f"来自 {folder_count} 个文件夹")
        self.status_lb.setText("扫描完成")
        if errors:
            QMessageBox.warning(self, "部分文件夹扫描失败",
                                "\n".join(errors[:8]))

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

    def _open_selected(self):
        paths = self._selected_file_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先勾选要预览的文件")
            return
        for p in paths[:8]:
            _open_with_default(p)

    def _reveal_selected(self):
        paths = self._selected_file_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先勾选文件")
            return
        _reveal_in_explorer(paths[0])

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
        ok_rows = [row for row in rows
                   if self.result_table.item(row, 1).text() in ok_set]
        for row in reversed(ok_rows):
            self.result_table.removeRow(row)
        if failed_paths:
            QMessageBox.warning(
                self, "部分失败",
                f"成功 {len(ok_paths)} 个，失败 {len(failed_paths)} 个")
        else:
            QMessageBox.information(
                self, "完成", f"已将 {len(ok_paths)} 个文件移入回收站")
        self.status_lb.setText(
            f"已删除 {len(ok_paths)} 个文件，剩余 "
            f"{self.result_table.rowCount()} 条结果")

    def _on_result_cell_clicked(self, row, column):
        path_item = self.result_table.item(row, 1)
        folder_item = self.result_table.item(row, 4)
        if path_item is None:
            return
        if column == 1:
            _open_with_default(path_item.text())
        elif column == 4 and folder_item:
            _open_folder(folder_item.text())

    def _on_result_double_clicked(self, row, _column):
        path_item = self.result_table.item(row, 1)
        if path_item:
            _reveal_in_explorer(path_item.text())

