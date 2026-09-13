"""install.py - 安装状态与卸载（Windows 注册表 / macOS app bundle）"""

import os
import shutil
import sys

from . import paths, shell

APP_NAME = "PhotoTools"
MAC_APP_NAME = "PhotoTools.app"
MAC_INSTALL_PATH = "/Applications/" + MAC_APP_NAME

if sys.platform == "win32":
    MARKER_KEY = r"Software\PhotoTools"
    UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PhotoTools"
else:
    MARKER_KEY = ""
    UNINSTALL_KEY = ""


def _win_registry_install_dir() -> str:
    if sys.platform != "win32":
        return ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MARKER_KEY) as key:
            return winreg.QueryValueEx(key, "InstallPath")[0] or ""
    except Exception:
        return ""


def install_dir() -> str:
    if sys.platform == "win32":
        return _win_registry_install_dir()
    if sys.platform == "darwin":
        if os.path.exists(MAC_INSTALL_PATH):
            return MAC_INSTALL_PATH
        return ""
    return ""


def is_installed() -> bool:
    return bool(install_dir())


def app_bundle_path() -> str:
    if sys.platform == "darwin":
        if os.path.exists(MAC_INSTALL_PATH):
            return MAC_INSTALL_PATH
        exe = os.path.abspath(sys.executable)
        for parent in (exe, os.path.dirname(exe)):
            if parent.endswith(".app"):
                return parent
        return ""
    return ""


def remove_user_data() -> bool:
    """删除配置/缓存/日志/自定义预设，绝不动用户的图片与视频输出。"""
    ok = True
    for target in (paths.config_dir(), paths.cache_dir()):
        try:
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=False)
        except Exception as e:
            print(f"[ERROR] 删除 {target} 失败: {e}")
            ok = False
    return ok


def uninstall(remove_data: bool = True):
    """返回 (是否成功, 提示信息)。Windows 调用自带卸载器；macOS 把 .app 移入废纸篓。"""
    if sys.platform == "darwin":
        bundle = app_bundle_path()
        if not bundle:
            return False, "未找到 PhotoTools.app，可能已经是开发环境运行"
        moved = shell.send_to_trash(bundle)
        data_ok = remove_user_data() if remove_data else True
        if moved:
            return True, "PhotoTools 已移入废纸篓" + ("，配置与缓存已清理" if data_ok else "，但部分缓存未清理")
        return False, "移入废纸篓失败，请手动把 PhotoTools.app 拖到废纸篓"
    if sys.platform == "win32":
        import subprocess
        uninstaller = os.path.join(install_dir(), "PhotoToolsUninstall.exe")
        if os.path.exists(uninstaller):
            subprocess.Popen([uninstaller])
            return True, "已启动卸载程序"
        return False, "未找到卸载程序"
    return False, "当前平台不支持应用内卸载"
