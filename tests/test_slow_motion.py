"""慢放（`seg.speed`）：赛点/冲击瞬间的标配剪辑手段，长度账一处都不能歪。

来路：账号所有者点名「不仅仅是内容还有剪辑手段和画面设计等等」，此前也说过
「主要参考文案和叙事方式，以及画面剪辑和速度快慢放等等」。头部账号的赛点
几乎都上慢放，而这条管线此前只有 1:1 一档。

设计定死三件事，测试分别钉住：

- `start`/`end` 仍是**源片窗口**（挑段、切点、死球那套判据一个字不变），
  `length` 是**成片时长** `(end-start)/speed`——旁白预算、字幕偏移、
  溶解长度账全走它，一个口径
- 现场声跟着 atempo 放慢（保音高）。**裸 map 的原声不会报错，只会画面慢了
  声音没慢**——只有按时间片量响度才看得出来，所以判据必须真渲一段
- 变速两头（0.4 ≤ speed ≤ 2.5）：**快放 2026-08-27 才放开**，在那之前挡着它的
  不是滤镜是账——溶解底料的**源片**消耗是 `SEG_FADE×speed`，慢放时比 `SEG_FADE`
  短（检查偏保守，无害），快放时比它长（ghost 检查会漏报跨切点）。现在两处
  检查都走 `source_tail(speed)`，快放才敢开
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import check_reel_landed  # noqa: E402
from build_match_reel import (  # noqa: E402
    FPS,
    SEG_FADE,
    SPEED_MAX,
    SPEED_MIN,
    ReelError,
    Segment,
    cut_segment,
    parse_segments,
    sample_track,
    seg_seconds,
    segments_over_source_end,
    segments_straddling_cuts,
    source_tail,
)


def test_length是成片时长而且三处口径一致():
    """`Segment.length`、`seg_seconds`、`check_reel_landed` 抄的那份，
    三处必须是同一笔账——最后那份是故意抄的（保持零依赖），抄的东西
    会分叉，所以钉在这儿。"""
    slow = Segment(2.0, 6.0, 0.5, "", speed=0.5)
    assert slow.length == 8.0, "0.5 倍速的 4 秒窗口在成片里占 8 秒"
    plain = Segment(2.0, 6.0, 0.5, "")
    assert plain.length == 4.0

    spec = {"segments": [{"start": 2.0, "end": 6.0, "speed": 0.5},
                         {"start": 10.0, "end": 13.0}]}
    total = sum(seg_seconds(s) for s in spec["segments"])
    assert total == 11.0
    assert check_reel_landed.spec_segments_seconds(spec) == pytest.approx(total)


def test_速度闸慢放快放都认两头都拦():
    def parse_one(**extra):
        spec = {"segments": [{"start": 0.0, "end": 2.0, **extra}]}
        return parse_segments(spec, {"": Path("x.mp4")}, "")

    assert parse_one()[0].speed == 1.0
    assert parse_one(speed=0.5)[0].speed == 0.5
    # **快放 2026-08-27 放开**（账号所有者「还有快慢播放的结合」）。
    assert parse_one(speed=1.5)[0].speed == 1.5
    assert parse_one(speed=SPEED_MAX)[0].speed == SPEED_MAX
    assert parse_one(speed=SPEED_MIN)[0].speed == SPEED_MIN
    # 两头照旧要拦——放开不等于没有闸。
    with pytest.raises(ReelError, match="2.5"):
        parse_one(speed=SPEED_MAX + 0.1)
    with pytest.raises(ReelError, match="0.4"):
        parse_one(speed=SPEED_MIN - 0.1)
    with pytest.raises(ReelError, match="不是数字"):
        parse_one(speed="一半")


def test_源片侧的溶解底料就是SEG_FADE乘速度():
    """`source_tail()` 的单元账。行为那两条在下一个测试里，分开是**故意的**：
    合在一起时这三行会先红，把行为断言挡住。"""
    assert source_tail(1.0) == SEG_FADE
    assert source_tail(0.5) == pytest.approx(SEG_FADE * 0.5)
    assert source_tail(2.0) == pytest.approx(SEG_FADE * 2.0)


def test_溶解底料的源片消耗要按速度算否则快放会漏报():
    """这是**放开快放的前提**，不是附带的一条。

    `cut_segment` 的 `-t` 给的是**输出**时长（`length + tail`），而
    `setpts=PTS/speed` 排在它前面——所以真实的源片消耗是
    `(end-start) + SEG_FADE×speed`。两处检查（越界闸、ghost 检查）原来按
    常数 `SEG_FADE` 算：慢放时偏保守（无害），**快放时偏小，于是漏报**。

    两个方向都钉：快放要报出来，慢放不许被误伤。
    """
    # ⚠️ `source_tail()` 本身的单元断言**故意不放在这条里**——放前面的话它会先红，
    # 把底下两条行为断言挡住，我就证明不了「行为那两条真的咬得住」。
    # 见 `test_源片侧的溶解底料就是SEG_FADE乘速度`。

    # ── ① 越界闸：源片刚好够 1 倍速，快放就不够了 ──────────────────
    dur = {"": 10.0 + SEG_FADE}          # 正好够 1 倍速那一段的底料
    plain = Segment(6.0, 10.0, 0.5, "")
    fast = Segment(6.0, 10.0, 0.5, "", speed=2.0)
    assert not segments_over_source_end([plain], dur), "1 倍速正好够，不许误报"
    assert segments_over_source_end([fast], dur), (
        "2 倍速要多消耗一倍底料，源片不够了却没报——"
        "这正是快放当年被挡在门外的那笔账")

    # ── ② ghost 检查：切点落在 1 倍速尾巴之外、2 倍速尾巴之内 ──────
    cut_at = 10.0 + SEG_FADE * 1.5       # 1 倍速够不着，2 倍速够得着
    probes = [{"url": "u", "scene_cuts": [cut_at]}]
    def straddle(speed):
        spec = {"sources": {"s": "u"},
                "segments": [{"start": 6.0, "end": 10.0, "source": "s",
                              **({"speed": speed} if speed != 1 else {})},
                             {"start": 20.0, "end": 24.0, "source": "s"}]}
        return segments_straddling_cuts(spec, probes)[2]
    assert not straddle(1.0), "1 倍速的尾巴够不到这个切点，不许误报"
    assert straddle(2.0), "2 倍速的尾巴盖住了这个切点，必须报出来"


def test_跟踪采样按源片窗口不按成片时长():
    """sendcmd 排在 setpts 之前，命令时刻走源片时间——慢放段拿 `length`
    （成片时长）来采会采过窗口末尾，还发一堆永远不会命中的命令。"""
    coarse = [(2.0, 600.0), (6.0, 1000.0)]
    seg = Segment(2.0, 6.0, 0.5, "", track=True, speed=0.5)
    path = sample_track(coarse, seg)
    assert len(path) == int((seg.end - seg.start) * FPS), "采样点数 = 源片窗口×FPS"
    assert max(t for t, _ in path) < seg.end - seg.start, "时刻不许超出源片窗口"


def _volume_max(film: Path, a: float, b: float) -> float:
    """量输出里 [a, b] 这一段的峰值响度（dB）。⚠️ volumedetect 的输出在
    stderr 的 INFO 里，不能 `-v error`（CLAUDE.md 记过：会把它自己吞掉）。"""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(film),
         "-af", f"atrim={a}:{b},volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", proc.stderr)
    assert m, f"volumedetect 没报 max_volume：\n{proc.stderr[-800:]}"
    return float(m.group(1))


def _probe_dur(film: Path, stream: str) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(film)],
        capture_output=True, text=True, check=True).stdout.strip())


def test_慢放段真渲出来时长和音画同步都要对(tmp_path):
    """真跑一遍 `cut_segment`——「写了」不等于「跑过」。

    源片 8 秒，只在 5.5–6.0s 有一声蜂鸣。窗口 [2, 6] 半速：

    - 成片时长 ≈ 8s（窗口 4s ÷ 0.5）
    - 蜂鸣在源片窗口的 3.5–4.0s 处，半速后要落在成片的 **7.0–8.0s**。
      音轨没跟着变速的话它落在 3.5–4.0s——时长照样对（`-t` 卡着），
      **只有按时间片量响度才抓得到**，这正是这条判据存在的理由
    - 带 tail=0.18（溶解底料）时成片 ≈ 8.18s——tail 是输出侧的秒数
    """
    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=25:duration=8",
         "-f", "lavfi", "-i",
         "aevalsrc='if(between(t,5.5,6),0.6*sin(2*PI*880*t),0)':s=44100:d=8",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
         "-c:a", "aac", "-shortest", str(src)],
        check=True, capture_output=True, text=True)

    seg = Segment(2.0, 6.0, 0.5, "", track=False, speed=0.5)
    out = tmp_path / "part.mp4"
    cut_segment(src, seg, out, 1920, tail=0.0)

    v = _probe_dur(out, "v:0")
    a = _probe_dur(out, "a:0")
    assert abs(v - 8.0) < 0.25, f"成片时长 {v:.2f}s，该是 8s 上下"
    assert abs(a - v) < 0.35, f"音轨 {a:.2f}s 和画面 {v:.2f}s 不齐"
    assert _volume_max(out, 0.0, 6.5) < -45, "前 6.5s 该是静的——蜂鸣提前出现" \
        "，多半是音轨没跟着变速（裸 map 的原声还是原速）"
    assert _volume_max(out, 6.8, 8.0) > -25, "7~8s 该有蜂鸣——慢放后它落在这儿"

    with_tail = tmp_path / "part_tail.mp4"
    cut_segment(src, seg, with_tail, 1920, tail=0.18)
    v2 = _probe_dur(with_tail, "v:0")
    assert abs(v2 - 8.18) < 0.25, f"带溶解底料该是 8.18s 上下，量到 {v2:.2f}s"
