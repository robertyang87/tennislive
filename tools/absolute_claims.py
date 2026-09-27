"""全称断言那道闸的**单一出处**——竖版短片、解说片、赛后开麦三条线共用。

「零胜 / 一场没赢过 / 唯一一个 / 史上第一 / 从来没有」这一族话，**一个反例
就倒**，所以不能从「我查到的那几场」推，只能从一张能穷举的表读，而且要两个
独立源对得上（账号所有者 2026-08-07：「最好经过多个信息源交叉验证过」）。
写了就要在 `_claims` 里认领两个不同主机的 URL——判据和那次事故的来路记在
`build_match_reel._absolute_claims_need_a_source` 的 docstring 里。

这个模块是 2026-09-27 从 `build_match_reel.py` 里拆出来的，为的是两件事：

① **闸原来只装在竖版短片那条线上。** 解说片（`explainer._SCRIPTS`）和采访线
   一道都没有——CLAUDE.md「『一共只 N 次，N 次全 X』是全称断言的一种」那节
   记着：「解说片这条线一道都没有……这是个**已知缺口**」。而那条线上真出过事：
   `wawrinka-wildcard` 第 ④ 屏「他**一共只进过三次**大满贯决赛，**三次全部拿下**」，
   推了微信之后账号所有者指出是四次（f58553ef，第四次是 2017 法网决赛负纳达尔）。
   装闸那天量的存量：解说片 52 条里 9 条带着没认领的全称断言
   （`EXPLAINER_LEGACY`），采访线 2 条（`INTERVIEW_LEGACY`）。

② **计数式认不出来。** `wawrinka` 那句不含词表里任何一个词。

⚠️⚠️ **②这件事仓库里量过一次，结论是「词表不动」**——
`.claude/skills/tennis-editorial/SKILL.md`「我本来想把词表放宽，是数据把它否掉的」：
按词加（`一共只` / `N 次全部` / `N 次都输`）扫存量 **9 处命中 7 处误伤**，误伤的
全是**这一场之内**的计数（「决胜盘一共只有四十六个小分」「保发四次全部失败」），
而那一类是闭集，逐分数据本身就穷举得了。那次的结论写的是「**分界是语义，不是词**」。

这次没有推翻它，是**换了一个形状**再量：同一个数说两遍、第二遍跟着「全／都」，
**而且第一遍挂在「交手 / 打进 / 进过 / 站上 / 去过 / 打过」这类生涯动词上**
（`COUNT_RE`）。生涯动词正是那条分界本身：交手记录、进过几次决赛是开集
（多输一次这句话就错），「两次零比四十」「五次破发点」「三次被逼到赛点」没有
这类动词。2026-09-27 全库量的（竖版短片 305 条 + 采访 106 条 + 解说片 52 条，
含小红书正文）：

    只要求「N次…N次全/都」          27 条命中，12 条是这一场之内的闭集（误伤）
    ＋ 第一遍挂生涯动词（COUNT_RE）  13 条命中，**13 条全是生涯/交手计数**，零误伤

仍然认不出的形状（**宁可窄**，这一半靠写的时候自己问那一句）：
`zverev-norrie`「上了巡回赛之后，八次全输」（只说一遍数）、示意图标题
「三次大满贯决赛，三次都赢」（没有动词——同一条片子的旁白会被认出来）。
"""

from __future__ import annotations

import re
from typing import Iterable

#: 否定式和最高级那一族。⚠️ `零胜` 前面不许是「比」：「六比零胜阿朗戈」是比分，
#: 不是断言——采访线 `swiatek-arango-cincinnati-2026-r2` 的封面文字当场被它误认过
#: （2026-09-27 把采访线接进来时扫出来的，竖版短片那边存量里恰好没撞上）。
WORD_RE = re.compile(
    r"(?<!比)零胜|一场没赢过|一场都没赢|一次都没赢|没赢过一场|从没赢过|从未赢过"
    r"|唯一一个|唯一一位|史上第一|历史上第一|从来没有")

_N = r"[一二三四五六七八九十两\d]+"
#: 生涯／交手那一类的动词——**分界就在这儿**，见模块 docstring。
_CAREER_VERB = r"(?:交手|打进|进过|进入|站上|去过|打过|闯进)"
#: 「两次打进抢七，两次都拿下」是这一场之内的事，动词对了宾语不对。存量里一处
#: 都没有，是写判据时自己拿它造句造出来的（反向验证只测得出「该拦的拦没拦」，
#: 测不出「不该拦的拦没拦」，所以两头都要自己写一遍）。
_IN_MATCH = r"(?!抢七|抢十|决胜盘|决胜局|平分|局点|盘点|赛点|破发)"
_GAP = r"[^。？！；\n]{0,20}?"
COUNT_RE = re.compile(
    rf"({_N})次{_CAREER_VERB}{_IN_MATCH}{_GAP}\1次(?:全|都)"
    rf"|{_CAREER_VERB}过?({_N})次{_IN_MATCH}{_GAP}\2次(?:全|都)")

#: 解说片（`explainer._SCRIPTS`）里装闸之前就发出去的。**只许减不许加**，
#: 自检在 `tests/test_absolute_claims.py`：名字要真的还在、而且真的还带着没认领的断言。
#: ⚠️ **豁免的是「不用补出处」，不是「那句话是对的」。**
EXPLAINER_LEGACY = frozenset({
    "finals-venues",     # 「以前从来没有过的东西」（合同里的总部搬迁）
    "lucky-loser",       # 「再赢一场就是史上第一个」
    "mandatory-1000",    # 「网球史上第一个赢下赛季前四站大师赛的人」
    "nadal-academy",     # 学院公告原文「史上第一次」
    "pr-allowance",      # 「史上第一个用保护排名拿到大满贯的球员」
    "shang-nishikori",   # 「公开赛年代唯一一位代表亚洲国家打进大满贯男单决赛」
    "shang-rublev",      # 「那个星期天第一个赢下首轮的人——也是唯一一个」
    "venus-potapova",    # 「网球史上第一个拿到与男子冠军等额支票的女子冠军」
    "wildcard",          # 「公开赛年代唯一一个以外卡身份拿下大满贯男单冠军」
})

#: 采访线（`specs/interviews/`）里装闸之前就发出去的。只许减不许加。
INTERVIEW_LEGACY = frozenset({
    "bu-jodar-us-open-2026-r1-interview",       # 「一场没赢过」「六次打进正赛，六次全」
    "rybakina-townsend-cincinnati-2026-r2",     # 「她是唯一一个八站首战全胜的球员」
})

#: 竖版短片里，**只因为计数式那一档**才会新红的存量（2026-09-27 加进 `COUNT_RE`
#: 那天量的）。它们豁免的只是计数式那一句——词表那一档照旧要认领，
#: 那一档的老豁免还在 `build_match_reel._LEGACY_UNSOURCED_CLAIMS`。只许减不许加。
REEL_COUNT_LEGACY = frozenset({
    "mensik-tien-davis-cup-2026-q2",       # 三次交手，三次都
    "nakashima-medvedev",                  # 三次交手，中岛此前三次都
    "putintseva-bencic-us-open-2026-r1",   # 交手过两次，郑钦文两次都
    "rublev-virtanen-us-open-2026-r1",     # 四分之一决赛他去过十次，十次都
    "swiatek-parry",                       # 两次交手，两次都
    "swiatek-svitolina-toronto-sf",        # 两次交手的剧本——那两次全
    "tsitsipas-royer",                     # 两次打进大满贯决赛，两次都
    "wang-xinyu-story",                    # 两次打进决赛，两次都
})


def claim_phrases(texts: Iterable[str], *, count_form: bool = True) -> list[str]:
    """这批文字里命中的全称断言，去重排好序。`count_form=False` 只看词表那一档。"""
    found: set[str] = set()
    for text in texts:
        text = str(text or "")
        found |= {m.group(0) for m in WORD_RE.finditer(text)}
        if count_form:
            found |= {m.group(0) for m in COUNT_RE.finditer(text)}
    return sorted(found)


def is_count_phrase(phrase: str) -> bool:
    return bool(COUNT_RE.fullmatch(phrase))


def claim_hosts(value: object) -> set[str]:
    """一条认领里引了几个**不同**的源——按主机名去重，同一个站点算一个。"""
    return {m.group(1).lower()
            for m in re.finditer(r"https?://([^/\s)）]+)", str(value))}


def unsourced(texts: Iterable[str], claims: dict | None, *,
              count_form: bool = True) -> list[tuple[str, int]]:
    """没认领够两个独立源的断言：[(那句话, 现在有几个源)]。

    认领的写法：`{"<把那句话抄进键里>": "…核过的记录… https://A/… ；https://B/…"}`，
    键里**含着**命中的那几个字就算认领到它（和竖版短片那条闸原来的口径一样）。
    """
    claims = claims if isinstance(claims, dict) else {}
    missing = []
    for phrase in claim_phrases(texts, count_form=count_form):
        hosts: set[str] = set()
        for key, value in claims.items():
            if phrase in str(key):
                hosts |= claim_hosts(value)
        if len(hosts) < 2:
            missing.append((phrase, len(hosts)))
    return missing


def problem_text(missing: list[tuple[str, int]], where: str) -> str:
    """报错正文：说清是哪几句、去哪儿认领、怎么认领。"""
    return (
        "这几句是**全称断言**，一个反例就能推翻——必须在 " + where + " 里\n"
        "认领**两个独立源**的穷举出处（各带 URL），而且要按断言本身的粒度逐行核：\n"
        + "".join(f"  · {p}（现在只有 {n} 个源）\n" for p, n in missing)
        + '  {"<把那句话抄进来>": "…核过的记录… https://A/… ；https://B/…"}\n'
        "⚠️ **断言的粒度 ≤ 查询的粒度**：说「轮次」就要查到轮次那一列。\n"
        "  `chwalinska-gibson` 就是这么错的——「场地＋级别」的 6 胜 4 负分不出\n"
        "  Q1/Q2 和 R32/R16，而轮次就在同一张表里；而第二个源（维基引 WTA 官方标题\n"
        "  「…beats Marino for first hard-court win」）一句话就能推翻它。\n"
        "⚠️ **计数式**（「一共只进过三次决赛，三次全部拿下」）是同一族：夺冠 N 次是闭集，\n"
        "  进过 N 次决赛／交手 N 次是开集，多输一次这句话就错（`wawrinka-wildcard` 那次）。\n"
        "  能用夺冠数说清楚的，别改用决赛数说。")


_QUOTED = re.compile(r"「[^」]*」|“[^”]*”|『[^』]*』|\"[^\"\n]*\"")


def without_quotes(text: str) -> str:
    """去掉引号里的话——那是受访者说的，不是我们的断言，出处是他本人。

    ⚠️ 只给采访线用。竖版短片那条闸的面**照旧不去引号**（它的 `quote` 段是转播
    解说的原声，一直在扫描面里，存量也都按这个口径认领过），别顺手改宽改窄。
    """
    return _QUOTED.sub("", str(text or ""))


def interview_texts(spec: dict) -> list[str]:
    """采访线的扫描面：「我们的话」（push / takeaway / cover），去掉引语。

    ⚠️ **不扫小红书正文、不扫 `zh` 字幕行**：`zh` 是受访者的话的译文；正文那一面
    竖版短片的闸也不扫（`build_match_reel.spec_outward_text` 不含 xhs），两条线
    口径一致，要扩一起扩。
    """
    from spec_wording import interview_outward_texts  # noqa: PLC0415

    return [without_quotes(t) for t in interview_outward_texts(spec)]


def interview_problem(spec: dict, slug: str) -> str | None:
    """采访 spec 的全称断言没认领够两个源 → 报错正文；合格或在存量表里 → None。"""
    if slug in INTERVIEW_LEGACY:
        return None
    missing = unsourced(interview_texts(spec), spec.get("_claims"))
    if not missing:
        return None
    return problem_text(missing, f"specs/interviews/{slug}.json 的 `_claims`")
