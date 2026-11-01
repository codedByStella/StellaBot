"""Model transport, response hygiene, retries, and short-term history."""

import difflib
import json
import os
import random
import re
import threading
import time

from dotenv import load_dotenv
from openai import APIConnectionError, OpenAI

from companion_app.logging import wlog
from companion_app.persistence import _load_json, _save_json
from companion_app.patterns import LEAK_MARKERS
from companion_app.database.common import BASE_DIR, RUNTIME_DIR

load_dotenv(str(BASE_DIR / ".env"))

API_TOKEN = os.getenv("OPENROUTER_API_KEY")
MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
CHAT_HISTORY_FILE = RUNTIME_DIR / "companion_chat_history.json"
CHAT_HISTORY_MAX_TURNS = 10

client = None


def get_client():
    """Create the OpenRouter client lazily and validate configuration."""
    global client

    if not API_TOKEN:
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing. Add it to the .env file "
            "or the process environment before starting Companion."
        )

    if client is None:
        client = OpenAI(
            api_key=API_TOKEN,
            base_url="https://openrouter.ai/api/v1",
            timeout=120.0,
            max_retries=0,
        )

    return client


_COMPANION_CANCEL = threading.Event()


class CompanionCancelled(Exception):
    """Raised when the current companion turn is cancelled."""


def _clean_reply(text):
    """
    Convert raw model output into natural conversational text.

    This is defensive cleanup only. It does not intentionally
    rewrite personality, wording, or meaning.
    """
    text = str(text or "")

    # Common reasoning-channel boundary.
    if "<channel|>" in text:
        text = text.rsplit("<channel|>", 1)[1]

    # Other channel wrappers.
    text = re.sub(
        r"<\|channel>.*?(?:<channel\|>|$)",
        "",
        text,
        flags=re.S,
    )

    # Special generation tokens.
    text = re.sub(
        r"<\|[^>\n]{1,60}>|<[^<>\n|]{1,60}\|>",
        "",
        text,
    )

    # Remove accidentally generated speaker labels.
    text = re.sub(
        r"^\s*(?:Companion|User)"
        r"\s*(?:\([^)\n]{0,80}\))?"
        r"\s*:\s*",
        "",
        text,
        flags=re.I,
    )

    # Collapse excessive blank lines.
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def _opening_key(text):
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(text).lower(),
    ).strip()[:80]


def _too_similar(new, old):
    """
    Reject obvious repeated autonomous output.

    Checks:
        1. Whole-response similarity.
        2. Identical long opening.
    """
    new = str(new or "")
    old = str(old or "")

    if not new or not old:
        return False

    if (
        len(new) >= 100
        and len(old) >= 100
        and difflib.SequenceMatcher(
            None,
            old.lower(),
            new.lower(),
        ).ratio() >= 0.88
    ):
        return True

    new_opening = _opening_key(new)
    old_opening = _opening_key(old)

    return (
        len(new_opening) >= 40
        and new_opening == old_opening
    )

_RETRYABLE_STATUS = {
    408,
    409,
    425,
    429,
    500,
    502,
    503,
    504,
}


def _create_with_retry(messages, max_tokens):
    """
    Submit one OpenRouter request with bounded transient-error retries.

    OpenRouter chooses the serving provider according to the request's
    provider settings. Provider failover is controlled explicitly below.
    """

    attempts = 3
    retry_delay = 4.0
    retry_multiplier = 1.5
    max_retry_delay = 60.0

    cancel_event = _COMPANION_CANCEL

    def cancelled():
        return cancel_event.is_set()

    def wait_retry(delay):
        if cancel_event.wait(delay):
            raise CompanionCancelled()

    last_exc = None

    for attempt in range(1, attempts + 1):
        if cancelled():
            raise CompanionCancelled()

        started = time.time()

        try:
            wlog(
                "OPENROUTER",
                f"request attempt {attempt}/{attempts} | {len(messages)} messages",
            )

            response = get_client().chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=max_tokens,
                extra_body={
                    "provider": {
                        "allow_fallbacks": True,
                    }
                },
            )

            elapsed = time.time() - started

            if cancelled():
                raise CompanionCancelled()

            wlog(
                "OPENROUTER",
                f"request succeeded after {elapsed:.1f}s",
            )

            return response

        except Exception as exc:
            last_exc = exc
            elapsed = time.time() - started

            status = getattr(exc, "status_code", None)

            if status is None:
                error_response = getattr(exc, "response", None)
                status = getattr(error_response, "status_code", None)

            wlog(
                "OPENROUTER",
                (
                    f"attempt {attempt}/{attempts} failed after "
                    f"{elapsed:.1f}s: {type(exc).__name__} "
                    f"status={status} | {exc}"
                ),
            )

            if cancelled():
                raise CompanionCancelled()

            retryable = (
                status in _RETRYABLE_STATUS
                or isinstance(exc, APIConnectionError)
            )

            if not retryable or attempt >= attempts:
                break

            delay = min(
                retry_delay,
                max_retry_delay,
            )

            wlog(
                "OPENROUTER",
                f"transient failure (status={status}); retrying in {delay:.1f}s",
            )

            wait_retry(delay)

            retry_delay = min(
                retry_delay * retry_multiplier,
                max_retry_delay,
            )

    if last_exc is not None:
        raise last_exc

    raise RuntimeError(
        "OpenRouter request exited without a response."
    )

def _brain_request(messages, max_tokens=2000):
    return _create_with_retry(
        messages,
        max_tokens,
    )


def _extract_reply(response):
    try:
        content = response.choices[0].message.content

        return (
            _clean_reply(content)
            if content
            else ""
        )

    except Exception:
        return ""


# ============================================================
# ROLLING CONVERSATIONAL TRANSCRIPT
# ============================================================

_CHAT_HISTORY = [
    entry
    for entry in _load_json(
        CHAT_HISTORY_FILE,
        [],
    )
    if isinstance(entry, dict)
]

_CHAT_HISTORY_LOCK = threading.Lock()


def _record_exchange(
    user_text,
    reply,
    initiative,
):
    now = time.time()

    with _CHAT_HISTORY_LOCK:
        if user_text:
            _CHAT_HISTORY.append({
                "who": "user",
                "text": str(user_text)[:600],
                "ts": now,
            })

        if reply:
            _CHAT_HISTORY.append({
                "who": (
                    "Companion (unprompted)"
                    if initiative
                    else "Companion"
                ),
                "text": str(reply)[:600],
                "ts": now,
            })

        del _CHAT_HISTORY[
            :-CHAT_HISTORY_MAX_TURNS * 2
        ]

        snapshot = list(_CHAT_HISTORY)

    _save_json(
        CHAT_HISTORY_FILE,
        snapshot,
    )


_BOOKKEEPING_LOCK = threading.Lock()


def _recent_history_messages():
    """
    Convert the rolling transcript into valid user/assistant turns.

    Consecutive entries with the same role are merged. Any leading
    assistant messages are removed so the history begins with a user turn.
    """
    with _CHAT_HISTORY_LOCK:
        entries = list(_CHAT_HISTORY)[
            -(CHAT_HISTORY_MAX_TURNS * 2):
        ]

    output = []

    for entry in entries:
        text = re.sub(
            r"[ \t]+",
            " ",
            str(entry.get("text", "")),
        ).strip()[:600]

        if not text:
            continue

        who = str(entry.get("who", ""))

        role = (
            "assistant"
            if who.startswith("Companion")
            else "user"
        )

        if output and output[-1]["role"] == role:
            output[-1]["content"] += "\n" + text

        else:
            output.append({
                "role": role,
                "content": text,
            })

    while (
        output
        and output[0]["role"] == "assistant"
    ):
        output.pop(0)

    return output


# ============================================================
# BRAIN CONTEXT ASSEMBLY
# Compact, relevance-ranked context blocks
# ============================================================

# One permanent personality definition, followed by compact,
# labelled context blocks. Generated companion dialogue is not
# injected as personality instructions.
