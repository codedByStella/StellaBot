"""Shared compiled patterns used by response processing and diagnostics."""

import re

LEAK_MARKERS = re.compile(
    r"(?i)("
    r"self-correction|"
    r"internal thought|"
    r"internal thoughts|"
    r"thought process|"
    r"internal assessment|"
    r"final output generation|"
    r"response generation|"
    r"revised response|"
    r"drafting the message|"
    r"self-assessment|"
    r"chosen response|"
    r"decision before responding|"
    r"reasoning before responding|"
    r"based on the image provided"
    r")"
)
