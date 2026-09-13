"""
build.py - PyInstaller 打包脚本 (V12.1)
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

    # 排除运行时自带的第三方原生库目录，避免 PyInstaller 误打包 PATH 里的
    # icuuc.dll / icudt*.dll 等，导致 Qt6Core 加载时提示“找不到指定的程序”。
    env = os.environ.copy()
    keep = []
    for p in env.get("PATH", "").split(os.pathsep):
        low = p.lower()
        if not p:
            continue
        if "dependencies" in low and "native" in low:
            continue
        keep.append(p)
    env["PATH"] = os.pathsep.join(keep)

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
        "--hidden-import", "phototools",
        "--hidden-import", "phototools.qt_main",
        "--hidden-import", "phototools.qt_pages",
        "--hidden-import", "phototools.qt_widgets",
        "--hidden-import", "phototools.quality_page",
        "--hidden-import", "phototools.scanner",
        "--hidden-import", "phototools.scanner_ui",
        "--hidden-import", "phototools.quality",
        "--hidden-import", "phototools.utils",
        "--hidden-import", "phototools.pushplus_client",
        "--hidden-import", "phototools.preview",
        "--hidden-import", "phototools.proxy",
        "--hidden-import", "phototools.audio_extract",
        "--hidden-import", "phototools.timelapse",
        "--hidden-import", "phototools.dynamic_extract",
        "--hidden-import", "phototools.gallery",
        "--hidden-import", "phototools.convert",
        "--hidden-import", "phototools.auto_color",
        "--hidden-import", "phototools.auto_color_ui",
        "--hidden-import", "phototools.lut_loader",
        "--hidden-import", "phototools.image_pipeline",
        "--hidden-import", "phototools.image_pipeline_ui",
        "--hidden-import", "phototools.geometric_correction",
        "--hidden-import", "phototools.auto_crop",
        "--hidden-import", "phototools.content_fill",
        "--hidden-import", "phototools.app_config",
        "--hidden-import", "phototools.theme",
        "--hidden-import", "phototools.settings_page",
        "--hidden-import", "phototools.about_page",
        "--hidden-import", "phototools.platform_utils",
        "--hidden-import", "phototools.image_view",
        "--hidden-import", "cv2",
        "--hidden-import", "rawpy",
        "--hidden-import", "exifread",
        "--hidden-import", "onnxruntime",
    ]

    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    for data_name in ("config.json", "eval_history.json"):
        data_path = root / data_name
        if data_path.exists():
            cmd.extend(["--add-data", f"{data_path}{os.pathsep}phototools"])
    style_path = root / "style.qss"
    if style_path.exists():
        cmd.extend(["--add-data", f"{style_path}{os.pathsep}phototools"])
    template_path = root / "style_template.qss"
    if template_path.exists():
        cmd.extend(["--add-data", f"{template_path}{os.pathsep}phototools"])
    lut_dir = root / "luts"
    if lut_dir.exists():
        cmd.extend(["--add-data", f"{lut_dir}{os.pathsep}phototools/luts"])
    models_dir = root / "models"
    if models_dir.exists():
        cmd.extend(["--add-data", f"{models_dir}{os.pathsep}phototools/models"])
    cmd.extend(["--collect-all", "PIL"])

    if ffmpeg_path.exists():
        cmd.extend(["--add-binary", f"{ffmpeg_path}{os.pathsep}assets"])
    else:
        print("[BUILD] 警告: phototools/assets/ffmpeg.exe 不存在")

    cmd.append(str(main_script))

    print(f"[BUILD] 打包中: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(root), env=env)
    if result.returncode == 0:
        print(f"[BUILD] 打包成功: {root / 'dist' / 'PhotoTools.exe'}")
    else:
        print(f"[BUILD] 打包失败，返回码 {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(build())
