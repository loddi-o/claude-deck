"""Offline voice dictation: record from the default microphone, detect the end of speech,
transcribe with whisper.cpp (bin/whisper-cli) and hand the text back to the GUI.

Dictation only: the text is inserted into the message box, nothing is spoken back.
"""

from __future__ import annotations

import array
import asyncio
import math
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .util import clean_env

SAMPLE_RATE = 16000
CHUNK_BYTES = 3200  # 100 ms of s16 mono
MAX_RECORD_S = 90
NO_SPEECH_TIMEOUT_S = 12
NO_AUDIO_TIMEOUT_S = 2.5

MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{file}"
MODELS: Dict[str, Dict[str, Any]] = {
    "base-q5_1": {"file": "ggml-base-q5_1.bin", "size": 59_707_625},
    "small-q5_1": {"file": "ggml-small-q5_1.bin", "size": 190_085_487},
    "small": {"file": "ggml-small.bin", "size": 487_601_967},
}

Publish = Callable[[str, Dict[str, Any], bool], Awaitable[None]]

# Where distros keep the CA bundle. Decky is a PyInstaller binary whose embedded Python often finds
# no default CA store ("CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate"), so we
# point it at the system bundle explicitly.
CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu, Arch / SteamOS
    "/etc/ca-certificates/extracted/tls-ca-bundle.pem",  # Arch
    "/etc/pki/tls/certs/ca-bundle.crt",  # Fedora / Bazzite
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # Fedora
    "/etc/ssl/cert.pem",
)


def ssl_context() -> ssl.SSLContext:
    """TLS context that trusts the system CA bundle even inside Decky's embedded Python."""
    for path in [os.environ.get("SSL_CERT_FILE", ""), *CA_BUNDLES]:
        if path and os.path.isfile(path):
            try:
                return ssl.create_default_context(cafile=path)
            except (ssl.SSLError, OSError):
                continue
    return ssl.create_default_context()


def is_tls_error(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(exc)


def rms_s16(data: bytes) -> float:
    """Root-mean-square of little-endian s16 samples (audioop is gone in Python 3.13)."""
    n = len(data) // 2
    if n == 0:
        return 0.0
    samples = array.array("h")
    samples.frombytes(data[: n * 2])
    if sys.byteorder == "big":  # pragma: no cover
        samples.byteswap()
    return math.sqrt(sum(s * s for s in samples) / n)


class EndpointDetector:
    """Energy based voice activity detection with a small noise-floor calibration."""

    def __init__(self, silence_ms: int):
        self.silence_chunks = max(5, silence_ms // 100)
        self.calib: List[float] = []
        self.threshold = 400.0
        self.speech = False
        self.loud_run = 0
        self.quiet_run = 0
        self.elapsed = 0.0

    def feed(self, level: float) -> bool:
        """Returns True when the utterance is finished."""
        self.elapsed += 0.1
        if len(self.calib) < 3:
            self.calib.append(level)
            if len(self.calib) == 3:
                floor = sum(self.calib) / 3
                self.threshold = max(350.0, floor * 2.5 + 150.0)
            return False
        if level > self.threshold:
            self.loud_run += 1
            self.quiet_run = 0
            if self.loud_run >= 2:
                self.speech = True
        else:
            self.loud_run = 0
            if self.speech:
                self.quiet_run += 1
        return self.speech and self.quiet_run >= self.silence_chunks


def clean_transcript(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # whisper annotations such as [BLANK_AUDIO], (music), *tosse*
        line = re.sub(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*", " ", line)
        line = " ".join(line.split())
        if line:
            lines.append(line)
    return " ".join(lines).strip()


class VoiceEngine:
    def __init__(
        self,
        bin_dir: str,
        models_dir: str,
        work_dir: str,
        publish: Publish,
        env_fn: Callable[[], Dict[str, str]],
        log: Any,
    ):
        self.bin_dir = bin_dir
        self.models_dir = models_dir
        self.work_dir = work_dir
        self.publish = publish
        self.env_fn = env_fn
        self.log = log
        self.state = "idle"  # idle | recording | transcribing
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._task: Optional[asyncio.Task] = None
        self._pcm = bytearray()
        self._cancelled = False
        self._download_task: Optional[asyncio.Task] = None
        self._download_cancel = False
        self.downloading = ""
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.work_dir, exist_ok=True)

    # ---------------------------------------------------------------- discovery
    def whisper_binary(self) -> Optional[str]:
        local = os.path.join(self.bin_dir, "whisper-cli")
        if os.path.isfile(local) and os.access(local, os.X_OK):
            return local
        for name in ("whisper-cli", "whisper-cpp"):
            found = shutil.which(name, path=self.env_fn().get("PATH"))
            if found:
                return found
        return None

    def model_path(self, name: str) -> str:
        return os.path.join(self.models_dir, MODELS[name]["file"])

    def model_status(self) -> List[Dict[str, Any]]:
        out = []
        for name, info in MODELS.items():
            path = self.model_path(name)
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            out.append(
                {
                    "name": name,
                    "file": info["file"],
                    "size": info["size"],
                    "installed": size >= info["size"] * 0.98,
                    "downloading": self.downloading == name,
                }
            )
        return out

    async def list_sources(self) -> Dict[str, Any]:
        env = self.env_fn()
        sources: List[Dict[str, str]] = []
        default = ""
        if shutil.which("pactl", path=env.get("PATH")):
            out = await self._run(["pactl", "list", "short", "sources"], env)
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) >= 2 and not parts[1].endswith(".monitor"):
                    sources.append({"name": parts[1], "state": parts[-1]})
            default = (await self._run(["pactl", "get-default-source"], env)).strip()
        return {"sources": sources, "default": default, "has_mic": bool(sources)}

    async def _run(self, cmd: List[str], env: Dict[str, str], timeout: float = 6.0) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return out.decode("utf-8", "replace")
        except (OSError, asyncio.TimeoutError):
            return ""

    # ---------------------------------------------------------------- recording
    def _record_command(self, device: str, env: Dict[str, str]) -> Optional[List[str]]:
        path = env.get("PATH")
        if shutil.which("parecord", path=path):
            cmd = ["parecord", "--raw", f"--rate={SAMPLE_RATE}", "--channels=1", "--format=s16le", "--latency-msec=40"]
            if device:
                cmd.append(f"--device={device}")
            return cmd
        if shutil.which("pw-record", path=path):
            cmd = ["pw-record", "--raw", "--rate", str(SAMPLE_RATE), "--channels", "1", "--format", "s16"]
            if device:
                cmd += ["--target", device]
            return cmd + ["-"]
        if shutil.which("arecord", path=path):
            cmd = ["arecord", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1"]
            if device:
                cmd += ["-D", device]
            return cmd
        return None

    async def start(self, silence_ms: int = 1400, device: str = "") -> None:
        if self.state != "idle":
            return
        env = self.env_fn()
        cmd = self._record_command(device, env)
        if cmd is None:
            await self._error("no_recorder")
            return
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
                limit=1 << 20,
            )
        except OSError as exc:
            self.log.error("voice: cannot start recorder %s: %s", cmd[0], exc)
            await self._error("no_recorder")
            return
        self._pcm = bytearray()
        self._cancelled = False
        self.state = "recording"
        await self.publish("voice", {"state": "recording", "level": 0.0}, False)
        self._task = asyncio.create_task(self._pump(silence_ms))

    async def _pump(self, silence_ms: int) -> None:
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        detector = EndpointDetector(silence_ms)
        started = time.monotonic()
        last_publish = 0.0
        reason = "stopped"
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(proc.stdout.readexactly(CHUNK_BYTES), timeout=NO_AUDIO_TIMEOUT_S)
                except asyncio.IncompleteReadError as exc:
                    self._pcm.extend(exc.partial)
                    reason = "no_audio" if not self._pcm else "stopped"
                    break
                except asyncio.TimeoutError:
                    reason = "no_audio"
                    break
                self._pcm.extend(chunk)
                level = rms_s16(chunk)
                now = time.monotonic()
                if now - last_publish >= 0.09:
                    last_publish = now
                    await self.publish(
                        "voice",
                        {"state": "recording", "level": min(1.0, level / 6000.0), "speech": detector.speech},
                        False,
                    )
                if detector.feed(level):
                    reason = "endpoint"
                    break
                elapsed = now - started
                if not detector.speech and elapsed > NO_SPEECH_TIMEOUT_S:
                    reason = "no_speech"
                    break
                if elapsed > MAX_RECORD_S:
                    reason = "max_length"
                    break
        except asyncio.CancelledError:
            reason = "cancelled"
            raise
        finally:
            await self._kill_recorder()
        if self._cancelled or reason == "cancelled":
            self.state = "idle"
            await self.publish("voice", {"state": "idle"}, False)
            return
        if reason == "no_audio":
            await self._error("no_audio")
            return
        if reason == "no_speech" and not detector.speech:
            await self._error("no_speech")
            return
        await self._transcribe_pcm(bytes(self._pcm))

    async def stop(self) -> None:
        """Manual stop: finish the recording and transcribe what was captured."""
        if self.state != "recording":
            return
        if self._proc is not None:
            await self._kill_recorder()  # pump sees EOF and moves on to transcription

    async def cancel(self) -> None:
        self._cancelled = True
        if self._task and not self._task.done():
            self._task.cancel()
        await self._kill_recorder()
        if self.state != "idle":
            self.state = "idle"
            await self.publish("voice", {"state": "idle"}, False)

    async def _kill_recorder(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None or proc.returncode is not None:
            return
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=2)
        except (ProcessLookupError, asyncio.TimeoutError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    # ------------------------------------------------------------ transcription
    async def _transcribe_pcm(self, pcm: bytes) -> None:
        model = self._model_choice
        language = self._language
        if len(pcm) < SAMPLE_RATE * 2 * 0.4:  # < 0.4 s
            await self._error("no_speech")
            return
        self.state = "transcribing"
        await self.publish("voice", {"state": "transcribing"}, False)
        wav_path = os.path.join(self.work_dir, "dictation.wav")
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(pcm)
        text, err = await self.transcribe_file(wav_path, model, language)
        try:
            os.unlink(wav_path)
        except OSError:
            pass
        if err:
            await self._error(err)
            return
        self.state = "idle"
        if not text:
            await self.publish("voice", {"state": "idle", "error": "no_speech"}, False)
            return
        await self.publish("voice", {"state": "idle", "text": text}, False)

    # set by the plugin before each recording (from settings)
    _model_choice = "small-q5_1"
    _language = "auto"

    def configure(self, model: str, language: str) -> None:
        if model in MODELS:
            self._model_choice = model
        self._language = language or "auto"

    async def transcribe_file(self, wav_path: str, model: str, language: str):
        """Returns (text, error_code)."""
        binary = self.whisper_binary()
        if binary is None:
            return "", "no_binary"
        if model not in MODELS:
            return "", "no_model"
        mpath = self.model_path(model)
        if not os.path.isfile(mpath) or os.path.getsize(mpath) < MODELS[model]["size"] * 0.98:
            return "", "no_model"
        threads = max(1, min(4, (os.cpu_count() or 4) - 1))
        cmd = [binary, "-m", mpath, "-f", wav_path, "-l", language or "auto", "-nt", "-np", "-t", str(threads), "-bs", "1", "-bo", "1"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env_fn(),
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            return "", "timeout"
        except OSError as exc:
            self.log.error("voice: whisper failed to start: %s", exc)
            return "", "no_binary"
        if proc.returncode != 0:
            self.log.error("voice: whisper exit %s: %s", proc.returncode, err.decode("utf-8", "replace")[-400:])
            return "", "whisper_failed"
        return clean_transcript(out.decode("utf-8", "replace")), ""

    async def _error(self, code: str) -> None:
        self.state = "idle"
        await self.publish("voice", {"state": "idle", "error": code}, False)

    # ---------------------------------------------------------------- downloads
    def start_download(self, name: str) -> bool:
        if name not in MODELS or self.downloading:
            return False
        self.downloading = name
        self._download_cancel = False
        self._download_task = asyncio.create_task(self._download(name))
        return True

    def cancel_download(self) -> None:
        self._download_cancel = True

    async def _download(self, name: str) -> None:
        loop = asyncio.get_running_loop()
        info = MODELS[name]
        url = MODEL_URL.format(file=info["file"])
        dest = self.model_path(name)
        part = dest + ".part"
        state = {"done": 0, "total": info["size"], "error": ""}

        def curl_fallback() -> bool:
            """Download with the system curl (its TLS trust store always works). True on success."""
            curl = shutil.which("curl", path=self.env_fn().get("PATH"))
            if not curl:
                return False
            state["done"] = 0
            with subprocess.Popen(
                [curl, "-fL", "--silent", "--show-error", "--retry", "2", "-o", part, url],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=self.env_fn(),
            ) as proc:  # the context manager closes the pipe and reaps the process
                while proc.poll() is None:
                    if self._download_cancel:
                        proc.terminate()
                        state["error"] = "cancelled"
                        return True
                    try:
                        state["done"] = os.path.getsize(part)
                    except OSError:
                        pass
                    time.sleep(0.3)
                if proc.returncode != 0:
                    err = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", "replace").strip()
                    state["error"] = f"curl: {err}"[:160]
                    return True
            try:
                state["done"] = os.path.getsize(part)
            except OSError:
                pass
            return True

        def finish() -> None:
            if state["error"]:
                return
            if state["done"] < info["size"] * 0.98:
                state["error"] = "incomplete"
                return
            os.replace(part, dest)

        def work() -> None:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "claude-deck"})
                with urllib.request.urlopen(req, timeout=30, context=ssl_context()) as resp, open(part, "wb") as out:
                    total = int(resp.headers.get("Content-Length") or info["size"])
                    state["total"] = total
                    while True:
                        if self._download_cancel:
                            state["error"] = "cancelled"
                            return
                        block = resp.read(256 * 1024)
                        if not block:
                            break
                        out.write(block)
                        state["done"] += len(block)
                finish()
            except Exception as exc:  # noqa: BLE001
                close = getattr(exc, "close", None)
                if callable(close):
                    close()
                if is_tls_error(exc) and curl_fallback():
                    finish()
                    return
                state["error"] = f"{type(exc).__name__}: {exc}"[:160]

        fut = loop.run_in_executor(None, work)
        try:
            while not fut.done():
                await self.publish(
                    "voice_download", {"name": name, "done": state["done"], "total": state["total"]}, False
                )
                await asyncio.sleep(0.4)
            await fut
        finally:
            self.downloading = ""
            if state["error"]:
                try:
                    os.unlink(part)
                except OSError:
                    pass
            await self.publish(
                "voice_download",
                {"name": name, "done": state["done"], "total": state["total"], "finished": True, "error": state["error"]},
                False,
            )

    async def shutdown(self) -> None:
        self._download_cancel = True
        await self.cancel()
