"""Thread-safe diagnostic logging for the Companion application."""

import os
import re
import threading
from datetime import datetime

from .patterns import LEAK_MARKERS
from .database.common import RUNTIME_DIR

_WLOG_CONSOLE = os.getenv("COMPANION_LOG", "1") != "0"
_WLOG_FILE_ON = os.getenv("COMPANION_LOG_FILE", "1") != "0"
_WLOG_FULL = os.getenv("COMPANION_LOG_FULL", "0") != "0"

_WLOG_FILE = RUNTIME_DIR / "companion_debug.log"

_WLOG_MAX_BYTES = 20 * 1024 * 1024
_WLOG_LOCK = threading.Lock()
_WLOG_LAST = {}
_WLOG_CHANGE_LOCK = threading.Lock()


def _wlog_write(text):
    if not _WLOG_FILE_ON:
        return

    try:
        if (
            _WLOG_FILE.exists()
            and _WLOG_FILE.stat().st_size > _WLOG_MAX_BYTES
        ):
            old = _WLOG_FILE.with_name("companion_debug.log.old")

            if old.exists():
                old.unlink()

            _WLOG_FILE.rename(old)

        with open(_WLOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(text)

    except Exception:
        pass


def wlog(tag, msg):
    stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    line = (
        f"{stamp} [{tag}] "
        f"({threading.current_thread().name}) {msg}"
    )

    with _WLOG_LOCK:
        if _WLOG_CONSOLE:
            try:
                print(line, flush=True)

            except Exception:
                try:
                    print(
                        line.encode(
                            "ascii",
                            "replace"
                        ).decode("ascii"),
                        flush=True
                    )
                except Exception:
                    pass

        _wlog_write(line + "\n")


def wdump(tag, title, body):
    if not (_WLOG_FILE_ON and _WLOG_FULL):
        return

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _WLOG_LOCK:
        _wlog_write(
            f"\n===== {stamp} [{tag}] {title} =====\n"
            f"{body}\n"
            f"===== end {title} =====\n\n"
        )


def wlog_change(key, msg, tag="INITIATIVE"):
    """Log only when the message associated with a key changes."""

    with _WLOG_CHANGE_LOCK:
        changed = _WLOG_LAST.get(key) != msg
        if changed:
            _WLOG_LAST[key] = msg

    if changed:
        wlog(tag, msg)


def reset_wlog_changes():
    """Clear change-deduplication state after an initiative evaluation."""
    with _WLOG_CHANGE_LOCK:
        _WLOG_LAST.clear()


def _wpreview(text, limit=160):
    t = re.sub(r"\s+", " ", str(text)).strip()

    return (
        t
        if len(t) <= limit
        else t[:limit] + "..."
    )


def wlog_exc(tag, exc):
    import traceback

    wlog(tag, f"ERROR {type(exc).__name__}: {exc}")

    tb = traceback.format_exc()

    if tb and "NoneType: None" not in tb:
        wlog(tag, "traceback:\n" + tb.rstrip())


def _wformat_messages(messages):
    parts = []

    for i, message in enumerate(messages):
        content = message.get("content", "")

        parts.append(
            f"--- [{i}] {message.get('role')} "
            f"({len(str(content))} chars) ---\n"
            f"{content}"
        )

    return "\n\n".join(parts)


def _wmsgs_summary(messages):
    try:
        sizes = [
            f"{message.get('role', '?')}:"
            f"{len(str(message.get('content', '')))}c"
            for message in messages
        ]

        total = sum(
            len(str(message.get("content", "")))
            for message in messages
        )

        return (
            f"{len(messages)} msgs, "
            f"{total} chars (~{total // 4} tokens) "
            f"[{', '.join(sizes)}]"
        )

    except Exception:
        return "?"


def _wlog_response(response, reply, elapsed):
    try:
        choice = response.choices[0]

        raw = choice.message.content or ""

        finish = getattr(choice, "finish_reason", None)
        usage = getattr(response, "usage", None)

        if usage:
            used = (
                f"prompt_tokens="
                f"{getattr(usage, 'prompt_tokens', '?')} "
                f"completion_tokens="
                f"{getattr(usage, 'completion_tokens', '?')}"
            )
        else:
            used = "usage=n/a"

        trimmed = len(raw.strip()) - len(reply)

        note = (
            f" | cleaner removed {trimmed} chars"
            if trimmed > 0
            else ""
        )

        wlog(
            "BRAIN",
            f"reply in {elapsed:.1f}s | "
            f"model={getattr(response, 'model', '?')} "
            f"finish={finish} {used} | "
            f"raw={len(raw)}c cleaned={len(reply)}c{note}",
        )

        if finish == "length":
            wlog(
                "BRAIN",
                "WARNING: finish=length -> "
                "reply was CUT OFF by the max_tokens limit"
            )

        if not reply.strip():
            wlog(
                "BRAIN",
                "WARNING: reply is EMPTY after cleaning. "
                f"Raw output length: {len(raw)} chars."
            )

        if "###" in raw:
            wlog(
                "BRAIN",
                "NOTE: raw output contained ### template markers; "
                "inspect the raw and cleaned output"
            )

        try:
            if LEAK_MARKERS.search(raw):
                wlog(
                    "BRAIN",
                    "WARNING: raw output looks like "
                    "leaked reasoning/meta text"
                )
        except Exception:
            pass

        wdump("BRAIN", "RAW MODEL OUTPUT", raw)
        wdump("BRAIN", "CLEANED REPLY", reply)

        if _WLOG_FULL:
            wlog(
                "BRAIN",
                "reply preview: " + _wpreview(reply, 220)
            )
        else:
            wlog(
                "BRAIN",
                f"reply preview omitted ({len(reply)} chars; full logging disabled)"
            )

    except Exception as exc:
        wlog(
            "BRAIN",
            f"(could not log response details: {exc})"
        )


# ============================================================
