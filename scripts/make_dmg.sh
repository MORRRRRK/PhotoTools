#!/usr/bin/env bash
# 把 dist/PhotoTools.app 打成可分发 DMG（含“应用程序”快捷方式）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/src/phototools/_version.py" | head -1)"
if [[ -z "$VERSION" ]]; then
  VERSION="0.0.0"
fi

APP="$ROOT/dist/PhotoTools.app"
if [[ ! -d "$APP" ]]; then
  echo "未找到 $APP，请先运行 scripts/build_macos.sh --no-dmg" >&2
  exit 1
fi

STAGE="$ROOT/build/dmg"
DMG="$ROOT/dist/PhotoTools-${VERSION}-arm64.dmg"

rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

rm -f "$DMG"
hdiutil create -volname "PhotoTools" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
echo "DMG 完成: $DMG"
