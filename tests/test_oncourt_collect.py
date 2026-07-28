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

    ~~YouTube 频道深扫 800 条是 0 条场上采访~~ ——**这句话作废了**：
    实测 Tennis TV 频道有 3000+ 条，800 根本没扫到底，那个「0」是扫深不够
    造出来的（见 `test_scan_depth_reaches_the_bottom_of_every_channel`）。
    现在扫深已提到 5000。留着这条测试是为了另一件事：**两个源不能合并**。
    站上的库逐轮都有
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


def test_title_rules_cannot_split_press_from_oncourt():
    """**两次想从标题里找规律，两次都错。** 这条测试就是钉住别再试第三次。

    法网和巴黎大师赛（同属法网协会 FFT）把新闻发布会也写成
    `post-match interview`，跟真正的场上采访一个词。

    第一版按年份切法网——2024 的 post-match 一律当发布会。61 条里错杀 4 条：

        Schwartzman Q2 / Thiem Q1     两场告别，人在场上，身边站着纳达尔
        Sinner Round 2 / Wawrinka R1  主持人手持话筒、看台、红土

    第二版按「标题不写 on-court」切巴黎，25 条里错杀 7 条。最要命的是这三条：

        IOLtTF-PzZ8  Jannik Sinner post-match interview | Rolex Paris Masters → 场上
        bWTTWu_uA_I  Jannik Sinner post-match interview | Rolex Paris Masters → 场上
        p8z5dEVgXck  Jannik Sinner post-match interview | Rolex Paris Masters → 背景板

    标题一字不差，画面两回事。所以现在**一条正则都不留**，全部按 id。
    """
    from tools.collect_oncourt_interviews import compile_deny, load_sources

    cfg = load_sources()
    assert compile_deny(cfg) == {}, "不许再用标题正则分发布会——两次都被证明是错的"

    ids = set(cfg["deny_ids"])
    assert "p8z5dEVgXck" in ids
    for oncourt in ("IOLtTF-PzZ8", "bWTTWu_uA_I"):
        assert oncourt not in ids, f"{oncourt} 看过帧确认在场上"


def test_denied_ids_are_all_recorded_as_verified():
    """拉黑名单上的每一条，都得在判定文件里有一条看过画面的记录。

    不许凭印象拉黑——名单和证据必须一一对上。

    **四种理由都算数**，因为它们是四回事：
      press    人根本不在场上（发布厅、媒体混合区）
      ceremony 人在场上，但是**独自对着观众讲**，不是接受采访
               （判据是话筒：落地支架麦＝致辞，手持话筒＝有人在问）
      other    在场上、也是采访，但**受访的不是球员**——
               tennistv 那条 `Albert II, Prince of Monaco special interview`
               画面里是摩纳哥亲王站在蒙特卡洛红土边上。
      degraded 是场上采访，画面也是官方转播信号，但**被二次加工毁掉了**：
               缩成小窗套装饰边框、竖屏放大后左右补虚化侧栏、烧录字幕、画中画。
               这一档是后来才有的——「肯定要用官方的直播的视频，清晰度和角度
               根本达不到要求」。**它和上面三种不一样：内容合格，画面不合格。**
               台标和轻微裁切不算，那两样裁完还是转播画质，记在源的 `picture` 里照收。
    用户要的只有「球员赛后直接在场上接受采访、且画面是能用的转播信号」，四种都不是。

    **`oncourt` 绝不能出现在拉黑名单上**——那说明看过是场上采访却还是剔了。
    （`degraded` 之所以单列而不并进 `oncourt`，就是为了守住这一条：
    画面不合格要说成画面不合格，不能借 `oncourt` 的名义悄悄剔掉。）
    """
    from tools.collect_oncourt_interviews import ROOT, load_sources

    with (ROOT / "data" / "oncourt_verify.json").open(encoding="utf-8") as fh:
        seen = json.load(fh)["verdicts"]
    for vid in load_sources()["deny_ids"]:
        assert vid in seen, f"{vid} 被拉黑却没有看图记录"
        assert seen[vid]["verdict"] in ("press", "ceremony", "other", "degraded"), \
            f"{vid} 的判定是 {seen[vid]['verdict']}，不该在拉黑名单上"


def test_every_source_declares_where_its_picture_comes_from():
    """每个源都要声明 `provenance`，而且必须是那三档之一。

    **这条测试是从一次口误里长出来的。** Edimator 那 158 条我一直说成「现场拍摄者」，
    还据此打算把它整个删掉；直到把自动帧拼成联络表看了一眼——温网那条带着**转播下方
    字幕条**，上海那条右上角是 **prime 台标**，加拿大那条**切到了采访者**（反打机位，
    看台上拍不出来）。它是搬运官方转播信号，不是自己拍的。

    同一批看下来，11 个 rehost 源**没有一个**是自己拍的。所以字段的意义不在于
    区分「官方 / 非官方」——那是 `unofficial` 管的事——而在于**逼着每个源在进库之前
    回答「这段画面是谁拍的」**，答不上来就不能进。

    判据只认画面里的转播要素：官方话筒旗、转播图形包（比分条 / 下方字幕条 /
    LED 上的 MATCH WINNER / 角落台标）、反打机位。频道名字看着像不像官方不作数。
    """
    cfg = load_sources()
    ok = {"official", "broadcaster", "rehost"}
    for src in cfg["sources"]:
        assert src.get("provenance") in ok, \
            f"{src['name']} 没声明画面出处（provenance），或者写了 {src.get('provenance')!r}"
        # rehost 是搬运官方信号，不是自拍——两个标记必须一致，
        # 免得哪天又把「非官方频道」和「自己拍的」混为一谈
        if src["provenance"] == "rehost":
            assert src.get("unofficial"), f"{src['name']} 标了 rehost 却没标 unofficial"
        else:
            assert not src.get("unofficial"), \
                f"{src['name']} 标了 {src['provenance']} 却又标 unofficial"


def test_store_sources_are_all_declared_in_the_registry():
    """库里出现过的每个来源，注册表里都要有——**摘掉一个源要连着它的条目一起摘。**

    起因：安特卫普、Sportiva Arena、Karendoms Tandem 三个源这一轮被判不合格，
    从注册表里摘掉了。但注册表和库是两份文件，只改一份的话，库里那 14 条会
    继续被推送、被统计成覆盖率，而报表上再也看不到它们来自哪个源——
    **看着像已经清干净了。**
    """
    from tools.collect_oncourt_interviews import ROOT

    with (ROOT / "data" / "oncourt_interviews.json").open(encoding="utf-8") as fh:
        items = json.load(fh)["items"]
    known = {s["name"] for s in load_sources()["sources"]}
    stray = {it["source"] for it in items.values()} - known
    assert not stray, f"库里这些来源已经不在注册表里，条目却还留着：{sorted(stray)}"


def test_ceremony_speech_and_ceremony_interview_are_split_by_the_microphone():
    """同一批 `Champion/Finalist` 标题里，致辞和采访各占一半。

    18 条看下来 12 条是致辞、6 条是采访，**标题上完全看不出来**：

        Lilli Tagger Champion Prague 2026   落地支架麦，捧着奖杯独自讲  → 致辞
        Petra Marcinko Champion Rabat 2026  WTA TOUR 手持话筒，有人在问 → 采访

    所以判据落在**话筒**上，不落在标题上——又一次只能按 id。
    """
    from tools.collect_oncourt_interviews import ROOT, load_sources

    ids = set(load_sources()["deny_ids"])
    with (ROOT / "data" / "oncourt_verify.json").open(encoding="utf-8") as fh:
        seen = json.load(fh)["verdicts"]

    assert "TgvGNvqYuYk" in ids, "布拉格冠军那条是支架麦致辞"
    assert seen["TgvGNvqYuYk"]["verdict"] == "ceremony"
    for interview in ("XGGF3Cq4pQg", "BY7GOFzxWOU", "hHaklqxZmKY"):
        if interview in seen:                      # 只查记录在案的
            assert seen[interview]["verdict"] == "oncourt"
            assert interview not in ids


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


def test_store_matches_every_rule_and_every_verdict():
    """规则、判定、库存三者要对得上。

    分三条查，因为三种不一致的形状不一样：
    加了规则没清库＝规则只管未来不管现在；拉黑了却还在库里＝白拉；
    **看图确认在场上的却不在库里＝误剔**——最后这条是踩出来的，
    巴黎那版正则一次误剔了七条真场上的。
    """
    from tools.collect_oncourt_interviews import (
        ROOT,
        STORE,
        compile_deny,
        load_sources,
    )

    cfg = load_sources()
    deny = compile_deny(cfg)
    with STORE.open(encoding="utf-8") as fh:
        items = json.load(fh)["items"]
    with (ROOT / "data" / "oncourt_verify.json").open(encoding="utf-8") as fh:
        seen = json.load(fh)["verdicts"]

    by_title = [v["title"] for v in items.values()
                if any(p.search(v["title"]) for p in deny.get(v.get("source", ""), ()))]
    assert by_title == [], f"库里还留着 {len(by_title)} 条被规则判为发布会的：{by_title[:3]}"

    by_id = [vid for vid in cfg["deny_ids"] if vid in items]
    assert by_id == [], f"拉黑名单上的 {by_id} 还在库里"

    # 判定为发布会的，才允许不在库里；判定为场上的必须在
    missing = [vid for vid, v in seen.items()
               if v["verdict"] == "oncourt" and vid not in items
               and not any(p.search(v.get("title", "")) for p in deny.get(v.get("source", ""), ()))]
    assert missing == [], f"看图确认在场上、却被剔出库的：{missing}"


def test_allow_by_source_is_scoped_to_its_own_source():
    """按源的白名单：官方赛事频道标题太简，全局模式够不着。

    巴斯塔德写 `Filip Misolic Interview - Nordea Open 2025`——只有一个光秃秃的
    `interview`。加进全局 `patterns_oncourt` 会把发布会、播客、专访一起灌进来。

    **和 assume_oncourt 的区别是踩出来的**：一开始给 Nordea 打了
    assume_oncourt，300 条全进来了，其中大半是 16–35 秒的 `Hot shot` 好球集锦。
    白名单只放标题对得上的那 27 条。
    """
    from tools.collect_oncourt_interviews import compile_allow, load_sources

    cfg = load_sources()
    allow = compile_allow(cfg)
    assert "Nordea Open" in allow
    assert allow.get("Wimbledon") is None, "白名单不能外溢到别的源"

    rx = allow["Nordea Open"]
    assert any(p.search("Filip Misolic Interview - Nordea Open 2025") for p in rx)
    # 好球集锦不带 interview，白名单碰不到它
    assert not any(p.search("Luciano Darderi - Hot shot - Nordea Open 2026") for p in rx)

    # 打了白名单的源不该同时打 assume_oncourt——那样白名单就没意义了
    for src in cfg["sources"]:
        if src["name"] in allow:
            assert not src.get("assume_oncourt"), f"{src['name']} 白名单与整包收不能并存"


def test_calendar_covers_every_tier_and_patterns_compile():
    """赛历本身要能用：正则编得过、日期成对、级别齐。

    这张表是覆盖率对账的**分母**——之前用我手搓的清单，
    漏掉的赛事在报表上根本不出现，看着一片绿其实半张日历没查过。
    """
    import re as _re

    from tools.collect_oncourt_interviews import ROOT

    with (ROOT / "data" / "tour_calendar_2026.json").open(encoding="utf-8") as fh:
        events = json.load(fh)["events"]
    assert len(events) >= 100
    tiers = {e["tier"] for e in events}
    for t in ("大满贯", "ATP1000", "WTA1000", "ATP500", "WTA500", "ATP250", "WTA250"):
        assert t in tiers, f"赛历缺 {t} 这一档"
    for e in events:
        _re.compile(e["pat"])                       # 编不过就炸在这
        assert e["tour"] in ("atp", "wta", "both"), e["zh"]
        assert _re.fullmatch(r"\d\d-\d\d", e["start"]), e["zh"]


def test_slug_patterns_tolerate_hyphens_and_underscores():
    """赛事名在 URL 里是 `indian-wells`、`/paris_round-1-`，不是空格。

    实测这一条漏了 85 条：60 条印第安维尔斯 + 25 条巴黎全被判成
    「不属于任何赛事」，因为正则写的是 `indian wells`（空格）。
    """
    import re as _re

    from tools.collect_oncourt_interviews import ROOT

    with (ROOT / "data" / "tour_calendar_2026.json").open(encoding="utf-8") as fh:
        events = {e["zh"] + e["tour"]: e for e in json.load(fh)["events"]}

    iw = _re.compile(events["印第安维尔斯大师赛atp"]["pat"], _re.I)
    assert iw.search("https://www.tennistv.com/videos/1/indian-wells-2025-r2-griekspoor-interview")
    assert iw.search("ARYNA SABALENKA/ON COURT INTERVIEW/INDIAN WELLS OPEN 2025")

    par = _re.compile(events["巴黎大师赛atp"]["pat"], _re.I)
    assert par.search("/videos/10/paris_round-1-post-match-interview-dimitrov")
    assert par.search("Novak Djokovic on-court interview Final | Rolex Paris Masters 2023")


def test_source_owned_events_catch_titles_without_the_event_name():
    """`srcs`：频道本身就说明了赛事，标题写不写无所谓。

    汉堡官方频道写 `HEO2021 /// ATP QF /// ON-COURT INTERVIEW with …`，
    迪拜写 `Post-Match Interview: Roger Federer`——标题里一个赛事名都没有。
    只按标题匹配，这两个源的 129 条全成孤儿。
    """
    from tools.collect_oncourt_interviews import ROOT

    with (ROOT / "data" / "tour_calendar_2026.json").open(encoding="utf-8") as fh:
        events = json.load(fh)["events"]
    owned = {}
    for e in events:
        for s in e.get("srcs", ()):
            owned.setdefault(s, set()).add(e["zh"])
    assert owned.get("Hamburg European Open") == {"汉堡公开赛"}
    assert owned.get("Nordea Open") == {"博斯塔德公开赛"}
    # 大满贯拆成了男单 / 女单两个赛事，同一个频道挂在两边——
    # 一届大满贯是两个 128 签、男女各 127 场，分母不拆会把覆盖率算高一倍。
    assert owned.get("Wimbledon") == {"温布尔登网球锦标赛（男单）", "温布尔登网球锦标赛（女单）"}


def test_broadcaster_round_interview_form(rules):
    """转播商写「赛事 + 轮次 + Interview」，不写 on-court / post-match。

    Stan Sport（澳洲持权方）写 `Wimbledon First Round Interview 🎙️`——
    前三条模式一条都不认，88 条取到 **0 条**。

    加这条之前拿库里 4241 条全量试过：额外命中 0，不扰动现有分类；
    `Quarterfinals Press Conference` 这类发布会也不会被它收进来
    （它要求 `round interview` 连在一起，或 `quarter-final interview`）。
    """
    for title in [
        "Stan Wawrinka tears up during farewell 🥹 | Wimbledon First Round Interview 🎙️",
        "Grigor Dimitrov on last year's return 🥹 | Wimbledon Second Round Interview",
        "Jannik Sinner Reveals Golf Skills 🏌️| Wimbledon Second Round Interview 🎙️",
    ]:
        assert tag(title, rules) == "oncourt", title

    # 发布会不能被顺进来
    for title in [
        "Iga Swiatek | Quarterfinals Press Conference | 2025 Cincinnati Open",
        "Frances Tiafoe | Post Match Press Conference | 2025 Mubadala Citi DC Open",
    ]:
        assert tag(title, rules) is None, title


def test_gender_is_read_off_the_official_ranking_snapshot():
    """男女分流以 ATP / WTA 各 500 人的官方排名快照为准，不靠手搓正则。

    **这条是从一个虚高的数字里长出来的。** 澳网男单曾经报 100%、女单 99%，
    而当时进入统计的 847 条里有 365 条**认不出球员性别**——按老规则
    「认不出的两边都算」，同一批条目把男单和女单两个 127 的分母同时填满了。

    快照的两个性质是实测的，不是假设：全名零重叠（所以全名命中即定案），
    姓氏有 10 个两边都有（Zhang / Zheng / Sun / Smith …，所以共用姓不作数）。
    """
    from tools.oncourt_coverage import side

    assert side({"title": "Jannik Sinner On-Court Interview | Australian Open 2026"}) == "atp"
    assert side({"title": "Aryna Sabalenka On-Court Interview | US Open 2025 Final"}) == "wta"
    # 音标要去掉：库里写 Muchová，快照写 Muchova
    assert side({"title": "Karolína Muchová On-Court Interview | 2023 US Open Round 3"}) == "wta"
    # 退役的走补充名单
    assert side({"title": "Roger Federer on-court interview (3R) | Australian Open 2018"}) == "atp"
    assert side({"title": "Serena Williams on court interview | US Open 2019"}) == "wta"
    # 男女都命中就认不出——霍普曼杯的混合队、以及「斯维托丽娜夸丈夫蒙菲尔斯」
    assert side({"title": "Karen Khachanov and Anastasia Pavlyuchenkova "
                          "on-court interview (RR) | Hopman Cup"}) is None
    assert side({"title": "Team Germany on-court interview (RR) | Hopman Cup 2019"}) is None


def test_short_surnames_do_not_match_inside_longer_words():
    """短姓氏不能匹进别的词里，也不能匹上英文常用词。

    旧的手搓正则**没有词边界**，四个真实的误判：

        Paul      汤米·保罗（男）匹上 `against Paula Badosa`
        Lys       伊娃·利斯（女）匹上 `Quentin Halys`
        Jovic     伊娃·约维奇（女）匹上 `Dusan Lajovic`
        Cristian  雅克琳·克里斯蒂安（女）匹上 `Cristian Garín`

    还有一类词边界救不了：`Day` 是凯拉·戴的姓，**也是英文里最常见的词之一**，
    匹上了 `Sinner: 'Today was a very difficult day in the office'`。
    那条判据是大小写——人名在标题里一定不是全小写的。
    不用「首字母大写」而用「不全小写」，是因为标题常常整句大写。
    """
    from tools.oncourt_coverage import side

    assert side({"title": "Katie Boulter interview after 1st round win "
                          "against Paula Badosa"}) == "wta"
    assert side({"title": "Quentin Halys | Post-Match Interview | QF | 2025 Dubai"}) == "atp"
    assert side({"title": "ON-COURT INTERVIEW with Dusan Lajovic"}) == "atp"
    assert side({"title": "Cristian Garín interview after 1st Round win"}) == "atp"
    assert side({"title": "Sinner: 'Today was a very difficult day in the office'"}) == "atp"
    # 但真的叫 Day 的还是要认出来
    assert side({"title": "Kayla Day On-Court Interview | Australian Open 2024"}) == "wta"
    # 整句大写也要认
    assert side({"title": "WORLD NO.1 IGA SWIATEK ON COURT INTERVIEW"}) == "wta"


def test_supplementary_roster_does_not_duplicate_the_snapshot():
    """补充名单里不许出现快照已有的现役球员——**两份名单打架就是这么来的**。

    补充名单原来塞了 249 个词，其中 191 个是现役球员。快照接手之后它们
    全是冗余，而冗余不是无害的：`Cristian`（女）和 `Jovic`（女）正是这样
    把 Cristian Garín 和 Dusan Lajovic 判成了女子。

    这条只查姓氏层面的重复。**语序或拼法与快照不同的允许保留**
    （`Zhang Shuai` vs 快照的 `Shuai Zhang`、`Auger-Aliassime` 的连字符），
    所以比的是「补充名单里这个词，是不是同一巡回赛快照里的某个姓氏」。
    """
    import json as _json
    import re as _re

    from tools.oncourt_coverage import MEN, SNAPSHOT, WOMEN, _fold

    snap = _json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    sur = {t: {_fold(e["name_en"]).split()[-1].lower() for e in snap["tours"][t]}
           for t in ("ATP", "WTA")}

    def words(rx):
        inner = _re.sub(r"^\\b\(\?:|\)\\b$", "", rx.pattern)
        return [w for w in inner.split("|") if w]

    for rx, tour in ((WOMEN, "WTA"), (MEN, "ATP")):
        dupes = [w for w in words(rx) if _fold(w).lower() in sur[tour]]
        assert not dupes, f"{tour} 补充名单和快照重复：{dupes}"


def test_unknown_gender_never_counts_toward_a_single_tour_draw():
    """认不出性别的条目，不许进单巡回赛事的分子。

    两个工具在这里**故意不一致**，别去「统一」它：

        oncourt_coverage.py        放过去。它报的是「这一站有没有覆盖、有几条」，
                                   多算不致命，漏算反而会让缺口从报表上消失
        oncourt_match_coverage.py  丢掉。它报的是**占某一张签表的百分比**，
                                   一条认不出性别的条目会在男单和女单各算一次，
                                   两个 127 的分母被同一批条目同时填

    辛辛那提 WTA 是最干净的例证：混在里面的 35 条全是男子
    （Fonseca、Opelka、Rune、Tsitsipas、Sinner…），剔掉之后从 8% 落到 1%。
    """
    import re as _re

    from tools.oncourt_coverage import haystack, side
    from tools.oncourt_match_coverage import coverage, is_main_singles, load

    items, events = load()
    ev = next(e for e in events if e["zh"] == "辛辛那提公开赛" and e["tour"] == "wta")
    rx, own = _re.compile(ev["pat"], _re.I), set(ev.get("srcs", ()))
    leaked = [it for it in items.values()
              if (it.get("source") in own or rx.search(haystack(it)))
              and is_main_singles(it) and side(it) == "atp"]
    assert leaked, "这一站本来就是靠混进来的男子条目撑着的，样本没了这条测试就失去意义"

    row = next(r for r in coverage(items, events)
               if r["zh"] == "辛辛那提公开赛" and r["tour"] == "wta")
    assert row["covered"] <= 3, f"辛辛那提 WTA 覆盖 {row['covered']} 场，男子条目又混进来了"
    # 被丢掉的数量要报出来——只报命中的，没法证明它真的看过全部
    assert "unknown" in row


def test_scan_depth_reaches_the_bottom_of_every_channel():
    """注册的 `scan_depth` 不能小于这个频道实测的条数——**否则采集器走不到底**。

    **这条是 `scan_depth` 骗过我之后加的。** WTA 官方频道注册的是 800，看着不小；
    全量扫下来 13791 条，而分类器判为场上采访的 86 条**全部排在第 800 名之后**——
    按注册深度一条都拿不到。而报表上它只显示「这个源贡献 0 条」，
    看着像「WTA 不发场上采访」。

    **不够深的时候采集器不报错，它只是没走到那里。** 这是「空结果 ≠ 不存在」
    里最隐蔽的一种：没有异常、没有告警、数字看着就是真的。

    顺着查下来 14 个源不够深，合计漏 350 条：Tennis TV 800→5000、
    印第安维尔斯 500→2600、Tennis Channel 250→5000……**其中 Tennis Channel
    那条最要命**——我曾据 700 条深扫断言它「一条场上采访都没有」，
    而它的真实体量是 3000+，那个结论根本不作数。

    `measured` 是 2026-07-27 用 `tools/check_scan_depth.py` 实测的条数；
    探到 3000 就停，所以记 3000 的是**下界**不是真值，注册深度给了余量。
    """
    for src in load_sources()["sources"]:
        m = src.get("measured")
        if m is None or src.get("depth_exempt"):
            continue
        assert src.get("scan_depth", 150) >= m, (
            f"{src['name']} 实测 {m} 条，scan_depth 只有 {src.get('scan_depth', 150)}"
            f"——后面那截扫不到")


def test_depth_exempt_sources_say_why():
    """扫深故意低于实测条数的，必须写明理由——**不许默默留个浅的**。

    只有一个：WTA 官方频道。它实测 13791 条，深处 86 条命中分类器，
    但逐批看帧全是发布会（2020 罗马那 28 条：长桌、BNL 背景板、台式麦）
    和演播室专访（2016 新加坡年终、2016 亚洲赛季：黑底、赛事 logo 角标、领夹麦），
    真在场上的只有 2–3 条。为这个把扫深开到 14000 不划算。

    **豁免要写清楚是「查过了，那里没有」，不是「没查」。** 两者在报表上
    长得一模一样，只有这段字能分开。
    """
    cfg = load_sources()
    exempt = [s for s in cfg["sources"] if s.get("depth_exempt")]
    for s in exempt:
        assert len(s["depth_exempt"]) > 30, f"{s['name']} 的豁免理由太短，说不清查过什么"
        assert s.get("measured"), f"{s['name']} 声称豁免却没有实测数"
