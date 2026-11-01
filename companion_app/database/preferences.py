"""User preference learning and profile persistence."""

import re
import sqlite3
import time
from datetime import datetime

from .common import DB_FILE, COMPANION_PROFILE_FILE, _load_json, _save_json
from .core import _contains_any

RELATIONSHIP_PREFERENCES_READY = False

def _load_companion_profile():
    data = _load_json(COMPANION_PROFILE_FILE, {})
    return data if isinstance(data, dict) else {}


# ============================================================
# USER PREFERENCE MEMORY
# ============================================================

def _init_user_preferences():
    global RELATIONSHIP_PREFERENCES_READY

    if RELATIONSHIP_PREFERENCES_READY:
        return

    with sqlite3.connect(DB_FILE) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                preference TEXT NOT NULL,
                confidence INTEGER NOT NULL DEFAULT 3,
                source TEXT NOT NULL DEFAULT 'explicit',
                last_reinforced TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            )
            """
        )
        db.commit()

    RELATIONSHIP_PREFERENCES_READY = True


def get_user_preferences(limit=15):
    _init_user_preferences()

    with sqlite3.connect(DB_FILE) as db:
        return db.execute(
            """
            SELECT preference, confidence, source, last_reinforced
            FROM relationship_preferences
            WHERE status = 'active'
            ORDER BY confidence DESC, id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()


def _learn_user_preference(user_text):
    text = str(user_text).strip()

    if len(text) < 8:
        return

    lower = text.lower()

    positive_markers = (
        "i like when you",
        "i love when you",
        "i prefer when you",
        "i enjoy when you",
        "i want you to",
        "i'd like you to",
        "i like it when you",
        "i love it when you",
        "i prefer you",
        "i'd rather you",
    )

    negative_markers = (
        "i don't like when you",
        "i dont like when you",
        "i hate when you",
        "i don't want you to",
        "i dont want you to",
        "please don't",
        "please dont",
        "don't call me",
        "dont call me",
        "never call me",
    )

    if not _contains_any(
        lower,
        positive_markers + negative_markers,
    ):
        return

    normalized = re.sub(
        r"\s+",
        " ",
        text
    ).strip()[:700]
    normalized_key = normalized.lower()

    now = datetime.now().isoformat(timespec="seconds")

    with sqlite3.connect(DB_FILE) as db:
        row = db.execute(
            """
            SELECT id, confidence
            FROM relationship_preferences
            WHERE LOWER(preference) = ?
              AND status = 'active'
            LIMIT 1
            """,
            (normalized_key,),
        ).fetchone()

        if row:
            pref_id, confidence = row

            db.execute(
                """
                UPDATE relationship_preferences
                SET confidence = ?, last_reinforced = ?
                WHERE id = ?
                """,
                (
                    min(5, int(confidence) + 1),
                    now,
                    pref_id,
                ),
            )

        else:
            db.execute(
                """
                INSERT INTO relationship_preferences
                (
                    created_at,
                    preference,
                    confidence,
                    source,
                    last_reinforced,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    normalized,
                    3,
                    "explicit",
                    now,
                    "active",
                ),
            )

        db.commit()


# ============================================================
# COMPANION SELF-MEMORY
# ============================================================
