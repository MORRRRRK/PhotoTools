import logging
logger = logging.getLogger(__name__)

"""uninstaller.py - PhotoTools 独立卸载器 (V12.0)"""

import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

if getattr(sys, "frozen", False):
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        os.environ.setdefault("TCL_LIBRARY", os.path.join(meipass, "tcl", "tcl8.6"))
        os.environ.setdefault("TK_LIBRARY", os.path.join(meipass, "tcl", "tk8.6"))

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PhotoTools"
MARKER_KEY = r"Software\PhotoTools"
CACHE_REL = os.path.join("PhotoTools", "preview_cache")
CREATE_NO_WINDOW = 0x08000000
SILENT = "--silent" in sys.argv
DELETE_CACHE = "--delete-cache" in sys.argv


def install_path_from_registry() -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MARKER_KEY) as key:
            return winreg.QueryValueEx(key, "InstallPath")[0]
    except Exception as _exc:
        return ""


def resolve_install_path() -> str:
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--install-path" and i + 1 < len(args):
            return args[i + 1]
    reg = install_path_from_registry()
    if reg and os.path.isdir(reg):
        return reg
    if not os.environ.get("PT_UNINSTALL_TEMP"):
        return os.path.dirname(os.path.abspath(sys.executable))
    return ""


def relaunch_from_temp():
    if os.environ.get("PT_UNINSTALL_TEMP"):
        return False
    install_path = resolve_install_path()
    temp_dir = os.environ.get("TEMP") or os.path.dirname(sys.executable)
    temp_exe = os.path.join(temp_dir, "PhotoToolsUninstall_tmp.exe")
    try:
        shutil.copy2(sys.executable, temp_exe)
    except Exception as _exc:
        return False
    env = os.environ.copy()
    env["PT_UNINSTALL_TEMP"] = "1"
    cmd = [temp_exe] + sys.argv[1:]
    if install_path and "--install-path" not in sys.argv[1:]:
        cmd.extend(["--install-path", install_path])
    subprocess.Popen(cmd, env=env)
    return True


def remove_registry():
    try:
        import winreg
        for key in (UNINSTALL_KEY, MARKER_KEY):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
            except OSError:
                pass
    except Exception as _exc: logger.warning("handled exception", exc_info=True)


def remove_shortcut():
    try:
        ps = (
            "$lnk = [Environment]::GetFolderPath('Desktop') + '\\PhotoTools.lnk'; "
            "if (Test-Path $lnk) { Remove-Item $lnk -Force }"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW,
        )
    except Exception as _exc: logger.warning("handled exception", exc_info=True)


def delete_install_dir(install_dir: str, keep_cache: bool):
    if not os.path.isdir(install_dir):
        return []
    failed = []
    cache_path = os.path.normcase(os.path.abspath(
        os.path.join(install_dir, CACHE_REL)))
    for name in os.listdir(install_dir):
        p = os.path.join(install_dir, name)
        if keep_cache and os.path.normcase(os.path.abspath(p)) == cache_path:
            continue
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)
        except OSError:
            failed.append(p)
    if not keep_cache:
        try:
            shutil.rmtree(install_dir)
        except Exception as e:
            failed.append(f"{install_dir}: {e}")
    return failed


def is_main_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq PhotoTools.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW,
        ).stdout or ""
        return "PhotoTools.exe" in out
    except Exception as _exc:
        return False


def force_close_main():
    try:
        subprocess.run(
            ["taskkill", "/IM", "PhotoTools.exe", "/F"],
            capture_output=True, timeout=20, creationflags=CREATE_NO_WINDOW,
        )
    except Exception as _exc: logger.warning("handled exception", exc_info=True)


def schedule_self_delete():
    try:
        exe = os.path.abspath(sys.executable)
        ps = (
            "Start-Sleep -Seconds 2; "
            f"Remove-Item -LiteralPath '{exe.replace(chr(39), chr(39)+chr(39))}' -Force -ErrorAction SilentlyContinue"
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as _exc: logger.warning("handled exception", exc_info=True)


class UninstallerApp(tk.Tk):
    def __init__(self, install_dir: str):
        super().__init__()
        self.install_dir = install_dir
        self.title("PhotoTools 卸载程序")
        self.geometry("560x280")
        self.resizable(False, False)
        self.configure(bg="#f0f0f0")
        self._build()

    def _build(self):
        tk.Label(self, text="卸载 PhotoTools",
                 font=("Microsoft YaHei", 15, "bold"), bg="#f0f0f0").pack(pady=(16, 4))
        tk.Label(self, text=f"安装位置：{self.install_dir}",
                 font=("Microsoft YaHei", 10), bg="#f0f0f0",
                 wraplength=500, justify="left").pack(padx=20)
        self.keep_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            self, text="保留本机缓存（二次安装到同一路径可直接复用，不删除照片预览缓存）",
            variable=self.keep_var, bg="#f0f0f0",
            font=("Microsoft YaHei", 10)).pack(anchor="w", padx=30, pady=12)
        tk.Button(self, text="确认卸载", width=24, height=2,
                  font=("Microsoft YaHei", 11, "bold"),
                  command=self._uninstall).pack(pady=6)
        self.status_lb = tk.Label(self, text="", fg="#1f6feb", bg="#f0f0f0",
                                  font=("Microsoft YaHei", 10))
        self.status_lb.pack()

    def _uninstall(self):
        if is_main_running():
            if not SILENT:
                if not messagebox.askyesno(
                        "检测到 PhotoTools 正在运行",
                        "卸载时需要删除 PhotoTools.exe，但程序正在运行会被 Windows 锁定。\n"
                        "是否强制关闭 PhotoTools 后继续卸载？"):
                    return
            force_close_main()
            self.update()
        if not SILENT and not messagebox.askyesno("确认卸载", "确定要卸载 PhotoTools 吗？"):
            return
        keep = (not DELETE_CACHE) if SILENT else self.keep_var.get()
        self.status_lb.configure(text="正在卸载...")
        self.update()
        remove_registry()
        remove_shortcut()
        failed = delete_install_dir(self.install_dir, keep)
        if not keep:
            cache_root = os.path.dirname(self.install_dir)
            # 卸载器只在明确要求时删除 %LOCALAPPDATA%\\PhotoTools 旧缓存
            local_root = os.path.join(
                os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                "PhotoTools")
            try:
                if os.path.isdir(local_root):
                    shutil.rmtree(local_root, ignore_errors=True)
            except Exception as _exc: logger.warning("handled exception", exc_info=True)
        self.status_lb.configure(text="卸载完成", fg="#2ecc71")
        if failed and not SILENT:
            messagebox.showwarning(
                "卸载未完全完成",
                "部分文件删除失败（可能被其他程序占用）：\n" +
                "\n".join(failed[:8]) +
                "\n请关闭占用程序后重试。")
        elif not SILENT:
            messagebox.showinfo(
                "卸载完成",
                "PhotoTools 已卸载。" +
                ("已保留本机缓存。" if keep else "已删除本机缓存。"))
        schedule_self_delete()
        self.after(800, self.destroy)


if __name__ == "__main__":
    if relaunch_from_temp():
        sys.exit(0)
    path = resolve_install_path()
    if SILENT:
        app = UninstallerApp(path)
        app.withdraw()
        app.update()
        app._uninstall()
        app.destroy()
    else:
        UninstallerApp(path).mainloop()
