#!/bin/bash
# Builds GhostMail.app and a distributable DMG on macOS.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "[1/3] Installing build dependencies..."
"$PYTHON" -m pip install --disable-pip-version-check -r requirements.txt -r requirements-build.txt

echo "[2/3] Building GhostMail.app..."
"$PYTHON" -m PyInstaller --clean --noconfirm GhostMail.spec

echo "[3/3] Creating DMG..."
mkdir -p installer/output
rm -f installer/output/GhostMail.dmg
hdiutil create -volname "GhostMail" -srcfolder "dist/GhostMail.app" -ov -format UDZO "installer/output/GhostMail.dmg"

echo ""
echo "Done: installer/output/GhostMail.dmg"
echo "Note: unsigned builds require right-click > Open (or System Settings approval) on first launch."
