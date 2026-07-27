"""场上采访采集器的标题归档规则。

规则全部来自实扫到的真实标题，别改成想当然的写法：各家赛事叫法差得很远，
上海写 `Reacts After`，马德里写西语 `Entrevista con`，印第安维尔斯只发
`Champion's Press Conference`（那是发布会，不该收）。
"""

from __future__ import annotations

import pytest

from tools.collect_oncourt_interviews import classify, compile_rules, load_sources


@pytest.fixture(scope="module")
def rules():
    return compile_rules(load_sources())


def tag(title, rules):
    return classify(title, *rules)


# 真实标题，扫 Tennis Channel / 罗马 / 四大满贯时抓到的
CONFIDENT = [
    "Quentin Halys Championship Speech | 2026 Kitzbuhel",
    "Maria Sakkari Finalist Speech | 2026 Athens",
    "Madison Keys champion speech | 2026 Eastbourne",          # 小写也要认
    "Jannik Sinner On-Court Interview | Final | Rome 2026",
    "Luciano Darderi On-Court Interview | Quarterfinal | Rome 2026",
    "Jannik Sinner Trophy & Speech | Rome 2026",
    "Men's Singles Trophy Ceremony | Carlos Alcaraz v Novak Djokovic | Australian Open 2026",
    "Jannik Sinner reacts to retaining his Championship | Final Post-Match Interview | Wimbledon 2026",
    '"Mum left a couple of times!" | Jannik Sinner Champion\'s Dinner Speech | Wimbledon 2026',
    "Men's singles final post-match ceremony | Roland-Garros 2026",
]

# 确实是赛后讲话，但标题分不出在场上还是媒体间——要单独一档，不能混进 confident
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
    "Andrey Rublev vs Tommy Paul Highlights | Rolex Shanghai Masters 2023",
    "Inside The Tour | 2025 Internazionali BNL d'Italia",
]


@pytest.mark.parametrize("title", CONFIDENT)
def test_confident(title, rules):
    assert tag(title, rules) == "confident", title


@pytest.mark.parametrize("title", MAYBE)
def test_maybe(title, rules):
    assert tag(title, rules) == "maybe", title


@pytest.mark.parametrize("title", EXCLUDED)
def test_excluded(title, rules):
    assert tag(title, rules) == "excluded", title


@pytest.mark.parametrize("title", MISSES)
def test_press_conference_not_collected(title, rules):
    assert tag(title, rules) is None, title


def test_podcast_reaction_never_reaches_exclude(rules):
    """『reacts to』后面跟的不是一场球时，前瞻就该拦下，轮不到 exclude。

    这条是从一次真实误报里来的：`Henry Patten Reacts to the ATP's
    Controversial Doubles Proposal | The Big T Podcast` 一度被收进结果。
    收紧前瞻（要求近处出现 champion/final/win/victory 这类词）之后，
    它在第一道就被挡住，返回 None 而不是 excluded——**两道都要有，
    但顺序决定了它落在哪一档**，这里把顺序钉住。
    """
    title = ("Henry Patten Reacts to the ATP's Controversial Doubles Proposal "
             "| The Big T Podcast")
    assert tag(title, rules) is None


def test_victory_and_possessive_forms(rules):
    """两个正则边界 bug 的回归：\\b 卡在词中间会静默漏掉整类标题。

    - `victor\\b` 匹配不上 `Victory`（词还没结束），上海那批全漏
    - `champions?'?` 要求 s 在 ' 之前，而实际写法是 `Champion's`
    """
    assert tag("Holger Rune Reacts To Victory Over Baez | Shanghai 2025", rules) == "maybe"
    assert tag("Jannik Sinner Champion's Dinner Speech | Wimbledon 2026", rules) == "confident"


def test_sources_registry_is_sane():
    cfg = load_sources()
    seen = set()
    for src in cfg["sources"]:
        assert src["url"].startswith("https://www.youtube.com/"), src["name"]
        assert src["name"] not in seen, f"源名重复：{src['name']}"
        seen.add(src["name"])
        # 赛期集中在一年里某几周的赛事，取样太浅会假阴性——澳网在 1 月，
        # 七月里扫近 100 条一条都搜不到，看着就像"澳网不发采访"。
        assert src.get("scan_depth", 150) >= 100, src["name"]


def test_tennis_channel_is_present_and_deep():
    """小赛事只有 Tennis Channel 有，它掉了等于整个 250 级别断供。"""
    cfg = load_sources()
    tc = [s for s in cfg["sources"] if "Tennis Channel" in s["name"]]
    assert tc, "Tennis Channel 是唯一覆盖 250 级别小站的源，不能从注册表里去掉"
    assert tc[0]["scan_depth"] >= 200
