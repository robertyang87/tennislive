"""筛选层：关键场次 + 中国球员（且必须是受访者，不是被打败的对手）。

这一层的错误比采集层更贵：采集多收了顶多占点空间，**推送推错了人就不看了**。
所以宁可漏推也不误推——解析不出轮次的不当关键场次。
"""

from __future__ import annotations

import pytest

from tools.oncourt_feed import KEY_ROUNDS, cn_hit, load_cn, parse_round, pick


@pytest.fixture(scope="module")
def pats():
    """cn_hit 现在要 (全名, 姓氏, 排除) 三套模式。"""
    return load_cn()[1:]


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
    """同姓但不是中国大陆球员的，必须挡住。

    开了姓氏匹配之后这条变成硬需求：Michael Zheng 是美国人、Lulu Sun 是
    新西兰人、Ann Li 是美国人、谢淑薇是中华台北，他们的姓全在名单里。
    消歧靠 cn_players.json 的 excluded_full，且必须在姓氏匹配**之前**判。
    """
    for t in ["Ann Li On-Court Interview | Final",
              "Lulu Sun On-Court Interview | Wimbledon 2026",
              "Su-Wei Hsieh On-Court Interview | Final",
              "Michael Zheng On-Court Interview | Australian Open 2026 First Round",
              "An emotional Lulu Sun after knocking out Raducanu | On-court Interview"]:
        assert cn_hit(t, pats) is None, t


def test_surname_only_titles_are_caught():
    """只写姓的标题必须收——漏的正是最关键的那几条。

    实测漏过：
      `Zheng Quarter-final post-match interview | Roland-Garros 2025`
          郑钦文法网八强，标题只有姓
      `Zhu/Zhang On-Court Interview | United Cup 2026 Group B`
          双打配对，写两个姓
      `Zheng Post-Match Interview: "Finding My Rhythm" vs Kenin | Madrid 2026`

    只认全名时这三条全丢，中国球员条目从 7 掉到 4。
    姓氏命中时**不断言是哪一位**，标 surname_only 交人工确认。
    """
    rules = load_cn()[1:]
    for t in ["Zheng Quarter-final post-match interview | Roland-Garros 2025",
              "Zhu/Zhang On-Court Interview | United Cup 2026 Group B",
              'Zheng Post-Match Interview: "Finding My Rhythm" vs Kenin | Madrid 2026']:
        hit = cn_hit(t, rules)
        assert hit, t
        assert hit[0].get("surname_only"), f"只有姓，不该断言具体是谁：{t}"


def test_full_name_wins_over_surname():
    """标题里有全名时要认全名，不能退化成姓氏匹配的『待确认』。"""
    rules = load_cn()[1:]
    hit = cn_hit("Zheng Qinwen On-Court Interview | Final", rules)
    assert hit and hit[0]["zh"] == "郑钦文"
    assert not hit[0].get("surname_only")


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


# 双打识别：只要单打，双打不推
DOUBLES = [
    "Zhu/Zhang On-Court Interview | United Cup 2026 Group B",
    "Collins/Harrison On-Court Interview | 2025 US Open Round 1",
    "Kawa/Zielinski On-Court Interview | United Cup 2026 Group E",
    "Alfie Hewett & Gordon Reid: Wheelchair Doubles Final Post-Match Interview | Wimbledon",
    "Men's Doubles Trophy Ceremony | Australian Open 2026",
]

# **单打**，但球员在采访里谈到了双打——不能因为出现 doubles 就误杀
SINGLES_MENTIONING_DOUBLES = [
    '"I need a crash course in doubles" | Emma Raducanu | Third round On-court Interview',
    "Playing her former doubles partner | Iga Swiatek | On-Court Interview | Wimbledon",
    "Why she'll play doubles with Andy | Emma Raducanu | Second round On-court Interview",
]


@pytest.mark.parametrize("title", DOUBLES)
def test_doubles_detected(title):
    from tools.oncourt_feed import is_doubles
    assert is_doubles({"title": title}), title


@pytest.mark.parametrize("title", SINGLES_MENTIONING_DOUBLES)
def test_singles_players_talking_about_doubles_are_not_filtered(title):
    """光秃秃的 `doubles` 不能当双打判据。

    库里三条真实标题都是**单打**采访，只是球员聊到了双打。按词一刀切
    会把它们全杀掉。所以判据是配对写法（`Zhu/Zhang`）和带限定词的
    （`Wheelchair Doubles`、`Men's Doubles`），不是这个词本身。
    """
    from tools.oncourt_feed import is_doubles
    assert not is_doubles({"title": title}), title


def test_tennistv_match_type_beats_the_title():
    """tennistv.com 自带 matchType，比从标题猜可靠，要优先用。"""
    from tools.oncourt_feed import is_doubles
    assert not is_doubles({"title": "A/B On-Court Interview", "matchType": "singles"})
    assert is_doubles({"title": "Sinner On-Court Interview", "matchType": "doubles"})


def test_pick_drops_doubles_by_default(pats):
    items = {
        "s": {"id": "s", "title": "Jannik Sinner On-Court Interview | Final | Rome 2026",
              "url": "u", "source": "x"},
        "d": {"id": "d", "title": "Bolelli/Vavassori On-Court Interview | Final | Rome 2026",
              "url": "u", "source": "x"},
    }
    assert {r["id"] for r in pick(items, pats)} == {"s"}
    assert {r["id"] for r in pick(items, pats, include_doubles=True)} == {"s", "d"}


# 不属于 ATP / WTA 巡回赛的赛事，一律不推
NON_TOUR = [
    "Roger Federer on-court interview (Final) | Mastercard Hopman Cup 2019",
    "Taylor Fritz On-Court Interview | Laver Cup 2025 Match 12",
    '"My level goes up in the Davis Cup" | On-court Interview | Spain v Germany | 2025 Davis Cup',
    "Anna Danilina | On-court Interview | 2023 Billie Jean King Cup",
]

# United Cup 属巡回赛，不能连它一起砍
UNITED_CUP = [
    "Zhizhen Zhang On-Court Interview | United Cup 2026 Group B",
    "Xinyu Gao's On-Court Interview | United Cup 2025 Group E",
    "Hubert Hurkacz On-Court Interview | United Cup 2026 Final",
]


@pytest.mark.parametrize("title", NON_TOUR)
def test_non_tour_events_filtered(title):
    from tools.oncourt_feed import is_tour_event
    assert not is_tour_event({"title": title}), title


@pytest.mark.parametrize("title", UNITED_CUP)
def test_united_cup_is_a_tour_event(title):
    """United Cup 是 ATP 与 WTA 官方联办、计双方排名积分、在两边日历上。

    它形式上是团体赛，容易被连坐砍掉，但它属巡回赛。而且它是中国球员
    场上采访的重要来源——库里 6 条中国球员条目有 2 条出自这里
    （张之臻、高馨妤），砍掉会让本就稀少的中国球员再少三分之一。
    """
    from tools.oncourt_feed import is_tour_event
    assert is_tour_event({"title": title}), title


def test_pick_drops_non_tour_by_default(pats):
    items = {
        "t": {"id": "t", "title": "Jannik Sinner On-Court Interview | Final | Rome 2026",
              "url": "u", "source": "x"},
        "u": {"id": "u", "title": "Hurkacz On-Court Interview | United Cup 2026 Final",
              "url": "u", "source": "x"},
        "l": {"id": "l", "title": "Taylor Fritz On-Court Interview | Laver Cup 2025 Final",
              "url": "u", "source": "x"},
    }
    got = {r["id"] for r in pick(items, pats)}
    assert got == {"t", "u"}, "拉沃尔杯该滤掉，United Cup 该留下"
    assert {r["id"] for r in pick(items, pats, include_team=True)} == {"t", "u", "l"}


@pytest.mark.parametrize("verb", [
    "overcomes", "overcame", "outlasts", "stuns", "upsets", "dispatches",
    "topples", "halts", "ends",
])
def test_second_batch_beaten_verbs(verb, pats):
    """败方词表是逐条从真实误收补出来的，别凭空精简。

    第二批的起因：`Musetti overcomes Bu in Monte Carlo` —— 布云朝克特是输的
    那个，这是 Musetti 赢球后的采访。第一批词表里没有 `overcomes`，
    它就被当成「布云朝克特赢球后的采访」推出去了。
    """
    hit = cn_hit(f"Somebody wins after {verb} Qinwen Zheng at the Open", pats)
    assert hit and hit[1] is False, verb


def test_surname_hits_that_are_real_interviewees(pats):
    """tennistv 的标题只写姓，这几条是真的中国球员受访者，不能误杀。"""
    for t in ["Wu pays tribute to Monfils after victory",
              "Shang comes though in epic contest!",
              "Home hero Bu progresses into second round"]:
        hit = cn_hit(t, pats)
        assert hit and hit[1] is True, t


def test_outcome_words_count_as_the_final():
    """搬运号写 `Winner` / `Champion` / `Finalist`，不写 `Final`。

    不认这几个词的代价极大——**冠军那条采访是最该推的一条**。实测 WTA
    500/1000 的决赛条目几乎全靠它们才认得出来：改之前十三个赛事里
    只有一个能认出决赛，改之后十二个都能。
    """
    from tools.oncourt_feed import parse_round

    for title in [
        "Elena Rybakina Winner Porsche GP '26",
        "Jessica Pegula Winner Charleston '26",
        "Linda Noskova Winner Berlin 2026",
        "Karolina Muchova Winner Qatar '26",
        "Jannik Sinner Champion Wimbledon 2026",
        "Petra Marcinko Champion Rabat 2026",
        "The new Wimbledon Champion | Jannik Sinner | Final On-Court Interview | Wimbledon 2025",
        "Victoria Mboko Finalist Qatar '26",
        "Emma Raducanu Finalist London '26",
        '"Today is still a good day" | Beaten Finalist Jasmine Paolini | On-court Interview',
    ]:
        assert parse_round({"title": title}) == "决赛", title


def test_outcome_words_describing_the_opponent_are_not_the_final():
    r"""同样几个词也大量用来**描述对手**，那不是轮次。

    反例逐条从库里挑出来的，不是编的：`Defending champion Sinner up and
    running in Shanghai` 是他刚开赛那场。

    还有一条更要命的：迪拜赛事全名就叫 `Dubai Duty Free Tennis
    Championships`——库里 126 条含 champion 的有 116 条是它，
    `\bchampions?\b` 不加 `(?!ship)` 就全成决赛了。
    """
    from tools.oncourt_feed import parse_round

    for title, expect in [
        ("Defending champion Sinner up and running in Shanghai", None),
        ("Former champion Evans stuns Musetti", None),
        ("Sonay Kartal beats Grand-Slam Winner | On-Court Interview", None),
        ("2022 finalist Ruud advances in Miami", None),
        ("Cerundolo conquers last year's finalist Jarry", None),
        ("Bergs stuns former finalist Rublev", None),
        # 赛事全名里的 Championships，一条都不能当决赛
        ("Andrey Rublev - Post-Match Interview - R2 2021 Dubai Duty Free Tennis Championships",
         "第二轮"),
        ("Alexei Popyrin | Post-Match Interview | R1 | 2025 Dubai Duty Free Tennis Championships",
         "第一轮"),
        ("Anna Kalinskaya – Semifinals Post-Match Interview – 2024 Dubai Duty Free Tennis "
         "Championships", "半决赛"),
        # 明确轮次要压过结果词：这条写着 First Round
        ("How he beat a Grand Slam Champion | Benjamin Bonzi | First Round On-Court Interview",
         "第一轮"),
    ]:
        assert parse_round({"title": title}) == expect, title


def test_r32_r64_are_labelled_but_deliberately_imprecise():
    """R32 / R64 / R128 **换算不出第几轮**，因为签表大小不写在标题里。

    R32 在 128 签是第三轮、64 签是第二轮、32 签是第一轮。所以给一个粗标签
    `早轮`，别硬猜。反正都不是关键轮次，但标上之后缺口报告里就不会再算成
    「判不出轮次」——库里这样的有 88 条。
    """
    from tools.oncourt_feed import KEY_ROUNDS, parse_round

    for title in ["Lilli Tagger R32 Linz '26", "Coco Gauff R64 Rome '26",
                  "Barbora Krejcikova R128 Rome '26"]:
        assert parse_round({"title": title}) == "早轮", title
    assert "早轮" not in KEY_ROUNDS, "早轮不是关键轮次，不能进推送口径"


def test_every_real_outcome_word_title_in_the_store_is_judged_correctly():
    """**全量校验，不抽样。** 库里每一条含结果词的标题都过一遍。

    这条规则是从「标题正则栽过两次」之后写的，所以不再拿几个样本了事：
    描述对手的写法必须一条都不被判成决赛。
    """
    import json
    import re

    from tools.oncourt_feed import STORE, parse_round

    with STORE.open(encoding="utf-8") as fh:
        items = json.load(fh)["items"]
    descr = re.compile(r"defending champion|former champion|former finalist"
                       r"|grand.slam (?:champion|winner)|\d{4} finalist"
                       r"|last year's finalist", re.I)
    wrong = [v["title"] for v in items.values()
             if descr.search(v["title"]) and parse_round(v) == "决赛"]
    assert wrong == [], f"描述对手却被判成决赛：{wrong}"


def test_qualifying_final_is_not_the_tournament_final():
    """`final round qualifying` 里有 final，但那是**资格赛末轮**，不是决赛。

    实测 9 条温网资格赛全被判成了温网决赛——`\\bfinals?\\b` 一视同仁。
    所以资格赛排在 `_ROUNDS` 最前面，先拦下来。
    """
    from tools.oncourt_feed import KEY_ROUNDS, parse_round

    for title in [
        "Bianca Andreescu interview after final round qualifying at 2026 Wimbledon",
        "UPSET! Oliver Tarvet (719) interview after final round qualifying win at 2025 Wimbledon",
        "Darja Semeņistaja interview after 2nd round qualifying win at 2026 Wimbledon",
        "Dan Evans interview after 2nd round qualifying loss at 2026 Wimbledon",
    ]:
        assert parse_round({"title": title}) == "资格赛", title
    assert "资格赛" not in KEY_ROUNDS, "资格赛不能进推送口径"

    # 正赛的决赛不受影响
    assert parse_round({"title": "Carlos Alcaraz On-Court Interview | Australian Open 2026 Final"}) \
        == "决赛"


def test_ordinal_round_forms_are_recognised():
    """`2nd round` 和 `second round` 是同一件事，两种都得认。

    Edimator 那种源全写序数——只认英文单词的话，84 条非资格赛条目里
    **漏 69 条**，全部落到「判不出轮次」。
    """
    from tools.oncourt_feed import parse_round

    for title, expect in [
        ("Alex Eala interview after 2nd round win at 2026 Wimbledon", "第二轮"),
        ("Tyra Caterina Grant interview after 1st round win at 2026 Wimbledon", "第一轮"),
        ("Alexander Bublik interview after 3rd round win at 2026 Wimbledon", "第三轮"),
        ("Jan-Lennard Struff interview after 4th round win at 2026 Wimbledon", "十六强"),
        # 英文单词写法照旧
        ("Emma Raducanu | Second round On-court Interview | Wimbledon 2026", "第二轮"),
    ]:
        assert parse_round({"title": title}) == expect, title


def test_winner_interview_is_a_genre_label_not_a_round():
    """`winner interview` 是**体裁标签**，不是「决赛」。

    巴斯塔德官方频道写 `Andrea Pellegrino winner interview at Nordea Open 2026`
    ——意思是「赢家采访」。而搬运号写 `Elena Rybakina Winner Porsche GP '26`
    才是「冠军」。**同一个词，隔一个 interview 就换了意思。**
    """
    from tools.oncourt_feed import parse_round

    assert parse_round({"title": "Andrea Pellegrino winner interview at Nordea Open 2026"}) is None
    assert parse_round({"title": "Nuno Borges winner interview - R32 - Nordea Open 2026"}) == "早轮"
    assert parse_round({"title": "Andrey Rublev - R16 - Winner interview - Nordea Open 2026"}) \
        == "十六强"
    # 冠军那一档不受影响
    assert parse_round({"title": "Elena Rybakina Winner Porsche GP '26"}) == "决赛"
    assert parse_round({"title": "Jessica Pegula Winner Charleston '26"}) == "决赛"
