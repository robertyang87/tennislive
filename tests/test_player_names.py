from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennislive.zh import player_zh


SNAPSHOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "tennislive"
    / "zh"
    / "player_names_top500.json"
)


def test_top_500_snapshot_has_1000_chinese_first_display_names():
    from tools.update_player_names import validate_snapshot

    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    validate_snapshot(payload)

    for tour in ("ATP", "WTA"):
        entries = payload["tours"][tour]
        assert len(entries) == 500
        assert all(player_zh(entry["name_en"]) != entry["name_en"] for entry in entries)


def test_official_media_form_and_feed_aliases_are_resolved():
    assert player_zh("Learner Tien") == "勒纳·钱"
    assert player_zh("Felix Auger-Aliassime") == "阿利亚西姆"
    assert player_zh("Brandon Nakashima") == "中岛布兰登"
    assert player_zh("Iga Swiatek") == "斯瓦泰克"
    assert player_zh("Ann Li") == "李吉妮"
    assert player_zh("Joanna Garland") == "葛蓝乔安娜"
    assert player_zh("Sara Sorribes Tormo") == "索里贝斯·托莫"
    assert player_zh("Tamara Korpatsch") == "科尔帕奇"
    assert player_zh("Chak Lam Coleman Wong") == "黄泽林"
    assert player_zh("Aleksandr Shevchenko") == "舍甫琴科"
    assert player_zh("Catherine McNally") == "麦克纳莉"


def test_同姓不同人不能靠姓氏兜底混成一个():
    """**「表里这个姓只有一个人」只说明表里只有一个，不说明是同一个人。**

    2026-07-29 查黄泽林那场时撞出来的：香港有两个姓 Wong 的球员同一天在打，
    `Coleman Wong`（黄泽林，男，ATP）在表里，`Hong Yi Cody Wong`（女，WTA）
    不在——姓氏兜底把她也解析成「黄泽林」，错的人还错了性别。

    兜底不能删：ESPN 给黄泽林的写法是 `Chak Lam Coleman Wong`，全名、反序、
    去中间名三条都匹配不上，正是靠它才认出来的。所以判据要能同时分开三种：

        Chak Lam Coleman Wong  vs  coleman wong    同一个词        → 认
        Catherine McNally      vs  caty mcnally    昵称，不共用词  → 认
        Hong Yi Cody Wong      vs  coleman wong    两个人          → 不认

    中间那条是第一版漏掉的：只要求「共用一个词」会把 Catherine 拦掉。按名的
    公共前缀算就分得开——catherine/caty 共三个字符，cody/coleman 只共两个。
    """
    # 认得出来的
    assert player_zh("Chak Lam Coleman Wong") == "黄泽林"
    assert player_zh("Coleman Wong") == "黄泽林"
    assert player_zh("Catherine McNally") == "麦克纳莉"
    assert player_zh("Caty McNally") == "麦克纳莉"
    # **认不出来好过认成另一个人**：原样返回英文名
    for other in ("Hong Yi Cody Wong", "Cody Wong"):
        assert player_zh(other) == other, (
            f"{other} 被解析成了 {player_zh(other)}——那是另一个人")


def test_official_ranking_text_parsers_require_exact_top_500_coverage():
    from tools.update_player_names import parse_atp_text, parse_wta_text

    atp_text = "\n".join(
        f"{rank} Surname{rank}, Given{rank} (USA) {1000-rank} 0 0 0"
        for rank in range(1, 501)
    )
    wta_blocks = []
    for rank in range(1, 501):
        name = (
            "SÁNCHEZ, ANA SOFIA"
            if rank == 417
            else f"SURNAME{rank}, GIVEN{rank}"
        )
        wta_blocks.extend(
            [str(rank), f"({rank})", name, "USA", "100"]
        )

    assert len(parse_atp_text(atp_text)) == 500
    wta = parse_wta_text("\n".join(wta_blocks))
    assert len(wta) == 500
    assert wta[416].name == "Ana Sofia Sánchez"

    with pytest.raises(ValueError, match="found=499"):
        parse_atp_text(atp_text.rsplit("\n", 1)[0])


def test_snapshot_validator_rejects_an_english_primary_name():
    from tools.update_player_names import validate_snapshot

    valid = [
        {"rank": rank, "name_en": f"Player {rank}", "name_zh": f"球员{rank}"}
        for rank in range(1, 501)
    ]
    payload = {"tours": {"ATP": list(valid), "WTA": list(valid)}}
    payload["tours"]["WTA"][80] = {
        "rank": 81,
        "name_en": "Tamara Korpatsch",
        "name_zh": "Tamara Korpatsch",
    }

    with pytest.raises(ValueError, match="non-Chinese"):
        validate_snapshot(payload)


def test_cctv_is_the_highest_translation_source_after_native_names():
    from tools.update_player_names import _source_priority, _store_translation

    cctv = _source_priority("央视网", "https://sports.cctv.com/example")
    xinhua = _source_priority("新华社", "https://www.news.cn/example")
    sport_gov = _source_priority(
        "国家体育总局", "https://www.sport.gov.cn/example"
    )
    tournament = _source_priority(
        "中国网球公开赛", "https://www.chinaopen.com/example"
    )

    assert _source_priority("球员原生中文名") > cctv
    assert cctv > xinhua > sport_gov > tournament
    assert _source_priority("央视网", "https://example.com/not-cctv") < cctv

    lookup = {}
    _store_translation(
        lookup,
        "Example Player",
        ("央视译名", "央视网", "https://sports.cctv.com/example"),
    )
    _store_translation(
        lookup,
        "Example Player",
        ("新华社译名", "新华社", "https://www.news.cn/newer-example"),
    )
    assert lookup["example player"][0] == "央视译名"


def test_review_queue_is_non_blocking_and_only_contains_provisional_names():
    from tools.update_player_names import build_review_queue

    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    queue = build_review_queue(payload)
    expected = {
        entry["name_en"]
        for tour in ("ATP", "WTA")
        for entry in payload["tours"][tour]
        if entry["translation_source"] == "machine-transliteration"
        or "待国内媒体复核" in entry["translation_source"]
    }

    assert queue["blocking"] is False
    assert {entry["name_en"] for entry in queue["entries"]} == expected
    assert "Learner Tien" not in expected


def test_带重音的拼法要认得出是同一个人():
    """**同一个人换个拼法就掉回英文名，而且不吭声。**

    `player_zh("Gaël Monfils")` 原样返回 `Gaël Monfils`，
    `player_zh("Gael Monfils")` 给「孟菲尔斯」——卡片上就是一个英文名混在
    一排中文名里，看着像「这个人表里没有」，和真的没有长得一模一样。

    2026-08-01 查洛斯卡沃斯四强时撞到：对手 `Arthur Géa` 是法国人，维基
    条目标题带重音；ESPN 恰好给的是不带重音的写法，**纯属运气**。

    折叠同时作用在建索引和查询两边，所以它只把「查不到」变成「查得到」。

    ⚠️ `đ` 要折成 `dj` 而不是 `d`：塞尔维亚语的拉丁转写就是这么写的
    （`Đoković` → `Djokovic`，表里正是后者）。折成 `d` 得到 `dokovic`，
    照样查不到——**一个改一半的折叠比不折更难发现**，因为它看起来已经修过了。
    """
    from tennislive.zh import player_zh

    pairs = [
        ("Gael Monfils", "Gaël Monfils"),
        ("Felix Auger-Aliassime", "Félix Auger-Aliassime"),
        ("Arthur Gea", "Arthur Géa"),
        ("Novak Djokovic", "Novak Đoković"),
    ]
    for plain, accented in pairs:
        zh = player_zh(plain)
        assert zh != plain, f"{plain} 本来就查不到，这条测试的前提不成立"
        assert player_zh(accented) == zh, (
            f"{accented} 没解析成 {zh}，而是 {player_zh(accented)}——"
            "带重音的拼法掉回了英文名")

    # 反面：折叠不许把本来查得到的改掉
    for name, expect in (("Zheng Qinwen", "郑钦文"),
                         ("Chak Lam Coleman Wong", "黄泽林"),
                         ("Elina Svitolina", "斯维托丽娜")):
        assert player_zh(name) == expect, f"{name} 被折叠改坏了"
