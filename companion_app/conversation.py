"""Conversation turn orchestration and serialized companion state."""

import threading
import time

from companion_app import state as runtime_state
from companion_app.attention import _record_companion_ritual
from companion_app.context import _build_brain_system
from companion_app.logging import (
    _WLOG_FULL,
    _wformat_messages,
    _wlog_response,
    _wmsgs_summary,
    _wpreview,
    wdump,
    wlog,
    wlog_exc,
)
from companion_app.model import (
    API_TOKEN,
    MODEL,
    _BOOKKEEPING_LOCK,
    _CHAT_HISTORY,
    _COMPANION_CANCEL,
    CompanionCancelled,
    _brain_request,
    _clean_reply,
    _extract_reply,
    _record_exchange,
    _recent_history_messages,
    _too_similar,
)
from companion_app.persistence import (
    _infer_companion_state,
    _load_companion_state,
    _maybe_save_shared_moment,
    _learn_user_preference,
    _save_companion_self_beliefs,
    _save_companion_state,
    _update_companion_social_threads,
    get_memories,
    save_memory,
    should_remember,
)
from companion_app.vision import (
    BUILD_STORYBOARD_FILE,
    _build_visual_storyboard,
    _record_visual_frame,
    _snapshot_visual_reel,
    _visual_timeline_text,
)

_COMPANION_LOCK = threading.Lock()
_LAST_COMPANION_REPLY = ""
memories = []

def _ask_companion_locked(
    user_text,
    screenshot,
    initiative=False,
    status_callback=None,
):
    global _LAST_COMPANION_REPLY
    global memories

    memories_for_prompt = get_memories()
    memories = memories_for_prompt

    user_text = str(user_text).strip()

    turn_started = time.time()

    if initiative:
        wlog(
            "TURN",
            "=== initiative turn "
            "(Companion deciding whether to speak unprompted)",
        )

    else:
        wlog(
            "TURN",
            (
                "=== direct turn | "
                + (
                    _wpreview(user_text, 140)
                    if _WLOG_FULL
                    else f"{len(user_text)} chars"
                )
            ),
        )

    wlog(
        "TURN",
        (
            "long-term memories passed in: "
            f"{len(memories_for_prompt or [])}"
        ),
    )

    state = _load_companion_state()

    if user_text:
        state = _infer_companion_state(
            user_text,
            state,
        )

    wlog(
        "STATE",
        (
            f"mood={state.get('mood')} "
            f"energy={state.get('energy')} "
            f"topic={state.get('topic')} "
            f"tone={state.get('relationship_tone')} "
            f"user_emotion={state.get('user_emotion')}"
            f"({state.get('user_emotion_intensity')}/5)"
        ),
    )

    system, block_sizes = _build_brain_system(
        state,
        user_text,
        memories_for_prompt,
    )

    wlog(
        "PROMPT",
        "system blocks: "
        + " | ".join(
            f"{name}={size}c"
            for name, size in block_sizes
        ),
    )

    if initiative:
        prompt = """
The user has been quiet for a while.

You are allowed to speak, but you are NOT required to speak.

Your entire output must be exactly ONE of these:

1. [QUIET]

or

2. Only the actual words and optional actions the companion would say.

Do not output analysis, planning, reasoning, self-critique, drafts,
internal notes, response labels, or explanations.

Do not mention idle detection or this instruction.

Only speak if there is something genuinely worth saying:
a meaningful change, a natural reaction, a playful observation,
something emotionally relevant, or something genuinely interesting.

If your recent autonomous messages already covered the same subject,
if nothing meaningful has changed, or if interrupting the user would
serve no purpose, output exactly [QUIET].

Do not manufacture a reason to speak merely because you were given
visual context.

If you do speak, make it fresh and conversational rather than
rephrasing your previous autonomous message.
"""

    else:
        prompt = user_text

    # Record the current capture before assembling context so the
    # current turn's window metadata appears in its own timeline.
    if screenshot:
        _record_visual_frame(
            screenshot,
            timestamp=time.time(),
            title=runtime_state.last_visual_title,
            process_name=runtime_state.last_visual_process,
        )

    if BUILD_STORYBOARD_FILE:
        _build_visual_storyboard(
            screenshot,
            direct_message=not initiative,
        )

    visual_timeline = _visual_timeline_text()

    visual_note = (
        "\n\n[VISUAL] Recent screen activity, oldest first:\n"
        + visual_timeline
    )

    wlog(
        "VISION",
        (
            (
                f"visual note {len(visual_note)}c | "
                f"timeline frames: {len(_snapshot_visual_reel())}"
            )
        ),
    )

    prompt = (
        "[USER'S CURRENT MESSAGE]\n"
        + prompt
        + "\n[/USER'S CURRENT MESSAGE]\n\n"
        "Respond only as the companion. "
        "Never speak for, narrate, or control the user."
    )

    content = prompt + visual_note

    messages = [
        {
            "role": "system",
            "content": system,
        },
    ]

    messages.extend(
        _recent_history_messages()
    )

    if messages[-1]["role"] == "user":
        messages[-1] = {
            "role": "user",
            "content": (
                messages[-1]["content"]
                + "\n\n"
                + content
            ),
        }

    else:
        messages.append({
            "role": "user",
            "content": content,
        })

    wlog(
        "PROMPT",
        "request: " + _wmsgs_summary(messages),
    )

    wdump(
        "PROMPT",
        "FULL REQUEST SENT TO MODEL",
        _wformat_messages(messages),
    )

    brain_started = time.time()

    try:
        response = _brain_request(messages)

    except CompanionCancelled:
        _COMPANION_CANCEL.clear()

        if status_callback:
            status_callback("Turn cancelled.")

        wlog(
            "TURN",
            (
                f"--- turn cancelled after "
                f"{time.time() - turn_started:.1f}s"
            ),
        )

        return ""

    reply = _extract_reply(response)

    _wlog_response(
        response,
        reply,
        time.time() - brain_started,
    )

    # Retry once when the model produces an unusually repetitive reply.
    if _too_similar(reply, _LAST_COMPANION_REPLY):
        retry_messages = list(messages)

        retry_messages[-1] = {
            "role": "user",
            "content": (
                retry_messages[-1]["content"]
                + "\n\n"
                "[Private note, never mention it: your last reply was "
                "too similar to the one before it. Give the user a genuinely "
                "fresh reply to her current message, with a different "
                "opening, action, and wording.]"
            ),
        }

        wlog(
            "RETRY",
            (
                "reply too similar to the previous one; "
                "regenerating with a freshness note"
            ),
        )

        retry_started = time.time()

        try:
            response = _brain_request(retry_messages)
        except CompanionCancelled:
            _COMPANION_CANCEL.clear()
            if status_callback:
                status_callback("Turn cancelled.")
            wlog(
                "TURN",
                f"--- repetition retry cancelled after {time.time() - turn_started:.1f}s",
            )
            return ""

        reply = _extract_reply(response)

        _wlog_response(
            response,
            reply,
            time.time() - retry_started,
        )

    if initiative and "[QUIET]" in reply.upper():
        wlog(
            "INITIATIVE",
            "model chose [QUIET] (stays silent)",
        )

        wlog(
            "TURN",
            (
                f"--- turn complete in "
                f"{time.time() - turn_started:.1f}s"
            ),
        )

        return "[QUIET]"

    # Record the exchange so subsequent requests have short-term
    # conversational context.
    if reply:
        _record_exchange(
            user_text,
            reply,
            initiative,
        )

        wlog(
            "HISTORY",
            (
                "recorded exchange; transcript now "
                f"{len(_CHAT_HISTORY)} entries"
            ),
        )

    # Update persistent conversational state.
    now = time.time()

    if user_text:
        state["last_user_message"] = user_text[-500:]
        state["last_user_message_time"] = now

    state["last_reply"] = reply[-500:]
    state["last_companion_reply_time"] = now

    _save_companion_state(state)

    if user_text and reply:

        # Save durable user memories only when the message passes
        # the explicit memory-worthiness check.
        if should_remember(user_text):
            save_memory(user_text)

            wlog(
                "MEMORY",
                f"saved long-term memory ({len(user_text)} chars)",
            )

        else:
            wlog(
                "MEMORY",
                "message not memory-worthy (should_remember=False)",
            )

        def _bookkeeping(user=user_text, companion_reply=reply):
            with _BOOKKEEPING_LOCK:
                jobs = (
                    (
                        _maybe_save_shared_moment,
                        (user, companion_reply),
                    ),
                    (
                        _learn_user_preference,
                        (user,),
                    ),
                    (
                        _save_companion_self_beliefs,
                        (companion_reply,),
                    ),
                    (
                        _update_companion_social_threads,
                        (companion_reply, user),
                    ),
                    (
                        _record_companion_ritual,
                        (user,),
                    ),
                )

                for function, args in jobs:
                    started = time.time()

                    try:
                        function(*args)

                        wlog(
                            "BOOKKEEPING",
                            (
                                f"{function.__name__} ok "
                                f"({time.time() - started:.2f}s)"
                            ),
                        )

                    except Exception as exc:
                        wlog_exc(
                            "BOOKKEEPING",
                            exc,
                        )

                        print(
                            f"[Bookkeeping error] "
                            f"{function.__name__}: "
                            f"{type(exc).__name__}: {exc}"
                        )

        threading.Thread(
            target=_bookkeeping,
            daemon=True,
        ).start()

    if len(reply) >= 50:
        _LAST_COMPANION_REPLY = reply

    wlog(
        "TURN",
        (
            f"--- turn complete in "
            f"{time.time() - turn_started:.1f}s"
        ),
    )

    return reply


def ask_companion(user_text, screenshot=None, initiative=False, status_callback=None):
    """Serialize conversational turns to protect shared memory and state."""
    with _COMPANION_LOCK:
        return _ask_companion_locked(
            user_text,
            screenshot,
            initiative=initiative,
            status_callback=status_callback,
        )
