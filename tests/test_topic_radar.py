"""选题雷达：把每天的新闻提炼成选题候选，而不是快讯候选。"""

from __future__ import annotations

import json

from tennislive.research.topic_radar import (
    ANGLES,
    cluster_headlines,
    distil_topics,
    leftover_terms,
    match_angle,
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


def test_已发过的选题标出来并排到后面():
    """账本撞上就标「做过」，别让同一条隔一周再冒出来一次。

    仍然返回它——今年的新闻可能值得做续集，但要让人一眼看见做过。
    """
    news = [
        _h("Kyrgios handed Wimbledon wild card by AELTC", "ATP Tour"),
        _h("AELTC confirms Kyrgios wild card for Wimbledon", "ESPN"),
        _h("Draper to undergo surgery after arm injury", "BBC"),
        _h("Draper surgery confirmed, injury rules him out for months", "Sky Sports"),
    ]
    topics, _ = distil_topics(news, state_path=None)
    labels = [t.angle.slug for t in topics]
    assert "wildcard" in labels and "protected-ranking" in labels
    # wildcard 2026-07-28 已发，应当排在没做过的那条后面
    done = published_topics()
    if "wildcard" in done:
        assert labels.index("wildcard") > labels.index("protected-ranking")
        wc = next(t for t in topics if t.angle.slug == "wildcard")
        assert wc.published_on == done["wildcard"]


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

    hot_but_unmatched = [
        _h("Wimbledon ballkid selection begins for the season", "ATP Tour"),
        _h("How Wimbledon picks its ballkid squad each season", "ESPN"),
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


def test_产物里带着信号数和没对上的词(tmp_path):
    """queue 文件要能自己回答「今天为什么没有候选」。"""
    from tennislive.research.topic_radar import distil_topics as _d

    news = [
        _h("Wimbledon ballkid selection begins", "ATP Tour"),
        _h("How Wimbledon picks its ballkid squad", "ESPN"),
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
    assert any(x["term"] == "ballkid" for x in back["unmatched_terms"])
