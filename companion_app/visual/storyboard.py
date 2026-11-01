"""Local diagnostic storyboard rendering from the rolling visual reel."""

import base64
import io
import time
from datetime import datetime
from pathlib import Path

from companion_app import state
from companion_app.visual.reel import (
    VISUAL_REEL_MAX_FRAMES,
    _image_hash,
    _snapshot_visual_reel,
)

from companion_app.database.common import RUNTIME_DIR

BUILD_STORYBOARD_FILE = False
VISUAL_STORYBOARD_PATH = RUNTIME_DIR / "companion_visual_storyboard.jpg"

def _decode_visual_frame(data_url):
    if not data_url or "," not in data_url:
        return None

    try:
        payload = data_url.split(",", 1)[1]
        raw = base64.b64decode(payload)

        from PIL import Image

        return Image.open(
            io.BytesIO(raw)
        ).convert("RGB")

    except Exception:
        return None

def _encode_visual_image(image, quality=86):
    buffer = io.BytesIO()

    image.save(
        buffer,
        format="JPEG",
        quality=quality,
        optimize=True,
    )

    return (
        "data:image/jpeg;base64,"
        + base64.b64encode(
            buffer.getvalue()
        ).decode("ascii")
    )

def _build_visual_storyboard(
    current_screenshot=None,
    *,
    direct_message=False,
):
    """
    Build a local diagnostic storyboard from the rolling screenshot reel.

    The resulting image is saved locally and is not attached to the
    text-only model request.

    Normal initiative:
        Equal-size chronological recent history only.

    Direct user message:
        One temporary large current-view panel plus equal-size history.

    The local rolling reel is never cleared here.
    """

    frames = _snapshot_visual_reel()

    if current_screenshot:
        current_hash = _image_hash(current_screenshot)

        # Do not mutate the rolling reel just because this is the
        # priority view for the current turn.
        if (
            not frames
            or frames[-1]["hash"] != current_hash
        ):
            priority_frame = {
                "ts": time.time(),
                "screenshot": current_screenshot,
                "hash": current_hash,
                "title": state.last_visual_title,
                "process": state.last_visual_process,
            }

        else:
            priority_frame = frames[-1]

    else:
        priority_frame = frames[-1] if frames else None

    if not priority_frame and not frames:
        return None

    # Current image is the latest valid visual application frame.
    if priority_frame:
        current_img = _decode_visual_frame(
            priority_frame["screenshot"]
        )

    else:
        current_img = None

    if current_img is None:
        return None

    # Historical thumbnails exclude the current hash so the
    # storyboard does not waste space duplicating the same frame.
    current_hash = priority_frame["hash"]

    history = [
        frame
        for frame in frames
        if frame["hash"] != current_hash
    ]

    # Four columns keeps 16 frames at 4x4 and gives every frame
    # a predictable footprint.

    cols = 4
    thumb_w = 384
    thumb_h = thumb_w * 9 // 16

    gap = 10
    label_h = 24
    header_h = 40

    if direct_message:
        canvas_w = (
            cols * thumb_w
            + (cols - 1) * gap
        )

        current_h = canvas_w * 9 // 16

        history_rows = (
            (len(history) + cols - 1) // cols
        )

        history_h = (
            history_rows * (thumb_h + label_h + gap)
            if history_rows
            else 0
        )

        canvas_h = (
            header_h
            + current_h
            + (gap + history_h if history_h else 0)
        )

        from PIL import Image, ImageDraw, ImageFont

        canvas = Image.new(
            "RGB",
            (canvas_w, max(canvas_h, 600)),
            "#101010",
        )

        draw = ImageDraw.Draw(canvas)

        try:
            font = ImageFont.truetype(
                "arial.ttf",
                16
            )

            small = ImageFont.truetype(
                "arial.ttf",
                12
            )

        except Exception:
            font = ImageFont.load_default()
            small = ImageFont.load_default()

        draw.rectangle(
            (0, 0, canvas_w, header_h),
            fill="#1d1d1d",
        )

        draw.text(
            (10, 10),
            "COMPANION SHORT-TERM VISUAL CONTEXT",
            fill="white",
            font=font,
        )

        y = header_h

        current_box = current_img.copy()

        current_box.thumbnail(
            (canvas_w, current_h),
            Image.Resampling.LANCZOS,
        )

        x = (canvas_w - current_box.width) // 2

        y_off = (
            y
            + (current_h - current_box.height) // 2
        )

        canvas.paste(
            current_box,
            (x, y_off)
        )

        draw.rectangle(
            (0, y, canvas_w - 1, y + 28),
            fill="#090909",
        )

        draw.text(
            (10, y + 7),
            "CURRENT VIEW",
            fill="white",
            font=small,
        )


        y += current_h
        y += gap

        for index, frame in enumerate(history[-(cols * 4):]):
            image = _decode_visual_frame(frame["screenshot"])

            if image is None:
                continue

            image.thumbnail(
                (thumb_w, thumb_h),
                Image.Resampling.LANCZOS,
            )

            cell = Image.new(
                "RGB",
                (thumb_w, thumb_h),
                "#000000",
            )

            cell.paste(
                image,
                (
                    (thumb_w - image.width) // 2,
                    (thumb_h - image.height) // 2,
                ),
            )

            row, col = divmod(index, cols)
            x = col * (thumb_w + gap)
            yy = y + row * (thumb_h + label_h + gap)

            canvas.paste(cell, (x, yy))

            draw.rectangle(
                (
                    x,
                    yy + thumb_h,
                    x + thumb_w,
                    yy + thumb_h + label_h,
                ),
                fill="#202020",
            )

            draw.text(
                (x + 6, yy + thumb_h + 5),
                datetime.fromtimestamp(
                    frame["ts"]
                ).strftime("%H:%M:%S"),
                fill="white",
                font=small,
            )

    else:
        # Initiative / passive observation:
        # Every frame receives the same dimensions.
        selected = history + (
            [priority_frame] if priority_frame else []
        )

        selected.sort(
            key=lambda frame: frame["ts"]
        )

        selected = selected[-VISUAL_REEL_MAX_FRAMES:]

        canvas_w = (
            cols * thumb_w
            + (cols - 1) * gap
        )

        rows = (
            (len(selected) + cols - 1) // cols
        )

        canvas_h = (
            header_h
            + rows * (thumb_h + label_h + gap)
        )

        from PIL import Image, ImageDraw, ImageFont

        canvas = Image.new(
            "RGB",
            (canvas_w, max(canvas_h, header_h)),
            "#101010",
        )

        draw = ImageDraw.Draw(canvas)

        try:
            font = ImageFont.truetype(
                "arial.ttf",
                16,
            )

            small = ImageFont.truetype(
                "arial.ttf",
                12,
            )

        except Exception:
            font = ImageFont.load_default()
            small = ImageFont.load_default()

        draw.rectangle(
            (0, 0, canvas_w, header_h),
            fill="#1d1d1d",
        )

        draw.text(
            (10, 10),
            "COMPANION SHORT-TERM VISUAL CONTEXT - CHRONOLOGICAL",
            fill="white",
            font=font,
        )

        for index, frame in enumerate(selected):
            image = _decode_visual_frame(
                frame["screenshot"]
            )

            if image is None:
                continue

            image.thumbnail(
                (thumb_w, thumb_h),
                Image.Resampling.LANCZOS,
            )

            cell = Image.new(
                "RGB",
                (thumb_w, thumb_h),
                "#000000",
            )

            cell.paste(
                image,
                (
                    (thumb_w - image.width) // 2,
                    (thumb_h - image.height) // 2,
                ),
            )

            row, col = divmod(index, cols)

            x = col * (thumb_w + gap)

            y = (
                header_h
                + row * (thumb_h + label_h + gap)
            )

            canvas.paste(cell, (x, y))

            draw.rectangle(
                (
                    x,
                    y + thumb_h,
                    x + thumb_w,
                    y + thumb_h + label_h,
                ),
                fill="#202020",
            )

            timestamp = datetime.fromtimestamp(
                frame["ts"]
            ).strftime("%H:%M:%S")

            draw.text(
                (x + 6, y + thumb_h + 5),
                timestamp,
                fill="white",
                font=small,
            )

    canvas.save(
        VISUAL_STORYBOARD_PATH,
        format="JPEG",
        quality=86,
        optimize=True,
    )

    print(
        f"[Visual storyboard] "
        f"{len(frames)} local frames -> "
        f"{VISUAL_STORYBOARD_PATH.name}"
    )

    return _encode_visual_image(
        canvas,
        quality=86,
    )
