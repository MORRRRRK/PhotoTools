"""run.py - 开发模式启动入口（Windows / macOS 通用）

用法：
    python run.py                 # 使用当前解释器
    .venv/bin/python run.py       # macOS 虚拟环境
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from phototools.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
