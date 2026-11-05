import asyncio
import http.server
import logging
import os
import ssl
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock

from support import Sandbox, wait_for  # noqa: F401  (sets sys.path)

from claude_deck import voice as V  # noqa: E402
from claude_deck.util import agent_env  # noqa: E402

FAKE_PARECORD = r'''#!/usr/bin/env python3
import array, math, sys, time, os
mode = os.environ.get("FAKE_REC_MODE", "speech")
if mode == "dead":
    sys.exit(1)
def chunk(level):
    return array.array("h", [int(level * math.sin(i / 3.0)) for i in range(1600)]).tobytes()
out = sys.stdout.buffer
i = 0
while True:
    if mode == "silence":
        level = 40
    elif mode == "endless":
        level = 4000
    else:  # speech: noise, 1s of speech, then silence forever
        level = 40 if i < 3 else (4000 if i < 14 else 40)
    out.write(chunk(level)); out.flush()
    i += 1
    time.sleep(0.02)
'''

FAKE_WHISPER = '''#!/bin/sh
echo "$@" > "$WHISPER_ARGS_LOG"
echo "[BLANK_AUDIO]"
echo " Ciao Deck, controlla i log"
'''


class VoiceTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sb = Sandbox(with_fake_claude=False)
        self.sb.install_exe("parecord", FAKE_PARECORD)
        self.bin_dir = os.path.join(self.sb.tmp, "plugin-bin")
        os.makedirs(self.bin_dir)
        self.whisper = os.path.join(self.bin_dir, "whisper-cli")
        with open(self.whisper, "w") as f:
            f.write(FAKE_WHISPER)
        os.chmod(self.whisper, 0o755)
        self.args_log = os.path.join(self.sb.tmp, "whisper-args.txt")
        os.environ["WHISPER_ARGS_LOG"] = self.args_log
        os.environ.pop("FAKE_REC_MODE", None)
        self.events = []

        async def publish(kind, payload, persist=False):
            self.events.append((kind, payload))

        self.engine = V.VoiceEngine(
            bin_dir=self.bin_dir,
            models_dir=os.path.join(self.sb.runtime_dir, "models"),
            work_dir=os.path.join(self.sb.runtime_dir, "tmp"),
            publish=publish,
            env_fn=lambda: agent_env(self.sb.home, self.bin_dir),
            log=logging.getLogger("v"),
        )
        self.install_model("base-q5_1")
        self.engine.configure("base-q5_1", "it")

    async def asyncTearDown(self):
        await self.engine.shutdown()
        os.environ.pop("FAKE_REC_MODE", None)

    def install_model(self, name):
        path = self.engine.model_path(name)
        with open(path, "wb") as f:
            f.truncate(V.MODELS[name]["size"])  # sparse file of the right size

    def voice_events(self):
        return [p for k, p in self.events if k == "voice"]


class TestDictation(VoiceTestCase):
    async def test_speech_then_silence_autostops_and_transcribes(self):
        await self.engine.start(silence_ms=500)
        self.assertTrue(await wait_for(lambda: any(p.get("text") for p in self.voice_events()), timeout=15))
        states = [p["state"] for p in self.voice_events()]
        self.assertIn("recording", states)
        self.assertIn("transcribing", states)
        self.assertEqual([p["text"] for p in self.voice_events() if p.get("text")], ["Ciao Deck, controlla i log"])
        levels = [p["level"] for p in self.voice_events() if "level" in p]
        self.assertTrue(levels and max(levels) > 0.3)
        with open(self.args_log) as f:
            args = f.read()
        self.assertIn("-l it", args)
        self.assertIn("-nt", args)
        self.assertEqual(self.engine.state, "idle")

    async def test_manual_stop_transcribes_what_was_captured(self):
        os.environ["FAKE_REC_MODE"] = "endless"
        await self.engine.start(silence_ms=5000)
        await wait_for(lambda: sum(1 for p in self.voice_events() if "level" in p) >= 5)
        self.assertEqual(self.engine.state, "recording")
        await self.engine.stop()
        self.assertTrue(await wait_for(lambda: any(p.get("text") for p in self.voice_events()), timeout=15))

    async def test_cancel_discards(self):
        os.environ["FAKE_REC_MODE"] = "endless"
        await self.engine.start(silence_ms=5000)
        await wait_for(lambda: self.engine.state == "recording")
        await self.engine.cancel()
        self.assertEqual(self.engine.state, "idle")
        await asyncio.sleep(0.3)
        self.assertFalse(any(p.get("text") for p in self.voice_events()))

    async def test_dead_recorder_reports_no_audio(self):
        os.environ["FAKE_REC_MODE"] = "dead"
        await self.engine.start()
        self.assertTrue(await wait_for(lambda: any(p.get("error") for p in self.voice_events())))
        self.assertEqual([p["error"] for p in self.voice_events() if p.get("error")], ["no_audio"])
        self.assertEqual(self.engine.state, "idle")

    async def test_no_recorder_installed(self):
        self.engine.env_fn = lambda: {"PATH": "/nonexistent"}
        await self.engine.start()
        self.assertEqual([p["error"] for p in self.voice_events() if p.get("error")], ["no_recorder"])

    async def test_missing_model_is_reported(self):
        os.unlink(self.engine.model_path("base-q5_1"))
        os.environ["FAKE_REC_MODE"] = "endless"
        await self.engine.start(silence_ms=500)
        await wait_for(lambda: self.engine.state == "recording")
        await asyncio.sleep(0.5)
        await self.engine.stop()
        self.assertTrue(await wait_for(lambda: any(p.get("error") for p in self.voice_events())))
        self.assertEqual([p["error"] for p in self.voice_events() if p.get("error")][-1], "no_model")

    async def test_missing_binary_is_reported(self):
        os.unlink(self.whisper)
        text, err = await self.engine.transcribe_file("/dev/null", "base-q5_1", "it")
        self.assertEqual((text, err), ("", "no_binary"))

    async def test_model_status(self):
        status = {m["name"]: m["installed"] for m in self.engine.model_status()}
        self.assertEqual(status, {"base-q5_1": True, "small-q5_1": False, "small": False})


class TestModelDownload(VoiceTestCase):
    def serve(self, payload: bytes, status=200):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self_inner):  # noqa: N805
                self_inner.send_response(status)
                self_inner.send_header("Content-Length", str(len(payload)))
                self_inner.end_headers()
                self_inner.wfile.write(payload)

            def log_message(self_inner, *a):  # noqa: N805
                pass

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return srv.server_address[1]

    async def test_download_success(self):
        os.unlink(self.engine.model_path("base-q5_1"))
        port = self.serve(b"m" * 4096)
        old_url, old_size = V.MODEL_URL, V.MODELS["base-q5_1"]["size"]
        V.MODEL_URL, V.MODELS["base-q5_1"]["size"] = f"http://127.0.0.1:{port}/{{file}}", 4096
        self.addCleanup(lambda: (setattr(V, "MODEL_URL", old_url), V.MODELS["base-q5_1"].update(size=old_size)))
        self.assertTrue(self.engine.start_download("base-q5_1"))
        self.assertFalse(self.engine.start_download("small"))  # one download at a time
        self.assertTrue(await wait_for(lambda: any(p.get("finished") for k, p in self.events if k == "voice_download")))
        done = [p for k, p in self.events if k == "voice_download" and p.get("finished")][0]
        self.assertEqual(done["error"], "")
        self.assertTrue(self.engine.model_status()[0]["installed"])
        self.assertFalse(os.path.exists(self.engine.model_path("base-q5_1") + ".part"))

    async def test_download_http_error_cleans_up(self):
        os.unlink(self.engine.model_path("base-q5_1"))
        port = self.serve(b"nope", status=404)
        old_url = V.MODEL_URL
        V.MODEL_URL = f"http://127.0.0.1:{port}/{{file}}"
        self.addCleanup(lambda: setattr(V, "MODEL_URL", old_url))
        self.engine.start_download("base-q5_1")
        self.assertTrue(await wait_for(lambda: any(p.get("finished") for k, p in self.events if k == "voice_download")))
        done = [p for k, p in self.events if k == "voice_download" and p.get("finished")][0]
        self.assertIn("HTTP", done["error"])
        self.assertFalse(self.engine.model_status()[0]["installed"])
        self.assertEqual(self.engine.downloading, "")


FAKE_CURL = """#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
if os.environ.get("FAKE_CURL_FAIL"):
    sys.stderr.write("curl: (22) The requested URL returned error: 404\\n")
    sys.exit(22)
out = args[args.index("-o") + 1]
open(out, "wb").write(b"m" * 4096)
"""


class TestTlsTrust(unittest.TestCase):
    """Decky's embedded Python often finds no CA store: we must hand it the system bundle."""

    def test_ssl_context_prefers_env_then_system_bundles(self):
        tmp = tempfile.mkdtemp()
        env_file, sys_file = os.path.join(tmp, "env.pem"), os.path.join(tmp, "sys.pem")
        for f in (env_file, sys_file):
            open(f, "w").close()
        with mock.patch.object(V.ssl, "create_default_context") as m, mock.patch.object(V, "CA_BUNDLES", (sys_file,)):
            with mock.patch.dict(os.environ, {"SSL_CERT_FILE": env_file}):
                V.ssl_context()
            self.assertEqual(m.call_args.kwargs["cafile"], env_file)
            with mock.patch.dict(os.environ, {"SSL_CERT_FILE": os.path.join(tmp, "missing.pem")}):
                V.ssl_context()
            self.assertEqual(m.call_args.kwargs["cafile"], sys_file)
            with mock.patch.object(V, "CA_BUNDLES", (os.path.join(tmp, "nope"),)), mock.patch.dict(os.environ, {"SSL_CERT_FILE": ""}):
                V.ssl_context()
            self.assertEqual(m.call_args.kwargs, {})  # nothing found: library defaults

    def test_real_system_bundle_is_loadable_when_present(self):
        present = [p for p in V.CA_BUNDLES if os.path.isfile(p)]
        if not present:
            self.skipTest("no system CA bundle on this machine")
        with mock.patch.dict(os.environ, {"SSL_CERT_FILE": "", "SSL_CERT_DIR": "/nonexistent"}):
            self.assertIsInstance(V.ssl_context(), ssl.SSLContext)

    def test_tls_error_detection(self):
        self.assertTrue(V.is_tls_error(urllib.error.URLError(ssl.SSLCertVerificationError(1, "CERTIFICATE_VERIFY_FAILED"))))
        self.assertTrue(V.is_tls_error(Exception("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")))
        self.assertFalse(V.is_tls_error(urllib.error.URLError(ConnectionRefusedError())))


class TestDownloadTls(VoiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        os.unlink(self.engine.model_path("base-q5_1"))
        old = V.MODELS["base-q5_1"]["size"]
        V.MODELS["base-q5_1"]["size"] = 4096
        self.addCleanup(lambda: V.MODELS["base-q5_1"].update(size=old))
        self.sb.install_exe("curl", FAKE_CURL)
        os.environ.pop("FAKE_CURL_FAIL", None)

    async def asyncTearDown(self):
        os.environ.pop("FAKE_CURL_FAIL", None)
        await super().asyncTearDown()

    async def finished(self):
        self.assertTrue(await wait_for(lambda: any(p.get("finished") for k, p in self.events if k == "voice_download")))
        return [p for k, p in self.events if k == "voice_download" and p.get("finished")][0]

    def tls_failure(self):
        return mock.patch.object(
            V.urllib.request, "urlopen",
            side_effect=urllib.error.URLError(ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate")),
        )

    async def test_urllib_receives_the_system_trust_context(self):
        seen = {}

        def fake_urlopen(req, timeout=None, context=None):
            seen["context"] = context
            raise urllib.error.URLError(ConnectionRefusedError())  # not TLS: no curl fallback

        with mock.patch.object(V.urllib.request, "urlopen", fake_urlopen):
            self.engine.start_download("base-q5_1")
            done = await self.finished()
        self.assertIsInstance(seen["context"], ssl.SSLContext)
        self.assertIn("URLError", done["error"])
        self.assertFalse(self.engine.model_status()[0]["installed"])

    async def test_tls_error_falls_back_to_curl_and_installs_the_model(self):
        with self.tls_failure():
            self.engine.start_download("base-q5_1")
            done = await self.finished()
        self.assertEqual(done["error"], "")
        self.assertTrue(self.engine.model_status()[0]["installed"])
        self.assertFalse(os.path.exists(self.engine.model_path("base-q5_1") + ".part"))

    async def test_tls_error_without_curl_reports_the_tls_error(self):
        self.engine.env_fn = lambda: {"PATH": "/nonexistent"}
        with self.tls_failure():
            self.engine.start_download("base-q5_1")
            done = await self.finished()
        self.assertIn("CERTIFICATE_VERIFY_FAILED", done["error"])
        self.assertFalse(self.engine.model_status()[0]["installed"])

    async def test_curl_failure_is_reported_and_cleaned_up(self):
        os.environ["FAKE_CURL_FAIL"] = "1"
        with self.tls_failure():
            self.engine.start_download("base-q5_1")
            done = await self.finished()
        self.assertTrue(done["error"].startswith("curl:"), done["error"])
        self.assertFalse(self.engine.model_status()[0]["installed"])
        self.assertEqual(self.engine.downloading, "")


if __name__ == "__main__":
    unittest.main()
