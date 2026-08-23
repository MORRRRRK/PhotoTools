
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
        f.write(f"Python: {sys.executable}\n")
