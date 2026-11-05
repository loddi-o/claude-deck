"""Claude Deck - Decky Loader backend.

Runs Claude Code (agent mode) as a subprocess, bridges its stream-json protocol to the
Quick Access Menu UI, and provides offline voice dictation and persistent memory.
All state is emitted to the frontend through the single event "cd" (seq, kind, payload).
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List

import decky

# Decky adds <plugin>/py_modules to sys.path; be explicit so the file also works when run by tests.
_PY_MODULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "py_modules")
if _PY_MODULES not in sys.path:
    sys.path.insert(0, _PY_MODULES)

from claude_deck import __version__  # noqa: E402
from claude_deck import sessions_index, setup_check  # noqa: E402
from claude_deck.hub import Hub  # noqa: E402
from claude_deck.memory import Memory  # noqa: E402
from claude_deck.session import ClaudeSession, Paths  # noqa: E402
from claude_deck.settings import Settings  # noqa: E402
from claude_deck.sudo import Sudo  # noqa: E402
from claude_deck.util import agent_env, find_claude  # noqa: E402
from claude_deck.voice import MODELS, VoiceEngine  # noqa: E402


class Plugin:
    def __init__(self) -> None:
        home = decky.DECKY_USER_HOME
        plugin_dir = decky.DECKY_PLUGIN_DIR
        self.paths = Paths(
            home=home,
            claude_home=os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(home, ".claude"),
            plugin_dir=plugin_dir,
            bin_dir=os.path.join(plugin_dir, "bin"),
            settings_dir=decky.DECKY_PLUGIN_SETTINGS_DIR,
            runtime_dir=decky.DECKY_PLUGIN_RUNTIME_DIR,
            decky_home=decky.DECKY_HOME,
        )
        self.settings = Settings(os.path.join(self.paths.settings_dir, "settings.json"))
        self.memory = Memory(
            os.path.join(self.paths.settings_dir, "memory.md"),
            os.path.join(plugin_dir, "defaults", "memory.seed.md"),
        )
        self.sudo = Sudo(self.paths.settings_dir, self.paths.bin_dir)
        # resolve decky.emit at call time: the loader installs it after importing the module
        self.hub = Hub(lambda *a: decky.emit(*a), decky.logger)
        self.session = ClaudeSession(self.hub, self.settings, self.paths, self.sudo, self.memory, decky.logger)
        self.voice = VoiceEngine(
            bin_dir=self.paths.bin_dir,
            models_dir=os.path.join(self.paths.runtime_dir, "models"),
            work_dir=os.path.join(self.paths.runtime_dir, "tmp"),
            publish=self.hub.publish,
            env_fn=self._env,
            log=decky.logger,
        )
        self.installer = setup_check.ClaudeInstaller("install", self.hub.publish, self._env, decky.logger)
        self.login = setup_check.ClaudeLogin("login", self.hub.publish, self._env, decky.logger)

    def _env(self) -> Dict[str, str]:
        return agent_env(self.paths.home, self.paths.bin_dir, self.sudo.env())

    # ------------------------------------------------------------- lifecycle
    async def _main(self) -> None:
        decky.logger.info("Claude Deck %s starting (user=%s)", __version__, decky.USER)
        self._ensure_executables()
        self.memory.ensure()
        last = self.settings["last_session_id"]
        if self.settings["resume_on_open"] and last:
            known = {s["id"] for s in sessions_index.list_sessions(self.paths.claude_home, self.session.cwd(), 50)}
            if last in known:
                await self.session.resume(last)

    async def _unload(self) -> None:
        decky.logger.info("Claude Deck unloading")
        await self.voice.shutdown()
        await self.installer.cancel()
        await self.login.cancel()
        await self.session.stop()

    async def _uninstall(self) -> None:
        # Decky calls this on every reinstall too (updating from a ZIP = uninstall + install), so the
        # saved sudo password is deliberately kept: users remove it from Settings before uninstalling.
        await self._unload()

    def _ensure_executables(self) -> None:
        try:
            for name in os.listdir(self.paths.bin_dir):
                path = os.path.join(self.paths.bin_dir, name)
                if os.path.isfile(path) and not os.access(path, os.X_OK):
                    try:
                        os.chmod(path, 0o755)
                    except OSError as exc:
                        decky.logger.warning("cannot chmod %s: %s", path, exc)
        except OSError:
            pass

    # ------------------------------------------------------------------ state
    async def get_state(self) -> Dict[str, Any]:
        return {
            "version": __version__,
            "status": self.session.status_payload(),
            "events": self.hub.snapshot(),
            "seq": self.hub.seq,
            "settings": self.settings.get(),
            "voice": {"state": self.voice.state, "downloading": self.voice.downloading},
            "sudo": {"has_password": self.sudo.has_password()},
        }

    async def get_settings(self) -> Dict[str, Any]:
        return self.settings.get()

    async def set_settings(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        before = self.settings.get()
        patch = dict(patch or {})
        if "voice_model" in patch and patch["voice_model"] not in MODELS:
            patch.pop("voice_model")
        after = self.settings.update(patch)
        if before["model"] != after["model"]:
            await self.session.set_model(after["model"])
        if before["mode"] != after["mode"]:
            await self.session.set_mode(after["mode"])
        await self.session.publish_status()
        return after

    # --------------------------------------------------------------- chat I/O
    async def send_message(self, text: str) -> bool:
        return await self.session.send(text)

    async def interrupt(self) -> bool:
        await self.session.interrupt()
        return True

    async def set_mode(self, mode: str) -> bool:
        await self.session.set_mode(mode)
        return True

    async def respond_permission(self, request_id: str, decision: Dict[str, Any]) -> bool:
        return await self.session.respond(request_id, decision or {})

    async def new_session(self) -> bool:
        await self.session.new_session()
        return True

    async def restart_session(self) -> bool:
        """Kill the CLI process; the next message respawns it and resumes the conversation."""
        await self.session.stop()
        await self.session.publish_status()
        return True

    async def resume_session(self, session_id: str) -> bool:
        await self.session.resume(session_id)
        return True

    async def list_sessions(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, sessions_index.list_sessions, self.paths.claude_home, self.session.cwd(), 30
        )

    async def delete_session(self, session_id: str) -> bool:
        if session_id == self.session.session_id:
            await self.session.new_session()
        return sessions_index.delete_session(self.paths.claude_home, self.session.cwd(), session_id)

    # ----------------------------------------------------------------- memory
    async def memory_get(self) -> str:
        return self.memory.read()

    async def memory_set(self, text: str) -> bool:
        self.memory.write(text)
        return True

    async def memory_add(self, note: str) -> bool:
        try:
            self.memory.add(note)
            return True
        except ValueError:
            return False

    async def memory_clear(self) -> bool:
        self.memory.clear()
        return True

    # ------------------------------------------------------------------- sudo
    async def sudo_set_password(self, password: str) -> bool:
        if not password:
            return False
        self.sudo.set_password(password)
        return True

    async def sudo_clear(self) -> bool:
        self.sudo.clear()
        return True

    async def sudo_test(self) -> Dict[str, Any]:
        ok, message = await self.sudo.test()
        return {"ok": ok, "message": message}

    # ------------------------------------------------------------------ voice
    async def voice_start(self) -> bool:
        s = self.settings
        self.voice.configure(s["voice_model"], s["voice_language"])
        await self.voice.start(silence_ms=s["voice_silence_ms"])
        return True

    async def voice_stop(self) -> bool:
        await self.voice.stop()
        return True

    async def voice_cancel(self) -> bool:
        await self.voice.cancel()
        return True

    async def voice_download(self, name: str) -> bool:
        return self.voice.start_download(name)

    async def voice_download_cancel(self) -> bool:
        self.voice.cancel_download()
        return True

    # ------------------------------------------------------------------ setup
    async def setup_check(self) -> Dict[str, Any]:
        return await setup_check.check(self._env(), self.paths.home, self.voice, self.sudo, self.settings.get())

    async def install_claude(self) -> bool:
        return await self.installer.start()

    async def login_start(self) -> bool:
        claude = find_claude(self.paths.home, self._env())
        return bool(claude) and await self.login.start(claude)

    async def login_code(self, code: str) -> bool:
        return await self.login.submit_code(code)

    async def login_cancel(self) -> bool:
        await self.login.cancel()
        return True

    async def log_frontend(self, level: str, message: str) -> None:
        getattr(decky.logger, level if level in ("debug", "info", "warning", "error") else "info")(
            "[ui] %s", str(message)[:500]
        )
