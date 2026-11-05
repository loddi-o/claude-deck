# Da "sourciare": rende disponibili node/pnpm installati da setup-node.sh
TOOLS="${CLAUDE_DECK_TOOLS:-$HOME/.cache/claude-deck-build}"
if [ -x "$TOOLS/node/bin/node" ]; then
  export PATH="$TOOLS/node/bin:$PATH"
fi
