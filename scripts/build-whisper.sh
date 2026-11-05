#!/usr/bin/env bash
# Compila whisper.cpp (whisper-cli) in modo quasi-statico (AVX2/FMA, senza OpenMP)
# e lo copia in bin/whisper-cli. Richiede gcc, g++, cmake, make, git.
# Il binario funziona su qualsiasi x86_64 con AVX2 (Steam Deck, ROG Ally, Legion Go, ...).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${WHISPER_WORK:-$HOME/.cache/claude-deck-build/whisper.cpp}"
REF="${WHISPER_REF:-}"

if [ -z "$REF" ]; then
  REF="$(git ls-remote --tags --refs https://github.com/ggml-org/whisper.cpp 'v*' \
        | sed 's#.*refs/tags/##' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)"
fi
echo "==> whisper.cpp ${REF}"

if [ ! -d "$WORK/.git" ]; then
  mkdir -p "$(dirname "$WORK")"
  git clone --depth 1 --branch "$REF" https://github.com/ggml-org/whisper.cpp "$WORK"
fi

cmake -S "$WORK" -B "$WORK/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF \
  -DGGML_NATIVE=OFF -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON \
  -DGGML_OPENMP=OFF \
  -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF -DWHISPER_BUILD_EXAMPLES=ON \
  -DCMAKE_EXE_LINKER_FLAGS="-static-libgcc -static-libstdc++"
cmake --build "$WORK/build" --config Release -j"$(nproc)" --target whisper-cli

install -m 0755 "$WORK/build/bin/whisper-cli" "$ROOT/bin/whisper-cli"
strip "$ROOT/bin/whisper-cli" || true
echo "$REF" > "$ROOT/bin/whisper-cli.version"
echo "==> OK: $(du -h "$ROOT/bin/whisper-cli" | cut -f1)  $ROOT/bin/whisper-cli"
ldd "$ROOT/bin/whisper-cli" || true
