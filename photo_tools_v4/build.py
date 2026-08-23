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
    project_root = root.parent
    main_script = root / "main.py"
    icon_path = root / "icon.ico"
    ffmpeg_path = root / "assets" / "ffmpeg.exe"

    # 参数
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",  # 单文件
        "--windowed",  # 无控制台
        "--clean",
        "--name", "PhotoTools",
        "--distpath", str(root / "dist"),
        "--workpath", str(root / "build"),
        "--specpath", str(root),
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "customtkinter",
        "--hidden-import", "photo_tools_v4",
        "--hidden-import", "photo_tools_v4.scanner",
        "--hidden-import", "photo_tools_v4.quality",
        "--hidden-import", "photo_tools_v4.utils",
        "--hidden-import", "photo_tools_v4.pushplus_client",
        "--hidden-import", "photo_tools_v4.preview",
        "--hidden-import", "photo_tools_v4.proxy",
        "--hidden-import", "photo_tools_v4.proxy_ui",
        "--hidden-import", "cv2",
        "--hidden-import", "rawpy",
        "--hidden-import", "exifread",
    ]

    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    # 添加运行期需要读取的数据文件
    for data_name in ("config.json", "eval_history.json"):
        data_path = root / data_name
        if data_path.exists():
            cmd.extend(["--add-data", f"{data_path}{os.pathsep}photo_tools_v4"])
    cmd.extend(["--add-data", f"{project_root / 'tcl'}{os.pathsep}tcl"])
    cmd.extend(["--collect-all", "customtkinter"])
    cmd.extend(["--collect-all", "PIL"])

    if ffmpeg_path.exists():
        cmd.extend(["--add-binary", f"{ffmpeg_path}{os.pathsep}assets"])
    else:
        print("[BUILD] 警告: photo_tools_v4/assets/ffmpeg.exe 不存在，打包后无法生成代理")

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
