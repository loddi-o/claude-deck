"""Environment checks for the Setup page + helpers to install / log in to Claude Code."""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .prompts import device_name, distro_family, read_os_release
from .util import find_claude

Publish = Callable[[str, Dict[str, Any], bool], Awaitable[None]]
INSTALL_CMD = "curl -fsSL https://claude.ai/install.sh | bash"


async def _run(cmd: List[str], env: Dict[str, str], timeout: float = 15.0) -> tuple:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    except (OSError, asyncio.TimeoutError):
        return -1, "", ""


async def check(env: Dict[str, str], home: str, voice: Any, sudo: Any, settings: Dict[str, Any]) -> Dict[str, Any]:
    claude = find_claude(home, env)
    osr = read_os_release()
    result: Dict[str, Any] = {
        "claude": {"found": bool(claude), "path": claude or "", "version": ""},
        "auth": {"logged_in": None, "email": "", "method": ""},
        "system": {
            "pretty": osr.get("PRETTY_NAME", "Linux"),
            "family": distro_family(osr),
            "device": device_name(),
        },
        "sudo": {"has_password": sudo.has_password()},
    }

    async def claude_info() -> None:
        if not claude:
            return
        rc, out, _ = await _run([claude, "--version"], env)
        if rc == 0:
            result["claude"]["version"] = out.strip().split(" ")[0]
        rc, out, _ = await _run([claude, "auth", "status"], env)
        if out.strip():
            try:
                data = json.loads(out)
                result["auth"] = {
                    "logged_in": bool(data.get("loggedIn")),
                    "email": data.get("email", ""),
                    "method": data.get("authMethod", ""),
                }
            except ValueError:
                result["auth"]["logged_in"] = rc == 0

    async def mic_info() -> None:
        result["mic"] = await voice.list_sources()

    await asyncio.gather(claude_info(), mic_info())
    models = voice.model_status()
    selected = settings.get("voice_model", "")
    result["voice"] = {
        "binary": bool(voice.whisper_binary()),
        "models": models,
        "selected": selected,
        "selected_installed": any(m["name"] == selected and m["installed"] for m in models),
    }
    return result


class _Streamed:
    """Runs a long shell/CLI job and streams its output lines to the UI."""

    def __init__(self, kind: str, publish: Publish, env_fn: Callable[[], Dict[str, str]], log: Any):
        self.kind = kind
        self.publish = publish
        self.env_fn = env_fn
        self.log = log
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.task: Optional[asyncio.Task] = None
        self.lines: List[str] = []

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def cancel(self) -> None:
        if self.proc and self.proc.returncode is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass


class ClaudeInstaller(_Streamed):
    """Official native installer: no root, installs to ~/.local/bin."""

    async def start(self) -> bool:
        if self.running:
            return False
        self.lines = []
        self.proc = await asyncio.create_subprocess_exec(
            "bash", "-c", INSTALL_CMD,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=self.env_fn(),
            start_new_session=True,
        )
        self.task = asyncio.create_task(self._pump(self.proc))
        return True

    async def _pump(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", raw.decode("utf-8", "replace")).rstrip()
            if line:
                self.lines = (self.lines + [line])[-60:]
                await self.publish("setup_log", {"job": "install", "line": line[:300]}, False)
        rc = await proc.wait()
        await self.publish("setup_log", {"job": "install", "done": True, "ok": rc == 0}, False)


class ClaudeLogin(_Streamed):
    """Best-effort `claude auth login`: captures the sign-in URL for Steam's browser and
    forwards the pasted code to the CLI. Not exercised on a logged-out machine in CI."""

    URL_RE = re.compile(r"https?://[^\s\"'<>]+")

    async def start(self, claude: str) -> bool:
        if self.running:
            return False
        env = self.env_fn()
        env["BROWSER"] = "/bin/true"  # do not try to launch a browser from the background service
        self.proc = await asyncio.create_subprocess_exec(
            claude, "auth", "login", "--claudeai",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        self.task = asyncio.create_task(self._pump(self.proc))
        return True

    async def submit_code(self, code: str) -> bool:
        if not self.running or self.proc is None or self.proc.stdin is None:
            return False
        try:
            self.proc.stdin.write((code.strip() + "\n").encode())
            await self.proc.stdin.drain()
            return True
        except (BrokenPipeError, ConnectionResetError):
            return False

    async def _pump(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        sent_url = ""
        async for raw in proc.stdout:
            line = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", raw.decode("utf-8", "replace")).strip()
            match = self.URL_RE.search(line)
            if match and match.group(0) != sent_url:
                sent_url = match.group(0)
                await self.publish("login", {"url": sent_url}, False)
            elif line:
                await self.publish("login", {"line": line[:200]}, False)
        rc = await proc.wait()
        await self.publish("login", {"done": True, "ok": rc == 0}, False)
