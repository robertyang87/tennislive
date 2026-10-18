"""采访／发言段按人物中心裁：固定框、不跟随、凭 `cx_face` 证据放行 cx≠0.5。

账号所有者 2026-10-18：「人物采访的时候，他那个画面的裁切要以人物的中心做裁切比较好」，
看过对比图后「好的，可以」「比赛的还是以球场中心为弄」。量法 `tools/measure_person_center.py`。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from tennislive.video import crop_policy as C  # noqa: E402

LEGACY = json.loads((ROOT / "data" / "legacy_person_frame.json").read_text(encoding="utf-8"))["reels"]


def _person(samples, cx=None, size=(1920, 1080)):
    lo, hi = min(samples), max(samples)
    return {"frame": "person", "cx": C.person_center_cx(lo, hi, *size) if cx is None else cx,
            "track": False, "cx_face": {"samples": samples, "source_size": list(size)}}


def test_固定框取所有脸的正中_夹住不出画():
    assert C.person_center_cx(0.485, 0.646, 1920, 1080) == 0.566
    assert C.person_center_cx(0.95, 0.97, 1920, 1080) == round(1 - 810 / 3840, 3)
    assert C.person_center_cx(0.4, 0.5, 1080, 1920) == 0.5     # 竖屏源本来就不裁左右


def test_有证据的人物段放行_其余照旧钉死中心():
    C.require_fixed_center(_person([0.62, 0.63, 0.63, 0.64, 0.64]))
    bad = [_person([0.62, 0.63, 0.63, 0.64]),                     # 认出脸不足 5 帧
           _person([0.30, 0.40, 0.50, 0.60, 0.70]),               # 散开超过一个框
           _person([0.62, 0.63, 0.63, 0.64, 0.64], cx=0.5),       # cx 不是证据算出来的
           {**_person([0.62, 0.63, 0.63, 0.64, 0.64]), "track": True},
           {"frame": "person", "cx": 0.6}]                        # 没有证据
    for s in bad:
        with pytest.raises(C.VideoCropPolicyError):
            C.require_fixed_center(s)
    with pytest.raises(C.VideoCropPolicyError, match="固定中间"):
        C.require_fixed_center({"frame": "court", "cx": 0.6})


def test_cut_segment_凭person_frame放行(tmp_path):
    import build_match_reel as reel  # noqa: PLC0415
    good = _person([0.62, 0.63, 0.63, 0.64, 0.64])
    seg = reel.Segment(0, 1, good["cx"], "", person_frame={"frame": "person", "cx_face": good["cx_face"]})
    with pytest.raises(Exception) as exc:      # 过了裁切闸，死在找不到源片
        reel.cut_segment(tmp_path / "missing.mp4", seg, tmp_path / "out.mp4", 1920)
    assert not isinstance(exc.value, C.VideoCropPolicyError)
    with pytest.raises(C.VideoCropPolicyError):
        reel.cut_segment(tmp_path / "missing.mp4", reel.Segment(0, 1, good["cx"], ""),
                         tmp_path / "out.mp4", 1920)


def test_采访段必须声明取景():
    seg = {"_quote_kind": "ceremony", "quote": "x"}
    assert C.person_frame_problems({"segments": [seg]})
    assert C.person_frame_problems({"segments": [{**seg, "frame": "court"}]})
    assert not C.person_frame_problems({"segments": [{**seg, "frame": "court", "_frame_why": "人在走动"}]})
    assert not C.person_frame_problems({"segments": [{**seg, **_person([0.5, 0.5, 0.51, 0.5, 0.5])}]})
    assert not C.person_frame_problems({"segments": [{"_quote_kind": "broadcast", "quote": "x"}]})


def _reels():
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        yield spec.get("slug") or path.stem, spec


def test_新片都合规矩_豁免表只许减():
    bad = [f"{slug}: {p}" for slug, spec in _reels() if slug not in LEGACY
           for p in C.person_frame_problems(spec)]
    assert not bad, "\n".join(bad)
    slugs = {slug for slug, _ in _reels()}
    assert not [s for s in LEGACY if s not in slugs], "豁免表里有已经不在库里的 slug"
    assert len(LEGACY) <= 9, "豁免表只许减不许加（2026-10-18 定规矩那天 9 条）"
    assert "kartal-story-2026" not in LEGACY, "kartal-story-2026 是这条规矩的样板"


def test_validate_spec在dry_run就拦(monkeypatch):
    import build_match_reel as reel  # noqa: PLC0415
    spec = json.loads((ROOT / "specs" / "reels" / "kartal-story-2026.json").read_text(encoding="utf-8"))
    seg = next(s for s in spec["segments"] if s.get("frame") == "person")
    seg.pop("frame")
    seg.pop("cx_face")
    with pytest.raises(reel.ReelError, match="人物中心裁切"):
        reel.validate_spec(spec)
