"""Shared process state for the Companion application."""

import time

COMPANION_SESSION_STARTED = time.time()
COMPANION_HWND = 0
last_visual_title = ""
last_visual_process = ""
