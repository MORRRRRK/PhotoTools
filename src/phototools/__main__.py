"""__main__.py - 允许 python -m phototools 启动"""

import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
