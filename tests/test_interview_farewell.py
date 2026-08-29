"""最后一战告别仪式必须是独立、可签名、可补冷开场的内容类型。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import attach_interview_lead_in as lead  # noqa: E402
import build_interview_request as request_builder  # noqa: E402
import interview_source_gate as gate  # noqa: E402


def _request() -> dict:
    return {
        "slug": "nishikori-sakamoto-us-open-2026-q3-farewell",
        "url": "https://www.youtube.com/watch?v=jBJ8mtkKGcM",
        "source": "US Open",
        "source_title": "Kei Nishikori's Final Match Presentation | 2026 US Open",
        "requested_content_type": "farewell",
        "event": "2026 美网 男单资格赛决胜轮",
        "winner": "坂本怜",
        "featured_player": "锦织圭",
        "opening": {"kind": "none", "why": "正文是独立告别仪式"},
        "match": {
            "id": "2026:us-open:q3:sakamoto-nishikori",
            "event": "2026 US Open",
            "event_search": "US Open",
            "round": "Qualifying Final Round",
            "year": 2026,
            "winner": "坂本怜",
            "loser": "锦织圭",
            "participants": ["坂本怜", "锦织圭"],
            "winner_en": "Rei Sakamoto",
            "loser_en": "Kei Nishikori",
        },
        "cover": {"frame_at": 34.0, "title": ["一", "二"], "sub": "告别", "tag": "锦织圭"},
        "takeaway": {"close": {"point": "告别", "ask": "记得哪场？"}},
        "push": {"matchup": "坂本怜 vs 锦织圭", "score": "6-4 7-6(3)", "auto": True},
    }


def test_官方最后一战标题被识别为farewell():
    assert gate.explicit_title_type(
        "Kei Nishikori's Final Match Presentation | 2026 US Open"
    ) == "farewell"
    assert gate.explicit_title_type("US Open final highlights") == ""


def test_farewell正式契约保留真实胜者与告别主角():
    spec = request_builder.build_spec(_request(), ["谢谢大家"], duration=90.0)
    assert spec["winner"] == "坂本怜"
    assert spec["featured_player"] == "锦织圭"
    assert spec["interview_kind"] == "赛后告别仪式"
    assert spec["source_verification"]["method"] == "official_explicit_farewell"
    assert len(gate.validate_source_contract(spec)) == 64


def test_farewell需要同场冷开场但捧杯致辞维持原规则():
    spec = request_builder.build_spec(_request(), ["谢谢大家"], duration=90.0)
    assert lead.needs_lead_in(spec)
    spec["requested_content_type"] = "ceremony"
    assert not lead.needs_lead_in(spec)
    spec["requested_content_type"] = "farewell"
    spec["lead_in"] = {"url": "https://example.test/highlight"}
    assert not lead.needs_lead_in(spec)


def test_请求文件本身可构建且比分方向没有反转():
    path = ROOT / "requests" / "interviews" / "nishikori-sakamoto-us-open-2026-q3-farewell.json"
    req = json.loads(path.read_text(encoding="utf-8"))
    spec = request_builder.build_spec(req, ["谢谢大家"], duration=120.0)
    assert spec["push"]["matchup"].startswith("坂本怜")
    assert spec["match"]["winner"] == "坂本怜"
    assert spec["match"]["loser"] == "锦织圭"
