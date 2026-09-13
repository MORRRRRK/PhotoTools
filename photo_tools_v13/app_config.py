"""app_config.py - 用户级配置存储（跨平台可写目录）(V13)"""

import json
import os
import sys
from typing import Any, Dict

APP_NAME = "PhotoTools"

DEFAULT_CONFIG: Dict[str, Any] = {
    "appearance": "dark",
    "accent_color": "blue",
    "font_scale": "md",
    "max_workers": 4,
    "delete_confirm": True,
    "skip_existing": True,
    "open_output_after_done": False,
    "proxy_output_dir": "",
    "audio_output_dir": "",
    "enhance_output_dir": "",
}


def config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, APP_NAME)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


def bundled_defaults_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config() -> Dict[str, Any]:
    data = dict(DEFAULT_CONFIG)
    bundled = bundled_defaults_path()
    if os.path.exists(bundled):
        try:
            with open(bundled, "r", encoding="utf-8") as f:
                data.update(json.load(f) or {})
        except Exception:
            pass
    user_path = config_path()
    if os.path.exists(user_path):
        try:
            with open(user_path, "r", encoding="utf-8") as f:
                data.update(json.load(f) or {})
        except Exception:
            pass
    return data


def save_config(values: Dict[str, Any]) -> None:
    data = load_config()
    data.update(values or {})
    path = config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get(key: str, default: Any = None) -> Any:
    return load_config().get(key, default)


def set_many(values: Dict[str, Any]) -> None:
    save_config(values)
