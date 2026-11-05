#!/usr/bin/env bash
# Renders the real plugin components in headless Chrome (Flatpak or native) with a mocked Decky
# environment and saves screenshots: QAM width (308px) and full screen (1280x800).
# usage: scripts/ui-shots.sh [OUT_DIR]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/.tools/ui-shots}"
source "$ROOT/scripts/env.sh"
mkdir -p "$OUT"
node "$ROOT/tests/ui-harness/build.mjs" "$OUT"

if command -v google-chrome-stable >/dev/null; then CHROME=(google-chrome-stable --no-sandbox)
elif command -v chromium >/dev/null; then CHROME=(chromium --no-sandbox)
elif flatpak info com.google.Chrome >/dev/null 2>&1; then CHROME=(flatpak run --filesystem="$OUT" com.google.Chrome)
else echo "no Chrome/Chromium found" >&2; exit 1; fi

shot() { # name view scenario tab width height [lang=it] [steam-language]
  local q="view=$2&scenario=$3&tab=$4&lang=${7:-it}"
  [ -n "${8:-}" ] && q="$q&steam=$8"
  "${CHROME[@]}" --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=3500 \
    --window-size="$5,$6" --screenshot="$OUT/$1.png" "file://$OUT/index.html?$q" >/dev/null 2>&1
  echo "  $1.png"
}
for sc in empty chat perm edit plan question streaming streaming-tool notices; do
  shot "full-$sc" full "$sc" chat 1280 800
  shot "qam-$sc" qam "$sc" chat 330 1000
done
for tab in sessions memory settings; do shot "full-tab-$tab" full chat "$tab" 1280 800; done
shot "full-settings-missing" full setup-missing settings 1280 1500
shot "qam-setup-missing" qam setup-missing chat 330 800
# English UI, and automatic language following Steam's (simulated) language
for sc in chat perm setup-missing; do shot "en-qam-$sc" qam "$sc" chat 330 1000 en; done
shot en-full-empty full empty chat 1280 800 en
shot en-full-settings full chat settings 1280 1500 en
shot auto-it-qam qam chat chat 330 1000 auto italian
shot auto-de-qam qam chat chat 330 1000 auto german
echo "done -> $OUT"
