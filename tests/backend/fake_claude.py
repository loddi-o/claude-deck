#!/usr/bin/env python3
"""A stand-in for the `claude` CLI speaking the same stream-json protocol (shapes captured from
claude 2.1.x). Scenario is chosen by the text of the user message."""
import json
import os
import sys
import uuid


def out(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def arg(name, default=""):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


MODE = arg("--permission-mode", "manual")
SESSION = arg("--session-id") or arg("--resume") or str(uuid.uuid4())
RESUMING = "--resume" in sys.argv
LOG = os.environ.get("FAKE_CLAUDE_LOG")


def log(line):
    if LOG:
        with open(LOG, "a") as f:
            f.write(line + "\n")


log("ARGV " + json.dumps(sys.argv[1:]))
if os.environ.get("FAKE_NO_AUTO") and MODE == "auto":
    sys.stderr.write("error: option '--permission-mode <mode>' argument 'auto' is invalid for this account\n")
    sys.exit(1)
if os.environ.get("FAKE_RESUME_FAIL") and RESUMING:
    sys.stderr.write("No conversation found with session ID: %s\n" % SESSION)
    sys.exit(1)

started = False
mid_counter = 0


def init():
    global started
    if started:
        return
    started = True
    out({"type": "system", "subtype": "init", "cwd": os.getcwd(), "session_id": SESSION,
         "tools": ["Bash", "Read"], "mcp_servers": [{"name": "claude_deck", "status": "connected"}],
         "model": "fake-model", "permissionMode": MODE, "slash_commands": []})


def assistant_text(text):
    global mid_counter
    mid_counter += 1
    mid = "msg_%d" % mid_counter
    out({"type": "stream_event", "event": {"type": "message_start", "message": {"id": mid, "role": "assistant"}}})
    out({"type": "stream_event", "event": {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}})
    for i in range(0, len(text), 4):
        out({"type": "stream_event", "event": {"type": "content_block_delta", "index": 0,
                                              "delta": {"type": "text_delta", "text": text[i:i + 4]}}})
    out({"type": "assistant", "message": {"id": mid, "role": "assistant", "model": "fake-model",
                                          "content": [{"type": "text", "text": text}],
                                          "usage": {"input_tokens": 3, "output_tokens": 5}}})
    out({"type": "stream_event", "event": {"type": "content_block_stop", "index": 0}})
    out({"type": "stream_event", "event": {"type": "message_stop"}})


def tool_use(name, tool_input):
    global mid_counter
    mid_counter += 1
    tid = "toolu_%d" % mid_counter
    out({"type": "assistant", "message": {"id": "msg_t%d" % mid_counter, "role": "assistant", "model": "fake-model",
                                          "content": [{"type": "tool_use", "id": tid, "name": name, "input": tool_input}]}})
    return tid


def tool_result(tid, text, is_error=False):
    out({"type": "user", "message": {"role": "user", "content": [
        {"tool_use_id": tid, "type": "tool_result", "content": text, "is_error": is_error}]},
        "tool_use_result": {"stdout": "x" * 50}, "tool_result_meta": [{"id": tid}]})


def result(is_error=False):
    out({"type": "result", "subtype": "error_during_execution" if is_error else "success", "is_error": is_error,
         "result": "done", "session_id": SESSION, "duration_ms": 12, "num_turns": 1, "total_cost_usd": 0.001,
         "usage": {"input_tokens": 3, "output_tokens": 5}})


def wait_response(rid):
    """Block until the host answers the given control_request."""
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if msg.get("type") == "control_response" and msg["response"].get("request_id") == rid:
            return msg["response"]["response"]
        handle_control(msg)
    sys.exit(0)


def ask_permission(tool, tool_input, tid, suggestions=None):
    rid = "req_" + uuid.uuid4().hex[:8]
    req = {"subtype": "can_use_tool", "tool_name": tool, "display_name": tool, "input": tool_input, "tool_use_id": tid}
    if suggestions:
        req["permission_suggestions"] = suggestions
    out({"type": "control_request", "request_id": rid, "request": req})
    return wait_response(rid)


def handle_control(msg):
    if msg.get("type") != "control_request":
        return False
    sub = msg["request"]["subtype"]
    rid = msg["request_id"]
    log("CONTROL " + json.dumps(msg["request"]))
    if sub == "set_permission_mode":
        global MODE
        MODE = msg["request"]["mode"]
    out({"type": "control_response", "response": {"subtype": "success", "request_id": rid, "response": {}}})
    return True


def turn(text):
    init()
    if text == "die":
        sys.exit(3)
    if text.startswith("hello"):
        assistant_text("Ciao dal finto Claude")
        result()
    elif text == "bash":
        tid = tool_use("Bash", {"command": "echo hi", "description": "say hi"})
        sugg = [{"type": "addRules", "rules": [{"toolName": "Bash", "ruleContent": "echo *"}], "behavior": "allow",
                 "destination": "localSettings"}]
        resp = ask_permission("Bash", {"command": "echo hi", "description": "say hi"}, tid, sugg)
        log("PERM_RESPONSE " + json.dumps(resp))
        if resp.get("behavior") == "allow":
            tool_result(tid, "hi")
            assistant_text("eseguito")
        else:
            tool_result(tid, resp.get("message", "denied"), True)
            assistant_text("negato: " + resp.get("message", ""))
        result()
    elif text == "mem":
        tid = tool_use("mcp__claude_deck__remember", {"note": "x"})
        resp = ask_permission("mcp__claude_deck__remember", {"note": "x"}, tid)
        log("PERM_RESPONSE " + json.dumps(resp))
        assistant_text("memoria:" + resp.get("behavior", "?"))
        result()
    elif text == "plan":
        tid = tool_use("ExitPlanMode", {"plan": "# Piano\n1. fai\n2. verifica"})
        resp = ask_permission("ExitPlanMode", {"plan": "# Piano\n1. fai\n2. verifica"}, tid)
        log("PERM_RESPONSE " + json.dumps(resp))
        assistant_text("piano:" + resp.get("behavior", "?"))
        result()
    elif text == "ask":
        q = {"questions": [{"question": "A o B?", "header": "Scelta", "multiSelect": False,
                            "options": [{"label": "A", "description": "a"}, {"label": "B", "description": "b"}]}]}
        tid = tool_use("AskUserQuestion", q)
        resp = ask_permission("AskUserQuestion", q, tid)
        log("PERM_RESPONSE " + json.dumps(resp))
        assistant_text("risposta:" + json.dumps(resp.get("updatedInput", {}).get("answers")))
        result()
    elif text == "slow":
        out({"type": "stream_event", "event": {"type": "message_start", "message": {"id": "m_slow"}}})
        for line in sys.stdin:
            msg = json.loads(line)
            if handle_control(msg) and msg["request"]["subtype"] == "interrupt":
                result(True)
                return
    else:
        assistant_text("echo:" + text)
        result()


def main():
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if handle_control(msg):
            continue
        if msg.get("type") == "user":
            content = msg["message"]["content"]
            text = content if isinstance(content, str) else "".join(b.get("text", "") for b in content)
            turn(text)


main()
