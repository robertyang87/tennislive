"""比分板回贴的右缘要跟着板的真实长度走——spec 的 scorebox x1 是提示，不是上限。

账号所有者 2026-09-25：「比分板剪切有问题，双打的比较长」「同时要自适应不同的
长度啊」。拉沃尔杯单打三条 spec 的 scorebox 都写 x1=520，而 `alcaraz-mensik`
双打板（「ALCARAZ / MENSIK」）抽帧量到 ~590；单打 `bublik-jodar` 那几帧的
「2 0 AD」也被切在 380 附近——两行的结构段在比分数字那一截就断了，原来往右只接
70px。ATP / WTA / ITF 三家则是 `min(量到的, spec x1)` 硬封顶。

判据用合成源片（numpy 画板 → ffv1 无损，走真的 ffmpeg 解码）过一遍 `resolve_masks`：
(a) 板比 spec x1 长 → 贴片盖住整块板，并且出声；(b) 板比 x1 短 → 照旧按板裁，不多抠球场。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import atp_scoreboard as atp  # noqa: E402
import itf_scoreboard as itf  # noqa: E402
import lavercup_scoreboard as laver  # noqa: E402
import wta_scoreboard as wta  # noqa: E402

W, H = 1920, 1080
FPS = "10"


def _write_source(tmp: Path, frame: np.ndarray, name: str = "src.mkv") -> Path:
    """一帧 RGB 画面 → 1 秒无损源片（ffv1 bgr0，颜色逐像素不变）。"""
    src = tmp / name
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pixel_format", "rgb24",
         "-video_size", f"{W}x{H}", "-framerate", FPS, "-i", "-",
         "-c:v", "ffv1", "-pix_fmt", "bgr0", str(src)],
        input=frame.tobytes() * 10, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    return src


def _seg(box):
    return SimpleNamespace(score_inset=tuple(box), source="main", start=0.0, end=0.8,
                           speed=1.0, score_inset_mask=None, score_inset_spans=None)


def _mask(path: str, w: int, h: int) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w)


# ---------------------------------------------------------------- 拉沃尔杯

LC_BOX = (80, 862, 520, 1036)       # 三条单打 spec 写的就是这个框


def _laver_frame(right: int, digits_from: int = 250) -> np.ndarray:
    """紧凑版两行板，右缘在源片 x=80+right。比分数字那一截（名字之后）用灰字铺满
    行中间，让「四条描边都在＋行中间是底或字」的结构段在那儿断开——真片子就是这样。"""
    f = np.zeros((H, W, 3), np.uint8)
    f[:] = (80, 73, 81)                                         # 球场
    x0, y0 = LC_BOX[0], LC_BOX[1]
    left = 17
    for (a, b), edge in (((58, 106), (15, 47, 85)), ((108, 154), (55, 0, 13))):
        f[y0 + a:y0 + b, x0 + left:x0 + right] = edge          # 描边
        f[y0 + a + 4:y0 + b - 4, x0 + left + 4:x0 + right - 4] = (7, 7, 7)
        f[y0 + a + 16:y0 + b - 16, x0 + left + 30:x0 + left + 120] = (185, 183, 186)
        # 比分数字：抗锯齿的灰把行中间占掉
        f[y0 + a + 6:y0 + b - 6, x0 + digits_from:x0 + right - 30] = (110, 110, 110)
    f[y0 + 22:y0 + 54, x0 + 21:x0 + 150] = (131, 120, 74)     # 金色标签
    return f


def test_拉沃尔杯_板比spec右缘长_贴片盖住整块板并出声(tmp_path, capsys):
    """双打板右缘在 590（spec 写 520）：原来结构段在 330 就断，往右只接 70px，
    贴片停在 ~400，最后几列比分和右端圆头全被切掉，一声不吭。"""
    src = _write_source(tmp_path, _laver_frame(510))
    seg = _seg(LC_BOX)
    laver.resolve_masks({"main": src}, [seg], tmp_path, FPS, 0.0)
    assert seg.score_inset[2] >= 80 + 510, seg.score_inset
    assert seg.score_inset[2] <= 80 + 510 + 6, "越过板右缘多抠了球场"
    out = capsys.readouterr().out
    assert "比 spec scorebox 右缘 520" in out, out
    m = _mask(seg.score_inset_mask, seg.score_inset[2] - 80, 174)
    assert m[3][82, 505] == 255 and m[3][130, 505] == 255      # 右端圆头之前那一列在蒙版里


def test_拉沃尔杯_板比spec右缘短_照旧按板裁不多抠球场(tmp_path, capsys):
    src = _write_source(tmp_path, _laver_frame(380))
    seg = _seg(LC_BOX)
    laver.resolve_masks({"main": src}, [seg], tmp_path, FPS, 0.0)
    assert 80 + 380 <= seg.score_inset[2] <= 80 + 380 + 6, seg.score_inset
    assert "比 spec scorebox 右缘" not in capsys.readouterr().out


def test_拉沃尔杯_名字长的双打紧凑板不许被认成宽版面板():
    """双打名字那一截结构段碎掉，第一截够宽的要到 x≈190 才出现——按它判宽版，
    紧凑板会被当成整条带高的矩形抠出去（`alcaraz-mensik` 抽帧 93s）。判宽版看描边从哪儿起。"""
    band = _laver_frame(560, digits_from=400)[862:1036, 80:1000].copy()
    for a, b in ((64, 100), (114, 148)):                 # 长名字把两行的行中间占满
        band[a:b, 17 + 30:17 + 175] = (110, 110, 110)
    ps = laver.pills(band)
    assert ps is not None and len(ps) >= 2, ps
    assert all(p[2] > 0 for p in ps), f"被认成了宽版面板：{ps}"
    assert ps[0][0] <= 20 and ps[0][1] >= 560


def test_描边接到扫描带右头时退回老的封顶():
    zone = np.ones(900, bool)
    assert laver._reach_right(zone, 400) == 400 + laver.LEFT_REACH
    zone[520:] = False
    assert laver._reach_right(zone, 400) == 520


# ---------------------------------------------------------------- ATP / WTA / ITF

ATP_BOX = (40, 930, 400, 1038)      # spec 按单打板量的 x1


def _atp_frame(board_w: int) -> np.ndarray:
    f = np.zeros((H, W, 3), np.uint8)
    f[:] = (123, 167, 128)
    x0, y0, _x1, y1 = ATP_BOX
    f[y0:y1, x0:x0 + board_w] = (6, 16, 36)
    f[y0:y1, x0 + board_w - 100:x0 + board_w - 52] = (22, 16, 248)     # 盘分格
    f[y0 + 20:y0 + 30, x0 + 20:x0 + 120] = (240, 255, 250)
    return f


def test_ATP_板比spec右缘长_贴片盖住整块板并出声(tmp_path, capsys):
    src = _write_source(tmp_path, _atp_frame(470))                     # 右缘 510 > spec 400
    seg = _seg(ATP_BOX)
    atp.resolve_masks({"main": src}, [seg], tmp_path, FPS, 0.0)
    assert seg.score_inset[2] >= 40 + 470, seg.score_inset
    assert seg.score_inset[2] <= 40 + 470 + 4
    assert "比 spec scorebox 右缘 400" in capsys.readouterr().out


def test_ATP_板比spec右缘短_照旧按板裁(tmp_path, capsys):
    src = _write_source(tmp_path, _atp_frame(300))
    seg = _seg(ATP_BOX)
    atp.resolve_masks({"main": src}, [seg], tmp_path, FPS, 0.0)
    assert 40 + 300 <= seg.score_inset[2] <= 40 + 300 + 4, seg.score_inset
    assert "比 spec scorebox 右缘" not in capsys.readouterr().out


def test_ATP_越过提示的那一截要有盘分蓝撑着_深色挡板骗不过():
    band = np.zeros((108, 760, 3), np.uint8)
    band[:] = (123, 167, 128)
    band[:, :300] = (6, 16, 36)
    band[:, 240:270] = (22, 16, 248)            # 盘分格止于 270
    band[20:30, 20:120] = (240, 255, 250)
    band[:, 300:600] = (6, 16, 36)              # 近景深蓝挡板贴着板右边
    assert atp.board_edge(band) == 600, "不给提示时量到的就是连成一片的宽度"
    e = atp.board_edge(band, cap=300)
    assert e == 270 + atp.POINTS_MAX, e         # 最多到最后一格蓝再一格小分宽
    band[:, 600:] = (6, 16, 36)                 # 一路连到带右头：不可信，退回提示
    assert atp.board_edge(band, cap=300) == 300


def test_WTA_有薄荷绿钉着才越过提示():
    def band(board_w, mint=True):
        b = np.zeros((110, 760, 3), np.uint8)
        b[:] = (125, 179, 110)
        b[:, :board_w] = (55, 95, 66)
        b[20:30, 30:120] = (254, 255, 253)
        b[70:80, 30:110] = (254, 255, 253)
        if mint:
            b[:, board_w - 80:board_w - 54] = (21, 255, 171)
        return b
    assert wta.board_edge(band(459), cap=420) == 459
    assert wta.board_edge(band(459, mint=False), cap=420) == 420


def test_ITF_扫描带不再按spec板宽的1点3倍封死_有浅青格撑着就按量到的走():
    h = 97

    def band(board_w, cells=True, width=900):
        b = np.zeros((h, width, 3), np.uint8)
        b[:] = (117, 195, 252)
        b[4:h - 4, :board_w - 40] = (24, 79, 240)
        if cells:
            b[4:h - 4, board_w - 40:board_w] = (142, 255, 251)
        b[15:30, 40:130] = (228, 254, 255)
        return b
    assert itf.board_edge(band(560), cap=390) == 560
    assert itf.board_edge(band(300), cap=390) == 300
    no_cells = band(560, cells=False)
    assert itf.board_edge(no_cells, cap=390) == 390

