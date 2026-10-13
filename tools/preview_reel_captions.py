#!/usr/bin/env python3
"""Preview actual native caption pixels before encoding a complete reel.

PNG samples are visual previews, never QC/publication proof. Source and measured
mask are decoded from the original segment start: both retain the exact native
clock, including changing board widths and BREAK/SET/MATCH POINT graphics.
"""
from __future__ import annotations

import argparse
from functools import partial
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'src')]
import build_match_reel as reel


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def safe_output(outdir: Path) -> Path:
    outdir = outdir.resolve()
    if outdir == ROOT or outdir.is_relative_to(ROOT / 'output'):
        raise ValueError('Caption preview must use a scratch directory outside production output/')
    if any((outdir / name).exists() or (outdir / name).is_symlink() for name in
           ('render.json', 'qc_attestation.json', 'pushed.json', 'preview_manifest.json')):
        raise ValueError('Preview destination contains production metadata or an earlier preview')
    return outdir


def sample_frames(cues, segments, cover_secs, *, maximum=8, cue_ids=(), at=()):
    if type(maximum) is not int or not 1 <= maximum <= 24:
        raise ValueError('max-frames must be an integer from 1 to 24')
    windows = []
    cursor = cover_secs
    for index, seg in enumerate(segments):
        windows.append((cursor, cursor + seg.length, index))
        cursor += seg.length
    selected = []

    def add(time, reason, cue=None):
        if not isinstance(time, (int, float)) or not math.isfinite(time):
            raise ValueError('Preview time must be finite')
        span = next((w for w in windows if w[0] <= time < w[1]), None)
        if span is None:
            raise ValueError('Preview time must be inside a match segment, not cover/outro')
        lo, hi, index = span
        frame = math.floor((time - lo) * reel.FPS + 1e-6)
        landed = lo + frame / reel.FPS
        if cue and landed < cue[0] - 1e-6:
            frame = math.ceil((cue[0] - lo) * reel.FPS - 1e-6)
            landed = lo + frame / reel.FPS
        if landed >= hi or (cue and not cue[0] - 1e-6 <= landed < cue[1]):
            raise ValueError('The selected caption has no complete video frame in this segment')
        identity = (index, frame)
        if not any((s['segment'], s['frame']) == identity for s in selected):
            selected.append({'segment': index, 'frame': frame, 'film_time': landed,
                             'segment_time': frame / reel.FPS, 'reason': reason,
                             'cue_text': cue[2] if cue else None})

    if cue_ids or at:
        for value in cue_ids:
            if type(value) is not int or not 1 <= value <= len(cues):
                raise ValueError('cue is a one-based index into the actual ASS cue list')
            cue = cues[value - 1]
            add((cue[0] + cue[1]) / 2, f'manual-cue-{value}', cue)
        for time in at:
            add(time, 'manual-film-time')
        if len(selected) > maximum:
            raise ValueError('Requested samples exceed max-frames; raise the explicit bound')
        return selected
    # Native geometry records may contain only SETS of widths/headers, with no
    # per-frame timestamps. Do not invent transition times from those sets.
    # Explicit position windows and actual point cues are reliable time anchors.
    position_windows = reel.segment_subtitle_bottom_windows(segments, cover_secs)
    seen_margins = set()
    for lo, hi, bottom in position_windows:
        if bottom in seen_margins:
            continue
        seen_margins.add(bottom)
        contained = next((cue for cue in cues if lo <= cue[0] < cue[1] <= hi), None)
        time = (contained[0] + contained[1]) / 2 if contained else (lo + hi) / 2
        add(time, f'distinct-bottom-{bottom}', contained)
        if len(selected) >= maximum:
            break
    # Remaining slots can show native geometry on both sides of a declared
    # header-position change; those positions are not inferred width changes.
    for lo, hi, _bottom in position_windows:
        if len(selected) >= maximum:
            break
        for time, reason in ((lo - 1 / reel.FPS, 'before-position-window'),
                             (hi, 'after-position-window')):
            if cover_secs <= time < cursor:
                add(time, reason)
                if len(selected) >= maximum - 1:
                    break
        if len(selected) >= maximum - 1:
            break
    ranked = sorted(enumerate(cues, 1), key=lambda pair: (
        not bool(re.search(r'BREAK POINT|SET POINT|MATCH POINT|破发点|盘点|赛点', pair[1][2], re.I)),
        -max(map(len, pair[1][2].splitlines())), pair[0]))
    for number, cue in ranked:
        if len(selected) >= maximum:
            break
        if any(lo <= (cue[0] + cue[1]) / 2 < hi for lo, hi, _ in windows):
            add((cue[0] + cue[1]) / 2, f'actual-cue-{number}', cue)
    if not selected:
        raise ValueError('No actual match captions available to preview')
    return selected


def visual_graph(spec, segments, cover_secs, ass, outdir, first_extra):
    """Use the native final match canvas, fonts, ASS and full-canvas restoration."""
    match_end = cover_secs + sum(s.length for s in segments)
    topbar = reel._topbar_lines(spec)
    top_ass = None
    if topbar:
        raw = (spec.get('topbar') or {}).get('pulse_at') or []
        pulses = [float(t) for t in raw] if isinstance(raw, list) else []
        top_ass = reel.write_topbar_ass(topbar, cover_secs, match_end,
                                        outdir / 'preview_topbar.ass', pulse_at=pulses)
    inputs = []
    foot = wm = scrim = None
    scrim_y = 0

    def append(path):
        index = first_extra + len(inputs) // 2
        inputs.extend(['-i', str(path)])
        return index

    if reel.LAYOUT == 'band' and top_ass:
        foot = append(reel.band_foot_strip(outdir / '_preview_foot.png'))
    column = str((spec.get('cover') or {}).get('eyebrow') or '').strip() or '赛场之上'
    topic = str((spec.get('cover') or {}).get('topic') or '').strip()
    if reel.wants_watermark(column):
        wm = append(reel.brand_watermark(outdir / '_preview_watermark.png', column, topic))
    if reel.LAYOUT != 'band' and reel.wants_subtitle_scrim(spec):
        default = reel.default_margin_v()
        margin = (int(spec['subtitle_top']) if 'subtitle_top' in spec
                  else reel.subtitle_margin_for_boards(segments, default))
        lead = reel.SUB_SCRIM_LEAD_PX if margin >= default else reel.SUB_SCRIM_LIFTED_LEAD_PX
        image, scrim_y = reel.subtitle_scrim(outdir / '_preview_scrim.png', margin, lead)
        scrim = append(image)
    if top_ass:
        fonts = reel._escape(ROOT / 'assets/fonts')
        graph = ('[0:v]' + reel.match_canvas_filtergraph(
            foot_input=foot, wm_input=wm, scrim_input=scrim, scrim_y=scrim_y)
            + f'[match_canvas]subtitles={reel._escape(top_ass)}:fontsdir={fonts},'
            + f'subtitles={reel._escape(ass)}:fontsdir={fonts}[out]')
    else:
        graph = reel.plain_filtergraph(ass, cover_secs, match_end, wm,
                                      scrim_input=scrim, scrim_y=scrim_y)
    return inputs, reel.full_canvas_filtergraph(graph, segments, cover_secs, subtitles_ass=ass)


def frame_command(native, graph, extra_inputs, offset, frame, dest):
    """Adapt an actual native segment command to a video-only, lossless PNG."""
    native = list(native)
    position = native.index('-filter_complex') if '-filter_complex' in native else native.index('-vf')
    prefix = native[:position]
    # -t is an output option in the native command. Adding decoration inputs
    # must not turn it into an input option or truncate an absolute ASS clock.
    if '-t' in prefix:
        limit = prefix.index('-t')
        del prefix[limit:limit + 2]
    # Native audio stream/filter options must not leave an unconnected label.
    part = native[position + 1]
    if native[position] == '-vf':
        part = '[0:v]' + part + '[part]'
    else:
        part = part.replace('[vout]', '[part]')
        if '[aout]' in part:
            part += ';[aout]anullsink'
    count = graph.count('[0:v]')
    if not count:
        raise ValueError('Native final graph has no video input')
    labels = [f'[preview_global_{i}]' for i in range(count)]
    normalized = f';[part]format=yuv420p,setpts=PTS+{offset:.9f}/TB'
    normalized += (f',split={count}' if count > 1 else ',null') + ''.join(labels) + ';'
    for label in labels:
        graph = graph.replace('[0:v]', label, 1)
    result = part + normalized + graph + f";[out]select='eq(n,{frame})'[preview_frame]"
    return [*prefix, *extra_inputs, '-filter_complex_threads', '1', '-filter_complex', result,
            '-map', '[preview_frame]', '-an', '-frames:v', '1', '-c:v', 'png',
            '-threads', '1', '-pix_fmt', 'rgb24', str(dest)]


def render_frames(*, spec, segments, sources, source_w, ass, cues, cover_secs,
                  outdir, maximum=8, cue_ids=(), at=(), spec_path=None):
    """Callback runs before any complete-part encode and creates no QC record."""
    outdir = safe_output(Path(outdir))
    outdir.mkdir(parents=True, exist_ok=True)
    if any(s.track or s.square_pan for s in segments):
        raise ValueError('Preview cannot silently approximate a tracked video crop')
    samples = sample_frames(cues, segments, cover_secs, maximum=maximum, cue_ids=cue_ids, at=at)
    offsets = []
    cursor = cover_secs
    for seg in segments:
        offsets.append(cursor); cursor += seg.length
    source_hashes = {key: sha(path) for key, path in sources.items()}
    rows = []
    for number, sample in enumerate(samples, 1):
        index = sample['segment']; seg = segments[index]
        dest = outdir / f'caption-{number:02d}.png'
        command_record = {}

        def sink(*native):
            extras, graph = visual_graph(spec, segments, cover_secs, ass, outdir, list(native).count('-i'))
            command = frame_command(native, graph, extras, offsets[index], sample['frame'], dest)
            command_record.update(native=list(native), preview=command)
            reel.run(*command)

        if seg.image:
            reel.cut_still_segment(seg, dest, threads=1, command_sink=sink)
        else:
            reel.cut_segment(sources[seg.source], seg, dest, source_w,
                             threads=1, command_sink=sink)
        from PIL import Image
        with Image.open(dest) as picture:
            picture.load()
            if picture.size != (reel.VIDEO_W, reel.VIDEO_H):
                raise ValueError('Native preview did not produce the real canvas size')
        mask = Path(seg.score_inset_mask) if seg.score_inset_mask else None
        rows.append({**sample, 'image': dest.name, 'image_sha256': sha(dest),
                     'source': seg.source, 'source_time': None if seg.image else
                     seg.start + sample['segment_time'] * seg.speed,
                     'source_sha256': None if seg.image else source_hashes[seg.source],
                     'still_sha256': sha(Path(seg.image)) if seg.image else None,
                     'mask_sha256': sha(mask) if mask else None,
                     'resolved_scorebox': seg.score_inset,
                     'native_command': command_record['native'],
                     'preview_command': command_record['preview']})
    manifest = {'schema': 'tennislive.native-caption-frame-preview.v1',
                'kind': 'visual_preview_only', 'publication_approved': False,
                'spec_file_sha256': sha(Path(spec_path)) if spec_path else None,
                'spec_canonical_sha256': hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                'ass_sha256': sha(ass), 'fps': reel.FPS_EXPR,
                'canvas': [reel.VIDEO_W, reel.VIDEO_H], 'cover_seconds': cover_secs,
                'limitations': ['No final QC or publication approval',
                    'Interior segment samples exclude dissolves and final H.264 compression',
                    'Audio is not produced or evaluated',
                    'Geometry sets without timestamps do not prove all board-width transitions were sampled'],
                'samples': rows}
    report = outdir / 'preview_manifest.json'
    report.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--source', action='append', default=[], metavar='KEY=PATH')
    parser.add_argument('--outdir', required=True, type=Path)
    parser.add_argument('--max-frames', type=int, default=8)
    parser.add_argument('--cue', default='', help='One-based actual caption indices, comma separated')
    parser.add_argument('--at', default='', help='Absolute film times in seconds, comma separated')
    parser.add_argument('--voice', default='zh-CN-YunjianNeural')
    parser.add_argument('--rate', default='+6%')
    args = parser.parse_args()
    if not 1 <= args.max_frames <= 24:
        parser.error('--max-frames must be from 1 to 24')
    try:
        cue_ids = tuple(int(x) for x in args.cue.split(',') if x)
        times = tuple(float(x) for x in args.at.split(',') if x)
        if any(x < 1 for x in cue_ids) or any(not math.isfinite(x) or x < 0 for x in times):
            raise ValueError('Invalid cue index or nonfinite/negative film time')
        if len(set(cue_ids)) + len(set(times)) > args.max_frames:
            raise ValueError('Explicit samples exceed --max-frames')
    except ValueError as exc:
        parser.error(str(exc))
    outdir = safe_output(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    spec = json.loads(args.spec.read_text())
    for source in args.source:
        key, separator, path = source.partition('=')
        if not separator or key not in reel.spec_sources(spec):
            raise ValueError('--source must use an actual spec source key (empty key allowed)')
        original = Path(path).resolve(strict=True)
        staged = outdir / (f'source_{key}.mp4' if key else 'source.mp4')
        if staged.parent != outdir:
            raise ValueError('Source key must remain a flat filename inside preview scratch')
        if staged.exists() or staged.is_symlink():
            raise ValueError('Source destination already exists')
        staged.symlink_to(original)
    reel.apply_tts_backend(spec)
    callback = partial(render_frames, maximum=args.max_frames,
                       cue_ids=cue_ids, at=times, spec_path=args.spec)
    report = reel.render(spec, outdir, voice=args.voice, rate=args.rate, preview_callback=callback)
    print(f'Native caption PNG preview: {report}; no final-film QC/publication proof')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
