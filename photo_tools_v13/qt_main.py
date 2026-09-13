"""qt_main.py - V13.0 主窗口：分组侧边栏 + 主题系统 + 中央堆叠页面"""

import os
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .about_page import AboutPage
from .qt_pages import (
    AudioPage,
    ConvertPage,
    DynamicPage,
    GalleryPage,
    ProxyPage,
    TimelapsePage,
)
from .quality_page import QualityPageV101
from .image_pipeline_ui import ImagePipelinePage
from .scanner_ui import ScannerPage
from .settings_page import SettingsPage
from .theme import ACCENTS, ThemeManager
from .qt_widgets import DropOverlay

APP_VERSION = "13.0.0"
SIDEBAR_W = 248
SIDEBAR_COLLAPSED_W = 68


def make_icon(char: str, color: str) -> QIcon:
    pix = QPixmap(26, 26)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, 22, 22, 6, 6)
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
        self.theme = ThemeManager.instance()
        self.setWindowTitle("PhotoTools V13.0 — 摄影素材管理工具箱")
        self.resize(1440, 900)
        self.setMinimumSize(1200, 760)
        self.nav_expanded = True
        self.row_to_page = {}
        self.row_meta = {}
        self._build_menus()
        self._build_central()
        self._build_statusbar()
        self.theme.changed.connect(self._on_theme_changed)
        first = next((row for row, meta in self.row_meta.items() if meta[0] == "page"), None)
        if first is not None:
            self.nav.setCurrentRow(first)

    def _build_menus(self):
        file_menu = self.menuBar().addMenu("文件")
        exit_act = QAction("退出", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        help_menu = self.menuBar().addMenu("帮助")
        about_act = QAction("关于 PhotoTools", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_central(self):
        central = QWidget(self)
        central.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central)
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_W)
        self.sidebar = sidebar
        side_lay = QVBoxLayout(sidebar)
        side_lay.setContentsMargins(0, 8, 0, 8)
        side_lay.setSpacing(0)

        brand = QHBoxLayout()
        brand.setContentsMargins(14, 6, 14, 10)
        brand.setSpacing(8)
        self.brand_mark = QLabel("PT")
        self.brand_mark.setObjectName("brandMark")
        self.brand_mark.setFixedSize(28, 28)
        self.brand_mark.setAlignment(Qt.AlignCenter)
        self.brand_name = QLabel("PhotoTools")
        self.brand_name.setObjectName("brandName")
        self.brand_ver = QLabel("V13")
        self.brand_ver.setObjectName("brandVer")
        brand.addWidget(self.brand_mark)
        brand.addWidget(self.brand_name)
        brand.addWidget(self.brand_ver)
        brand.addStretch(1)
        side_lay.addLayout(brand)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setSpacing(2)
        self.nav.setViewMode(QListWidget.ListMode)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        groups = [
            ("素材整理", [
                ("单一文件类型筛选", "筛", ScannerPage),
                ("动态照片提取", "动", DynamicPage),
                ("RAW/PNG 转 JPG", "转", ConvertPage),
            ]),
            ("质量与调色", [
                ("照片质量评估", "评", QualityPageV101),
                ("AI 图像增强", "增", ImagePipelinePage),
                ("作品展示", "展", GalleryPage),
            ]),
            ("视频工具", [
                ("视频代理", "代", ProxyPage),
                ("音频提取", "声", AudioPage),
                ("一键生成延时视频", "延", TimelapsePage),
            ]),
            ("系统", [
                ("设置", "设", SettingsPage),
                ("关于", "关", AboutPage),
            ]),
        ]

        self.pages = QStackedWidget()
        self.page_instances = {}
        accent = ACCENTS.get(self.theme.accent, ACCENTS["blue"])["ACCENT"]
        for group_title, entries in groups:
            header = QListWidgetItem(group_title)
            header.setFlags(Qt.NoItemFlags)
            header.setSizeHint(QSize(0, 26))
            font = QFont()
            font.setPixelSize(11)
            font.setBold(True)
            header.setFont(font)
            self.nav.addItem(header)
            self.row_meta[self.nav.row(header)] = ("group", group_title)
            for text, char, page_cls in entries:
                item = QListWidgetItem(make_icon(char, accent), text)
                item.setSizeHint(QSize(0, 44))
                item.setData(Qt.UserRole, text)
                self.nav.addItem(item)
                page = page_cls()
                self.pages.addWidget(page)
                self.page_instances[text] = page
                self.row_to_page[self.nav.row(item)] = page
                self.row_meta[self.nav.row(item)] = ("page", text, char)

        self.nav.currentRowChanged.connect(self._on_nav_changed)
        side_lay.addWidget(self.nav, 1)

        self.collapse_btn = QToolButton()
        self.collapse_btn.setObjectName("collapseBtn")
        self.collapse_btn.setText("« 收起侧栏")
        self.collapse_btn.setFixedHeight(34)
        self.collapse_btn.clicked.connect(self._toggle_nav)
        side_lay.addWidget(self.collapse_btn, 0, Qt.AlignBottom)

        lay.addWidget(sidebar)
        lay.addWidget(self.pages, 1)
        self.drop_overlay = DropOverlay(central)
        self.drop_overlay.hide()

    def _on_nav_changed(self, row):
        page = self.row_to_page.get(row)
        if page is not None:
            self.pages.setCurrentWidget(page)
            meta = self.row_meta.get(row)
            if meta:
                self.statusBar().showMessage(meta[1])

    def _on_theme_changed(self, *_args):
        accent = ACCENTS.get(self.theme.accent, ACCENTS["blue"])["ACCENT"]
        for row, meta in self.row_meta.items():
            if meta[0] != "page":
                continue
            item = self.nav.item(row)
            if item is not None:
                item.setIcon(make_icon(meta[2], accent))
        self.brand_mark.setStyleSheet(
            "QLabel { background: %s; color: #ffffff; border-radius: 7px; font-weight: 700; }" % accent)

    def _toggle_nav(self):
        self.nav_expanded = not self.nav_expanded
        self.sidebar.setFixedWidth(SIDEBAR_W if self.nav_expanded else SIDEBAR_COLLAPSED_W)
        self.collapse_btn.setText("« 收起侧栏" if self.nav_expanded else "»")
        self.brand_name.setVisible(self.nav_expanded)
        self.brand_ver.setVisible(self.nav_expanded)
        for row, meta in self.row_meta.items():
            if meta[0] != "page":
                continue
            item = self.nav.item(row)
            if self.nav_expanded:
                item.setText(meta[1])
            else:
                item.setToolTip(meta[1])
                item.setText("")

    def _build_statusbar(self):
        bar = QStatusBar(self)
        bar.showMessage("就绪")
        self.setStatusBar(bar)

    def _show_about(self):
        page = self.page_instances.get("关于")
        if page is not None:
            self.pages.setCurrentWidget(page)
            for row, target in self.row_to_page.items():
                if target is page:
                    self.nav.setCurrentRow(row)
                    break


def run() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    manager = ThemeManager.instance()
    manager.apply(app)
    win = MainWindow()
    win._on_theme_changed()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
