# -*- mode: python ; coding: utf-8 -*-
"""PhotoTools macOS 打包配置（onedir + .app，Apple Silicon，未签名）"""
import os

def project_root():
    import os
    candidates = []
    for name in ("SPEC", "SPECPATH"):
        value = globals().get(name)
        if value:
            candidates.append(os.path.abspath(value))
    if "__file__" in globals():
        candidates.append(os.path.abspath(__file__))
    candidates.append(os.getcwd())
    for candidate in candidates:
        current = os.path.dirname(candidate) if os.path.isfile(candidate) else candidate
        for _ in range(5):
            if os.path.isdir(os.path.join(current, "src", "phototools")):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
    return os.getcwd()


def collect_project_data():
    import os
    from PyInstaller.utils.hooks import collect_all
    pkg = os.path.join(project_root(), "src", "phototools")
    datas = []
    for name in ("config.json", "style_template.qss", "style.qss"):
        candidate = os.path.join(pkg, name)
        if os.path.exists(candidate):
            datas.append((candidate, "phototools"))
    for folder in ("luts", "models"):
        candidate = os.path.join(pkg, folder)
        if os.path.exists(candidate):
            datas.append((candidate, "phototools/" + folder))
    binaries = []
    hidden = []
    for package in ("PIL", "imageio_ffmpeg"):
        try:
            data, binary, hook_hidden = collect_all(package)
            datas += data
            binaries += binary
            hidden += hook_hidden
        except Exception:
            pass
    return datas, binaries, hidden


def project_hidden_imports():
    import os
    pkg = os.path.join(project_root(), "src", "phototools")
    modules = ["phototools", "phototools.platform",
               "phototools.platform.paths", "phototools.platform.shell",
               "phototools.platform.process", "phototools.platform.ffmpeg",
               "phototools.platform.install"]
    modules += ["phototools." + name[:-3] for name in sorted(os.listdir(pkg))
                if name.endswith(".py") and name != "__init__.py"]
    modules += ["cv2", "rawpy", "exifread", "onnxruntime"]
    return modules


def read_version():
    import os
    import re
    path = os.path.join(project_root(), "src", "phototools", "_version.py")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            match = re.search(r'__version__\s*=\s*"([^"]+)"', handle.read())
        if match:
            return match.group(1)
    except OSError:
        pass
    return "0.0.0"


datas, binaries, extra_hidden = collect_project_data()
hiddenimports = project_hidden_imports() + extra_hidden

src = os.path.join(project_root(), "src")
entry = os.path.join(src, "phototools", "launcher.py")
version = read_version()

a = Analysis(
    [entry],
    pathex=[src],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PhotoTools",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch="arm64",
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PhotoTools",
)

app = BUNDLE(
    coll,
    name="PhotoTools.app",
    icon=None,
    bundle_identifier="com.phototools.app",
    info_plist={
        "CFBundleName": "PhotoTools",
        "CFBundleDisplayName": "PhotoTools",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "CFBundleExecutable": "PhotoTools",
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.photography",
        "NSRequiresAquaSystemAppearance": False,
        "NSHumanReadableCopyright": "PhotoTools",
    },
)
