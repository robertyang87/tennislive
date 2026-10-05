"""Editorial story layouts: authentic photos and PDF crops; provenance stays in records."""
from __future__ import annotations

import html
from pathlib import Path


def source_slide_html(segment, *, index, height, topic, column, root: Path,
                      font_css: str, asset_uri) -> str:
    from PIL import Image

    visual = segment.visual
    layout = visual['layout']
    if layout not in {'incident', 'case', 'rule', 'closing'}:
        raise ValueError(f'Unknown source-story layout: {layout}')

    def img(asset: str, cls: str = '') -> str:
        path = root / asset
        with Image.open(path) as probe:
            probe.verify()
        return f'<img class="{cls}" src="{asset_uri(path)}" alt="{html.escape(asset)}">'

    esc = html.escape
    photo = img(visual['photo'], 'photo') if visual.get('photo') else ''
    quote_rows = []
    for quote in visual.get('quotes', []):
        quote_rows.append('<div class="quote-row"><div class="original">'
                          + img(quote['asset']) + '</div><div class="meaning">'
                          + esc(quote['meaning']) + '</div></div>')
    quotes = '<div class="quotes">' + ''.join(quote_rows) + '</div>' if quote_rows else ''
    title = '<br>'.join(f'<span class="turn">{esc(line)}</span>' if i else esc(line)
                       for i, line in enumerate(segment.title.splitlines()))
    notes = ''.join(f'<p>{esc(line)}</p>' for line in visual.get('notes', []))
    icon = img('assets/logo/brand/icon.png', 'brand-icon')
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>{font_css}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:1080px;height:{height}px;overflow:hidden}}
body{{font-family:'TL Sans SC','Noto Sans CJK SC','Noto Sans SC',sans-serif;background:#071322;color:#f5f3ed}}
.scene{{position:relative;height:{height}px;overflow:hidden;background:linear-gradient(160deg,#102b43,#081322 68%)}}
.spectrum{{height:7px;background:linear-gradient(90deg,#c9f45e,#2ee3a5,#d67d91,#5eacf6)}}
.brand{{position:absolute;top:43px;left:70px;display:flex;align-items:center;gap:18px}}
.brand-icon{{width:52px;height:52px}}
.brand-name{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:38px;font-weight:400;letter-spacing:1px}}
.topic{{display:block;font-family:'TL Sans SC',sans-serif;font-size:27px;font-weight:700;margin-top:2px;color:#c1ccd6;letter-spacing:1px}}
.chapter{{position:absolute;left:70px;top:163px;font-size:22px;letter-spacing:2px;color:#e8edf1}}
.scene-index{{position:absolute;right:70px;top:163px;font-family:'TL Score',sans-serif;font-size:23px;color:#8f9daa;letter-spacing:2px}}
.kicker{{position:absolute;left:70px;top:220px;font-size:24px;color:#d4dde5;letter-spacing:1px}}
.scene::before{{content:'';position:absolute;left:70px;right:70px;top:137px;border-top:1px solid #8093a333}}
.photo{{position:absolute;top:285px;left:0;width:1080px;height:730px;object-fit:contain}}
.headline{{position:absolute;left:70px;right:70px;top:1040px;font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:56px;font-weight:400;line-height:1.14;letter-spacing:1px}}
.turn{{color:#e8edf1}}
.focus{{position:absolute;left:70px;top:1200px;font-size:28px;font-weight:400;color:#e8edf1}}
.source{{position:absolute;left:70px;right:70px;top:1190px;font-size:21px;line-height:1.5;color:#a8b7c7}}
.source::before{{content:'';display:block;width:110px;border-top:2px solid #c9f45e;margin-bottom:13px}}
 .year{{position:absolute;right:70px;top:215px;font-size:38px;line-height:1;font-weight:400;color:#b1bdc7;font-family:'TL Score',sans-serif;letter-spacing:1px}}
.notes{{position:absolute;left:70px;right:70px;top:1085px;font-size:31px;line-height:1.6}}
.rule .headline{{top:243px;font-size:56px}}
.rule .kicker{{top:210px;font-size:22px}}
.rule .year{{display:none}}
.rule .quotes{{position:absolute;left:70px;right:70px;top:475px}}
.quote-row{{display:flex;align-items:center;gap:35px;min-height:145px;margin-bottom:18px;border-bottom:1px solid #d5e1ed22;padding-bottom:18px}}
.original{{background:transparent;flex:0 0 565px;padding:10px 0;display:flex;justify-content:center;align-items:center}}
.original img{{filter:invert(1);mix-blend-mode:screen;display:block;max-width:100%;max-height:82px;width:auto;height:auto}}
.meaning{{font-size:30px;font-weight:400;line-height:1.2;color:#e8edf1}}
.rule .focus{{top:1055px;font-size:28px}}
.rule .notes{{top:1110px;font-size:27px;color:#d5dde5}}
.rule .source{{top:1200px}}
.rule.table .original img{{max-height:360px;width:540px}}
.rule.table .quote-row{{min-height:410px}}
.rule.table .meaning{{white-space:pre-line;font-size:30px;line-height:2.7}}
.incident .photo{{top:285px;height:730px}}
.incident .focus{{font-size:28px}}
.closing .photo{{top:285px;height:730px}}
.closing .headline{{top:1040px;font-size:56px}}
.case .photo{{top:285px;height:730px}}
</style></head><body><main class="scene {esc(layout)} {esc(visual.get('variant',''))}">
<div class="spectrum"></div><div class="brand">{icon}<div><div class="brand-name">网球时差 · {esc(column)}</div><span class="topic">{esc(topic)}</span></div></div>
<div class="chapter">{esc(visual.get('chapter',''))}</div><div class="scene-index">{("① " if index == 1 else f"{index:02d}")}</div>
<div class="kicker">{esc(visual.get('kicker',''))}</div><div class="year">{esc(visual.get('year',''))}</div>
{photo}<h1 class="headline">{title}</h1>{quotes}
<div class="focus">{esc(visual.get('focus',''))}</div><div class="notes">{notes}</div>
</main></body></html>'''


def _subtitle_intervals(path: Path) -> list[tuple[float, float]]:
    """Read actual ASS events in both languages for caption-safe overlays."""
    def seconds(value: str) -> float:
        hours, minutes, sec = value.strip().split(':')
        return int(hours) * 3600 + int(minutes) * 60 + float(sec)

    fields = []
    intervals = []
    in_events = False
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if line.startswith('['):
            in_events = line.lower() == '[events]'
        elif in_events and line.startswith('Format:'):
            fields = [field.strip().lower() for field in line.split(':', 1)[1].split(',')]
        elif in_events and line.startswith('Dialogue:'):
            event = dict(zip(fields, line.split(':', 1)[1].split(',', len(fields) - 1)))
            start, end = seconds(event['start']), seconds(event['end'])
            if start < end:
                intervals.append((start, end))
    return sorted(set(intervals))


def _annotation_enable(subtitles: Path, duration: float, annotation: dict) -> str:
    """Place annotation phases in usable gaps between actual ASS captions."""
    start = max(0.0, float(annotation.get('start', 0)))
    end = min(duration, float(annotation.get('end', duration)))
    windows = []
    cursor = start
    for caption_start, caption_end in _subtitle_intervals(subtitles):
        caption_start, caption_end = caption_start - .12, caption_end + .12
        if caption_end <= cursor or caption_start >= end:
            continue
        if caption_start - cursor >= .6:
            windows.append((cursor, min(caption_start, end)))
        cursor = max(cursor, caption_end)
    if end - cursor >= .6:
        windows.append((cursor, end))
    return '+'.join(f'gte(t,{a:.3f})*lt(t,{b:.3f})' for a, b in windows) or '0'


def _render_source_annotation(annotation: dict, outdir: Path) -> Path:
    """Two editorial lines below the original frame, with a fine rule on the right."""
    from playwright.sync_api import sync_playwright
    from ..render.webcards import _font_css
    from ..chromium import launch_chromium

    title = html.escape(annotation['title'])
    detail = html.escape(annotation['detail'])
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:180px;background:transparent;color:#e8edf1}}
.card{{position:absolute;top:38px;right:96px;text-align:right}}
.title{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:40px;font-weight:400;line-height:1.35;letter-spacing:1px}}
.detail{{font-family:'TL Sans SC',sans-serif;font-size:32px;font-weight:400;line-height:1.55;letter-spacing:1px;color:#c1ccd6;margin-top:4px}}
.rule{{position:absolute;right:68px;top:42px;height:96px;width:3px;background:#c9f45e}}
</style></head><body><div class="card"><div class="title">{title}</div><div class="detail">{detail}</div></div><div class="rule"></div></body></html>"""
    outdir.mkdir(parents=True, exist_ok=True)
    output = outdir / '_source_annotation.png'
    with sync_playwright() as p:
        browser = launch_chromium(p)
        try:
            page = browser.new_page(viewport={'width': 1080, 'height': 180},
                                    device_scale_factor=1)
            try:
                page.set_content(doc)
                page.wait_for_function("document.fonts.status === 'loaded'", timeout=15000)
                if page.locator('.card').bounding_box()['width'] > 840:
                    raise ValueError('原声说明字卡过长，请缩短文字')
                page.screenshot(path=str(output), type='png', omit_background=True)
            finally:
                page.close()
        finally:
            browser.close()
    return output


def prepare_source_inserts(specs, temp_dir: Path, canvas_h: int) -> dict[int, Path]:
    """Cut official sources with native sound and caption-safe editorial annotations."""
    import math
    import subprocess
    import requests
    from . import explainer as E

    result = {}
    for spec in specs:
        index = spec['before_slide']
        if index in result:
            raise E.ExplainerVideoError('同一屏之前不能重复声明原声片段')
        start, end = float(spec['start']), float(spec['end'])
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
            raise E.ExplainerVideoError('原声插段时间区间不合法')
        subtitles = E._REPO / spec['subtitles']
        if not subtitles.is_file():
            raise E.ExplainerVideoError(f'原声插段字幕找不到：{subtitles}')
        source = temp_dir / f'source_{index}.mp4'
        with requests.get(spec['url'], stream=True, timeout=(15, 180)) as response:
            response.raise_for_status()
            with source.open('wb') as handle:
                for chunk in response.iter_content(1024 * 1024):
                    handle.write(chunk)
        if source.stat().st_size < 1024:
            raise E.ExplainerVideoError('原声源文件异常小')
        badge_dir = temp_dir / f'badge_{index}'
        badge_dir.mkdir(exist_ok=True)
        badge = E._render_intro_badge(spec['topic'], E.DEFAULT_COLUMN, badge_dir)
        if badge is None:
            raise E.ExplainerVideoError('原声插段台头渲染失败')
        if spec.get('fit') != 'original':
            raise E.ExplainerVideoError('证据插段必须保留原幅：fit=original')
        frame = ''
        if spec.get('remove_logo_bbox') is not None:
            frame = E._platform_logo_filter(spec['remove_logo_bbox']) + ','
        frame += (f'scale=1080:{canvas_h}:force_original_aspect_ratio=decrease:flags=lanczos,'
                  f'pad=1080:{canvas_h}:(ow-iw)/2:(oh-ih)/2:color=0x071322,setsar=1,fps=30')
        frame += (f",subtitles='{E._filter_path(subtitles)}'"
                  f":fontsdir='{E._filter_path(E._ASS_EN_FONT_FILE.parent)}'")
        output = temp_dir / f'insert_{index}.mp4'
        graph = f'[0:v]{frame}[base];[base][1:v]overlay=0:0:shortest=1:format=auto[branded]'
        extra_inputs = []
        current = 'branded'
        annotation = spec.get('annotation')
        if annotation:
            phases = annotation.get('phases', [annotation])
            for phase_index, phase in enumerate(phases):
                image = _render_source_annotation(phase, badge_dir / f'annotation_{phase_index}')
                enable = _annotation_enable(subtitles, end - start, phase)
                extra_inputs.extend(['-loop', '1', '-i', str(image)])
                label = f'annotation{phase_index}'
                graph += (f";[{current}][{phase_index + 2}:v]overlay=0:{canvas_h - 180}:"
                          f"shortest=1:format=auto:enable='{enable}'[{label}]")
                current = label
        graph += f';[{current}]null[v]'
        subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                        '-ss', str(start), '-t', str(end-start), '-i', str(source),
                        '-loop', '1', '-i', str(badge), *extra_inputs,
                        '-filter_complex', graph, '-map', '[v]', '-map', '0:a',
                        '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-ar', '24000', '-ac', '1', '-b:a', '96k',
                        '-movflags', '+faststart', str(output)],
                       check=True, capture_output=True)
        result[index] = output
    return result
