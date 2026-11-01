"""Shared interaction history persistence."""

import json
import re
import sqlite3
import time
from datetime import datetime

from .common import DB_FILE, _load_json, _save_json

RELATIONSHIP_TABLE_READY = False

def _init_shared_history():
    global RELATIONSHIP_TABLE_READY

    if RELATIONSHIP_TABLE_READY:
        return

    with sqlite3.connect(DB_FILE) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                category TEXT NOT NULL,
                moment TEXT NOT NULL
            )
            """
        )
        db.commit()

    RELATIONSHIP_TABLE_READY = True


def get_shared_history(limit=20):
    _init_shared_history()

    with sqlite3.connect(DB_FILE) as db:
        rows = db.execute(
            """
            SELECT created_at, category, moment
            FROM relationship_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    return list(reversed(rows))


def _save_shared_moment(category, user_text, companion_reply):
    _init_shared_history()

    user_part = re.sub(
        r"\s+",
        " ",
        str(user_text).strip()
    )

    reply_part = re.sub(
        r"\s+",
        " ",
        str(companion_reply).strip()
    )

    if not user_part:
        return

    moment = (
        f"User: {user_part[:400]} | "
        f"Companion: {reply_part[:350]}"
    )

    normalized = re.sub(
        r"\s+",
        " ",
        moment.lower()
    ).strip()

    with sqlite3.connect(DB_FILE) as db:
        recent = db.execute(
            """
            SELECT moment
            FROM relationship_history
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

        if any(
            re.sub(
                r"\s+",
                " ",
                str(row[0]).lower()
            ).strip() == normalized
            for row in recent
        ):
            return

        db.execute(
            """
            INSERT INTO relationship_history
            (created_at, category, moment)
            VALUES (?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                category,
                moment,
            ),
        )
        db.commit()


def _maybe_save_shared_moment(user_text, companion_reply):
    """
    Identify potentially meaningful shared interactions.

    This records milestones, recurring jokes, explicit memory
    requests, and significant project progress without treating
    routine dialogue as a special memory category.
    """

    text = f"{user_text} {companion_reply}".lower()

    score = 0
    category = "shared moment"

    if any(x in text for x in (
        "remember this",
        "remember that",
        "don't forget",
        "do not forget",
        "never forget",
        "remember when",
    )):
        score += 5
        category = "important memory"

    if any(x in text for x in (
        "we did it",
        "we made it",
        "we fixed it",
        "we finally",
        "we built",
        "our first",
        "we got it working",
        "your voice works",
        "your new voice",
        "your memory works",
    )):
        score += 3
        category = "milestone"

    if any(x in text for x in (
        "inside joke",
        "remember when",
        "that's our",
        "thats our",
        "we always",
        "you always",
        "our joke",
        "the joke",
    )):
        score += 2
        category = "inside joke"

    if any(x in text for x in (
        "companion.py",
        "build companion",
        "built companion",
        "companion voice",
        "gave you a voice",
        "gave you memory",
        "companion milestone",
    )):
        score += 2
        category = "project milestone"

    if score >= 2:
        _save_shared_moment(
            category,
            user_text,
            companion_reply,
        )


# ============================================================
# COMPANION PROFILE
# ============================================================
