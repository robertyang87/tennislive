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
    / "player_names_top300.json"
)


def test_top_300_snapshot_has_600_chinese_first_display_names():
    from tools.update_player_names import validate_snapshot

    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    validate_snapshot(payload)

    for tour in ("ATP", "WTA"):
        entries = payload["tours"][tour]
        assert len(entries) == 300
        assert all(player_zh(entry["name_en"]) != entry["name_en"] for entry in entries)


def test_official_media_form_and_feed_aliases_are_resolved():
    assert player_zh("Tamara Korpatsch") == "科尔帕奇"
    assert player_zh("Chak Lam Coleman Wong") == "黄泽林"
    assert player_zh("Aleksandr Shevchenko") == "舍甫琴科"
    assert player_zh("Catherine McNally") == "麦克纳莉"


def test_official_ranking_text_parsers_require_exact_top_300_coverage():
    from tools.update_player_names import parse_atp_text, parse_wta_text

    atp_text = "\n".join(
        f"{rank} Surname{rank}, Given{rank} (USA) {1000-rank} 0 0 0"
        for rank in range(1, 301)
    )
    wta_blocks = []
    for rank in range(1, 301):
        wta_blocks.extend(
            [str(rank), f"({rank})", "SURNAME, GIVEN", "USA", "100"]
        )

    assert len(parse_atp_text(atp_text)) == 300
    assert len(parse_wta_text("\n".join(wta_blocks))) == 300

    with pytest.raises(ValueError, match="missing"):
        parse_atp_text(atp_text.rsplit("\n", 1)[0])


def test_snapshot_validator_rejects_an_english_primary_name():
    from tools.update_player_names import validate_snapshot

    valid = [
        {"rank": rank, "name_en": f"Player {rank}", "name_zh": f"球员{rank}"}
        for rank in range(1, 301)
    ]
    payload = {"tours": {"ATP": list(valid), "WTA": list(valid)}}
    payload["tours"]["WTA"][80] = {
        "rank": 81,
        "name_en": "Tamara Korpatsch",
        "name_zh": "Tamara Korpatsch",
    }

    with pytest.raises(ValueError, match="non-Chinese"):
        validate_snapshot(payload)
