"""Regression tests for isolating mutable runtime data from checked-in artifacts."""

import unittest

from companion_app.database.common import (
    BASE_DIR,
    RUNTIME_DIR,
    DB_FILE,
    COMPANION_PROFILE_FILE,
    COMPANION_STATE_FILE,
)
from companion_app.model import CHAT_HISTORY_FILE
from companion_app.logging import _WLOG_FILE
from companion_app.attention import (
    COMPANION_ATTENTION_FILE,
    COMPANION_RITUAL_FILE,
)
from companion_app.visual.storyboard import VISUAL_STORYBOARD_PATH


class RuntimePathTests(unittest.TestCase):
    def test_mutable_application_files_live_under_runtime_directory(self):
        runtime_files = (
            DB_FILE,
            COMPANION_STATE_FILE,
            CHAT_HISTORY_FILE,
            _WLOG_FILE,
            COMPANION_ATTENTION_FILE,
            COMPANION_RITUAL_FILE,
            VISUAL_STORYBOARD_PATH,
        )

        self.assertEqual(RUNTIME_DIR.parent, BASE_DIR)
        for path in runtime_files:
            with self.subTest(path=path.name):
                self.assertEqual(path.parent, RUNTIME_DIR)

    def test_checked_in_profile_remains_outside_runtime_directory(self):
        self.assertEqual(COMPANION_PROFILE_FILE.parent, BASE_DIR)
        self.assertNotEqual(COMPANION_PROFILE_FILE.parent, RUNTIME_DIR)


if __name__ == "__main__":
    unittest.main()
