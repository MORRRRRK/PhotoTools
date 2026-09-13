"""theme.py - V13 主题系统：设计 token、QSS 生成与全局主题管理"""

import os
from typing import Dict

from PySide6.QtCore import QObject, Signal

from . import app_config

FONT_SANS = ('"Microsoft YaHei UI", "PingFang SC", "Inter", "Helvetica Neue", sans-serif')
FONT_MONO = '"JetBrains Mono", "Cascadia Mono", "Consolas", "SF Mono", monospace'

DARK: Dict[str, str] = {
    "BG": "#171c24",
    "PANEL": "#1f2630",
    "PANEL2": "#232a36",
    "BORDER": "#303a48",
    "TEXT": "#e5e7eb",
    "MUTED": "#9aa3b2",
    "NAV_BG": "#10141a",
    "NAV_TEXT": "#c7ccd4",
    "NAV_BORDER": "rgba(255,255,255,15)",
    "NAV_HOVER": "rgba(255,255,255,15)",
    "NAV_HOVER_TEXT": "#ffffff",
    "NAV_GROUP_TITLE": "rgba(255,255,255,140)",
    "NAV_BRAND_TEXT": "#ffffff",
    "NAV_SEG_BG": "rgba(255,255,255,15)",
    "BTN": "#2a3340",
    "BTN_HOVER": "#34404f",
    "INPUT": "#232a36",
    "HEADER": "#232a36",
    "ROW_ALT": "#293240",
    "ROW_HOVER": "#2b3441",
    "SCROLL": "#3a4554",
    "SCROLL_HOVER": "#4a5668",
    "GRID_LINE": "rgba(255,255,255,13)",
    "CANVAS": "#0d1014",
    "DANGER": "#ef4444",
    "DANGER_TEXT": "#f87171",
    "DANGER_SOFT": "rgba(239,68,68,36)",
    "SUCCESS": "#16a34a",
    "SUCCESS_TEXT": "#4ade80",
    "WARNING": "#d97706",
    "WARNING_TEXT": "#fbbf24",
    "SHADOW": "rgba(0,0,0,0.38)",
}

LIGHT: Dict[str, str] = {
    "BG": "#f5f6f8",
    "PANEL": "#ffffff",
    "PANEL2": "#eef0f4",
    "BORDER": "#e2e5ea",
    "TEXT": "#1f2430",
    "MUTED": "#5f6b7c",
    "NAV_BG": "#ffffff",
    "NAV_TEXT": "#4b5563",
    "NAV_BORDER": "#e2e5ea",
    "NAV_HOVER": "#f1f3f7",
    "NAV_HOVER_TEXT": "#1f2430",
    "NAV_GROUP_TITLE": "#6b7280",
    "NAV_BRAND_TEXT": "#1f2430",
    "NAV_SEG_BG": "#eef0f4",
    "BTN": "#eef0f4",
    "BTN_HOVER": "#e2e6ec",
    "INPUT": "#ffffff",
    "HEADER": "#f1f3f7",
    "ROW_ALT": "#f8fafc",
    "ROW_HOVER": "#eef2f7",
    "SCROLL": "#c8ced8",
    "SCROLL_HOVER": "#aab2bf",
    "GRID_LINE": "rgba(15,23,42,15)",
    "CANVAS": "#e9edf2",
    "DANGER": "#dc2626",
    "DANGER_TEXT": "#b91c1c",
    "DANGER_SOFT": "rgba(220,38,38,26)",
    "SUCCESS": "#16a34a",
    "SUCCESS_TEXT": "#166534",
    "WARNING": "#b45309",
    "WARNING_TEXT": "#92400e",
    "SHADOW": "rgba(15,23,42,0.10)",
}

ACCENTS: Dict[str, Dict[str, str]] = {
    "blue": {
        "ACCENT": "#2563eb", "ACCENT_HOVER": "#1d4ed8",
        "ACCENT_TEXT": "#8ab4f8", "ACCENT_TEXT_LIGHT": "#1d4ed8",
        "ACCENT_SOFT": "rgba(37,99,235,46)", "ACCENT_SOFT_LIGHT": "rgba(37,99,235,26)",
    },
    "amber": {
        "ACCENT": "#d97706", "ACCENT_HOVER": "#b45309",
        "ACCENT_TEXT": "#fbbf24", "ACCENT_TEXT_LIGHT": "#92400e",
        "ACCENT_SOFT": "rgba(217,119,6,46)", "ACCENT_SOFT_LIGHT": "rgba(217,119,6,31)",
    },
    "teal": {
        "ACCENT": "#0d9488", "ACCENT_HOVER": "#0f766e",
        "ACCENT_TEXT": "#5eead4", "ACCENT_TEXT_LIGHT": "#115e59",
        "ACCENT_SOFT": "rgba(13,148,136,46)", "ACCENT_SOFT_LIGHT": "rgba(13,148,136,31)",
    },
    "violet": {
        "ACCENT": "#7c3aed", "ACCENT_HOVER": "#6d28d9",
        "ACCENT_TEXT": "#c4b5fd", "ACCENT_TEXT_LIGHT": "#6d28d9",
        "ACCENT_SOFT": "rgba(124,58,237,46)", "ACCENT_SOFT_LIGHT": "rgba(124,58,237,31)",
    },
}

ACCENT_LABELS = {"blue": "蓝", "amber": "琥珀", "teal": "青绿", "violet": "紫"}
THEME_LABELS = {"dark": "深色", "light": "浅色", "system": "跟随系统"}
FONT_LABELS = {"sm": "小", "md": "中", "lg": "大", "xl": "特大"}

FONT_SCALES: Dict[str, Dict[str, str]] = {
    "sm": {"FS_BASE": "13px", "FS_SMALL": "11px", "FS_NAV": "13px", "FS_TITLE": "20px",
           "FS_SECTION": "14px", "FS_CARD": "22px", "ROW_H": "30px", "CTL_H": "30px", "NAV_ROW": "40px"},
    "md": {"FS_BASE": "14px", "FS_SMALL": "12px", "FS_NAV": "14px", "FS_TITLE": "22px",
           "FS_SECTION": "15px", "FS_CARD": "24px", "ROW_H": "32px", "CTL_H": "32px", "NAV_ROW": "44px"},
    "lg": {"FS_BASE": "15px", "FS_SMALL": "12px", "FS_NAV": "15px", "FS_TITLE": "23px",
           "FS_SECTION": "16px", "FS_CARD": "26px", "ROW_H": "34px", "CTL_H": "34px", "NAV_ROW": "46px"},
    "xl": {"FS_BASE": "17px", "FS_SMALL": "13px", "FS_NAV": "16px", "FS_TITLE": "26px",
           "FS_SECTION": "18px", "FS_CARD": "30px", "ROW_H": "38px", "CTL_H": "38px", "NAV_ROW": "50px"},
}


def resolve_theme(mode: str) -> str:
    if mode in ("dark", "light"):
        return mode
    try:
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import Qt
        hints = QGuiApplication.styleHints()
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Light:
            return "light"
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
    except Exception:
        pass
    return "dark"


def tokens(resolved_theme: str, accent_name: str) -> Dict[str, str]:
    data = dict(DARK if resolved_theme == "dark" else LIGHT)
    accent = ACCENTS.get(accent_name) or ACCENTS["blue"]
    data.update(accent)
    if resolved_theme == "dark":
        data["ACCENT_TEXT"] = accent["ACCENT_TEXT"]
        data["ACCENT_SOFT"] = accent["ACCENT_SOFT"]
        data["NAV_ACTIVE_TEXT"] = "#ffffff"
    else:
        data["ACCENT_TEXT"] = accent["ACCENT_TEXT_LIGHT"]
        data["ACCENT_SOFT"] = accent["ACCENT_SOFT_LIGHT"]
        data["NAV_ACTIVE_TEXT"] = accent["ACCENT_TEXT_LIGHT"]
    data["FONT_SANS"] = FONT_SANS
    data["FONT_MONO"] = FONT_MONO
    return data


def template_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "style_template.qss")


def build_stylesheet(resolved_theme: str, accent_name: str, font_scale: str,
                     template: str = "") -> str:
    if not template:
        with open(template_path(), "r", encoding="utf-8") as f:
            template = f.read()
    data = tokens(resolved_theme, accent_name)
    data.update(FONT_SCALES.get(font_scale) or FONT_SCALES["md"])
    for key, value in data.items():
        template = template.replace("__" + key + "__", value)
    return template


class ThemeManager(QObject):
    changed = Signal(str, str, str)

    _instance = None

    def __init__(self):
        super().__init__()
        cfg = app_config.load_config()
        self.theme_mode = str(cfg.get("appearance") or "dark")
        self.accent = str(cfg.get("accent_color") or "blue")
        self.font_scale = str(cfg.get("font_scale") or "md")
        if self.accent not in ACCENTS:
            self.accent = "blue"
        if self.font_scale not in FONT_SCALES:
            self.font_scale = "md"

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def resolved(self) -> str:
        return resolve_theme(self.theme_mode)

    def stylesheet(self) -> str:
        return build_stylesheet(self.resolved(), self.accent, self.font_scale)

    def apply(self, app=None) -> None:
        from PySide6.QtWidgets import QApplication
        application = app or QApplication.instance()
        if application is not None:
            application.setStyleSheet(self.stylesheet())
        self.changed.emit(self.theme_mode, self.accent, self.font_scale)

    def update(self, theme_mode=None, accent=None, font_scale=None, persist=True) -> None:
        if theme_mode in ("dark", "light", "system"):
            self.theme_mode = theme_mode
        if accent in ACCENTS:
            self.accent = accent
        if font_scale in FONT_SCALES:
            self.font_scale = font_scale
        if persist:
            app_config.set_many({
                "appearance": self.theme_mode,
                "accent_color": self.accent,
                "font_scale": self.font_scale,
            })
        self.apply()
