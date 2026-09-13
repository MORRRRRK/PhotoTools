"""logging_config.py - 统一日志配置（V11）"""

import logging
import os
from logging.handlers import RotatingFileHandler


def get_log_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "PhotoTools")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def setup_logging() -> None:
    root_logger = logging.getLogger("PhotoTools")
    if root_logger.handlers:
        return
    root_logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    try:
        file_handler = RotatingFileHandler(
            os.path.join(get_log_dir(), "photo_tools.log"),
            maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")
        file_handler.setFormatter(fmt)
        root_logger.addHandler(file_handler)
    except OSError:
        pass
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root_logger.addHandler(console)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"PhotoTools.{name}")


setup_logging()
