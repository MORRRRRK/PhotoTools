"""qt_main.py - V12.0 主窗口：可折叠侧边栏 + 中央堆叠页面"""

import os
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .qt_pages import (
    AudioPage,
    ConvertPage,
    DynamicPage,
    GalleryPage,
    ProxyPage,
    ScannerPage,
    SettingsPage,
    TimelapsePage,
)
from .quality_page import QualityPageV101
from .auto_color_ui import AutoColorPage
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
        self.setWindowTitle("PhotoTools V12.0 — 摄影素材管理工具箱")
        self.resize(1440, 900)
        self.setMinimumSize(1200, 760)
        self.nav_expanded = True
        self.nav_texts = {}

        self._build_menus()
        self._build_central()
        self._build_statusbar()
        self.nav.setCurrentRow(0)

    def _build_menus(self):
        file_menu = self.menuBar().addMenu("文件")
        exit_act = QAction("退出", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        help_menu = self.menuBar().addMenu("帮助")
        about_act = QAction("关于 PhotoTools V12.0", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.addAction(QIcon.fromTheme("go-home"), "返回", lambda: self.nav.setCurrentRow(0))
        self.addToolBar(Qt.TopToolBarArea, toolbar)

    def _build_central(self):
        central = QWidget(self)
        central.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central)
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        sidebar = QWidget()
        sidebar.setStyleSheet("background: #121214; border-right: 1px solid #2e2e36;")
        sidebar.setFixedWidth(200)
        self.sidebar = sidebar
        side_lay = QVBoxLayout(sidebar)
        side_lay.setContentsMargins(0, 0, 0, 0)
        side_lay.setSpacing(0)

        self.logo_lb = QLabel("PhotoTools")
        self.logo_lb.setFixedHeight(56)
        self.logo_lb.setAlignment(Qt.AlignCenter)
        self.logo_lb.setStyleSheet(
            "color: #e8e8ed; font-size: 14px; font-weight: 600;"
            "border-bottom: 1px solid #2e2e36; background: #121214;")
        side_lay.addWidget(self.logo_lb)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setSpacing(0)
        self.nav.setViewMode(QListWidget.ListMode)

        entries = [
            ("单一文件类型筛选", "1"),
            ("照片质量评估", "评"),
            ("视频代理", "代"),
            ("音频提取", "声"),
            ("一键生成延时视频", "延"),
            ("作品展示", "展"),
            ("RAW/PNG 转 JPG", "转"),
            ("AI 自动调色", "调"),
            ("动态照片提取", "动"),
        ]
        self.pages = QStackedWidget()
        self.page_instances = {}
        page_cls = {
            "单一文件类型筛选": ScannerPage,
            "照片质量评估": QualityPageV101,
            "视频代理": ProxyPage,
            "音频提取": AudioPage,
            "一键生成延时视频": TimelapsePage,
            "作品展示": GalleryPage,
            "RAW/PNG 转 JPG": ConvertPage,
            "AI 自动调色": AutoColorPage,
            "动态照片提取": DynamicPage,
        }
        for text, char in entries:
            item = QListWidgetItem(make_icon(char, "#6366f1"), text)
            self.nav.addItem(item)
            self.nav_texts[self.nav.row(item)] = text
            self.pages.addWidget(page_cls[text]())

        sep_item = QListWidgetItem()
        sep_item.setFlags(Qt.NoItemFlags)
        sep_item.setSizeHint(QSize(1, 1))
        self.nav.addItem(sep_item)
        self._separator_row = self.nav.row(sep_item)

        settings_item = QListWidgetItem(make_icon("设", "#6366f1"), "设置")
        self.nav.addItem(settings_item)
        self.nav_texts[self.nav.row(settings_item)] = "设置"
        self.pages.addWidget(SettingsPage())

        self.nav.currentRowChanged.connect(self._on_nav_changed)
        side_lay.addWidget(self.nav, 1)

        self.collapse_btn = QToolButton()
        self.collapse_btn.setText("« 收起")
        self.collapse_btn.setFixedHeight(36)
        self.collapse_btn.setStyleSheet(
            "QToolButton { background: transparent; color: #9a9aa5; border: none;"
            " border-top: 1px solid #2e2e36; }"
            "QToolButton:hover { background: #222228; color: #e8e8ed; }")
        self.collapse_btn.clicked.connect(self._toggle_nav)
        side_lay.addWidget(self.collapse_btn)

        lay.addWidget(sidebar)
        lay.addWidget(self.pages, 1)
        self.drop_overlay = DropOverlay(central)
        self.drop_overlay.hide()

    def _on_nav_changed(self, row):
        if row == self._separator_row:
            return
        index = row if row < self._separator_row else row - 1
        self.pages.setCurrentIndex(index)

    def _toggle_nav(self):
        self.nav_expanded = not self.nav_expanded
        self.sidebar.setFixedWidth(200 if self.nav_expanded else 64)
        self.collapse_btn.setText("« 收起" if self.nav_expanded else "» 展开")
        self.logo_lb.setText("PhotoTools" if self.nav_expanded else "PT")
        for i in range(self.nav.count()):
            item = self.nav.item(i)
            if i == self._separator_row:
                continue
            text = self.nav_texts.get(i, "")
            if self.nav_expanded:
                item.setText(text)
            else:
                item.setToolTip(text)
                item.setText("")

    def _build_statusbar(self):
        bar = QStatusBar(self)
        bar.showMessage("就绪")
        self.setStatusBar(bar)

    def _show_about(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "关于 PhotoTools V12.0",
            "PhotoTools V12.0 摄影素材管理工具箱\n\n"
            "专业摄影工作站风格 · AI 自动调色 · 3D LUT 电影风格")


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
