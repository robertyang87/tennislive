"""出片一律竖版——三条视频线的画布都要高大于宽。

账号所有者 2026-09-25：「**作为短视频最好还是竖版**」。来路是拆参考账号
李小球Tennis（`tennis-editorial`「第九个账号」）：它的长片是 16:9 横版原片、
另一家居说那条是 4:3 横版，而我们三条线早就都是竖版——赛场之上 / 赛后开麦
1080×1440（3:4），网球有故事 1080×1920（9:16）。

**这条测的不是「现在是几比几」**（各条线自己的测试钉着具体数），而是**跨线的
那条口径**：哪天有人想「这场是老转播，4:3 原样放更完整」而把某条线的画布改成
横的，这儿当场红。3:4 和 9:16 之间怎么选仍是各条线自己的事，不在这条管辖内。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _tools(name: str):
    sys.path.insert(0, str(Path("tools").resolve()))
    return __import__(name)


def _canvases() -> dict[str, tuple[int, int]]:
    from tennislive.video import explainer, outro_page  # noqa: PLC0415

    reel = _tools("build_match_reel")
    interview = _tools("build_interview_clip")
    return {
        "赛场之上 build_match_reel": (reel.VIDEO_W, reel.VIDEO_H),
        "赛后开麦 build_interview_clip": (interview.CANVAS_W, interview.CANVAS_H),
        "网球有故事 explainer（默认 9:16）": (explainer.VIDEO_W, explainer.VIDEO_H),
        "网球有故事 explainer（认领 3:4）": (explainer.VIDEO_W, explainer.CARD_H),
        "品牌片尾 outro_page": (outro_page.VIDEO_W, outro_page.VIDEO_H),
    }


@pytest.mark.parametrize("line", list(_canvases()))
def test_出片画布一律竖版(line):
    w, h = _canvases()[line]
    assert h > w, (
        f"{line} 的画布是 {w}×{h}，不是竖版。账号所有者 2026-09-25："
        "「作为短视频最好还是竖版」——老转播是 4:3 / 16:9 也要裁进竖版画布，"
        "见 tennis-editorial「第九个账号：李小球Tennis」。"
    )


def test_竖版判据的主语没丢():
    """扫到的画布少于四条就说明有条线被漏掉了，那条的横版改动这儿看不见。

    反向验证过（2026-09-25）：把 `outro_page` 的画布临时改成 1440×1080，
    `test_出片画布一律竖版` 红在「品牌片尾 outro_page 的画布是 1440×1080」那一行。
    """
    assert len(_canvases()) >= 4, "扫到的画布少于四条线，判据的主语丢了"


def test_横屏只许出现在那条单独认领的小路上():
    """竖版是三条常规线的口径；**唯一的例外是账号所有者点名要的横屏原片**。

    2026-09-25 拉沃尔杯出场：「单独出一个视频……横屏的，不裁切画面」。它走
    `tools/build_landscape_clip.py`，不挂任何栏目、不进上面那张画布表——
    所以这里钉两件事：那条小路确实是 16:9 横屏（它存在的全部理由），
    而且它**不许被上面三条线 import 去用**（那等于把横屏偷渡进常规线）。
    """
    lc = _tools("build_landscape_clip")
    assert (lc.CANVAS_W, lc.CANVAS_H) == (1920, 1080)
    for f in ("build_match_reel.py", "build_interview_clip.py"):
        assert "build_landscape_clip" not in (Path("tools") / f).read_text(encoding="utf-8"), (
            f"{f} 引用了横屏那条小路——横屏只给单独认领的原片用，常规线一律竖版")
