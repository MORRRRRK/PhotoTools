"""
build.py - PyInstaller 打包脚本 (V10.1)
构建为单个可执行文件
"""

import os
import sys
import subprocess
from pathlib import Path


def build():
    root = Path(__file__).parent.resolve()
    project_root = root.parent
    main_script = root / "launcher.py"
    icon_path = root / "icon.ico"
    ffmpeg_path = root / "assets" / "ffmpeg.exe"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--paths", str(project_root),
        "--onefile",
        "--windowed",
        "--clean",
        "--name", "PhotoTools",
        "--distpath", str(root / "dist"),
        "--workpath", str(root / "build"),
        "--specpath", str(root),
        "--hidden-import", "photo_tools_v10_1",
        "--hidden-import", "photo_tools_v10_1.qt_main",
        "--hidden-import", "photo_tools_v10_1.qt_pages",
        "--hidden-import", "photo_tools_v10_1.qt_widgets",
        "--hidden-import", "photo_tools_v10_1.quality_page",
        "--hidden-import", "photo_tools_v10_1.scanner",
        "--hidden-import", "photo_tools_v10_1.quality",
        "--hidden-import", "photo_tools_v10_1.utils",
        "--hidden-import", "photo_tools_v10_1.pushplus_client",
        "--hidden-import", "photo_tools_v10_1.preview",
        "--hidden-import", "photo_tools_v10_1.proxy",
        "--hidden-import", "photo_tools_v10_1.audio_extract",
        "--hidden-import", "photo_tools_v10_1.timelapse",
        "--hidden-import", "photo_tools_v10_1.dynamic_extract",
        "--hidden-import", "photo_tools_v10_1.gallery",
        "--hidden-import", "photo_tools_v10_1.convert",
        "--hidden-import", "cv2",
        "--hidden-import", "rawpy",
        "--hidden-import", "exifread",
    ]

    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    for data_name in ("config.json", "eval_history.json"):
        data_path = root / data_name
        if data_path.exists():
            cmd.extend(["--add-data", f"{data_path}{os.pathsep}photo_tools_v10_1"])
    style_path = root / "style.qss"
    if style_path.exists():
        cmd.extend(["--add-data", f"{style_path}{os.pathsep}photo_tools_v10_1"])
    cmd.extend(["--collect-all", "PIL"])

    if ffmpeg_path.exists():
        cmd.extend(["--add-binary", f"{ffmpeg_path}{os.pathsep}assets"])
    else:
        print("[BUILD] 警告: photo_tools_v10_1/assets/ffmpeg.exe 不存在")

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
