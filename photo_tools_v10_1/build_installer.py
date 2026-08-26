"""build_installer.py - 构建独立安装器与卸载器 (V9.1)"""

import os
import subprocess
import sys
from pathlib import Path


def build():
    root = Path(__file__).parent.resolve()
    project_root = root.parent
    dist = root / "dist"
    build_dir = root / "build_installer"
    tcl_dir = project_root / "tcl"
    py = sys.executable

    main_exe = dist / "PhotoTools.exe"
    print("[BUILD] 构建主程序 PhotoTools.exe ...")
    subprocess.run([py, str(root / "build.py")], cwd=str(project_root), check=True)

    uninstaller_exe = dist / "PhotoToolsUninstall.exe"
    if not uninstaller_exe.exists():
        print("[BUILD] 构建 PhotoToolsUninstall.exe ...")
        cmd = [
            py, "-m", "PyInstaller",
            "--onefile", "--windowed", "--clean",
            "--name", "PhotoToolsUninstall",
            "--distpath", str(dist),
            "--workpath", str(build_dir),
            "--specpath", str(root),
            "--paths", str(project_root),
            "--add-data", f"{tcl_dir}{os.pathsep}tcl",
            str(root / "uninstaller.py"),
        ]
        subprocess.run(cmd, cwd=str(root), check=True)

    print("[BUILD] 构建 PhotoToolsSetup.exe ...")
    cmd = [
        py, "-m", "PyInstaller",
        "--onefile", "--windowed", "--clean",
        "--name", "PhotoToolsSetup",
        "--distpath", str(dist),
        "--workpath", str(build_dir),
        "--specpath", str(root),
        "--paths", str(project_root),
        "--add-data", f"{tcl_dir}{os.pathsep}tcl",
        "--add-binary", f"{main_exe}{os.pathsep}.",
        "--add-binary", f"{uninstaller_exe}{os.pathsep}.",
        str(root / "installer_gui.py"),
    ]
    subprocess.run(cmd, cwd=str(root), check=True)

    print("[BUILD] 构建完成:")
    print(f"  安装器:   {dist / 'PhotoToolsSetup.exe'}")
    print(f"  主程序:   {main_exe}")
    print(f"  卸载器:   {uninstaller_exe}")


if __name__ == "__main__":
    build()
