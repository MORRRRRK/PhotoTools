# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\49212\\Documents\\素材管理\\photo_tools_v5_1\\config.json', 'photo_tools_v5_1'), ('C:\\Users\\49212\\Documents\\素材管理\\photo_tools_v5_1\\eval_history.json', 'photo_tools_v5_1'), ('C:\\Users\\49212\\Documents\\素材管理\\tcl', 'tcl')]
binaries = [('C:\\Users\\49212\\Documents\\素材管理\\photo_tools_v5_1\\assets\\ffmpeg.exe', 'assets')]
hiddenimports = ['PIL._tkinter_finder', 'customtkinter', 'photo_tools_v5_1', 'photo_tools_v5_1.scanner', 'photo_tools_v5_1.quality', 'photo_tools_v5_1.utils', 'photo_tools_v5_1.pushplus_client', 'photo_tools_v5_1.preview', 'photo_tools_v5_1.proxy', 'photo_tools_v5_1.proxy_ui', 'photo_tools_v5_1.timelapse', 'photo_tools_v5_1.timelapse_ui', 'cv2', 'rawpy', 'exifread']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:\\Users\\49212\\Documents\\素材管理\\photo_tools_v5_1\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PhotoTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
