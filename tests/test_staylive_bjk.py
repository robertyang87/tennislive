"""金杯官网视频库（StayLive）取数工具的判据——只测不联网的那两个函数。"""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "staylive_bjk", Path(__file__).resolve().parents[1] / "tools" / "staylive_bjk.py"
)
staylive_bjk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(staylive_bjk)


def test_整节直播回放和集锦要分得开():
    # 库里 2025 深圳总决赛的真实标题：集锦带 Highlights 字样，整节回放是「A vs. B」
    assert (
        staylive_bjk.kind(
            "Jasmine Paolini (ITA) v Wang Xinyu (CHN) | 2025 Finals | Match Highlights"
        )
        == "highlights"
    )
    assert staylive_bjk.kind("Jasmine Paolini vs. Xinyu Wang") == "replay"
    assert (
        staylive_bjk.kind("Sara Errani & Jasmine Paolini vs. Xinyu Jiang & Shuai Zhang")
        == "replay"
    )
    assert staylive_bjk.kind("Press conference: Italy") == "press"
    assert (
        staylive_bjk.kind("Elise Mertens (BEL) – 2026 Qualifiers Pre-Event Feature")
        == "interview"
    )
    assert staylive_bjk.kind("2025 BJK Cup Finals Shenzhen drone show") == "other"


def test_grep扫标题也扫描述且不分大小写():
    v = {
        "name": "Coming Soon: 2026 Billie Jean King Cup Finals Shenzhen",
        "description": None,
    }
    assert staylive_bjk.matches(v, r"shenzhen")
    assert not staylive_bjk.matches(v, r"\(CHN\)")
    assert staylive_bjk.matches({"name": "x", "description": "host China"}, r"china")


def test_频道表里金杯和戴维斯杯的号不重叠():
    assert not set(staylive_bjk.BJK_CHANNELS) & set(staylive_bjk.DAVIS_CHANNELS)
    assert staylive_bjk.BJK_CHANNELS["7179"] == "bjkc-2026"


def test_锁地域的条目要说清楚而不是KeyError():
    import pytest

    blocked = {
        "name": "Jasmine Paolini vs. Xinyu Wang",
        "geo_restricted": {"allowed": False, "currentCountry": "US"},
    }
    with pytest.raises(SystemExit) as e:
        staylive_bjk.playback_url(blocked)
    assert "锁地域" in str(e.value) and "US" in str(e.value)
    assert (
        staylive_bjk.playback_url({"playback_url": "https://x/master.m3u8"})
        == "https://x/master.m3u8"
    )
