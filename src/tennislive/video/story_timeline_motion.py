"""Composable, source-labelled calendar → interruption → restart motion.

The story composer supplies fonts, the offline GSAP runtime and one global
clock. This fragment never owns the page background, header, photographs, TTS
or publication. Dates are endpoints, not a synthetic day-by-day match schedule.
"""
from __future__ import annotations

from datetime import date
import html
import json
import math
from typing import Callable

from ..design_tokens import DARK


def _number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"timeline {name} must be a finite number")
    return float(value)


def _text(value, name: str, *, required=True) -> str:
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"timeline {name} must be {'nonempty ' if required else ''}text")
    return value.strip()


def _source(value, name: str) -> str:
    value = _text(value, name)
    if not value.startswith('https://'):
        raise ValueError(f"timeline {name} needs its original HTTPS evidence URL")
    return value


def _json(value) -> str:
    # Safe even when the caller puts this JS in an inline script element.
    return json.dumps(value, ensure_ascii=False).replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')


def validate_block(block: dict) -> dict:
    """Validate/normalize a source-backed timeline block without building HTML.

    Safe for plan dry-run: all object levels reject unknown fields. Returns a
    new normalized block; does not mutate the caller or certify source facts.
    """
    if not isinstance(block, dict) or block.get('kind') != 'timeline':
        raise ValueError('timeline block requires kind=timeline')
    unknown = block.keys() - {'kind', 'start', 'duration', 'events', 'interruption', 'resume_label', 'gap_label', 'summary', 'frame'}
    if unknown:
        raise ValueError(f'timeline unknown block keys: {sorted(unknown)}')
    start = _number(block.get('start'), 'start')
    duration = _number(block.get('duration'), 'duration')
    if start < 0 or duration <= 0:
        raise ValueError('timeline start must be >=0 and duration must be >0')
    frame = block.get('frame', [70, 200, 940, 1000])
    if not isinstance(frame, (list, tuple)) or len(frame) != 4:
        raise ValueError('timeline frame requires x,y,width,height')
    x, y, w, h = [_number(v, 'frame') for v in frame]
    if w <= 0 or h <= 0 or x < 0 or x+w > 1080 or y < 160 or y+h > 1244:
        raise ValueError('timeline frame must fit horizontal canvas and y=160..1244 text area')
    events = block.get('events')
    if not isinstance(events, list) or len(events) != 2:
        raise ValueError('timeline needs exactly two source-backed endpoint events')
    endpoints = []
    for i, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError('timeline endpoint must be an object')
        unknown = event.keys() - {'date', 'calendar', 'label', 'source'}
        if unknown:
            raise ValueError(f'timeline unknown endpoint keys: {sorted(unknown)}')
        iso = _text(event.get('date'), 'event.date')
        try:
            parsed = date.fromisoformat(iso)
        except ValueError as exc:
            raise ValueError('timeline event.date must be a valid ISO YYYY-MM-DD date') from exc
        if parsed.isoformat() != iso:
            raise ValueError('timeline event.date must use ISO YYYY-MM-DD')
        calendar = event.get('calendar', {})
        if not isinstance(calendar, dict) or calendar.keys() - {'month', 'day'}:
            raise ValueError('timeline calendar supports month and day only')
        month = _text(calendar.get('month', parsed.strftime('%Y.%m')), 'calendar.month')
        day = str(calendar.get('day', parsed.day))
        if not day.isdigit() or int(day) != parsed.day:
            raise ValueError('calendar.day disagrees with event.date')
        endpoints.append({'date': iso, 'calendar': {'month': month, 'day': day},
                          'label': _text(event.get('label'), 'event.label'),
                          'source': _source(event.get('source'), 'event.source')})
    if endpoints[0]['date'] >= endpoints[1]['date']:
        raise ValueError('timeline end date must follow its start date')
    interruption = block.get('interruption')
    if interruption is not None:
        if not isinstance(interruption, dict):
            raise ValueError('timeline interruption must contain label and source')
        unknown = interruption.keys() - {'label', 'detail', 'source'}
        if unknown:
            raise ValueError(f'timeline unknown interruption keys: {sorted(unknown)}')
        interruption = {'label': _text(interruption.get('label'), 'interruption.label'),
                        'detail': _text(interruption.get('detail', ''), 'interruption.detail', required=False),
                        'source': _source(interruption.get('source'), 'interruption.source')}
    resume = _text(block.get('resume_label', ''), 'resume_label', required=False)
    if len(resume.splitlines()) > 2:
        raise ValueError('timeline resume_label supports at most two deliberate lines')
    gap = _text(block.get('gap_label', ''), 'gap_label', required=False)
    summary = block.get('summary', [])
    if isinstance(summary, str):
        summary = summary.splitlines()
    if not isinstance(summary, list) or len(summary) > 2:
        raise ValueError('timeline summary supports at most two deliberate lines')
    summary = [_text(line, 'summary line') for line in summary]
    return {'kind': 'timeline', 'start': start, 'duration': duration, 'frame': [x,y,w,h],
            'events': endpoints, 'interruption': interruption, 'resume_label': resume,
            'gap_label': gap, 'summary': summary}


def timeline_blocks_html(block: dict, index: int, asset_uri: Callable) -> tuple[str, str, str]:
    """Return (HTML, scoped CSS, installation JS) for one timeline block.

    Required block: ``kind='timeline', start>=0, duration>0, events=[a,b]``.
    Each endpoint has an ISO ``date``, ``label`` and original ``source`` URL.
    Optional ``calendar={month,day}`` controls its display; day must agree with
    the supplied date. No intermediate dates or tournament results are inferred.
    Optional ``interruption={label,detail?,source}``, ``resume_label`` (up to two
    lines), ``gap_label``, ``summary`` (text or up to two text lines), and
    ``frame=[x,y,width,height]`` compose freely with other story blocks.

    Default frame is [70,200,940,1000]. It must remain inside x=0..1080 and
    y=160..1244. All content is clipped to that frame; text carries
    ``data-story-text`` for the composer's native geometry/overflow checks.
    ``asset_uri`` is accepted for the shared block interface, but this original
    diagram uses no raster assets.

    Run returned JS inside the composer's fonts.ready callback, after HTML is
    inserted and GSAP is available. It registers a global-time function in
    window.storyRenderers and retains endpoint evidence verbatim in
    window.storyTimelineMetadata. Its private paused timeline maps arbitrary
    duration to the eight-unit design clock and supports backward seeking.
    Evidence provenance is caller supplied; rendering does not certify facts.
    """
    del asset_uri
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise ValueError('timeline index must be a nonnegative integer')
    validated = validate_block(block)
    start, duration = validated['start'], validated['duration']
    frame = validated['frame']
    x, y, w, h = frame
    endpoints, interruption = validated['events'], validated['interruption']
    resume, gap, summary = validated['resume_label'], validated['gap_label'], validated['summary']
    name = f'story-timeline-{index}'
    scope = f'#{name}'
    e = html.escape
    def lines(text):
        return '<br>'.join(e(line) for line in text.splitlines())
    def page(event, role):
        return (f'<div class="stm-page stm-{role}" data-source="{e(event["source"], quote=True)}">'
                f'<div class="stm-month" data-story-text>{e(event["calendar"]["month"])}</div>'
                f'<div class="stm-day" data-story-text>{e(event["calendar"]["day"])}</div>'
                f'<div class="stm-label" data-story-text>{e(event["label"])}</div></div>')
    missing = (f'<div class="stm-interruption"><div class="stm-missing-label" data-story-text>{e(interruption["label"])}</div>'
               f'<div class="stm-detail" data-story-text>{e(interruption["detail"])}</div></div>') if interruption else '<div class="stm-interruption"></div>'
    markup = (f'<section id="{name}" class="story-timeline-component" data-story-component="timeline" '
              f'data-story-start="{start}" data-story-duration="{duration}" aria-label="{e(gap or resume or "timeline")}" '
              f'style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;visibility:hidden">'
              f'<div class="stm-design" style="transform:scale({min(w/1000,h/1000)});">'
              '<svg class="stm-stage" viewBox="0 0 1000 1000" aria-hidden="true">'
              '<path class="stm-court" d="M30 800 L280 500 L720 500 L970 800 Z M130 680 L870 680 M500 500 L500 800"/>'
              '<path class="stm-before" d="M30 680H405"/><path class="stm-after" d="M595 680H970"/>'
              '<path class="stm-bridge" d="M405 680H595"/>'
              '<g class="stm-ball"><circle r="22"/><path d="M-13-17Q12 0-13 17M13-17Q-12 0 13 17"/></g>'
              '<g class="stm-break"><path d="M470 656L451 704M526 656L507 704"/></g></svg>'
              '<div class="stm-calendar">'+page(endpoints[1], 'end')+page(endpoints[0], 'start')+'</div>'
              +missing+f'<div class="stm-gap" data-story-text>{e(gap)}</div>'
              +f'<div class="stm-resume" data-story-text>{lines(resume)}</div>'
              +'<div class="stm-summary">'+''.join(f'<div data-story-text>{e(line)}</div>' for line in summary)+'</div>'
              '</div></section>')
    foreground, muted, primary = DARK['foreground'], DARK['muted-foreground'], DARK['primary']
    css = f'''
{scope}{{position:absolute;overflow:hidden;pointer-events:none;color:{foreground};font-family:'TL Sans SC',sans-serif}}
{scope} *{{box-sizing:border-box}}
{scope} .stm-design{{position:absolute;left:0;top:0;width:1000px;height:1000px;transform-origin:0 0}}
{scope} .stm-stage{{position:absolute;inset:0;width:1000px;height:1000px;fill:none}}
{scope} .stm-court{{stroke:#51758f;stroke-width:2.5;opacity:.35}}
{scope} .stm-before,{scope} .stm-after,{scope} .stm-bridge{{stroke:#72a5bc;stroke-width:4;stroke-linecap:round}}
{scope} .stm-after,{scope} .stm-bridge{{stroke:{primary}}}
{scope} .stm-ball circle{{fill:{primary}}}{scope} .stm-ball path{{stroke:#f0ffc0;stroke-width:3}}
{scope} .stm-break path{{stroke:#9eb0bf;stroke-width:5}}
{scope} .stm-calendar{{position:absolute;left:0;top:50px;width:550px;height:475px;perspective:1400px}}
{scope} .stm-page{{position:absolute;inset:0;transform-origin:50% 0;backface-visibility:hidden;background:linear-gradient(140deg,#1b3a58,#10263c);border:1px solid #6b93af65;padding:32px 38px;box-shadow:0 24px 50px #0003}}
{scope} .stm-page:before,{scope} .stm-page:after{{content:'';position:absolute;top:-14px;width:9px;height:40px;background:#90a9bd;border-radius:4px}}
{scope} .stm-page:before{{left:64px}}{scope} .stm-page:after{{right:64px}}
{scope} .stm-month{{font-family:'TL Numeral','TL Sans SC';font-size:40px;line-height:1.3;letter-spacing:3px;padding-bottom:15px;border-bottom:1px solid #b4d1e33b;white-space:nowrap}}
{scope} .stm-day{{font-family:'TL Numeral','TL Sans SC';font-size:220px;line-height:1.1;letter-spacing:-7px;white-space:nowrap}}
{scope} .stm-label{{font-size:36px;line-height:1.4;white-space:nowrap}}
{scope} .stm-end .stm-month,{scope} .stm-end .stm-day{{color:{primary}}}
{scope} .stm-interruption{{position:absolute;left:640px;top:145px;width:355px;padding-left:24px;border-left:2px solid #7388a352}}
{scope} .stm-missing-label{{font-family:'TL Display SC';font-size:63px;line-height:1.25;white-space:nowrap}}
{scope} .stm-detail{{font-size:30px;line-height:1.6;color:{muted};margin-top:25px}}
{scope} .stm-gap{{position:absolute;left:340px;top:735px;width:320px;text-align:center;color:{muted};font-size:31px;line-height:1.4;white-space:nowrap}}
{scope} .stm-resume{{position:absolute;left:640px;top:130px;width:355px;font-family:'TL Display SC';font-size:76px;line-height:1.25;color:{primary};white-space:nowrap}}
{scope} .stm-summary{{position:absolute;left:0;top:840px;right:0;font-family:'TL Display SC';font-size:56px;line-height:1.35}}
{scope} .stm-summary>div:last-child{{color:{primary}}}
{scope} .stm-summary>div{{white-space:nowrap}}
'''
    metadata = {'kind': 'calendar_break_restart', 'component_id': name, 'start': start, 'duration': duration,
                'frame': list(frame), 'events': endpoints, 'interruption': interruption,
                'gap_label': gap, 'resume_label': resume, 'summary': summary,
                'evidence_status': 'caller_supplied_source_urls_not_independently_certified',
                'timeline_semantics': 'two dated endpoints and a labelled gap; no generated intermediate events',
                'clock': 'global seconds mapped to a private paused eight-unit GSAP timeline'}
    js = r'''
(()=>{
const d=__DATA__,root=document.getElementById(d.component_id);
if(!root||typeof gsap==='undefined')throw Error('timeline requires mounted DOM and offline GSAP');
const q=s=>root.querySelector(s),many=s=>Array.from(root.querySelectorAll(s));
const tl=gsap.timeline({paused:true});
gsap.set(many('.stm-end,.stm-interruption,.stm-resume,.stm-summary,.stm-gap,.stm-break,.stm-before,.stm-after,.stm-bridge'),{opacity:0});
gsap.set(q('.stm-ball'),{x:30,y:800,opacity:0,svgOrigin:'0 0'});
gsap.set(q('.stm-calendar'),{rotation:-4,y:35,opacity:0});
tl.to(q('.stm-calendar'),{y:0,opacity:1,rotation:0,duration:.72,ease:'power3.out'},.2);
tl.to(q('.stm-court'),{attr:{d:'M30 680 L405 680 L595 680 L970 680 Z M30 680 L970 680 M500 680 L500 680'},opacity:.55,duration:1.05,ease:'power2.inOut'},1.25);
tl.to(q('.stm-before'),{opacity:1,duration:.4},1.9);
tl.to(q('.stm-ball'),{x:30,y:680,opacity:1,duration:.35},1.55);
tl.to(q('.stm-ball'),{x:405,rotation:280,duration:1.12,ease:'power2.out'},1.8);
tl.to(many('.stm-gap,.stm-break'),{opacity:1,duration:.45},2.3);
tl.fromTo(q('.stm-interruption'),{x:40,opacity:0},{x:0,opacity:1,duration:.65,ease:'power2.out'},2.55);
tl.to(q('.stm-start'),{rotationX:-19,y:-20,opacity:.43,duration:.65,ease:'power2.inOut'},2.8);
tl.to(q('.stm-ball'),{scale:.85,duration:.55,ease:'sine.inOut'},3.05);
tl.to(q('.stm-ball'),{scale:1,duration:.55,ease:'sine.inOut'},3.6);
tl.to(q('.stm-interruption'),{x:30,opacity:0,duration:.5},4.25);
tl.to(q('.stm-start'),{rotationX:-100,y:-20,opacity:0,duration:.8,ease:'power2.in'},4.3);
tl.fromTo(q('.stm-end'),{rotationX:15,y:30,opacity:0},{rotationX:0,y:0,opacity:1,duration:.75,ease:'power2.out'},4.45);
tl.to(q('.stm-after'),{opacity:1,duration:.5},4.7);
tl.to(many('.stm-gap,.stm-break'),{opacity:0,duration:.48},4.75);
tl.to(q('.stm-bridge'),{opacity:1,duration:.48},4.75);
tl.to(q('.stm-ball'),{x:945,rotation:650,duration:1.1,ease:'power2.inOut'},4.85);
tl.fromTo(q('.stm-resume'),{x:25,opacity:0},{x:0,opacity:1,duration:.55,ease:'power2.out'},4.9);
tl.fromTo(q('.stm-summary'),{y:16,opacity:0},{y:0,opacity:1,duration:.55,ease:'power2.out'},4.95);
const render=t=>{t=Number(t);if(!Number.isFinite(t))throw Error('timeline clock must be finite');const local=Math.max(0,Math.min(8,(t-d.start)*8/d.duration));tl.seek(local,false);root.style.visibility=t>=d.start&&t<d.start+d.duration?'visible':'hidden';gsap.ticker.sleep();};
window.storyRenderers=window.storyRenderers||[];window.storyRenderers.push(render);
window.storyTimelineMetadata=window.storyTimelineMetadata||[];window.storyTimelineMetadata.push(d);
render(-1);
})();
'''.replace('__DATA__', _json(metadata))
    return markup, css, js
