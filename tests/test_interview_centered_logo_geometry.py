"""The logo gate must agree with the actual ffmpeg crop, including zoom."""
import subprocess

import numpy as np
import pytest
from PIL import Image

from tools.build_interview_clip import CROP_RATIO, _crop_expr, tennistv_logo_problem


@pytest.mark.parametrize("keep,shift,allowed", [
    (1.0, -0.06, True),   # Existing shifted template remains valid.
    (1.0, 0.0, False),    # Default centre retains part of the logo.
    (0.90, 0.0, False),   # Zoom alone is not an exemption.
    (0.86, 0.0, True),    # Exact centred window ends before the logo.
])
def test_gate_matches_rendered_logo_pixels(tmp_path, keep, shift, allowed):
    source = tmp_path / "source.png"
    image = Image.new("RGB", (1920, 1080), (48, 48, 48))
    # First logo pixel is at the measured source boundary x=.823.
    image.paste((255, 255, 255), (1580, 43, 1860, 108))
    image.save(source)
    frame = tmp_path / "cropped.png"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(source), "-vf",
        _crop_expr(CROP_RATIO, keep, shift), "-frames:v", "1", str(frame),
    ], check=True)
    has_logo = bool((np.asarray(Image.open(frame).convert("L")) > 200).any())
    spec = {"slug": "geometry-probe", "url": "https://www.tennistv.com/videos/test",
            "crop_shift_x": shift, "crop_keep_top": keep}
    assert (tennistv_logo_problem(spec) is None) is allowed
    assert has_logo is (not allowed)
