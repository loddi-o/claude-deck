#!/usr/bin/env bash
# Builds the installable ZIP for Decky: <OUT>/claude-deck-v<version>.zip
# The archive has a single root folder "claude-deck/" (what Decky's installer expects) and contains
# the whole repository + the built dist/ + bin/whisper-cli (if built). No node_modules, no .git,
# no docs/media (screenshots and videos are only for the README).
# usage: scripts/package.sh [OUT_DIR]      (default: parent directory of the repo)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$(dirname "$ROOT")}"
cd "$ROOT"

VERSION="$(python3 -c 'import json; print(json.load(open("package.json"))["version"])')"
[ -f dist/index.js ] || { echo "dist/index.js missing: run scripts/build.sh first" >&2; exit 1; }
[ -f plugin.json ] && [ -f main.py ] || { echo "plugin.json/main.py missing" >&2; exit 1; }
if [ ! -x bin/whisper-cli ]; then
  echo "WARNING: bin/whisper-cli not found - voice dictation will need it (run scripts/build-whisper.sh)" >&2
fi
chmod 755 bin/sudo bin/askpass scripts/*.sh 2>/dev/null || true
[ -f bin/whisper-cli ] && chmod 755 bin/whisper-cli

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/claude-deck"
tar -C "$ROOT" \
  --exclude='./node_modules' --exclude='./.git' --exclude='./.tools' --exclude='*.zip' \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='./dist/*.map' --exclude='.pytest_cache' \
  --exclude='./docs/media' \
  -cf - . | tar -C "$STAGE/claude-deck" -xf -

ZIP="$OUT/claude-deck-v${VERSION}.zip"
rm -f "$ZIP"
(cd "$STAGE" && zip -qr -X "$ZIP" claude-deck)

echo "==> $ZIP ($(du -h "$ZIP" | cut -f1))"
unzip -l "$ZIP" | grep -E "claude-deck/(plugin.json|package.json|main.py|dist/index.js|bin/)" || true
