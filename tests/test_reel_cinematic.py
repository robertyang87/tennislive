"""电影感出片选项（tools/reel_cinematic.py）：全部 opt-in，不写就和原来一致。

账号所有者 2026-10-17「加一些出片工具」；同日明令：**分一律原速，不许慢放、定格**。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel  # noqa: E402
import reel_cinematic as cine  # noqa: E402
import reel_join_fusion  # noqa: E402
import render_title_card  # noqa: E402

FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="需要 ffmpeg")


# ---------- 形状校验 ----------

def test_没写cinematic就是空_滤镜全空():
    assert cine.config({}) == {}
    assert cine.look_filter({}) == ""
    assert cine.source_match_filter({}, "a") == ""
    assert cine.push_filter(1.0, 3, 1080, 1440) == ""


@pytest.mark.parametrize("bad", [
    {"grade": "sepia"}, {"grain": 2}, {"vignette": -0.1}, {"grade_strength": True},
    {"match": {"x": {"exposure": 1}}}, {"match": {"zz": {}}}, {"stems": "yes"}, {"lut": "a"},
])
def test_写错当场红(bad):
    with pytest.raises(cine.CinematicError):
        cine.config({"sources": {"x": "u"}, "cinematic": bad})


def test_build_match_reel把错转成ReelError():
    with pytest.raises(reel.ReelError):
        reel._cine_call(cine.config, {"cinematic": {"grade": "nope"}})


def test_没有变速入口_分保持原速():
    """不许慢放、定格：cinematic 里不认任何变速键，转场时长也不改段长。"""
    for key in ("speed", "slowmo", "freeze", "ramp"):
        with pytest.raises(cine.CinematicError):
            cine.config({"cinematic": {key: 0.5}})
    # dissolve_filtergraph 换转场不改长度账（offset 一模一样）
    a = reel.dissolve_filtergraph([2.0, 3.0, 1.5], 0.18)
    b = reel.dissolve_filtergraph([2.0, 3.0, 1.5], 0.18, transitions=["dissolve", "flash", "whip"])
    import re
    assert re.findall(r"offset=[0-9.]+", a) == re.findall(r"offset=[0-9.]+", b)


def test_调色预设与强度():
    f = cine.look_filter({"grade": "teal_orange", "grain": 0.5, "vignette": 0.4})
    assert "colorbalance=rs=-0.060" in f and "eq=contrast=1.080" in f
    assert "vignette=angle=" in f and "noise=c0s=7" in f
    half = cine.look_filter({"grade": "teal_orange", "grade_strength": 0.5})
    assert "rs=-0.030" in half and "contrast=1.040" in half
    assert cine.look_filter({"grade": "neutral"}) == ""


def test_逐源拉齐():
    cfg = cine.config({"sources": {"iw": "u"}, "cinematic": {"match": {
        "iw": {"exposure": -0.05, "temperature": 5600, "saturation": 0.9}}}})
    f = cine.source_match_filter(cfg, "iw")
    assert f == "colortemperature=temperature=5600,eq=brightness=-0.050:saturation=0.900,"
    assert cine.source_match_filter(cfg, "other") == ""


def test_转场和推镜的段落校验():
    assert cine.seg_transition({}, 0) == "dissolve"
    assert cine.seg_transition({"transition_in": "flash"}, 0) == "flash"
    with pytest.raises(cine.CinematicError):
        cine.seg_transition({"transition_in": "spin"}, 0)
    assert cine.seg_push({"push_in": 1.1}, 0) == 1.1
    for bad in ({"push_in": 1.5}, {"push_in": 1.1, "title_card": "x"}, {"push_in": 1.1, "score_inset": True}):
        with pytest.raises(cine.CinematicError):
            cine.seg_push(bad, 0)


def test_parse_segments认新键():
    spec = {"sources": {"r1": "u"}, "segments": [
        {"source": "r1", "start": 0, "end": 3, "transition_in": "whip", "push_in": 1.08}]}
    seg = reel.parse_segments(spec, {"r1": Path("a.mp4")}, "r1")[0]
    assert seg.transition_in == "whip" and seg.push == 1.08


# ---------- 拼接图 ----------

def test_融合拼接认得新转场():
    graph = reel.dissolve_filtergraph([2.0, 3.0, 1.5, 2.0], 0.18,
                                      transitions=["dissolve", "cut", "flash", "whip"])
    plan, why = reel_join_fusion.plan(graph, 4)
    assert plan is not None, why
    assert "transition=fadewhite" in graph and "transition=hblur" in graph
    assert "transition=custom:expr=" in graph


# ---------- 画面占比 ----------

def test_预告片卡和章节卡不算比赛画面():
    spec = {"_unofficial": {"fan": "粉丝搬运"}, "segments": [
        {"title_card": "第七次", "title_style": "trailer", "seconds": 2},
        {"source": "a", "start": 0, "end": 6},
        {"source": "fan", "start": 0, "end": 2},
    ]}
    r = cine.footage_ratio(spec)
    assert r == {"total": 10.0, "footage": 8.0, "official": 6.0,
                 "footage_pct": 80.0, "official_pct": 60.0}


def test_预告片卡_只放一句话不放数据():
    html = render_title_card.build("第七次 你押谁？", kicker="武汉", style="trailer")
    assert 'class="lb"' in html and "第七次" in html
    with pytest.raises(SystemExit):
        render_title_card.build("x", style="poster")


def test_title_style写错dry_run就红():
    spec = {"segments": [{"title_card": "第七次", "seconds": 2, "title_style": "poster"}]}
    with pytest.raises(reel.ReelError):
        reel._normalize_title_card_segments(spec)


# ---------- 锐化白名单 ----------

def test_锐化只给放大的低清授权源():
    url = next(iter(reel.APPROVED_LOW_RES_SOURCES))
    ok = {"sources": {"lo": url}, "conform": {"lo": "720p 放大"}, "conform_sharpen": {"lo": "轻锐化"}}
    assert reel.check_conform_sharpen(ok) == {"lo": "轻锐化"}
    with pytest.raises(reel.ReelError):   # 没放大
        reel.check_conform_sharpen({**ok, "conform": {}})
    with pytest.raises(reel.ReelError):   # 1080p 源
        reel.check_conform_sharpen({**ok, "sources": {"lo": "https://www.youtube.com/watch?v=hd"}})
    with pytest.raises(reel.ReelError):   # 没写理由
        reel.check_conform_sharpen({**ok, "conform_sharpen": {"lo": ""}})


# ---------- 真跑 ffmpeg ----------

def _clip(path: Path, color: str, secs: float, w=320, h=240):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"color=c={color}:s={w}x{h}:r=25:d={secs}", "-f", "lavfi", "-i",
                    f"sine=f=440:d={secs}:r=48000", "-ac", "2", "-shortest",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


def _dur(path: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(path)], capture_output=True,
                                text=True, check=True).stdout)


@needs_ffmpeg
@pytest.mark.parametrize("kinds", [["dissolve", "cut", "flash"], ["dissolve", "whip", "cut"]])
def test_真拼接_每种转场总长不变(tmp_path, kinds):
    lengths, f = [1.0, 1.2, 0.8], 0.18
    ins = []
    for i, (L, c) in enumerate(zip(lengths, ["red", "green", "blue"])):
        p = tmp_path / f"p{i}.mp4"
        _clip(p, c, L + (f if i < 2 else 0))
        ins += ["-i", str(p)]
    out = tmp_path / "o.mp4"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *ins, "-filter_complex",
                    reel.dissolve_filtergraph(lengths, f, transitions=kinds),
                    "-map", "[vout]", "-map", "[aout]", str(out)], check=True)
    assert abs(_dur(out) - sum(lengths)) < 0.08


@needs_ffmpeg
def test_真跑_调色颗粒暗角推镜_尺寸不变(tmp_path):
    src = tmp_path / "s.mp4"
    _clip(src, "gray", 1.0, 1080, 1440)
    out = tmp_path / "o.mp4"
    vf = ("null" + cine.look_filter({"grade": "teal_orange", "grain": 0.4, "vignette": 0.5})
          + cine.push_filter(1.1, 1.0, 1080, 1440))
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-vf", vf,
                    "-an", str(out)], check=True)
    wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                         "stream=width,height,nb_frames", "-of", "json", str(out)],
                        capture_output=True, text=True, check=True).stdout
    st = json.loads(wh)["streams"][0]
    assert (st["width"], st["height"]) == (1080, 1440)
    assert int(st["nb_frames"]) == 25            # 推镜不改帧数＝原速


@needs_ffmpeg
def test_真跑_分轨三条同长(tmp_path, monkeypatch):
    joined = tmp_path / "silent.mp4"
    _clip(joined, "black", 2.0)
    voice = tmp_path / "v.wav"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=f=880:d=0.8:r=48000", str(voice)], check=True)
    mixed = tmp_path / "mixed.m4a"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(joined), "-vn",
                    "-c:a", "aac", str(mixed)], check=True)
    out = reel.export_audio_stems({"slug": "t"}, tmp_path, joined, mixed,
                                  ["-i", str(voice)], ["[1:a]adelay=500|500[v0]"], ["[v0]"])
    lens = {k: _dur(p) for k, p in out.items()}
    assert set(lens) == {"narration", "original", "mix"}
    assert max(lens.values()) - min(lens.values()) < 0.03
