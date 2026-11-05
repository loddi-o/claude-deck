"""Shared test scaffolding: fake `decky` module, temp dirs, fake `claude` on PATH."""
import asyncio
import atexit
import logging
import os
import shutil
import stat
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "py_modules"))


class Sandbox:
    """A throw-away HOME + Decky directory layout."""

    def __init__(self, with_fake_claude=True):
        self.tmp = tempfile.mkdtemp(prefix="cd-test-")
        atexit.register(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        self.settings_dir = os.path.join(self.tmp, "homebrew", "settings", "claude-deck")
        self.runtime_dir = os.path.join(self.tmp, "homebrew", "data", "claude-deck")
        self.log_dir = os.path.join(self.tmp, "homebrew", "logs", "claude-deck")
        for d in (self.home, self.settings_dir, self.runtime_dir, self.log_dir,
                  os.path.join(self.home, ".local", "bin")):
            os.makedirs(d, exist_ok=True)
        self.claude_log = os.path.join(self.tmp, "claude.log")
        if with_fake_claude:
            self.install_exe("claude", "#!/usr/bin/env python3\nimport runpy,sys\n"
                             "sys.argv[0]=%r\nrunpy.run_path(%r, run_name='__main__')\n"
                             % (os.path.join(HERE, "fake_claude.py"), os.path.join(HERE, "fake_claude.py")))
        os.environ["FAKE_CLAUDE_LOG"] = self.claude_log

    def install_exe(self, name, content, subdir=os.path.join(".local", "bin")):
        path = os.path.join(self.home, subdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        return path

    def claude_log_lines(self):
        try:
            with open(self.claude_log) as f:
                return f.read().splitlines()
        except FileNotFoundError:
            return []


def install_fake_decky(sb: Sandbox):
    mod = types.ModuleType("decky")
    mod.DECKY_USER_HOME = sb.home
    mod.HOME = sb.home
    mod.USER = "deck"
    mod.DECKY_HOME = os.path.join(sb.tmp, "homebrew")
    mod.DECKY_PLUGIN_DIR = REPO
    mod.DECKY_PLUGIN_SETTINGS_DIR = sb.settings_dir
    mod.DECKY_PLUGIN_RUNTIME_DIR = sb.runtime_dir
    mod.DECKY_PLUGIN_LOG_DIR = sb.log_dir
    mod.logger = logging.getLogger("decky-test")
    mod.events = []

    async def emit(event, *args):
        mod.events.append((event, args))

    mod.emit = emit
    sys.modules["decky"] = mod
    return mod


async def wait_for(pred, timeout=10.0, step=0.02):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if pred():
            return True
        await asyncio.sleep(step)
    return False


def ring_kinds(hub):
    return [(k, p) for _, k, p in hub.ring]
