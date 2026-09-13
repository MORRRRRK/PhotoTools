"""platform_utils.py - 兼容层：转发到 phototools.platform（保留旧导入路径）"""

from .platform.ffmpeg import find_ffmpeg  # noqa: F401
from .platform.paths import APP_NAME, cache_dir, config_dir, data_dir, logs_dir  # noqa: F401
from .platform.process import CREATE_NO_WINDOW, subprocess_flags  # noqa: F401
from .platform.shell import (  # noqa: F401
    open_path,
    reveal_in_file_manager,
    send_to_trash,
    send_to_trash_many,
)

__all__ = [
    "find_ffmpeg", "subprocess_flags", "CREATE_NO_WINDOW",
    "open_path", "reveal_in_file_manager", "send_to_trash", "send_to_trash_many",
    "config_dir", "cache_dir", "logs_dir", "data_dir", "APP_NAME",
]
