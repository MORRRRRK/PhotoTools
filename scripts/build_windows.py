"""build_windows.py - 构建 Windows 单文件 exe

用法（仓库根目录）：
    python scripts/build_windows.py
产物：
    dist/PhotoTools.exe
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "PhotoTools.win.spec"


def main() -> int:
    if not SPEC.exists():
        print(f"[BUILD] 找不到打包配置: {SPEC}")
        return 1
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "win"),
        str(SPEC),
    ]
    print("[BUILD] " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode == 0:
        print(f"[BUILD] 完成: {ROOT / 'dist' / 'PhotoTools.exe'}")
    else:
        print(f"[BUILD] 失败，返回码 {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
