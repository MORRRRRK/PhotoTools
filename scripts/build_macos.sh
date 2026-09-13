#!/usr/bin/env bash
# 构建 macOS 版（Apple Silicon）：PhotoTools.app + DMG
# 用法： ./scripts/build_macos.sh [--no-dmg]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
  else
    PYTHON="$(command -v python3 || true)"
  fi
fi
if [[ -z "$PYTHON" ]]; then
  echo "未找到 python3。请先安装 Python 3.12 并创建虚拟环境：" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

echo "使用解释器: $PYTHON"
if ! "$PYTHON" - <<'PY'
import importlib.util as u
import sys
required = ["PySide6", "cv2", "numpy", "PIL", "rawpy", "onnxruntime", "imageio_ffmpeg", "scipy", "skimage"]
missing = [name for name in required if not u.find_spec(name)]
if missing:
    print("缺少依赖: " + ", ".join(missing))
    sys.exit(1)
PY
then
  echo "请先安装依赖：$PYTHON -m pip install -r requirements.txt" >&2
  exit 1
fi

"$PYTHON" -m PyInstaller --noconfirm --clean \
  --distpath "$ROOT/dist" \
  --workpath "$ROOT/build/mac" \
  "$ROOT/packaging/PhotoTools.mac.spec"

APP="$ROOT/dist/PhotoTools.app"
if [[ -d "$APP" ]]; then
  # 未签名交付：做 ad-hoc 签名，保证本机可运行
  codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
  echo "构建完成: $APP"
else
  echo "构建失败：未生成 $APP" >&2
  exit 1
fi

if [[ "${1:-}" != "--no-dmg" ]]; then
  bash "$ROOT/scripts/make_dmg.sh"
fi
