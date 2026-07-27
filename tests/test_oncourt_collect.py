"""场上采访采集器的标题归类规则。

要的只有一类：**赛后直接在场上接受采访**（主持人拿麦上场问、球员站着答）。
颁奖礼致辞、冠军演讲是"讲"不是"接受采访"，媒体间发布会更是另一回事——
两者都必须归到别的类去，不能混进 oncourt。

标题全部取自实扫结果，别改成想当然的写法：各家赛事叫法差得很远，
上海写 `Reacts After`，马德里写西语 `Entrevista con`，
印第安维尔斯和华盛顿只发 `Press Conference`。
"""

from __future__ import annotations

import json

import pytest

from tools.collect_oncourt_interviews import (
    classify,
    compile_rules,
    is_tennis,
    load_sources,
)


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


# 综合体育频道上的真实足球标题——它们命中 post-match interview，但不是网球
FOOTBALL = [
    "Arteta reacts to reaching UCL FINAL 🤩 | full post-match interview | UEFA Champions League",
    '"I KNEW we would win" 😤 | Declan Rice full post-match interview | UEFA Champions League',
    '"More, even more" 🤨 | Kompany post-match interview | UEFA Champions League 🎙️',
]


@pytest.mark.parametrize("title", FOOTBALL)
def test_football_matches_the_pattern_but_fails_the_tennis_gate(title, rules):
    """`post-match interview` 是通用体育说法，综合频道上会大量误收。

    真实污染：Amazon Prime Video Sport 深扫 500 条命中 25 条，全是 UEFA 欧冠。
    分类器**照样把它判成 oncourt**——这是对的，正则本来就只看格式；
    拦下来的是 `require_tennis` 那道闸。两件事要分开测，
    否则改坏了任何一边都发现不了。
    """
    assert classify(title, rules) == "oncourt"      # 格式确实是赛后采访
    assert not is_tennis(title, rules)              # 但不是网球


@pytest.mark.parametrize("title", ONCOURT)
def test_real_tennis_titles_pass_the_tennis_gate(title, rules):
    """网球闸不能误伤真条目——它只在 require_tennis 的源上开，但也得准。"""
    assert is_tennis(title, rules), title


def test_general_sport_sources_have_the_tennis_gate_on():
    """综合体育频道必须打 require_tennis，否则足球会灌进库里。"""
    cfg = load_sources()
    general = {"Amazon Prime Video Sport", "TNT Sports", "Wide World of Sports (Nine)"}
    for src in cfg["sources"]:
        if src["name"] in general:
            assert src.get("require_tennis"), f"{src['name']} 是综合体育频道，必须开 require_tennis"


def test_sources_registry_is_sane():
    cfg = load_sources()
    seen = set()
    for src in cfg["sources"]:
        assert src["url"].startswith("https://"), src["name"]
        assert src["name"] not in seen, f"源名重复：{src['name']}"
        seen.add(src["name"])
        if src.get("fetch"):
            # 站点类抓取器（tennistv.com / wtatennis.com）不是按频道翻页的，
            # 页面固定给最新的十几二十条，scan_depth 对它们没有意义，
            # 不适用下面的深度下限。
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


def test_daily_depth_is_much_shallower_than_baseline_depths():
    """日常跑和建基线是两件事，深度不能混用。

    注册表里的 scan_depth 是 600–800，那是**建基线**时为了不漏掉整届赛事
    才要的（美网 300 只得 11 条，600 得 53 条）。但每天拿它重刷一遍历史
    既慢又没意义——新内容永远在频道最前面。

    这里钉住两件事：日常深度显著小于任何一个基线深度；且它没小到会漏掉
    一天的更新（大满贯期间单个频道一天也发不到 60 条）。
    """
    from tools.collect_oncourt_interviews import DAILY_DEPTH

    cfg = load_sources()
    # 只比 YouTube 频道源。站点类抓取器的 scan_depth 是个占位值，
    # 拿它算 min 会把下限拉到 20，断言就永远不成立。
    depths = [s.get("scan_depth", 150) for s in cfg["sources"] if not s.get("fetch")]
    assert DAILY_DEPTH < min(depths), "日常深度应比所有基线深度都小"
    assert DAILY_DEPTH >= 40, "太小会漏掉赛事高峰期一天的更新"


def test_discovery_dedup_recognises_the_same_channel_in_both_url_forms():
    """注册表里同一频道有 @句柄 和 /channel/ID 两种写法，去重要认得出。

    踩过：搜索返回「US Open Tennis Championships」+ /channel/UCXbboag…，
    注册表写的是「US Open」+ @usopen——URL 不同、名字也不同，
    结果每周都把这个已收录的源当成「新发现」重复报一遍。
    """
    from tools.discover_oncourt_sources import already_known, registry_channels

    known_urls, known_names = registry_channels()
    assert already_known("US Open Tennis Championships",
                         "https://www.youtube.com/channel/UCXbboag48Qlr78zzz6SkzkQ",
                         known_urls, known_names)
    assert already_known("Eurosport Tennis", "https://whatever", known_urls, known_names)
    # 真没收录的不能被误判成已知
    assert not already_known("Some Random Fan Channel",
                             "https://www.youtube.com/channel/UCzzz",
                             known_urls, known_names)


def test_tennistv_duration_guard_separates_press_conferences():
    """tennistv 的 videoType=interviews 里混着发布会，靠时长切开。

    实测混进来的 12 条全在 7–23 分钟，而且多是两人同台
    （`Sinner & Lehecka React To Miami Final` 23:11）——场上不会让两个人
    一起站着答，那只可能是媒体间。场上采访实测 40 秒–4 分钟。

    界划在 6 分钟：550 条里 535 条在 1–4 分钟，4–6 分钟只有 2 条，
    所以这个界既能滤掉发布会，又不会误伤真条目。
    """
    from tools.collect_oncourt_interviews import TENNISTV_MAX_SECS

    assert 240 <= TENNISTV_MAX_SECS <= 420, "界要落在场上采访上限和发布会下限之间"
    # 真实条目的时长，都该在界内
    for secs in (39, 92, 127, 208, 235):
        assert secs < TENNISTV_MAX_SECS
    # 真实的发布会时长，都该被挡掉
    for secs in (473, 588, 626, 1391):
        assert secs >= TENNISTV_MAX_SECS


def test_roland_garros_2024_post_match_is_the_press_room():
    """法网频道把**发布会**也写成 post-match interview，只有画面能分。

    抽 32 条法网 `post-match interview` 看缩略图：2024 那批 18 条里 16 条
    画面是新闻发布厅（BNP Paribas 背景板、长桌、绿话筒、矿泉水），
    2025 那批 10 条里 8 条真在场上（手持杆麦、看台、红土）。
    同一个词在同一个频道里隔一年意思就反了，所以按源按年记。

    2026 起法网自己改了写法，明写 `on-court Interview`（23 条），
    这条规则往后碰不到真条目。
    """
    from tools.collect_oncourt_interviews import compile_deny, load_sources

    deny = compile_deny(load_sources())
    rg = deny["Roland-Garros"]
    assert rg, "法网必须有单源黑名单"

    def denied(title):
        return any(p.search(title) for p in rg)

    # 看图确认过是发布会的
    for title in [
        "Sabalenka Round 1 post-match interview | Roland-Garros 2024",
        "Djokovic Round 2 post-match interview | Roland-Garros 2024",
        "Swiatek Semi-final post-match interview | Roland-Garros 2024",
        "Garcia Round 1 post-match interview | Roland-Garros 2024",
        "Thiem Q1 post-match interview | Roland-Garros 2024",
    ]:
        assert denied(title), title

    # 看图确认过真在场上的，一条都不能被这条规则碰到
    for title in [
        "Sinner Round 2 on-court interview | Roland-Garros 2024",
        "Alcaraz Quarter-final on-court interview | Roland-Garros 2024",
        "Hugo Gaston | Round 1 on-court Interview | Roland-Garros 2026",
        "Mirra Andreeva | Semi-final on-court Interview | Roland-Garros 2026",
        "Monfils Round 1 post-match interview | Roland-Garros 2025",
        "Boisson Round 4 post-match interview | Roland-Garros 2025",
    ]:
        assert not denied(title), title

    # 黑名单是**按源**的，不能外溢到别家同样写法的标题上
    for title in [
        "Ugo Humbert Round 2 post-match interview | Rolex Paris Masters 2024",
        "Novak Djokovic | Gentlemen's Singles Final Post-Match Interview | Wimbledon 2024",
    ]:
        assert not denied(title), title


def test_deny_list_only_applies_to_its_own_source():
    """黑名单挂在源名下，别的源取不到——防止哪天顺手写进全局 exclude。"""
    from tools.collect_oncourt_interviews import compile_deny, load_sources

    deny = compile_deny(load_sources())
    assert "Roland-Garros" in deny
    assert deny.get("Wimbledon") is None
    assert deny.get("US Open") is None


def test_wta_dead_page_is_not_collected():
    """列表页挂着链接 ≠ 详情页打得开。

    实测 wtatennis.com 的三条 post-match-interview 详情页全 404，
    而同一张列表页上另外八条视频 8/8 都是 200——不是整站坏了，
    是这几条下架了、链接没撤。收进来就是推给人一个死链。

    **只把 404 当死**：超时、403、429 都是「没问过」，
    那种情况要放过去——这就是「空结果 ≠ 不存在」在可达性上的那一面。
    """
    import subprocess as sp

    from tools.collect_oncourt_interviews import _wta_page_alive

    calls = {}

    def fake_run(cmd, **kw):
        calls["url"] = cmd[-1]
        return sp.CompletedProcess(cmd, 0, stdout=calls["code"], stderr="")

    orig = sp.run
    try:
        sp.run = fake_run
        for code, alive in (("404", False), ("200", True),
                            ("403", True), ("429", True), ("000", True)):
            calls["code"] = code
            assert _wta_page_alive("1", "berlin-post-match-interview-sf-x") is alive, code
    finally:
        sp.run = orig
    assert calls["url"].endswith("/videos/1/berlin-post-match-interview-sf-x")


def test_paris_masters_post_match_is_the_media_zone():
    """巴黎大师赛自己的图卡上就分两种标签，所以标题也得按两种收。

    抽 16 条看图：写 `ON-COURT ITW` 的（德约决赛、鲁内三轮、迪米特洛夫决赛）
    画面在场上；写 `POST-MATCH ITW` / `POST-MATCH INTERVIEW` 的，
    卡佐背后是背景板加长杆麦，辛纳那条是一圈手机怼着的媒体混合区。
    一个频道同时用两种标签，说明这两个词在它那儿不是一回事。

    和罗兰加洛斯是同一个毛病——两个赛事都归法网协会（FFT）办。
    """
    from tools.collect_oncourt_interviews import compile_deny, load_sources

    deny = compile_deny(load_sources())
    par = deny["Rolex Paris Masters"]

    def denied(title):
        return any(p.search(title) for p in par)

    for title in [
        "Ugo Humbert Round 2 post-match interview | Rolex Paris Masters 2024",
        "Carlos Alcaraz Round 2 post-match interview | Rolex Paris Masters",
        "Alexander Zverev final post-match interview | Rolex Paris Masters 2024",
        "Arthur Cazaux post-match interview | Rolex Paris Masters",
    ]:
        assert denied(title), title

    for title in [
        "Novak Djokovic on-court interview Final | Rolex Paris Masters 2023",
        "Holger Rune on-court interview Round 3 | Rolex Paris Masters 2023",
        "Jannik Sinner quarter-finals on-court interview | Rolex Paris Masters",
        "Alexander Zverev's quarter-finals on-court interview | Rolex Paris Masters",
    ]:
        assert not denied(title), title


def test_store_has_no_denied_titles_left():
    """规则和库要一致——加了规则却没清库，等于规则只管未来不管现在。"""
    from tools.collect_oncourt_interviews import STORE, compile_deny, load_sources

    deny = compile_deny(load_sources())
    with STORE.open(encoding="utf-8") as fh:
        items = json.load(fh)["items"]
    left = [v["title"] for v in items.values()
            if any(p.search(v["title"]) for p in deny.get(v.get("source", ""), ()))]
    assert left == [], f"库里还留着 {len(left)} 条被规则判为发布会的：{left[:3]}"
