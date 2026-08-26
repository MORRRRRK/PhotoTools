"""qt_main.py - V10 主窗口：左侧导航 + 中央堆叠页面 + 右侧可停靠面板"""

import os
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .qt_pages import (
    AudioPage,
    ConvertPage,
    DynamicPage,
    GalleryPage,
    ProxyPage,
    QualityPage,
    ScannerPage,
    SettingsPage,
    TimelapsePage,
)
from .qt_widgets import DropOverlay


def make_icon(char: str, color: str) -> QIcon:
    pix = QPixmap(24, 24)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, 20, 20, 5, 5)
    painter.setPen(QColor("#FFFFFF"))
    font = painter.font()
    font.setPixelSize(12)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pix.rect(), Qt.AlignCenter, char)
    painter.end()
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhotoTools V10.0 — 摄影素材管理工具箱")
        self.resize(1280, 820)
        self.setMinimumSize(1080, 700)

        self._build_menus()
        self._build_central()
        self._build_dock()
        self._build_statusbar()
        self.nav.setCurrentRow(0)

    def _build_menus(self):
        file_menu = self.menuBar().addMenu("文件")
        exit_act = QAction("退出", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        help_menu = self.menuBar().addMenu("帮助")
        about_act = QAction("关于 PhotoTools V10.0", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.addAction(QIcon.fromTheme("go-home"), "首页", lambda: self.nav.setCurrentRow(0))
        self.addToolBar(Qt.TopToolBarArea, toolbar)

    def _build_central(self):
        central = QWidget(self)
        central.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central)
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setIconSize(QSize(24, 24))
        self.nav.setFixedWidth(220)
        self.nav.setSpacing(2)
        self.nav.setViewMode(QListWidget.ListMode)
        entries = [
            ("单一文件类型筛选", "1", "#4A90D9"),
            ("照片质量评估", "评", "#4A90D9"),
            ("视频代理", "代", "#4A90D9"),
            ("音频提取", "声", "#4A90D9"),
            ("一键生成延时视频", "延", "#4A90D9"),
            ("作品展示", "展", "#4A90D9"),
            ("RAW/PNG 转 JPG", "转", "#4A90D9"),
            ("动态照片提取", "动", "#4A90D9"),
            ("设置", "设", "#4A90D9"),
        ]
        self.pages = QStackedWidget()
        self.page_instances = {}
        for text, char, color in entries:
            from PySide6.QtWidgets import QListWidgetItem
            self.nav.addItem(QListWidgetItem(make_icon(char, color), text))
            page_cls = {
                "单一文件类型筛选": ScannerPage,
                "照片质量评估": QualityPage,
                "视频代理": ProxyPage,
                "音频提取": AudioPage,
                "一键生成延时视频": TimelapsePage,
                "作品展示": GalleryPage,
                "RAW/PNG 转 JPG": ConvertPage,
                "动态照片提取": DynamicPage,
                "设置": SettingsPage,
            }[text]
            page = page_cls()
            self.pages.addWidget(page)
            self.page_instances[text] = page

        lay.addWidget(self.nav)
        lay.addWidget(self.pages, 1)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)

        self.drop_overlay = DropOverlay(central)
        self.drop_overlay.hide()

    def _build_dock(self):
        dock = QDockWidget("信息面板", self)
        dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        info = QLabel(
            "欢迎使用 PhotoTools V10.0\n\n"
            "从左侧选择功能模块。\n"
            "右侧信息面板可关闭或移动。\n\n"
            "深色摄影蓝主题 · 本地优先")
        info.setWordWrap(True)
        info.setContentsMargins(12, 12, 12, 12)
        dock.setWidget(info)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.info_dock = dock

    def _build_statusbar(self):
        bar = QStatusBar(self)
        bar.showMessage("就绪")
        self.setStatusBar(bar)

    def _show_about(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "关于 PhotoTools V10.0",
            "PhotoTools V10.0 摄影素材管理工具箱\n\n"
            "文件筛选 / 质量评估 / 视频代理 / 音频提取 / 延时视频 / "
            "作品展示 / RAW 转 JPG / 动态照片提取")


def run() -> int:
    app = QApplication(sys.argv)
    qss = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.qss")
    if os.path.exists(qss):
        with open(qss, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
