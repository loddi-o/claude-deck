"""Reads Claude Code's own session transcripts (~/.claude/projects/<cwd>/<session>.jsonl) to list
past conversations and to rebuild the chat when one is resumed."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from .util import shrink

NOISE_PREFIXES = (
    "<system-reminder>",
    "<local-command-caveat>",
    "<local-command-stdout>",
    "<command-name>",
    "<command-message>",
    "Caveat: The messages below",
)


def project_dir(claude_home: str, cwd: str) -> str:
    return os.path.join(claude_home, "projects", re.sub(r"[^A-Za-z0-9]", "-", cwd))


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p)
    return ""


def _is_noise(text: str) -> bool:
    stripped = text.lstrip()
    return not stripped or stripped.startswith(NOISE_PREFIXES)


def _scan_meta(path: str) -> Dict[str, str]:
    """Title (ai-title, else first real user prompt) of a transcript, without parsing every line."""
    title = ""
    first_prompt = ""
    last_prompt = ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"ai-title"' in line[:80]:
                    try:
                        title = json.loads(line).get("aiTitle", "") or title
                    except ValueError:
                        pass
                elif '"last-prompt"' in line[:80]:
                    try:
                        last_prompt = json.loads(line).get("lastPrompt", "") or last_prompt
                    except ValueError:
                        pass
                elif not first_prompt and '"type":"user"' in line:
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    if obj.get("isSidechain") or obj.get("isMeta"):
                        continue
                    text = _text_of((obj.get("message") or {}).get("content"))
                    if not _is_noise(text):
                        first_prompt = text
    except OSError:
        pass
    return {"title": (title or first_prompt or last_prompt or "").strip()}


def list_sessions(claude_home: str, cwd: str, limit: int = 30) -> List[Dict[str, Any]]:
    directory = project_dir(claude_home, cwd)
    try:
        names = [n for n in os.listdir(directory) if n.endswith(".jsonl")]
    except OSError:
        return []
    entries = []
    for name in names:
        path = os.path.join(directory, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        entries.append((st.st_mtime, st.st_size, name, path))
    entries.sort(reverse=True)
    out: List[Dict[str, Any]] = []
    for mtime, size, name, path in entries[:limit]:
        meta = _scan_meta(path)
        title = meta["title"]
        if not title:
            continue  # empty session (no prompt ever sent)
        out.append(
            {
                "id": name[: -len(".jsonl")],
                "title": " ".join(title.split())[:120],
                "mtime": int(mtime),
                "age_s": max(0, int(time.time() - mtime)),
                "size": size,
            }
        )
    return out


def _convert_block_content(content: Any) -> Any:
    return shrink(content, max_str=4000, max_items=60)


def load_history(claude_home: str, cwd: str, session_id: str, limit: int = 160) -> List[Dict[str, Any]]:
    """Transcript -> list of stream-json-like events ('user'/'assistant') for the UI."""
    path = os.path.join(project_dir(claude_home, cwd), f"{session_id}.jsonl")
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", session_id) or not os.path.isfile(path):
        return []
    events: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                # Key order differs between line kinds ("type" can come after a big "message"),
                # so test the whole line; escaped quotes inside strings can't match.
                if '"type":"user"' not in line and '"type":"assistant"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if obj.get("isSidechain") or obj.get("isMeta"):
                    continue
                kind = obj.get("type")
                msg = obj.get("message")
                if kind not in ("user", "assistant") or not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                if kind == "user":
                    if isinstance(content, str) and _is_noise(content):
                        continue
                    if isinstance(content, list) and not any(
                        isinstance(b, dict) and b.get("type") in ("text", "tool_result") for b in content
                    ):
                        continue
                    if isinstance(content, list) and all(
                        isinstance(b, dict) and b.get("type") == "text" and _is_noise(b.get("text", ""))
                        for b in content
                    ):
                        continue
                events.append(
                    {
                        "type": kind,
                        "history": True,
                        "message": {
                            "id": msg.get("id", ""),
                            "role": msg.get("role", kind),
                            "model": msg.get("model", ""),
                            "content": _convert_block_content(content),
                        },
                    }
                )
    except OSError:
        return []
    return events[-limit:]


def delete_session(claude_home: str, cwd: str, session_id: str) -> bool:
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", session_id):
        return False
    path = os.path.join(project_dir(claude_home, cwd), f"{session_id}.jsonl")
    try:
        os.unlink(path)
        return True
    except OSError:
        return False


def newest_session_id(claude_home: str, cwd: str) -> Optional[str]:
    sessions = list_sessions(claude_home, cwd, limit=1)
    return sessions[0]["id"] if sessions else None
