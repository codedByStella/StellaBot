"""Foreground-window screenshot capture."""

import base64
import ctypes
import ctypes.wintypes
import io
import threading
from pathlib import Path

from PIL import ImageGrab

from companion_app import state
from companion_app.windows import _user32, _kernel32

_SCREENSHOT_LOCK = threading.Lock()

def _take_screenshot_locked():
    """
    Capture the foreground application rather than the entire desktop.

    The companion's own window is excluded. If it is foreground or
    minimized, the last valid application frame is returned.

    The capture is based on the foreground window's client area.
    """

    user32 = _user32
    kernel32 = _kernel32

    if user32 is None or kernel32 is None:
        return getattr(take_screenshot, "_last_visual_frame", None)

    hwnd = user32.GetForegroundWindow()

    if not hwnd or not user32.IsWindowVisible(hwnd):
        return getattr(
            take_screenshot,
            "_last_visual_frame",
            None,
        )

    if hwnd == state.COMPANION_HWND or user32.IsIconic(hwnd):
        return getattr(
            take_screenshot,
            "_last_visual_frame",
            None,
        )

    length = user32.GetWindowTextLengthW(hwnd)

    title_buffer = ctypes.create_unicode_buffer(
        length + 1
    )

    if length > 0:
        user32.GetWindowTextW(
            hwnd,
            title_buffer,
            length + 1,
        )

    title = title_buffer.value.strip()

    # Resolve the foreground application's process name.
    process_name = ""

    pid = ctypes.wintypes.DWORD()

    user32.GetWindowThreadProcessId(
        hwnd,
        ctypes.byref(pid),
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

                exe_buffer = ctypes.create_unicode_buffer(
                    1024
                )

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

    client_rect = ctypes.wintypes.RECT()

    if not user32.GetClientRect(
        hwnd,
        ctypes.byref(client_rect),
    ):
        return getattr(
            take_screenshot,
            "_last_visual_frame",
            None,
        )

    class POINT(ctypes.Structure):
        _fields_ = [
            ("x", ctypes.wintypes.LONG),
            ("y", ctypes.wintypes.LONG),
        ]

    user32.ClientToScreen.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.POINTER(POINT),
    ]
    user32.ClientToScreen.restype = ctypes.wintypes.BOOL

    top_left = POINT(0, 0)

    bottom_right = POINT(
        client_rect.right,
        client_rect.bottom,
    )

    if not user32.ClientToScreen(
        hwnd,
        ctypes.byref(top_left),
    ):
        return getattr(
            take_screenshot,
            "_last_visual_frame",
            None,
        )

    if not user32.ClientToScreen(
        hwnd,
        ctypes.byref(bottom_right),
    ):
        return getattr(
            take_screenshot,
            "_last_visual_frame",
            None,
        )

    left = top_left.x
    top = top_left.y
    right = bottom_right.x
    bottom = bottom_right.y

    if right <= left or bottom <= top:
        return getattr(
            take_screenshot,
            "_last_visual_frame",
            None,
        )

    try:
        image = ImageGrab.grab(
            bbox=(left, top, right, bottom),
            all_screens=True,
        )

    except Exception:
        return getattr(
            take_screenshot,
            "_last_visual_frame",
            None,
        )

    image.thumbnail((1920, 1080))

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="JPEG",
        quality=82,
        optimize=True,
    )

    data = (
        "data:image/jpeg;base64,"
        + base64.b64encode(
            buffer.getvalue()
        ).decode("ascii")
    )

    take_screenshot._last_visual_frame = data

    state.last_visual_title = title
    state.last_visual_process = process_name

    return data

def take_screenshot():
    """Capture a foreground application frame without concurrent overlap."""
    with _SCREENSHOT_LOCK:
        return _take_screenshot_locked()
