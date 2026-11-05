"""Runs Claude Code as a persistent subprocess speaking stream-json and bridges it to the UI.

One ClaudeSession == one live conversation. The CLI process is started lazily on the first
message (resuming the stored session when there is one) and killed on unload / new session.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

from . import protocol as P
from .hub import Hub
from .memory import Memory
from .prompts import build_system_prompt
from .sessions_index import load_history
from .settings import Settings
from .sudo import Sudo
from .util import agent_env, find_claude, shrink

# Read-only diagnostics that never need an approval card.
READONLY_ALLOW = [
    "Bash(journalctl *)", "Bash(dmesg *)", "Bash(systemctl status *)", "Bash(systemctl list-*)",
    "Bash(systemctl --user status *)", "Bash(systemctl is-active *)", "Bash(systemctl is-enabled *)",
    "Bash(lsusb *)", "Bash(lspci *)", "Bash(lsblk *)", "Bash(df *)", "Bash(free *)", "Bash(uname *)",
    "Bash(uptime)", "Bash(ps *)", "Bash(pactl list *)", "Bash(pactl info)", "Bash(wpctl status *)",
    "Bash(flatpak list *)", "Bash(pacman -Q*)", "Bash(steamos-readonly status)", "Bash(ip addr *)",
    "Bash(ip link *)", "Bash(nmcli *)", "Bash(rpm-ostree status *)", "Bash(fastfetch *)",
    "Bash(lscpu *)", "Bash(cat /etc/*)", "Bash(cat /proc/*)", "Bash(cat /sys/*)", "Bash(ls *)",
]
MEMORY_TOOLS = ["mcp__claude_deck__remember", "mcp__claude_deck__recall", "mcp__claude_deck__forget"]


@dataclass
class Paths:
    home: str
    claude_home: str
    plugin_dir: str
    bin_dir: str
    settings_dir: str
    runtime_dir: str
    decky_home: str

    @property
    def template(self) -> str:
        return os.path.join(self.plugin_dir, "defaults", "system_prompt.md")

    @property
    def mcp_script(self) -> str:
        return os.path.join(self.plugin_dir, "py_modules", "claude_deck", "memory_mcp.py")


class ClaudeSession:
    def __init__(self, hub: Hub, settings: Settings, paths: Paths, sudo: Sudo, memory: Memory, log: Any):
        self.hub = hub
        self.settings = settings
        self.paths = paths
        self.sudo = sudo
        self.memory = memory
        self.log = log

        self.proc: Optional[asyncio.subprocess.Process] = None
        self.session_id = ""
        self.has_transcript = False  # a transcript exists on disk -> next spawn must --resume
        self.mode = settings["mode"]
        self.effective_mode = ""
        self.model = ""
        self.busy = False
        self.auto_unavailable = False
        self.rate: Dict[str, Any] = {}
        self.last_result: Dict[str, Any] = {}
        self.pending: Dict[str, Dict[str, Any]] = {}

        self._waiters: Dict[str, asyncio.Future] = {}
        self._stderr_tail: Deque[str] = deque(maxlen=40)
        self._got_init = False
        self._first_text: Optional[str] = None
        self._used_resume = False
        self._used_mode_flag = ""
        self._stopping = False
        self._tasks: List[asyncio.Task] = []
        self._dbuf: Dict[Any, List[str]] = {}
        self._flush_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ helpers
    def env(self) -> Dict[str, str]:
        return agent_env(self.paths.home, self.paths.bin_dir, self.sudo.env())

    def alive(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    def cwd(self) -> str:
        return self.settings.effective_cwd(self.paths.home)

    def status_name(self) -> str:
        if self.pending:
            return "waiting"
        if self.busy:
            return "working"
        return "idle"

    def status_payload(self) -> Dict[str, Any]:
        return {
            "status": self.status_name(),
            "running": self.alive(),
            "mode": self.mode,
            "effective_mode": self.effective_mode,
            "auto_unavailable": self.auto_unavailable,
            "session_id": self.session_id,
            "model": self.model,
            "cwd": self.cwd(),
            "pending": len(self.pending),
            "rate": self.rate,
            "last_result": self.last_result,
        }

    async def publish_status(self) -> None:
        await self.hub.publish("status", self.status_payload(), False)

    async def notice(self, code: str, level: str = "info", **extra: Any) -> None:
        await self.hub.publish("notice", {"code": code, "level": level, **extra})

    def mode_flag(self, mode: str) -> str:
        return P.ACCEPT_EDITS if (mode == P.AUTO and self.auto_unavailable) else mode

    # -------------------------------------------------------------------- spawn
    async def _spawn(self) -> None:
        env = self.env()
        claude = find_claude(self.paths.home, env)
        if not claude:
            raise FileNotFoundError("claude")
        self.memory.ensure()
        loop = asyncio.get_running_loop()
        cwd = self.cwd()
        prompt = await loop.run_in_executor(
            None,
            build_system_prompt,
            self.paths.template,
            env,
            cwd,
            self.memory.prompt_block(),
            {"decky_home": self.paths.decky_home, "runtime": self.paths.runtime_dir},
        )
        flag = self.mode_flag(self.mode)
        cmd: List[str] = [
            claude, "--output-format", "stream-json", "--input-format", "stream-json", "--verbose",
            "--include-partial-messages", "--permission-prompt-tool", "stdio", "--permission-mode", flag,
        ]
        self._used_resume = bool(self.session_id and self.has_transcript)
        if self._used_resume:
            cmd += ["--resume", self.session_id]
        else:
            self.session_id = self.session_id or str(uuid.uuid4())
            cmd += ["--session-id", self.session_id]
        if self.settings["model"]:
            cmd += ["--model", self.settings["model"]]
        if self.settings["effort"]:
            cmd += ["--effort", self.settings["effort"]]
        python = shutil.which("python3", path=env.get("PATH")) or "/usr/bin/python3"
        mcp = {"mcpServers": {"claude_deck": {"command": python, "args": [self.paths.mcp_script, self.memory.path]}}}
        cmd += ["--append-system-prompt", prompt, "--mcp-config", json.dumps(mcp)]
        cmd += ["--allowedTools", *MEMORY_TOOLS, *READONLY_ALLOW]
        dirs = [d for d in self.settings["extra_dirs"] if os.path.isdir(d)]
        if dirs:
            cmd += ["--add-dir", *dirs]

        self._stopping = False
        self._got_init = False
        self._used_mode_flag = flag
        self._stderr_tail.clear()
        self.log.info("spawning claude (mode=%s resume=%s session=%s)", flag, self._used_resume, self.session_id)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=1 << 26,
            start_new_session=True,
        )
        self.proc = proc
        self._tasks = [
            asyncio.create_task(self._read_stdout(proc)),
            asyncio.create_task(self._read_stderr(proc)),
        ]

    async def _write(self, obj: Dict[str, Any]) -> bool:
        proc = self.proc
        if proc is None or proc.stdin is None or proc.returncode is not None:
            return False
        try:
            proc.stdin.write(P.dumps(obj))
            await proc.stdin.drain()
            return True
        except (BrokenPipeError, ConnectionResetError):
            return False

    # ---------------------------------------------------------------- public API
    async def send(self, text: str, echo: bool = True) -> bool:
        text = (text or "").strip()
        if not text:
            return False
        async with self._lock:
            if not self.alive():
                try:
                    await self._spawn()
                except FileNotFoundError:
                    await self.notice("claude_missing", "error")
                    return False
                except OSError as exc:
                    await self.notice("spawn_failed", "error", detail=str(exc)[:200])
                    return False
        self._first_text = None if self._got_init else text
        self.busy = True
        if echo:
            await self.hub.publish(
                "msg", {"type": "user", "local": True, "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
            )
        if not await self._write(P.user_message(text, self.session_id)):
            self.busy = False
            await self.notice("write_failed", "error")
        await self.publish_status()
        return True

    async def interrupt(self) -> None:
        if self.alive():
            await self._control("interrupt")

    async def set_mode(self, mode: str) -> None:
        if mode not in P.UI_MODES:
            return
        self.mode = mode
        self.settings.update({"mode": mode})
        if self.alive():
            resp = await self._control("set_permission_mode", mode=self.mode_flag(mode))
            if resp is None or resp.get("subtype") == "error":
                if mode == P.AUTO and not self.auto_unavailable:
                    self.auto_unavailable = True
                    await self._control("set_permission_mode", mode=P.ACCEPT_EDITS)
                    await self.notice("auto_fallback", "warn")
                else:
                    await self.notice("mode_failed", "warn")
            else:
                self.effective_mode = self.mode_flag(mode)
        await self.publish_status()

    async def set_model(self, model: str) -> None:
        if self.alive():
            await self._control("set_model", model=model or None)

    async def respond(self, request_id: str, decision: Dict[str, Any]) -> bool:
        pending = self.pending.pop(request_id, None)
        if pending is None:
            return False
        kind = pending["kind"]
        if decision.get("behavior") == "allow":
            updated_input = pending["input"]
            permissions: Optional[List[Dict[str, Any]]] = None
            if kind == "question":
                updated_input = P.question_answers(pending["input"], decision.get("answers") or {})
            elif kind == "plan":
                target = decision.get("mode") if decision.get("mode") in P.UI_MODES else P.AUTO
                self.mode = target
                self.settings.update({"mode": target})
                permissions = [P.set_mode_update(self.mode_flag(target))]
                self.effective_mode = self.mode_flag(target)
            elif decision.get("always"):
                permissions = P.session_scoped(pending.get("suggestions"))
            reply = P.allow_response(request_id, updated_input, permissions)
            outcome = "allow"
        else:
            default = (
                "L'utente non ha approvato il piano. Rivedilo in base alle sue note e riproponilo."
                if kind == "plan"
                else "L'utente ha negato questa azione."
            )
            message = (decision.get("message") or "").strip() or default
            reply = P.deny_response(request_id, message, bool(decision.get("interrupt")))
            outcome = "deny"
        await self._write(reply)
        await self.hub.publish("perm_done", {"request_id": request_id, "outcome": outcome})
        await self.publish_status()
        return True

    async def new_session(self) -> None:
        await self.stop()
        self.session_id = ""
        self.has_transcript = False
        self.last_result = {}
        self.hub.clear()
        await self.hub.publish("reset", {"session_id": ""})
        self.settings.update({"last_session_id": ""})
        await self.publish_status()

    async def resume(self, session_id: str) -> None:
        await self.stop()
        self.session_id = session_id
        self.has_transcript = True
        self.last_result = {}
        loop = asyncio.get_running_loop()
        events = await loop.run_in_executor(None, load_history, self.paths.claude_home, self.cwd(), session_id)
        self.hub.clear()
        await self.hub.publish("reset", {"session_id": session_id})
        if events:
            await self.hub.publish("history", {"events": events})
        self.settings.update({"last_session_id": session_id})
        await self.publish_status()

    async def stop(self) -> None:
        self._stopping = True
        proc, self.proc = self.proc, None
        if proc is not None and proc.returncode is None:
            for sig, wait in ((signal.SIGTERM, 3.0), (signal.SIGKILL, 2.0)):
                try:
                    os.killpg(proc.pid, sig)
                except (ProcessLookupError, PermissionError):
                    break
                try:
                    await asyncio.wait_for(proc.wait(), timeout=wait)
                    break
                except asyncio.TimeoutError:
                    continue
        for t in self._tasks:
            if not t.done() and t is not asyncio.current_task():
                t.cancel()
        self._tasks = []
        await self._drop_pending("cancelled")
        for fut in self._waiters.values():
            if not fut.done():
                fut.cancel()
        self._waiters.clear()
        self.busy = False
        self._dbuf.clear()

    async def _drop_pending(self, outcome: str) -> None:
        for rid in list(self.pending):
            self.pending.pop(rid, None)
            await self.hub.publish("perm_done", {"request_id": rid, "outcome": outcome})

    # ---------------------------------------------------------------- control I/O
    async def _control(self, subtype: str, timeout: float = 6.0, **fields: Any) -> Optional[Dict[str, Any]]:
        req = P.control_request(subtype, **fields)
        rid = req["request_id"]
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._waiters[rid] = fut
        if not await self._write(req):
            self._waiters.pop(rid, None)
            return None
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            return None
        finally:
            self._waiters.pop(rid, None)

    # ------------------------------------------------------------------- readers
    async def _read_stderr(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stderr is not None
        try:
            async for raw in proc.stderr:
                line = raw.decode("utf-8", "replace").rstrip()
                if line:
                    self._stderr_tail.append(line)
                    self.log.debug("claude stderr: %s", line)
        except (asyncio.CancelledError, ValueError):
            pass

    async def _read_stdout(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        try:
            while True:
                try:
                    line = await proc.stdout.readline()
                except ValueError:  # a single line above the 64 MB limit
                    self.log.error("claude emitted an oversized line, dropping it")
                    continue
                if not line:
                    break
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                try:
                    await self._handle(msg)
                except Exception:  # noqa: BLE001
                    self.log.exception("error handling claude message")
        except asyncio.CancelledError:
            raise
        rc = await proc.wait()
        await self._on_exit(proc, rc)

    async def _on_exit(self, proc: asyncio.subprocess.Process, rc: int) -> None:
        if proc is not self.proc:
            return  # stopped on purpose or already replaced
        self.proc = None
        was_busy = self.busy
        self.busy = False
        await self._flush_deltas()
        await self._drop_pending("cancelled")
        tail = "\n".join(self._stderr_tail)
        retry = self._first_text if not self._got_init else None
        self.log.warning("claude exited rc=%s got_init=%s tail=%s", rc, self._got_init, tail[-300:])
        if retry and rc != 0:
            if self._used_mode_flag == P.AUTO and not self.auto_unavailable and "auto" in tail.lower():
                self.auto_unavailable = True
                await self.notice("auto_fallback", "warn")
                asyncio.create_task(self.send(retry, echo=False))
                return
            if self._used_resume:
                self.session_id = ""
                self.has_transcript = False
                await self.notice("resume_failed", "warn")
                asyncio.create_task(self.send(retry, echo=False))
                return
        await self.notice("process_exited", "error" if (rc != 0 or was_busy) else "info", rc=rc, detail=tail[-500:])
        await self.publish_status()

    # ------------------------------------------------------------------ dispatch
    async def _handle(self, msg: Dict[str, Any]) -> None:
        t = msg.get("type")
        if t == "stream_event":
            if msg.get("parent_tool_use_id"):
                return
            await self._on_stream(msg.get("event") or {})
        elif t == "assistant":
            if msg.get("parent_tool_use_id"):
                return
            await self._flush_deltas()
            await self.hub.publish("msg", self._trim_assistant(msg))
        elif t == "user":
            if msg.get("parent_tool_use_id"):
                return
            await self._flush_deltas()
            await self.hub.publish("msg", self._trim_user(msg))
        elif t == "result":
            await self._on_result(msg)
        elif t == "system":
            await self._on_system(msg)
        elif t == "control_request":
            await self._on_control_request(msg)
        elif t == "control_response":
            resp = msg.get("response") or {}
            fut = self._waiters.get(resp.get("request_id", ""))
            if fut and not fut.done():
                fut.set_result(resp)
        elif t == "control_cancel_request":
            rid = msg.get("request_id", "")
            if self.pending.pop(rid, None) is not None:
                await self.hub.publish("perm_done", {"request_id": rid, "outcome": "cancelled"})
                await self.publish_status()
        elif t == "rate_limit_event":
            info = msg.get("rate_limit_info") or {}
            windows = info.get("unifiedWindows") or {}
            self.rate = {
                "status": info.get("status", ""),
                "five_hour": (windows.get("five_hour") or {}).get("utilization"),
                "seven_day": (windows.get("seven_day") or {}).get("utilization"),
            }
            await self.publish_status()

    @staticmethod
    def _clean_blocks(content: Any, max_str: int = 8000) -> Any:
        if isinstance(content, list):
            blocks = []
            for b in content:
                if isinstance(b, dict) and b.get("type") in ("thinking", "redacted_thinking"):
                    blocks.append({"type": "thinking", "thinking": shrink(b.get("thinking", ""), 1500)})
                else:
                    blocks.append(b)
            content = blocks
        return shrink(content, max_str=max_str, max_items=80)

    def _trim_assistant(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        m = msg.get("message") or {}
        usage = m.get("usage") or {}
        return {
            "type": "assistant",
            "uuid": msg.get("uuid"),
            "message": {
                "id": m.get("id"),
                "model": m.get("model"),
                "role": "assistant",
                "content": self._clean_blocks(m.get("content")),
                "usage": {"in": usage.get("input_tokens"), "out": usage.get("output_tokens")},
            },
        }

    def _trim_user(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        m = msg.get("message") or {}
        return {
            "type": "user",
            "uuid": msg.get("uuid"),
            "message": {"role": "user", "content": self._clean_blocks(m.get("content"))},
        }

    async def _on_system(self, msg: Dict[str, Any]) -> None:
        sub = msg.get("subtype")
        if sub == "init":
            self._got_init = True
            self._first_text = None
            self.has_transcript = True
            self.session_id = msg.get("session_id") or self.session_id
            self.model = msg.get("model") or self.model
            self.effective_mode = msg.get("permissionMode") or self.effective_mode
            self.settings.update({"last_session_id": self.session_id})
            for server in msg.get("mcp_servers") or []:
                if server.get("name") == "claude_deck" and server.get("status") not in ("connected", "pending"):
                    await self.notice("memory_unavailable", "warn")
            await self.publish_status()
        elif sub == "status":
            await self.hub.publish("sys", {"status": msg.get("status")}, False)
        elif sub in ("api_retry", "compact_boundary"):
            await self.hub.publish("sys", {"status": sub}, False)

    async def _on_result(self, msg: Dict[str, Any]) -> None:
        await self._flush_deltas()
        usage = msg.get("usage") or {}
        self.last_result = {
            "subtype": msg.get("subtype"),
            "is_error": bool(msg.get("is_error")),
            "duration_ms": msg.get("duration_ms"),
            "num_turns": msg.get("num_turns"),
            "cost_usd": msg.get("total_cost_usd"),
            "tokens_in": usage.get("input_tokens"),
            "tokens_out": usage.get("output_tokens"),
        }
        self.busy = False
        self._first_text = None
        await self.hub.publish(
            "msg",
            {
                "type": "result",
                "subtype": msg.get("subtype"),
                "is_error": bool(msg.get("is_error")),
                "result": shrink(msg.get("result") or "", 2000),
                "stats": self.last_result,
            },
        )
        await self.publish_status()

    # ---------------------------------------------------------- permission prompts
    async def _on_control_request(self, msg: Dict[str, Any]) -> None:
        req = msg.get("request") or {}
        rid = msg.get("request_id", "")
        if req.get("subtype") != "can_use_tool":
            await self._write(P.error_response(rid, "unsupported control request"))
            return
        tool = req.get("tool_name", "")
        tool_input = req.get("input") or {}
        if tool in MEMORY_TOOLS:
            # Our own, harmless memory tools: the CLI sometimes still asks (race on first use of a
            # freshly connected MCP server) - never bother the user with it.
            await self._write(P.allow_response(rid, tool_input))
            return
        kind = "plan" if tool == P.TOOL_EXIT_PLAN else "question" if tool == P.TOOL_ASK else "tool"
        suggestions = req.get("permission_suggestions") or []
        self.pending[rid] = {"kind": kind, "input": tool_input, "suggestions": suggestions, "tool": tool}
        await self.hub.publish(
            "perm",
            {
                "request_id": rid,
                "kind": kind,
                "tool_name": tool,
                "tool_use_id": req.get("tool_use_id"),
                "input": shrink(tool_input, max_str=5000, max_items=60),
                "title": req.get("title"),
                "description": req.get("description"),
                "decision_reason": req.get("decision_reason"),
                "blocked_path": req.get("blocked_path"),
                "can_always": bool(P.session_scoped(suggestions)),
            },
        )
        await self.publish_status()

    # ------------------------------------------------------------ streaming deltas
    async def _on_stream(self, ev: Dict[str, Any]) -> None:
        et = ev.get("type")
        if et == "content_block_delta":
            delta = ev.get("delta") or {}
            kind = {"text_delta": "text", "thinking_delta": "thinking"}.get(delta.get("type", ""))
            if kind is None:
                return
            text = delta.get("text") if kind == "text" else delta.get("thinking")
            if not text:
                return
            self._dbuf.setdefault((ev.get("index", 0), kind), []).append(text)
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._flush_later())
            return
        await self._flush_deltas()
        if et == "message_start":
            await self.hub.publish("stream", {"e": "ms", "mid": (ev.get("message") or {}).get("id")}, False)
        elif et == "content_block_start":
            block = ev.get("content_block") or {}
            await self.hub.publish(
                "stream", {"e": "bs", "i": ev.get("index", 0), "k": block.get("type"), "name": block.get("name")}, False
            )
        elif et == "content_block_stop":
            await self.hub.publish("stream", {"e": "be", "i": ev.get("index", 0)}, False)
        elif et == "message_stop":
            await self.hub.publish("stream", {"e": "me"}, False)

    async def _flush_later(self) -> None:
        await asyncio.sleep(0.06)
        await self._flush_deltas()

    async def _flush_deltas(self) -> None:
        if not self._dbuf:
            return
        buf, self._dbuf = self._dbuf, {}
        for (index, kind), parts in buf.items():
            await self.hub.publish("stream", {"e": "d", "i": index, "k": kind, "s": "".join(parts)}, False)
