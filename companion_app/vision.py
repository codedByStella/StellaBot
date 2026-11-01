"""Public visual-context service facade."""

from companion_app.visual.capture import _take_screenshot_locked, take_screenshot
from companion_app.visual.reel import (
    VISUAL_REEL_INTERVAL_SECONDS,
    VISUAL_REEL_MAX_AGE_SECONDS,
    VISUAL_REEL_MAX_FRAMES,
    _capture_visual_reel_frame,
    _companion_visual_reel_loop,
    _image_hash,
    _latest_reel_hash,
    _record_visual_frame,
    _snapshot_visual_reel,
    stop_visual_reel,
    _visual_timeline_text,
)
from companion_app.visual.storyboard import (
    BUILD_STORYBOARD_FILE,
    VISUAL_STORYBOARD_PATH,
    _build_visual_storyboard,
    _decode_visual_frame,
    _encode_visual_image,
)
