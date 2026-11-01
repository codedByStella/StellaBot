"""Import-graph smoke tests for the modular application services."""

import importlib
import importlib.util
import unittest


class ModuleImportTests(unittest.TestCase):
    def test_service_modules_import_without_starting_desktop_workers(self):
        modules = (
            "companion_app.attention",
            "companion_app.context",
            "companion_app.conversation",
            "companion_app.database.common",
            "companion_app.database.core",
            "companion_app.database.history",
            "companion_app.database.preferences",
            "companion_app.database.companion_memory",
            "companion_app.initiative",
            "companion_app.logging",
            "companion_app.model",
            "companion_app.persistence",
            "companion_app.prompts",
            "companion_app.vision",
            "companion_app.visual.capture",
            "companion_app.visual.reel",
            "companion_app.visual.storyboard",
            "companion_app.voice",
            "companion_app.windows",
        )
        for module in modules:
            with self.subTest(module=module):
                importlib.import_module(module)

        # Tkinter is a standard-library dependency but is not installed
        # in every minimal Python distribution used for source validation.
        if importlib.util.find_spec("tkinter") is None:
            self.skipTest("Tkinter is not available in this Python environment")

        importlib.import_module("companion_app.interface.window")
        importlib.import_module("companion_app.app")


if __name__ == "__main__":
    unittest.main()
