#!/usr/bin/env bash
# Installa Node LTS + pnpm@9 in user-space (nessun sudo, nessuna modifica al sistema).
# Destinazione: $CLAUDE_DECK_TOOLS (default ~/.cache/claude-deck-build)
set -euo pipefail

TOOLS="${CLAUDE_DECK_TOOLS:-$HOME/.cache/claude-deck-build}"
NODE_MAJOR="${NODE_MAJOR:-22}"
mkdir -p "$TOOLS"

if [ ! -x "$TOOLS/node/bin/node" ]; then
  echo "==> Scarico Node ${NODE_MAJOR}.x LTS"
  ver="$(curl -fsSL https://nodejs.org/dist/index.json | python3 -c '
import sys, json
m = sys.argv[1]
print(next(x["version"] for x in json.load(sys.stdin) if x["version"].startswith("v" + m + ".")))
' "$NODE_MAJOR")"
  curl -fsSL "https://nodejs.org/dist/${ver}/node-${ver}-linux-x64.tar.xz" | tar -xJ -C "$TOOLS"
  rm -rf "$TOOLS/node"
  mv "$TOOLS/node-${ver}-linux-x64" "$TOOLS/node"
fi

export PATH="$TOOLS/node/bin:$PATH"

if ! [ -x "$TOOLS/node/bin/pnpm" ]; then
  echo "==> Installo pnpm@9"
  npm install -g pnpm@9 --prefix "$TOOLS/node" >/dev/null
fi

echo "node $(node -v) · pnpm $(pnpm -v) · in $TOOLS"
