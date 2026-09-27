"""账号所有者的口味闸：做视频前就拦掉，而不是做了一半又返工。

账号所有者 2026-09-27：「总结我的口味和品味这种个性化的要求，形成一个通用的
规则在做视频前就拦掉，而不是说做了一半又返工」。判据单一出处在
`tools/taste_gates.py`（模块 docstring 里有来路和量出来的账），这里钉三件事：

1. 每一道闸**抓得住被否的那一版**，**放得过被接受的那一版**（两个方向都用真稿）
2. 豁免表**只许减不许加**、**冻的是原文**，而且全库当前零误报
3. 闸真的坐在入口上：`validate_spec`（`--dry-run`）、采访渲染入口、采访预检、
   起草阶段的回喂重写——自动产的 spec 只报不拦
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("tools").resolve()))
sys.path.insert(0, str(Path("src").resolve()))

import taste_gates as T  # noqa: E402

REELS = sorted(Path("specs/reels").glob("*.json"))
INTERVIEWS = sorted(Path("specs/interviews").glob("*.json"))


def _load(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec.setdefault("slug", path.stem)
    return spec


def _reel(slug: str) -> dict:
    return _load(Path(f"specs/reels/{slug}.json"))


def _hook_spec(hook: str, eyebrow: str = "赛场之上", slug: str = "new-hand-written") -> dict:
    return {"slug": slug, "cover": {"eyebrow": eyebrow, "hook": hook}}


# ════════════════════════ ① 钩子第二行是结果 ════════════════════════

#: 被账号所有者否掉的版本（引语在 taste_gates / CLAUDE.md「钩子只讲重点和结果」）
REJECTED_NO_RESULT = [
    "5比2被追成5比5\n她连拿最后2局",          # fernandez-andreeva：「钩子文案都看不出什么」
    "首盘告负\n抢七七比三扳平",                # cobolli-jodar：「标题文案要让人看懂结果的」
    "决胜盘二比五落后\n五个赛点，一个没给",    # shang-rublev v1：没说清赢的是谁
    "整场她只丢了一局\n丢在自己的发球局",      # oliynykova：「要和赛果相关」
    "三比五 对手发球胜盘\n他破了 再没输过一盘",  # tsitsipas-fils：「换成完成逆转」
    "一盘落后翻上来\n全场只多赢一分",          # chung-nagal：总分差
]

#: 规矩之后（2026-09-25 13:21Z）被接受的版本
ACCEPTED = [
    "决胜盘一度落后\n中岛布兰登逆转门西克",    # 账号所有者从四个候选里挑的
    "次盘5比2被追平\n7比5淘汰头号种子",
    "只差一分被拖进决胜盘\n他还是挺进了8强",
    "去年被保利尼逆转\n今年2比0赢回来",
    "单打刚被逆转\n兹维列夫双打赢回来",
    "前10次机会全落空\n黄泽林挺进8强",
]


def test_钩子第二行要交代结果_被否的抓得住_被接受的放得过():
    for hook in REJECTED_NO_RESULT:
        assert T.hook_result_problem(_hook_spec(hook), legacy={}), f"没拦住被否的：{hook!r}"
    for hook in ACCEPTED:
        assert T.hook_result_problem(_hook_spec(hook), legacy={}) is None, f"误伤：{hook!r}"
    # 只管「赛场之上」——网球有故事的钩子可以是一问
    assert T.hook_result_problem(
        _hook_spec("冰与火的碰撞\n这次谁能笑到最后？", eyebrow="网球有故事"), legacy={}) is None


def test_弱动词的宾语是分局盘时不算结果():
    """「丢了一局」「没输过一盘」是过程——候选阶段的宽表就是这么放过三条被否钩子的。"""
    assert not T.has_match_result("丢在自己的发球局")
    assert not T.has_match_result("他破了 再没输过一盘")
    assert not T.has_match_result("一局也没拿下")
    assert not T.has_match_result("全场只多赢一分")
    assert T.has_match_result("他还是赢了")
    assert T.has_match_result("阿尔卡拉斯击败弗里茨")


def test_钩子里比全场总分差要拦():
    assert T.hook_result_problem(_hook_spec("三盘打满\n全场只多赢一分，她赢了"), legacy={})
    assert T.hook_result_problem(_hook_spec("总分少拿五分\n他照样逆转"), legacy={})
    # 「只差一分」是关键分，放行；「至少」不是差值
    assert T.hook_result_problem(_hook_spec("只差一分被拖进决胜盘\n他还是挺进了8强"), legacy={}) is None
    assert not T.TOTAL_POINTS.search("至少3分")


def test_新闻点就是事件本身可以认领():
    spec = _hook_spec("威廉姆斯姐妹\n时隔四年合体")
    assert T.hook_result_problem(spec, legacy={})
    spec["cover"]["_hook_shape_why"] = "新闻点就是两人重新搭档本身，这场球的结果不是卖点"
    assert T.hook_result_problem(spec, legacy={}) is None


def test_第一行比分没说是哪一盘_只报():
    assert T.hook_score_label_report(_hook_spec("最后关头4比6落后\n逆转门西克赢下首秀"), legacy={})
    assert T.hook_score_label_report(_hook_spec("次盘5比2被追平\n7比5淘汰头号种子"), legacy={}) is None
    # 局内比分（40-30）不问是哪一盘
    assert T.hook_score_label_report(_hook_spec("对手四十比三十握着赛点\n她赢了回来"), legacy={}) is None


# ════════════════════════ ② 钩子里的术语和梗 ════════════════════════

def test_钩子里的术语和梗要拦_O6破发抢七也禁():
    for hook in ("3个赛点全丢了\n最后一局破发到零",           # bouzkova：「破发到 0 是啥意思」
                 "首秀就被逼到4比6\n7分里拿下6分",            # mensik v1
                 "11个月前跟腱断了\n先丢一盘打到抢七",        # O6：抢七也禁
                 "对手5个破发点全没兑现\n她挺进8强",           # O6：破发也禁
                 "二发Ace破局\n抢十惊险突围",
                 "网球为什么要安静\n德约对看台说晚安"):       # 读者：「莫名其妙的文案」
        assert T.hook_jargon_problem(_hook_spec(hook), legacy={}), f"没拦住：{hook!r}"
    for hook in ("对手5次机会全落空\n梅德韦杰夫挺进8强",
                 "首盘错过4个盘点\n第二盘他还是赢了",          # 盘点、赛点、决胜盘放行
                 "决胜盘一度落后\n中岛布兰登逆转门西克"):
        assert T.hook_jargon_problem(_hook_spec(hook), legacy={}) is None, f"误伤：{hook!r}"
    # 「世界第一发球胜赛」里的「第一发」不是一发
    assert "一发" not in T.jargon_hits("世界第一发球胜赛")
    # ACE 在汉字中间也认得出（`\b` 在中文里不起作用，候选阶段那版漏了）
    assert "Ace" in T.jargon_hits("二发Ace破局")


def test_术语认领口只给网球有故事():
    story = _hook_spec("抢七是怎么来的\n一场五小时的球逼出来的", eyebrow="网球有故事")
    assert T.hook_jargon_problem(story, legacy={})
    story["cover"]["_hook_term_why"] = "这条片子讲的就是抢七规则本身"
    assert T.hook_jargon_problem(story, legacy={}) is None
    reel = _hook_spec("首盘打到抢七\n他还是赢了")
    reel["cover"]["_hook_term_why"] = "想用"
    assert T.hook_jargon_problem(reel, legacy={}), "赛场之上没有这个口（O6 点名禁的就是这一栏）"


def test_采访封面标题同一条规矩():
    spec = {"slug": "new-iv", "cover": {"title": ["20岁首秀 两盘拿下", "他先谢看台上的费德勒"]},
            "push": {"summary": "他说谢谢费德勒"}}
    assert T.interview_title_jargon_problem(spec, legacy={})
    spec["cover"]["title"] = ["20岁第一次登场 两盘拿下", "他先谢看台上的费德勒"]
    assert T.interview_title_jargon_problem(spec, legacy={}) is None


def test_字卡封面问句同一条规矩():
    """字卡这条线没有 --dry-run，判据坐在 CI：全部 `_OPENINGS` 问句过闸。"""
    from tennislive.video.explainer import _OPENINGS

    bad = [p for slug, o in _OPENINGS.items()
           if (p := T.explainer_question_jargon_problem(slug, o))]
    assert not bad, "\n".join(bad)
    assert T.explainer_question_jargon_problem("new-deck", {"question": "二发前拍20下球算违规吗？"})
    assert T.explainer_question_jargon_problem(
        "new-deck", {"question": "二发前拍20下球算违规吗？",
                     "hook_term_why": "这条片子讲的就是二发计时规则本身"}) is None


# ════════════════════════ ③ 钩子 × 推送标题一个数一个说法 ════════════════════════

def test_钩子和推送标题的数字要一致_wu_walton那次():
    spec = {"slug": "x", "cover": {"hook": "两次差点丢掉一盘\n三个盘点一个没给"},
            "push": {"summary": "两个盘点没给，吴易昺过关"}}
    assert T.copy_count_problem(spec), "wu-walton 推出去的那一版必须红"
    spec["push"]["summary"] = "三个盘点没给，吴易昺过关"
    assert T.copy_count_problem(spec) is None
    # 隐含计数：「第七个才落地」＝前六个没兑现；「一个都没给」＝0
    assert T.copy_count_clash("六个赛点被救下\n第七个才落地", "七个赛点她才拿下这场") == []
    assert T.copy_count_clash("第四个赛点才落地\n她赢了", "三个赛点没兑现") == []
    assert T.copy_count_clash("一个破发点都没给", "零破发点") == []
    # 认领口
    spec["push"]["summary"] = "两个盘点没给，吴易昺过关"
    spec["push"]["_summary_count_why"] = "推送标题说的是另一盘"
    assert T.copy_count_problem(spec) is None


def test_钩子和推送标题的排名要和matchup一致():
    spec = {"cover": {"hook": "伤停五个月\n他掀翻了世界第九",
                      "matchup": [{"name": "商竣程", "rank": 107}, {"name": "卢布列夫", "rank": 16}]},
            "push": {"summary": "商竣程掀翻卢布列夫"}}
    assert T.rank_claim_problem(spec)
    spec["cover"]["hook"] = "伤停五个月\n他掀翻了世界第十六"
    assert T.rank_claim_problem(spec) is None
    assert T.rank_claims("这一站的十号种子卢布列夫") == [], "种子序号被当成了排名"


# ════════════════════════ ④ 旁白走向 ════════════════════════

def test_逐局报发球的密度闸():
    seg = lambda n: {"narration": n, "start": 0, "end": 5}  # noqa: E731
    bad = {"slug": "x", "segments": [seg("轮到她发球，十五比零")] * 4 + [seg("她赢了")] * 2}
    assert T.board_announce_problem(bad, legacy=frozenset())
    ok = {"slug": "x", "segments": [seg("轮到自己发球，三十比四十——第二个盘点")]
          + [seg("她反手直线穿越")] * 5}
    assert T.board_announce_problem(ok, legacy=frozenset()) is None


def test_每一盘至少一句_只报():
    spec = {"cover": {"eyebrow": "赛场之上", "result": "3-6 6-3 7-6(4)"},
            "segments": [{"narration": "北京时间九月二十号，戴维斯杯。"},
                         {"narration": "决胜盘五比六，再丢一分就结束。"}]}
    assert "第 1 盘" in T.set_coverage_report(spec)
    spec["segments"].append({"narration": "首盘五个破发点一个没兑现，第二盘连破两次。"})
    assert T.set_coverage_report(spec) is None


# ════════════════════════ ⑤ 收在时间上最晚的镜头 ════════════════════════

def _cold_open(segs):
    return {"slug": "new", "cover": {"eyebrow": "赛场之上"}, "sources": {"m": "u"},
            "segments": [{"source": "m", "start": s, "end": e} for s, e in segs]}


def test_握手之后不许再接回放():
    # 冷开场 160–171，正文从 10s 倒回，第 3 段已经放到 190（握手），最后一段又回到 164
    bad = _cold_open([(160, 171), (10, 30), (171, 190), (150, 164)])
    assert T.ending_order_problem(bad, legacy=frozenset())
    good = _cold_open([(160, 171), (10, 30), (150, 164), (164, 190)])
    assert T.ending_order_problem(good, legacy=frozenset()) is None
    bad["segments"][-1]["_ending_order_why"] = "最后一段是赛点慢放，握手在它前面是导演故意的"
    assert T.ending_order_problem(bad, legacy=frozenset()) is None


# ════════════════════════ ⑥ 交手史片的信息条 ════════════════════════

def test_交手史片每一场第一次出现都要贴信息条():
    spec = _reel("sabalenka-rybakina-h2h")
    assert T.is_h2h_story(spec)
    assert T.story_band_problem(spec) is None, "已接受的那一版不该红"
    naked = copy.deepcopy(spec)
    for seg in naked["segments"]:
        seg.pop("inset", None)
    assert T.story_band_problem(naked), "信息条全拿掉必须红（被否的 v1 就是这样）"
    # 讲规则的片子拿比赛当 B-roll，不在管辖内
    rules = {**naked, "slug": "rules-story", "cover": {**naked["cover"], "hook": "为什么要安静", "topic": "规则"}}
    assert not T.is_h2h_story(rules)


# ════════════════════════ 豁免表：只许减不许加、冻原文、全库零误报 ════════════════════════

def test_口味豁免表只许减不许加_冻的是原文():
    legacy = T.load_legacy()
    reels = {p.stem: _load(p) for p in REELS}
    interviews = {p.stem: _load(p) for p in INTERVIEWS}
    stale = []
    for slug, text in legacy["hook_shape"].items():
        spec = reels.get(slug)
        if spec is None or T._hook_text(spec) != text or not T.hook_result_problem(spec, legacy={}):
            stale.append(f"hook_shape:{slug}")
    for slug, text in legacy["hook_jargon"].items():
        spec = reels.get(slug)
        if spec is None or T._hook_text(spec) != text or not T.hook_jargon_problem(spec, legacy={}):
            stale.append(f"hook_jargon:{slug}")
    for slug, text in legacy["interview_title_jargon"].items():
        spec = interviews.get(slug)
        title = "\n".join(T.hook_lines_of((spec or {}).get("cover", {}).get("title")))
        if spec is None or title != text or not T.interview_title_jargon_problem(spec, legacy={}):
            stale.append(f"interview_title_jargon:{slug}")
    from tennislive.video.explainer import _OPENINGS
    for slug, text in legacy["explainer_question_jargon"].items():
        o = _OPENINGS.get(slug) or {}
        if str(o.get("question")) != text or not T.explainer_question_jargon_problem(slug, o, legacy={}):
            stale.append(f"explainer_question_jargon:{slug}")
    assert not stale, ("这些豁免已经不成立（改好了、改了原文或删了）——从 "
                       "data/legacy_taste_gates.json 里删掉：" + "、".join(stale))
    # 只许减：数目只能往下走（2026-09-27 落地那天的数）
    assert len(legacy["hook_shape"]) <= 178
    assert len(legacy["hook_jargon"]) <= 75
    assert len(legacy["interview_title_jargon"]) <= 11
    assert len(legacy["explainer_question_jargon"]) <= 1
    for table, cap in ((T.BOARD_ANNOUNCE_LEGACY, 1), (T.ENDING_ORDER_LEGACY, 3)):
        assert len(table) <= cap


def test_小表的豁免真的还不合格():
    for slug in T.ENDING_ORDER_LEGACY:
        assert T.ending_order_problem(_reel(slug), legacy=frozenset()), f"{slug} 已经合格了，删掉"
    for slug in T.BOARD_ANNOUNCE_LEGACY:
        assert T.board_announce_problem(_reel(slug), legacy=frozenset()), f"{slug} 已经合格了，删掉"


def test_全库当前零误报():
    """全部已发的 spec 过硬闸（带豁免表）一条都不许红——红了要么是闸写宽了，
    要么是有人在豁免之后改了原文却没按新规矩写。"""
    bad = []
    for path in REELS:
        hard, _soft = T.reel_taste_findings(_load(path))
        bad += [f"{path.stem}: {h.splitlines()[0][:80]}" for h in hard]
    for path in INTERVIEWS:
        bad += [f"{path.stem}: {h[:80]}" for h in T.interview_taste_findings(_load(path))]
    assert not bad, "\n".join(bad)


# ════════════════════════ 入口：闸真的坐在该坐的地方 ════════════════════════

def _hand_written(slug: str, hook: str) -> dict:
    """一条已接受、`validate_spec` 全绿的手写 spec，只换钩子、换 slug（新片子不吃豁免）。

    medvedev-royer 是规矩之后（09-26）写的，封面是抽帧（lean 检出没有
    assets/reel 也能过前面那些闸）。封面口播跟着钩子一起换——两处是一句话。
    """
    import build_match_reel as reel

    spec = reel.load_spec(Path("specs/reels/medvedev-royer-hangzhou-2026-r2.json"))
    spec["slug"] = slug
    spec["cover"]["hook"] = hook
    spec["cover"]["narration"] = hook.replace("\n", "，")
    return spec


def test_validate_spec手写的新spec当场红():
    """`--dry-run` 走的就是 validate_spec：换上被否的钩子，第 0.2 秒就红。"""
    import build_match_reel as reel

    ok = _hand_written("medvedev-royer-hangzhou-2026-r2", "对手5次机会全落空\n梅德韦杰夫挺进8强")
    reel.validate_spec(ok)                          # 原样放行
    for hook, why in (("对手5次机会全落空\n最后4分全是他的", "没交代结果"),
                      ("对手5个破发点全丢\n梅德韦杰夫挺进8强", "破发"),
                      ("首秀就被逼到4比6\n7分里拿下6分", "首秀")):
        with pytest.raises(reel.ReelError, match="口味") as err:
            reel.validate_spec(_hand_written("medvedev-royer-hangzhou-2026-r2", hook))
        assert why in str(err.value)
    # 已发的那一版钩子冻在豁免表里：同 slug、原文不变 → 放行；改一个字 → 受管
    legacy_slug = "wu-duckworth-us-open-2026-r2"
    frozen = T.load_legacy()["hook_shape"][legacy_slug]
    assert T.hook_result_problem(_hook_spec(frozen, slug=legacy_slug)) is None
    assert T.hook_result_problem(_hook_spec(frozen + "了", slug=legacy_slug))


def test_自动产的spec只报不拦(capsys):
    import build_match_reel as reel

    auto = _hand_written("medvedev-royer-hangzhou-2026-r2", "首秀就被逼到4比6\n7分里拿下6分")
    auto["_production"] = {"status": "ready_for_render"}
    reel._owner_taste(auto)          # 不抛
    out = capsys.readouterr().out
    assert "[口味·旁白/窗口/钩子] 自动 spec 只报不拦" in out
    # repair_reel_spec 回喂时按行挑判据：每一条都得被 SALIENT 认出来
    import repair_reel_spec
    lines = [ln for ln in out.splitlines() if ln.startswith("[口味·")]
    assert lines and all(repair_reel_spec.SALIENT.search(ln) for ln in lines)


def test_采访渲染入口和预检都过口味闸(tmp_path):
    import build_interview_clip as clip
    import production_preflight

    spec = {"slug": "new-iv", "cover": {"title": ["五比一 却被拖到抢七", "「一分一分找回节奏」"]},
            "push": {"summary": "他说慢慢找回节奏"}}
    with pytest.raises(SystemExit, match="口味"):
        clip.check_taste(spec)
    with pytest.raises(ValueError, match="口味"):
        production_preflight.check_taste(spec)
    ok = copy.deepcopy(spec)
    ok["cover"]["title"] = ["五比一 却被拖到最后一局", "「一分一分找回节奏」"]
    clip.check_taste(ok)
    production_preflight.check_taste(ok)
    # 预检的请求路径（build_interview_request 在任何下载之前调它）
    with pytest.raises(ValueError, match="口味"):
        production_preflight.check_request(spec)
    import inspect
    assert "check_taste(spec)" in inspect.getsource(clip.main)


def test_起草阶段钩子不合口味就回喂重写一轮(monkeypatch):
    import assemble_spec as a

    calls = []

    def fake(chat, **kw):
        calls.append(kw["facts"])
        if len(calls) == 1:
            return {"hook": ["5比2被追成5比5", "她连拿最后2局"], "beats": ["b"]}
        return {"hook": ["次盘5比2被追平", "她还是挺进了决赛"], "beats": ["b"]}

    monkeypatch.setattr(a, "draft_editorial", fake)
    draft = {"editorial": fake(None, facts="f"), "stats": {}, "cover": {}}
    notes: list[str] = []
    a._retry_hook_taste(draft, None, home="A", away="B", event="E", year=2026,
                        fixture="", facts="f", background="", scores=[], notes=notes)
    assert draft["editorial"]["hook"] == ["次盘5比2被追平", "她还是挺进了决赛"]
    assert "不合账号所有者的口味" in calls[-1], "判据原文没回喂给模型"
    assert notes and "重写后通过" in notes[0]

    # 重写没改善：留首稿、只报，**不撤稿**（自动链不能被卡成「今天没有候选」）
    calls.clear()
    monkeypatch.setattr(a, "draft_editorial",
                        lambda chat, **kw: {"hook": ["5比2被追成5比5", "她连拿最后2局"]})
    draft = {"editorial": {"hook": ["5比2被追成5比5", "她连拿最后2局"]}, "stats": {}, "cover": {}}
    notes = []
    a._retry_hook_taste(draft, None, home="A", away="B", event="E", year=2026,
                        fixture="", facts="f", background="", scores=[], notes=notes)
    assert "editorial" in draft and "只报不拦" in notes[0]
