#!/usr/bin/env bash
# PhotoTools macOS 一次性环境准备（Apple Silicon）
# 用法： bash scripts/mac_setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== PhotoTools macOS 环境准备 =="

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "此脚本仅用于 macOS；当前系统：$(uname -s)" >&2
  exit 1
fi

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "提示：当前架构为 $(uname -m)，构建脚本按 Apple Silicon(arm64) 配置。" >&2
fi

if ! xcode-select -p >/dev/null 2>&1; then
  echo "未检测到 Xcode Command Line Tools（PyInstaller 与 codesign 需要）。"
  echo "即将触发系统安装窗口，安装完成后请重新运行本脚本。"
  xcode-select --install || true
  exit 0
fi
echo "Xcode CLT: $(xcode-select -p)"

PY="$(command -v python3.12 || command -v python3 || true)"
if [[ -z "$PY" ]]; then
  echo "未找到 python3，请先从 https://www.python.org/downloads/ 安装 Python 3.12" >&2
  exit 1
fi
VERSION="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "Python: $VERSION ($PY)"
case "$VERSION" in
  3.12|3.13|3.14) ;;
  *) echo "需要 Python 3.12 或更高版本，当前 $VERSION" >&2; exit 1 ;;
esac

if [[ ! -d .venv ]]; then
  echo "创建虚拟环境 .venv ..."
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip >/dev/null
echo "安装依赖（首次约 3-6 分钟）..."
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-macos.txt
# PyInstaller 只在打包时需要，不放进跨平台运行依赖，这里单独安装。
.venv/bin/pip install "pyinstaller>=6.0"

.venv/bin/python - <<'PY'
import importlib.util as u
import sys
required = ["PySide6", "cv2", "numpy", "PIL", "rawpy", "onnxruntime", "imageio_ffmpeg", "scipy", "skimage", "PyInstaller"]
missing = [name for name in required if not u.find_spec(name)]
if missing:
    print("缺少依赖: " + ", ".join(missing))
    sys.exit(1)
import imageio_ffmpeg
print("自带 ffmpeg: " + imageio_ffmpeg.get_ffmpeg_exe())
print("依赖检查通过")
PY

echo ""
echo "环境就绪。下一步执行： ./scripts/build_macos.sh"
