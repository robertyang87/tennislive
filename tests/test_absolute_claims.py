"""全称断言那道闸：三条线一份词表，计数式按「生涯动词」认。

来路和量法在 `tools/absolute_claims.py` 的 docstring：
- 解说片这条线原来一道闸都没有——`wawrinka-wildcard`「一共只进过三次大满贯决赛，
  三次全部拿下」推了微信才被指出是四次（f58553ef）；
- 计数式按词放宽量过一次是 9 处命中 7 处误伤（tennis-editorial「我本来想把词表放宽，
  是数据把它否掉的」），这次按「生涯动词 ＋ 同一个数说两遍」再量：13 处命中，零误伤。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import absolute_claims as A  # noqa: E402

#: 必须认出来的——全是**生涯／交手**计数（开集，多输一次这句话就错）。
_OPEN_SET = (
    # f58553ef 之前 `wawrinka-wildcard` 第 ④ 屏的原句（打过四次，第四次 2017 法网负纳达尔）
    "他一共只进过三次大满贯决赛，三次全部拿下。",
    "三次交手，中岛此前三次都输——其中一次是今年一月的布里斯班决赛",   # nakashima-medvedev
    "两次打进大满贯决赛，两次都输给德约科维奇。",                   # tsitsipas-royer
    "大满贯的四分之一决赛他去过十次，十次都停在那儿。",             # rublev-virtanen
    "两个人交手过两次，郑钦文两次都输了。",                         # putintseva-bencic
)

#: 不许认的——**这一场之内**的计数（闭集，逐分数据本身就穷举得了），
#: 前五条就是 tennis-editorial 那张「误伤」表，后面是存量里真出现过的同形句。
_IN_MATCH = (
    "决胜盘一共只有四十六个小分",
    "这场球的破发点一共只有四个",
    "上一盘她一共只赢了一局",
    "保发四次全部失败",
    "五场球，她一共只丢了三盘",
    "五次破发点，五次都变成了破发——一个都没浪费。",          # eala-ruse
    "全场两次零比四十，两次都把发球局送了出去。",              # medvedev-zandschulp
    "三次被逼到赛点，三次都扛了过去。",                        # keys-bondar
    "两次拿到盘点，两次都被他救掉。",                          # wu-walton
    # 动词对了、宾语是这一场之内的——存量里没有，写判据时自己造句造出来的
    "两次打进抢七，两次都拿下了。",
    # 比分不是断言：采访线 swiatek-arango 的封面文字当场被老词表误认过
    "斯瓦泰克六比零胜阿朗戈",
)


def test_计数式认得出生涯和交手_认不出这一场之内的计数():
    for text in _OPEN_SET:
        assert A.claim_phrases([text]), f"该认的没认：{text}"
    for text in _IN_MATCH:
        assert not A.claim_phrases([text]), f"误伤了这一场之内的计数：{text} → {A.claim_phrases([text])}"
    # 词表那一档照旧
    assert A.claim_phrases(["硬地的巡回赛正赛，她零胜"]) == ["零胜"]
    # `count_form=False` 只看词表——竖版短片计数式存量表靠它豁免那一句
    assert not A.claim_phrases([_OPEN_SET[0]], count_form=False)


def test_认领要两个不同主机_同一个站点算一个():
    phrase = A.claim_phrases([_OPEN_SET[0]])[0]
    texts = [_OPEN_SET[0]]
    assert A.unsourced(texts, None) == [(phrase, 0)]
    assert A.unsourced(texts, {phrase: "查过了"}) == [(phrase, 0)]
    assert A.unsourced(texts, {phrase: "https://www.atptour.com/a ；https://www.atptour.com/b"}) \
        == [(phrase, 1)]
    assert A.unsourced(texts, {
        phrase: "生涯统计 https://www.atptour.com/x ；2017 法网男单 https://en.wikipedia.org/y",
    }) == []
    # 报错要说出路：去哪儿认领、计数式为什么也算
    msg = A.problem_text([(phrase, 0)], "`explainer._CLAIMS['x']`")
    assert "`explainer._CLAIMS['x']`" in msg and "两个独立源" in msg and "计数式" in msg


# ── 竖版短片 ────────────────────────────────────────────────────────────

def _reel():
    import build_match_reel  # noqa: PLC0415

    return build_match_reel


def test_竖版短片的闸也认计数式_存量表只豁免计数式那一句():
    reel = _reel()
    bad = {"slug": "全新的一条", "segments": [],
           "cover": {"hook": "三次交手，三次都输给了他"}}
    with pytest.raises(reel.ReelError, match="全称断言"):
        reel._absolute_claims_need_a_source(bad)

    legacy = sorted(A.REEL_COUNT_LEGACY)[0]
    # 计数式存量：计数式那一句放行……
    reel._absolute_claims_need_a_source({**bad, "slug": legacy})
    # ……词表那一档照旧要认领（存量表不是整条放行）
    with pytest.raises(reel.ReelError, match="零胜"):
        reel._absolute_claims_need_a_source({
            **bad, "slug": legacy, "cover": {"hook": "三次交手，三次都输 硬地零胜"}})


def test_竖版短片计数式存量表只许减不许加():
    reel = _reel()
    assert len(A.REEL_COUNT_LEGACY) <= 8, "计数式存量 2026-09-27 冻结在 8 条，只许减不许加"
    for slug in sorted(A.REEL_COUNT_LEGACY):
        path = ROOT / "specs" / "reels" / f"{slug}.json"
        assert path.is_file(), f"存量表里的 {slug} 不存在了——过期的名字就是恒真的绿灯"
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert spec.get("slug") == slug
        still = [p for p, _ in A.unsourced(reel.spec_outward_text(spec), spec.get("_claims"))
                 if A.is_count_phrase(p)]
        assert still, f"{slug} 的计数式已经认领了（或者删了），从 REEL_COUNT_LEGACY 里删掉"


# ── 解说片（`explainer._CLAIMS`） ────────────────────────────────────────

def test_解说片的全称断言要在_CLAIMS里认领两个独立源():
    import explainer_preflight as P  # noqa: PLC0415
    from tennislive.video import explainer as E  # noqa: PLC0415

    red = {deck.slug: P.claim_problems(deck)
           for deck in (P.load_deck(slug) for slug in E._SCRIPTS)}
    red = {slug: probs for slug, probs in red.items() if probs}
    assert not red, "\n".join(p for probs in red.values() for p in probs)

    # 存量表自检：名字要在、而且真的还欠着出处
    assert len(A.EXPLAINER_LEGACY) <= 9, "解说片存量 2026-09-27 冻结在 9 条，只许减不许加"
    for slug in sorted(A.EXPLAINER_LEGACY):
        assert slug in E._SCRIPTS, f"{slug} 已经不是字卡稿了，从 EXPLAINER_LEGACY 里删掉"
        deck = P.load_deck(slug)
        assert A.unsourced(P.outward_texts(deck), E._CLAIMS.get(slug)), (
            f"{slug} 已经没有没认领的全称断言了，从 EXPLAINER_LEGACY 里删掉")


def test_解说片写了计数式不认领就红_认领两个源就放行(monkeypatch):
    """f58553ef 那一句原样放回一条**不在存量表里**的稿子上，预检当场红。"""
    import explainer_preflight as P  # noqa: PLC0415
    from tennislive.video import explainer as E  # noqa: PLC0415

    slug = "hawkeye"
    assert slug not in A.EXPLAINER_LEGACY
    beats = list(E._SCRIPTS[slug])
    first = list(beats[0])
    first[3] = first[3] + "他一共只进过三次大满贯决赛，三次全部拿下。"
    monkeypatch.setitem(E._SCRIPTS, slug, (tuple(first), *beats[1:]))
    red = P.claim_problems(P.load_deck(slug))
    assert red and "进过三次" in red[0], red

    phrase = A.claim_phrases(["他一共只进过三次大满贯决赛，三次全部拿下。"])[0]
    monkeypatch.setitem(E._CLAIMS, slug, {phrase: "https://www.atptour.com/a"})
    assert P.claim_problems(P.load_deck(slug)), "一个源不够"
    monkeypatch.setitem(E._CLAIMS, slug, {
        phrase: "https://www.atptour.com/a ；https://en.wikipedia.org/b"})
    assert P.claim_problems(P.load_deck(slug)) == []


# ── 采访线 ──────────────────────────────────────────────────────────────

def _interview_specs():
    for path in sorted((ROOT / "specs" / "interviews").glob("*.json")):
        if path.name.endswith(".draft.json"):
            continue
        yield path, json.loads(path.read_text(encoding="utf-8"))


def test_采访线的全称断言要认领_引号里的是受访者的话():
    red, seen = [], 0
    for path, spec in _interview_specs():
        seen += 1
        problem = A.interview_problem(spec, path.stem)
        if problem:
            red.append(f"{path.name}：{problem.splitlines()[2]}")
    assert seen >= 50, f"只扫到 {seen} 份采访 spec，扫描面塌了"
    assert not red, "\n".join(red)

    assert len(A.INTERVIEW_LEGACY) <= 2, "采访线存量 2026-09-27 冻结在 2 条，只许减不许加"
    for slug in sorted(A.INTERVIEW_LEGACY):
        path = ROOT / "specs" / "interviews" / f"{slug}.json"
        assert path.is_file(), f"存量表里的 {slug} 不存在了"
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert A.unsourced(A.interview_texts(spec), spec.get("_claims")), (
            f"{slug} 已经没有没认领的全称断言了，从 INTERVIEW_LEGACY 里删掉")

    ours = {"push": {"lead": "她是本赛季唯一一个八站首战全胜的球员。"}}
    assert A.interview_problem(ours, "全新的一条")
    quoted = {"push": {"lead": "她说：「过去十年我从来没有成功过。」"}}
    assert A.interview_problem(quoted, "全新的一条") is None
    # 注解不算发出去的话
    assert A.interview_problem({"push": {"_why": "上一版写了「唯一一个」"}}, "x") is None


def test_采访线的全称断言在runner的前置检查里就红(tmp_path, monkeypatch):
    """`interview-clip.yml` 的「发布文案前置检查」跑的就是 production_preflight。"""
    import production_preflight as PP  # noqa: PLC0415

    spec = tmp_path / "brand-new-interview.json"
    spec.write_text(json.dumps(
        {"push": {"lead": "他此前六次打进正赛，六次全部首轮出局。"}}, ensure_ascii=False),
        encoding="utf-8")
    copies = []
    monkeypatch.setattr(PP, "check_copy", lambda *a, **k: copies.append(a))
    monkeypatch.setattr(sys, "argv", ["production_preflight.py", "--spec", str(spec),
                                      "--column", "赛后开麦"])
    with pytest.raises(SystemExit, match="全称断言"):
        PP.main()
    assert not copies, "断言那一关要排在文案检查前面，红了就不用再起子进程"

    # 竖版短片那条线不走这一关（它的闸在 validate_spec 里）
    monkeypatch.setattr(sys, "argv", ["production_preflight.py", "--spec", str(spec),
                                      "--column", "赛场之上"])
    PP.main()
    assert copies
