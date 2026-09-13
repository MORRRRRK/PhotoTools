"""about_page.py - V13 关于页：版本号、更新说明与开源许可"""

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import app_config
from ._version import BUILD_DATE, __version__ as APP_VERSION
from .platform.shell import open_path

CHANGELOG = [
    ("V13.0", "2026-09-13", [
        "全新高级感界面：分组侧边栏、深/浅主题、四档字号与四种主题色",
        "外观与字号设置移入设置页并真实生效，新增关于页",
        "浅色主题下侧栏与整机配色同步变浅",
        "照片预览按原始比例自适应窗口，完整显示不裁切",
    ]),
    ("V12.1", "2026-09-06", [
        "内置 SCI 曝光校正模型，AI 自动调色开箱可用",
        "生成结果改为版本化无损 PNG，不再覆盖历史版本",
        "恢复单一文件类型筛选的批量导入与逐文件删除",
    ]),
    ("V12.0", "2026-08-26", [
        "新增 AI 自动调色与 10 个电影胶片 LUT 预设",
        "接入 ONNX Runtime 推理管线",
    ]),
    ("V11", "2026-08-26", [
        "迁移到 PySide6 / Qt Widgets，统一暗色工作台风格",
        "新增作品展示与独立安装器",
    ]),
]

LICENSES = [
    ("Lucide 图标", "ISC"),
    ("SCI 模型", "MIT"),
    ("ONNX Runtime", "MIT"),
    ("OpenCV", "Apache 2.0"),
]


def _card(title: str) -> tuple:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)
    head = QLabel(title)
    head.setObjectName("cardTitle")
    lay.addWidget(head)
    return frame, lay


def _metric_row(lay, key: str, value: str):
    row = QHBoxLayout()
    left = QLabel(key)
    left.setObjectName("fieldLabel")
    right = QLabel(value)
    right.setObjectName("metricValue")
    right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    right.setTextInteractionFlags(Qt.TextSelectableByMouse)
    row.addWidget(left)
    row.addStretch(1)
    row.addWidget(right)
    lay.addLayout(row)


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("关于")
        title.setObjectName("pageTitle")
        desc = QLabel("版本信息、更新说明与开源许可。")
        desc.setObjectName("pageDesc")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        head.addLayout(title_box)
        head.addStretch(1)
        log_btn = QPushButton("打开日志目录")
        check_btn = QPushButton("检查更新")
        check_btn.setProperty("accent", True)
        log_btn.clicked.connect(self._open_logs)
        check_btn.clicked.connect(self._check_update)
        head.addWidget(log_btn)
        head.addWidget(check_btn)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(12)

        identity, ilay = _card("PhotoTools")
        badge = QLabel("V" + APP_VERSION)
        badge.setObjectName("cardSub")
        ilay.addWidget(badge)
        _metric_row(ilay, "版本号", APP_VERSION)
        _metric_row(ilay, "构建日期", BUILD_DATE)
        _metric_row(ilay, "界面框架", "PySide6 / Qt Widgets")
        _metric_row(ilay, "推理框架", "ONNX Runtime")
        _metric_row(ilay, "配置文件", app_config.config_path())
        left.addWidget(identity)

        changelog, clay = _card("更新说明")
        for version, date, items in CHANGELOG:
            row = QHBoxLayout()
            tag = QLabel(version)
            tag.setObjectName("metricValue")
            when = QLabel(date)
            when.setObjectName("cardSub")
            row.addWidget(tag)
            row.addWidget(when)
            row.addStretch(1)
            clay.addLayout(row)
            for text in items:
                line = QLabel("· " + text)
                line.setWordWrap(True)
                line.setObjectName("cardSub")
                clay.addWidget(line)
            divider = QFrame()
            divider.setObjectName("divider")
            clay.addWidget(divider)
        left.addWidget(changelog)
        left.addStretch(1)
        body.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(12)
        licenses, rlay = _card("开源许可")
        for name, license_name in LICENSES:
            _metric_row(rlay, name, license_name)
        right.addWidget(licenses)

        if sys.platform == "darwin":
            platform_card, play = _card("macOS 首版说明")
            for line in ("已支持：单一文件类型筛选、照片质量评估、AI 图像增强、作品展示",
                         "后续版本支持：视频代理、音频提取、一键生成延时视频、动态照片提取、RAW/PNG 转 JPG",
                         "首次打开：若提示“无法验证开发者”，请右键点击应用图标选择“打开”"):
                note = QLabel("· " + line)
                note.setObjectName("cardSub")
                note.setWordWrap(True)
                play.addWidget(note)
            right.addWidget(platform_card)

        support, slay = _card("技术支持")
        hint = QLabel("日志目录：" + os.path.join(app_config.config_dir(), "logs"))
        hint.setObjectName("cardSub")
        hint.setWordWrap(True)
        slay.addWidget(hint)
        note = QLabel("反馈问题时附上最近一次运行日志，便于定位。")
        note.setObjectName("cardSub")
        note.setWordWrap(True)
        slay.addWidget(note)
        right.addWidget(support)
        right.addStretch(1)
        body.addLayout(right, 2)
        root.addLayout(body, 1)

    def _open_logs(self):
        path = os.path.join(app_config.config_dir(), "logs")
        os.makedirs(path, exist_ok=True)
        open_path(path)

    def _check_update(self):
        QMessageBox.information(
            self, "检查更新",
            "当前为本地版本，尚未接入在线更新服务。\n可在 GitHub 仓库查看最新发布。")
