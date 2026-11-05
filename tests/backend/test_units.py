import asyncio
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

from support import REPO, Sandbox, wait_for  # noqa: F401  (sets sys.path)

from claude_deck import memory_mcp, protocol as P, sessions_index  # noqa: E402
from claude_deck.memory import Memory  # noqa: E402
from claude_deck.prompts import build_system_prompt, distro_family, language_name  # noqa: E402
from claude_deck.settings import Settings  # noqa: E402
from claude_deck.sudo import Sudo  # noqa: E402
from claude_deck.util import agent_env, clean_env, clip, shrink  # noqa: E402
from claude_deck.voice import EndpointDetector, clean_transcript, rms_s16  # noqa: E402


class TestProtocol(unittest.TestCase):
    def test_user_message_shape(self):
        m = P.user_message("ciao", "sid")
        self.assertEqual(m["type"], "user")
        self.assertEqual(m["message"]["content"][0], {"type": "text", "text": "ciao"})

    def test_allow_and_deny_envelopes(self):
        a = P.allow_response("r1", {"x": 1}, [{"type": "setMode", "mode": "auto", "destination": "session"}])
        self.assertEqual(a["type"], "control_response")
        self.assertEqual(a["response"]["subtype"], "success")
        self.assertEqual(a["response"]["request_id"], "r1")
        self.assertEqual(a["response"]["response"]["behavior"], "allow")
        self.assertEqual(a["response"]["response"]["updatedInput"], {"x": 1})
        d = P.deny_response("r2", "no", interrupt=True)
        self.assertEqual(d["response"]["response"], {"behavior": "deny", "message": "no", "interrupt": True})
        self.assertNotIn("interrupt", P.deny_response("r3", "no")["response"]["response"])

    def test_session_scoped_overrides_destination(self):
        out = P.session_scoped([{"type": "addRules", "destination": "localSettings", "rules": []}])
        self.assertEqual(out[0]["destination"], "session")

    def test_question_answers_join_multi(self):
        out = P.question_answers({"questions": []}, {"q": ["a", "b"], "z": "c"})
        self.assertEqual(out["answers"], {"q": "a, b", "z": "c"})

    def test_dumps_is_one_line(self):
        self.assertEqual(P.dumps({"a": "è"}).count(b"\n"), 1)


class TestUtil(unittest.TestCase):
    def test_clean_env_restores_pyinstaller_ld_path(self):
        env = clean_env({"LD_LIBRARY_PATH": "/tmp/_MEI123", "LD_LIBRARY_PATH_ORIG": "/opt/lib", "PYTHONHOME": "/x", "CLAUDECODE": "1"})
        self.assertEqual(env["LD_LIBRARY_PATH"], "/opt/lib")
        self.assertNotIn("PYTHONHOME", env)
        self.assertNotIn("CLAUDECODE", env)
        env = clean_env({"LD_LIBRARY_PATH": "/tmp/_MEI123"})
        self.assertNotIn("LD_LIBRARY_PATH", env)
        env = clean_env({"LD_LIBRARY_PATH": "/tmp/_MEI123:/usr/lib/foo"})
        self.assertEqual(env["LD_LIBRARY_PATH"], "/usr/lib/foo")

    def test_agent_env_puts_plugin_bin_first(self):
        env = agent_env("/home/deck", "/plugin/bin", {"A": "b"})
        self.assertEqual(env["PATH"].split(":")[0], "/plugin/bin")
        self.assertIn("/home/deck/.local/bin", env["PATH"])
        self.assertEqual(env["A"], "b")
        self.assertEqual(env["HOME"], "/home/deck")

    def test_shrink(self):
        big = "x" * 20000
        out = shrink({"a": big, "img": {"type": "image", "source": {"data": "A" * 100}}, "l": list(range(1000))}, 100, 10)
        self.assertLess(len(out["a"]), 300)
        self.assertEqual(out["img"], {"type": "image", "omitted_bytes": 100})
        self.assertEqual(len(out["l"]), 11)
        self.assertEqual(clip("abc", 10), "abc")


class TestSettings(unittest.TestCase):
    def test_validation_and_persistence(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "s.json")
        s = Settings(path)
        self.assertEqual(s["mode"], "plan")
        s.update({"mode": "bogus", "text_scale": 9, "voice_silence_ms": "10", "unknown": 1, "extra_dirs": ["/etc", "rel"]})
        self.assertEqual(s["mode"], "plan")
        self.assertEqual(s["text_scale"], 1.6)
        self.assertEqual(s["voice_silence_ms"], 500)
        self.assertNotIn("unknown", s.get())
        self.assertEqual(s["extra_dirs"], ["/etc"])
        s.update({"mode": "auto"})
        self.assertEqual(Settings(path)["mode"], "auto")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_resolved_ui_language_is_validated(self):
        s = Settings(os.path.join(tempfile.mkdtemp(), "s.json"))
        self.assertEqual(s["ui_language_resolved"], "en")
        s.update({"ui_language_resolved": "xx"})
        self.assertEqual(s["ui_language_resolved"], "en")
        s.update({"ui_language_resolved": "it", "ui_language": "auto"})
        self.assertEqual((s["ui_language_resolved"], s["ui_language"]), ("it", "auto"))
        s.update({"ui_language": "de"})  # unsupported pick is ignored
        self.assertEqual(s["ui_language"], "auto")

    def test_corrupt_file_falls_back_to_defaults(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "s.json")
        with open(path, "w") as f:
            f.write("{not json")
        self.assertEqual(Settings(path)["mode"], "plan")


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.mem = Memory(os.path.join(self.d, "memory.md"), os.path.join(REPO, "defaults", "memory.seed.md"))
        self.mem.ensure()

    def test_add_forget_clear(self):
        self.mem.add("Il Deck usa   Bazzite")
        self.mem.add("Ho installato   fastfetch")
        text = self.mem.read()
        self.assertIn("Il Deck usa Bazzite", text)
        self.assertEqual(self.mem.forget("fastfetch"), 1)
        self.assertNotIn("fastfetch", self.mem.read())
        self.mem.clear()
        self.assertNotIn("Bazzite", self.mem.read())
        with self.assertRaises(ValueError):
            self.mem.add("   ")

    def test_prompt_block_truncates_oldest(self):
        for i in range(400):
            self.mem.add(f"nota numero {i} " + "x" * 30)
        block = self.mem.prompt_block(limit=2000)
        self.assertLessEqual(len(block), 2200)
        self.assertIn("nota numero 399", block)
        self.assertNotIn("nota numero 0 ", block)
        self.assertIn("recall", block)

    def test_mcp_server_roundtrip(self):
        init = memory_mcp.handle(self.mem, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")
        tools = memory_mcp.handle(self.mem, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual([t["name"] for t in tools["result"]["tools"]], ["remember", "recall", "forget"])
        call = memory_mcp.handle(self.mem, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "remember", "arguments": {"note": "ciao"}}})
        self.assertFalse(call["result"]["isError"])
        self.assertIn("ciao", self.mem.read())
        self.assertIsNone(memory_mcp.handle(self.mem, {"jsonrpc": "2.0", "method": "notifications/initialized"}))
        bad = memory_mcp.handle(self.mem, {"jsonrpc": "2.0", "id": 4, "method": "nope"})
        self.assertEqual(bad["error"]["code"], -32601)

    def test_mcp_server_as_real_subprocess(self):
        script = os.path.join(REPO, "py_modules", "claude_deck", "memory_mcp.py")
        proc = subprocess.Popen([sys.executable, "-I", script, self.mem.path], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True)
        reqs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "remember", "arguments": {"note": "via stdio"}}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "recall", "arguments": {}}}]
        out, _ = proc.communicate("\n".join(json.dumps(r) for r in reqs) + "\n", timeout=15)
        replies = [json.loads(l) for l in out.splitlines()]
        self.assertEqual([r["id"] for r in replies], [1, 2, 3])
        self.assertIn("via stdio", replies[2]["result"]["content"][0]["text"])


class TestPrompts(unittest.TestCase):
    def test_distro_family(self):
        self.assertEqual(distro_family({"ID": "steamos", "ID_LIKE": "arch"}), "steamos")
        self.assertEqual(distro_family({"ID": "bazzite", "ID_LIKE": "fedora"}), "bazzite")
        self.assertEqual(distro_family({"ID": "arch"}), "generic")

    def test_reply_language_is_rendered(self):
        tpl = os.path.join(REPO, "defaults", "system_prompt.md")
        env = agent_env("/home/deck", "/b")
        kw = dict(env=env, cwd="/home/deck", memory_text="", plugin_dirs={"decky_home": "/h", "runtime": "/r"})
        it = build_system_prompt(tpl, reply_language=language_name("it"), **kw)
        self.assertIn("if unsure, use Italian", it)
        self.assertIn("if unsure, use English", build_system_prompt(tpl, **kw))
        self.assertEqual(language_name("de"), "English")  # unsupported -> English
        self.assertNotIn("{{", it)

    def test_prompt_fully_rendered(self):
        text = build_system_prompt(os.path.join(REPO, "defaults", "system_prompt.md"), agent_env("/home/deck", "/b"), "/home/deck",
                                   "- [2026-11-05] nota", {"decky_home": "/home/deck/homebrew", "runtime": "/r"})
        self.assertNotIn("{{", text)
        self.assertIn("- [2026-11-05] nota", text)
        self.assertIn("AskUserQuestion", text)
        self.assertIn("plugin_loader", text)


class TestSessionsIndex(unittest.TestCase):
    def setUp(self):
        self.claude_home = tempfile.mkdtemp()
        self.cwd = "/home/deck"
        self.dir = sessions_index.project_dir(self.claude_home, self.cwd)
        os.makedirs(self.dir)
        self.sid = "2d5c8788-901d-4d76-b2cf-1e9537918011"

    def write(self, name, lines):
        with open(os.path.join(self.dir, name + ".jsonl"), "w") as f:
            for l in lines:
                f.write(json.dumps(l, separators=(",", ":")) + "\n")

    def test_project_dir_encoding(self):
        self.assertTrue(sessions_index.project_dir("/c", "/home/deck/.config").endswith("projects/-home-deck--config"))

    def test_list_and_history(self):
        self.write(self.sid, [
            {"type": "permission-mode", "permissionMode": "auto", "sessionId": self.sid},
            {"type": "user", "message": {"role": "user", "content": "<system-reminder>boh</system-reminder>"}, "isMeta": True},
            {"type": "user", "message": {"role": "user", "content": "perche i miei giochi non partono"}},
            # real transcripts put "message" before "type" on assistant lines
            {"parentUuid": "p", "isSidechain": False, "message": {"id": "m1", "role": "assistant", "model": "x", "content": [{"type": "text", "text": "Controllo i log " + "y" * 900}]}, "type": "assistant", "uuid": "u"},
            {"type": "assistant", "isSidechain": True, "message": {"role": "assistant", "content": [{"type": "text", "text": "sub"}]}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]}},
            {"type": "ai-title", "aiTitle": "Giochi che non partono", "sessionId": self.sid},
        ])
        self.write("empty-one-1234", [{"type": "permission-mode", "permissionMode": "auto"}])
        sessions = sessions_index.list_sessions(self.claude_home, self.cwd)
        self.assertEqual([s["id"] for s in sessions], [self.sid])  # empty session hidden
        self.assertEqual(sessions[0]["title"], "Giochi che non partono")
        hist = sessions_index.load_history(self.claude_home, self.cwd, self.sid)
        kinds = [(e["type"], e["message"]["content"] if isinstance(e["message"]["content"], str) else e["message"]["content"][0]["type"]) for e in hist]
        self.assertEqual(kinds, [("user", "perche i miei giochi non partono"), ("assistant", "text"), ("user", "tool_result")])

    def test_title_falls_back_to_first_prompt_and_rejects_bad_ids(self):
        self.write(self.sid, [{"type": "user", "message": {"role": "user", "content": "primo messaggio"}}])
        self.assertEqual(sessions_index.list_sessions(self.claude_home, self.cwd)[0]["title"], "primo messaggio")
        self.assertEqual(sessions_index.load_history(self.claude_home, self.cwd, "../../etc/passwd"), [])
        self.assertFalse(sessions_index.delete_session(self.claude_home, self.cwd, "../x"))
        self.assertTrue(sessions_index.delete_session(self.claude_home, self.cwd, self.sid))


class TestSudo(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.sudo = Sudo(self.d, os.path.join(REPO, "bin"))

    def test_password_file_is_private(self):
        self.assertFalse(self.sudo.has_password())
        self.sudo.set_password("s3cret")
        self.assertTrue(self.sudo.has_password())
        self.assertEqual(stat.S_IMODE(os.stat(self.sudo.pw_file).st_mode), 0o600)
        self.sudo.clear()
        self.assertFalse(self.sudo.has_password())

    def test_askpass_prints_password_verbatim(self):
        self.sudo.set_password("pa ss")
        out = subprocess.run([self.sudo.askpass], env={**os.environ, **self.sudo.env()}, capture_output=True, text=True)
        self.assertEqual(out.stdout, "pa ss")
        self.assertEqual(subprocess.run([self.sudo.askpass], env={"PATH": "/usr/bin"}).returncode, 1)

    def test_wrapper_uses_askpass_only_with_password(self):
        # a fake "sudo" earlier than /usr/bin/sudo can't be injected (the wrapper hardcodes the path);
        # verify the wrapper's decision logic by reading it
        with open(os.path.join(REPO, "bin", "sudo")) as f:
            text = f.read()
        self.assertIn("/usr/bin/sudo -A", text)
        self.assertIn("/usr/bin/sudo -n", text)

    async def test_test_without_password(self):
        ok, msg = await self.sudo.test()
        self.assertFalse(ok)
        self.assertEqual(msg, "no_password")


class TestVoicePieces(unittest.TestCase):
    @staticmethod
    def chunk(level):
        import array
        import math
        n = 1600
        return array.array("h", [int(level * math.sin(i / 3.0)) for i in range(n)]).tobytes()

    def test_rms(self):
        self.assertEqual(rms_s16(b""), 0.0)
        self.assertAlmostEqual(rms_s16(self.chunk(0)), 0.0, places=3)
        self.assertGreater(rms_s16(self.chunk(5000)), 3000)

    def test_endpoint_detection(self):
        det = EndpointDetector(silence_ms=800)
        levels = [60] * 5 + [4000] * 10 + [50] * 12
        done_at = None
        for i, lv in enumerate(levels):
            if det.feed(rms_s16(self.chunk(lv))):
                done_at = i
                break
        self.assertIsNotNone(done_at)
        self.assertGreaterEqual(done_at, 5 + 10 + 7)  # 8 quiet chunks after speech
        det = EndpointDetector(silence_ms=800)
        self.assertFalse(any(det.feed(60) for _ in range(100)))  # silence alone never "finishes"

    def test_clean_transcript(self):
        self.assertEqual(clean_transcript(" [BLANK_AUDIO]\n Ciao  mondo (musica)\n*tosse*\n come stai "), "Ciao mondo come stai")
        self.assertEqual(clean_transcript("[BLANK_AUDIO]"), "")


if __name__ == "__main__":
    unittest.main()
