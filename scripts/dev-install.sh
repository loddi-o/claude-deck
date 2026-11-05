#!/usr/bin/env bash
# Developer helper: installs the current build straight into Decky and reloads it.
# Needs sudo (the plugins folder belongs to root) and Decky Loader running as plugin_loader.service.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${DECKY_PLUGINS:-$HOME/homebrew/plugins}/claude-deck"
[ -f "$ROOT/dist/index.js" ] || { echo "run scripts/build.sh first" >&2; exit 1; }

echo "==> installing to $DEST"
sudo rm -rf "$DEST"
sudo mkdir -p "$DEST"
sudo tar -C "$ROOT" --exclude=./node_modules --exclude=./.git --exclude=./.tools --exclude='*.zip' \
  --exclude=__pycache__ --exclude='./dist/*.map' -cf - . | sudo tar -C "$DEST" -xf -
sudo chown -R "$USER":"$USER" "$DEST"
sudo chmod 755 "$DEST" "$DEST/plugin.json" "$DEST"/bin/*
sudo chown root:root "$DEST" "$DEST/plugin.json"
echo "==> restarting Decky Loader (this briefly reloads the Steam UI)"
sudo systemctl restart plugin_loader
echo "done"
