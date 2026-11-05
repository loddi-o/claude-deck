"""Encoding/decoding of the Claude Code `stream-json` control protocol.

Shapes follow the official claude-agent-sdk-python:
  host -> CLI : {"type":"user",...}, {"type":"control_request","request_id","request":{"subtype":...}}
  CLI  -> host: {"type":"control_request","request":{"subtype":"can_use_tool",...}} that the host answers with
                {"type":"control_response","response":{"subtype":"success","request_id",
                 "response":{"behavior":"allow"|"deny",...}}}
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

PLAN = "plan"
AUTO = "auto"
ACCEPT_EDITS = "acceptEdits"
UI_MODES = (PLAN, AUTO)

TOOL_EXIT_PLAN = "ExitPlanMode"
TOOL_ASK = "AskUserQuestion"


def dumps(obj: Dict[str, Any]) -> bytes:
    return (json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def new_request_id() -> str:
    return "cd_" + uuid.uuid4().hex[:12]


def user_message(text: str, session_id: str = "") -> Dict[str, Any]:
    return {
        "type": "user",
        "session_id": session_id,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
        "parent_tool_use_id": None,
    }


def control_request(subtype: str, request_id: Optional[str] = None, **fields: Any) -> Dict[str, Any]:
    request = {"subtype": subtype}
    request.update(fields)
    return {"type": "control_request", "request_id": request_id or new_request_id(), "request": request}


def _success(request_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "control_response",
        "response": {"subtype": "success", "request_id": request_id, "response": payload},
    }


def allow_response(
    request_id: str,
    updated_input: Dict[str, Any],
    updated_permissions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"behavior": "allow", "updatedInput": updated_input}
    if updated_permissions:
        payload["updatedPermissions"] = updated_permissions
    return _success(request_id, payload)


def deny_response(request_id: str, message: str, interrupt: bool = False) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"behavior": "deny", "message": message}
    if interrupt:
        payload["interrupt"] = True
    return _success(request_id, payload)


def error_response(request_id: str, error: str) -> Dict[str, Any]:
    return {
        "type": "control_response",
        "response": {"subtype": "error", "request_id": request_id, "error": error},
    }


def session_scoped(suggestions: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Permission suggestions from the CLI, forced to live only for this session."""
    out: List[Dict[str, Any]] = []
    for s in suggestions or []:
        if isinstance(s, dict):
            item = dict(s)
            item["destination"] = "session"
            out.append(item)
    return out


def set_mode_update(mode: str) -> Dict[str, Any]:
    return {"type": "setMode", "mode": mode, "destination": "session"}


def question_answers(tool_input: Dict[str, Any], answers: Dict[str, Any]) -> Dict[str, Any]:
    """Build the updatedInput for AskUserQuestion: original questions + answers keyed by question text."""
    flat: Dict[str, str] = {}
    for question, value in (answers or {}).items():
        flat[str(question)] = ", ".join(value) if isinstance(value, list) else str(value)
    updated = dict(tool_input)
    updated["answers"] = flat
    return updated
