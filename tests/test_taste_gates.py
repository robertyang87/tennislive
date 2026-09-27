"""账号所有者的口味闸：做视频前就拦掉，而不是做了一半又返工。

账号所有者 2026-09-27：「总结我的口味和品味这种个性化的要求，形成一个通用的
规则在做视频前就拦掉，而不是说做了一半又返工」。判据单一出处在
`tools/taste_gates.py`（模块 docstring 里有来路和量出来的账），这里钉三件事：

1. 每一道闸**抓得住被否的那一版**，**放得过被接受的那一版**（两个方向都用真稿）
2. 豁免表**只许减不许加**、**冻的是原文**，而且全库当前零误报
3. 闸真的坐在入口上：`validate_spec`（`--dry-run`）、采访渲染入口、采访预检——
   自动产的 spec 只报不拦；**不接任何模型**（账号所有者 2026-09-27「minimax 和
   deepseek 都不要用，后续会拿掉」）
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
    # fernandez-gibson 新加坡决赛（09-27 11:44Z 已推）——评审 B2：词表只认挨着的
    # 「夺冠」，合进 main 当场把这条判红。补的是词表，不是冻结（规矩之后的钩子不进豁免表）
    "首盘只差一分丢盘\n连赢8局夺下冠军",
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


#: 评审（2026-09-27）量出来 has_match_result 认不出的结果说法——其中 4 条是冻进
#: 豁免表的老钩子的误报（「涉险过关」「锁定这场1/4决赛」「把这场半决赛收进口袋」），
#: 新写的手写钩子照样会被误伤，于是人会拿 `_hook_shape_why` 硬推过去。
RESULT_WORDING = [
    "他闯进1/8决赛", "她打进1/4决赛", "两人会师半决赛", "他打进决赛",
    "郑钦文打进第三轮", "梅德韦杰夫进第二轮", "她进了下一轮", "她是郑钦文下一轮对手",
    "吴易昺过关", "二号种子涉险过关", "6-3锁定这场1/4决赛", "她连下最后八局锁定比赛",
    "他才把这场半决赛收进口袋", "她却带走胜利", "斩获生涯首冠", "她捧起奖杯",
    "卫冕成功", "两人会师决赛", "笑到最后",
    "萨巴伦卡赢下这场球", "她还是赢球了", "这场球她赢了",
    # 评审 B2：「夺冠」两个字不挨着、以及输家那一侧的说法
    "连赢8局夺下冠军", "她夺得冠军", "夺得巡回赛冠军", "他登顶世界第一",
    "加冕新科冠军", "问鼎澳网", "他闯入八强", "她跻身四强", "一路杀入四强",
    "她不敌萨巴伦卡", "他惜败辛纳", "郑钦文憾负",
]


def test_轮次名和整场结果的说法都算结果():
    for line in RESULT_WORDING:
        assert T.has_match_result(line), f"认不出结果：{line!r}"
    # 反方向：「总决赛冠军」是身份；「这一球」「一分」仍然是过程
    for line in ("总决赛冠军", "赢了这一球", "一局也没拿下", "他破了 再没输过一盘",
                 "一路杀入决胜盘", "两人闯入抢七"):
        assert not T.has_match_result(line), f"把过程当成了结果：{line!r}"


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


def test_采访封面标题的术语只报_数字一致才硬():
    """规则书 `hook-no-jargon-or-allusion` 管的是 reel 和字卡、O6 说的是「钩子」——
    采访大标题一起做硬是实现时自己延伸的（已发 106 条里 11 条会中），**账号所有者
    确认之前只报**；`copy-fields-one-source-of-truth` 写明管三条线，照旧硬。"""
    spec = {"slug": "new-iv", "cover": {"title": ["20岁首秀 两盘拿下", "他先谢看台上的费德勒"]},
            "push": {"summary": "他说谢谢费德勒"}}
    assert T.interview_title_jargon_problem(spec, legacy={})
    hard, soft = T.interview_taste_findings(spec)
    assert not hard and soft, "术语只报"
    spec["cover"]["title"] = ["20岁第一次登场 两盘拿下", "他先谢看台上的费德勒"]
    assert T.interview_title_jargon_problem(spec, legacy={}) is None
    clash = {"slug": "new-iv", "cover": {"title": ["三个赛点没兑现", "他说还会回来"]},
             "push": {"summary": "两个赛点没兑现，他说还会回来"}}
    hard, soft = T.interview_taste_findings(clash)
    assert hard and not soft, "标题和推送标题一个数两个说法是硬的"


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
    assert len(legacy["hook_shape"]) <= 169      # 178 → 169：结果词表补全后 9 条老钩子本来就合格
    assert len(legacy["hook_jargon"]) <= 76      # 75 → 76：safiullin-bu（ACE），闸落地前已推，见 _counts
    assert len(legacy["interview_title_jargon"]) <= 11
    assert len(legacy["explainer_question_jargon"]) <= 1
    for table, cap in ((T.BOARD_ANNOUNCE_LEGACY, 1), (T.ENDING_ORDER_LEGACY, 3)):
        assert len(table) <= cap


def test_闸落地前已推的ACE钩子按原文冻结_改一个字就受管():
    """评审 B2：safiullin-bu（#1114，2026-09-27 14:47Z 合进 main、已推送）的钩子
    「15记ACE／萨菲乌林晋级4强」。09-22 那条规矩的 ❌ 列表里就有 ACE，闸判它是对的；
    可它已经发出去了——已发的不重渲，只能按原文冻结（豁免表上限 75 → 76）。

    ⚠️ 这一道闸合进 main 之前，每一条落到 main 上的手写 reel 都要这么过一遍：
    真中了术语就按原文冻结、是词表漏了就补词表（fernandez-gibson 那条）。"""
    spec = _reel("safiullin-bu-hangzhou-2026-qf")
    assert "ACE" in T.jargon_hits(T._hook_text(spec))
    assert T.hook_jargon_problem(spec, legacy={}), "闸本身要认得出 ACE"
    assert T.hook_jargon_problem(spec) is None, "已推的那一版冻在豁免表里"
    spec["cover"]["hook"] = spec["cover"]["hook"].replace("15", "16")
    assert T.hook_jargon_problem(spec), "改一个字就重新受管"


def test_小表的豁免真的还不合格():
    for slug in T.ENDING_ORDER_LEGACY:
        assert T.ending_order_problem(_reel(slug), legacy=frozenset()), f"{slug} 已经合格了，删掉"
    for slug in T.BOARD_ANNOUNCE_LEGACY:
        assert T.board_announce_problem(_reel(slug), legacy=frozenset()), f"{slug} 已经合格了，删掉"


def _corpus_hard_findings(reel_paths, interview_paths) -> tuple[list[str], list[str]]:
    """(手写 spec 的硬发现, 自动 spec 的发现)。

    ⚠️ **自动 spec（`_production.status == ready_for_render`）只进第二组，不判 main 红。**
    `validate_spec` / `promote_reel_draft` 对它们本来就只报不拦，而 reel-auto-ready /
    finalize-reel 把转正的 spec **直接推上 main**：当天 121 份 pending 草稿里 103 份的钩子
    过不了这两道闸——这里要是把它们也算硬，第一条自动转正就把 main CI 打红，而豁免表
    只许减、根本没有出口
    （评审 B1，和 explainer-preflight 同一天被拦的是同一类：推一次就红一次的全库判据）。
    自动 spec 过闸时只要求**不抛**。

    采访线没有自动标记要分：自动转正的标题是固定模板「{赢家}赢球之后／第一时间说了什么？」，
    推送标题「{赢家}赢球后的场上采访」，两边都没有被计数的名词，硬的那一条（数字一致）
    结构上碰不到它。
    """
    bad, auto = [], []
    for path in reel_paths:
        spec = _load(path)
        hard, _soft = T.reel_taste_findings(spec)
        (auto if T.is_auto(spec) else bad).extend(
            f"{path.stem}: {h.splitlines()[0][:80]}" for h in hard)
    for path in interview_paths:
        hard, _soft = T.interview_taste_findings(_load(path))
        bad += [f"{path.stem}: {h[:80]}" for h in hard]
    return bad, auto


def test_全库当前零误报():
    """全部手写的 spec 过硬闸（带豁免表）一条都不许红——红了要么是闸写宽了，
    要么是有人在豁免之后改了原文却没按新规矩写。自动 spec 只报（见上）。"""
    bad, _auto = _corpus_hard_findings(REELS, INTERVIEWS)
    assert not bad, "\n".join(bad)


def test_全库判据不拿自动spec判红_手写的照红(tmp_path):
    """B1 的判据：同一个坏钩子，自动转正的只报、手写的红。"""
    base = _taste_spec("zz-auto-sim", "对手5次机会全落空\n梅德韦杰夫挺进8强")
    auto = dict(base, slug="zz-auto-sim",
                cover=dict(base["cover"], hook="总分输4分\n她却带走胜利"),
                _production={"status": "ready_for_render"})
    hand = dict(auto, slug="zz-hand-sim")
    hand.pop("_production")
    for spec in (auto, hand):
        (tmp_path / f"{spec['slug']}.json").write_text(
            json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    bad, noted = _corpus_hard_findings([tmp_path / "zz-auto-sim.json"], [])
    assert not bad and noted, "自动 spec 的坏钩子要只报、不判 main 红"
    bad, noted = _corpus_hard_findings([tmp_path / "zz-hand-sim.json"], [])
    assert bad and not noted, "手写 spec 的坏钩子必须红"


def test_cover不是对象时读得懂地红_不抛traceback():
    """评审 N：`cover` 写成字符串（`requests/stories/*.cover-v2.json` 那种形状）原来是
    一个 AttributeError 的 traceback；现在各道闸单独调都不抛，入口给一条硬发现（不放行）。"""
    for bad in ("assets/reel/x.jpg", ["决胜盘一度落后", "他逆转了"]):
        spec = {"slug": "new", "cover": bad, "push": {"summary": "两个盘点没给"},
                "segments": [{"narration": "轮到他发球"}] * 6}
        for gate in (T.hook_result_problem, T.hook_jargon_problem, T.hook_score_label_report,
                     T.copy_count_problem, T.rank_claim_problem, T.set_coverage_report,
                     T.story_band_problem, T.interview_title_jargon_problem):
            gate(spec)                                   # 不抛
        scoped = T.reel_taste_scoped(spec)
        assert scoped and scoped[0][1] and "cover" in scoped[0][2], scoped
        hard, _soft = T.interview_taste_findings(spec)
        assert hard and "cover" in hard[0]
    assert T.shape_problem({"slug": "ok", "cover": {"hook": "x"}, "push": None}) is None
    assert T.shape_problem({"slug": "x", "_production": "ready_for_render"})


# ════════════════════════ 入口：闸真的坐在该坐的地方 ════════════════════════

def _taste_spec(slug: str, hook: str, *, narrated: int = 4) -> dict:
    """一份**只喂口味闸**的合成 spec：钩子、封面口播和几段旁白。

    ⚠️ 不拿 live spec 当夹具（评审 N）：原来这里载 medvedev-royer 再过整条
    `validate_spec`——main 上以后加的任何一道闸、或者那条 spec 被改一个字，都会把
    口味闸的测试打红，而红的原因跟口味无关。判口味只调 `_owner_taste`；闸坐没坐在
    `--dry-run` 上，由 `_validate_spec_reaches_owner_taste` 单独钉。
    """
    return {"slug": slug,
            "cover": {"eyebrow": "赛场之上", "hook": hook, "narration": hook.replace("\n", "，")},
            "segments": [{"narration": "他退台半步，把回发球兜回对角。"}] * narrated}


#: 挑夹具时先试这条：规矩之后（09-26）写的，封面是抽帧，lean 检出没有 assets/reel 也过得了前面那些闸。
_WIRING_PREFERRED = "medvedev-royer-hangzhou-2026-r2"


def _validate_spec_reaches_owner_taste(monkeypatch) -> str:
    """`--dry-run` 走的 `validate_spec` 真的调到 `_owner_taste`，而且不吞它的异常。

    夹具**不钉死一条 live spec**：从已接受的手写 reel 里挑第一条能一路走到口味闸的
    （先试 `_WIRING_PREFERRED`）。别的闸红了只说明这一条当不了夹具，换下一条。
    """
    import build_match_reel as reel

    class _Reached(Exception):
        pass

    def spy(spec: dict) -> None:
        raise _Reached(spec.get("slug"))

    monkeypatch.setattr(reel, "_owner_taste", spy)
    paths = sorted(REELS, key=lambda p: p.stem != _WIRING_PREFERRED)
    tried = []
    for path in paths[:40]:
        try:
            spec = reel.load_spec(path)
            if T.is_auto(spec):
                continue
            reel.validate_spec(spec)
        except _Reached as hit:
            return str(hit)
        except (Exception, SystemExit) as err:  # noqa: BLE001 —— 当不了夹具，换下一条
            tried.append(f"{path.stem}: {type(err).__name__} {str(err)[:60]}")
            continue
        tried.append(f"{path.stem}: validate_spec 走完了却没调口味闸")
    pytest.fail("validate_spec 一次都没走到 _owner_taste：\n" + "\n".join(tried))


def test_validate_spec手写的新spec当场红(monkeypatch):
    """`--dry-run` 走的就是 validate_spec：换上被否的钩子，第 0.2 秒就红。"""
    import build_match_reel as reel

    reel._owner_taste(_taste_spec("new-hand", "对手5次机会全落空\n梅德韦杰夫挺进8强"))   # 原样放行
    for hook, why in (("对手5次机会全落空\n最后4分全是他的", "没交代结果"),
                      ("对手5个破发点全丢\n梅德韦杰夫挺进8强", "破发"),
                      ("首秀就被逼到4比6\n7分里拿下6分", "首秀")):
        with pytest.raises(reel.ReelError, match="口味") as err:
            reel._owner_taste(_taste_spec("new-hand", hook))
        assert why in str(err.value)
    # 已发的那一版钩子冻在豁免表里：同 slug、原文不变 → 放行；改一个字 → 受管
    legacy_slug = "wu-duckworth-us-open-2026-r2"
    frozen = T.load_legacy()["hook_shape"][legacy_slug]
    assert T.hook_result_problem(_hook_spec(frozen, slug=legacy_slug)) is None
    assert T.hook_result_problem(_hook_spec(frozen + "了", slug=legacy_slug))
    # 闸坐在 --dry-run 上
    assert _validate_spec_reaches_owner_taste(monkeypatch)


def test_自动产的spec只报不拦(capsys):
    """自动 spec 的硬发现只报、不抛；日志行首 `[口味·<块>]` 只告诉人去哪一块改。"""
    import build_match_reel as reel

    auto = _taste_spec("new-auto", "首秀就被逼到4比6\n7分里拿下6分", narrated=6)
    auto["_production"] = {"status": "ready_for_render"}
    for seg in auto["segments"]:              # 逐局报发球：旁白那一块
        seg["narration"] = "轮到他发球，十五比零。"
    reel._owner_taste(auto)          # 不抛
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("[口味·")]
    hard = [ln for ln in lines if "自动 spec 只报不拦" in ln]
    assert any(ln.startswith("[口味·钩子]") for ln in hard), lines
    assert any(ln.startswith("[口味·旁白]") for ln in hard), lines
    hand = dict(auto)
    hand.pop("_production")
    with pytest.raises(reel.ReelError, match="口味"):
        reel._owner_taste(hand)       # 同一份稿子，手写的就红


def test_口味闸不接模型():
    """账号所有者 2026-09-27「minimax 和 deepseek 都不要用，后续会拿掉」：口味闸只读
    spec，不回喂模型重写钩子（原来 `assemble_spec._retry_hook_taste` 那一轮），也不为
    `repair_reel_spec` 的回喂去挑日志行首（原来的 `REPAIRABLE`）。自动链本身不在这儿拆，
    那是账号所有者后面的一步——这里只钉住口味闸不往模型那头长。"""
    for gone in ("hook_taste_problems", "REPAIRABLE"):
        assert not hasattr(T, gone), f"taste_gates.{gone} 是给模型回喂用的，别加回来"
    model_side = ("assemble_spec", "draft_spec", "draft_segments", "repair_reel_spec")
    for name in model_side:
        src = Path(f"tools/{name}.py").read_text(encoding="utf-8")
        assert "taste_gates" not in src, f"{name} 不许把口味闸接进模型那一头"
    owner = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    body = owner[owner.index("def _owner_taste("):owner.index("def scoreboard_profile(")]
    assert "SALIENT" not in body and "REPAIRABLE" not in body


def _clash_interview() -> dict:
    return {"slug": "new-iv", "cover": {"title": ["三个赛点没兑现", "「一分一分找回节奏」"]},
            "push": {"summary": "两个赛点没兑现，他说慢慢找回节奏"}}


def _jargon_interview() -> dict:
    return {"slug": "new-iv", "cover": {"title": ["五比一 却被拖到抢七", "「一分一分找回节奏」"]},
            "push": {"summary": "他说慢慢找回节奏"}}


def test_采访渲染入口和预检都过口味闸(capsys):
    import build_interview_clip as clip
    import build_interview_request
    import production_preflight

    # 硬的：标题和推送标题一个数两个说法
    with pytest.raises(SystemExit, match="口味"):
        clip.check_taste(_clash_interview())
    with pytest.raises(ValueError, match="口味"):
        production_preflight.check_taste(_clash_interview())
    # 预检的请求路径（build_interview_request 在任何下载之前调它）
    with pytest.raises(ValueError, match="口味"):
        production_preflight.check_request(_clash_interview())
    # 只报的：大标题里的术语（等账号所有者确认）
    capsys.readouterr()
    clip.check_taste(_jargon_interview())
    production_preflight.check_taste(_jargon_interview())
    out = capsys.readouterr().out
    assert out.count("只报") == 2 and "抢七" in out
    import inspect
    assert "check_taste(spec)" in inspect.getsource(clip.main)
    # 「只改元数据」那条路上，预检读的是按请求差量改过的**现有 spec** 的标题（spec 后铺、
    # 手改过的标题赢），不是请求里那份可能过时的；重建那条路 build_spec 原样抄请求的
    # cover/push，所以请求本身就是这一趟会写进去的标题。
    src = inspect.getsource(build_interview_request._build_one_unlocked)
    assert "check_request({**req, **spec" in src
    assert '"cover": dict(req.get("cover") or {})' in inspect.getsource(
        build_interview_request.build_spec)


def test_采访预检main在赛后开麦上跑口味闸(tmp_path, monkeypatch, capsys):
    """工作流那一步（interview-clip.yml：production_preflight.py --column 赛后开麦）
    真的调了口味闸（评审 N2：删掉 main 里那两行，原来的测试一条都不红）。"""
    import production_preflight

    copies = []
    monkeypatch.setattr(production_preflight, "check_copy",
                        lambda copy, column, **kw: copies.append(column))

    def run(spec: dict, column: str) -> None:
        path = tmp_path / f"{column}.json"
        path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["production_preflight.py", "--spec", str(path),
                                          "--column", column])
        production_preflight.main()

    with pytest.raises(ValueError, match="口味"):
        run(_clash_interview(), "赛后开麦")
    assert copies == [], "口味闸排在文案检查（和任何下载）之前"
    capsys.readouterr()
    run(_jargon_interview(), "赛后开麦")             # 术语只报：不拦，文案检查照走
    assert "只报" in capsys.readouterr().out and copies == ["赛后开麦"]
    run(_clash_interview(), "赛场之上")             # reel 那头由 validate_spec 管
    assert copies == ["赛后开麦", "赛场之上"]
