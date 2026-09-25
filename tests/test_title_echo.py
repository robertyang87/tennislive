"""正文第一句不许把标题再说一遍（账号所有者 2026-09-25：「以后标题里有的内容，
正文第一句话就不要写了，重复了」）。判据见 `tools/spec_wording.title_echo_problem`。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import push_reel  # noqa: E402
import spec_wording as w  # noqa: E402


def _pairs():
    for xhs in sorted((ROOT / "specs" / "reels").glob("*.xhs.txt")):
        slug = xhs.name[: -len(".xhs.txt")]
        spec_path = xhs.with_name(f"{slug}.json")
        if spec_path.is_file():
            yield slug, json.loads(spec_path.read_text("utf-8")), xhs.read_text("utf-8")


def test_正文第一句不许重复标题_新片子():
    bad = [f"{slug}：{w.title_echo_problem(spec, slug, text)}"
           for slug, spec, text in _pairs() if w.title_echo_problem(spec, slug, text)]
    assert not bad, "\n".join(bad)


def test_重复标题的豁免表只许减_每条都真的还在重复():
    legacy = w.legacy_title_echo()
    assert legacy, "豁免表读空了——判据的主语像是没了"
    known = {slug: (spec, text) for slug, spec, text in _pairs()}
    stale = []
    for slug in sorted(legacy):
        if slug not in known:
            stale.append(f"{slug}（spec 不在了）")
            continue
        spec, text = known[slug]
        title = str((spec.get("push") or {}).get("summary") or "")
        if w.title_echo_ratio(title, text) < w.TITLE_ECHO_MIN:
            stale.append(f"{slug}（已经不重复了，从表里删掉）")
    assert not stale, "豁免表里有过期的条目：\n" + "\n".join(stale)
    assert len(legacy) <= 150, "豁免表只许减不许加"


def test_判据正反两头():
    spec = {"push": {"summary": "鲁德抢十扳回柏林旧账"}}
    echo = "鲁德抢十扳回柏林旧账🎾\n\n北京时间9月25日晚上8点多开球。"
    fresh = "北京时间9月25日晚上8点多开球，拉沃尔杯伦敦站首日：鲁德 6-7(4)、6-4、10-8 胜塞伦多洛。"
    assert w.title_echo_problem(spec, "x-new", echo)
    assert w.title_echo_problem(spec, "x-new", fresh) is None     # 只重合一个人名


def test_复制页正文去掉只是重复标题的那一行():
    title = "9.26 赛场之上 | 鲁德抢十扳回柏林旧账"
    body = push_reel.copy_body_only("鲁德抢十扳回柏林旧账🎾\n\n北京时间……", title)
    assert body.startswith("北京时间")
    # 带新内容的开头一个字都不动
    keep = "鲁德抢十扳回柏林旧账，两年前输给他的那一场\n\n北京时间……"
    assert push_reel.copy_body_only(keep, title).startswith("鲁德抢十")
