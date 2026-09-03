"""三档音床（review 路线 ⑤，3.2 C-8）：每段可写 `bed: low|high`，乘在这一段自己的
音轨上再进全局闪避——闪避阈值一个字不动。纪录片的情绪几乎全在赛点落地、全场
起立那几秒的现场声里，而它们原来只有「原样」和「压到地板（mute）」两档。"""
from __future__ import annotations

import inspect
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel  # noqa: E402


def _mean_db(path):
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect",
         "-f", "null", os.devnull], capture_output=True, text=True).stderr
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", out)
    assert m, f"量不出响度：{out[-300:]}"
    return float(m.group(1))


def test_bed字段解析_只认low_high_和mute互斥():
    assert reel._seg_bed({}, 0) == "" and reel._seg_bed({"bed": "mid"}, 0) == ""
    assert reel._seg_bed({"bed": "low"}, 0) == "low"
    assert reel._seg_bed({"bed": "high"}, 0) == "high"
    with pytest.raises(reel.ReelError, match="bed"):
        reel._seg_bed({"bed": "loud"}, 0)
    with pytest.raises(reel.ReelError, match="二选一"):
        reel._seg_bed({"bed": "high", "mute": True}, 0)
    segs = reel.parse_segments({"segments": [
        {"start": 0, "end": 3, "narration": "x", "bed": "high"},
        {"start": 3, "end": 6, "narration": "y"}]}, {"": 1}, "")
    assert segs[0].bed == "high" and segs[1].bed == ""
    assert "bed" in reel._REAL_FIELDS["segment"], "白名单不认它的话 _reject_underscored_fields 对 `_bed` 是哑的"


def test_音床真的乘进这一段的音轨_low压下去high顶上来(tmp_path):
    """真切三段量响度：对照组要响（先证明量的东西存在）；low 比对照低 4~8 dB
    （0.5 倍 ≈ −6 dB）；high 比对照高 1.5~4 dB（1.35 倍 ≈ +2.6 dB）。
    反向验证过：把 `_seg_audio_needs_filter` 里的 `bool(seg.bed)` 拆掉，
    滤镜链算好了却被 `-map 0:a:0` 绕过去，三段一样响——正是那条单一出处要防的。"""
    def _ff(*args):
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        *args], check=True)

    src = tmp_path / "source.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=25:duration=5",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
        "-c:a", "aac", "-shortest", str(src))
    outs = {}
    for name, bed in (("mid", ""), ("low", "low"), ("high", "high")):
        seg = reel.Segment(0.5, 2.5, 0.5, "", track=False, bed=bed)
        outs[name] = tmp_path / f"{name}.mp4"
        reel.cut_segment(src, seg, outs[name], 1920)
    db = {k: _mean_db(v) for k, v in outs.items()}
    assert db["mid"] > -40, f"对照组只有 {db['mid']} dB——源声根本没进来"
    assert 4 <= db["mid"] - db["low"] <= 8, db
    assert 1.5 <= db["high"] - db["mid"] <= 4, db


def test_音轨要不要走滤镜只有一处出处():
    """cut_segment 里两处 `-map` 判据都要读同一个函数——原来写成
    `seg.speed != 1 or seg.mute` 两遍，加一档漏改一处的样子是滤镜链算好了、
    map 把它绕过去，不报错。"""
    body = inspect.getsource(reel.cut_segment)
    assert body.count("_seg_audio_needs_filter(seg)") == 2
    assert "seg.speed != 1 or seg.mute" not in body
    assert reel._seg_audio_chain(reel.Segment(0, 1, 0.5, "", bed="low")) == \
        f"volume={reel.BED_TIERS['low']}"
    assert reel._seg_audio_chain(reel.Segment(0, 1, 0.5, "", speed=0.5, bed="high")) == \
        f"atempo=0.5,volume={reel.BED_TIERS['high']}"
