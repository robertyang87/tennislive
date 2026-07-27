"""筛选层：关键场次 + 中国球员（且必须是受访者，不是被打败的对手）。

这一层的错误比采集层更贵：采集多收了顶多占点空间，**推送推错了人就不看了**。
所以宁可漏推也不误推——解析不出轮次的不当关键场次。
"""

from __future__ import annotations

import pytest

from tools.oncourt_feed import KEY_ROUNDS, cn_hit, load_cn, parse_round, pick


@pytest.fixture(scope="module")
def pats():
    return load_cn()[1]


def rnd(title, round_field=""):
    return parse_round({"title": title, "round": round_field})


# 各家写法差得很远，全部取自实扫标题
@pytest.mark.parametrize("title,want", [
    ("Jannik Sinner On-Court Interview | Final | Rome 2026", "决赛"),
    ("Casper Ruud On-Court Interview | Semifinal | Rome 2026", "半决赛"),
    ("Luciano Darderi On-Court Interview | Quarterfinal | Rome 2026", "四分之一决赛"),
    ("Post-Match Interview: Andrey Rublev after QF of 2026 Dubai", "四分之一决赛"),
    ("Post-Match Interview: Tallon Griekspoor after SF of 2026 Dubai", "半决赛"),
    ("Carlos Alcaraz On-Court Interview | Australian Open 2026 Final", "决赛"),
    ('"Today I had to raise my level" | Jannik Sinner | Semi-Finals Post-match '
     "Interview | Wimbledon 2026", "半决赛"),
    ("Xinyu Wang On-Court Interview | Australian Open 2026 Third Round", "第三轮"),
    ("Jannik Sinner On-Court Interview | Round 4 | Rome 2026", "十六强"),
])
def test_round_parsing(title, want, pats):
    assert rnd(title) == want


def test_semifinal_must_beat_final():
    """`Semi-Finals` 里含 `Final`，模式顺序反了半决赛会被判成决赛。

    这不是假想——温网的写法就是 `Semi-Finals Post-match Interview`，
    Dubai 是 `after SF of`。顺序错了这两家的半决赛会全部误标成决赛，
    然后混进"关键场次"里推出去。
    """
    assert rnd("Semi-Finals Post-match Interview | Wimbledon 2026") == "半决赛"
    assert rnd("| SF | Dubai 2026") == "半决赛"
    assert rnd("Final | Rome 2026") == "决赛"


def test_round_field_wins_over_title():
    """tennistv.com 自带 metadataRound，比标题可靠，要优先用。"""
    assert rnd("Merida Elated to Win First ATP Tour Title", "Final") == "决赛"
    assert rnd("Darderi ready for final!", "SF") == "半决赛"


def test_unparseable_round_is_not_a_key_match():
    """解析不出轮次就不算关键场次——宁可漏推也不误推。"""
    assert rnd("Wawrinka is honoured in Estoril") is None
    assert rnd("Wawrinka is honoured in Estoril") not in KEY_ROUNDS


# 中国球员：受访者 vs 被打败的对手
def test_chinese_player_as_interviewee(pats):
    for title, zh in [
        ("Zhizhen Zhang On-Court Interview | United Cup 2026 Group B", "张之臻"),
        ("Xinyu Wang On-Court Interview | Australian Open 2026 Third Round", "王欣瑜"),
        ('On-Court Interview: Zheng Qinwen says "pressure is a privilege"', "郑钦文"),
    ]:
        hit = cn_hit(title, pats)
        assert hit, title
        assert hit[0]["zh"] == zh
        assert hit[1] is True, f"应判为受访者：{title}"


def test_chinese_player_as_beaten_opponent_is_not_the_interviewee(pats):
    """真实误收：中国球员在标题里，但是**被打败的那个**。

    `On-Court Interview: Jasmine Paolini feels 'elated' with her stunning
     win against Sijia Wei 💪`

    韦思佳确实在标题里，但这是 Paolini 赢球后的采访。要的是「中国球员
    赢球后」，方向正好相反，必须剔掉。
    """
    title = ("On-Court Interview: Jasmine Paolini feels 'elated' with her "
             "stunning win against Sijia Wei 💪")
    hit = cn_hit(title, pats)
    assert hit and hit[0]["zh"] == "韦思佳"
    assert hit[1] is False, "作为被打败的对手出现，不该算受访者"


@pytest.mark.parametrize("verb", [
    "against", "beating", "beat", "defeats", "over", "past", "vs", "sees off",
])
def test_beaten_markers(verb, pats):
    hit = cn_hit(f"Somebody wins after {verb} Qinwen Zheng at the Open", pats)
    assert hit and hit[1] is False, verb


def test_name_order_both_ways(pats):
    """标题里 `Qinwen Zheng` 和 `Zheng Qinwen` 两种写法都出现过。"""
    for t in ["Qinwen Zheng On-Court Interview | Final",
              "Zheng Qinwen On-Court Interview | Final"]:
        hit = cn_hit(t, pats)
        assert hit and hit[0]["zh"] == "郑钦文", t


def test_non_mainland_lookalikes_are_excluded(pats):
    """Ann Li（美国）、Lulu Sun（新西兰）、谢淑薇（中华台北）不是中国大陆球员。

    只匹配姓会把她们全收进来——Li / Sun / Wu 这些姓在名单里到处都是，
    所以匹配必须用全名，且名单里明确列了排除项。
    """
    for t in ["Ann Li On-Court Interview | Final",
              "Lulu Sun On-Court Interview | Wimbledon 2026",
              "Su-Wei Hsieh On-Court Interview | Final"]:
        assert cn_hit(t, pats) is None, t


def test_pick_requires_key_round_or_chinese_interviewee(pats):
    items = {
        "a": {"id": "a", "title": "Jannik Sinner On-Court Interview | Final | Rome 2026",
              "url": "u", "source": "s"},
        "b": {"id": "b", "title": "Xinyu Wang On-Court Interview | Australian Open 2026 "
                                  "Third Round", "url": "u", "source": "s"},
        "c": {"id": "c", "title": "Somebody On-Court Interview | Round 2 | Rome 2026",
              "url": "u", "source": "s"},
        "d": {"id": "d", "title": "Paolini feels elated with her win against Sijia Wei",
              "url": "u", "source": "s"},
    }
    got = {r["id"] for r in pick(items, pats)}
    assert "a" in got, "决赛属关键场次"
    assert "b" in got, "中国球员即使非关键轮次也要"
    assert "c" not in got, "普通第二轮且无中国球员，不要"
    assert "d" not in got, "中国球员是被打败的对手，不要"


def test_only_cn_drops_key_matches_without_chinese_players(pats):
    items = {
        "a": {"id": "a", "title": "Jannik Sinner On-Court Interview | Final | Rome 2026",
              "url": "u", "source": "s"},
        "b": {"id": "b", "title": "Xinyu Wang On-Court Interview | Third Round",
              "url": "u", "source": "s"},
    }
    got = {r["id"] for r in pick(items, pats, only_cn=True)}
    assert got == {"b"}


def test_cn_roster_matches_the_repo_translation_table():
    """译名唯一出处是 src/tennislive/zh/players.py，名单不能另写一套。

    踩过的原型是把 Rybakina 写成"里巴金娜"发出去，而表里一直写着莱巴金娜。
    这里把两边钉死，防止名单里的中文名和表里对不上。
    """
    import sys
    sys.path.insert(0, "src")
    from tennislive.zh.players import PLAYER_ZH

    for p in load_cn()[0]:
        if p["en"] in PLAYER_ZH:
            assert PLAYER_ZH[p["en"]] == p["zh"], (
                f"{p['en']}：名单写 {p['zh']}，译名表写 {PLAYER_ZH[p['en']]}")
