"""sudo support for the headless agent.

Claude runs without a TTY, so plain `sudo` cannot ask for a password. We put a `sudo` wrapper
(bin/sudo) first in PATH that calls `sudo -A`, and `bin/askpass` prints the stored password.
The password lives in a 0600 file inside the plugin's settings dir (user choice: stored on disk).
"""

from __future__ import annotations

import asyncio
import os
from typing import Dict, Tuple

from .util import atomic_write, clean_env

PW_FILENAME = "sudo.pw"


class Sudo:
    def __init__(self, settings_dir: str, plugin_bin_dir: str):
        self.pw_file = os.path.join(settings_dir, PW_FILENAME)
        self.bin_dir = plugin_bin_dir
        self.askpass = os.path.join(plugin_bin_dir, "askpass")

    def has_password(self) -> bool:
        try:
            return os.path.getsize(self.pw_file) > 0
        except OSError:
            return False

    def set_password(self, password: str) -> None:
        # No trailing newline: askpass prints the file verbatim.
        atomic_write(self.pw_file, password, 0o600)

    def clear(self) -> None:
        try:
            os.unlink(self.pw_file)
        except FileNotFoundError:
            pass

    def env(self) -> Dict[str, str]:
        """Variables that make `sudo` (wrapper) work for child processes.

        Always set: the wrapper checks the password file at call time, so a password saved
        while a conversation is running works immediately."""
        return {"SUDO_ASKPASS": self.askpass, "CLAUDE_DECK_SUDO_PW_FILE": self.pw_file}

    async def test(self) -> Tuple[bool, str]:
        """Validate the stored password. Returns (ok, message)."""
        if not self.has_password():
            return False, "no_password"
        env = clean_env()
        env.update(self.env())
        env["LC_ALL"] = "C"
        # -k forgets cached credentials so we really test the stored password.
        for args in (["/usr/bin/sudo", "-k"], ["/usr/bin/sudo", "-A", "-v"]):
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                _, err = await asyncio.wait_for(proc.communicate(), timeout=20)
            except asyncio.TimeoutError:
                proc.kill()
                return False, "timeout"
            if proc.returncode != 0 and args[1] != "-k":
                text = err.decode("utf-8", "replace").strip()
                if "incorrect" in text or "Sorry" in text or "Authentication" in text:
                    return False, "wrong_password"
                return False, text[:200] or "failed"
        return True, "ok"
