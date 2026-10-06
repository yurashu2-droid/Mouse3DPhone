#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "An unsigned iOS build still requires macOS and Xcode. Use GitHub Actions on Windows." >&2
  exit 1
fi
xcodebuild -version
xcodebuild \
  -project iOS/SpatialPointer.xcodeproj \
  -scheme SpatialPointer \
  -configuration Release \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath "$ROOT/.derived" \
  ARCHS=arm64 \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGN_IDENTITY= \
  build

APP="$ROOT/.derived/Build/Products/Release-iphoneos/SpatialPointer.app"
if codesign --display "$APP" >/dev/null 2>&1; then
  echo "Unexpected signed bundle; refusing to label it unsigned." >&2
  exit 1
fi
python3 tools/package_ipa.py --app "$APP" --output "$ROOT/dist/SpatialPointer-unsigned.ipa"
