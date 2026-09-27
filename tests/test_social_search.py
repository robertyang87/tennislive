"""当事人声明类「网球有故事」要写 `_social_search`：X 和 Instagram 各查了什么。

来路：`sinner-beijing-withdrawal-2026` 第一版只在官网找、拿旁白转述了他的话，而他本人
44 秒的退赛视频一直挂在 X 上；推出去之后账号所有者说「多去找找 X 和 Instagram」，
重推一次（97ebe27a）。CLAUDE.md 2026-09-25 那节把它写成了规矩，没有闸。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import reel_facts as rf  # noqa: E402


def _story(slug="x-story", summary="辛纳因膝伤退出中网", hook="温网捧杯之后\n他再没打过一场",
           topic="辛纳退出中网 · 他的膝盖怎么了", **extra):
    return {"slug": slug, "cover": {"eyebrow": "网球有故事", "hook": hook, "topic": topic},
            "push": {"summary": summary}, **extra}


def _story_specs():
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if str((spec.get("cover") or {}).get("eyebrow", "")).strip() == "网球有故事":
            yield spec.get("slug") or path.stem, spec


def test_声明类选题按标题层认_逆转和回归不算():
    assert rf.statement_topic(_story()) in {"伤", "退出"}
    assert rf.statement_topic(_story(summary="普罗佐罗娃被强制退赛", hook="a", topic="b")) == "退赛"
    assert rf.statement_topic(_story(summary="谢淑薇詹皓晴握手风波", hook="两位台将隔空开吵",
                                     topic="c")) == "隔空"
    # slug 那一层：英文词要整段（-withdrawal-），不许半截命中
    assert rf.statement_topic(_story(slug="x-withdrawal-2026", summary="a", hook="b",
                                     topic="c")) == "withdrawal"
    # ⚠️ 故意不收的：场上逆转、重返决赛——收了就是误伤（comeback-five-love-down / tiafoe-story）
    for slug, summary, hook in (
            ("comeback-five-love-down", "零比五落后也能赢回来", "决胜盘零比五\n他们都赢回来了"),
            ("tiafoe-story", "两年后，重回决赛", "两年前，输给辛纳\n今天，他回来了"),
            ("djokovic-beijing-return", "德约时隔11年回北京", "六次来，六次捧杯"),
            ("x", "伤心的夜晚", "b")):
        assert rf.statement_topic(_story(slug=slug, summary=summary, hook=hook, topic="t")) \
            is None, slug
    # 只管「网球有故事」：赛场之上的「对手退赛」不是当事人声明类选题
    match = _story()
    match["cover"]["eyebrow"] = "赛场之上"
    assert rf.statement_topic(match) is None


def test_没写或只写一半要红_两个都点名放行_认领放行():
    assert "没有 `_social_search`" in rf.social_search_problem(_story())
    only_x = rf.social_search_problem(_story(_social_search={"x": "@janniksin 有视频"}))
    assert only_x and "Instagram" in only_x and "没点到" in only_x
    only_word = rf.social_search_problem(_story(_social_search="查过了，没有"))
    assert only_word and "X" in only_word and "Instagram" in only_word
    ok = _story(_social_search={"x": "@janniksin 9/25 有退赛视频（已用）",
                                "instagram": "@janniksinner 只有图文"})
    assert rf.social_search_problem(ok) is None
    # 键写了、值空着不算查过
    assert rf.social_search_problem(_story(_social_search={"x": "", "instagram": " "}))
    # 写成一句话也行，只要两个平台都点到名
    assert rf.social_search_problem(_story(
        _social_search="X：@janniksin 有 44s 视频；IG：没有公开账号")) is None
    # ⚠️ 「X」要是单独的大写字母：`X-ray`/`Xinyu` 里的 X 不算点到了 X
    assert rf.social_search_problem(_story(_social_search="Xinyu 那边 instagram 查过")) \
        is not None
    assert rf.social_search_problem(_story(_social_search_why="标题里的「伤」说的是比赛里扭伤，"
                                                             "不是当事人声明")) is None


def test_全库网球有故事_新片子都过闸():
    legacy = rf.legacy_social_search()
    bad = [f"{slug}: {rf.social_search_problem(spec).splitlines()[0]}"
           for slug, spec in _story_specs()
           if slug not in legacy and rf.social_search_problem(spec)]
    assert not bad, "\n".join(bad)


def test_豁免表只许减不许加_名字要真的存在且真的还过不了闸():
    legacy = rf.legacy_social_search()
    assert legacy, "豁免表读不到——路径或键名写错了，整条判据会静静失效"
    seen = dict(_story_specs())
    missing = sorted(s for s in legacy if s not in seen)
    assert not missing, f"豁免表里的 slug 不存在：{missing}"
    fixed = sorted(s for s in legacy
                   if rf.statement_topic(seen[s]) is None
                   or rf.social_search_problem({**seen[s], "slug": "probe"}) is None)
    assert not fixed, f"这些已经过闸了，从豁免表里删掉：{fixed}"
    # 定规矩那天（2026-09-27）扫全部「网球有故事」剪辑片命中 3 条
    assert len(legacy) <= 3


def test_闸接在validate_spec上_手写硬拦_自动产只报(monkeypatch, capsys):
    import build_match_reel as reel

    path = ROOT / "specs" / "reels" / "sinner-beijing-withdrawal-2026.json"
    if not Path(json.loads(path.read_text(encoding="utf-8"))["cover"]["portrait"]["image"]
                ).exists():
        pytest.skip("封面图不在这份检出里（稀疏检出）")
    spec = json.loads(path.read_text(encoding="utf-8"))
    monkeypatch.setattr(rf, "legacy_social_search", lambda: frozenset())
    with pytest.raises(reel.ReelError, match="_social_search"):
        reel.validate_spec(copy.deepcopy(spec))
    auto = copy.deepcopy(spec)
    auto["_production"] = {"status": "ready_for_render"}
    reel.validate_spec(auto)
    assert "[当事人声明] 自动 spec，只报不拦" in capsys.readouterr().out
    fixed = copy.deepcopy(spec)
    fixed["_social_search"] = {"x": "@janniksin 9/25 退赛视频（第 1 段）",
                               "instagram": "@janniksinner 只有图文"}
    reel.validate_spec(fixed)
