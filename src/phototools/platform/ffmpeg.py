"""ffmpeg.py - 跨平台 ffmpeg 定位（优先后端自带二进制）"""

import os
import shutil
import sys


def _bundled_candidates():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    names = ["ffmpeg.exe", "ffmpeg"] if sys.platform == "win32" else ["ffmpeg", "ffmpeg.exe"]
    for name in names:
        yield os.path.join(base, "assets", name)
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            for name in names:
                yield os.path.join(meipass, "assets", name)


def find_ffmpeg() -> str:
    """按优先级返回可用的 ffmpeg 路径，找不到返回空字符串。"""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    for candidate in _bundled_candidates():
        if os.path.exists(candidate):
            return candidate
    found = shutil.which("ffmpeg")
    if found:
        return found
    for extra in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if os.path.exists(extra):
            return extra
    return ""
