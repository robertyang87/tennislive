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
