"""「赛场之上」旁白时长的轻量单一事实源。"""

from __future__ import annotations

SPEECH_PER_CHAR = 0.166
SPEECH_PER_PUNCT = 0.32
SPEECH_TAIL = 0.45
# Keep these as strings: the renderer's calibration tests concatenate them.
SPEECH_PUNCT = "，。！？、；：—…,.!?;:"
SPEECH_QUIET = "“”‘’\"'（）()《》「」 \t\n"


def speech_seconds(text: str) -> float:
    """按已发布成片拟合系数估算一段中文旁白的秒数。"""
    body = "".join(char for char in text if char not in SPEECH_QUIET)
    punct = sum(1 for char in body if char in SPEECH_PUNCT)
    chars = len(body) - punct
    if not chars and not punct:
        return 0.0
    return chars * SPEECH_PER_CHAR + punct * SPEECH_PER_PUNCT + SPEECH_TAIL
