"""Editorial story layouts: authentic photos and PDF crops; provenance stays in records."""
from __future__ import annotations

import html
from pathlib import Path


def source_slide_html(segment, *, index, height, topic, column, root: Path,
                      font_css: str, asset_uri) -> str:
    """One conclusion, one supporting context and a closely grouped real source."""
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
    headline = visual.get('headline', segment.title)
    title = '<br>'.join(esc(line) for line in headline.splitlines())
    context = esc(visual.get('context', visual.get('kicker', '')))
    caption = esc(visual.get('caption', ''))
    takeaway = esc(visual.get('takeaway', visual.get('focus', '')))
    icon = img('assets/logo/brand/icon.png', 'brand-icon')
    if layout == 'rule':
        rows = []
        for quote in visual.get('quotes', []):
            rows.append('<div class="quote-row"><div class="original">'
                        + img(quote['asset']) + '</div><div class="meaning">'
                        + esc(quote['meaning']).replace('\n', '<br>') + '</div></div>')
        evidence = '<div class="quotes">' + ''.join(rows) + '</div>'
        if visual.get('photo'):
            photo_caption = f'<figcaption>{caption}</figcaption>' if caption else ''
            evidence = ('<div class="rule-visual">' + img(visual['photo'], 'photo')
                        + photo_caption + '</div>' + evidence)
            caption = ''
        elif visual.get('graphic'):
            from .story_rule_graphics import rule_graphic_html
            evidence = rule_graphic_html(visual['graphic']) + evidence
    else:
        evidence = img(visual['photo'], 'photo')
    compact = 'compact' if layout == 'rule' and len(visual.get('quotes', [])) < 3 else ''
    illustrated = 'illustrated' if layout == 'rule' and (visual.get('photo') or visual.get('graphic')) else ''
    dense = 'dense' if layout == 'rule' and len(visual.get('quotes', [])) >= 3 else ''
    figcaption = f'<figcaption>{caption}</figcaption>' if caption else ''
    support = f'<p class="support">{takeaway}</p>' if takeaway else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>{font_css}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:1080px;height:{height}px;overflow:hidden}}
body{{font-family:'TL Sans SC','Noto Sans CJK SC',sans-serif;background:#071322;color:#edf1f5}}
.scene{{position:relative;height:{height}px;overflow:hidden;background:linear-gradient(160deg,#0c1c2d,#071322 58%)}}
.spectrum{{height:7px;background:linear-gradient(90deg,#c9f45e,#2ee3a5,#d67d91,#5eacf6)}}
.brand{{position:absolute;top:43px;left:70px;display:flex;align-items:center;gap:18px}}
.brand-icon{{width:52px;height:52px}}
.brand-name{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:38px;font-weight:400;letter-spacing:1px}}
.topic{{display:block;font-size:27px;font-weight:700;margin-top:2px;color:#c1ccd6;letter-spacing:1px}}
.content{{position:absolute;top:212px;left:70px;right:70px;bottom:250px;display:flex;flex-direction:column;gap:28px}}
.lead{{flex:none}}
.headline{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:60px;font-weight:400;line-height:1.2;letter-spacing:1px}}
.context{{font-size:28px;font-weight:400;line-height:1.5;color:#aebccc;margin-top:18px}}
.evidence{{flex:none;display:flex;flex-direction:column;align-items:center;gap:20px}}
.photo{{display:block;width:auto;height:auto;max-width:100%;max-height:550px;object-fit:contain}}
figcaption{{width:100%;font-size:28px;font-weight:400;line-height:1.5;color:#aebccc}}
.support{{flex:none;font-size:32px;font-weight:400;line-height:1.5;color:#d2dde5}}
.rule .evidence{{margin-top:48px}}
.rule.compact .evidence{{margin-top:96px}}
.quotes{{width:100%}}
.quote-row{{display:grid;grid-template-columns:1.12fr 1fr;align-items:center;gap:48px;padding:30px 0}}
.quote-row + .quote-row{{border-top:1px solid #aebccc26}}
.original{{display:flex;align-items:center;justify-content:flex-start;min-width:0}}
.original img{{display:block;height:44px;width:auto;max-width:100%;object-fit:contain;object-position:left center;filter:invert(1);mix-blend-mode:screen}}
.meaning{{font-size:34px;font-weight:400;line-height:1.65;color:#d2dde5}}
.rule.table .original img{{height:168px;max-height:none}}
.rule.table .meaning{{line-height:56px}}
.rule.illustrated .evidence{{margin-top:0;gap:20px}}
.rule-visual{{display:flex;flex-direction:column;align-items:center;gap:12px;width:100%}}
.rule-visual .photo{{max-height:300px}}
.rule.dense .rule-visual .photo{{max-height:260px}}
.rule.illustrated .quote-row{{padding:14px 0}}
.rule.illustrated .original img{{height:36px}}
.rule.illustrated .meaning{{font-size:30px;line-height:1.4}}
.rule.illustrated.table .original img{{height:144px}}
.rule.illustrated.table .meaning{{line-height:48px}}
</style></head><body><main class="scene {esc(layout)} {esc(visual.get('variant',''))} {compact} {illustrated} {dense}">
<div class="spectrum"></div><div class="brand">{icon}<div><div class="brand-name">网球时差 · {esc(column)}</div><span class="topic">{esc(topic)}</span></div></div>
<section class="content"><header class="lead"><h1 class="headline">{title}</h1><p class="context">{context}</p></header>
<figure class="evidence">{evidence}{figcaption}</figure>{support}</section>
</main></body></html>'''


def focus_narration_subtitles(path: Path) -> None:
    """Keep narration readable in its own quiet footer; preserve every cue and time."""
    import re

    text = path.read_text(encoding='utf-8')
    lines = []
    for line in text.splitlines():
        if line.startswith('Style: TL,'):
            fields = line.split(',')
            fields[2] = '60'
            fields[3] = '&H00E5DDD2'
            fields[7] = '0'
            fields[16] = '1'
            fields[17] = '0'
            line = ','.join(fields)
        elif line.startswith('Dialogue:'):
            line = re.sub(r'\\fs(?:68|78)\b', r'\\fs60', line)
        lines.append(line)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


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
    """Two transparent editorial lines, with a fine rule on the right."""
    from playwright.sync_api import sync_playwright
    from ..render.webcards import _font_css
    from ..chromium import launch_chromium

    title = html.escape(annotation['title'])
    detail = html.escape(annotation['detail'])
    shadow = ("text-shadow:0 1px 3px #071322,0 0 1px #071322;"
              "-webkit-text-stroke:.5px #071322;"
              if annotation.get('position') == 'top-right' else '')
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:180px;background:transparent;color:#e8edf1}}
.card{{position:absolute;top:38px;right:96px;text-align:right;{shadow}}}
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
            position = annotation.get('position', 'bottom')
            if position not in {'bottom', 'top-right'}:
                raise E.ExplainerVideoError('原声说明字卡位置只支持bottom或top-right')
            annotation_y = 150 if position == 'top-right' else canvas_h - 180
            phases = annotation.get('phases', [annotation])
            for phase_index, phase in enumerate(phases):
                image = _render_source_annotation({**annotation, **phase},
                                                   badge_dir / f'annotation_{phase_index}')
                enable = _annotation_enable(subtitles, end - start, phase)
                extra_inputs.extend(['-loop', '1', '-i', str(image)])
                label = f'annotation{phase_index}'
                graph += (f";[{current}][{phase_index + 2}:v]overlay=0:{annotation_y}:"
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
