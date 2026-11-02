#!/usr/bin/env python3
"""Silent, credited photo/card sequences for the Vacherot year story only.

Input follows the reviewed Alcaraz HD photo-plan: segment-keyed objects with
seconds, shots, optional cuts, and optional tail_seconds (default .56). Photos
use image/focus/photo_source; cards use native_title/native_content/label.
Run --previews-only for native PNG layout checks, without encoding sequences.
The main reel owns TTS, subtitles, the top brand watermark and publication.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from tennislive.video import transition_cards
from tennislive.chromium import launch_chromium
from tennislive.video.explainer import _data_uri

ASSET = ROOT / 'assets/reel/vacherot-basel-title-story-2026/year-story'
SIZE = (1080, 1440)
PHOTO = (1080, 950)
FPS = 25
FADE = .28
LABELS = {
    'paris-official-r2': '2025.10.29 巴黎大师赛 第二轮',
    'monte-official-qf1990': '2026.04.10 蒙特卡洛 1/4决赛',
    'atp-4585737': '2026.10.02 东京 第二轮',
    'atp-4591062': '2026.10.12 上海大师赛 第三轮',
    'atp-4591063': '2026.10.12 上海大师赛 第三轮',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def credited_photo(shot):
    path = (ROOT / shot['image']).resolve()
    credits = json.loads((ASSET / 'credits.json').read_text())
    found = next((c for c in credits if (ROOT / c['path']).resolve() == path), None)
    if not found or digest(path) != found['sha256']:
        raise ValueError(f'Photo must match this story\'s credited original: {path}')
    if shot.get('photo_source', found['source']) != found['source']:
        raise ValueError('photo_source differs from the verified original')
    return path, found


def photo_html(shot, seconds, *, image=None):
    _, credit = credited_photo(shot)
    # Reuse native dark card, colour rail, fonts, court graphic and footer.
    page = transition_cards.build('真实照片', seconds=seconds, size=SIZE)
    label = LABELS[credit['id']]
    picture = '' if image is None else (
        '<div class="year-photo"><img src="' + _data_uri(image) + '"></div>')
    return page + '''<style>
.wrap,.transition-proof{display:none!important}
.year-photo{position:absolute;left:0;top:250px;width:1080px;height:950px;overflow:hidden}
.year-photo img{display:block;width:1080px;height:950px;object-fit:cover}
.year-label{position:absolute;left:70px;top:177px;width:940px;height:48px;
 color:#c7d5e2;font:700 34px/1.3 'TL Sans SC';white-space:nowrap}
</style>''' + picture + '<div class="year-label">' + html.escape(label) + '</div>'


def screenshot(document, path, *, photo=False, card_plan=None):
    from playwright.sync_api import sync_playwright
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    source = path.with_suffix('.html')
    source.write_text(document)
    with sync_playwright() as pw:
        browser = launch_chromium(pw, args=['--no-sandbox'])
        try:
            page = browser.new_page(viewport={'width': 1080, 'height': 1440}, device_scale_factor=1)
            page.goto(source.as_uri())
            page.evaluate('document.fonts.ready')
            page.wait_for_function('window.transitionMotion || window.transitionMotionError')
            page.wait_for_function('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
            page.evaluate('window.setTransitionTime(6)')
            if photo:
                evidence = page.evaluate('''() => {
                    const e=document.querySelector('.year-label'), r=e.getBoundingClientRect();
                    const p=document.querySelector('.year-photo');
                    return {label:{text:e.innerText,scroll:e.scrollWidth,width:e.clientWidth,
                        top:r.top,bottom:r.bottom}, photo:p?p.getBoundingClientRect().toJSON():null};
                }''')
                if evidence['label']['scroll'] > 940 or evidence['label']['bottom'] > 250:
                    raise ValueError('Date/round label overflows the photo header')
                if evidence['photo'] and evidence['photo']['bottom'] != 1200:
                    raise ValueError('Photo leaves its fixed area')
            else:
                evidence = transition_cards.check_page(page, card_plan)
            page.screenshot(path=str(path), type='png')
            return evidence
        finally:
            browser.close()


def prepare_photo(shot, dest, seconds):
    source, credit = credited_photo(shot)
    focus = shot.get('focus', [.5, .5])
    if len(focus) != 2 or any(not 0 <= float(x) <= 1 for x in focus):
        raise ValueError('focus must contain two fractions in [0,1]')
    # A double-resolution working crop makes the small slow push smooth. Never
    # enlarge the original; every selected photograph can supply this crop.
    with Image.open(source) as original:
        original = ImageOps.exif_transpose(original).convert('RGB')
        scale = max(2160 / original.width, 1900 / original.height)
        if scale > 1:
            raise ValueError('Original cannot supply the 2160x1900 working crop without enlargement')
        work = ImageOps.fit(original, (2160, 1900), Image.Resampling.LANCZOS,
                            centering=tuple(map(float, focus)))
        work.save(dest.with_suffix('.photo.png'))
        still = work.resize(PHOTO, Image.Resampling.LANCZOS)
        still.save(dest.with_suffix('.still.png'))
    evidence = screenshot(photo_html(shot, seconds, image=dest.with_suffix('.still.png')),
                          dest.with_suffix('.png'), photo=True)
    screenshot(photo_html(shot, seconds), dest.with_suffix('.background.png'), photo=True)
    return source, credit, evidence


def render_photo(shot, dest, seconds, *, preview_only=False):
    source, credit, evidence = prepare_photo(shot, dest, seconds)
    if not preview_only:
        # 0.01 / (8s * 25fps) = .00005 per frame; fixed label/footer never zoom.
        graph = ("[1:v]zoompan=z='1+on*0.00005':x='iw/2-iw/zoom/2':"
                 "y='ih/2-ih/zoom/2':d=1:s=1080x950:fps=25[p];"
                 "[0:v][p]overlay=0:250:shortest=1,format=yuv420p[v]")
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-filter_complex_threads', '1',
                        '-loop', '1', '-framerate', '25', '-i', str(dest.with_suffix('.background.png')),
                        '-loop', '1', '-framerate', '25', '-i', str(dest.with_suffix('.photo.png')),
                        '-filter_complex', graph, '-map', '[v]', '-t', str(seconds),
                        '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19',
                        '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(dest)], check=True)
    for suffix in ('.photo.png', '.still.png', '.background.png', '.html', '.background.html'):
        dest.with_suffix(suffix).unlink(missing_ok=True)
    return {'kind': 'photo', 'image': str(source.relative_to(ROOT)),
            'original_sha256': credit['sha256'], 'original_dimensions': credit['dimensions'],
            'source': credit['source'], 'label': LABELS[credit['id']],
            'preview': str(dest.with_suffix('.png')), 'browser_evidence': evidence}


def card_args(shot):
    return {'text': shot.get('native_title', shot.get('title', '')),
            'content': shot.get('native_content'), 'kicker': shot.get('label', '')}


def render_card(shot, dest, seconds, *, preview_only=False):
    args = card_args(shot)
    if preview_only:
        p = transition_cards.plan(**args, size=SIZE)
        screenshot(transition_cards.build(**args, seconds=seconds, size=SIZE),
                   dest.with_suffix('.png'), card_plan=p)
    else:
        transition_cards.render_clip(**args, out=dest, seconds=seconds, fps=FPS, size=SIZE)
    return {'kind': 'card', **args, 'preview': str(dest.with_suffix('.png') if preview_only else dest.with_suffix('.jpg'))}


def render_sequence(index, item, outdir, *, preview_only=False):
    with tempfile.TemporaryDirectory(prefix=f'vacherot-photos-{index}-') as tmp:
        return _render_sequence(index, item, outdir, Path(tmp), preview_only=preview_only)


def _render_sequence(index, item, outdir, workdir, *, preview_only=False):
    seconds = float(item['seconds'])
    duration = math.ceil((seconds + float(item.get('tail_seconds', .56))) * FPS) / FPS
    shots = item['shots']
    if not math.isfinite(duration) or seconds <= 0 or not shots:
        raise ValueError('Positive duration and nonempty shots are required')
    cuts = list(map(float, item.get('cuts', [duration * j / len(shots) for j in range(len(shots))])))
    if len(cuts) == len(shots):
        cuts.append(duration)
    if len(cuts) != len(shots) + 1 or cuts[0] != 0 or abs(cuts[-1] - duration) > .04:
        raise ValueError('cuts must be [0, shot starts..., seconds+tail_seconds]')
    if any(b - a <= FADE for a, b in zip(cuts, cuts[1:])):
        raise ValueError('Every shot must be longer than the .28s dissolve')
    records, parts = [], []
    previews = outdir / 'previews'
    previews.mkdir(parents=True, exist_ok=True)
    for j, shot in enumerate(shots):
        d = cuts[j+1] - cuts[j] + (FADE if j < len(shots)-1 else 0)
        dest = workdir / f'{j:02d}.mp4'
        fn = {'photo': render_photo, 'card': render_card}.get(shot['kind'])
        if fn is None:
            raise ValueError('Only genuine photographs and native fact cards are supported')
        record = fn(shot, dest, d, preview_only=preview_only)
        original_preview = Path(record['preview'])
        preview = previews / f'segment-{index}-shot-{j:02d}{original_preview.suffix}'
        shutil.copyfile(original_preview, preview)
        record['preview'] = str(preview)
        receipt = dest.with_suffix('.transition-render.json')
        if receipt.exists():
            record['native_card_receipt'] = json.loads(receipt.read_text())
        records.append(record)
        parts.append(dest)
    result = {'segment': index, 'seconds': seconds, 'rendered_seconds': duration,
              'cuts': cuts, 'shots': records, 'silent': True, 'canvas': list(SIZE),
              'photo_area': [0, 250, 1080, 950], 'caption_safe_start_y': 1284}
    if not preview_only:
        dest = outdir / f'sequence-{index}.mp4'
        args, filters = [], []
        for j, part in enumerate(parts):
            args += ['-i', str(part)]
            filters.append(f'[{j}:v]setpts=PTS-STARTPTS,fps=25,settb=1/25,format=yuv420p[p{j}]')
        prev = 'p0'
        for j in range(1, len(parts)):
            name = f'x{j}'
            filters.append(f'[{prev}][p{j}]xfade=transition=fade:duration={FADE}:offset={cuts[j]},fps=25[{name}]')
            prev = name
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-filter_complex_threads', '1',
                        *args, '-filter_complex', ';'.join(filters), '-map', f'[{prev}]',
                        '-t', str(duration), '-an', '-c:v', 'libx264', '-preset', 'veryfast',
                        '-crf', '19', '-threads', '2', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', str(dest)], check=True)
        result.update(path=str(dest.relative_to(ROOT)) if dest.is_relative_to(ROOT) else str(dest),
                      sha256=digest(dest))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--outdir', type=Path, default=ASSET / 'sequences')
    parser.add_argument('--only', nargs='*', help='Segment keys to render')
    parser.add_argument('--previews-only', action='store_true')
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    args.outdir.mkdir(parents=True, exist_ok=True)
    records = [render_sequence(key, item, args.outdir, preview_only=args.previews_only)
               for key, item in plan.items() if args.only is None or key in args.only]
    receipt = {'tool_sha256': digest(__file__), 'plan_sha256': digest(args.plan),
               'kind': 'native_layout_preview_only' if args.previews_only else 'silent_visual_inputs',
               'sequences': records, 'publication_approved': False}
    dest = args.outdir / ('preview-receipt.json' if args.previews_only else 'sequences.json')
    dest.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(dest)


if __name__ == '__main__':
    main()
