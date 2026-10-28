"""比分字卡必须照抄来源赛果（赢家在前），屏幕比分由闸按 people 顺序翻转比对。

账号所有者 2026-10-28：「整体 review 下这个视频里的比分字卡，然后做一个全局规则
保证之后比分字卡不会错」。来路是 wawrinka-career-story-2026 的 2013 澳网字卡：
来源「德约 d. 瓦林卡 1-6 7-5 6-4 6-7(5) 12-10」，手翻成瓦林卡视角时第四盘写成了
6-7(5)（应为 7-6(5)），推出去才被读者指出。
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import render_story_info_band as band  # noqa: E402

#: 闸落地那天表里的数目。只许减不许加。
LEGACY_CEILING = 29

AO13 = {"winner": "德约科维奇", "score": "1-6 7-5 6-4 6-7(5) 12-10",
        "source": "https://www.aljazeera.com/sport/tennis/2013/01/2013120152121386422.html"}


def _label(score: str, people: str = "瓦林卡 vs 德约科维奇", result: dict | None = AO13) -> dict:
    label = {"topic": "决胜盘10比12", "date": "2013.01.20", "place": "澳网 第四轮",
             "people": people, "score": score}
    if result is not None:
        label["result"] = result
    return label


def _specs():
    for path in sorted(glob.glob(str(ROOT / "specs" / "reels" / "*.json"))):
        try:
            yield json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue


def test_翻转比分时抢七小分跟着输的那一盘走():
    assert band.flip_score("1-6 7-5 6-4 6-7(5) 12-10") == "6-1 5-7 4-6 7-6(5) 10-12"
    assert band.flip_score("7-6(4) 7-6(3) 6-0") == "6-7(4) 6-7(3) 0-6"
    assert band.flip_score("6-4 [10-7]") == "4-6 [7-10]"


def test_2013澳网那张字卡写反的第四盘会被拦下():
    bad = band.label_result_problem(_label("6-1 5-7 4-6 6-7(5) 10-12"))
    assert bad and "7-6(5)" in bad
    assert band.label_result_problem(_label("6-1 5-7 4-6 7-6(5) 10-12")) is None


def test_赢家在左边时照抄来源不翻():
    result = {"winner": "德约科维奇", "score": AO13["score"], "source": AO13["source"]}
    assert band.label_result_problem(
        _label("1-6 7-5 6-4 6-7(5) 12-10", people="德约科维奇 vs 瓦林卡", result=result)) is None


def test_带比分的字卡不写来源赛果就红():
    assert "result" in band.label_result_problem(_label("6-1 5-7 4-6 7-6(5) 10-12", result=None))


def test_来源赛果必须是赢家视角且赢家在people里():
    flipped = dict(AO13, score="6-1 5-7 4-6 7-6(5) 10-12")
    assert "赢家视角" in band.label_result_problem(_label("6-1 5-7 4-6 7-6(5) 10-12", result=flipped))
    stranger = dict(AO13, winner="纳达尔")
    assert "people" in band.label_result_problem(_label("6-1 5-7 4-6 7-6(5) 10-12", result=stranger))
    no_link = dict(AO13, source="Al Jazeera")
    assert "来源链接" in band.label_result_problem(_label("6-1 5-7 4-6 7-6(5) 10-12", result=no_link))


def test_抢七小分只跟7比6那一盘():
    odd = dict(AO13, score="1-6 7-5(3) 6-4 6-7(5) 12-10")
    assert "抢七小分" in band.label_result_problem(_label("6-1 5-7(3) 4-6 7-6(5) 10-12", result=odd))


def test_说明性的字和没有比分的字卡不受这道闸管():
    assert band.label_result_problem({"topic": "x", "people": "a", "event": "告别仪式"}) is None
    assert band.label_result_problem(_label("决胜盘 1-5 赛点", result=None)) is None


def test_所有不在豁免表的片子比分字卡都对得上来源():
    legacy = band.legacy_label_result_slugs()
    bad = {spec.get("slug"): problems for spec in _specs()
           if spec.get("slug") not in legacy
           and (problems := band.story_label_result_problems(spec))}
    assert not bad, bad


def test_比分字卡豁免表只许减_表里每一条确实还缺():
    legacy = band.legacy_label_result_slugs()
    assert len(legacy) <= LEGACY_CEILING, "豁免表只许减不许加：新片要写 result"
    specs = {spec.get("slug"): spec for spec in _specs()}
    stale = [slug for slug in legacy
             if slug in specs and not band.story_label_result_problems(specs[slug], honor_legacy=False)]
    assert not stale, f"这些已经补齐 result，从 data/legacy_label_result.json 删掉：{stale}"
