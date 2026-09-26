"""顶栏赛事行的格式：「2026 ATP250 成都 首轮」（2026-09-26 账号所有者去掉了「站」：「把文案里的站去掉吧」）。

账号所有者 2026-09-24：「视频顶部要写上 2026 ATP250 成都站 首轮 这样的格式，
以后其他比赛都按这个格式写」。在这之前 `topbar.line1`（赛场之上）和 `event`
（赛后开麦）是自由文本，同一个级别有五六种写法，代码只校验非空。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import reel_facts as rf  # noqa: E402


@pytest.mark.parametrize("line", [
    "2026 ATP250 成都 首轮",
    "2026 WTA1000 武汉 1/4决赛",
    "2026 ATP1000 辛辛那提 第三轮",
    "2026 美网 第一轮",               # 大满贯：没有级别和「站」，不管
    "2026 戴维斯杯资格赛 第二轮",      # 团体赛：同上
])
def test_合格式的和不归这条管的都放行(line):
    assert rf.tour_topline_problem(line) is None


@pytest.mark.parametrize("line", [
    "2026 成都公开赛 首轮",            # 胡佳那条第一版：缺级别、没「站」
    "WTA1000 辛辛那提 第一轮",         # 缺年份
    "2026 辛辛那提 WTA1000 1/8决赛",   # 顺序反了
    "2026 WTA 1000 武汉站 1/4决赛",    # 级别中间有空格
    "2026 ATP250 成都站 首轮",         # 2026-09-26 起城市后面不带「站」
])
def test_不合格式的巡回赛要拦(line):
    assert rf.tour_topline_problem(line)
    # 写了认领就放行——特例由人说清楚
    assert rf.tour_topline_problem(line, claim="这一站没有官方级别") is None


def test_自动草稿按赛事名拼出这个格式():
    assert rf.tour_topline(2026, "Chengdu Open", "首轮", "ATP") == "2026 ATP250 成都 首轮"
    assert rf.tour_topline(2026, "Cincinnati Open", "第三轮", "WTA") == "2026 WTA1000 辛辛那提 第三轮"
    # 大满贯认不出级别＋城市站 → None，调用方照旧用原来的写法
    assert rf.tour_topline(2026, "US Open", "第一轮") is None


def _specs(kind: str):
    folder = ROOT / "specs" / ("reels" if kind == "reels" else "interviews")
    for path in sorted(folder.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        slug = spec.get("slug") or path.stem
        if kind == "reels":
            if str((spec.get("cover") or {}).get("eyebrow", "")).strip() != "赛场之上":
                continue
            line = (spec.get("topbar") or {}).get("line1")
        else:
            line = spec.get("event")
        if line:
            yield slug, line, spec.get("_topbar_format_why", "")


@pytest.mark.parametrize("kind", ["reels", "interviews"])
def test_新片子的顶栏赛事行都合格式(kind):
    legacy = rf.legacy_topline(kind)
    bad = [f"{slug}: {line}" for slug, line, claim in _specs(kind)
           if slug not in legacy and rf.tour_topline_problem(line, claim)]
    assert not bad, "这些顶栏赛事行不合「2026 ATP250 成都 首轮」的格式：\n  " + "\n  ".join(bad)


@pytest.mark.parametrize("kind", ["reels", "interviews"])
def test_豁免表只许减不许加_名字要真的存在且真的还不合格式(kind):
    legacy = rf.legacy_topline(kind)
    assert legacy, "豁免表读不到——路径或键名写错了，整条判据会静静失效"
    seen = {slug: (line, claim) for slug, line, claim in _specs(kind)}
    missing = sorted(s for s in legacy if s not in seen)
    fixed = sorted(s for s in legacy
                   if s in seen and not rf.tour_topline_problem(*seen[s]))
    assert not missing, f"豁免表里有不存在的 slug（写错了就成了恒真的绿灯）：{missing}"
    assert not fixed, f"这些已经合格式了，从 data/legacy_topline_format.json 里删掉：{fixed}"


def test_赛场之上的渲染入口真的会拦(tmp_path):
    import build_match_reel as bmr
    spec = json.loads((ROOT / "specs/reels/hu-kopriva-chengdu-2026-r1.json").read_text(encoding="utf-8"))
    spec["slug"] = "new-one"  # 这一条挂在豁免表里（按「成都站」发的），换个名字才走得到闸
    spec["topbar"]["line1"] = "2026 ATP250 成都 首轮"
    spec["cover"]["topic"] = __import__("reel_facts").cover_topic(spec["topbar"]["line1"], spec["cover"])
    assert bmr._topbar_lines(spec)[0] == "2026 ATP250 成都 首轮"
    spec["topbar"]["line1"] = "2026 成都公开赛 首轮"
    with pytest.raises(bmr.ReelError, match="ATP250 成都 首轮"):
        bmr._topbar_lines(spec)


def test_赛后开麦的渲染入口真的会拦():
    import build_interview_clip as bic
    bic.check_topline_format({"slug": "new-one", "event": "2026 WTA500 华盛顿 1/4决赛"})
    bic.check_topline_format({"slug": "new-one", "event": "2026 美网 第一轮"})
    with pytest.raises(SystemExit, match="ATP250 成都 首轮"):
        bic.check_topline_format({"slug": "new-one", "event": "2026 华盛顿 WTA500 1/4 决赛"})
