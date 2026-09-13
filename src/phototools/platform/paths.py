"""paths.py - 各平台标准目录解析"""

import os
import sys

APP_NAME = "PhotoTools"


def _ensure(path: str) -> str:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return _ensure(os.path.join(base, APP_NAME))


def cache_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return _ensure(os.path.join(base, APP_NAME, "preview_cache"))
    if sys.platform == "darwin":
        return _ensure(os.path.join(os.path.expanduser("~"), "Library", "Caches", APP_NAME))
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return _ensure(os.path.join(base, APP_NAME))


def logs_dir() -> str:
    return _ensure(os.path.join(config_dir(), "logs"))


def data_dir() -> str:
    return config_dir()


def lut_dir() -> str:
    return _ensure(os.path.join(config_dir(), "luts"))
