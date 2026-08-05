"""选题雷达：把每天的新闻提炼成选题候选，而不是快讯候选。"""

from __future__ import annotations

import json

from tennislive.research.topic_radar import (
    ANGLES,
    cluster_headlines,
    distil_topics,
    leftover_terms,
    match_angle,
    measure_heat,
    published_topics,
)


def _h(title: str, source: str) -> dict:
    return {"title": title, "source": source, "url": f"https://x/{abs(hash(title))}",
            "kind": "official-news"}


def test_一个新闻点要几家在报_同一家发两条不算两家():
    """孤零零一条标题多半是流水（「Norrie ends losing streak」），不是新闻点。

    判据是**不同来源**的家数，不是条数——ATP 官网同一件事发两条，仍然只有
    它一家在说。这条挡住的是「一家自己刷屏」被当成热点。
    """
    one_outlet = [
        _h("Sinner, Djokovic withdraw from Montreal", "ATP Tour"),
        _h("Sinner and Djokovic withdraw from Montreal Masters", "ATP Tour"),
    ]
    assert cluster_headlines(one_outlet) == []

    two_outlets = one_outlet + [
        _h("Jannik Sinner, Novak Djokovic withdraw from Montreal event", "ESPN")
    ]
    clusters = cluster_headlines(two_outlets)
    assert len(clusters) == 1 and len(clusters[0]) == 3


def test_撞不上角度就不猜():
    """`ANGLES` 里每条角度背后都有一份能翻的规则书或史料，编出来的没有。

    撞不上的进「没对上角度的热点」让人自己看——**宁可少给一条，也别给一条
    像模像样但没有出处的**。
    """
    wedding = [
        _h("Best photos from de Minaur and Boulter's wedding", "WTA Tennis"),
        _h("Inside the de Minaur-Boulter wedding weekend", "BBC"),
    ]
    assert match_angle(wedding) is None

    topics, leftover = distil_topics(wedding)
    assert topics == []
    assert len(leftover) == 1, "没对上角度的簇要留着，不能直接丢"
    assert leftover_terms(leftover), "要报出高频词，否则不知道该补什么角度"


def test_作证的单位是标题不是同一个词():
    """⚠️ 第一版要求**同一个触发词**出现在两条标题上，于是漏掉一整条角度。

    2026-08-05 真实数据，华盛顿决赛因雨推迟：

        Eala, Pegula Washington DC championship **suspended** to Monday
        Washington final **delayed** ... due to **rain**

    两条都在讲天气，**却没有任何一个词同时出现在两条上**——不同媒体本来就用
    suspended / delayed / postponed 说同一件事。按词数就判成「撞不上」，
    而**撞不上和「今天没有这类新闻」长得一模一样**。

    这条钉两头：真该撞的要撞上，**而它当初防的那个误判仍然拦得住**。
    """
    rain = [
        _h("Eala, Pegula Washington DC championship suspended to Monday", "WTA Tennis"),
        _h("Washington final delayed until Monday due to rain", "ATP Tour"),
    ]
    got = match_angle(rain)
    assert got is not None and got.slug == "roof-and-weather", (
        "两条标题各自为「天气」作证，只是用词不同"
    )

    # ↓ 老 docstring 里那个它专门要防的误判：并错的簇，只有第一条带 mixed/doubles。
    #   新规则下第二条一个触发词都没有 → 只有一条作证 → 照旧不算。
    miscluster = [
        _h("US Open Mixed Doubles entries revealed", "US Open"),
        _h("Shelton looks ahead to the 2026 season", "ATP Tour"),
    ]
    assert match_angle(miscluster) is None, "并错的簇不许因为一条标题就叠上角度"


def test_退赛和天气的说法要收全():
    """英文媒体说同一件事有好几种写法，少一个词就少一条证据。

    两条都是 2026-08-05 真实漏掉的：拉杜卡努那簇两条标题写的都是
    `to **miss** US Open`，而表里当时只有 withdraw/pullout/skip 这一族。
    """
    miss = [
        _h("Raducanu to miss US Open to continue recovery", "BBC Sport"),
        _h("Emma Raducanu to miss US Open with leg injury", "The Guardian"),
    ]
    got = match_angle(miss)
    assert got is not None and got.slug == "withdrawal-deadline"

    # ⚠️ `out` 故意没收：太宽（`knocked out` / `out of form`），判据宁可窄。
    #    这条钉住那个决定——有人图省事加上去，它会当场红。
    knocked = [
        _h("Sinner knocked out in Montreal third round", "ATP Tour"),
        _h("Alcaraz knocked out by Rublev in Montreal", "BBC Sport"),
    ]
    assert match_angle(knocked) is None, "`knocked out` 不是退赛，别把 out 收进触发词"


def test_已发角度的账本要真的对得上角度表():
    """⚠️ 这条防的是「标记恒空」——而恒空和「这些角度都还没做过」长得一样。

    2026-08-05 查出来：仓库里已经发过 29 条解说片（含 protected-ranking、
    special-exempt、shot-clock、hawkeye、roof、lucky-loser…），而账本里记的
    是**另一套命名**，于是 `known_done_on` 几乎永远是空的——简报会把三周前
    做过的角度当新鲜的推出来。

    判据是**交集不许太小**（「判据自己也要有判据」）：写错名字的记录不会报错，
    只会让这个交集悄悄缩回 0。
    """
    slugs = {a.slug for a in ANGLES}
    marked = {k for k in published_topics() if k in slugs}
    assert len(marked) >= 8, (
        f"账本里只有 {len(marked)} 条对得上角度表——"
        "「这条做过没有」这个标记基本是死的，八成是 slug 写成了解说片那套命名"
    )
    for key in marked:
        assert published_topics()[key][:4].isdigit(), f"{key} 的值要是发布日期"


def test_已发过的选题标出来并排到后面(tmp_path):
    """账本撞上就标「做过」，别让同一条隔一周再冒出来一次。

    仍然返回它——今年的新闻可能值得做续集，但要让人一眼看见做过。

    ⚠️ **账本自带，不读仓库里那份。** 第一版直接用 `published_topics()`，
    它的前提是「wildcard 做过、protected-ranking 没做过」；2026-08-05 把账本
    按实际发过的解说片补齐之后 protected-ranking 也成了已做，**这条测试的
    主语当场没了**（两条都已做，排序无从比起）。判据要自带它比较的那两端，
    别挂在一份会变的产物账本上。
    """
    ledger = tmp_path / "state.json"
    ledger.write_text(json.dumps({"wildcard": "2026-07-28"}), encoding="utf-8")
    news = [
        _h("Kyrgios handed Wimbledon wild card by AELTC", "ATP Tour"),
        _h("AELTC confirms Kyrgios wild card for Wimbledon", "ESPN"),
        _h("Draper to undergo surgery after arm injury", "BBC"),
        _h("Draper surgery confirmed, injury rules him out for months", "Sky Sports"),
    ]
    topics, _ = distil_topics(news, state_path=ledger)
    labels = [t.angle.slug for t in topics]
    assert "wildcard" in labels and "protected-ranking" in labels
    # 做过的那条要排在没做过的后面
    assert labels.index("wildcard") > labels.index("protected-ranking")
    wc = next(t for t in topics if t.angle.slug == "wildcard")
    assert wc.published_on == "2026-07-28"
    pr = next(t for t in topics if t.angle.slug == "protected-ranking")
    assert not pr.published_on, "这份账本里没记它，就不该标成做过"


def test_空产要能分清是没热点还是没角度():
    """一条候选都没有时，两种原因要分得开：

    · 今天真没有多家在报的新闻点 → 不用做任何事
    · 有热点但都没撞上表里的角度 → 该往 ANGLES 里补一条

    分不开的话，「候选静默消失」就无从追查——和 flash-radar 的空产摘要
    是同一条规矩。
    """
    quiet = [_h("Norrie ends losing streak", "Sky Sports")]
    topics, leftover = distil_topics(quiet)
    assert topics == [] and leftover == [], "单条标题不成簇，也不该算没对上角度"

    # ⚠️ 这个例子换过一次：原来用的是球童（ballkid），而球童**已经被补进
    # `ANGLES` 了**——正是这份清单该起的作用（它连着几天占着 unmatched_terms
    # 第一位）。所以撞不上角度的例子要换成表里确实没有的：装备/赞助那一路。
    hot_but_unmatched = [
        _h("Alcaraz unveils his new Nike kit", "ATP Tour"),
        _h("Inside the Alcaraz Nike kit launch", "ESPN"),
    ]
    topics, leftover = distil_topics(hot_but_unmatched)
    assert topics == [] and len(leftover) == 1


def test_每条角度都写了出处和开场问题():
    """角度表是这条流水线唯一的编辑资产。

    没有出处的角度等于「我觉得可以讲」——`docs/newshook-topics.md` 里每条
    背后都有一份能翻的规则书或史料，这张表也照这个要求。
    """
    slugs = [a.slug for a in ANGLES]
    assert len(slugs) == len(set(slugs)), "角度 slug 不能重复"
    for angle in ANGLES:
        assert angle.triggers, f"{angle.slug} 没有触发词，永远撞不上"
        assert angle.evergreen.strip(), f"{angle.slug} 没写底下压着的常青线"
        assert angle.source.strip(), f"{angle.slug} 没写去哪儿核实"
        assert angle.question.rstrip().endswith("？"), (
            f"{angle.slug} 的开场没有问出一个问题：{angle.question}")


def test_赛事名不能当并簇的锚():
    """2026-07-29 实跑：28 条标题里 `washington` 占了 **13 条**——它是本周
    那一站，凡是那站的新闻都带着它。

    「共享一个专名 + 总共享词 ≥2」挡不住这个：随便一个虚词（`i've`、`only`）
    凑上去就成簇了，于是「Eala 首胜郑钦文」和「Shelton 谈 2026 赛季」并到了
    一起。**而且这不只是多出一条假候选，它还会吃掉真的**：Draper 那条自己
    带着 `withdraws`，本该对上「退赛与截止日」，被并进一个没有第二条
    `withdraws` 的簇之后，触发词那一关就过不去了。

    所以锚定的那个专名还得**今天罕见**（df ≤ 标题数的四分之一）。
    """
    week = [
        _h("'I've already had that in me.' Eala's grit yields Washington debut win vs. Zheng", "WTA Tennis"),
        _h("Shelton on 2026 season ahead of Washington: 'There are so many things I've been frustrated about'", "ATP Tour"),
        _h("Draper withdraws from Washington: 'I'm only grateful for the struggle'", "ATP Tour"),
        _h("Top quotes from Washington DC media day: 'The only way to go forward is growth'", "WTA Tennis"),
        _h("Atmane gains Tiafoe revenge, breaks home hearts in Washington opener", "ATP Tour"),
        _h("By the numbers: Samsonova puts third-set woes behind her in Washington upset of Keys", "WTA Tennis"),
        _h("In Washington, Fernandez has an 'aggressive' approach to title defense", "WTA Tennis"),
        _h("What is the Washington schedule?", "ATP Tour"),
        _h("What to watch this week: De Minaur, Shelton in Washington; Cerundolo in Los Cabos", "ATP Tour"),
        _h("Ngounoue / Smith vs Routliffe / Sutjiadi · Quarterfinal · ATP/WTA Washington D.C.", "Tennis.com"),
        _h("Krajicek / Mektic vs Harrison / Skupski · Quarterfinal · ATP/WTA Washington D.C.", "Tennis.com"),
        _h("Anastasia Potapova vs Venus Williams · Round 1 · ATP/WTA Washington D.C.", "Tennis.com"),
        _h("Around the Washington grounds: Osaka unites DC fans as Venus, Shnaider prevail", "WTA Tennis"),
    ]
    clusters = cluster_headlines(week)
    titles = [{h["title"] for h in g} for g in clusters]
    for group in titles:
        assert not any("Eala" in t for t in group) or len(group) == 1, \
            f"Eala 那条又被赛事名并进别的故事里了：{group}"
        assert not any("Draper" in t for t in group), \
            f"Draper 退赛被并进了别的簇，「退赛与截止日」就撞不上了：{group}"

    # 罕见的专名照样并得起来：同一天 venus 只出现在两条里，那两条确实是同一件事
    assert any({"Venus", "venus"} & {w for t in g for w in t.split()} for g in titles), \
        "把满天飞的词挡掉之后，罕见专名那条真簇不能跟着一起没了"


def test_触发词必须是切得出来的词():
    """`hawk-eye`、`12-day`、`no1`、`top10` 都当过触发词，**一次都没匹配上**。

    `match_angle` 拿的是 `_WORD.findall(标题)` 那个词集合，而 `_WORD` 把连字符
    和句点当分隔符：`hawk-eye` 切成 hawk / eye，`No. 1` 切成 no / 1，
    `Top 50` 切成 top / 50。整词永远不在集合里——写进表里看着像在防守，
    其实是个哑弹，而且**不吭声**，和「兜底出事的时候不报错」是同一种毛病。
    """
    from tennislive.research.topic_radar import _WORD

    dead = [
        (a.slug, t) for a in ANGLES for t in a.triggers
        if not _WORD.fullmatch(t) or t != t.casefold()
    ]
    assert dead == [], f"这些触发词切不出来，永远匹配不上：{dead}"


def test_触发词不能是每周都会出现的词():
    """「退役与告别」原来的触发词里有 `final` 和 `last`。

    **任何一个赛事周都会把它们撞上**——「reaches final」「into final」两条标题
    就够了，于是每周都自动冒出一条假的「退役与告别」，看着像模像样，
    和聚类那两个假阳性是同一种错。触发词要挑**只有这类新闻才会用的词**。
    """
    routine = [
        _h("Alcaraz reaches final in Cincinnati", "ATP Tour"),
        _h("Alcaraz into Cincinnati final", "ESPN"),
    ]
    assert match_angle(routine) is None

    real = [
        _h("Nishikori announces he will retire after this season", "ATP Tour"),
        _h("Nishikori to retire, farewell tour confirmed", "ESPN"),
    ]
    angle = match_angle(real)
    assert angle is not None and angle.slug == "retirement-farewell"


def test_中文热搜只是加成不能单独把一条顶上来():
    """中文平台比 Google 热搜重一点（×4 vs ×3）——读者就在那儿。

    但仍然是**加成**：三家在报、零中文热搜的那条，仍然要排在
    一家在报、撞满中文热搜的那条前面。中文那边热而没有一家媒体在报的事，
    产物里 `zh_hot` 那一栏会单独列出来，不该靠打分挤进选题候选。
    """
    zh = [{"word": f"热搜{i}", "terms": ["draper"]} for i in range(3)]
    thin = measure_heat(
        [{"title": "Draper withdraws", "source": "ATP Tour"}], zh_signals=zh
    )
    thick = measure_heat(
        [{"title": "Sinner withdraws", "source": "ATP Tour"},
         {"title": "Sinner out", "source": "ESPN"},
         {"title": "Sinner pulls out", "source": "BBC"}],
    )
    assert thin.zh_hits == 3 and thick.zh_hits == 0
    assert thick.score > thin.score


def test_产物里带着信号数和没对上的词(tmp_path):
    """queue 文件要能自己回答「今天为什么没有候选」。"""
    from tennislive.research.topic_radar import distil_topics as _d

    news = [
        _h("Alcaraz unveils his new Nike kit", "ATP Tour"),
        _h("Inside the Alcaraz Nike kit launch", "ESPN"),
    ]
    topics, leftover = _d(news)
    payload = {
        "count": len(topics),
        "unmatched_clusters": len(leftover),
        "unmatched_terms": [{"term": t, "clusters": n} for t, n in leftover_terms(leftover)],
    }
    (tmp_path / "q.json").write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
    back = json.loads((tmp_path / "q.json").read_text("utf-8"))
    assert back["count"] == 0
    assert back["unmatched_clusters"] == 1
    assert any(x["term"] == "nike" for x in back["unmatched_terms"])


def test_该补什么角度那份清单必须是确定的():
    """本地过、CI 红，查出来是 `Counter.most_common` 在**计数全相同**时按插入
    顺序返回，而插入顺序来自遍历 `set`——字符串的 set 顺序取决于
    `PYTHONHASHSEED`，每个进程都不一样。

    这不只是测试不稳：这份清单是给人看「该往 ANGLES 里补什么角度」的，
    每次随机取八个等于没写。改成按 (-次数, 词) 排。
    """
    import subprocess
    import sys

    code = (
        "from tennislive.research.topic_radar import distil_topics, leftover_terms\n"
        "h=lambda t,s:{'title':t,'source':s,'url':'x'}\n"
        "n=[h('Alcaraz unveils his new Nike kit','ATP Tour'),"
        " h('Inside the Alcaraz Nike kit launch','ESPN')]\n"
        "print([x[0] for x in leftover_terms(distil_topics(n)[1])])\n"
    )
    seen = set()
    for seed in ("0", "1", "12345", "99999"):
        out = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True,
            env={"PYTHONHASHSEED": seed, "PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
        )
        assert out.returncode == 0, out.stderr
        seen.add(out.stdout.strip())
    assert len(seen) == 1, f"不同 PYTHONHASHSEED 下结果不一致：{seen}"
    only = seen.pop()
    assert "nike" in only, "这个例子必须真的撞不上角度，否则测的是一份空清单"
    # 拼接词是聚类的中间产物，人读起来是噪点，不该出现在这份清单里
    assert "nikekit" not in only
