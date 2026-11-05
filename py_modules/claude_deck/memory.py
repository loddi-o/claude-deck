"""Long-term memory: a plain markdown file shared by the GUI, the agent (through the MCP
server in memory_mcp.py) and the system prompt."""

from __future__ import annotations

import os
from typing import List

from .util import atomic_write, today

HEADER = (
    "# Memoria di Claude Deck\n"
    "Note persistenti su questo dispositivo. Claude le legge a ogni nuova conversazione.\n\n"
    "## Note\n"
)


class Memory:
    def __init__(self, path: str, seed_path: str | None = None):
        self.path = path
        self.seed_path = seed_path

    def ensure(self) -> None:
        if os.path.exists(self.path):
            return
        text = HEADER
        if self.seed_path and os.path.exists(self.seed_path):
            try:
                with open(self.seed_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                pass
        atomic_write(self.path, text, 0o644)

    def read(self) -> str:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def write(self, text: str) -> None:
        atomic_write(self.path, text if text.endswith("\n") else text + "\n", 0o644)

    def add(self, note: str) -> str:
        note = " ".join(note.split())
        if not note:
            raise ValueError("empty note")
        text = self.read() or HEADER
        if not text.endswith("\n"):
            text += "\n"
        line = f"- [{today()}] {note}"
        self.write(text + line + "\n")
        return line

    def forget(self, needle: str) -> int:
        needle = needle.strip().lower()
        if not needle:
            return 0
        kept: List[str] = []
        removed = 0
        for line in self.read().splitlines():
            if line.lstrip().startswith("- ") and needle in line.lower():
                removed += 1
            else:
                kept.append(line)
        if removed:
            self.write("\n".join(kept))
        return removed

    def clear(self) -> None:
        self.write(HEADER)

    def prompt_block(self, limit: int = 7000) -> str:
        """Memory text for the system prompt; drops the oldest lines when too long."""
        text = self.read().strip()
        if len(text) <= limit:
            return text or "(vuota)"
        lines = text.splitlines()
        head, body = lines[:3], lines[3:]
        out: List[str] = []
        size = sum(len(x) + 1 for x in head)
        for line in reversed(body):
            if size + len(line) + 1 > limit:
                break
            out.append(line)
            size += len(line) + 1
        out.reverse()
        return "\n".join(head + ["(… note più vecchie omesse: usa lo strumento recall …)"] + out)
