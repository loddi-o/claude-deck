"""Persistent plugin settings (JSON in Decky's settings dir)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .util import atomic_write

DEFAULTS: Dict[str, Any] = {
    "mode": "plan",  # plan | auto
    "model": "",  # "" = Claude Code default
    "effort": "",  # "" | low | medium | high | xhigh | max
    "resume_on_open": True,  # reopen the last conversation when the plugin starts
    "cwd": "",  # "" = $HOME
    "extra_dirs": ["/etc", "/var", "/usr", "/opt", "/run", "/boot", "/sys", "/proc"],
    "ui_language": "auto",  # auto | it | en (what the user picked)
    "ui_language_resolved": "en",  # it | en (what the UI actually uses; sent by the frontend)
    "voice_language": "auto",  # whisper language: auto | it | en | ...
    "voice_model": "small-q5_1",
    "voice_silence_ms": 1400,
    "voice_autosend": False,
    "notifications": True,
    "text_scale": 1.0,
    "last_session_id": "",
}

CHOICES = {
    "mode": ("plan", "auto"),
    "effort": ("", "low", "medium", "high", "xhigh", "max"),
    "ui_language": ("auto", "it", "en"),
    "ui_language_resolved": ("it", "en"),
}


class Settings:
    def __init__(self, path: str):
        self.path = path
        self._data: Dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                stored = json.load(f)
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            return
        if isinstance(stored, dict):
            self._data = self._merge(stored)

    def _merge(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(self._data)
        for key, default in DEFAULTS.items():
            if key not in patch:
                continue
            value = patch[key]
            if key in CHOICES and value not in CHOICES[key]:
                continue
            if isinstance(default, bool):
                value = bool(value)
            elif isinstance(default, int) and not isinstance(default, bool):
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    continue
            elif isinstance(default, float):
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
                value = max(0.7, min(1.6, value)) if key == "text_scale" else value
            elif isinstance(default, str):
                value = "" if value is None else str(value)
            elif isinstance(default, list):
                if not isinstance(value, list):
                    continue
                value = [str(v) for v in value if str(v).startswith("/")]
            out[key] = value
        out["voice_silence_ms"] = max(500, min(5000, int(out["voice_silence_ms"])))
        return out

    def get(self) -> Dict[str, Any]:
        return dict(self._data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        self._data = self._merge(patch)
        self.save()
        return self.get()

    def save(self) -> None:
        atomic_write(self.path, json.dumps(self._data, indent=2, ensure_ascii=False), 0o600)

    def effective_cwd(self, home: str) -> str:
        cwd = self._data.get("cwd") or home
        return cwd if os.path.isdir(cwd) else home
