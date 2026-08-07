"""`tools/detect_scorebox.py` 的算法本身，和一条端到端的视频冒烟测试。

判据核心是**填充率，不是面积**——记分条是实心矩形，阴影/树荫/看台深色衣服
这类暗色区域即使被闭运算粘成一坨，也是散的、填充率低。下面第一组测试直接
拿合成数组验这条判据（不用现造视频，几毫秒跑完）；最后一条用 ffmpeg 生成
一段真实小片子，验 `sample_gray_frames()` 到 `candidates_from_stack()` 这条
链子真的接得上。

2026-08-07 用 `zhang-putintseva` 这条真实 WTA 转播源片（1280×720，188.7s）
端到端验过：肉眼量出的真值 `(61,579)-(359,653)`，这个脚本猜出
`(61,579)-(382,654)`——三边对齐，右边多 23px，不影响下游判据（见工具
docstring）。**只有这一份真实样本**，没有跨转播商验证过，这条限制写在
工具的 docstring 里，不在这份测试里重复断言（重复了也验证不了什么）。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

pytest.importorskip("cv2", reason="visualqa extra")

import detect_scorebox as dsb  # noqa: E402


def _rng():
    return np.random.default_rng(20260807)


def test_实心矩形要被识别为候选():
    """记分条：一块几何位置锁死的实底深色矩形，文字/高亮闪烁不影响判它在。"""
    rng = _rng()
    n, h, w = 40, 300, 400
    stack = np.full((n, h, w), 200.0, dtype=np.float32)  # 明亮背景（球场）
    y0, y1, x0, x1 = 200, 280, 30, 250  # 记分条位置
    stack[:, y0:y1, x0:x1] = 30.0  # 深色底板
    # 模拟文字/高亮条闪烁：每帧随机挑一小块翻亮，但翻亮的从来不超过整块的
    # 三分之一——真实记分条上文字占比远小于底板
    for i in range(n):
        fy0 = rng.integers(y0, y1 - 10)
        fx0 = rng.integers(x0, x1 - 20)
        stack[i, fy0:fy0 + 8, fx0:fx0 + 15] = 220.0

    cands = dsb.candidates_from_stack(stack)
    assert cands, "实心矩形一个候选都没找到"
    best = cands[0]
    bx0, by0, bx1, by1 = best["box"]
    # 允许几像素的边界误差（真实源片上也有类似的、不影响下游判据的偏差）
    assert abs(bx0 - x0) <= 5 and abs(by0 - y0) <= 5
    assert abs(bx1 - x1) <= 15 and abs(by1 - y1) <= 15
    assert best["fill"] >= dsb.MIN_FILL


def test_散布的暗色区域填充率不够要被滤掉():
    """阴影/树荫/看台深色衣服：闭运算粘连之后面积可能很大，但是散的。

    棋盘格模拟：8-连通下对角线相邻的暗格会连成**一个**连通域（贴近现实里
    树叶缝隙、看台深色衣服这类斑驳暗区被闭运算粘连成一坨的样子），但填充率
    只有 0.5——这正是「面积大不代表是记分条」要拦的那类假阳性（第一版按面积
    排序时，真记分条 area=22491/fill=0.93 排在一整片看台阴影 area=158390/
    fill=0.41 后面，如果只看面积会选错）。
    """
    n, h, w = 20, 200, 200
    stack = np.full((n, h, w), 200.0, dtype=np.float32)
    cell = 10
    for gy in range(0, h, cell):
        for gx in range(0, w, cell):
            if ((gy // cell) + (gx // cell)) % 2 == 0:
                stack[:, gy:gy + cell, gx:gx + cell] = 30.0

    cands = dsb.candidates_from_stack(stack, close_kernel=1)  # 不闭运算，看纯棋盘格填充率
    assert not cands, f"棋盘格（fill≈0.5）不该通过 MIN_FILL={dsb.MIN_FILL} 那道闸：{cands}"


def test_全亮画面没有候选():
    """没有任何持续暗区——记分条被换成透明水印，或者这段源片压根没露出来。

    空结果要能自证：`main()` 走到这条路会打印「没有找到」并给出门槛，
    见 CLI 那条测试；这里只验算法本身确实返回空列表，不是漏了什么判据。
    """
    stack = np.full((10, 100, 100), 210.0, dtype=np.float32)
    assert dsb.candidates_from_stack(stack) == []


def test_填充率才是排序判据不是面积():
    """反向验证：如果排序改成只看面积，这条会红——面积大的散布区排在前面。"""
    n, h, w = 20, 300, 400
    stack = np.full((n, h, w), 200.0, dtype=np.float32)
    # 一大块棋盘格（面积大、填充率低）
    for gy in range(0, 200, 10):
        for gx in range(0, 300, 10):
            if ((gy // 10) + (gx // 10)) % 2 == 0:
                stack[:, gy:gy + 10, gx:gx + 10] = 30.0
    # 一小块实心矩形（面积远小于棋盘格、填充率高）——70×45=3150，卡在
    # MIN_AREA=2500 之上，否则会被面积门槛挡掉，测不出「填充率排序」这件事
    stack[:, 220:265, 320:390] = 30.0

    cands = dsb.candidates_from_stack(stack, min_fill=0.0, close_kernel=1)
    assert len(cands) >= 2, f"两块都该进候选列表（min_fill=0 不筛）：{cands}"
    # min_fill=0.0 时两个都进候选列表，而且棋盘格面积更大、排第一
    assert cands[0]["box"] == (0, 0, 300, 200), "面积大的棋盘格应该排第一"
    # 真正生产用的门槛（MIN_FILL=0.70）应该只留下那块实心矩形
    real = dsb.candidates_from_stack(stack)
    assert len(real) == 1, f"生产门槛下应该只剩实心矩形一个候选，实际 {real}"
    assert real[0]["box"] == (320, 220, 390, 265)


def test_端到端跑一遍真视频(tmp_path: Path):
    """`sample_gray_frames()` 到 `candidates_from_stack()` 这条链子真的接得上。

    造一段 6 秒纯色片子，左下角烧一块固定深色矩形（模拟记分条），
    右上角烧一块每 2 秒闪一次的小方块（模拟别处偶发的暗色噪声，填充率虽高
    但面积太小，会被 `MIN_AREA` 挡掉）。
    """
    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了"
    video = tmp_path / "score.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "color=c=0x88aa66:s=640x360:r=25:d=6",
         "-vf", "drawbox=x=20:y=280:w=200:h=60:color=black:t=fill,"
                "drawbox=x=580:y=10:w=20:h=20:color=black:t=fill:"
                "enable='lt(mod(t,4),2)'",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         str(video)], check=True)

    cands = dsb.detect(video)
    assert cands, "真视频一个候选都没找到"
    best = cands[0]
    x0, y0, x1, y1 = best["box"]
    assert abs(x0 - 20) <= 6 and abs(y0 - 280) <= 6
    assert abs(x1 - 220) <= 10 and abs(y1 - 340) <= 10
    # 右上角那个小方块面积不够（20x20=400 < MIN_AREA=2500），不该进候选
    assert not any(c["box"][0] > 550 for c in cands), (
        f"小方块不该被当成候选：{cands}")


def test_没给视频要报错(tmp_path: Path):
    old = sys.argv
    sys.argv = ["detect_scorebox.py", "--video", str(tmp_path / "nope.mp4")]
    try:
        with pytest.raises(SystemExit, match="不存在"):
            dsb.main()
    finally:
        sys.argv = old
