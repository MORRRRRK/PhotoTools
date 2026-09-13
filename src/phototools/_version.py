"""_version.py - 版本号唯一来源（Windows / macOS 共用）"""

__version__ = "13.0.0"
BUILD_DATE = "2026-09-13"
APP_NAME = "PhotoTools"


def version_tuple():
    return tuple(int(part) for part in __version__.split(".") if part.isdigit())
