"""process.py - 子进程平台差异封装"""

import sys

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def subprocess_flags() -> int:
    """Windows 下隐藏控制台窗口；POSIX 必须返回 0，否则 Popen 会报错。"""
    return CREATE_NO_WINDOW


def is_windows() -> bool:
    return sys.platform == "win32"


def is_macos() -> bool:
    return sys.platform == "darwin"
