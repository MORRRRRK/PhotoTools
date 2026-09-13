"""settings_page.py - V13 设置页：外观、路径与行为，保存后全局生效"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import app_config
from .theme import ACCENTS, ACCENT_LABELS, FONT_LABELS, THEME_LABELS, ThemeManager


def _card(title: str, subtitle: str = "") -> tuple:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)
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


def _segmented(options, current, on_change, parent=None) -> QWidget:
    box = QWidget(parent)
    box.setObjectName("segBox")
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    group = QButtonGroup(box)
    group.setExclusive(True)
    for value, label in options:
        btn = QPushButton(label, box)
        btn.setObjectName("segBtn")
        btn.setCheckable(True)
        btn.setChecked(value == current)
        btn.setCursor(Qt.PointingHandCursor)
        group.addButton(btn)
        lay.addWidget(btn)
        btn.clicked.connect(lambda _checked=False, v=value: on_change(v))
    lay.addStretch(1)
    return box


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = ThemeManager.instance()
        self._build_ui()
        self.theme.changed.connect(lambda *_: self._refresh_swatches())

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("设置")
        title.setObjectName("pageTitle")
        desc = QLabel("外观、字号与默认路径在这里统一配置，外观保存后立即全局生效。")
        desc.setObjectName("pageDesc")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        head.addLayout(title_box)
        head.addStretch(1)
        self.reset_btn = QPushButton("恢复默认")
        self.save_btn = QPushButton("保存设置")
        self.save_btn.setProperty("accent", True)
        head.addWidget(self.reset_btn)
        head.addWidget(self.save_btn)
        root.addLayout(head)

        cfg = app_config.load_config()

        appearance, lay, _head = _card("外观", "主题模式与字号对整个软件立即生效")
        row1 = QHBoxLayout()
        label1 = QLabel("主题模式")
        label1.setObjectName("fieldLabel")
        label1.setMinimumWidth(96)
        row1.addWidget(label1)
        row1.addWidget(_segmented(
            [(k, THEME_LABELS[k]) for k in ("dark", "light", "system")],
            self.theme.theme_mode, self._on_theme, self))
        row1.addStretch(1)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        label2 = QLabel("界面字号")
        label2.setObjectName("fieldLabel")
        label2.setMinimumWidth(96)
        row2.addWidget(label2)
        row2.addWidget(_segmented(
            [(k, FONT_LABELS[k]) for k in ("sm", "md", "lg", "xl")],
            self.theme.font_scale, self._on_font, self))
        row2.addStretch(1)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        label3 = QLabel("主题色")
        label3.setObjectName("fieldLabel")
        label3.setMinimumWidth(96)
        row3.addWidget(label3)
        self.swatches = {}
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(8)
        for key in ("blue", "amber", "teal", "violet"):
            btn = QPushButton(self)
            btn.setCheckable(True)
            btn.setFixedSize(22, 22)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(ACCENT_LABELS.get(key, key))
            btn.setChecked(key == self.theme.accent)
            btn.clicked.connect(lambda _c=False, k=key: self._on_accent(k))
            self.swatches[key] = btn
            swatch_row.addWidget(btn)
        self.accent_label = QLabel(ACCENT_LABELS.get(self.theme.accent, ""))
        self.accent_label.setObjectName("cardSub")
        swatch_row.addWidget(self.accent_label)
        swatch_row.addStretch(1)
        row3.addLayout(swatch_row)
        lay.addLayout(row3)
        self._refresh_swatches()
        root.addWidget(appearance)

        paths, play, _ = _card("默认路径", "留空表示输出到原文件旁的默认目录")
        self.enhance_dir = self._path_row(play, "图像增强输出目录", cfg.get("enhance_output_dir", ""))
        self.proxy_dir = self._path_row(play, "视频代理目录", cfg.get("proxy_output_dir", ""))
        self.audio_dir = self._path_row(play, "音频输出目录", cfg.get("audio_output_dir", ""))
        root.addWidget(paths)

        behavior, blay, _ = _card("行为")
        self.delete_confirm = QCheckBox("删除前二次确认")
        self.delete_confirm.setChecked(bool(cfg.get("delete_confirm", True)))
        self.skip_existing = QCheckBox("已存在的输出文件自动跳过")
        self.skip_existing.setChecked(bool(cfg.get("skip_existing", True)))
        self.open_after = QCheckBox("任务完成后打开输出目录")
        self.open_after.setChecked(bool(cfg.get("open_output_after_done", False)))
        for cb in (self.delete_confirm, self.skip_existing, self.open_after):
            blay.addWidget(cb)
        root.addWidget(behavior)
        root.addStretch(1)

        self.save_btn.clicked.connect(self._save)
        self.reset_btn.clicked.connect(self._reset)

    def _path_row(self, layout, label_text, value) -> QLineEdit:
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setMinimumWidth(140)
        edit = QLineEdit(value or "")
        edit.setPlaceholderText("留空使用默认目录")
        browse = QPushButton("浏览")
        browse.clicked.connect(lambda _c=False, e=edit: self._browse(e))
        row.addWidget(label)
        row.addWidget(edit, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        return edit

    def _browse(self, edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "选择目录", edit.text() or "")
        if folder:
            edit.setText(folder)

    def _refresh_swatches(self):
        from .theme import DARK, LIGHT
        border = LIGHT["TEXT"] if self.theme.resolved() == "light" else DARK["TEXT"]
        for key, btn in self.swatches.items():
            color = ACCENTS[key]["ACCENT"]
            btn.setStyleSheet(
                "QPushButton { background: %s; border: 2px solid transparent; border-radius: 11px; }"
                "QPushButton:checked { border: 2px solid %s; }" % (color, border))
            btn.setChecked(key == self.theme.accent)
        self.accent_label.setText(ACCENT_LABELS.get(self.theme.accent, ""))

    def _on_theme(self, value):
        self.theme.update(theme_mode=value)
        self._refresh_swatches()

    def _on_font(self, value):
        self.theme.update(font_scale=value)

    def _on_accent(self, value):
        self.theme.update(accent=value)
        self._refresh_swatches()

    def _save(self):
        app_config.save_config({
            "enhance_output_dir": self.enhance_dir.text().strip(),
            "proxy_output_dir": self.proxy_dir.text().strip(),
            "audio_output_dir": self.audio_dir.text().strip(),
            "delete_confirm": self.delete_confirm.isChecked(),
            "skip_existing": self.skip_existing.isChecked(),
            "open_output_after_done": self.open_after.isChecked(),
        })
        self.theme.update()
        QMessageBox.information(self, "设置", "设置已保存并立即生效")

    def _reset(self):
        self.theme.update(theme_mode="dark", accent="blue", font_scale="md")
        self.delete_confirm.setChecked(True)
        self.skip_existing.setChecked(True)
        self.open_after.setChecked(False)
        for edit in (self.enhance_dir, self.proxy_dir, self.audio_dir):
            edit.clear()
        self._refresh_swatches()
