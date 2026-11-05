#!/usr/bin/env bash
# Full local check + build: typecheck, frontend tests, backend tests, rollup bundle.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source scripts/env.sh
if ! command -v pnpm >/dev/null; then
  bash scripts/setup-node.sh
  source scripts/env.sh
fi
[ -d node_modules ] || pnpm install --frozen-lockfile

echo "==> typecheck";        pnpm run typecheck
echo "==> frontend tests";   pnpm run test
echo "==> backend compile";  python3 -I -m compileall -q py_modules main.py
echo "==> backend tests";    python3 -m unittest discover -s tests/backend -t tests/backend
echo "==> bundle";           pnpm run build
echo "OK: dist/index.js ready"
