"""A measured odd crop must preserve its actual source pixels, not YUV rounding."""
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel


def test_odd_native_graphic_edges_keep_the_complete_source_crop(tmp_path):
    yy, xx = np.indices((32, 48))
    rgb = np.stack(((xx * 5) % 255, (yy * 7) % 255, (xx * 3 + yy * 4) % 255), axis=2).astype(np.uint8)
    source = tmp_path / 'source.mkv'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                    '-s', '48x32', '-r', '1', '-i', '-', '-frames:v', '1',
                    '-c:v', 'ffv1', '-pix_fmt', 'yuv420p', str(source)], input=rgb.tobytes(), check=True)
    mask = tmp_path / 'mask.mkv'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray',
                    '-s', '13x9', '-r', '1', '-i', '-', '-frames:v', '1',
                    '-c:v', 'ffv1', str(mask)], input=bytes([255]) * 13 * 9, check=True)
    decoded = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(source),
                                      '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
    expected = np.frombuffer(decoded, np.uint8).reshape(32, 48, 3)[7:16, 5:18]
    patch = reel.masked_board_patch(5, 7, 18, 16, str(mask), 13, 9)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(source),
                                  '-filter_complex', '[0:v]null[wb];' + patch,
                                  '-map', '[b]', '-frames:v', '1', '-pix_fmt', 'rgba', '-f', 'rawvideo', '-'])
    actual = np.frombuffer(raw, np.uint8).reshape(9, 13, 4)
    assert np.array_equal(actual[:, :, :3], expected), 'Native graphic pixels moved or stretched by crop rounding'
    assert (actual[:, :, 3] == 255).all()
