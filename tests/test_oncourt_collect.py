"""场上采访采集器的标题归类规则。

要的只有一类：**赛后直接在场上接受采访**（主持人拿麦上场问、球员站着答）。
颁奖礼致辞、冠军演讲是"讲"不是"接受采访"，媒体间发布会更是另一回事——
两者都必须归到别的类去，不能混进 oncourt。

标题全部取自实扫结果，别改成想当然的写法：各家赛事叫法差得很远，
上海写 `Reacts After`，马德里写西语 `Entrevista con`，
印第安维尔斯和华盛顿只发 `Press Conference`。
"""

from __future__ import annotations

import pytest

from tools.collect_oncourt_interviews import classify, compile_rules, load_sources


@pytest.fixture(scope="module")
def rules():
    return compile_rules(load_sources())


def tag(title, rules):
    return classify(title, rules)


# 唯一要收的一类：场上接受采访
ONCOURT = [
    "Jannik Sinner On-Court Interview | Final | Rome 2026",
    "Luciano Darderi On-Court Interview | Quarterfinal | Rome 2026",
    "Carlos Alcaraz On-Court Interview | Australian Open 2026 Final",
    "Elena Rybakina On-Court Interview | Australian Open 2026 Final",
    "Jannik Sinner reacts to retaining his Championship | Final Post-Match Interview | Wimbledon 2026",
    "Venus Williams Post Match Interview | 2025 Mubadala DC Citi Open",
    "Oda's brilliant interview after winning Wheelchair Singles | Post-match Interview | Wimbledon 2026",
]

# 是赛后在场上讲，但是"致辞"不是"接受采访"——默认不收
CEREMONY = [
    "Quentin Halys Championship Speech | 2026 Kitzbuhel",
    "Maria Sakkari Finalist Speech | 2026 Athens",
    "Madison Keys champion speech | 2026 Eastbourne",          # 小写也要认
    "Jannik Sinner Trophy & Speech | Rome 2026",
    "Men's Singles Trophy Ceremony | Carlos Alcaraz v Novak Djokovic | Australian Open 2026",
    '"Mum left a couple of times!" | Jannik Sinner Champion\'s Dinner Speech | Wimbledon 2026',
    "Men's singles final post-match ceremony | Roland-Garros 2026",
]

# 确实是赛后球员讲话，但标题既分不出场上/媒体间，也分不出采访/致辞
MAYBE = [
    "Valentin Vacherot Reacts After Becoming The Shanghai Champion | Rolex Shanghai Masters 2025",
    "Holger Rune Reacts To Victory Over Baez | Rolex Shanghai Masters 2025",
    "Coco Gauff reacts to EPIC tiebreak comeback to reach 3rd round | 2026 Wimbledon",
    "Entrevista con Jannik Sinner, campeón del #MMOPEN 2026",
    "Marta Kostyuk is crowned champion at #MMOPEN 2026",
]

# 命中了模式但不是赛后讲话，靠 exclude 挡掉
EXCLUDED = [
    "Novak Djokovic Reacts To Final Draw | Pre-Tournament Press Conference",
    "Sinner's Championship Speech Breakdown | The Big T Podcast",
    "Wimbledon Final Preview: Championship Speech Predictions",
]

# 压根不该命中：发布会是另一类素材，有 ASAP Sports 的人工文字稿，别混进来
MISSES = [
    "'A great achievement' | Jannik Sinner | Champion's Press Conference | BNP Paribas Open",
    "Iga Swiatek | Quarterfinals Press Conference | 2025 Cincinnati Open",
    "Press conference with Jannik Sinner // #MMOPEN 2026",
    "Frances Tiafoe | Post Match Press Conference | 2025 Mubadala Citi DC Open",
    "Andrey Rublev vs Tommy Paul Highlights | Rolex Shanghai Masters 2023",
    "Inside The Tour | 2025 Internazionali BNL d'Italia",
]


@pytest.mark.parametrize("title", ONCOURT)
def test_oncourt(title, rules):
    assert tag(title, rules) == "oncourt", title


@pytest.mark.parametrize("title", CEREMONY)
def test_ceremony_is_not_oncourt(title, rules):
    assert tag(title, rules) == "ceremony", title


@pytest.mark.parametrize("title", MAYBE)
def test_maybe(title, rules):
    assert tag(title, rules) == "maybe", title


@pytest.mark.parametrize("title", EXCLUDED)
def test_excluded(title, rules):
    assert tag(title, rules) == "excluded", title


@pytest.mark.parametrize("title", MISSES)
def test_press_conference_not_collected(title, rules):
    assert tag(title, rules) is None, title


def test_post_match_ceremony_beats_post_match_interview(rules):
    """`post-match ceremony` 和 `post-match interview` 只差一个词，顺序不能反。

    法网的 `Men's singles final post-match ceremony` 是 18–23 分钟的完整颁奖礼；
    温网的 `Final Post-Match Interview` 才是场上那 3 分钟。判 ceremony 必须
    先于判 oncourt，否则颁奖礼会被当成场上采访收进来。
    """
    assert tag("Men's singles final post-match ceremony | Roland-Garros 2026", rules) == "ceremony"
    assert tag("Final Post-Match Interview | Wimbledon 2026", rules) == "oncourt"


def test_podcast_reaction_never_reaches_exclude(rules):
    """`reacts to` 后面跟的不是一场球时，前瞻就该拦下，轮不到 exclude。

    这条是从一次真实误报里来的：`Henry Patten Reacts to the ATP's
    Controversial Doubles Proposal | The Big T Podcast` 一度被收进结果。
    收紧前瞻（要求近处出现 champion/final/win/victory 这类词）之后，
    它在第一道就被挡住，返回 None 而不是 excluded。
    """
    title = ("Henry Patten Reacts to the ATP's Controversial Doubles Proposal "
             "| The Big T Podcast")
    assert tag(title, rules) is None


def test_victory_and_possessive_forms(rules):
    r"""两个正则边界 bug 的回归：\b 卡在词中间会静默漏掉整类标题。

    - `victor\b` 匹配不上 `Victory`（词还没结束），上海那批全漏
    - `champions?'?` 要求 s 在 ' 之前，而实际写法是 `Champion's`
    """
    assert tag("Holger Rune Reacts To Victory Over Baez | Shanghai 2025", rules) == "maybe"
    assert tag("Jannik Sinner Champion's Dinner Speech | Wimbledon 2026", rules) == "ceremony"


def test_sources_registry_is_sane():
    cfg = load_sources()
    seen = set()
    for src in cfg["sources"]:
        assert src["url"].startswith("https://"), src["name"]
        assert src["name"] not in seen, f"源名重复：{src['name']}"
        seen.add(src["name"])
        if src.get("fetch") == "tennistv":
            # tennistv.com 的库页固定给 20 条最新且翻页参数无效，
            # scan_depth 对它没有意义，不适用下面的深度下限。
            continue
        # 赛期集中在一年里某几周的赛事，取样太浅会假阴性——澳网在 1 月，
        # 七月里扫近 100 条一条都搜不到，看着就像"澳网不发采访"。
        assert src.get("scan_depth", 150) >= 100, src["name"]


def test_tennistv_site_source_is_present_and_not_the_youtube_channel():
    """tennistv.com 的库和 Tennis TV 的 YouTube 频道是两回事，别搞混。

    YouTube 频道深扫 800 条是 **0 条**场上采访；站上的库逐轮都有
    （R1/QF/SF/Final，0:56–3:27），而且 16/20 免费、4/20 freemium，
    premium 一条都没有。它是唯一系统覆盖 ATP 250 场上采访的来源。
    """
    cfg = load_sources()
    site = [s for s in cfg["sources"] if s.get("fetch") == "tennistv"]
    assert site, "tennistv.com 媒体库是 ATP 250 场上采访的唯一来源，不能去掉"
    assert site[0]["url"].startswith("https://www.tennistv.com/")

    yt = [s for s in cfg["sources"]
          if s["name"] == "Tennis TV" and "youtube.com" in s["url"]]
    assert yt, "Tennis TV 的 YouTube 频道要单独留着，记录它 0 条的结论"
    assert yt[0]["url"] != site[0]["url"]


def test_rome_is_present_and_deep():
    """罗马是唯一每一轮都单发场上采访的赛事，它掉了就没有分轮次的语料了。"""
    cfg = load_sources()
    rome = [s for s in cfg["sources"] if "Rome" in s["name"]]
    assert rome, "罗马每一轮都发 On-Court Interview，是场上语料的主力，不能去掉"
