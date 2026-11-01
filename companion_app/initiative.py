"""Autonomous initiative scheduling and idle detection."""

import ctypes
import ctypes.wintypes
import random
import threading
import time

from companion_app.logging import (
    reset_wlog_changes,
    wlog,
    wlog_change,
    wlog_exc,
)
from companion_app.model import _COMPANION_CANCEL, CompanionCancelled
from companion_app.vision import _latest_reel_hash
from companion_app.voice import speak
from companion_app.windows import _user32, _kernel32

INITIATIVE_MAX_UNANSWERED = 2
INITIATIVE_BACKOFF_CAP = 6
INITIATIVE_VISUAL_SETTLE_SECONDS = 8
INITIATIVE_CHECK_SECONDS = 15
INITIATIVE_MIN_IDLE_SECONDS = 120
INITIATIVE_MAX_IDLE_SECONDS = 210
INITIATIVE_POST_SPEAK_MIN_SECONDS = 90
INITIATIVE_POST_SPEAK_MAX_SECONDS = 180

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


def get_idle_seconds():
    if _user32 is None or _kernel32 is None:
        return 0.0

    info = LASTINPUTINFO()

    info.cbSize = ctypes.sizeof(
        LASTINPUTINFO
    )

    get_last_input_info = _user32.GetLastInputInfo
    get_last_input_info.argtypes = [
        ctypes.POINTER(LASTINPUTINFO),
    ]
    get_last_input_info.restype = ctypes.wintypes.BOOL

    if not get_last_input_info(ctypes.byref(info)):
        return 0.0

    get_tick_count = _kernel32.GetTickCount
    get_tick_count.restype = ctypes.wintypes.DWORD
    tick_count = get_tick_count()

    elapsed_ms = (
        int(tick_count) - int(info.dwTime)
    ) & 0xFFFFFFFF

    return elapsed_ms / 1000.0


class InitiativeManager:
    """Owns autonomous timing state and coordinates background initiative."""

    def __init__(self, add_message, set_status, ask_companion, take_screenshot):
        self.add_message = add_message
        self.set_status = set_status
        self.ask_companion = ask_companion
        self.take_screenshot = take_screenshot

        self.next_initiative_at = (
            time.time()
            + random.uniform(
                INITIATIVE_MIN_IDLE_SECONDS,
                INITIATIVE_MAX_IDLE_SECONDS,
            )
        )
        self.lock = threading.Lock()
        self.running = False
        self.unanswered = 0
        self.checks = 0
        self.last_visual_hash = ""
        self.visual_changed_at = 0.0
        self.last_spoken_hash = ""
        self.stop_event = threading.Event()

    def stop(self):
        """Request an orderly exit from the initiative polling loop."""
        self.stop_event.set()

    def reset_after_user(self):
        self.unanswered = 0
        self.checks = 0
        self.last_spoken_hash = ""
        self.next_initiative_at = (
            time.time()
            + random.uniform(
                INITIATIVE_MIN_IDLE_SECONDS,
                INITIATIVE_MAX_IDLE_SECONDS,
            )
        )

    def schedule_next(self):
        """Increase the delay between consecutive autonomous checks."""
        factor = min(
            INITIATIVE_BACKOFF_CAP,
            1 + self.checks,
        )
        self.next_initiative_at = (
            time.time()
            + random.uniform(
                INITIATIVE_POST_SPEAK_MIN_SECONDS,
                INITIATIVE_POST_SPEAK_MAX_SECONDS,
            ) * factor
        )

    def run(self):
        """Run the autonomous initiative polling loop."""
        while not self.stop_event.wait(INITIATIVE_CHECK_SECONDS):
    
            now = time.time()
    
            if now < self.next_initiative_at:
                wlog_change(
                    "init_skip",
                    "waiting for the next initiative window",
                )
                continue
    
            # ----------------------------------------------------
            # The user is active again.
            # ----------------------------------------------------
    
            if (
                get_idle_seconds()
                < INITIATIVE_MIN_IDLE_SECONDS
            ):
                wlog_change(
                    "init_skip",
                    (
                        "The user is active "
                        "(idle time below threshold); "
                        "initiative counters reset"
                    ),
                )
    
                self.reset_after_user()
                continue
    
            # ----------------------------------------------------
            # Stop after the unanswered-message limit is reached.
            # ----------------------------------------------------
    
            if (
                self.unanswered
                >= INITIATIVE_MAX_UNANSWERED
            ):
                wlog_change(
                    "init_skip",
                    (
                        "muted: Companion has reached the "
                        "unanswered autonomous-message limit"
                    ),
                )
                continue
    
            # ----------------------------------------------------
            # Prevent overlapping model requests.
            # ----------------------------------------------------
    
            if self.running:
                continue
    
            with self.lock:
                if self.running:
                    continue
    
                self.running = True
    
            try:
                reel_hash = _latest_reel_hash()
    
                # ------------------------------------------------
                # Track visual changes separately from initiative
                # checks. A changing screen must settle before it
                # can trigger a model request.
                # ------------------------------------------------
    
                if (
                    reel_hash
                    and reel_hash != self.last_visual_hash
                ):
                    self.visual_changed_at = now
                    self.last_visual_hash = reel_hash
    
                # ------------------------------------------------
                # No visual state has been captured yet.
                # ------------------------------------------------
    
                if not reel_hash:
                    wlog_change(
                        "init_skip",
                        "no visual state captured yet",
                    )
    
                    self.schedule_next()
                    continue
    
                # ------------------------------------------------
                # Wait for the current visual state to settle.
                # ------------------------------------------------
    
                if (
                    now - self.visual_changed_at
                    < INITIATIVE_VISUAL_SETTLE_SECONDS
                ):
                    wlog_change(
                        "init_skip",
                        "screen changed recently; waiting for it to settle",
                    )
    
                    self.schedule_next()
                    continue
    
                # ------------------------------------------------
                # Do not repeatedly initiate conversation about
                # an unchanged visual state.
                # ------------------------------------------------
    
                if (
                    reel_hash
                    == self.last_spoken_hash
                ):
                    wlog_change(
                        "init_skip",
                        (
                            "already spoke about this exact screen "
                            "state; staying quiet"
                        ),
                    )
    
                    self.checks += 1
                    self.schedule_next()
                    continue
    
                wlog(
                    "INITIATIVE",
                    (
                        "screen state is new and settled; "
                        "asking the model whether to speak"
                    ),
                )
    
                self.set_status(
                    "Checking whether there's something worth mentioning..."
                )
    
                screenshot = self.take_screenshot()
    
                self.checks += 1
    
                reply = self.ask_companion(
                    "",
                    screenshot,
                    initiative=True,
                )
    
                if self.stop_event.is_set():
                    break

                reply = str(
                    reply or ""
                ).strip()
    
                reset_wlog_changes()
    
                if (
                    reply
                    and "[QUIET]" not in reply.upper()
                    and len(reply) >= 2
                ):
                    wlog(
                        "INITIATIVE",
                        (
                            (
                                "Companion produced an autonomous reply "
                                f"({len(reply)} chars)"
                            )
                        ),
                    )
    
                else:
                    wlog(
                        "INITIATIVE",
                        "Companion stayed quiet (reply was [QUIET] or empty)",
                    )
    
                # ------------------------------------------------
                # [QUIET] does not count as an unanswered message.
                # ------------------------------------------------
    
                if (
                    reply
                    and "[QUIET]" not in reply.upper()
                    and len(reply) >= 2
                ):
                    self.add_message(
                        "Companion",
                        reply,
                    )
    
                    self.set_status(
                        "Companion has something to share."
                    )
    
                    threading.Thread(
                        target=speak,
                        args=(reply,),
                        daemon=True,
                    ).start()
    
                    self.unanswered += 1
    
                    wlog(
                        "INITIATIVE",
                        (
                            "unanswered autonomous messages: "
                            f"{self.unanswered}/"
                            f"{INITIATIVE_MAX_UNANSWERED}"
                        ),
                    )
    
                    # Mark the visual state only after an actual
                    # autonomous message has been produced.
                    self.last_spoken_hash = reel_hash
    
                else:
                    self.set_status("Companion is ready.")
    
                self.schedule_next()
    
            except CompanionCancelled:
                _COMPANION_CANCEL.clear()
    
                wlog(
                    "INITIATIVE",
                    "autonomous request cancelled",
                )
    
                self.schedule_next()
    
                self.set_status("Companion is ready.")
    
            except Exception as exc:
                wlog_exc(
                    "INITIATIVE",
                    exc,
                )
    
                print(
                    "[Initiative error] "
                    f"{type(exc).__name__}: {exc}"
                )
    
                self.checks += 1
    
                self.schedule_next()
    
                self.set_status("Companion is ready.")
    
            finally:
                self.running = False
    
    
    # ============================================================
