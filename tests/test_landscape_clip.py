"""横屏双语原片（`tools/build_landscape_clip.py`）的机械判据。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("tools").resolve()))
import build_landscape_clip as lc  # noqa: E402


def _spec(lines):
    return {"slug": "t", "url": "https://www.youtube.com/watch?v=x", "start": 10.0,
            "end": 30.0, "lines": lines}


def test_不裁切_只等比缩放补边():
    f = lc._fit_filter()
    assert "force_original_aspect_ratio=decrease" in f and "pad=1920:1080" in f
    assert "crop" not in f, "这条路存在的理由就是不裁画面"


def test_字幕两行都要有_不许重叠_不许出窗():
    ok = [{"start": 11, "end": 13, "en": "Hello there.", "zh": "你好。"}]
    assert lc.line_problems(_spec(ok)) == []
    assert any("中英两行" in p for p in lc.line_problems(
        _spec([{"start": 11, "end": 13, "en": "Hello.", "zh": ""}])))
    assert any("重叠" in p for p in lc.line_problems(_spec(ok + [
        {"start": 12, "end": 14, "en": "Again.", "zh": "再来。"}])))
    assert any("窗口" in p for p in lc.line_problems(
        _spec([{"start": 29, "end": 31, "en": "Late.", "zh": "晚了。"}])))


def test_超宽的行会被拦下():
    long_en = "welcome " * 40
    probs = lc.line_problems(_spec([{"start": 11, "end": 13, "en": long_en, "zh": "欢迎"}]))
    assert any("px" in p for p in probs)


def test_ASS_字体字号_英文在上中文在下():
    ass = lc.build_ass(_spec([{"start": 11, "end": 13, "en": "Hi.", "zh": "你好"}]))
    # 账号所有者：「中文在下吧」「中文字体不好看」（第一版是宋体在上）
    assert "Style: ZH,Noto Sans CJK SC,36," in ass
    assert "Style: EN,Noto Sans,31," in ass
    zh_mv = int(ass.split("Style: ZH,")[1].split("\n")[0].split(",")[-2])
    en_mv = int(ass.split("Style: EN,")[1].split("\n")[0].split(",")[-2])
    assert zh_mv < en_mv, "MarginV 越小越贴底：中文要在英文下面"
    # 时间轴相对剪辑起点
    assert "Dialogue: 0,0:00:01.00,0:00:03.00,ZH" in ass


@pytest.mark.parametrize("path", sorted(Path("specs/landscape").glob("*.json")))
def test_仓库里的横屏spec都过得了闸(path):
    spec = lc.load_spec(path)
    if spec.get("lines"):
        assert lc.line_problems(spec) == []
    else:  # 还在取字幕那一步：窗口是占位，lines 空着
        assert json.loads(path.read_text(encoding="utf-8"))["_window_why"]
