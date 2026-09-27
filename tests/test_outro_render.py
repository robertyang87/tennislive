"""真跑片尾滤镜图的几条判据——单独一个文件，是为了 CI 的 `--dist loadfile`。

这几条原来分住在 `test_match_reel.py`（两条）和 `test_interview_clip.py`（一条）。
2026-09-27 片尾推镜改成 4 倍超采样（`outro_page.push_filter`，UI/VI 评审 WP7）之后，
每条真跑一遍滤镜图的测试 CPU 涨到约 5.4 倍（评审实测：灰层、ultrafast 编码，30fps
3.85s 那条 7.8s → 41.9s）。CI 按 `pytest -n auto --dist loadfile` 分工，**同一个文件
整个落在同一个 worker 上**——而 `test_match_reel.py` 本来就是最长的那个文件，
再往它身上压 70 秒 CPU 就是直接加在关键路径上。挪到这儿，`loadfile` 才能把它们
分给别的 worker。

⚠️ **别挪回去**，也别把新的「真跑片尾滤镜」测试写进那两个大文件——写这儿。
判据本身一个字没改，只是换了文件。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_片尾的动效每一层都要按时出现(tmp_path):
    """账号所有者 2026-08-05：「最后最好有一个动效出来这一屏」。

    **真跑一遍生产用的那个滤镜图**，量每一层在自己该出现的时刻之前是不是还没
    出现、之后是不是出来了。查源码里有没有 `fade=` 只能防「有人把它删了」，
    防不住「它从来没工作过」——这个仓库里「签名对了、实现是空的」是常客。

    ⚠️ 拿**纯色块**当层，不渲真页面：这条判据要在 CI 上跑得起来，而 CI 上
    没有 Chromium 也没有品牌字体。它验的是滤镜图的时序，不是版式好不好看。

    ⚠️ **必须按 30fps 跑，不能用 25。** 静图输入不给 `-framerate` 时 ffmpeg
    按 25fps 解 `-loop 1`，而 `zoompan` 输出标的是目标帧率——帧数不够，画面
    就缩成 `total × 25/fps`。**fps 恰好是 25 时两者相等，这个 bug 完全看不见**：
    第一版就是拿 25 跑的，绿得很干净，而真跑一次解说片（30fps）当场量到
    画面 3.57s、音轨 4.29s。判据的参数选在「恰好掩盖缺陷」的那一档上，
    和没有判据是一回事。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    from tennislive.video import outro_page  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    secs, fps = 3.85, 30
    # 底层纯黑，三层各是一条横带，落在互不重叠的高度上——这样量某一条带的
    # 亮度就等于量那一层出没出来。
    base = tmp_path / "base.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=black:s={outro_page.VIDEO_W}x{outro_page.VIDEO_H}",
                    "-frames:v", "1", str(base)], check=True)
    bands = {}
    layer_files = []
    for i, (key, st, dur, _rise) in enumerate(outro_page.LAYERS):
        y0 = 200 + i * 300
        bands[key] = (y0, y0 + 160, st, dur)
        f = tmp_path / f"l{i}.png"
        # 透明底 + 一条白带
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             f"color=c=black@0.0:s={outro_page.VIDEO_W}x{outro_page.VIDEO_H}",
             "-vf", f"drawbox=x=0:y={y0}:w={outro_page.VIDEO_W}:h=160:"
                    "c=white@1.0:t=fill",
             "-frames:v", "1", "-pix_fmt", "rgba", str(f)], check=True)
        layer_files.append(f)

    film = tmp_path / "outro.mp4"
    args = ["ffmpeg", "-v", "error", "-y",
            "-framerate", str(fps), "-loop", "1", "-t", f"{secs}", "-i", str(base)]
    for f in layer_files:
        args += ["-framerate", str(fps), "-loop", "1", "-t", f"{secs}", "-i", str(f)]
    args += ["-filter_complex", outro_page.motion_filter(secs, str(fps), float(fps)),
             "-map", "[vout]", "-c:v", "libx264", "-preset", "ultrafast",
             "-crf", "12", "-pix_fmt", "yuv420p", str(film)]
    subprocess.run(args, check=True)

    # ① **画面必须真有那么长。** 少给 `-framerate` 时它会缩成 total×25/fps，
    # 而 ffmpeg 不报错——真跑解说片时量到画面 3.57s、音轨 4.29s 就是这个。
    got = float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(film)],
        check=True, capture_output=True, text=True).stdout.strip().rstrip(","))
    assert abs(got - secs) < 0.12, (
        f"片尾画面 {got:.2f}s，要的是 {secs:.2f}s——"
        f"差 {secs / got if got else 0:.3f} 倍。静图输入少了 `-framerate`，"
        "帧数按 25fps 铺、时长按目标帧率标，画面就比音轨短一截")

    def band_brightness(moment: float, y0: int, y1: int) -> float:
        shot = tmp_path / "s.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{moment:.3f}",
                        "-i", str(film), "-frames:v", "1", str(shot)], check=True)
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(shot), "-vf",
             f"crop={outro_page.VIDEO_W}:{y1 - y0}:0:{y0},"
             "format=gray,signalstats,metadata=print:key=lavfi.signalstats.YAVG",
             "-f", "null", "-"], capture_output=True, text=True).stderr
        got = re.search(r"YAVG=(\S+)", out)
        assert got, f"量不到 {moment}s 的亮度"
        return float(got.group(1))

    for key, (y0, y1, st, dur) in bands.items():
        # 入场之前：还没出来（留 0.06s 余量给取帧的量化误差）
        before = band_brightness(max(0.0, st - 0.10), y0, y1)
        # 淡完之后：出来了
        after = band_brightness(min(secs - 0.05, st + dur + 0.25), y0, y1)
        assert before < 12, (
            f"「{key}」层在 {st}s 之前就已经出现了（亮度 {before:.1f}）——"
            "淡入没生效，那一层从第 0 帧就是满的")
        assert after > 90, (
            f"「{key}」层淡完之后还没出来（亮度 {after:.1f}）——"
            "这一层根本没被合进去，或者 fade 把 alpha 弄反了")
        assert after - before > 60, (
            f"「{key}」层前后差得太小（{before:.1f} → {after:.1f}），淡入没在动")


def test_片尾片段的画面要和它自己要的一样长(tmp_path):
    """**真调一次 `render_clip`**，量它出来的画面有多长。

    ⚠️ 这条是补上一条判据的漏洞的。`test_片尾的动效每一层都要按时出现` 验的是
    `motion_filter`（滤镜图），而真出问题的地方在 `render_clip` 拼的那串
    **ffmpeg 参数**里——静图输入少了 `-framerate`，ffmpeg 就按 25fps 铺
    `-loop 1`，而 `zoompan` 输出标的是目标帧率，画面于是缩成 `total×25/fps`。

    实测（解说片，30fps，目标 4.29s）：**画面 3.57s，音轨 4.29s。**
    ffmpeg 不报错，成片能出来，只是最后 0.72 秒没有画面。

    而那条老判据**抓不到它**：测试自己拼命令行、自己带了 `-framerate`，
    把生产代码里的两处全拿掉照样绿。查的东西和跑的东西不是一回事。

    喂现成的 PNG 当层（`layers=`），所以这条不碰 Chromium，CI 上跑得起来。

    ⚠️ **必须按 30fps 跑**：fps 恰好是 25 时 `total×25/fps == total`，
    这个 bug 完全看不见。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from tennislive.video import outro_page  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    layers = {}
    for name in ["base"] + [k for k, *_ in outro_page.LAYERS]:
        f = tmp_path / f"{name}.png"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             f"color=c=gray:s={outro_page.VIDEO_W}x{outro_page.VIDEO_H}",
             "-frames:v", "1", "-pix_fmt", "rgba", str(f)], check=True)
        layers[name] = f

    want, fps = 4.29, 30
    dest = outro_page.render_clip(
        tmp_path, want,
        fps_expr=str(fps), fps=float(fps), chromium="", dest=tmp_path / "o.mp4",
        audio_rate="24000", preset="ultrafast", crf="26",
        audio_bitrate="64k", layers=layers,
    )
    got = float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(dest)],
        check=True, capture_output=True, text=True).stdout.strip().rstrip(","))
    assert abs(got - want) < 0.12, (
        f"片尾画面 {got:.2f}s，要的是 {want:.2f}s（差 {want / got if got else 0:.3f} "
        f"倍，25/{fps} = {25 / fps:.3f}）——静图输入少了 `-framerate`，"
        "帧数按 25fps 铺、时长按目标帧率标，画面就比音轨短一截，而 ffmpeg 不报错")


def test_采访片的片尾要和正片拼得起来(tmp_path):
    """**真跑一次 `-c copy` 的 concat。**

    这条线走 `concat` demuxer + `-c copy`，是三条线里对流参数最挑的一条：
    帧率、采样率、**声道数**差一项就静默丢流，成片从某一秒起没声音，
    **而 ffmpeg 不报错**（封面那一路的注释里已经为同一件事记过一次）。

    喂现成的 PNG 当层（`layers=`），所以不碰 Chromium 也不合语音，CI 上跑得起来。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from tennislive.video import outro_page  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    layers = {}
    for name in ["base"] + [k for k, *_ in outro_page.LAYERS]:
        f = tmp_path / f"{name}.png"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             f"color=c=gray:s={outro_page.VIDEO_W}x{outro_page.VIDEO_H}",
             "-frames:v", "1", "-pix_fmt", "rgba", str(f)], check=True)
        layers[name] = f

    # 片尾：参数照 `_build_outro` 传的那一组
    outro = outro_page.render_clip(
        tmp_path, 4.0, fps_expr="25", fps=25.0, chromium="",
        dest=tmp_path / "_outro.mp4", audio_rate="48000", preset="medium",
        crf="20", audio_bitrate="128k", audio_channels=2, layers=layers)

    # 「正片」：参数照 `render()` 里那一组
    body = tmp_path / "body.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "color=c=navy:s=1080x1440:r=25",
         "-f", "lavfi", "-i", "sine=frequency=200:sample_rate=48000",
         "-t", "6", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-r", "25", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-ar", "48000", "-ac", "2", str(body)], check=True)

    lst = tmp_path / "cc.txt"
    lst.write_text(f"file '{body.name}'\nfile '{outro.name}'\n", encoding="utf-8")
    joined = tmp_path / "joined.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(joined)], check=True)

    def _dur(stream):
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", stream,
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(joined)],
            check=True, capture_output=True,
            text=True).stdout.strip().rstrip(","))

    assert abs(_dur("v:0") - 10.0) < 0.3, (
        f"拼出来只有 {_dur('v:0'):.2f}s，要的是 6+4=10s——片尾的流参数和正片对不上")
    # **音轨也要在**：`-c copy` 参数不匹配时会丢掉其中一条流，而它不报错
    assert abs(_dur("a:0") - _dur("v:0")) < 0.4, (
        f"音轨 {_dur('a:0'):.2f}s vs 画面 {_dur('v:0'):.2f}s——concat 丢了一条流")
