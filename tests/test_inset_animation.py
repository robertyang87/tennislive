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

from build_match_reel import INSET_IN_SECS, Segment, cut_segment  # noqa: E402


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
