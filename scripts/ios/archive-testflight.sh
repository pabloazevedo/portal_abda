#!/usr/bin/env bash
# Arquiva Release no Mac e prepara upload TestFlight (requer Apple Team + Xcode signed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/mobile/ios/App"
ARCHIVE_DIR="${ARCHIVE_DIR:-$ROOT/mobile/ios/build}"
SCHEME=PortalMembro

mkdir -p "$ARCHIVE_DIR"
cd "$APP"

if [[ -x "$ROOT/.tools/xcodegen/bin/xcodegen" ]]; then
  "$ROOT/.tools/xcodegen/bin/xcodegen" generate
elif command -v xcodegen >/dev/null; then
  xcodegen generate
fi

echo "==> archive Release"
xcodebuild \
  -project PortalMembro.xcodeproj \
  -scheme "$SCHEME" \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE_DIR/PortalMembro.xcarchive" \
  DEVELOPMENT_TEAM="${DEVELOPMENT_TEAM:?defina DEVELOPMENT_TEAM=XXXXXXXX}" \
  archive

echo "==> export / upload (App Store Connect)"
xcodebuild -exportArchive \
  -archivePath "$ARCHIVE_DIR/PortalMembro.xcarchive" \
  -exportOptionsPlist ExportOptions-TestFlight.plist \
  -exportPath "$ARCHIVE_DIR/export"

echo "Pronto. Confira TestFlight no App Store Connect (conta da orquestra)."
