"""Companion self-memory and conversational thread persistence."""

import json
import re
import sqlite3
import threading
import time
from datetime import datetime

from .common import DB_FILE, _load_json, _save_json
from .core import _contains_any

COMPANION_SOCIAL_THREADS = []
COMPANION_SOCIAL_THREAD_MAX = 6
COMPANION_SOCIAL_LOCK = threading.Lock()
COMPANION_SELF_MEMORY_READY = False

def _init_companion_self_memory():
    global COMPANION_SELF_MEMORY_READY

    if COMPANION_SELF_MEMORY_READY:
        return

    with sqlite3.connect(DB_FILE) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS companion_self_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                belief TEXT NOT NULL,
                category TEXT NOT NULL,
                confidence INTEGER NOT NULL DEFAULT 2,
                last_reinforced TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            )
            """
        )
        db.commit()

    COMPANION_SELF_MEMORY_READY = True

def get_companion_self_memory(limit=15):
    _init_companion_self_memory()

    with sqlite3.connect(DB_FILE) as db:
        return db.execute(
            """
            SELECT belief, category, confidence
            FROM companion_self_memory
            WHERE status = 'active'
            ORDER BY confidence DESC, id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()


def _extract_companion_self_beliefs(reply):
    text = re.sub(
        r"\s+",
        " ",
        str(reply).replace("\n", " ")
    )

    candidates = []

    patterns = [
        (
            r"\bI (?:really |actually )?(?:like|love|prefer|enjoy|dislike|hate)"
            r"[^.!?]{3,160}[.!?]",
            "preference",
        ),
        (
            r"\bI (?:really |actually )?think "
            r"[^.!?]{3,160}[.!?]",
            "opinion",
        ),
        (
            r"\bI(?:'d| would) rather "
            r"[^.!?]{3,160}[.!?]",
            "preference",
        ),
        (
            r"\bI(?:'m| am) (?:a fan of|into) "
            r"[^.!?]{3,160}[.!?]",
            "interest",
        ),
    ]

    for pattern, category in patterns:
        for match in re.findall(pattern, text, flags=re.I):
            cleaned = re.sub(r"\s+", " ", match).strip()
            lower = cleaned.lower()

            if any(x in lower for x in (
                "i appreciate you",
                "i'm glad you're",
                "i am glad you're",
            )):
                continue

            if len(cleaned) >= 12:
                candidates.append((cleaned, category))

    result = []
    seen = set()

    for belief, category in candidates:
        key = belief.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append((belief, category))

    return result[:5]


def _save_companion_self_beliefs(reply):
    beliefs = _extract_companion_self_beliefs(reply)

    if not beliefs:
        return

    now = datetime.now().isoformat(timespec="seconds")

    with sqlite3.connect(DB_FILE) as db:
        for belief, category in beliefs:
            normalized = re.sub(
                r"\s+",
                " ",
                belief
            ).strip()
            normalized_key = normalized.lower()

            row = db.execute(
                """
                SELECT id, confidence
                FROM companion_self_memory
                WHERE LOWER(belief) = ?
                  AND status = 'active'
                LIMIT 1
                """,
                (normalized_key,),
            ).fetchone()

            if row:
                memory_id, confidence = row

                db.execute(
                    """
                    UPDATE companion_self_memory
                    SET confidence = ?, last_reinforced = ?
                    WHERE id = ?
                    """,
                    (
                        min(5, int(confidence) + 1),
                        now,
                        memory_id,
                    ),
                )

            else:
                db.execute(
                    """
                    INSERT INTO companion_self_memory
                    (
                        created_at,
                        belief,
                        category,
                        confidence,
                        last_reinforced,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now,
                        normalized,
                        category,
                        2,
                        now,
                        "active",
                    ),
                )

        db.commit()


# ============================================================
# CONVERSATIONAL THREAD TRACKING
# ============================================================


def _extract_companion_social_threads(reply):
    text = re.sub(
        r"\s+",
        " ",
        str(reply).strip()
    )

    if not text:
        return []

    candidates = []

    for match in re.findall(r"([^.!?]{3,220}\?)", text):
        question = match.strip()
        lower = question.lower()

        if any(x in lower for x in (
            "what's going on?",
            "whats going on?",
            "how are you?",
            "what are you doing?",
            "what are you working on?",
            "how's it going?",
            "hows it going?",
            "what happened?",
            "anything else?",
            "need anything?",
        )):
            continue

        candidates.append(question)

    for pattern in (
        r"\bI(?:'m| am) curious about ([^.!?]{4,180})",
        r"\bI wonder ([^.!?]{4,180})",
        r"\bI've been wondering ([^.!?]{4,180})",
        r"\bI'd like to know ([^.!?]{4,180})",
        r"\bI(?:'d| would) love to know ([^.!?]{4,180})",
    ):
        for match in re.findall(pattern, text, flags=re.I):
            candidates.append(
                "The companion is curious about " + match.strip()
            )

    result = []
    seen = set()

    for item in candidates:
        item = re.sub(r"\s+", " ", item).strip()
        key = item.lower()

        if len(item) < 8 or key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result[:3]


def _update_companion_social_threads(reply, user_text):
    new_threads = _extract_companion_social_threads(reply)

    with COMPANION_SOCIAL_LOCK:
        current = list(COMPANION_SOCIAL_THREADS)

        user_words = set(
            re.findall(
                r"[a-zA-Z]{4,}",
                str(user_text).lower()
            )
        )

        filtered = []

        for thread in current:
            thread_words = set(
                re.findall(
                    r"[a-zA-Z]{4,}",
                    thread.lower()
                )
            )

            if len(user_words & thread_words) >= 2:
                continue

            filtered.append(thread)

        existing = {
            item.lower()
            for item in filtered
        }

        for thread in new_threads:
            if thread.lower() not in existing:
                filtered.append(thread)
                existing.add(thread.lower())

        del filtered[:-COMPANION_SOCIAL_THREAD_MAX]

        COMPANION_SOCIAL_THREADS.clear()
        COMPANION_SOCIAL_THREADS.extend(filtered)


# ============================================================
# ATTENTION / FOREGROUND APPLICATION
# ============================================================
