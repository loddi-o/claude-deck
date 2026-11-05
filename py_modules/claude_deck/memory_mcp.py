#!/usr/bin/env python3
"""Tiny MCP server (stdio, JSON-RPC 2.0, newline-delimited) exposing the long-term memory.

Usage: python3 memory_mcp.py /path/to/memory.md
Tools: remember(note), recall(), forget(match)
Standard library only.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_deck.memory import Memory  # noqa: E402

TOOLS = [
    {
        "name": "remember",
        "description": (
            "Save one durable fact about this device or the user in the persistent memory "
            "(hardware quirks, fixes that worked, packages installed, config changes, preferences). "
            "One short sentence. Never store passwords or secrets."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"note": {"type": "string", "description": "The fact to remember"}},
            "required": ["note"],
        },
    },
    {
        "name": "recall",
        "description": "Return the full persistent memory (all saved notes).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "forget",
        "description": "Delete every memory note containing the given text (case-insensitive).",
        "inputSchema": {
            "type": "object",
            "properties": {"match": {"type": "string", "description": "Text to look for"}},
            "required": ["match"],
        },
    },
]


def _result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def call_tool(memory: Memory, name: str, args: dict) -> dict:
    try:
        if name == "remember":
            line = memory.add(str(args.get("note", "")))
            return _result(f"Salvato in memoria: {line}")
        if name == "recall":
            return _result(memory.read() or "(vuota)")
        if name == "forget":
            n = memory.forget(str(args.get("match", "")))
            return _result(f"Rimosse {n} note.")
    except Exception as exc:  # noqa: BLE001 - report to the model instead of crashing
        return _result(f"Errore: {exc}", True)
    return _result(f"Strumento sconosciuto: {name}", True)


def handle(memory: Memory, msg: dict) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")
    if mid is None:  # notification
        return None
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion") or "2024-11-05"
        result = {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "claude_deck", "version": "0.1.0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = msg.get("params") or {}
        result = call_tool(memory, params.get("name", ""), params.get("arguments") or {})
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> None:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: memory_mcp.py MEMORY_FILE\n")
        sys.exit(2)
    memory = Memory(sys.argv[1])
    memory.ensure()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = handle(memory, msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
