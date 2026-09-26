"""封面副标题（`cover.topic`）的格式：「ATP250 杭州 第二轮 · 梅德韦杰夫 VS 鲁瓦耶」（同日又去掉了「站」）。

账号所有者 2026-09-26：「以后所有 ATP 或者 WTA 的比赛的赛场之上视频的左上角，封面
左上角的副标题都是用 ATP500 或者是 WTA500 类似的这种开头，然后再说地名，然后再说
第几轮。然后后面，点开始的是对战双方的名字，VS」。看过样例后定了，比利·简·金杯
选的是全称写法。规则是**顶栏赛事行去掉年份 ＋「 · 」＋ 两个名字用「 VS 」连**。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import reel_facts as rf  # noqa: E402


def _spec(line1, topic, names=("梅德韦杰夫", "鲁瓦耶"), **extra):
    return {"slug": "x", "topbar": {"line1": line1, "line2": "…"},
            "cover": {"eyebrow": "赛场之上", "topic": topic,
                      "matchup": [{"name": n} for n in names]}, **extra}


def test_按顶栏去年份再接两个名字拼():
    assert rf.cover_topic("2026 ATP250 杭州 第二轮",
                          {"matchup": [{"name": "梅德韦杰夫"}, {"name": "鲁瓦耶"}]}) \
        == "ATP250 杭州 第二轮 · 梅德韦杰夫 VS 鲁瓦耶"
    # 没有级别＋站的赛事，同一条规则：账号所有者选的是全称写法
    assert rf.cover_topic("2026 比利·简·金杯 半决赛",
                          {"versus": {"names": ["斯维托丽娜", "保利尼"]}}) \
        == "比利·简·金杯 半决赛 · 斯维托丽娜 VS 保利尼"
    # 缺名字就拼不出，不管
    assert rf.cover_topic("2026 ATP250 杭州 第二轮", {"matchup": [{"name": "A"}]}) is None


def test_合格式的放行_不合的拦_认领了放行():
    ok = _spec("2026 ATP250 杭州 第二轮", "ATP250 杭州 第二轮 · 梅德韦杰夫 VS 鲁瓦耶")
    assert rf.cover_topic_problem(ok) is None
    for bad in ("杭州公开赛第二轮 · 梅德韦杰夫挺进8强",           # 老写法
                "ATP250 杭州 第二轮 · 梅德韦杰夫 vs 鲁瓦耶",     # vs 小写
                "2026 ATP250 杭州 第二轮 · 梅德韦杰夫 VS 鲁瓦耶",  # 带了年份
                "ATP250 杭州 第二轮 · 鲁瓦耶 VS 梅德韦杰夫"):     # 名字顺序反了
        assert rf.cover_topic_problem(_spec("2026 ATP250 杭州 第二轮", bad)), bad
    claimed = _spec("2026 ATP250 杭州 第二轮", "别的写法", _topic_format_why="特例")
    assert rf.cover_topic_problem(claimed) is None


def _reel_specs():
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if str((spec.get("cover") or {}).get("eyebrow", "")).strip() == "赛场之上":
            yield spec.get("slug") or path.stem, spec


def test_新片子的封面副标题都合格式():
    legacy = rf.legacy_cover_topic()
    bad = [f"{slug}: {rf.cover_topic_problem(spec).splitlines()[0]}"
           for slug, spec in _reel_specs()
           if slug not in legacy and rf.cover_topic_problem(spec)]
    assert not bad, "\n  ".join(["这些封面副标题不合格式："] + bad)


def test_豁免表只许减不许加_名字要真的存在且真的还不合格式():
    legacy = rf.legacy_cover_topic()
    assert legacy, "豁免表读不到——路径或键名写错了，整条判据会静静失效"
    seen = dict(_reel_specs())
    missing = sorted(s for s in legacy if s not in seen)
    assert not missing, f"豁免表里的 slug 不存在：{missing}"
    fixed = sorted(s for s in legacy if rf.cover_topic_problem(seen[s]) is None)
    assert not fixed, f"这些已经合格式了，从豁免表里删掉：{fixed}"
    # 只许减不许加：定格式那天是 232 条
    assert len(legacy) <= 232


def test_渲染入口在dry_run就拦():
    import build_match_reel as reel
    spec = json.loads((ROOT / "specs" / "reels" / "medvedev-royer-hangzhou-2026-r2.json")
                      .read_text(encoding="utf-8"))
    spec["slug"] = "not-in-legacy"
    spec["topbar"]["line1"] = "2026 ATP250 杭州 第二轮"  # 这一条是按「杭州站」发的，顶栏也挂豁免
    spec["cover"]["topic"] = "杭州公开赛第二轮 · 梅德韦杰夫挺进8强"
    try:
        reel._topbar_lines(spec)
    except reel.ReelError as exc:
        assert "封面副标题" in str(exc)
    else:
        raise AssertionError("不合格式的副标题在 _topbar_lines 没被拦下")
    spec["cover"]["topic"] = "ATP250 杭州 第二轮 · 梅德韦杰夫 VS 鲁瓦耶"
    reel._topbar_lines(spec)
