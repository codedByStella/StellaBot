"""SQLite durable memories and inferred conversational state."""

import re
import sqlite3
import time
from datetime import datetime

from .common import DB_FILE, COMPANION_STATE_FILE, _load_json, _save_json

def _init_memory_db():
    with sqlite3.connect(DB_FILE) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                memory TEXT NOT NULL
            )
            """
        )

        db.commit()


def get_memories(limit=30):
    _init_memory_db()

    with sqlite3.connect(DB_FILE) as db:
        rows = db.execute(
            """
            SELECT memory
            FROM memories
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    return [
        row[0]
        for row in reversed(rows)
    ]


def save_memory(memory):
    memory = re.sub(
        r"\s+",
        " ",
        str(memory).strip()
    )

    memory = memory[:800]

    if len(memory) < 10:
        return

    _init_memory_db()

    with sqlite3.connect(DB_FILE) as db:
        recent = db.execute(
            """
            SELECT memory
            FROM memories
            ORDER BY id DESC
            LIMIT 20
            """
        ).fetchall()

        normalized = memory.lower()

        if any(
            str(row[0]).strip().lower() == normalized
            for row in recent
        ):
            return

        db.execute(
            """
            INSERT INTO memories (created_at, memory)
            VALUES (?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                memory[:800],
            ),
        )

        db.commit()

    print("[Companion remembered something.]")


def should_remember(user_text):
    """
    Rule-based durable-memory gate.

    Favors explicit, persistent information while avoiding
    treating ordinary conversational or game activity
    as long-term memory.
    """

    text = str(user_text).strip().lower()

    if len(text) < 20:
        return False

    durable_markers = (
        "remember this",
        "remember that",
        "don't forget",
        "do not forget",
        "from now on",
        "i prefer",
        "i'd prefer",
        "i would prefer",
        "i like when you",
        "i love when you",
        "i don't like when you",
        "i dont like when you",
        "please don't call me",
        "please dont call me",
        "never call me",
        "call me",
        "my favorite",
        "my favourite",
        "my name is",
    )

    return _contains_any(
        text,
        durable_markers,
    )


# ============================================================
# COMPANION INTERNAL STATE
# ============================================================

def _load_companion_state():
    default = {
        "mood": "engaged",
        "energy": "normal",
        "topic": "general",
        "relationship_tone": "conversational",
        "last_user_message": "",
        "last_reply": "",
        "last_user_message_time": 0.0,
        "last_companion_reply_time": 0.0,
        "user_emotion": "calm",
        "user_emotion_intensity": 1,
    }

    data = _load_json(
        COMPANION_STATE_FILE,
        {}
    )

    if isinstance(data, dict):
        default.update(data)

    return default


def _save_companion_state(state):
    _save_json(
        COMPANION_STATE_FILE,
        state
    )


def _contains_any(text, phrases):
    """Match complete phrases without accidental substring hits."""
    return any(
        re.search(
            rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])",
            text,
        )
        for phrase in phrases
    )


def _infer_companion_state(user_text, previous):
    text = str(user_text).strip()
    t = text.lower()

    state = dict(previous)

    scores = {
        "excited": 0,
        "playful": 0,
        "warm": 0,
        "curious": 0,
        "frustrated": 0,
        "hurt": 0,
        "tired": 0,
        "calm": 1,
    }

    if _contains_any(t, (
        "thank you",
        "thanks",
        "i appreciate",
        "that means a lot",
        "you're great",
        "you are great",
        "nice work",
        "good job",
        "that's kind",
        "thats kind",
        "sweet of you",
        "well done",
    )):
        scores["warm"] += 4

    if _contains_any(t, (
        "omg",
        "oh my god",
        "holy shit",
        "lets go",
        "let's go",
        "we did it",
        "we got it",
        "amazing",
        "awesome",
        "finally",
        "excited",
        "fuck yes",
        "yes",
        "yess",
    )):
        scores["excited"] += 4

    if "!" in text:
        scores["excited"] += min(
            3,
            text.count("!")
        )

    if _contains_any(t, (
        "lol",
        "lmao",
        "haha",
        "hahaha",
        "??",
        "bonk",
        "gremlin",
        "silly",
        "tease",
        "teasing",
    )):
        scores["playful"] += 4

    if "?" in text:
        scores["curious"] += 2

    if _contains_any(t, (
        "how do",
        "why does",
        "what if",
        "can we",
        "could we",
        "is there",
        "i wonder",
        "what happens",
    )):
        scores["curious"] += 3

    if _contains_any(t, (
        "fuck this",
        "fucking",
        "bullshit",
        "annoying",
        "annoyed",
        "pissed",
        "angry",
        "hate this",
        "broken",
        "not working",
        "doesn't work",
        "doesnt work",
        "error",
        "failed",
        "why the fuck",
    )):
        scores["frustrated"] += 4

    if _contains_any(t, (
        "i'm upset", "im upset", "i am upset", "i'm sad", "im sad",
        "i am sad", "i'm hurt", "im hurt", "i am hurt", "crying",
        "cry", "i feel awful", "i feel terrible", "not okay", "not ok",
        "scared", "overwhelmed", "i can't do this", "i cant do this",
    )):
        scores["hurt"] += 5

    if _contains_any(t, (
        "tired", "exhausted", "sleepy", "so tired", "going to bed",
        "going to sleep", "need sleep", "can't stay awake",
        "cant stay awake",
    )):
        scores["tired"] += 5

    if _contains_any(t, (
        "okay", "alright", "fine", "just chilling", "chilling",
        "relaxing", "nothing much",
    )):
        scores["calm"] += 2

    uppercase_letters = sum(
        char.isalpha() and char.isupper()
        for char in text
    )
    letters = sum(char.isalpha() for char in text)

    if letters >= 8 and uppercase_letters / letters >= 0.65:
        scores["excited"] += 3

    emotion = max(scores, key=scores.get)
    values = sorted(scores.values(), reverse=True)
    top_score = values[0]
    second_score = values[1]

    if top_score <= 1 or (
        top_score - second_score <= 1 and top_score < 4
    ):
        emotion = "calm"

    intensity = min(5, max(1, int(top_score)))

    state["user_emotion"] = emotion
    state["user_emotion_intensity"] = intensity

    mood_map = {
        "calm": ("engaged", "conversational"),
        "warm": ("warm", "friendly"),
        "excited": ("bright", "energetic"),
        "playful": ("playful", "teasing"),
        "hurt": ("gentle", "supportive"),
        "frustrated": ("focused", "supportive"),
        "tired": ("soft", "calm"),
        "curious": (
            "curious",
            state.get("relationship_tone", "conversational"),
        ),
    }

    if emotion in mood_map:
        state["mood"], state["relationship_tone"] = mood_map[emotion]

    if emotion in ("excited", "playful"):
        state["energy"] = "high"
    elif emotion in ("tired", "hurt"):
        state["energy"] = "low"
    else:
        state["energy"] = "normal"

    if _contains_any(t, (
        "companion.py", "powershell", "python", "code", "coding",
        "script", "api", "terminal", "program",
    )):
        state["topic"] = "coding"

    elif _contains_any(t, (
        "game", "gaming", "minecraft", "last epoch", "aberoth",
        "terraria", "dungeon", "build", "loot", "boss",
    )):
        state["topic"] = "gaming"

    elif _contains_any(t, (
        "voice", "tts", "gemini voice", "elevenlabs", "speaking", "sound",
    )):
        state["topic"] = "voice"

    elif _contains_any(t, (
        "personal conversation", "family", "friendship",
    )):
        state["topic"] = "personal conversation"

    elif _contains_any(t, (
        "broken", "error", "crash", "not working", "doesn't work",
        "doesnt work", "fix", "failed",
    )):
        state["topic"] = "technical problem"

    return state


# ============================================================
# SHARED INTERACTION HISTORY
# ============================================================
