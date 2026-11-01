"""Rolling foreground-activity frame history and timeline metadata."""

import hashlib
import threading
import time
from datetime import datetime

from companion_app import state
from companion_app.logging import wlog_change
from companion_app.visual.capture import take_screenshot

VISUAL_REEL = []
VISUAL_REEL_LOCK = threading.Lock()
VISUAL_REEL_INTERVAL_SECONDS = 15
VISUAL_REEL_MAX_AGE_SECONDS = 300
VISUAL_REEL_MAX_FRAMES = 16
_VISUAL_REEL_STOP = threading.Event()

def _image_hash(data_url):
    if not data_url:
        return ""

    return hashlib.sha1(
        data_url.encode("utf-8")
    ).hexdigest()

def _record_visual_frame(
    screenshot,
    *,
    timestamp=None,
    title=None,
    process_name=None,
):
    if not screenshot:
        return

    digest = _image_hash(screenshot)

    if not digest:
        return

    if timestamp is None:
        timestamp = time.time()

    with VISUAL_REEL_LOCK:
        # Expire old frames even when the current screen is unchanged.
        cutoff = time.time() - VISUAL_REEL_MAX_AGE_SECONDS
        VISUAL_REEL[:] = [
            frame
            for frame in VISUAL_REEL
            if frame["ts"] >= cutoff
        ]

        if (
            VISUAL_REEL
            and VISUAL_REEL[-1]["hash"] == digest
        ):
            VISUAL_REEL[-1]["last_seen"] = float(timestamp)
            return

        VISUAL_REEL.append({
            "ts": float(timestamp),
            "last_seen": float(timestamp),
            "screenshot": screenshot,
            "hash": digest,
            "title": title or "",
            "process": process_name or "",
        })

        if len(VISUAL_REEL) > VISUAL_REEL_MAX_FRAMES:
            del VISUAL_REEL[
                :len(VISUAL_REEL) - VISUAL_REEL_MAX_FRAMES
            ]

def _snapshot_visual_reel():
    with VISUAL_REEL_LOCK:
        return [
            dict(frame)
            for frame in VISUAL_REEL
        ]

def _capture_visual_reel_frame():
    try:
        shot = take_screenshot()

        if not shot:
            return

        # When the companion is foreground, take_screenshot()
        # intentionally returns the last valid application frame.
        # It is still deduplicated before entering the rolling reel.

        _record_visual_frame(
            shot,
            timestamp=time.time(),
            title=state.last_visual_title,
            process_name=state.last_visual_process,
        )

    except Exception as exc:
        print(
            f"[Screen capture error] "
            f"{type(exc).__name__}: {exc}"
        )

def _visual_timeline_text():
    frames = _snapshot_visual_reel()

    if not frames:
        return "No recent screen history yet."

    now = time.time()
    lines = []

    for frame in frames:
        stamp = datetime.fromtimestamp(
            frame["ts"]
        ).strftime("%H:%M:%S")

        label = (
            frame["title"]
            or frame["process"]
            or "unknown window"
        )[:80]

        line = (
            f"- {stamp} "
            f"({int(now - frame['ts'])}s ago): "
            f"{label}"
        )

        if frame["process"]:
            line += f" [{frame['process']}]"

        held = int(
            frame.get("last_seen", frame["ts"])
            - frame["ts"]
        )

        if held >= 30:
            line += (
                f", screen stayed about the same for {held}s"
            )

        lines.append(line)

    return "\n".join(lines)

def stop_visual_reel():
    """Request an orderly exit from the visual-reel worker."""
    _VISUAL_REEL_STOP.set()


def _companion_visual_reel_loop():
    while not _VISUAL_REEL_STOP.wait(VISUAL_REEL_INTERVAL_SECONDS):

        try:
            _capture_visual_reel_frame()

        except Exception as exc:
            wlog_change(
                "reel_capture",
                (
                    "Visual reel capture failing: "
                    f"{type(exc).__name__}: {exc}"
                ),
                "SCREEN",
            )


# ============================================================
# SCREEN CAPTURE
# ============================================================

def _latest_reel_hash():
    with VISUAL_REEL_LOCK:
        return (
            VISUAL_REEL[-1]["hash"]
            if VISUAL_REEL
            else ""
        )
