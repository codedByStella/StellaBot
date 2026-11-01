"""Unit tests for bounded visual-reel history and deduplication."""

import time
import unittest

from companion_app.visual import reel


class VisualReelTests(unittest.TestCase):
    def setUp(self):
        with reel.VISUAL_REEL_LOCK:
            reel.VISUAL_REEL.clear()

    def tearDown(self):
        with reel.VISUAL_REEL_LOCK:
            reel.VISUAL_REEL.clear()

    def test_image_hash_is_stable_and_distinguishes_frames(self):
        first = "data:image/jpeg;base64,frame-one"
        second = "data:image/jpeg;base64,frame-two"

        self.assertEqual(reel._image_hash(first), reel._image_hash(first))
        self.assertNotEqual(reel._image_hash(first), reel._image_hash(second))

    def test_recording_same_frame_updates_last_seen_without_duplicate(self):
        screenshot = "data:image/jpeg;base64,same-frame"

        now = time.time()
        reel._record_visual_frame(screenshot, timestamp=now)
        reel._record_visual_frame(screenshot, timestamp=now + 15.0)

        frames = reel._snapshot_visual_reel()
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["ts"], now)
        self.assertEqual(frames[0]["last_seen"], now + 15.0)

    def test_reel_is_bounded_to_configured_frame_count(self):
        now = time.time()
        for index in range(reel.VISUAL_REEL_MAX_FRAMES + 3):
            reel._record_visual_frame(
                f"data:image/jpeg;base64,frame-{index}",
                timestamp=now + index,
            )

        frames = reel._snapshot_visual_reel()
        self.assertEqual(len(frames), reel.VISUAL_REEL_MAX_FRAMES)
        self.assertEqual(
            frames[-1]["hash"],
            reel._image_hash(
                f"data:image/jpeg;base64,frame-{reel.VISUAL_REEL_MAX_FRAMES + 2}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
