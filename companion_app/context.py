"""Prompt context selection and assembly."""

import re
from datetime import datetime
import time

from companion_app import state as runtime_state
from companion_app.attention import (
    _companion_companionship_context,
    _companion_conversation_rhythm,
    _companion_ritual_context,
    _update_companion_attention,
)
from companion_app.logging import wlog, wlog_exc
from companion_app.persistence import (
    COMPANION_SOCIAL_LOCK,
    COMPANION_SOCIAL_THREADS,
    _load_companion_profile,
    _load_companion_state,
    get_companion_self_memory,
    get_shared_history,
    get_user_preferences,
)
from companion_app.prompts import SYSTEM_PROMPT

BRAIN_MAX_MEMORIES = 4
BRAIN_MAX_RELATIONSHIP = 3

BRAIN_PREFS_ALWAYS = 3
BRAIN_PREFS_RELEVANT = 2

BRAIN_MAX_PROFILE = 5
BRAIN_MAX_SELF_BELIEFS = 3
BRAIN_MAX_THREADS = 2

BRAIN_ITEM_CHARS = 220


BRAIN_VISUAL_RULES = (
    "[VISUAL RULES] You receive a text timeline derived from local "
    "screen captures. It contains foreground-window titles and "
    "process names, not screenshot pixels or readable interface "
    "contents. Never infer unseen text, objects, code, numbers, "
    "people, or game events from a window title. The user's message "
    "always takes priority over this limited metadata."
)


_BRAIN_STOPWORDS = frozenset((
    "that this with have from your what when where which they them then "
    "than were been will would could should about just like into over "
    "some more very much really also only still even back here there "
    "thing things gonna want wanna dont cant didnt isnt youre thats "
    "user companion"
).split())


def _kw(text):
    return {
        word
        for word in re.findall(
            r"[a-z]{4,}",
            str(text).lower(),
        )
        if word not in _BRAIN_STOPWORDS
    }


def _trim(text, limit=BRAIN_ITEM_CHARS):
    text = re.sub(
        r"\s+",
        " ",
        str(text),
    ).strip()

    if len(text) <= limit:
        return text

    return text[:limit - 3].rstrip() + "..."


def _pick_relevant(
    items,
    query,
    limit,
    floor=1,
    key=lambda item: item,
):
    """
    Rank items by keyword overlap with the current query.

    Items are supplied oldest-to-newest or lowest-to-highest priority.
    Results are returned in their original chronological order.

    If fewer than `floor` relevant matches exist, newer items fill
    the remaining slots.
    """
    items = list(items)

    if not items or limit <= 0:
        return []

    query_keywords = _kw(query)
    scored = []

    if query_keywords:
        for index, item in enumerate(items):
            overlap = len(
                query_keywords & _kw(key(item))
            )

            if overlap > 0:
                scored.append((overlap, index))

    scored.sort(reverse=True)

    picked = [
        index
        for _, index in scored[:limit]
    ]

    needed = max(
        0,
        min(floor, limit) - len(picked),
    )

    for index in range(len(items) - 1, -1, -1):
        if needed <= 0:
            break

        if index not in picked:
            picked.append(index)
            needed -= 1

    return [
        items[index]
        for index in sorted(picked)
    ]


def _user_side(moment):
    moment = str(moment).strip()

    if moment.startswith("User:"):
        moment = moment[len("User:"):]

    return moment.split(
        " | Companion:",
        1,
    )[0].strip()


def _block_memory(memories_for_prompt, query):
    picked = _pick_relevant(
        memories_for_prompt or [],
        query,
        BRAIN_MAX_MEMORIES,
        floor=1,
    )

    if not picked:
        return ""

    return (
        "[MEMORY] Things the user has told you. "
        "Use only if relevant; never recite.\n"
        + "\n".join(
            f"- {_trim(memory)}"
            for memory in picked
        )
    )


def _block_relationship(query):
    rows = get_shared_history(40)

    picked = _pick_relevant(
        rows,
        query,
        BRAIN_MAX_RELATIONSHIP,
        floor=1,
        key=lambda row: _user_side(row[2]),
    )

    if not picked:
        return ""

    lines = [
        "[SHARED HISTORY] Relevant shared moments "
        "from the user's side. Use only if they naturally fit; "
        "never recite."
    ]

    for _created, category, moment in picked:
        lines.append(
            f"- [{category}] {_trim(_user_side(moment))}"
        )

    return "\n".join(lines)


def _block_preferences(query):
    rows = get_user_preferences(15)

    if not rows:
        return ""

    # Standing preferences always apply.
    # Additional preferences are ranked by topic relevance.
    always = rows[:BRAIN_PREFS_ALWAYS]

    extra = _pick_relevant(
        rows[BRAIN_PREFS_ALWAYS:],
        query,
        BRAIN_PREFS_RELEVANT,
        floor=0,
        key=lambda row: row[0],
    )

    lines = [
        "[HOW THE USER WANTS TO BE TREATED] "
        "Her own stated preferences. Respect them naturally; "
        "never recite."
    ]

    for preference, _confidence, _source, _reinforced in (
        always + extra
    ):
        lines.append(
            f"- {_trim(preference, 200)}"
        )

    return "\n".join(lines)


def _block_companion(query):
    parts = []

    profile = _load_companion_profile()

    if profile:
        identity = profile.get("identity", {})

        if (
            isinstance(identity, dict)
            and identity.get("self_description")
        ):
            parts.append(
                "Identity: "
                + _trim(
                    identity["self_description"],
                    300,
                )
            )

        # Lower-priority categories are inserted first.
        # This lets _pick_relevant use newer/higher-priority
        # entries as its fallback padding.
        items = []

        for key, label in (
            ("ambitions", "Ambition"),
            ("quirks", "Quirk"),
            ("opinions", "Opinion"),
            ("dislikes", "Dislike"),
            ("likes", "Like"),
        ):
            values = profile.get(key, [])

            if isinstance(values, list):
                items.extend(
                    (label, str(value))
                    for value in values
                )

        picked_profile = _pick_relevant(
            items,
            query,
            BRAIN_MAX_PROFILE,
            floor=2,
            key=lambda item: item[1],
        )

        for label, value in reversed(picked_profile):
            parts.append(
                f"{label}: {_trim(value, 120)}"
            )

    # These are candidate preferences extracted from the companion's
    # own earlier responses, not immutable personality instructions.
    beliefs = get_companion_self_memory(15)

    picked = _pick_relevant(
        list(reversed(beliefs)),
        query,
        BRAIN_MAX_SELF_BELIEFS,
        floor=0,
        key=lambda row: row[0],
    )

    for belief, category, _confidence in picked:
        parts.append(
            f"Previously expressed, open to revision "
            f"({category}): {_trim(belief, 160)}"
        )

    if not parts:
        return ""

    return (
        "[COMPANION PROFILE] Background about your personality. "
        "Profile lines are established preferences; lines marked "
        "'previously expressed' are things you once said and may "
        "change your mind about. These are yours, not the user's. "
        "You may disagree with her. This is not a script.\n"
        + "\n".join(
            f"- {part}"
            for part in parts
        )
    )


def _block_threads():
    with COMPANION_SOCIAL_LOCK:
        threads = list(
            COMPANION_SOCIAL_THREADS
        )[-BRAIN_MAX_THREADS:]

    if not threads:
        return ""

    return (
        "[OPEN THREADS] Optional topics raised earlier. "
        "Do not interrogate; return to one only if it fits.\n"
        + "\n".join(
            f"- {_trim(thread, 180)}"
            for thread in threads
        )
    )


def _block_state(state, user_text):
    attention = _update_companion_attention()

    category = attention.get(
        "category",
        "general desktop activity",
    )

    since = float(
        attention.get("since", 0) or 0
    )

    seconds = (
        max(0, int(time.time() - since))
        if since
        else 0
    )

    held = (
        f"{seconds // 60}m"
        if seconds >= 60
        else f"{seconds}s"
    )

    now = datetime.now()
    hour = now.hour

    if 5 <= hour < 12:
        period = "morning"
    elif 12 <= hour < 17:
        period = "afternoon"
    elif 17 <= hour < 22:
        period = "evening"
    else:
        period = "late night"

    last_user = float(
        state.get("last_user_message_time", 0) or 0
    )

    silence = int(
        time.time()
        - (
            last_user
            if last_user
            else runtime_state.COMPANION_SESSION_STARTED
        )
    )

    silence_text = (
        f"{silence // 60}m"
        if silence >= 60
        else f"{silence}s"
    )

    topic = state.get("topic", "general")

    lines = [
        "[CURRENT STATE] Private background. "
        "Never mention or recite it. "
        "Emotions are estimates, not mind-reading.",

        (
            f"mood={state.get('mood', 'calm')} | "
            f"energy={state.get('energy', 'normal')} | "
            f"tone={state.get('relationship_tone', 'conversational')} | "
            f"topic={topic}"
        ),

        (
            f"User: emotion="
            f"{state.get('user_emotion', 'calm')}"
            f"({state.get('user_emotion_intensity', 1)}/5) | "
            f"doing={category} for {held}"
        ),

        (
            f"time={now.strftime('%I:%M %p').lstrip('0')} "
            f"({period}) | "
            f"silence since the user's last message={silence_text}"
        ),
    ]

    if user_text and len(user_text.strip()) <= 45:
        lines.append("reply_shape=brief")

    ritual_context = _companion_ritual_context(user_text)

    flags = [
        line[2:].strip()
        for line in ritual_context.splitlines()
        if line.startswith("- ")
    ]

    if flags:
        lines.append(
            "moment: "
            + _trim(" ".join(flags), 300)
        )

    return "\n".join(lines)


def _build_brain_system(
    state,
    user_text,
    memories_for_prompt,
):
    """
    Assemble the permanent personality prompt and relevant context.

    Returns:
        system_text
        [(block_name, character_count), ...]
    """
    query = (
        user_text
        or state.get("last_user_message", "")
    )

    builders = (
        ("core", lambda: str(SYSTEM_PROMPT).strip()),

        ("visual_rules", lambda: BRAIN_VISUAL_RULES),

        (
            "memory",
            lambda: _block_memory(
                memories_for_prompt,
                query,
            ),
        ),

        (
            "shared_history",
            lambda: _block_relationship(query),
        ),

        (
            "preferences",
            lambda: _block_preferences(query),
        ),

        (
            "companion_profile",
            lambda: _block_companion(query),
        ),

        ("threads", _block_threads),

        (
            "conversation_rhythm",
            lambda: _companion_conversation_rhythm(user_text or query),
        ),

        # Volatile, moment-to-moment context goes last.
        (
            "state",
            lambda: _block_state(state, user_text),
        ),

        (
            "companionship_mode",
            lambda: _companion_companionship_context(state),
        ),
    )

    texts = []
    sizes = []

    for name, builder in builders:
        try:
            block = builder()

        except Exception as exc:
            wlog_exc("PROMPT", exc)

            wlog(
                "PROMPT",
                f"block '{name}' failed and was skipped",
            )

            continue

        if block and str(block).strip():
            block = str(block).strip()

            texts.append(block)
            sizes.append((name, len(block)))

    return (
        "\n\n".join(texts),
        sizes,
    )
