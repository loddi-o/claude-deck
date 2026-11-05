"""Small helpers shared by the backend modules."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional


def clean_env(base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Environment for child processes.

    Decky Loader is a PyInstaller binary: its bootloader prepends its private temp dir to
    LD_LIBRARY_PATH, which makes child processes (claude, whisper-cli, python3...) load the
    wrong shared libraries. Restore the original value (or drop the bundle entries).
    """
    env = dict(os.environ if base is None else base)
    meipass = getattr(sys, "_MEIPASS", None)
    for var in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
        orig = env.pop(var + "_ORIG", None)
        if orig is not None:
            env[var] = orig
            continue
        value = env.get(var)
        if not value:
            continue
        kept = [
            p
            for p in value.split(":")
            if p and "/_MEI" not in p and not (meipass and p.startswith(meipass))
        ]
        if kept:
            env[var] = ":".join(kept)
        else:
            env.pop(var, None)
    for var in ("PYTHONHOME", "PYTHONPATH", "PYTHONSAFEPATH", "_MEIPASS2", "CLAUDECODE"):
        env.pop(var, None)
    return env


def atomic_write(path: str, data: str | bytes, mode: int = 0o644) -> None:
    """Write a file atomically (tmp + rename) with the given permissions."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data.encode("utf-8") if isinstance(data, str) else data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def today() -> str:
    return time.strftime("%Y-%m-%d")


def clip(text: str, limit: int) -> str:
    """Clip a string keeping head and tail."""
    if len(text) <= limit:
        return text
    head = int(limit * 0.7)
    tail = limit - head
    return f"{text[:head]}\n… [{len(text) - limit} caratteri omessi] …\n{text[-tail:]}"


def shrink(obj: Any, max_str: int = 6000, max_items: int = 300, _depth: int = 0) -> Any:
    """Return a JSON-safe copy of `obj` with big strings/lists/images clipped.

    Everything goes over Decky's websocket, so single events must stay small.
    """
    if _depth > 12:
        return "…"
    if isinstance(obj, str):
        return clip(obj, max_str)
    if isinstance(obj, dict):
        if obj.get("type") == "image" and isinstance(obj.get("source"), dict):
            data = obj["source"].get("data", "")
            return {"type": "image", "omitted_bytes": len(data) if isinstance(data, str) else 0}
        return {str(k): shrink(v, max_str, max_items, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        items: List[Any] = [shrink(v, max_str, max_items, _depth + 1) for v in obj[:max_items]]
        if len(obj) > max_items:
            items.append(f"… [{len(obj) - max_items} elementi omessi]")
        return items
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    return str(obj)


def find_executable(name: str, extra_dirs: List[str], path_env: Optional[str] = None) -> Optional[str]:
    """Locate an executable in PATH plus a few well known extra dirs."""
    import shutil

    found = shutil.which(name, path=path_env)
    if found:
        return found
    for d in extra_dirs:
        candidate = os.path.join(d, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def agent_env(home: str, bin_dir: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Environment for everything the plugin spawns (claude, recorder, whisper, installers)."""
    env = clean_env()
    env["HOME"] = home
    uid = os.getuid()
    parts = [
        bin_dir,  # our `sudo` wrapper must win over /usr/bin/sudo
        os.path.join(home, ".local", "bin"),
        os.path.join(home, "bin"),
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/local/sbin",
        "/usr/sbin",
        "/sbin",
    ]
    for p in env.get("PATH", "").split(":"):
        if p and p not in parts:
            parts.append(p)
    env["PATH"] = ":".join(parts)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{uid}/bus")
    if os.path.exists("/tmp/.X11-unix/X0"):
        env.setdefault("DISPLAY", ":0")
    env.setdefault("LANG", "C.UTF-8")
    env["TERM"] = "dumb"
    env["NO_COLOR"] = "1"
    if extra:
        env.update(extra)
    return env


def find_claude(home: str, env: Dict[str, str]) -> Optional[str]:
    return find_executable(
        "claude",
        [
            os.path.join(home, ".local", "bin"),
            "/usr/local/bin",
            os.path.join(home, ".claude", "local"),
            os.path.join(home, ".npm-global", "bin"),
            "/opt/claude/bin",
        ],
        env.get("PATH"),
    )
