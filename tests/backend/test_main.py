"""Plugin-level behaviour (main.py) with a fake `decky` module."""
import asyncio
import importlib
import os
import sys
import unittest

from support import REPO, Sandbox, install_fake_decky  # noqa: F401  (sets sys.path)


def load_plugin_module(sb):
    install_fake_decky(sb)
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    import main  # noqa: WPS433

    return importlib.reload(main)  # re-bind `decky` to this sandbox


class TestPluginLifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sb = Sandbox(with_fake_claude=False)
        self.main = load_plugin_module(self.sb)
        self.plugin = self.main.Plugin()

    async def test_uninstall_keeps_the_sudo_password_across_updates(self):
        # Decky runs _uninstall on every reinstall (updating from a ZIP), so it must not wipe the password
        await self.plugin.sudo_set_password("s3cret")
        self.assertTrue(self.plugin.sudo.has_password())
        await self.plugin._uninstall()
        self.assertTrue(self.plugin.sudo.has_password())
        self.assertTrue(await self.plugin.sudo_clear())  # the explicit way to remove it still works
        self.assertFalse(self.plugin.sudo.has_password())

    async def test_ui_language_roundtrip_through_set_settings(self):
        state = await self.plugin.get_state()
        self.assertEqual(state["settings"]["ui_language_resolved"], "en")
        saved = await self.plugin.set_settings({"ui_language": "auto", "ui_language_resolved": "it"})
        self.assertEqual(saved["ui_language_resolved"], "it")
        self.assertEqual((await self.plugin.get_settings())["ui_language_resolved"], "it")
        bad = await self.plugin.set_settings({"ui_language_resolved": "klingon"})
        self.assertEqual(bad["ui_language_resolved"], "it")  # invalid value ignored

    async def test_memory_defaults_are_english(self):
        self.plugin.memory.ensure()
        self.assertIn("Claude Deck memory", await self.plugin.memory_get())


if __name__ == "__main__":
    unittest.main()
