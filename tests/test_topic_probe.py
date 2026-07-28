"""选题探图那一步的对题校验。

判据来自 2026-08 那一轮探图：两个槽位都报了健康的数字，点开全是错的图。
「混双」那一槽 28 张里排在最前的是 2018 青奥会的**乒乓球**混双——`table tennis`
里含着 `tennis`；「温网入口」那一槽 5 张里有考文垂教堂的彩窗和南温布尔登的地铁牌。
这正是 `_must` 想拦的那种错误，从它自己留的门里进来了。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from probe_topic_photos import TOPICS, on_topic  # noqa: E402


def test_关键词命中的仍然要对题():
    assert on_topic(
        "File:Mixed Doubles Wimbledon 2014.jpg",
        "Jamie Murray and Casey Dellacqua vs Horia Tecau and Sania Mirza",
        ["mixed doubles"],
    )


def test_乒乓球混双不算网球混双():
    """`table tennis` 里含着 `tennis`，靠 _must 挡不住。"""
    assert not on_topic(
        "File:Table tennis at the 2018 Summer Youth Olympics - Mixed Doubles.jpg",
        "Mixed doubles table tennis at the Youth Olympic Games",
        ["mixed doubles", "tennis"],
    )


def test_南温布尔登的地铁牌不算温网():
    assert not on_topic("File:South Wimbledon tube sign.jpg", "", ["wimbledon"])


def test_扫描版杂志不算照片():
    """探图第一轮的老账：温网赶鸽鹰报了 16 张，全是 1880 年代的杂志 PDF。"""
    assert not on_topic("File:Forest and Stream 1885.pdf", "hawk", ["hawk"])


def test_每个候选都写了对题词():
    """没有 _must 的槽位等于不校验，报出来的数字不能拿去排优先级。"""
    missing = [name for name, slots in TOPICS.items() if not slots.get("_must")]
    assert not missing, f"这些候选没写 _must：{missing}"
