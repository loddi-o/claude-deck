"""Builds the system prompt: template + machine description + distro-specific rules + memory."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Dict, List

MINIMAL_TEMPLATE = (
    "You are Claude Code running inside Claude Deck on {{DEVICE}}. Be concise, reply in the user's "
    "language ({{LANGUAGE}} if unsure), troubleshoot carefully.\n{{ENV_BLOCK}}\n{{DISTRO_RULES}}\n<memory>\n{{MEMORY}}\n</memory>\n"
)

STEAMOS_RULES = """\
- SteamOS has an immutable, read-only root filesystem. Changes to it (pacman packages, files in /usr, most of /etc) are LOST at every SteamOS update.
- To change the rootfs temporarily: `sudo steamos-readonly disable`; before the first `pacman -S` run `sudo pacman-key --init && sudo pacman-key --populate archlinux holo`; re-enable with `sudo steamos-readonly enable` when done. Tell the user it is not permanent.
- Prefer persistent options: Flatpak (`flatpak install --user`), distrobox/podman containers, binaries in ~/.local/bin, user systemd units (~/.config/systemd/user), Decky plugins, files under /home, and `/etc/atomic-update.conf.d/*.conf` to keep chosen /etc files across updates.
- Current rootfs state: {{RO_STATE}}"""

BAZZITE_RULES = """\
- Bazzite is an immutable Fedora Atomic image. Use `ujust` recipes, Flatpak, distrobox/toolbox and Homebrew (`brew`) for CLI tools. Use `rpm-ostree install` only when really necessary (needs a reboot, layered packages can block upgrades). Never use `dnf` on the host.
- Changes under /usr are not possible; /etc and /var are writable and persistent."""

GENERIC_RULES = """\
- Distribution not recognised as SteamOS or Bazzite: check which package manager and which filesystem layout is in use before installing anything, and prefer user-space installs (Flatpak, distrobox, ~/.local)."""


def read_os_release(path: str = "/etc/os-release") -> Dict[str, str]:
    data: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    data[key] = value.strip().strip('"')
    except OSError:
        pass
    return data


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return ""


def distro_family(osr: Dict[str, str]) -> str:
    ident = (osr.get("ID", "") + " " + osr.get("ID_LIKE", "") + " " + osr.get("VARIANT_ID", "")).lower()
    if "steamos" in ident or "holo" in ident:
        return "steamos"
    if "bazzite" in ident:
        return "bazzite"
    return "generic"


def device_name() -> str:
    vendor = _read("/sys/devices/virtual/dmi/id/sys_vendor")
    product = _read("/sys/devices/virtual/dmi/id/product_name")
    name = " ".join(x for x in (vendor, product) if x)
    return name or platform.node() or "unknown device"


def _running_comms() -> set:
    comms = set()
    try:
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                comm = _read(f"/proc/{entry}/comm")
                if comm:
                    comms.add(comm)
    except OSError:
        pass
    return comms


def _cpu_model() -> str:
    for line in _read("/proc/cpuinfo").splitlines():
        if line.lower().startswith("model name"):
            return line.partition(":")[2].strip()
    return platform.processor() or "unknown"


def _mem_gb() -> str:
    for line in _read("/proc/meminfo").splitlines():
        if line.startswith("MemTotal"):
            try:
                return f"{int(line.split()[1]) / 1024 / 1024:.1f} GB"
            except (ValueError, IndexError):
                break
    return "?"


def _readonly_state(env: Dict[str, str]) -> str:
    exe = shutil.which("steamos-readonly", path=env.get("PATH"))
    if not exe:
        return "unknown (steamos-readonly not found)"
    try:
        out = subprocess.run(
            [exe, "status"], capture_output=True, text=True, timeout=5, env=env, check=False
        )
        return (out.stdout or out.stderr).strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def describe_machine(env: Dict[str, str], cwd: str, plugin_dirs: Dict[str, str]) -> Dict[str, str]:
    osr = read_os_release()
    comms = _running_comms()
    if "plasmashell" in comms:
        ui = "Desktop Mode (KDE Plasma)"
    elif any(c.startswith("gamescope") for c in comms):
        ui = "Game Mode (gamescope)"
    else:
        ui = "unknown"
    disk = shutil.disk_usage(os.path.expanduser("~"))
    root = shutil.disk_usage("/")
    lines: List[str] = [
        f"- Device: {device_name()}",
        f"- OS: {osr.get('PRETTY_NAME', osr.get('NAME', 'Linux'))} (ID={osr.get('ID', '?')}, VARIANT_ID={osr.get('VARIANT_ID', '-')}, BUILD_ID={osr.get('BUILD_ID', '-')})",
        f"- Kernel: {platform.release()} · CPU: {_cpu_model()} · RAM: {_mem_gb()}",
        f"- Session right now: {ui}",
        f"- Disk: / {root.free / 1e9:.1f} GB free of {root.total / 1e9:.1f}; /home {disk.free / 1e9:.1f} GB free of {disk.total / 1e9:.1f}",
        f"- User: {env.get('USER', 'deck')} · HOME={env.get('HOME', '')} · working dir: {cwd}",
        f"- Decky Loader: {plugin_dirs.get('decky_home', '~/homebrew')} (plugins/, logs/, settings/, data/); this plugin's data: {plugin_dirs.get('runtime', '')}",
        "- Steam: ~/.local/share/Steam (logs in ~/.local/share/Steam/logs, Proton prefixes in steamapps/compatdata)",
    ]
    return {
        "family": distro_family(osr),
        "device": device_name(),
        "env_block": "\n".join(lines),
    }


LANGUAGE_NAMES = {"it": "Italian", "en": "English"}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, "English")


def build_system_prompt(
    template_path: str,
    env: Dict[str, str],
    cwd: str,
    memory_text: str,
    plugin_dirs: Dict[str, str],
    reply_language: str = "English",
) -> str:
    template = _read(template_path) or MINIMAL_TEMPLATE
    info = describe_machine(env, cwd, plugin_dirs)
    if info["family"] == "steamos":
        rules = STEAMOS_RULES.replace("{{RO_STATE}}", _readonly_state(env))
    elif info["family"] == "bazzite":
        rules = BAZZITE_RULES
    else:
        rules = GENERIC_RULES
    return (
        template.replace("{{DEVICE}}", info["device"])
        .replace("{{ENV_BLOCK}}", info["env_block"])
        .replace("{{DISTRO_RULES}}", rules)
        .replace("{{MEMORY}}", memory_text)
        .replace("{{LANGUAGE}}", reply_language)
    )
