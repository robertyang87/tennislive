"""Native caption frame previews preserve clock/masks and never approve a film."""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'src')]
import build_match_reel as reel
import preview_reel_captions as preview
from test_reel_caption_preflight import prepared_render


def ff(*args):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-threads', '1', *map(str, args)], check=True)


@pytest.fixture
def toy(monkeypatch, tmp_path):
    for key, value in {'VIDEO_W': 180, 'VIDEO_H': 240, 'CROP_W': 180,
                       'CROP_H': 240, 'CROP_Y': 0, 'FPS': 25, 'FPS_EXPR': '25',
                       'LAYOUT': 'full'}.items():
        monkeypatch.setattr(reel, key, value)
    source_frames = tmp_path / 'source'; source_frames.mkdir()
    mask_frames = tmp_path / 'mask'; mask_frames.mkdir()
    for index in range(30):
        picture = Image.new('RGB', (320, 240), (22, 55 + index, 100))
        draw = ImageDraw.Draw(picture)
        width = 60 if index < 12 else 110
        draw.rectangle((10, 190, 10 + width, 225), fill='navy')
        alpha = Image.new('L', (120, 52), 0)
        ad = ImageDraw.Draw(alpha); ad.rectangle((0, 16, width, 51), fill=255)
        if 12 <= index < 24:
            draw.rectangle((10, 174, 110, 189), fill='yellow')
            ad.rectangle((0, 0, 100, 15), fill=255)
        picture.save(source_frames / f'{index:03d}.png')
        alpha.save(mask_frames / f'{index:03d}.png')
    source = tmp_path / 'source.mkv'; mask = tmp_path / 'mask.mkv'
    ff('-framerate', '25', '-i', source_frames / '%03d.png', '-c:v', 'ffv1', source)
    ff('-framerate', '25', '-i', mask_frames / '%03d.png', '-c:v', 'ffv1', '-pix_fmt', 'gray', mask)
    ass = tmp_path / 'captions.ass'
    ass.write_text('''[Script Info]
ScriptType: v4.00+
PlayResX: 180
PlayResY: 240
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TL,DejaVu Sans,18,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,100,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.20,0:00:02.40,TL,,0,0,0,,POINT
''')
    seg = reel.Segment(0, 1.2, .5, '', quote='POINT',
                       score_inset=(10, 174, 130, 226), score_inset_mask=str(mask))
    spec = {'slug': 'toy', 'cover': {'eyebrow': '赛后开麦'}}  # No watermark.
    return source, mask, ass, seg, spec


def test_actual_dynamic_mask_and_absolute_ass_clock_match_two_native_lossless_stages(toy, tmp_path):
    source, mask, ass, seg, spec = toy
    destination = tmp_path / 'preview'
    report = preview.render_frames(spec=spec, segments=[seg], sources={'': source},
        source_w=320, ass=ass, cues=[(1.2, 2.4, 'POINT')], cover_secs=1.2,
        outdir=destination, maximum=2, at=(1.4, 1.92))
    data = json.loads(report.read_text())
    assert data['kind'] == 'visual_preview_only' and data['publication_approved'] is False
    assert 'status' not in data and not (destination / 'render.json').exists()
    assert [s['frame'] for s in data['samples']] == [5, 18]
    assert all(s['mask_sha256'] == preview.sha(mask) for s in data['samples'])
    # Reference uses the real native cut command and a LOSSLESS intermediate;
    # this compares pixel construction, without pretending H.264 is lossless.
    part = tmp_path / 'reference.mkv'
    def lossless(*command):
        command = list(command)
        index = command.index('-c:v')
        command = command[:index] + ['-c:v', 'ffv1', '-pix_fmt', 'yuv420p', '-an', str(part)]
        # Strip the native audio map: source is intentionally video-only.
        index = command.index('-map')
        del command[index + 2:index + 4]
        reel.run(*command)
    reel.cut_segment(source, seg, part, 320, threads=1, command_sink=lossless)
    colors = []
    for index, sample in enumerate(data['samples']):
        reference = tmp_path / f'reference-{index}.png'
        graph = (f'[0:v]setpts=PTS+1.2/TB,subtitles={reel._escape(ass)}:'
                 f"fontsdir={reel._escape(ROOT / 'assets/fonts')},select='eq(n,{sample['frame']})'[out]")
        ff('-i', part, '-filter_complex_threads', '1', '-filter_complex', graph,
           '-map', '[out]', '-frames:v', '1', '-pix_fmt', 'rgb24', reference)
        expected = np.asarray(Image.open(reference).convert('RGB'))
        actual = np.asarray(Image.open(destination / sample['image']).convert('RGB'))
        assert np.array_equal(actual, expected)
        assert np.all(actual[110:150] > 200, axis=2).sum() > 20, 'actual ASS clock must paint POINT'
        colors.append(np.all(actual[174:190, :100, :2] > 180, axis=2).sum())
    assert colors[0] == 0 and colors[1] > 500, 'actual header appears at its mask/source time'


def test_actual_still_full_canvas_keeps_opted_in_captions(tmp_path, monkeypatch):
    for key, value in {'VIDEO_W': 180, 'VIDEO_H': 240, 'FPS': 25, 'FPS_EXPR': '25', 'LAYOUT': 'full'}.items():
        monkeypatch.setattr(reel, key, value)
    image = tmp_path / 'card.png'; Image.new('RGB', (180, 240), 'navy').save(image)
    ass = reel.write_subtitles([(1.2, 2.2, 'OK')], tmp_path / 'sub.ass', height=240, bottom_margin=96)
    seg = reel.Segment(0, 1, .5, 'OK', image=str(image), full_canvas=True, subtitle_bottom=96)
    report = preview.render_frames(spec={'cover': {'eyebrow': '赛后开麦'}}, segments=[seg], sources={},
        source_w=320, ass=ass, cues=[(1.2, 2.2, 'OK')], cover_secs=1.2,
        outdir=tmp_path / 'preview', maximum=1, cue_ids=(1,))
    assert json.loads(report.read_text())['samples'][0]['still_sha256'] == preview.sha(image)
    pixels = np.asarray(Image.open(tmp_path / 'preview/caption-01.png'))
    assert np.all(pixels > 200, axis=2).sum() > 20
    assert not list((tmp_path / 'preview').glob('*.evidence.png'))


def test_preview_hook_uses_final_ass_and_exits_before_track_and_encoding(prepared_render):
    spec, outdir, _render = prepared_render
    def callback(**context):
        assert context['ass'].is_file() and len(context['cues']) == 5
        assert context['cover_secs'] == 1.2
        return outdir / 'preview_manifest.json'
    assert reel.render(spec, outdir, voice='fixture', rate='+0%', preview_callback=callback) == outdir / 'preview_manifest.json'
    assert not (outdir / 'render.json').exists() and not (outdir / 'qc_attestation.json').exists()


def test_real_libass_keeps_match_player_name_on_one_line(tmp_path):
    import cv2
    spec = {'cover': {'matchup': [{'name_en': 'Marie Bouzkova'}]}}
    original = 'was nowhere near Marie Bouzkova in the opening set,\n首盘被布兹科娃完全压制'
    protected = reel.protect_quote_player_names(original, spec)
    masks = []
    for i, text in enumerate((original, protected, 'Marie\u00a0Bouzkova\n中文')):
        ass = reel.write_subtitles([(0., 1., text)], tmp_path / f'{i}.ass',
                                  height=1440, bottom_margin=180)
        picture = tmp_path / f'{i}.png'
        ff('-f', 'lavfi', '-i', 'color=black:s=1080x1440:d=0.04',
           '-vf', f'subtitles={reel._escape(ass)}:fontsdir={reel._escape(ROOT / "assets/fonts")}',
           '-frames:v', '1', picture)
        mask = (np.asarray(Image.open(picture).convert('RGB'))[:, :, 0] > 200).astype('uint8') * 255
        masks.append(mask)
    # Find the actual English name glyphs in a native isolated-name control.
    # A match in the full caption proves both words occupy one physical row.
    ys = np.flatnonzero(masks[2].any(axis=1))
    last = next(y for y in ys if y + 1 not in ys)
    xs = np.flatnonzero(masks[2][ys[0]:last + 1].any(axis=0))
    # Smooth by one pixel to tolerate fractional glyph positioning when the
    # same name is centered as a standalone line vs part of a longer line.
    smoothed = [cv2.GaussianBlur(mask, (0, 0), 1.) for mask in masks]
    template = smoothed[2][ys[0]:last + 1, xs[0]:xs[-1] + 1]
    scores = [cv2.matchTemplate(mask, template, cv2.TM_CCOEFF_NORMED).max()
              for mask in smoothed[:2]]
    assert scores[0] < .80, 'fixture must reproduce the original split name'
    assert scores[1] > .95, 'both words must appear intact on one physical row'


@pytest.mark.parametrize('name', ['render.json', 'qc_attestation.json', 'pushed.json', 'preview_manifest.json'])
def test_destination_with_old_proof_cannot_be_reused(tmp_path, name):
    (tmp_path / name).write_text('{}')
    with pytest.raises(ValueError, match='metadata|preview'):
        preview.safe_output(tmp_path)


def test_actual_command_sink_preserves_default_argv(toy, monkeypatch, tmp_path):
    source, _mask, _ass, seg, _spec = toy
    seen = []
    monkeypatch.setattr(reel, '_has_audio', lambda _p: True)
    monkeypatch.setattr(reel, 'run', lambda *args: seen.append(args))
    dest = tmp_path / 'part.mp4'
    reel.cut_segment(source, seg, dest, 320, threads=1)
    captured = []
    reel.cut_segment(source, seg, dest, 320, threads=1, command_sink=lambda *args: captured.append(args))
    assert seen == captured and seen[0][-1] == str(dest)


def test_bad_sample_arguments_reject_without_media_io(tmp_path, monkeypatch):
    seg = reel.Segment(0, 1, .5, '字幕')
    for options in ({'maximum': 0}, {'cue_ids': (0,)}, {'at': (float('nan'),)}, {'at': (0.,)}):
        with pytest.raises(ValueError):
            preview.sample_frames([(1.2, 2.2, '字幕')], [seg], 1.2, **options)
    with pytest.raises(ValueError):
        preview.safe_output(ROOT / 'output/2026-10-13/reel/example')
    monkeypatch.setattr(sys, 'argv', ['preview', '--spec', 'missing.json', '--outdir', str(tmp_path), '--max-frames', '0'])
    monkeypatch.setattr(reel, 'render', lambda *_a, **_k: pytest.fail('invalid arguments reached render'))
    with pytest.raises(SystemExit):
        preview.main()


def test_automatic_sample_budget_prioritizes_distinct_native_bottoms(monkeypatch):
    monkeypatch.setattr(reel, 'FPS', 25)
    seg = reel.Segment(0, 12, .5, '字幕', subtitle_bottom=306,
        subtitle_bottom_windows=((1, 2, 360), (3, 4, 360), (7, 9, 480)))
    cues = [(1.2, 2., '普通板'), (2.3, 3., '提示条'), (4.3, 5., '第二次提示条'),
            (8.3, 9.5, '居中赛果')]
    samples = preview.sample_frames(cues, [seg], 1.2, maximum=3)
    assert len(samples) == 3
    assert {row['reason'] for row in samples} == {'distinct-bottom-306', 'distinct-bottom-360', 'distinct-bottom-480'}
    assert all(abs(row['segment_time'] * 25 - row['frame']) < 1e-6 for row in samples)



def _multi_match_preview_recipe():
    source = 'https://api.wtatennis.com/tennis/tournaments/405/2026/matches?states=C'
    spec = {
        'sources': {'r1': 'https://example.org/r1.mp4', 'final': 'https://example.org/final.mp4'},
        'cover': {'eyebrow': '赛场之上', 'layout': 'solo', 'winner': '西尼亚科娃',
                  'result': '6-1 6-0', 'topic': 'WTA250 大阪 决赛 · 西尼亚科娃 VS 克鲁格',
                  'matchup': [{'name': '西尼亚科娃'}, {'name': '克鲁格'}]},
        'topbar': {'line1': '2026 WTA250 大阪 决赛', 'line2': '西尼亚科娃 6-1 6-0 克鲁格',
                   'pulse_at': [9.5]},
        'segments': [{'source': 'r1', 'start': 100, 'end': 104},
                     {'title_card': '走向决赛', 'seconds': 2, 'narration': '走向决赛'},
                     {'source': 'final', 'start': 200, 'end': 205}],
        'topbar_by_source': {
            'r1': {'line1': '2026 WTA250 大阪 首轮', 'winner': '西尼亚科娃',
                   'loser': '斯特恩斯', 'result': '6-4 0-6 4-0 Ret.', 'source': source},
            'final': {'line1': '2026 WTA250 大阪 决赛', 'winner': '西尼亚科娃',
                      'loser': '克鲁格', 'result': '6-1 6-0', 'source': source}}}
    segments = [reel.Segment(100, 104, .5, '', source='r1'),
                reel.Segment(0, 2, .5, '走向决赛', image='native-card.jpg', full_canvas=True),
                reel.Segment(200, 205, .5, '', source='final')]
    return spec, segments


def test_preview_visual_graph_uses_native_per_source_match_header_windows(tmp_path):
    spec, segments = _multi_match_preview_recipe()
    ass = tmp_path / 'captions.ass'
    ass.write_text('[Script Info]\nScriptType: v4.00+\n')
    inputs, graph = preview.visual_graph(spec, segments, 1.2, ass, tmp_path, first_extra=1)
    actual = tmp_path / 'preview_topbar.ass'
    reference = reel.write_segment_topbar_ass(
        spec, segments, 1.2, tmp_path / 'native_topbar.ass',
        default_lines=reel._topbar_lines(spec), pulse_at=[9.5])
    assert actual.read_bytes() == reference.read_bytes()
    rows = [row for row in actual.read_text().splitlines() if row.startswith('Dialogue:')]
    assert len(rows) == 4
    assert all(',0:00:01.20,0:00:05.20,' in row for row in rows[:2])
    assert '斯特恩斯' in rows[1] and '克鲁格' not in rows[1]
    assert all(',0:00:07.20,0:00:12.20,' in row for row in rows[2:])
    assert '克鲁格' in rows[3] and '斯特恩斯' not in rows[3]
    assert reel._escape(actual) in graph
    # Full-canvas restoration still runs on the actual native card interval.
    assert 'gte(t,5.200000)*lt(t,7.200000)' in graph
    assert inputs == []


def test_preview_visual_graph_without_source_map_keeps_legacy_ass_bytes(tmp_path):
    spec, segments = _multi_match_preview_recipe()
    spec.pop('topbar_by_source')
    ass = tmp_path / 'captions.ass'
    ass.write_text('[Script Info]\nScriptType: v4.00+\n')
    preview.visual_graph(spec, segments, 1.2, ass, tmp_path, first_extra=1)
    reference = reel.write_topbar_ass(
        reel._topbar_lines(spec), 1.2, 12.2, tmp_path / 'legacy_topbar.ass', pulse_at=[9.5])
    assert (tmp_path / 'preview_topbar.ass').read_bytes() == reference.read_bytes()
