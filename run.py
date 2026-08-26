"""PhotoTools 启动器：动态查找 Python 解释器，无硬编码用户路径。"""

import glob
import os
import shutil
import subprocess
import sys

root = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(root, "error.log")
app_script = os.path.join(root, "_app.py")

if not os.path.exists(app_script):
    with open(app_script, "w", encoding="utf-8") as f:
        f.write("""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
try:
    if os.path.exists(_log_path):
        os.remove(_log_path)
except OSError:
    pass
try:
    from photo_tools_v11.main import main
    main()
except Exception:
    with open(_log_path, "w", encoding="utf-8") as f:
        traceback.print_exc(file=f)
        f.write(f"Python: {sys.executable}\\n")
""")


def find_pythonw() -> list:
    candidates = []
    exe = getattr(sys, "executable", "")
    if exe:
        candidates.append(exe)
        if exe.lower().endswith("python.exe"):
            pw = exe[:-4] + "w.exe"
            if os.path.exists(pw):
                candidates.insert(0, pw)
    for name in ("pythonw", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    localappdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    patterns = [
        os.path.join(localappdata, "Programs", "Python", "Python3*", "pythonw.exe"),
        os.path.join(localappdata, "Programs", "Python", "Python3*", "python.exe"),
        os.path.join(localappdata, "Microsoft", "WindowsApps", "pythonw.exe"),
        os.path.join(localappdata, "Microsoft", "WindowsApps", "python.exe"),
    ]
    for pattern in patterns:
        candidates.extend(sorted(glob.glob(pattern)))
    seen = set()
    result = []
    for p in candidates:
        key = os.path.normcase(os.path.abspath(p))
        if p and os.path.exists(p) and key not in seen:
            seen.add(key)
            result.append(p)
    return result


def main():
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    for exe in find_pythonw():
        try:
            subprocess.Popen([exe, app_script], env=env)
            return 0
        except Exception:
            continue
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("All launch attempts failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
