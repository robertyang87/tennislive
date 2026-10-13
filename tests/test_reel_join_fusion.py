"""The removed intermediate encode must not change the native media clock."""
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'src')]
import build_match_reel as reel
import reel_join_fusion as fusion


def ff(*args):
    return subprocess.run(['ffmpeg', '-v', 'error', '-y', '-filter_complex_threads', '1',
                           *map(str, args)], check=True, capture_output=True, text=True)


def packets(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_packets',
        '-show_data_hash', 'sha256', '-show_entries', 'packet=pts,dts,duration,data_hash',
        '-of', 'json', str(path)], text=True))['packets']


@pytest.fixture
def media(tmp_path):
    lengths = [1.217, .8, .613]  # Includes two boundaries between frame instants.
    parts = []
    for index, length in enumerate(lengths):
        duration = length + (.18 if index < 2 else 0)
        path = tmp_path / f'part-{index}.mp4'
        ff('-f', 'lavfi', '-i', f'testsrc2=size=96x128:rate=25:duration={duration}',
           '-f', 'lavfi', '-i', f'sine=frequency={400 + index * 130}:sample_rate=48000:duration={duration}',
           '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '12', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '160k', path)
        parts.append(path)
    graph = reel.dissolve_filtergraph(lengths, .18)
    plan, reason = fusion.plan(graph, len(parts))
    assert plan and not reason
    inputs = [arg for part in parts for arg in ('-i', str(part))]
    joined, clock = tmp_path / 'joined.mp4', tmp_path / 'clock.mp4'
    for path, g in [(joined, graph), (clock, plan.clock_graph())]:
        ff(*inputs, '-filter_complex', g, '-map', '[vout]', '-map', '[aout]',
           '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '12', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', path)
    return lengths, parts, inputs, plan, joined, clock


def test_nonintegral_native_clock_and_music_duck_mix_keep_every_aac_packet(media, tmp_path):
    _, _, _, _, joined, clock = media
    assert fusion.video_clock(joined) == fusion.video_clock(clock)
    assert reel.probe_duration(joined) == reel.probe_duration(clock)
    assert packets(joined) == packets(clock)
    voice = tmp_path / 'voice.m4a'
    ff('-f', 'lavfi', '-i', 'sine=frequency=740:sample_rate=48000:duration=0.31',
       '-c:a', 'aac', voice)
    mixed = []
    for name, path in [('reference', joined), ('clock', clock)]:
        target = tmp_path / f'{name}-mix.m4a'
        graph = reel.duck_filtergraph(['[1:a]adelay=280|280[v1]'], ['[v1]'],
                                     reel.music_chain(2, reel.probe_duration(path)))
        ff('-i', path, '-i', voice, '-stream_loop', '-1', '-i', voice,
           '-filter_complex', graph, '-map', '0:v:0', '-map', '[out]', '-c:v', 'copy',
           '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', target)
        mixed.append(target)
    assert packets(mixed[0]) == packets(mixed[1])


def test_full_canvas_and_all_three_extra_inputs_match_lossless_reference(media, tmp_path):
    lengths, _, inputs, plan, _, clock = media
    extras = []
    for index, color in enumerate(['red', 'lime', 'blue']):
        png = tmp_path / f'overlay-{index}.png'
        Image.new('RGB', (8, 8), color).save(png)
        extras.extend(['-i', str(png)])
    # Exercise real input relocation for footer, watermark and subtitle scrim
    # and a second undecorated joined-video consumer for full-canvas restoration.
    native = ('[0:v][2:v]overlay=4:4[a];[a][3:v]overlay=18:18[b];'
              '[b][4:v]overlay=30:30[out]')
    segs = [reel.Segment(0, .8, .5, ''),
            reel.Segment(0, .613, .5, '', full_canvas=True)]
    native = reel.full_canvas_filtergraph(native, segs, lengths[0])
    bridge = tmp_path / 'lossless.mkv'
    ff(*inputs, '-filter_complex', plan.video_graph, '-map', '[vout]', '-an',
       '-c:v', 'ffv1', '-pix_fmt', 'yuv420p', bridge)
    # Dummy input occupies the native mixed-audio slot; it is never selected.
    dummy = ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    reference = ff('-i', bridge, *dummy, *extras, '-filter_complex', native,
                   '-map', '[out]', '-an', '-pix_fmt', 'yuv420p', '-f', 'framemd5', '-').stdout
    actual = ff(*inputs, *dummy, *extras, '-filter_complex', plan.final_graph(native),
                '-map', '[out]', '-an', '-pix_fmt', 'yuv420p', '-f', 'framemd5', '-').stdout
    assert reference == actual
    final = tmp_path / 'final.mp4'
    ff(*inputs, *dummy, *extras, '-filter_complex', plan.final_graph(native),
       '-map', '[out]', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
       '-pix_fmt', 'yuv420p', final)
    fusion.require_matching_frame_clock(clock, final)
    rate, points = fusion.video_clock(final)
    assert rate == Fraction(25) and len(points) > 60


def test_clock_mismatch_fails_instead_of_silently_passing(media):
    _, parts, _, _, _, clock = media
    with pytest.raises(ValueError, match='native joined frame clock'):
        fusion.require_matching_frame_clock(clock, parts[0])


def test_unknown_graph_preselects_legacy_and_input_collision_fails():
    plan, reason = fusion.plan('[0:v]hflip[vout];[0:a]anull[aout]', 1)
    assert plan is None and reason
    valid, reason = fusion.plan(reel.dissolve_filtergraph([1., 2.], .18), 2)
    assert valid and not reason
    assert fusion.plan(reel.dissolve_filtergraph([1., 2.], .18) + ';[9:v]null[x]', 2)[0] is None
    with pytest.raises(ValueError, match='collides'):
        valid.final_graph('[0:v]null[fusion_collision];[fusion_collision]null[out]')
    with pytest.raises(ValueError, match='mixed-audio video'):
        valid.final_graph('[0:v][1:v]overlay[out]')


def test_one_part_uses_the_same_clock_and_finite_video_source():
    plan, reason = fusion.plan(reel.dissolve_filtergraph([1.], .18), 1)
    assert plan and not reason
    assert plan.audio_graph == '[0:a]anull[aout]'
    assert '[0:v]scale=2:2' in plan.clock_graph()
    assert '[2:v]' in plan.final_graph('[0:v][2:v]overlay[out]')
