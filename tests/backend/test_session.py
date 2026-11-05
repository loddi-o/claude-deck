import asyncio
import json
import os
import unittest
from unittest import mock

from support import Sandbox, install_fake_decky, ring_kinds, wait_for  # noqa: F401  (sets sys.path)

from claude_deck.hub import Hub  # noqa: E402
from claude_deck.memory import Memory  # noqa: E402
from claude_deck.session import ClaudeSession, Paths  # noqa: E402
from claude_deck.settings import Settings  # noqa: E402
from claude_deck.sudo import Sudo  # noqa: E402
import logging  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SessionTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sb = Sandbox()
        self.emitted = []

        async def emit(event, *args):
            self.emitted.append(args)

        log = logging.getLogger("t")
        self.hub = Hub(emit, log)
        self.settings = Settings(os.path.join(self.sb.settings_dir, "settings.json"))
        paths = Paths(home=self.sb.home, claude_home=os.path.join(self.sb.home, ".claude"), plugin_dir=REPO,
                      bin_dir=os.path.join(REPO, "bin"), settings_dir=self.sb.settings_dir,
                      runtime_dir=self.sb.runtime_dir, decky_home=os.path.join(self.sb.tmp, "homebrew"))
        self.memory = Memory(os.path.join(self.sb.settings_dir, "memory.md"))
        self.sudo = Sudo(self.sb.settings_dir, paths.bin_dir)
        self.session = ClaudeSession(self.hub, self.settings, paths, self.sudo, self.memory, log)
        for k in ("FAKE_NO_AUTO", "FAKE_RESUME_FAIL"):
            os.environ.pop(k, None)

    async def asyncTearDown(self):
        await self.session.stop()
        for k in ("FAKE_NO_AUTO", "FAKE_RESUME_FAIL"):
            os.environ.pop(k, None)

    # helpers -------------------------------------------------------------
    def msgs(self, type_):
        return [p for k, p in ring_kinds(self.hub) if k == "msg" and p.get("type") == type_]

    def kinds(self, kind):
        return [p for k, p in ring_kinds(self.hub) if k == kind]

    async def turn_done(self, n_results=1):
        self.assertTrue(await wait_for(lambda: len(self.msgs("result")) >= n_results), "no result event")


class TestBasicTurn(SessionTestCase):
    async def test_simple_turn_streams_and_finishes(self):
        self.assertTrue(await self.session.send("hello"))
        await self.turn_done()
        assistant = self.msgs("assistant")
        self.assertEqual(assistant[-1]["message"]["content"][0]["text"], "Ciao dal finto Claude")
        users = self.msgs("user")
        self.assertTrue(users[0].get("local"))  # local echo of the typed text
        deltas = [a[2] for a in self.emitted if a[1] == "stream" and a[2].get("e") == "d"]
        self.assertEqual("".join(d["s"] for d in deltas), "Ciao dal finto Claude")
        self.assertLess(len(deltas), len("Ciao dal finto Claude") // 4 + 1, "deltas should be coalesced")
        self.assertEqual(self.session.status_name(), "idle")
        self.assertTrue(self.session.session_id)
        self.assertEqual(self.settings["last_session_id"], self.session.session_id)

    async def test_heavy_fields_are_dropped_from_tool_results(self):
        await self.session.send("bash")
        await wait_for(lambda: self.session.pending)
        rid = next(iter(self.session.pending))
        await self.session.respond(rid, {"behavior": "allow"})
        await self.turn_done()
        for u in self.msgs("user"):
            self.assertNotIn("tool_use_result", u)
            self.assertNotIn("tool_result_meta", u)

    async def test_command_line_flags(self):
        await self.session.send("hello")
        await self.turn_done()
        argv = json.loads(self.sb.claude_log_lines()[0][5:])
        for flag in ("--input-format", "--output-format", "--include-partial-messages", "--session-id",
                     "--append-system-prompt", "--mcp-config", "--allowedTools", "--add-dir"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--permission-prompt-tool") + 1], "stdio")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "plan")
        prompt = argv[argv.index("--append-system-prompt") + 1]
        self.assertIn("Claude Deck", prompt)
        self.assertNotIn("{{", prompt)
        self.assertIn("mcp__claude_deck__remember", argv)
        mcp = json.loads(argv[argv.index("--mcp-config") + 1])
        self.assertTrue(mcp["mcpServers"]["claude_deck"]["args"][0].endswith("memory_mcp.py"))

    async def test_memory_is_injected_into_prompt(self):
        self.memory.ensure()
        self.memory.add("Il Deck ha 16GB di RAM")
        await self.session.send("hello")
        await self.turn_done()
        argv = json.loads(self.sb.claude_log_lines()[0][5:])
        self.assertIn("Il Deck ha 16GB di RAM", argv[argv.index("--append-system-prompt") + 1])


class TestPermissions(SessionTestCase):
    async def test_allow_once(self):
        await self.session.send("bash")
        self.assertTrue(await wait_for(lambda: self.session.pending))
        self.assertEqual(self.session.status_name(), "waiting")
        perm = self.kinds("perm")[0]
        self.assertEqual(perm["tool_name"], "Bash")
        self.assertEqual(perm["kind"], "tool")
        self.assertTrue(perm["can_always"])
        await self.session.respond(perm["request_id"], {"behavior": "allow"})
        await self.turn_done()
        resp = [l for l in self.sb.claude_log_lines() if l.startswith("PERM_RESPONSE")][0]
        data = json.loads(resp[len("PERM_RESPONSE "):])
        self.assertEqual(data["behavior"], "allow")
        self.assertEqual(data["updatedInput"]["command"], "echo hi")
        self.assertNotIn("updatedPermissions", data)
        self.assertEqual(self.kinds("perm_done")[0]["outcome"], "allow")

    async def test_allow_always_is_scoped_to_session(self):
        await self.session.send("bash")
        await wait_for(lambda: self.session.pending)
        rid = next(iter(self.session.pending))
        await self.session.respond(rid, {"behavior": "allow", "always": True})
        await self.turn_done()
        resp = [l for l in self.sb.claude_log_lines() if l.startswith("PERM_RESPONSE")][0]
        data = json.loads(resp[len("PERM_RESPONSE "):])
        self.assertEqual(data["updatedPermissions"][0]["destination"], "session")  # never localSettings

    async def test_deny_with_reason(self):
        await self.session.send("bash")
        await wait_for(lambda: self.session.pending)
        rid = next(iter(self.session.pending))
        await self.session.respond(rid, {"behavior": "deny", "message": "no grazie"})
        await self.turn_done()
        self.assertIn("negato: no grazie", self.msgs("assistant")[-1]["message"]["content"][0]["text"])

    async def test_memory_tools_are_auto_approved_without_a_card(self):
        await self.session.send("mem")
        await self.turn_done()
        self.assertEqual(self.kinds("perm"), [])
        self.assertIn("memoria:allow", self.msgs("assistant")[-1]["message"]["content"][0]["text"])

    async def test_unknown_request_is_rejected(self):
        self.assertFalse(await self.session.respond("nope", {"behavior": "allow"}))

    async def test_plan_approval_switches_mode(self):
        await self.session.send("plan")
        await wait_for(lambda: self.session.pending)
        perm = self.kinds("perm")[0]
        self.assertEqual(perm["kind"], "plan")
        self.assertIn("Piano", perm["input"]["plan"])
        await self.session.respond(perm["request_id"], {"behavior": "allow", "mode": "auto"})
        await self.turn_done()
        resp = [l for l in self.sb.claude_log_lines() if l.startswith("PERM_RESPONSE")][0]
        data = json.loads(resp[len("PERM_RESPONSE "):])
        self.assertEqual(data["updatedPermissions"], [{"type": "setMode", "mode": "auto", "destination": "session"}])
        self.assertEqual(self.session.mode, "auto")
        self.assertEqual(self.settings["mode"], "auto")

    async def test_plan_rejection_has_default_message(self):
        await self.session.send("plan")
        await wait_for(lambda: self.session.pending)
        rid = next(iter(self.session.pending))
        await self.session.respond(rid, {"behavior": "deny", "message": ""})
        await self.turn_done()
        resp = [l for l in self.sb.claude_log_lines() if l.startswith("PERM_RESPONSE")][0]
        data = json.loads(resp[len("PERM_RESPONSE "):])
        self.assertEqual(data["behavior"], "deny")
        self.assertIn("piano", data["message"].lower())
        self.assertEqual(self.session.mode, "plan")

    async def test_question_answers(self):
        await self.session.send("ask")
        await wait_for(lambda: self.session.pending)
        perm = self.kinds("perm")[0]
        self.assertEqual(perm["kind"], "question")
        await self.session.respond(perm["request_id"], {"behavior": "allow", "answers": {"A o B?": "B"}})
        await self.turn_done()
        self.assertIn('"A o B?": "B"', self.msgs("assistant")[-1]["message"]["content"][0]["text"])


class TestControl(SessionTestCase):
    async def test_interrupt(self):
        await self.session.send("slow")
        self.assertTrue(await wait_for(lambda: self.session.busy and self.session.alive()))
        await asyncio.sleep(0.2)
        await self.session.interrupt()
        await self.turn_done()
        self.assertTrue(self.msgs("result")[-1]["is_error"])
        self.assertFalse(self.session.busy)

    async def test_set_mode_while_running(self):
        await self.session.send("hello")
        await self.turn_done()
        await self.session.set_mode("auto")
        lines = [l for l in self.sb.claude_log_lines() if l.startswith("CONTROL")]
        self.assertIn('"set_permission_mode"', lines[-1])
        self.assertIn('"auto"', lines[-1])
        self.assertEqual(self.session.mode, "auto")

    async def test_auto_unavailable_falls_back_and_retries(self):
        os.environ["FAKE_NO_AUTO"] = "1"
        self.settings.update({"mode": "auto"})
        self.session.mode = "auto"
        await self.session.send("hello")
        await self.turn_done()
        self.assertTrue(self.session.auto_unavailable)
        self.assertIn("auto_fallback", [n["code"] for n in self.kinds("notice")])
        argv = json.loads([l for l in self.sb.claude_log_lines() if l.startswith("ARGV")][-1][5:])
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "acceptEdits")
        # the typed message was not lost nor duplicated
        self.assertEqual(len(self.msgs("user")), 1)
        self.assertEqual(self.msgs("assistant")[-1]["message"]["content"][0]["text"], "Ciao dal finto Claude")

    async def test_resume_failure_starts_fresh(self):
        os.environ["FAKE_RESUME_FAIL"] = "1"
        self.session.session_id = "11111111-2222-3333-4444-555555555555"
        self.session.has_transcript = True
        await self.session.send("hello")
        await self.turn_done()
        self.assertIn("resume_failed", [n["code"] for n in self.kinds("notice")])
        self.assertNotEqual(self.session.session_id, "11111111-2222-3333-4444-555555555555")

    async def test_crash_then_respawn_resumes(self):
        await self.session.send("hello")
        await self.turn_done()
        first_id = self.session.session_id
        await self.session.send("die")
        self.assertTrue(await wait_for(lambda: "process_exited" in [n["code"] for n in self.kinds("notice")]))
        self.assertFalse(self.session.alive())
        self.assertFalse(self.session.busy)
        await self.session.send("hello again")
        await self.turn_done(2)
        argv = json.loads([l for l in self.sb.claude_log_lines() if l.startswith("ARGV")][-1][5:])
        self.assertEqual(argv[argv.index("--resume") + 1], first_id)

    async def test_stop_kills_process_and_cancels_pending(self):
        await self.session.send("bash")
        await wait_for(lambda: self.session.pending)
        proc = self.session.proc
        await self.session.stop()
        self.assertFalse(self.session.pending)
        self.assertIsNotNone(proc.returncode)
        self.assertEqual(self.kinds("perm_done")[-1]["outcome"], "cancelled")

    async def test_new_session_resets_ring_and_ids(self):
        await self.session.send("hello")
        await self.turn_done()
        await self.session.new_session()
        self.assertEqual(self.session.session_id, "")
        self.assertEqual([k for _, k, _ in self.hub.ring], ["reset"])
        self.assertEqual(self.settings["last_session_id"], "")

    async def test_missing_claude_binary_reports_notice(self):
        os.unlink(os.path.join(self.sb.home, ".local", "bin", "claude"))
        with mock.patch("claude_deck.session.find_claude", return_value=None):
            ok = await self.session.send("hello")
        self.assertFalse(ok)
        self.assertEqual(self.kinds("notice")[-1]["code"], "claude_missing")


if __name__ == "__main__":
    unittest.main()
