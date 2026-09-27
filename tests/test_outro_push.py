"""片尾推镜的亚像素平滑（UI/VI 评审 WP7，2026-09-27）。

`zoompan` 的裁切框只认整数像素（x / y / 宽 / 高全是截断取整的 int），而 1.03 倍
的推镜一帧只走零点零几个像素——老母版量出来黄绿图标水平来回抖 **1.9px**、纵向
59 步里 **9 步往回跳**（按 >0.02px 数，最大一跳 0.70px；按 >0.001px 数是 18 步，
但那一档连新母版也有 8 步——≤0.009px 的 x264 编码噪声，数它没有意义）。
修法：先放大 4 倍再推、再缩回，裁切框按 3:4 成对地缩、框心钉在正中
（`outro_page.push_filter`）。

三条判据，前两条钉**滤镜代码**，第三条钉**提交进仓库的那份母版**：

- 真跑一遍生产用的滤镜图、逐帧量一个圆盘的亚像素质心：圆盘水平居中 → 推镜绕画布
  中心放大，横坐标**一动不动**；圆盘在中心上方 → 越推越往上走，纵坐标**只许单调**。
  输出直接走 rawvideo，不过 x264：编码噪声会把「单调」量糊，而这条要量的是滤镜本身。
  拿纯色块当层，不渲真页面——CI 上没有 Chromium 也没有品牌字体
- 结构：4 倍网格、对称步长、整数倍缩回
- **母版本身**（`outro_page.MASTER`）：滤镜改对了不等于母版按它重出过——中途被打断的
  那一趟就把一份 0.27px 的废版留在了原地，而前两条对它一律是绿的；「zoompan 直接
  缩出成片」那一版也只在**编码后**的母版上看得出来。查产物，不查信号
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

np = pytest.importorskip("numpy")

#: 和真片尾的台标同一个位置：水平居中、中心在 y≈557（图标 200px，量自母版）
_DISC = (540, 557, 90)


def _layers(tmp_path: Path, W: int, H: int) -> list[Path]:
    """底层：墨绿底 ＋ 一个亮圆盘（水平居中、在画布中心上方）＋ 两根**不对称**的
    深色表针（照着台标那只钟画的）；三层：全透明。

    ⚠️ 表针不是装饰：一个左右对称的圆盘，**清晰度随推镜一跳一跳**时质心照样纹丝
    不动（对称的模糊不挪质心），于是「边缘在呼吸」那种抖动它量不出来——
    `lanczos` 放大后让 `zoompan` 直接缩出成片尺寸那一版就是这么混过对称圆盘的：
    圆盘上漂 0.014px，真台标上 0.24px 一跳一跳。不对称的内容才量得出来。
    """
    from PIL import Image, ImageDraw  # noqa: PLC0415

    cx, cy, r = _DISC
    base = tmp_path / "base.png"
    im = Image.new("RGB", (W, H), (4, 18, 13))
    d = ImageDraw.Draw(im)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(198, 246, 90))
    d.line((cx, cy, cx + 38, cy - 52), fill=(4, 18, 13), width=12)   # 时针：一点钟方向
    d.line((cx, cy, cx - 62, cy + 6), fill=(4, 18, 13), width=9)     # 分针：九点钟方向
    im.save(base)
    clear = tmp_path / "clear.png"
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(clear)
    return [base, clear, clear, clear]


def _centroids(frames, box: tuple[int, int, int, int]):
    """逐帧的黄绿质心 (x, y)。`box` = (y0, y1, x0, x1)。"""
    y0, y1, x0, x1 = box
    ys, xs = np.mgrid[y0:y1, x0:x1]
    out = []
    for fr in frames:
        # 权重**故意是非线性的**（按「黄绿」认像素、上下都截断）：线性的亮度质心对
        # 对称模糊是不变的，边缘「一跳一跳地变虚变实」它量不出来，而眼睛看得出来
        a = fr[y0:y1, x0:x1].astype(np.float64)
        g, b = a[..., 1], a[..., 2]
        wt = np.clip((g - b - 40) / 110, 0, 1) * np.clip((g - 30) / 200, 0, 1)
        out.append(((wt * xs).sum() / wt.sum(), (wt * ys).sum() / wt.sum()))
    return np.array(out)


def _track(graph: str, layers: list[Path], secs: float, fps: int, W: int, H: int):
    args = ["ffmpeg", "-v", "error"]
    for f in layers:
        args += ["-framerate", str(fps), "-loop", "1", "-t", f"{secs:.3f}", "-i", str(f)]
    args += ["-filter_complex", graph, "-map", "[vout]", "-t", f"{secs:.3f}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(args, check=True, capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    cx, cy, r = _DISC
    return _centroids(frames, (cy - r - 30, cy + r + 30, cx - r - 30, cx + r + 30))


def test_片尾推镜亚像素平滑_台标横向不漂_纵向单调(tmp_path):
    from tennislive.video import outro_page  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    W, H = outro_page.VIDEO_W, outro_page.VIDEO_H
    # 推镜在 `frames` 帧里走完 1→1.03；帧少一点、步子就大一点，判据只会更严
    secs, fps = 1.2, 30
    layers = _layers(tmp_path, W, H)
    track = _track(outro_page.motion_filter(secs, str(fps), float(fps)),
                   layers, secs, fps, W, H)
    assert len(track) >= 30, f"只出了 {len(track)} 帧"
    xs, ys = track[:, 0], track[:, 1]

    # 验收线是成片母版上「≤0.25px」；这儿量的是**滤镜本身**（rawvideo，没有编码噪声），
    # 所以收紧到 0.1。这张合成台标上量过（2026-09-27）：老滤镜 1.08px、只放大 4 倍
    # 0.34px，四种「4 倍 ＋ 对称裁切」的放大/缩回组合 0.04~0.07px——0.1 正好把它们分开。
    drift = xs.max() - xs.min()
    assert drift <= 0.1, (
        f"台标水平漂了 {drift:.3f}px（逐帧 {np.round(xs, 3).tolist()}）——推镜绕画布中心"
        "放大，水平居中的东西横坐标不该动。老滤镜（整数裁切框）这里是 1~2px 的来回抖")
    dy = np.diff(ys)
    assert (dy <= 1e-6).all(), (
        f"台标纵向不单调：{int((dy > 1e-6).sum())} 次往回跳（最大 {dy.max():.3f}px）——"
        "推镜只会把中心上方的东西一路往上送，往回跳就是裁切框的整数截断在抖")
    rise = ys[0] - ys[-1]
    want = (H / 2 - _DISC[1]) * (outro_page.PUSH - 1)
    assert rise > 0.6 * want, (
        f"整段只往上走了 {rise:.2f}px，推满 {outro_page.PUSH} 倍应该约 {want:.2f}px——推镜没在动")


def test_推镜的超采样和对称裁切写进了滤镜():
    """结构上的三件事，缺一件上面那条就会红，这儿先把「红在哪」说清楚。"""
    from tennislive.video import outro_page  # noqa: PLC0415

    W, H, k = outro_page.VIDEO_W, outro_page.VIDEO_H, outro_page.SUPERSAMPLE
    assert k >= 4, f"超采样只有 {k} 倍——整数步长就是 1/{k}px，量出来的漂移压不到 0.25 以下"
    graph = outro_page.push_filter(100, "30")
    assert f"scale={W * k}:{H * k}:" in graph, "推之前没放大到超采样网格"
    assert f"z='{W * k}/(" in graph, "裁切框不是在超采样网格上按整数步缩的"
    # 缩回必须是**整数倍**：让 zoompan 直接缩出成片尺寸，缩小倍数跟着 m 变、滤波核
    # 相位一步一个样，编进母版后台标横向一跳 0.24px（rawvideo 上量不出来）
    assert f"s={W * k}x{H * k}:fps=30," in graph, "zoompan 没按超采样尺寸出，缩回就不是整数倍"
    assert graph.endswith(f"scale={W}:{H}:flags=lanczos"), "推完没整数倍缩回成片画幅"
    # 对称：x、y 的步长就是画幅比 3:4，框心才恒在正中
    assert "x='3*round(" in graph and "y='4*round(" in graph, graph


def test_提交进仓库的母版_台标横向不漂_纵向不往回():
    """**量母版本身**，不是量滤镜代码（查产物，不查信号）。

    从 t=2.2s 起解 60 帧（三层都已淡完、只剩推镜在动），逐帧量真台标的黄绿质心。
    三份真母版上量过（2026-09-27，同一个量法）：

    ====================================  ==========  ========================
    母版                                   横向漂移    纵向往回跳（>0.02px）
    ====================================  ==========  ========================
    老母版（整数裁切框）                    1.885px     9 次，最大 0.70px
    中途烘出的废版（zoompan 直接缩出成片）   0.270px     0 次
    现在这份（4 倍网格 ＋ 整数倍缩回）       0.029px     0 次（最大回跳 0.009px）
    ====================================  ==========  ========================

    0.25 是验收线，正好把中间那份废版挡在外面——它在前两条判据上是绿的。
    往回跳按 >0.02px 数：新母版有 ≤0.009px 的 x264 编码噪声，数到 0.001 会把它也算进去。
    解 60 帧 1080×1440，一秒上下。
    """
    from tennislive.video import outro_page  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    master = outro_page.MASTER
    assert master.is_file(), f"母版不在：{master}"
    W, H = outro_page.VIDEO_W, outro_page.VIDEO_H

    def probe(entry: str) -> str:
        return subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
             "-show_entries", f"stream={entry}", "-of", "default=nw=1:nk=1", str(master)],
            check=True, capture_output=True, text=True).stdout.strip()

    # 窗口按 60fps 定（2.2s 起 60 帧 ＝ 1 秒）；母版不是 60fps 的话这条量的就不是那 60 帧
    assert probe("r_frame_rate") == "60/1", f"母版帧率 {probe('r_frame_rate')}，不是 60"
    total = int(probe("nb_read_packets"))

    n = 60
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "2.2", "-i", str(master), "-frames:v", str(n),
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    assert len(frames) == n, f"只解出 {len(frames)} 帧"
    # 台标 200px 见方、水平居中、中心在 y≈557：框子四周各留 40px
    track = _centroids(frames, (420, 700, 400, 680))
    xs, ys = track[:, 0], track[:, 1]

    drift = xs.max() - xs.min()
    assert drift <= 0.25, (
        f"母版上台标水平漂了 {drift:.3f}px（验收线 0.25）——滤镜代码可能是对的，但提交进"
        "仓库的这份母版不是按它重出的（或者重出时走了「直接缩出成片」那条近路）。"
        "重出：PYTHONPATH=src python3 tools/build_outro_master.py --keep-voice")
    dy = np.diff(ys)
    back = dy > 0.02
    assert not back.any(), (
        f"母版上台标纵向往回跳了 {int(back.sum())} 次（最大 {dy.max():.3f}px）——"
        "推镜只会把中心上方的东西一路往上送，往回跳是裁切框的整数截断在抖")
    rise = ys[0] - ys[-1]
    want = (H / 2 - ys[0]) * (outro_page.PUSH - 1) * (n - 1) / (total - 1)
    assert rise > 0.6 * want, (
        f"这一秒台标只往上走了 {rise:.2f}px，推满 {outro_page.PUSH} 倍应该约 {want:.2f}px"
        "——母版里的推镜没在动")
