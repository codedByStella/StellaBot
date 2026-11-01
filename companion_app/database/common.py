"""Shared file paths and JSON persistence helpers."""

import json
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = BASE_DIR / ".companion_runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = RUNTIME_DIR / "companion_runtime.db"
COMPANION_STATE_FILE = RUNTIME_DIR / "companion_state.json"

# The profile is a checked-in seed/configuration artifact. Runtime code
# reads it but does not overwrite it.
COMPANION_PROFILE_FILE = BASE_DIR / "companion_profile.json"


def _load_json(path, default):
    try:
        if not path.exists():
            return default

        value = json.loads(
            path.read_text(encoding="utf-8")
        )

        return (
            value
            if isinstance(value, type(default))
            else default
        )

    except Exception:
        return default


def _save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(
        f".{path.name}.{threading.get_ident()}.tmp"
    )

    try:
        temporary_path.write_text(
            json.dumps(
                value,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(path)

    except Exception as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass

        print(
            f"[JSON save error] {path.name}: {exc}"
        )


# ============================================================
# DATABASE: LONG-TERM MEMORIES
# ============================================================
