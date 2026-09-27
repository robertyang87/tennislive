"""英文字幕统一走 Inter SemiBold；回贴了比分板的全出血片子，字幕底边钉在板正上方。

账号所有者 2026-09-26：「我们的英文字幕字体感觉不够美观精致」「要把所有英文字幕
样式都改掉，保证以后统一」——看过五款并排对比选了 Inter；同一轮「建议字幕可以
往下来一点」，看过前后对比选了「底边钉在比分板上方 24px」那一版。
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from tennislive.video import explainer as E  # noqa: E402


def test_三条线的英文字体是同一支():
    import build_interview_clip as clip
    assert clip._ASS_NAME["en"] == E._ASS_EN_FONT
    assert Path(clip._FONT_FILES["en"][0]) == E._ASS_EN_FONT_FILE


def test_字体名是文件自己声明的那个():
    ttlib = pytest.importorskip("fontTools.ttLib")
    names = {r.toUnicode() for r in ttlib.TTFont(E._ASS_EN_FONT_FILE)["name"].names
             if r.nameID in (1, 4, 16)}
    assert E._ASS_EN_FONT in names, f"ASS 里写的名字 libass 认不出，会静静回退：{names}"


def test_解说片的字幕滤镜带fontsdir():
    src = Path(E.__file__).read_text(encoding="utf-8")
    assert ":fontsdir='{_filter_path(_ASS_EN_FONT_FILE.parent)}'" in src, \
        "解说片烧字幕不带 fontsdir，仓库里的 Inter 读不到"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="要 ffmpeg 真渲一帧")
def test_libass真的用上了Inter(tmp_path):
    """和一个不存在的字体名比渲染结果：一样就说明回退了（本文件那条老账）。"""
    def burn(font: str) -> str:
        ass = tmp_path / f"{hashlib.md5(font.encode()).hexdigest()}.ass"
        E.write_subtitles([(0.0, 2.0, "What a way to finish!\n太漂亮了")], ass,
                          height=1440, margin_v=1284, outline=4, shadow=1)
        ass.write_text(ass.read_text("utf-8").replace(E._ASS_EN_FONT, font), "utf-8")
        png = ass.with_suffix(".png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", "color=c=black:s=1080x1440:d=2",
                        "-vf", f"subtitles={ass}:fontsdir={E._ASS_EN_FONT_FILE.parent}",
                        "-ss", "0.5", "-frames:v", "1", str(png)], check=True)
        return hashlib.md5(png.read_bytes()).hexdigest()
    assert burn(E._ASS_EN_FONT) != burn("NoSuchFontXYZ"), "Inter 没被 libass 认出来"


def test_有比分板时每条字幕都下锚_底边在板上方():
    import build_match_reel as reel

    class Seg:
        score_inset = (0, 920, 519, 1029)

    class NoBoard:
        score_inset = None

    bottom = reel.subtitle_bottom_for_boards([Seg(), NoBoard()], column="赛场之上")
    board_top = round(920 * reel.VIDEO_W / reel.CROP_W)
    assert bottom == reel.VIDEO_H - (board_top - reel.SCORE_INSET_GAP_PX)
    assert reel.subtitle_bottom_for_boards([NoBoard()], column="赛场之上") is None


def test_字幕下移只给赛场之上_别的栏目有板也不挪():
    """账号所有者 2026-09-27：「字幕下移的只有赛场之上，因为他有比分板」。
    网球有故事的剪辑片同样走 build_match_reel，借一段带板的画面也不许跟着挪。"""
    import build_match_reel as reel

    class Seg:
        score_inset = (0, 920, 519, 1029)

    assert reel.subtitle_bottom_for_boards([Seg()], column="赛场之上") is not None
    for other in ("网球有故事", "开球之前", ""):
        assert reel.subtitle_bottom_for_boards([Seg()], column=other) is None, other


def test_bottom_margin给了就每条都下锚(tmp_path):
    ass = E.write_subtitles([(0.0, 1.0, "北京时间9月"), (1.0, 2.0, "Game.\n好球")],
                            tmp_path / "s.ass", height=1440, margin_v=1067,
                            outline=4, shadow=1, bottom_margin=237)
    rows = [r for r in ass.read_text("utf-8").splitlines() if r.startswith("Dialogue")]
    assert all(",0,0,237,,{\\an2}" in r for r in rows), rows
    # 不给照旧：单行上锚（MarginV=0 用样式那个数）
    ass2 = E.write_subtitles([(0.0, 1.0, "北京时间9月")], tmp_path / "t.ass",
                             height=1440, margin_v=1067)
    row = [r for r in ass2.read_text("utf-8").splitlines() if r.startswith("Dialogue")][0]
    assert ",0,0,0,," in row and "\\an2" not in row


def test_render把下锚接上了():
    src = (ROOT / "tools" / "build_match_reel.py").read_text(encoding="utf-8")
    assert "bottom_margin=bottom" in src
    assert "subtitle_bottom_for_boards(segments, column=column)" in src
