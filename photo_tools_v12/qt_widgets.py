"""qt_widgets.py - V10 自定义控件：照片卡片、环形评分、折叠面板、Toast"""

import math

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class PhotoCardWidget(QFrame):
    """缩略图卡片：图片居中、文件名单行省略、评分角标、格式标签、悬停操作按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PhotoCard")
        self.setFixedSize(176, 148)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame#PhotoCard { background: #1E1E1E; border: 1px solid #333333;"
            " border-radius: 6px; }"
            "QFrame#PhotoCard[selected=\"true\"] { border: 2px solid #4A90D9; }"
            "QFrame#PhotoCard:hover { border-color: #4A90D9; }")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 6)
        lay.setSpacing(4)

        self.image_lb = QLabel("加载中...", self)
        self.image_lb.setAlignment(Qt.AlignCenter)
        self.image_lb.setMinimumHeight(96)
        self.image_lb.setStyleSheet("border: none; background: transparent; color: #888888;")
        lay.addWidget(self.image_lb, 1)

        self.name_lb = QLabel("", self)
        self.name_lb.setStyleSheet("border: none; color: #FFFFFF; background: transparent;")
        self.name_lb.setToolTip("")
        lay.addWidget(self.name_lb)

        self.score_badge = QLabel("", self)
        self.score_badge.setStyleSheet(
            "border-radius: 8px; background: rgba(74,144,217,180); color: #FFFFFF;"
            "padding: 1px 6px;")
        self.score_badge.setVisible(False)

        self.format_badge = QLabel("", self)
        self.format_badge.setStyleSheet(
            "border-radius: 4px; background: #3A3A3A; color: #CCCCCC;"
            "padding: 0px 5px;")
        self.format_badge.setVisible(False)

        self.actions = QWidget(self)
        self.actions.setStyleSheet("background: transparent; border: none;")
        act_lay = QHBoxLayout(self.actions)
        act_lay.setContentsMargins(0, 0, 0, 0)
        act_lay.setSpacing(4)
        self.zoom_btn = QToolButton(self.actions)
        self.zoom_btn.setText("放大")
        self.fav_btn = QToolButton(self.actions)
        self.fav_btn.setText("收藏")
        self.del_btn = QToolButton(self.actions)
        self.del_btn.setText("删除")
        for b in (self.zoom_btn, self.fav_btn, self.del_btn):
            b.setStyleSheet("QToolButton { background: rgba(20,20,20,180); color: white;"
                            " border: none; border-radius: 3px; padding: 2px 5px; }")
            act_lay.addWidget(b)
        self.actions.setVisible(False)
        self.actions.setGeometry(8, 8, 160, 24)

        self._selected = False
        self._data = {}

    def set_photo(self, pixmap: QPixmap):
        if pixmap and not pixmap.isNull():
            self.image_lb.setPixmap(pixmap)
        else:
            self.image_lb.setText("无法预览")

    def set_meta(self, name: str, fmt: str = "", score: str = ""):
        self.name_lb.setText(name)
        self.name_lb.setToolTip(name)
        if fmt:
            self.format_badge.setText(fmt)
            self.format_badge.setVisible(True)
            self.format_badge.move(8, self.height() - 24)
        if score:
            self.score_badge.setText(score)
            self.score_badge.setVisible(True)
            self.score_badge.adjustSize()
            self.score_badge.move(self.width() - self.score_badge.width() - 8, 8)

    def set_selected(self, selected: bool):
        self._selected = selected
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def is_selected(self) -> bool:
        return self._selected

    def set_data(self, data: dict):
        self._data = data

    def get_data(self) -> dict:
        return self._data

    def enterEvent(self, event):
        self.actions.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.actions.setVisible(False)
        super().leaveEvent(event)


class RingProgressWidget(QWidget):
    """环形评分控件：外圈灰环、主色内环按百分比填充、中心分数。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 150)
        self._value = 0.0
        self._animation = QPropertyAnimation(self, b"value", self)
        self._animation.setDuration(500)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float):
        self._value = max(0.0, min(100.0, float(value)))
        self.update()

    value = property(get_value, set_value)

    def animate_to(self, value: float):
        self._animation.stop()
        self._animation.setStartValue(self._value)
        self._animation.setEndValue(max(0.0, min(100.0, float(value))))
        self._animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#3A3A3A"), 10, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(12, 12, 126, 126)
        if self._value > 0:
            pen = QPen(QColor("#4A90D9"), 10, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen)
            span = int(-360 * self._value / 100.0)
            painter.drawArc(12, 12, 126, 126, 90 * 16, span * 16)
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Microsoft YaHei", 20)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, f"{self._value:.0f}")
        painter.end()


class CollapsiblePanel(QFrame):
    """可折叠面板：标题栏点击展开/收起，内容区放入 QScrollArea。"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Collapsible")
        self.setStyleSheet(
            "QFrame#Collapsible { background: #1E1E1E; border: 1px solid #3A3A3A;"
            " border-radius: 6px; }")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = QToolButton(self)
        self.header.setText("▼ " + title)
        self.header.setCheckable(True)
        self.header.setChecked(True)
        self.header.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.header.setStyleSheet(
            "QToolButton { background: transparent; color: #FFFFFF; border: none;"
            " text-align: left; padding: 10px 12px; font-weight: bold; }"
            "QToolButton:hover { background: #2D2D30; }")
        root.addWidget(self.header)

        self.content = QScrollArea(self)
        self.content.setWidgetResizable(True)
        self.content.setFrameShape(QFrame.NoFrame)
        self.content.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(10, 6, 10, 10)
        self.content.setWidget(self.body)
        root.addWidget(self.content)

        self.header.clicked.connect(self._toggle)
        self._expanded = True

    def body_layout(self) -> QVBoxLayout:
        return self.body_lay

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        self.content.setVisible(expanded)
        self.header.setText(("▼ " if expanded else "▶ ") + self.header.text()[2:])

    def is_expanded(self) -> bool:
        return self._expanded

    def _toggle(self):
        self.set_expanded(self.header.isChecked())


class Toast(QLabel):
    """右下角 Toast 提示，3 秒后自动消失。"""

    def __init__(self, parent: QWidget, text: str):
        super().__init__(text, parent)
        self.setStyleSheet(
            "background: #2D2D30; color: #FFFFFF; border: 1px solid #4A90D9;"
            "border-radius: 6px; padding: 10px 18px;")
        self.adjustSize()
        self.move(parent.width() - self.width() - 24, parent.height() - self.height() - 40)
        self.show()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._timer.start(3000)


class DropOverlay(QWidget):
    """拖拽导入时覆盖中央区的半透明提示层。"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setStyleSheet(
            "background: rgba(37,37,38,220); border: 2px dashed #4A90D9;")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        label = QLabel("释放以导入文件", self)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #FFFFFF; font-size: 26px; font-weight: bold;"
                            " background: transparent; border: none;")
        lay.addWidget(label)
        self.hide()

    def show_for(self, parent: QWidget):
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.raise_()
        self.show()

    def hide_overlay(self):
        self.hide()
