# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/49212/Documents/素材管理/photo_tools_v9_1/uninstaller.py'],
    pathex=['C:/Users/49212/Documents/素材管理'],
    binaries=[],
    datas=[('C:/Users/49212/Documents/素材管理/tcl', 'tcl')],
    hiddenimports=[],
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
    name='PhotoToolsUninstall',
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
