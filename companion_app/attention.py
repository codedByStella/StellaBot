"""Desktop attention, conversational rituals, and interaction rhythm."""

import ctypes
import ctypes.wintypes
import threading
import time
from datetime import datetime
from pathlib import Path

from companion_app import state as runtime_state
from companion_app.logging import wlog_change
from companion_app.persistence import _load_companion_state, _load_json, _save_json
from companion_app.windows import _user32, _kernel32
from companion_app.database.common import RUNTIME_DIR

COMPANION_ATTENTION_FILE = RUNTIME_DIR / "companion_attention.json"
COMPANION_RITUAL_FILE = RUNTIME_DIR / "companion_rituals.json"
_RITUAL_LOCK = threading.Lock()

def _get_foreground_window():
    user32 = _user32
    kernel32 = _kernel32

    if user32 is None or kernel32 is None:
        return "", ""

    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        return "", ""

    # When the companion window is foreground, retain the last
    # non-companion application as the user's observed context.
    if hwnd == runtime_state.COMPANION_HWND:
        return runtime_state.last_visual_title, runtime_state.last_visual_process

    length = user32.GetWindowTextLengthW(hwnd)

    if length > 0:
        buffer = ctypes.create_unicode_buffer(length + 1)

        user32.GetWindowTextW(
            hwnd,
            buffer,
            length + 1
        )

        title = buffer.value.strip()

    else:
        title = ""

    process_name = ""
    pid = ctypes.wintypes.DWORD()

    user32.GetWindowThreadProcessId(
        hwnd,
        ctypes.byref(pid)
    )

    if pid.value:
        handle = kernel32.OpenProcess(
            0x1000,
            False,
            pid.value,
        )

        if handle:
            try:
                size = ctypes.wintypes.DWORD(1024)
                exe_buffer = ctypes.create_unicode_buffer(1024)

                if kernel32.QueryFullProcessImageNameW(
                    handle,
                    0,
                    exe_buffer,
                    ctypes.byref(size),
                ):
                    process_name = Path(
                        exe_buffer.value
                    ).name.lower()

            finally:
                kernel32.CloseHandle(handle)

    return title, process_name


def _classify_attention(title, process_name):
    combined = f"{title} {process_name}".lower()

    if any(x in combined for x in (
        "chatgpt",
        "openai",
    )):
        return "companion interface"

    if any(x in combined for x in (
        "powershell",
        "windows terminal",
        "command prompt",
        "python",
        "visual studio",
        "vs code",
        "notepad",
    )):
        return "coding / technical work"

    if any(x in combined for x in (
        "last epoch",
        "minecraft",
        "aberoth",
        "terraria",
        "steam",
        "game",
        "dungeon",
        "roblox",
        "runescape",
    )):
        return "gaming"

    if any(x in combined for x in (
        "youtube",
        "twitch",
        "netflix",
        "spotify",
        "vlc",
        "media",
        "video",
    )):
        return "media / entertainment"

    if any(x in combined for x in (
        "chrome",
        "edge",
        "firefox",
        "opera",
        "browser",
    )):
        return "web browsing"

    return "general desktop activity"


def _load_attention_state():
    return _load_json(
        COMPANION_ATTENTION_FILE,
        {
            "title": "",
            "process": "",
            "category": "unknown",
            "since": 0.0,
            "previous_title": "",
            "previous_process": "",
            "changed": False,
        },
    )


def _update_companion_attention():
    now = time.time()
    state = _load_attention_state()

    title, process_name = _get_foreground_window()

    previous_title = state.get("title", "")
    previous_process = state.get("process", "")

    changed = (
        title != previous_title
        or process_name != previous_process
    )

    if changed:
        state["previous_title"] = previous_title
        state["previous_process"] = previous_process
        state["since"] = now

    state["title"] = title
    state["process"] = process_name
    state["category"] = _classify_attention(
        title,
        process_name
    )
    state["changed"] = changed

    _save_json(COMPANION_ATTENTION_FILE, state)

    return state


# ============================================================
# SITUATIONAL AWARENESS
# ============================================================


# ============================================================
# CONVERSATIONAL RITUALS
# ============================================================

def _load_companion_rituals():
    default = {
        "last_session_greeting": 0.0,
        "last_return_greeting": 0.0,
        "last_goodnight": 0.0,
        "last_goodbye": 0.0,
        "last_late_night_comment": 0.0,
    }

    data = _load_json(COMPANION_RITUAL_FILE, {})

    if isinstance(data, dict):
        default.update(data)

    return default


def _companion_ritual_context(user_text):
    with _RITUAL_LOCK:
        return _companion_ritual_context_locked(user_text)


def _companion_ritual_context_locked(user_text):
    now = time.time()
    text = str(user_text).lower().strip()

    rituals = _load_companion_rituals()
    state = _load_companion_state()

    situations = []

    session_age = max(
        0,
        int(now - runtime_state.COMPANION_SESSION_STARTED)
    )

    last_user = float(
        state.get("last_user_message_time", 0) or 0
    )

    silence = (
        int(now - last_user)
        if last_user
        else session_age
    )

    current_hour = datetime.now().hour

    if (
        session_age < 120
        and now - float(rituals.get("last_session_greeting", 0)) > 3600
    ):
        situations.append(
            "This is the beginning of a companion session. "
            "A natural greeting may fit, but do not use a canned greeting."
        )

    if (
        text
        and silence >= 600
        and now - float(rituals.get("last_return_greeting", 0)) > 1800
    ):
        situations.append(
            "The user has returned after being away. "
            "A natural acknowledgement may fit the message."
        )
        rituals["last_return_greeting"] = now

    if (
        current_hour < 5
        and now - float(rituals.get("last_late_night_comment", 0)) > 1800
    ):
        situations.append(
            "It is very late. The companion may naturally adopt "
            "a quieter or more relaxed conversational tone."
        )
        rituals["last_late_night_comment"] = now

    if any(x in text for x in (
        "goodnight",
        "good night",
        "going to bed",
        "going to sleep",
        "i should sleep",
    )):
        if now - float(rituals.get("last_goodnight", 0)) > 1800:
            situations.append(
                "This appears to be a goodnight moment."
            )

    if any(x in text for x in (
        "bye",
        "goodbye",
        "i'm leaving",
        "im leaving",
        "talk later",
        "see you later",
    )):
        if now - float(rituals.get("last_goodbye", 0)) > 1800:
            situations.append(
                "This may be a goodbye or temporary parting."
            )

    if not situations:
        return (
            "CONVERSATIONAL RITUAL CONTEXT:\n"
            "No special ritual moment is currently indicated."
        )

    _save_json(COMPANION_RITUAL_FILE, rituals)

    return (
        "CONVERSATIONAL RITUAL CONTEXT:\n"
        + "\n".join("- " + item for item in situations)
        + "\nRituals are patterns, not scripts."
    )


def _record_companion_ritual(user_text):
    with _RITUAL_LOCK:
        return _record_companion_ritual_locked(user_text)


def _record_companion_ritual_locked(user_text):
    now = time.time()
    text = str(user_text).lower()

    rituals = _load_companion_rituals()

    if any(x in text for x in (
        "goodnight",
        "good night",
        "going to bed",
        "going to sleep",
        "i should sleep",
    )):
        rituals["last_goodnight"] = now

    if any(x in text for x in (
        "bye",
        "goodbye",
        "talk later",
        "see you later",
    )):
        rituals["last_goodbye"] = now

    if now - runtime_state.COMPANION_SESSION_STARTED < 120:
        rituals["last_session_greeting"] = now

    _save_json(COMPANION_RITUAL_FILE, rituals)


# ============================================================
# CONVERSATIONAL RHYTHM
# ============================================================

def _companion_conversation_rhythm(user_text):
    text = str(user_text).strip()
    lower = text.lower()
    length = len(text)

    if length <= 45:
        mode = "brief natural conversation"

    elif length <= 180:
        mode = "normal conversational reply"

    else:
        mode = (
            "thoughtful conversational reply with enough detail "
            "to address what the user actually said"
        )

    if any(x in lower for x in (
        "i'm sad",
        "im sad",
        "i'm upset",
        "im upset",
        "i'm hurt",
        "im hurt",
        "i feel awful",
        "i feel terrible",
    )):
        mode += ". Prioritize the emotional moment."

    if any(x in lower for x in (
        "how do",
        "how can",
        "why does",
        "what causes",
        "error",
        "python",
        "powershell",
        "code",
        "coding",
        "api",
        "install",
        "fix",
        "crash",
    )):
        mode += (
            ". Be useful and specific without drowning the user "
            "in background."
        )

    if any(x in lower for x in (
        "bonk",
        "hehe",
        "lol",
        "lmao",
        "haha",
        "??",
        "gremlin",
        "dummy",
        "silly",
        "what the fuck",
    )):
        mode += ". Match the playful energy."

    if "?" in text:
        mode += (
            ". Answer the user's question directly before "
            "adding anything else."
        )

    return (
        "CONVERSATIONAL RHYTHM:\n"
        f"Preferred response shape: {mode}.\n"
        "Do not pad short moments into paragraphs.\n"
        "Do not make every response end with a question.\n"
        "Sometimes a natural response is only one sentence.\n"
        "Sometimes a longer response is appropriate.\n"
        "Prioritize natural social rhythm over perfectly structured prose."
    )


# ============================================================
# COMPANIONSHIP MODE
# ============================================================

def _companion_companionship_context(state=None):
    attention = _load_attention_state()
    state = (
        state
        if isinstance(state, dict)
        else _load_companion_state()
    )

    category = attention.get(
        "category",
        "general desktop activity"
    )

    topic = state.get("topic", "general")
    emotion = state.get("user_emotion", "calm")

    lines = ["CURRENT COMPANIONSHIP MODE:"]

    if category == "gaming" or topic == "gaming":
        lines.extend([
            "The companion is accompanying the user while she games.",
            "She may observe, react, tease, celebrate, commiserate, "
            "or offer an opinion.",
            "She does not need to comment on every gameplay event.",
        ])

    elif category == "coding / technical work" or topic in (
        "coding",
        "technical problem",
    ):
        lines.extend([
            "The companion is accompanying the user during technical work.",
            "She can act like a quiet co-pilot: notice progress, react to "
            "successes or problems, and help when asked.",
        ])

    elif category == "media / entertainment":
        lines.append(
            "The companion is accompanying the user during entertainment."
        )

    else:
        lines.append(
            "The companion is in general companionship mode."
        )

    emotion_notes = {
        "excited": "Matching some of the user's excitement is appropriate.",
        "frustrated": "Lean supportive rather than adding friction.",
        "hurt": "Prioritize warmth, patience, and emotional support.",
        "tired": "Companionship can be quieter and more relaxed.",
        "playful": "Playful teasing is welcome when natural.",
        "warm": "A warm and friendly tone is appropriate.",
    }

    if emotion in emotion_notes:
        lines.append(emotion_notes[emotion])

    lines.extend([
        "",
        "Companionship is not constant commentary.",
        "Being present can mean saying nothing.",
        "Do not manufacture observations merely because the companion "
        "has access to screen-activity metadata.",
    ])

    return "\n".join(lines)


# ============================================================
