"""Unit tests for the shared JSON persistence helpers."""

import tempfile
import unittest
from pathlib import Path

from companion_app.database.common import _load_json, _save_json


class JsonPersistenceTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            expected = {"count": 3, "items": ["a", "b"]}
            _save_json(path, expected)
            self.assertEqual(_load_json(path, {}), expected)

    def test_save_creates_missing_parent_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime" / "nested" / "state.json"
            expected = {"ready": True}
            _save_json(path, expected)
            self.assertEqual(_load_json(path, {}), expected)

    def test_wrong_root_type_returns_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text('["not", "a", "dict"]', encoding="utf-8")
            self.assertEqual(_load_json(path, {}), {})


if __name__ == "__main__":
    unittest.main()
