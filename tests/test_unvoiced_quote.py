"""没有我们配音的视频段，关键解说要留成原声，配中英双语字幕。

账号所有者 2026-09-26：「以后务必要保证冷开场的解说有中英文字幕」，紧接着
「没有我们配音的地方，如果有关键解说也务必要有中英文字幕」。
判据在 `build_match_reel.unvoiced_quote_problem`。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_match_reel as reel  # noqa: E402

NONE = frozenset()


def _spec(first: dict, middle: dict | None = None) -> dict:
    return {"slug": "x", "cover": {"eyebrow": "赛场之上"},
            "segments": [{"source": "ttv", "start": 680.0, "end": 690.0, **first},
                         {"source": "ttv", "start": 10.0, "end": 20.0, "narration": "坐标。"},
                         {"source": "ttv", "start": 30.0, "end": 36.0,
                          **(middle if middle is not None else {"narration": "正文。"})}]}


OK = "He's done it!\n他做到了！"


def test_冷开场没有原声字幕就拦():
    assert "冷开场" in reel.unvoiced_quote_problem(_spec({}), legacy=NONE)


def test_正文里没配音的段也要有():
    problem = reel.unvoiced_quote_problem(_spec({"quote": OK}, {}), legacy=NONE)
    assert problem and "第 3 段" in problem


@pytest.mark.parametrize("quote", [
    "He's done it!",                                   # 只有原文
    "他做到了！",                                        # 只有中文
    [{"at": 1.0, "text": OK}, {"at": 4.0, "text": "What a match"}],
])
def test_不是中英双语就拦(quote):
    assert reel.unvoiced_quote_problem(_spec({"quote": quote}), legacy=NONE)


@pytest.mark.parametrize("quote", [
    OK,
    [{"at": 1.0, "text": OK}, {"at": 4.0, "text": "7-6, 6-4\n七比六，六比四"}],
])
def test_中英双语放行(quote):
    assert reel.unvoiced_quote_problem(
        _spec({"quote": quote}, {"quote": quote}), legacy=NONE) is None


def test_认领和不管的情形():
    skip = {"_quote_skip_why": "这几秒只有现场声"}
    assert reel.unvoiced_quote_problem(_spec(skip, skip), legacy=NONE) is None
    # 配了旁白的段、静图段不管
    assert reel.unvoiced_quote_problem(
        _spec({"narration": "坐标。"}, {"image": "a.jpg"}), legacy=NONE) is None
    # 网球有故事的剪辑片同一条
    story = _spec({})
    story["cover"]["eyebrow"] = "网球有故事"
    assert reel.unvoiced_quote_problem(story, legacy=NONE)
    # 豁免表里的放行
    assert reel.unvoiced_quote_problem(_spec({}), legacy=frozenset({"x"})) is None


def _specs():
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        yield str(spec.get("slug") or path.stem), spec


def test_新片子没配音的段都有双语原声字幕():
    bad = [f"{slug}: {reel.unvoiced_quote_problem(spec).splitlines()[1]}"
           for slug, spec in _specs() if reel.unvoiced_quote_problem(spec)]
    assert not bad, "\n  ".join(["没配音的段缺中英双语原声字幕："] + bad)


def test_豁免表只许减不许加():
    legacy = reel.legacy_unvoiced_quote()
    assert legacy, "豁免表读不到——路径或键名写错了，整条判据会静静失效"
    seen = dict(_specs())
    missing = sorted(s for s in legacy if s not in seen)
    assert not missing, f"豁免表里的 slug 不存在：{missing}"
    fixed = sorted(s for s in legacy if reel.unvoiced_quote_problem(seen[s], legacy=NONE) is None)
    assert not fixed, f"这些已经合格了，从豁免表里删掉：{fixed}"
    # 定规矩那天（2026-09-26）量出来 223 条
    assert len(legacy) <= 223


def test_渲染入口在dry_run就拦():
    spec = json.loads((ROOT / "specs" / "reels" / "wong-vallejo-hangzhou-2026-r2.json")
                      .read_text(encoding="utf-8"))
    spec["slug"] = "not-in-legacy"
    with pytest.raises(reel.ReelError, match="中英双语字幕"):
        reel.validate_spec(spec)
    spec["segments"][0]["quote"] = [{"at": 3.0, "text": "What a way to finish!\n这样收尾太漂亮了"}]
    try:
        reel.validate_spec(spec)
    except reel.ReelError as exc:          # 别的闸（slug 改了）可以红，但不能再是这一条
        assert "中英双语字幕" not in str(exc), str(exc)
