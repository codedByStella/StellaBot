"""Unit tests for model-output cleanup and duplicate detection."""

import unittest

from companion_app.model import _clean_reply, _too_similar


class ResponseProcessingTests(unittest.TestCase):
    def test_clean_reply_removes_speaker_prefix_and_extra_blank_lines(self):
        self.assertEqual(
            _clean_reply("Companion: Hello\n\n\nthere"),
            "Hello\n\nthere",
        )

    def test_clean_reply_removes_generated_channel_wrappers(self):
        self.assertEqual(
            _clean_reply("analysis: hidden<channel|>Companion: Ready."),
            "Ready.",
        )

    def test_similarity_detection_rejects_repeated_long_output(self):
        repeated = "This is a sufficiently long response. " * 5
        self.assertTrue(_too_similar(repeated, repeated))

    def test_similarity_detection_allows_empty_comparison(self):
        self.assertFalse(_too_similar("", "previous response"))


if __name__ == "__main__":
    unittest.main()
