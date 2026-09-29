"""New footage renders must fail before encoding noncentral video crops."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from tennislive.video.crop_policy import (
    VideoCropPolicyError, require_fixed_center, require_reel_center,
)
import build_match_reel as reel
import build_interview_clip as interview


def test_segment_defaults_to_fixed_not_tracking():
    segment = reel.Segment(0, 1, .5, "")
    assert segment.track is False


@pytest.mark.parametrize("setting", [{"track": True}, {"cx": .3}])
def test_direct_cut_cannot_bypass_center_policy(setting, tmp_path):
    segment = reel.Segment(0, 1, setting.get("cx", .5), "",
                           track=setting.get("track", False))
    with pytest.raises(VideoCropPolicyError, match="固定中间"):
        reel.cut_segment(tmp_path / "missing.mp4", segment,
                         tmp_path / "out.mp4", 1920)


@pytest.mark.parametrize("setting", [{"track": True}, {"cx": .3},
                                     {"square_pan": [[0, .5], [1, .6]]}])
def test_reel_render_refuses_off_center_before_downloading(setting, tmp_path):
    with pytest.raises(VideoCropPolicyError, match="固定中间"):
        reel.render({"segments": [setting]}, tmp_path, voice="", rate="")


@pytest.mark.parametrize("block", ["body", "lead_in", "trail_in"])
def test_interview_all_video_blocks_refuse_shift(block, tmp_path):
    offcenter = {"crop_shift_x": -.1}
    spec = offcenter if block == "body" else {block: offcenter}
    with pytest.raises(VideoCropPolicyError, match="固定中间"):
        interview.render(spec, tmp_path / "subs.ass", tmp_path)


def test_explainer_intro_refuses_noncentral_crop_before_media_io(tmp_path):
    from tennislive.video.explainer import assemble_explainer_video
    with pytest.raises(VideoCropPolicyError, match="固定中间"):
        assemble_explainer_video([], [], tmp_path / "out.mp4",
                                 intro=tmp_path / "missing.mp4", intro_cx=.4)


def test_cover_focus_and_still_photo_framing_are_not_video_policy():
    spec = {"cover": {"portrait": {"focus": .2, "zoom": 1.3}},
            "segments": [{"image": "photo.jpg", "cx": .2}, {"cx": .5, "track": False}]}
    require_reel_center(spec)
    assert spec["cover"]["portrait"] == {"focus": .2, "zoom": 1.3}


@pytest.mark.parametrize("settings", [{}, {"cx": None},
                                     {"cx": .5, "track": False, "crop_shift_x": 0}])
def test_centered_or_default_framing_remains_allowed(settings):
    require_fixed_center(settings)
