
import threading
import time
import tkinter as tk

from companion_app import state
from companion_app.conversation import ask_companion as _conversation_ask_companion
from companion_app.initiative import InitiativeManager
from companion_app.interface.window import CompanionWindow
from companion_app.logging import (
    _WLOG_CONSOLE,
    _WLOG_FILE,
    _WLOG_FILE_ON,
    _WLOG_FULL,
    wlog,
    wlog_change,
    wlog_exc,
)
from companion_app.model import API_TOKEN, MODEL, _CHAT_HISTORY, _COMPANION_CANCEL, get_client
from companion_app.persistence import (
    DB_FILE,
    _init_companion_self_memory,
    _init_memory_db,
    _init_shared_history,
    _init_user_preferences,
    get_memories,
)
from companion_app.vision import (
    _companion_visual_reel_loop,
    stop_visual_reel,
    take_screenshot,
)
from companion_app.voice import shutdown_voice_worker, speak
from companion_app.windows import _user32


window = None
root = None
entry = None
initiative_manager = None
_APP_STOP = threading.Event()
_shutting_down = False


def add_message(who, text):
    if window is not None and not _shutting_down:
        window.add_message(who, text)


def set_status(text):
    if window is not None and not _shutting_down:
        window.set_status(text)


# ============================================================
# REPLY HYGIENE
# ============================================================

def _cancel_current_turn():
    _COMPANION_CANCEL.set()

    wlog(
        "OPENROUTER",
        "USER CANCEL requested",
    )

    set_status("Cancellation requested; waiting for the current request to return.")


def ask_companion(user_text, screenshot=None, initiative=False):
    """Application-facing wrapper that routes status updates to the UI."""
    return _conversation_ask_companion(
        user_text,
        screenshot,
        initiative=initiative,
        status_callback=set_status,
    )


def _reset_initiative_after_user():
    initiative_manager.reset_after_user()


def send_message(event=None):
    user_text = entry.get().strip()

    if not user_text:
        return

    entry.delete(0, tk.END)

    _reset_initiative_after_user()

    add_message("user", user_text)
    set_status("Companion is thinking...")

    threading.Thread(
        target=process_message,
        args=(user_text,),
        daemon=True,
    ).start()


# ============================================================
# MESSAGE PROCESSING
# ============================================================

def _short_error(exc):
    code = getattr(
        exc,
        "status_code",
        None,
    )

    if code is None:
        code = getattr(
            getattr(
                exc,
                "response",
                None,
            ),
            "status_code",
            None,
        )

    return (
        f"HTTP {code}"
        if code
        else type(exc).__name__
    )


def process_message(text):
    wlog(
        "MSG",
        f"user sent {len(text)} chars",
    )

    try:
        screenshot_started = time.time()
        screenshot = take_screenshot()

        wlog(
            "SCREEN",
            (
                f"screenshot "
                f"{'ok' if screenshot else 'EMPTY/None'} "
                f"in {time.time() - screenshot_started:.2f}s"
            ),
        )

        reply = ask_companion(
            text,
            screenshot,
            initiative=False,
        )

        wlog(
            "MSG",
            (
                f"Companion replied with {len(reply)} chars; "
                "sending to chat window and voice"
            ),
        )

        if reply and not _shutting_down:
            add_message(
                "Companion",
                reply,
            )

            set_status("Companion is ready.")

            threading.Thread(
                target=speak,
                args=(reply,),
                daemon=True,
            ).start()

        else:
            set_status("Companion is ready.")

    except Exception as exc:
        wlog_exc("MSG", exc)

        add_message(
            "Companion",
            (
                "Something went wrong while processing "
                f"the request: {_short_error(exc)}"
            ),
        )

        set_status("Something went wrong.")


# ============================================================
# INITIATIVE LOOP
# ============================================================

def _cache_companion_hwnd():
    root.update_idletasks()

    state.COMPANION_HWND = (
        _user32.GetAncestor(root.winfo_id(), 2)
        if _user32 is not None
        else 0
    )


def _shutdown_companion():
    """Stop background work and the voice worker before closing the UI."""
    global _shutting_down
    _shutting_down = True
    _APP_STOP.set()
    _COMPANION_CANCEL.set()

    if initiative_manager is not None:
        initiative_manager.stop()

    stop_visual_reel()
    shutdown_voice_worker()

    try:
        root.destroy()
    except tk.TclError:
        pass


def _companion_fast_capture_loop():
    """Refresh the screenshot cache without adding frames to the visual reel."""
    while not _APP_STOP.wait(3):
        try:
            take_screenshot()
        except Exception as exc:
            wlog_change(
                "fast_capture",
                (
                    "screenshot capture failing: "
                    f"{type(exc).__name__}: {exc}"
                ),
                "SCREEN",
            )


def main():
    """Initialize persistence, construct the desktop UI, and run workers."""
    global window, root, entry, initiative_manager

    get_client()
    _init_memory_db()
    _init_shared_history()
    _init_user_preferences()
    _init_companion_self_memory()
    get_memories()

    window = CompanionWindow()
    root = window.root
    entry = window.entry

    window.add_message(
        "Companion",
        "Ready. The conversational, memory, visual-context, and voice systems are initialized.",
    )

    print("Companion is starting...")
    wlog("START", f"brain model: {MODEL}")
    wlog("START", f"OpenRouter API key: {'present' if API_TOKEN else 'MISSING'}")
    wlog(
        "START",
        (
            f"database: {DB_FILE.name} "
            f"({DB_FILE.stat().st_size if DB_FILE.exists() else 0} bytes) | "
            f"transcript entries: {len(_CHAT_HISTORY)} | "
            f"long-term memories: {len(get_memories())}"
        ),
    )
    wlog(
        "START",
        (
            f"logging: console={'on' if _WLOG_CONSOLE else 'off'} "
            f"file={_WLOG_FILE.name if _WLOG_FILE_ON else 'off'} "
            f"full-dumps={'on' if _WLOG_FULL else 'off'}"
        ),
    )

    print("Visual context system initialized.")
    print("Memory system initialized.")
    print("Voice system initialized.")
    print("Initiative system initialized.")
    print("Close the Companion window to shut it down.")

    _cache_companion_hwnd()
    window.bind_actions(send_message, _cancel_current_turn)
    root.protocol("WM_DELETE_WINDOW", _shutdown_companion)

    threading.Thread(
        target=_companion_visual_reel_loop,
        daemon=True,
    ).start()
    threading.Thread(
        target=_companion_fast_capture_loop,
        daemon=True,
    ).start()

    initiative_manager = InitiativeManager(
        add_message=add_message,
        set_status=set_status,
        ask_companion=ask_companion,
        take_screenshot=take_screenshot,
    )
    threading.Thread(
        target=initiative_manager.run,
        daemon=True,
    ).start()

    window.run()


