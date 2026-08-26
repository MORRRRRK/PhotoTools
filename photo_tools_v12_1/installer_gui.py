import logging
logger = logging.getLogger(__name__)

"""installer_gui.py - PhotoTools 独立安装器 (V12.0)"""

import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

if getattr(sys, "frozen", False):
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        os.environ.setdefault("TCL_LIBRARY", os.path.join(meipass, "tcl", "tcl8.6"))
        os.environ.setdefault("TK_LIBRARY", os.path.join(meipass, "tcl", "tk8.6"))

APP_NAME = "PhotoTools"
APP_VERSION = "12.1.0"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PhotoTools"
MARKER_KEY = r"Software\PhotoTools"
CREATE_NO_WINDOW = 0x08000000
SILENT = "--silent" in sys.argv


def bundled_file(name: str) -> str:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
        p = base / name
        if p.exists():
            return str(p)
    p = Path(__file__).resolve().parent.parent / "photo_tools_v12_1" / "dist" / name
    return str(p) if p.exists() else ""


def write_registry(install_dir: str):
    import winreg
    exe = os.path.join(install_dir, "PhotoTools.exe")
    uninst = os.path.join(install_dir, "PhotoToolsUninstall.exe")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ,
                          "PhotoTools 摄影素材管理工具箱")
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "PhotoTools")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, exe)
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                          f'"{uninst}"')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, MARKER_KEY) as key:
        winreg.SetValueEx(key, "InstallPath", 0, winreg.REG_SZ, install_dir)
        winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "CachePath", 0, winreg.REG_SZ,
                          os.path.join(install_dir, "PhotoTools", "preview_cache"))


def create_shortcut(exe: str):
    try:
        folder = os.path.dirname(exe)
        ps = (
            "$ws = New-Object -ComObject WScript.Shell; "
            "$lnk = [Environment]::GetFolderPath('Desktop') + '\\PhotoTools.lnk'; "
            f"$s = $ws.CreateShortcut($lnk); $s.TargetPath = '{exe.replace(chr(39), chr(39)+chr(39))}'; "
            f"$s.WorkingDirectory = '{folder.replace(chr(39), chr(39)+chr(39))}'; $s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW,
        )
    except Exception as _exc: logger.warning("handled exception", exc_info=True)


class InstallerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION} 安装程序")
        self.geometry("560x260")
        self.resizable(False, False)
        self.configure(bg="#f0f0f0")
        self._build()

    def _build(self):
        tk.Label(self, text=f"安装 {APP_NAME} {APP_VERSION}",
                 font=("Microsoft YaHei", 15, "bold"), bg="#f0f0f0").pack(pady=(16, 4))
        tk.Label(self, text="请选择安装目录，安装后生成 PhotoTools.exe 与卸载程序",
                 font=("Microsoft YaHei", 10), bg="#f0f0f0").pack()

        row = tk.Frame(self, bg="#f0f0f0")
        row.pack(fill="x", padx=20, pady=14)
        self.path_var = tk.StringVar(value=self.default_dir())
        tk.Entry(row, textvariable=self.path_var, width=52).pack(side="left")
        tk.Button(row, text="浏览", command=self._browse).pack(side="left", padx=6)

        tk.Button(self, text="开始安装", width=24, height=2,
                  font=("Microsoft YaHei", 11, "bold"),
                  command=self._install).pack(pady=8)
        self.status_lb = tk.Label(self, text="", fg="#1f6feb", bg="#f0f0f0",
                                  font=("Microsoft YaHei", 10))
        self.status_lb.pack()

    @staticmethod
    def default_dir() -> str:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "Programs", APP_NAME)

    def _browse(self):
        folder = filedialog.askdirectory(title="选择安装目录")
        if folder:
            self.path_var.set(folder)

    def _install(self):
        dest = self.path_var.get().strip().strip('"')
        if not dest:
            if SILENT:
                return
            messagebox.showwarning("提示", "请选择安装目录")
            return
        main_exe = bundled_file("PhotoTools.exe")
        uninst_exe = bundled_file("PhotoToolsUninstall.exe")
        if not main_exe or not uninst_exe:
            if SILENT:
                return
            messagebox.showerror("错误", "安装负载缺失：PhotoTools.exe 或 PhotoToolsUninstall.exe")
            return
        self.status_lb.configure(text="正在安装...")
        self.update()
        try:
            os.makedirs(dest, exist_ok=True)
            shutil.copy2(main_exe, os.path.join(dest, "PhotoTools.exe"))
            shutil.copy2(uninst_exe, os.path.join(dest, "PhotoToolsUninstall.exe"))
            write_registry(dest)
            create_shortcut(os.path.join(dest, "PhotoTools.exe"))
        except Exception as e:
            self.status_lb.configure(text="安装失败", fg="#c0392b")
            if not SILENT:
                messagebox.showerror("安装失败", str(e))
            return
        self.status_lb.configure(text="安装完成", fg="#2ecc71")
        if not SILENT:
            messagebox.showinfo("安装完成",
                                f"{APP_NAME} 已安装到：\n{dest}\n桌面已创建快捷方式。")


if __name__ == "__main__":
    if "--install-path" in sys.argv:
        idx = sys.argv.index("--install-path")
        dest = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        app = InstallerApp()
        app.path_var.set(dest)
        if SILENT:
            app.withdraw()
            app.update()
            app._install()
        else:
            app._install()
        app.destroy()
    else:
        InstallerApp().mainloop()
