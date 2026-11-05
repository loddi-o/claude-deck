#!/usr/bin/env python3
"""End-to-end check of the backend against the REAL `claude` CLI (uses a few cheap haiku turns).

  python3 scripts/e2e_real_claude.py

Needs `claude` installed and logged in. Isolated: temp settings/memory, temp working directory,
transcripts removed at the end. Nothing is changed on the system.
"""
import asyncio
import logging
import os
import shutil
import sys
import tempfile
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "py_modules"))
logging.basicConfig(level=logging.WARNING)

TMP = tempfile.mkdtemp(prefix="cd-e2e-")
WORK = os.path.join(TMP, "work")
os.makedirs(WORK)
HOME = os.path.expanduser("~")

decky = types.ModuleType("decky")
decky.DECKY_USER_HOME = HOME
decky.HOME = HOME
decky.USER = os.environ.get("USER", "deck")
decky.DECKY_HOME = os.path.join(TMP, "homebrew")
decky.DECKY_PLUGIN_DIR = REPO
decky.DECKY_PLUGIN_SETTINGS_DIR = os.path.join(TMP, "settings")
decky.DECKY_PLUGIN_RUNTIME_DIR = os.path.join(TMP, "data")
decky.logger = logging.getLogger("e2e")
decky.events = []


async def _emit(event, *args):
    decky.events.append(args)


decky.emit = _emit
sys.modules["decky"] = decky
sys.path.insert(0, REPO)

import main  # noqa: E402
from claude_deck import sessions_index  # noqa: E402


def results(plugin):
    return [p for _, k, p in plugin.hub.ring if k == "msg" and p.get("type") == "result"]


def last_text(plugin):
    texts = []
    for _, k, p in plugin.hub.ring:
        if k == "msg" and p.get("type") == "assistant":
            for b in p["message"]["content"]:
                if b.get("type") == "text":
                    texts.append(b["text"])
    return texts[-1] if texts else ""


async def wait_results(plugin, n, timeout=150):
    end = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < end:
        if len(results(plugin)) >= n:
            return
        pend = [p for _, k, p in plugin.hub.ring if k == "perm"]
        done = {p["request_id"] for _, k, p in plugin.hub.ring if k == "perm_done"}
        for p in pend:
            if p["request_id"] not in done:
                print("   (auto-approving", p["tool_name"], ")")
                await plugin.respond_permission(p["request_id"], {"behavior": "allow"})
        await asyncio.sleep(0.2)
    raise SystemExit("TIMEOUT waiting for result #%d; ring=%s" % (n, [(k, p.get("type")) for _, k, p in plugin.hub.ring][-8:]))


def check(cond, label):
    print(("  PASS " if cond else "  FAIL ") + label)
    if not cond:
        raise SystemExit(1)


async def main_async():
    plugin = main.Plugin()
    await plugin._main()
    await plugin.set_settings({"model": "haiku", "cwd": WORK, "mode": "plan", "resume_on_open": False, "ui_language_resolved": "it"})
    state = await plugin.get_state()
    check(state["status"]["status"] == "idle", "initial state idle")

    print("1) plain turn")
    await plugin.send_message("Rispondi solo con la parola: ok")
    await wait_results(plugin, 1)
    check("ok" in last_text(plugin).lower(), "assistant answered: %r" % last_text(plugin)[:60])
    st = (await plugin.get_state())["status"]
    check(st["status"] == "idle" and st["session_id"] and st["effective_mode"] == "plan", "status idle, session id set, plan mode")
    check(st["model"], "model reported: %s" % st["model"])

    print("2) memory tool through the MCP server (no approval expected)")
    await plugin.send_message("Usa lo strumento remember per salvare esattamente questa nota: e2e-test-nota-blu. Poi rispondi solo: salvato")
    await wait_results(plugin, 2)
    memory = await plugin.memory_get()
    check("e2e-test-nota-blu" in memory, "note written to memory.md")

    print("3) new conversation sees the memory in its system prompt")
    sid1 = st["session_id"]
    await plugin.new_session()
    await plugin.send_message("Senza usare strumenti: quale nota con 'blu' c'è nella tua memoria persistente? Rispondi con la nota.")
    await wait_results(plugin, 1)
    check("e2e-test-nota-blu" in last_text(plugin), "memory visible in new session: %r" % last_text(plugin)[:80])
    sid2 = (await plugin.get_state())["status"]["session_id"]
    check(sid2 and sid2 != sid1, "new session id")

    print("4) session listing and resume restores the chat")
    sessions = await plugin.list_sessions()
    check({sid1, sid2} <= {s["id"] for s in sessions}, "both sessions listed: %s" % [s["title"][:30] for s in sessions])
    await plugin.resume_session(sid1)
    snap = (await plugin.get_state())["events"]
    hist = [e for e in snap if e[1] == "history"]
    check(hist and any(ev["type"] == "assistant" for ev in hist[0][2]["events"]), "history replayed from transcript")
    await plugin.send_message("Rispondi solo con la parola: ancora")
    await wait_results(plugin, 1)
    check("ancora" in last_text(plugin).lower(), "resumed session answers")

    print("5) mode switch while running")
    await plugin.set_mode("auto")
    st = (await plugin.get_state())["status"]
    print("   effective mode:", st["effective_mode"], "auto_unavailable:", st["auto_unavailable"])
    check(st["mode"] == "auto", "mode switched")

    await plugin._unload()
    print("ALL E2E CHECKS PASSED")


try:
    asyncio.run(main_async())
finally:
    proj = sessions_index.project_dir(os.path.join(HOME, ".claude"), WORK)
    shutil.rmtree(proj, ignore_errors=True)
    shutil.rmtree(TMP, ignore_errors=True)
