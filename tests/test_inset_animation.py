"""字卡/角标的入场动效：0.45s 淡入 + 上浮，默认开、能关掉。

来路：抖音七批创作诊断里六批点名「动态文字/卡片要有动感」（2026-08-09，
账号所有者转来）。判据必须真渲——overlay 表达式写错了 ffmpeg 多半不报错，
只是卡片瞬间出现或干脆不出现，和「没写」长得一样。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_match_reel import (  # noqa: E402
    EDITORIAL_IN_SECS,
    EDITORIAL_RISE_PX,
    INSET_IN_SECS,
    Segment,
    _overlay_chain,
    cut_segment,
)


def _mk_source(tmp: Path) -> Path:
    """纯灰底源片（无音轨——顺带走一遍 null_idx=2 那条补静音路）。"""
    src = tmp / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "color=c=0x303030:size=1920x1080:rate=25:duration=4",
         "-c:v", "libx264", "-preset", "ultrafast", str(src)],
        check=True, capture_output=True, text=True)
    return src


def _mk_card(tmp: Path) -> Path:
    from PIL import Image  # noqa: PLC0415

    card = tmp / "card.png"
    Image.new("RGBA", (400, 240), (0, 200, 0, 255)).save(card)
    return card


def _pixel(film: Path, at: float, xy: tuple[int, int]) -> tuple[int, int, int]:
    from PIL import Image  # noqa: PLC0415

    frame = film.with_suffix(f".t{at:.2f}.png")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{at}", "-i", str(film),
         "-frames:v", "1", str(frame)],
        check=True, capture_output=True, text=True)
    with Image.open(frame) as im:
        return im.convert("RGB").load()[xy]


def test_字卡入场要淡入上浮而且能关掉(tmp_path):
    src, card = _mk_source(tmp_path), _mk_card(tmp_path)
    # 卡贴 tl，pad=46；scale 到 367 宽 → 高约 220。取卡身中心附近的像素。
    probe_xy = (229, 156)

    seg = Segment(0.0, 3.0, 0.5, "", track=False,
                  inset={"image": str(card), "corner": "tl"})
    out = tmp_path / "animated.mp4"
    cut_segment(src, seg, out, 1920)
    r0, g0, _ = _pixel(out, 0.04, probe_xy)
    assert g0 - r0 < 40, (
        f"t=0.04 卡就全绿了（R={r0} G={g0}）——入场动效没生效，卡是瞬间出现的")
    r1, g1, _ = _pixel(out, INSET_IN_SECS + 1.0, probe_xy)
    assert g1 - r1 > 100, f"动效结束后卡该完全在场（R={r1} G={g1}）"

    seg_off = Segment(0.0, 3.0, 0.5, "", track=False,
                      inset={"image": str(card), "corner": "tl",
                             "animate": False})
    out2 = tmp_path / "static.mp4"
    cut_segment(src, seg_off, out2, 1920)
    r2, g2, _ = _pixel(out2, 0.04, probe_xy)
    assert g2 - r2 > 100, (
        f"animate:false 该保持老行为——第一帧卡就在（R={r2} G={g2}）")


def test_信息带可以限时出现并淡出(tmp_path):
    src, card = _mk_source(tmp_path), _mk_card(tmp_path)
    probe_xy = (229, 156)
    seg = Segment(0.0, 3.0, 0.5, "", track=False,
                  inset={"image": str(card), "corner": "tl", "show_for": 1.5})
    out = tmp_path / "timed.mp4"
    cut_segment(src, seg, out, 1920)
    r1, g1, _ = _pixel(out, 0.9, probe_xy)
    assert g1 - r1 > 100, "限时信息带在展示窗口内应完全可见"
    r2, g2, _ = _pixel(out, 2.0, probe_xy)
    assert g2 - r2 < 40, "限时信息带在 show_for 之后应淡出"


def test_编辑型屏幕文字用更克制的动效():
    chain = _overlay_chain(
        "[0:v]x[base]",
        {"image": "card.png", "corner": "tr", "motion": "editorial"},
    )
    assert f"d={EDITORIAL_IN_SECS}" in chain
    assert f"+{EDITORIAL_RISE_PX}*" in chain
    assert f"d={INSET_IN_SECS}" not in chain


def test_画常驻角标的栏目里顶角贴图要让开角标块(monkeypatch):
    """2026-09-05 comeback-five-love-down：story_text 按合同贴 tr/pad 0.085 落在 y=92，
    角标两行字占到 y≈125，贴图的标签行正压在「他们怎么赢回来的」上。合同是
    2026-08-24 定的、角标 2026-09-01 才有——前提变了，让位要在代码里做，不然
    下一条 spec 又照合同抄 0.085。只往下推、只推顶角；不画角标的栏目照旧。"""
    import re  # noqa: PLC0415
    import build_match_reel as reel  # noqa: PLC0415

    def y_of(chain: str) -> str:
        return re.search(r"overlay=[^:]+:(.*?)\[vout\]", chain).group(1)

    ins = {"image": "c.png", "corner": "tr", "width": 0.6, "pad": 0.085,
           "show_for": 3.8, "motion": "editorial", "animate": False}
    monkeypatch.setattr(reel, "_INSET_TOP_CLEAR_Y", 0)
    assert y_of(reel._overlay_chain("[0:v]x[base]", ins)) == "92"
    monkeypatch.setattr(reel, "_INSET_TOP_CLEAR_Y", 151)
    assert y_of(reel._overlay_chain("[0:v]x[base]", ins)) == "151"
    assert y_of(reel._overlay_chain("[0:v]x[base]", {**ins, "corner": "tl"})) == "151"
    assert y_of(reel._overlay_chain("[0:v]x[base]", {**ins, "pad": 0.2})) == "216", \
        "本来就比角标低的只往下推不往上拉"
    assert y_of(reel._overlay_chain("[0:v]x[base]", {**ins, "corner": "bl"})) == "H-h-92", \
        "底角不受角标影响"
    # 这条片子的真值：网球有故事、有副标题、没顶栏 → 44 + 56 + 27 + 24
    monkeypatch.setattr(reel, "LAYOUT", "full")
    spec = {"cover": {"eyebrow": "网球有故事", "topic": "决胜盘零比五"}}
    assert reel.inset_top_clear_y(spec) == 44 + 56 + 27 + reel.INSET_WATERMARK_GAP_PX
    assert reel.inset_top_clear_y({"cover": {"eyebrow": "网球有故事"}}) == 44 + 52 + reel.INSET_WATERMARK_GAP_PX
    assert reel.inset_top_clear_y({"cover": {"eyebrow": "赛场之上"}}) == 0, "不画角标的栏目不让"
    # render() 真的把它算进全局，且排在切段之前
    import inspect  # noqa: PLC0415
    body = inspect.getsource(reel.render)
    assert body.index("_INSET_TOP_CLEAR_Y = inset_top_clear_y(spec)") < body.index("def _encode_one(")
