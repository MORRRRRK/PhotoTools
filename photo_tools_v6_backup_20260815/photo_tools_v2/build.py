"""
build.py - PyInstaller 打包脚本
构建为单个可执行文件
"""

import os
import sys
import subprocess
from pathlib import Path


def build():
    """使用 PyInstaller 打包为 exe。"""
    # 项目根目录
    root = Path(__file__).parent.resolve()
    main_script = root / "photo_tools" / "main.py"
    icon_path = root / "photo_tools" / "icon.ico"

    # 参数
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",  # 单文件
        "--windowed",  # 无控制台
        "--name", "PhotoTools",
        "--distpath", str(root / "dist"),
        "--workpath", str(root / "build"),
        "--specpath", str(root),
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "customtkinter",
        "--hidden-import", "photo_tools",
        "--hidden-import", "photo_tools.scanner",
        "--hidden-import", "photo_tools.quality",
        "--hidden-import", "photo_tools.utils",
        "--hidden-import", "photo_tools.pushplus_client",
    ]

    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    # 添加数据文件
    cmd.extend(["--add-data", f"{root / 'photo_tools'}{os.pathsep}photo_tools"])

    cmd.append(str(main_script))

    print(f"[BUILD] 打包中: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(root))
    if result.returncode == 0:
        print(f"[BUILD] 打包成功: {root / 'dist' / 'PhotoTools.exe'}")
    else:
        print(f"[BUILD] 打包失败，返回码 {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(build())
