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


def test_match_coverage_counts_singles_only():
    """场次覆盖率**只算单打正赛**——分母是单打签表，分子混进双打就是虚高。

    被用户抓到的：澳网深扫新增的 835 条里有 213 条是双打
    （`Kostyuk/Ruse On-Court Interview | Australian Open 2023 Second Round`
    这种斜杠配对），当时报的「100%」是假的。滤掉之后澳网女单 99%、
    美网 85%/84%——**都掉了 6–7 个点**。

    轮椅、青少年、传奇表演赛同理：都不在单打正赛签表里。
    """
    from tools.oncourt_match_coverage import is_main_singles

    for title in [
        "Kostyuk/Ruse On-Court Interview | Australian Open 2023 Second Round",
        "Neal Skupski and Desirae Krawczyk Post-Match Interview | Wimbledon 2022",
        "Men's Doubles Final On-Court Interview | Australian Open 2026",
        "Oda's brilliant interview after winning Wheelchair Singles | Wimbledon 2026",
        "Boys' Singles Final Post-match Interview | Wimbledon 2025",
        "Legends Invitational On-Court Interview | Wimbledon 2024",
    ]:
        assert not is_main_singles({"title": title}), title

    for title in [
        "Carlos Alcaraz On-Court Interview | Australian Open 2026 Final",
        '"I need a crash course in doubles" | Emma Raducanu | Third round On-court Interview',
        "Jannik Sinner | First round On-court Interview | Wimbledon 2026",
    ]:
        assert is_main_singles({"title": title}), title


def test_chinese_player_qualifying_wins_say_so_on_the_card():
    """中国球员的资格赛，卡片上必须写出「资格赛」——**不能看着像正赛**。

    资格赛不是关键轮次，进推送口径只有一条路：中国球员赢了球。
    但卡片标签原来写的是「中国球员就只显示名字」，于是这三条

        布云朝克特 2026 温网资格赛一轮
        王曦雨     2026 温网资格赛一轮
        张帅       2026 温网资格赛二轮

    推出去只写着球员名，和正赛长得一模一样。**而覆盖率的分母是正赛签表，
    根本不含它们**（`rounds_of()` 只到「第一轮」，资格赛不在表里）——
    推的时候当正赛、算的时候不算数，两边对不上。

    只给资格赛加后缀：正赛轮次每条都跟在名字后面就成了噪音，
    而资格赛不写就是误导。两者不对称是故意的。
    """
    from tools.oncourt_feed import tag_of

    zheng = {"zh": "郑钦文"}
    assert tag_of({"cn_player": zheng, "round_zh": "资格赛"}) == "郑钦文 · 资格赛"
    assert tag_of({"cn_player": zheng, "round_zh": "四分之一决赛"}) == "郑钦文"
    assert tag_of({"cn_player": zheng, "round_zh": "决赛"}) == "郑钦文"
    # 没有中国球员时照旧显示轮次
    assert tag_of({"cn_player": None, "round_zh": "半决赛"}) == "半决赛"
    assert tag_of({"cn_player": None, "round_zh": None}) == ""


def test_qualifying_never_counts_toward_main_draw_coverage():
    """资格赛条目一条都不能进场次覆盖率的分子。

    Edimator 的温网 99 条里 **75 条是资格赛**（76%）——它是补温网早轮缺口的
    主力源，但那个「99」大部分不在正赛口径内，真正补上的是 24 条。
    分子若混进资格赛，温网男单会从 61% 虚高上去，而分母（127 场）
    是正赛签表，压根没有资格赛的位置。

    机制是 `coverage()` 里的 `if rd in tbl`——`rounds_of()` 生成的表
    只到「第一轮」。这条测试盯的是**那个机制别被人「顺手补全」**：
    有人看到 `parse_round` 会返回「资格赛」，很容易觉得表里漏了一项。
    """
    from tools.oncourt_match_coverage import rounds_of

    for draw in (128, 96, 64, 56, 32, 28):
        assert "资格赛" not in rounds_of(draw), f"{draw} 签的轮次表里混进了资格赛"

    # 分母只到正赛：128 签逐轮相加正好是 127 场
    assert sum(rounds_of(128).values()) == 127


def test_push_is_called_with_the_real_signature():
    """推送那一行的关键字参数，必须和 `pushplus.push()` 的形参对得上。

    **这条是从一次线上事故里长出来的。** 第一次定时触发（2026-07-27 21:54 UTC）
    整个 run 显示 success，11 个步骤全绿，日志里却躺着：

        TypeError: push() got an unexpected keyword argument 'content'

    50 条待推的一条都没出去。两个错叠在一起才让它变成静默失败：

      ① 调用写的是 `push(token=…, title=…, content=…, template="html")`，
         而形参是 `push(title, html_content, token=None, …)`——
         `content` 和 `template` 都不存在（template 在 push() 内部写死了）
      ② 工作流那一步是 `python ... | tee`，bash 默认报**管道最后一环**的退出码，
         所以 python 崩了照样绿。已加 `set -o pipefail`

    **这就是「查产物不要查信号」的又一次**：run 绿、step 绿，产物是零。

    用 inspect 比签名而不是真的调一次，是因为真调会往用户手机推微信。
    """
    import inspect
    import re

    from tennislive.publish.pushplus import push
    from tools import oncourt_feed

    sig = inspect.signature(push)
    src = inspect.getsource(oncourt_feed.main)
    # **取所有 `push(...)` 里带关键字参数的那一个**，不能拿 re.search 的第一个：
    # 上面的注释里就写着 `push()`，第一次这么写的时候正好匹到它，
    # 捕获组是空的，测试于是报「没把正文传给 push()」——**假阳性**。
    calls = [c for c in re.findall(r"push\(([^)]*)\)", src) if "=" in c]
    assert calls, "oncourt_feed.main 里找不到带参数的 push( 调用"
    kwargs = [k for c in calls for k in re.findall(r"(\w+)\s*=", c)]
    unknown = [k for k in kwargs if k not in sig.parameters]
    assert not unknown, (
        f"push() 没有这些形参：{unknown}；它接受的是 {list(sig.parameters)}")
    # 正文必须传进去——只传 title 的话推出去是一条空消息
    assert "html_content" in kwargs, "没把正文传给 push()，推出去会是空的"


def test_the_push_step_does_not_swallow_a_crash():
    """工作流里推送那一步必须开 `pipefail`，否则 python 崩了也报成功。

    上面那条测试防的是「参数写错」，这条防的是「写错了也看不见」——
    两道都得有。别的步骤故意写了 `|| true`（搜索和缺口对账失败不该拦住推送），
    那些不算数，这里只查推送这一步。
    """
    from pathlib import Path

    wf = Path(__file__).resolve().parent.parent / ".github/workflows/oncourt-interviews.yml"
    text = wf.read_text(encoding="utf-8")
    step = text.split("筛出关键场次与中国球员，推到微信", 1)[1].split("- name:", 1)[0]
    assert "set -o pipefail" in step, "推送这一步没开 pipefail，崩了会被 tee 吞掉"
    assert "oncourt_feed.py --push" in step, "样本取错了段落，这条测试没在看推送步骤"
