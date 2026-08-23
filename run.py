import sys, os, subprocess
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
    from photo_tools_v9_2.main import main
    main()
except Exception:
    with open(_log_path, "w", encoding="utf-8") as f:
        traceback.print_exc(file=f)
        f.write(f"Python: {sys.executable}\\n")
""")

codex_sp = r"C:\Users\49212\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\site-packages"
tcl_dir = r"C:\Users\49212\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\tcl"
env = os.environ.copy()
env["PYTHONPATH"] = codex_sp
env["TCL_LIBRARY"] = os.path.join(tcl_dir, "tcl8.6")
env["TK_LIBRARY"] = os.path.join(tcl_dir, "tk8.6")

candidates = [
    r"C:\Users\49212\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe",
    r"C:\Users\49212\AppData\Local\Microsoft\WindowsApps\pythonw.exe",
    r"C:\Users\49212\AppData\Local\Microsoft\WindowsApps\python.exe",
]
for exe in candidates:
    if os.path.exists(exe):
        try:
            subprocess.Popen([exe, app_script], env=env)
            sys.exit(0)
        except Exception:
            pass

with open(LOG, "w", encoding="utf-8") as f:
    f.write("All launch attempts failed")
input("Press Enter...")
