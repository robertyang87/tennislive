"""中文平台热搜：把「舆论热点」这一维从英文媒体的家数扩到中文那边。

这套原来完全看不见中文舆论场——实测那天微博热搜第 43 位挂着
「郑钦文状态怎么了」，而当天所有英文源里一条相关的都没有。
"""

from __future__ import annotations

import json

import pytest

from tennislive.research.topic_radar import measure_heat
from tennislive.research.zh_trends import (
    UNAVAILABLE,
    fetch_zh_hot,
    near_miss,
    tennis_clues,
)


class _Fake:
    def __init__(self, payload: bytes):
        self.content = payload

    def raise_for_status(self):
        return None


def _weibo_payload(*words: str) -> bytes:
    return json.dumps(
        {"data": {"realtime": [{"word": w, "num": 1000} for w in words]}},
        ensure_ascii=False,
    ).encode("utf-8")


def test_两个字的译名要有网球语境才算():
    """「保罗」是保罗·乔治，「李娜」首先是歌手，「安倍」根本不是球员。

    译名表里有 154 个两字条目，直接当关键词用等于把半个热搜榜判成网球。
    所以两个字的名字默认要同现一个网球语境词——**除了 `_SHORT_OK` 里那几个**，
    判据是「这两个字在中文里既不是常用词，也不是别的名人的通用简称」。
    """
    assert tennis_clues("保罗乔治抖音发文寻找电动车男孩")[0] == ()
    assert tennis_clues("李娜回应")[0] == ()
    assert "保罗" in tennis_clues("网球保罗")[0]

    # 「辛纳」在 _SHORT_OK 里：世界第一，单独出现就算数
    assert tennis_clues("辛纳夺冠")[0] == ("辛纳",)


def test_单字译名一律不当关键词():
    """排名表里有 18 条机器音译只出了姓（`Jiaqi Wang` → 「王」、
    `Boyoung Jeong` → 「郑」）。拿它当关键词，一轮 150 条榜单里挡出 7 条纯噪声
    ——「王楚钦」「张泽禹」「郑」全被判成网球，还给「郑钦文状态怎么了」
    配上了一个韩国球员的英文词。
    """
    for word in ("王楚钦大满贯", "张泽禹想你的夜高音好绝", "齐达内出任法国队主教练",
                 "蒸出了奶香爆米花馒头"):
        assert tennis_clues(word)[0] == (), word

    # 真正的三字名照样命中，而且只带自己的英文词
    matched, terms = tennis_clues("郑钦文状态怎么了")
    assert matched == ("郑钦文",)
    assert set(terms) == {"qinwen", "zheng"}


def test_道德约束不是德约科维奇():
    """中文里连字成词防不住：「**道德约**束」的中间两个字就是「德约」。

    所以「德约」进的是弱信号，要同现别的网球线索才算；而全名「德约科维奇」
    五个字，单独出现就够。
    """
    assert tennis_clues("道德约束")[0] == ()
    assert "德约" in near_miss("道德约束")
    assert "德约科维奇" in tennis_clues("德约科维奇退赛")[0]


def test_中文热搜要先过译名表才能和英文簇对上():
    """中文词和英文标题之间**没有任何共享的字符串**——「郑钦文状态怎么了」
    和 `Zheng Qinwen reaches quarterfinal` 直接取交集永远是空的。

    所以 `zh_trends` 在抓的时候就把英文词算好挂在那一条上，热度那一步
    才有东西可交。这是整条中文线唯一的接缝，断了就等于没接。
    """
    heat = measure_heat(
        [{"title": "Zheng Qinwen withdraws from Montreal", "source": "ATP Tour"},
         {"title": "Qinwen Zheng pulls out", "source": "ESPN"}],
        zh_signals=[{"word": "郑钦文状态怎么了", "terms": ["qinwen", "zheng"]}],
    )
    assert heat.zh_hits == 1
    assert heat.zh_words == ("郑钦文状态怎么了",)
    # 撞不上的那条一点也不该加分
    cold = measure_heat(
        [{"title": "Draper withdraws from Washington", "source": "ATP Tour"},
         {"title": "Jack Draper pulls out of Washington", "source": "ESPN"}],
        zh_signals=[{"word": "郑钦文状态怎么了", "terms": ["qinwen", "zheng"]}],
    )
    assert cold.zh_hits == 0 and cold.score < heat.score


def test_挡掉的也要报出来():
    """只在成功时出声的过滤器，没法证明它真的看过。

    差一点算网球的（只有弱信号、或只有两个字的名字）要进 `near`，
    让人一眼看见挡掉了什么——「保罗乔治」被挡掉是对的，
    但这件事必须看得见。
    """
    result = fetch_zh_hot(
        get=lambda url, **kw: _Fake(_weibo_payload("保罗乔治发文", "郑钦文状态怎么了")),
        top=10,
    )
    words = {h.word for h in result.hits}
    assert words == {"郑钦文状态怎么了"}
    assert any(n["word"] == "保罗乔治发文" and "保罗" in n["clues"] for n in result.near)


def test_一个源挂了不挡住别的():
    """四个源并发抓，一个 403 不能把整条流水线拖停——和 `fetch_trend_signals`
    同一条规矩。挂掉的那个照实记进 `status`，不是静默跳过。
    """
    def flaky(url, **kw):
        if "weibo" in url:
            return _Fake(_weibo_payload("郑钦文状态怎么了"))
        raise TimeoutError("boom")

    result = fetch_zh_hot(get=flaky, top=10)
    assert [h.word for h in result.hits] == ["郑钦文状态怎么了"]
    assert any(v.startswith("降级") for v in result.status.values())


def test_扫了几条和中了几条都要报():
    """榜上一条网球都没有是**常态**（微博 51 条里通常 0～1 条）。

    只报「中了 0 条」的话，它和「抓挂了」长得一模一样——又一次
    「空结果先自证是真空」。所以状态里两个数都要有。
    """
    result = fetch_zh_hot(
        get=lambda url, **kw: _Fake(_weibo_payload("泸溪河桃酥", "AI剧")),
        top=10,
    )
    assert result.hits == []
    assert result.scanned > 0
    assert any("扫" in v and "网球 0 条" in v for v in result.status.values())


@pytest.mark.parametrize("name", sorted(UNAVAILABLE))
def test_拿不到的源要写在产物里而不是消失(name):
    """微信指数要小程序签名、小红书官方两个入口 404/500——**拿不到就写清楚
    拿不到，还有为什么**。悄悄少一个源，下次没人知道它曾经在名单上。
    """
    result = fetch_zh_hot(get=lambda url, **kw: _Fake(b"{}"), top=5)
    assert name in result.status
    assert result.status[name].startswith("拿不到")
