"""人物类「网球有故事」的封面副标题：「<名字>：<故事内容>」。

账号所有者 2026-10-18：「下次再做这种人物类的视频的时候，然后在副标题上加上他的名字，
然后再加冒号，再加副标题的内容」，看过 fokina-story-2026 的新封面后：「然后把这个规则
定下来，变成全局规则，放在库里做强制要求」。

两条线（竖版短片 `specs/reels/*.json` 的 `cover`、字卡 `explainer._OPENINGS`）共用
`reel_facts.story_topic_name_problem`：新稿必须声明 `story_kind`（person／other），
person 的副标题以 `subject` ＋全角冒号开头。定规矩之前的挂在
`data/legacy_story_topic_name.json`，只许减不许加。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import reel_facts as rf  # noqa: E402

LEGACY = json.loads((ROOT / "data" / "legacy_story_topic_name.json").read_text(encoding="utf-8"))


def test_人物片副标题要以名字加全角冒号开头():
    ok = rf.story_topic_name_problem("福基纳：从五次亚军走到上海决赛", "person", "福基纳")
    assert ok is None
    for bad in ("从五次亚军走到上海决赛",          # 没写名字
                "福基纳:从五次亚军走到上海决赛",    # 半角冒号
                "福基纳 · 从五次亚军走到上海决赛",  # 用了间隔号
                "福基纳：",                        # 冒号后面没内容
                "卡塔尔：从五次亚军走到上海决赛"):  # 名字和主角对不上
        assert rf.story_topic_name_problem(bad, "person", "福基纳"), bad
    assert rf.story_topic_name_problem("福基纳：x", "person", ""), "人物片要写 subject"


def test_不声明类别就拦_other不管副标题():
    assert rf.story_topic_name_problem("擦网喊的是 Let 不是 Net", None, "主裁")
    assert rf.story_topic_name_problem("擦网喊的是 Let 不是 Net", "rule", "主裁")
    assert rf.story_topic_name_problem("擦网喊的是 Let 不是 Net", "other", "主裁") is None


def _story_reels():
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        cover = spec.get("cover") if isinstance(spec.get("cover"), dict) else {}
        if str(cover.get("eyebrow", "")).strip() == "网球有故事":
            yield spec.get("slug") or path.stem, cover


def test_新的网球有故事竖版短片都合规矩():
    legacy = rf.legacy_story_topic_name("reels")
    bad = [f"{slug}: {rf.story_topic_name_problem(c.get('topic'), c.get('story_kind'), c.get('subject'))}"
           for slug, c in _story_reels()
           if slug not in legacy
           and rf.story_topic_name_problem(c.get("topic"), c.get("story_kind"), c.get("subject"))]
    assert not bad, "\n".join(bad)


def test_新的网球有故事字卡都合规矩():
    import explainer_preflight as P  # noqa: PLC0415
    from tennislive.video import explainer as E  # noqa: PLC0415
    legacy = rf.legacy_story_topic_name("explainers")
    bad = []
    for slug, op in E._OPENINGS.items():
        if slug in legacy or E.explainer_column(slug) != "网球有故事":
            continue
        problem = rf.story_topic_name_problem(op.get("topic"), op.get("story_kind"), op.get("subject"))
        if problem:
            bad.append(f"{slug}: {problem}")
    assert not bad, "\n".join(bad)
    assert ("人物片副标题", P.story_topic_name_problems) in P.CHECKS


def test_豁免表只许减_每条都还在():
    reels = {slug for slug, _ in _story_reels()}
    from tennislive.video import explainer as E  # noqa: PLC0415
    stale = [s for s in LEGACY["reels"] if s not in reels]
    stale += [s for s in LEGACY["explainers"] if s not in E._OPENINGS]
    assert not stale, f"豁免表里这几条已经不在库里了，删掉：{stale}"
    # 只许减：表的大小钉在定规矩那一天（2026-10-18）的数，往里加就红
    assert len(LEGACY["reels"]) <= 65 and len(LEGACY["explainers"]) <= 45
    assert "fokina-story-2026" not in LEGACY["reels"], "fokina-story-2026 是这条规矩的样板，不许豁免"
