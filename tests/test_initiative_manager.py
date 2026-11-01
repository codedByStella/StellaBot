"""Unit tests for initiative state ownership."""

import time
import unittest

from companion_app.initiative import InitiativeManager


class InitiativeManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = InitiativeManager(
            add_message=lambda *args: None,
            set_status=lambda *args: None,
            ask_companion=lambda *args, **kwargs: "",
            take_screenshot=lambda: None,
        )

    def test_reset_clears_user_interaction_counters(self):
        self.manager.unanswered = 2
        self.manager.checks = 4
        self.manager.last_spoken_hash = "previous-frame"

        self.manager.reset_after_user()

        self.assertEqual(self.manager.unanswered, 0)
        self.assertEqual(self.manager.checks, 0)
        self.assertEqual(self.manager.last_spoken_hash, "")
        self.assertGreater(self.manager.next_initiative_at, time.time())

    def test_backoff_schedules_a_future_check(self):
        self.manager.checks = 3
        self.manager.schedule_next()
        self.assertGreater(self.manager.next_initiative_at, time.time())


if __name__ == "__main__":
    unittest.main()
