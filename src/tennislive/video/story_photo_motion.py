"""Composable magazine-photo motion, driven only by the caller's film clock.

``photo_blocks_html`` returns body HTML, CSS and registration JavaScript. The
caller supplies native fonts, branding, asset resolution and the master clock;
run the JS after fonts are ready, then call each ``window.storyRenderers``
function with the same absolute film time. No video, facts, files or clocks are
created here. Source strings remain metadata rather than visible footnotes.

Block: start, duration, pages; optional frame=[x,y,w,h], label_y, copy_y,
transition, label_font_size, date_font_size, kicker_font_size, headline_font_size.
Label/copy y coordinates are absolute canvas coordinates. Page: path, source,
date, event; optional headline, kicker, focus=[x,y], start, duration. Page times
are relative to the block. Omit every page start to distribute pages equally,
or provide every start in strictly increasing order. A shorter page duration
creates a transparent gap. The default photo frame preserves brand/subtitles.
"""
from __future__ import annotations

import html
import json
import math
from collections.abc import Callable

from ..design_tokens import DARK


def _number(value, name: str, *, minimum=None, maximum=None) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


def _string(value, name: str, *, required=True) -> str:
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"{name} must be {'a nonempty' if required else 'a'} string")
    if any(ord(c) < 32 for c in value):
        raise ValueError(f"{name} must be a single line without control characters")
    return value.strip()


def validate_block(block: dict) -> dict:
    """Return detached, normalized configuration; reject ambiguous page timing."""
    keys = {"start", "duration", "pages", "frame", "label_y", "copy_y", "transition",
            "label_font_size", "date_font_size", "kicker_font_size", "headline_font_size"}
    if not isinstance(block, dict) or block.keys() - keys:
        raise ValueError("photo block has unsupported fields")
    start = _number(block.get("start"), "start", minimum=0)
    duration = _number(block.get("duration"), "duration", minimum=.04)
    frame = block.get("frame", [0, 180, 1080, 1000])
    if not isinstance(frame, (list, tuple)) or len(frame) != 4:
        raise ValueError("frame must be [x,y,width,height]")
    x, y, w, h = [_number(v, "frame", minimum=0) for v in frame]
    if w < 540 or h < 640 or x + w > 1080 or y + h > 1440:
        raise ValueError("photo frame must fit the 1080x1440 canvas and be at least 540x640")
    label_y = _number(block.get("label_y", y + h * 862 / 1440), "label_y", minimum=y)
    copy_y = _number(block.get("copy_y", max(y + h * 955 / 1440, label_y + 90)), "copy_y", minimum=y)
    if label_y + 76 > copy_y or copy_y + 230 > y + h:
        raise ValueError("label/copy geometry does not fit the photo frame")
    transition = _number(block.get("transition", .3), "transition", minimum=0, maximum=1)
    sizes = {key: _number(block.get(key, default), key, minimum=16, maximum=180)
             for key, default in (("label_font_size", 31), ("date_font_size", 42),
                                  ("kicker_font_size", 98), ("headline_font_size", 80))}
    pages = block.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("pages must be a nonempty list")
    page_keys = {"path", "source", "date", "event", "headline", "kicker", "focus", "start", "duration"}
    if any(not isinstance(p, dict) or p.keys() - page_keys for p in pages):
        raise ValueError("photo page has unsupported fields")
    explicit = ["start" in p for p in pages]
    if any(explicit) and not all(explicit):
        raise ValueError("provide all page starts or omit all page starts")
    starts = [_number(p["start"], "page.start", minimum=0) if all(explicit)
              else i * duration / len(pages) for i, p in enumerate(pages)]
    if any(b <= a for a, b in zip(starts, starts[1:])) or starts[-1] >= duration:
        raise ValueError("page starts must increase within the block")
    normalized = []
    for i, page in enumerate(pages):
        end_limit = starts[i + 1] if i + 1 < len(pages) else duration
        seconds = _number(page.get("duration", end_limit - starts[i]), "page.duration", minimum=.04)
        if starts[i] + seconds > end_limit + 1e-8:
            raise ValueError("photo pages must not overlap or exceed block duration")
        focus = page.get("focus", [.5, .5])
        if not isinstance(focus, (list, tuple)) or len(focus) != 2:
            raise ValueError("focus must be [x,y] fractions")
        normalized.append({**{key: _string(page.get(key), "page." + key)
                             for key in ("path", "source", "date", "event")},
                           **{key: _string(page.get(key, ""), "page." + key, required=False)
                              for key in ("headline", "kicker")},
                           "focus": [_number(v, "focus", minimum=0, maximum=1) for v in focus],
                           "start": starts[i], "duration": seconds})
    return {"start": start, "duration": duration, "frame": [x, y, w, h],
            "label_y": label_y, "copy_y": copy_y, "transition": transition,
            **sizes, "pages": normalized}


def photo_blocks_html(block: dict, index: int, asset_uri: Callable[[str], str]) -> tuple[str, str, str]:
    """Build one independently scheduled block; never mutate a shared timeline.

    JS registers ``storyRenderers`` and a ``storyPhotoChecks`` callback. The
    latter reports natural text overflow at native font sizes, without changing
    type. It can be called after fonts load, even while the block is hidden.
    """
    if type(index) is not int or index < 0:
        raise ValueError("index must be a nonnegative integer")
    if not callable(asset_uri):
        raise ValueError("asset_uri must be callable")
    p = validate_block(block)
    ident = f"story-photo-{index}"
    x, y, w, h = p["frame"]
    e = html.escape
    pages = []
    for i, page in enumerate(p["pages"]):
        uri = _string(asset_uri(page["path"]), "resolved photo URI")
        if uri.lower().startswith(("javascript:", "vbscript:", "data:text/")):
            raise ValueError("resolved asset must be an image URI")
        fx, fy = page["focus"]
        pages.append(f'''<section class="spm-page" data-page="{i}">
<img class="spm-photo" src="{e(uri, quote=True)}" alt="{e(page['event'], quote=True)}" style="object-position:{fx*100:g}% {fy*100:g}%">
<div class="spm-shade"></div><div class="spm-label-mask"><div class="spm-label"><span class="spm-date" data-story-text>{e(page['date'])}</span><span class="spm-event" data-story-text>{e(page['event'])}</span></div></div>
<div class="spm-copy"><div class="spm-kicker-mask"><span class="spm-kicker" data-story-text>{e(page['kicker'])}</span></div><div class="spm-headline-mask"><span class="spm-headline" data-story-text>{e(page['headline'])}</span></div><div class="spm-rule"></div></div><div class="spm-edge"></div></section>''')
    markup = f'<div id="{ident}" class="story-photo-motion" aria-hidden="true">' + ''.join(pages) + '</div>'
    prefix = '#' + ident
    # Native fixed type sizes: the layout checker reports overflow; it never
    # silently shrinks labels or headlines to make unsupported copy fit.
    css = f'''
{prefix}{{position:absolute;left:{x:g}px;top:{y:g}px;width:{w:g}px;height:{h:g}px;overflow:hidden;visibility:hidden;pointer-events:none}}
{prefix} *{{box-sizing:border-box}}
{prefix} .spm-page{{position:absolute;inset:0;overflow:hidden;visibility:hidden;background:{DARK['background']}}}
{prefix} .spm-photo{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transform-origin:50% 48%}}
{prefix} .spm-shade{{position:absolute;inset:0;background:linear-gradient(180deg,#020a1440,transparent 28%,transparent 50%,#06111fc9 89%,#06111ff0)}}
{prefix} .spm-label-mask{{position:absolute;left:0;top:{p['label_y']-y:g}px;width:100%;height:76px;overflow:hidden}}
{prefix} .spm-label{{display:inline-flex;align-items:center;gap:25px;height:66px;padding:0 31px 0 64px;background:#12395df2;border-right:8px solid #63b9ff;color:#edf3f7;font: {p['label_font_size']:g}px/1.2 'TL Sans SC',sans-serif;white-space:nowrap}}
{prefix} .spm-date{{font: {p['date_font_size']:g}px/1.2 'TL Numeral','TL Sans SC',sans-serif;letter-spacing:1px}}
{prefix} .spm-copy{{position:absolute;left:64px;right:64px;top:{p['copy_y']-y:g}px}}
{prefix} .spm-kicker-mask{{height:116px;overflow:hidden}}
{prefix} .spm-kicker{{display:inline-block;font: {p['kicker_font_size']:g}px/1.1 'TL Numeral','TL Sans SC',sans-serif;color:#d8ebfa8c;white-space:nowrap}}
{prefix} .spm-headline-mask{{height:108px;overflow:hidden}}
{prefix} .spm-headline{{display:inline-block;font: {p['headline_font_size']:g}px/1.18 'TL Display SC','TL Sans SC',sans-serif;color:#f4fbf7;white-space:nowrap;text-shadow:0 4px 20px #0008}}
{prefix} .spm-rule{{width:130px;height:5px;background:#63b9ff;transform-origin:left}}
{prefix} .spm-edge{{position:absolute;right:0;top:0;bottom:0;width:8px;background:#63b9ff;opacity:.7;transform-origin:top}}
'''
    data = json.dumps(p, ensure_ascii=False).replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')
    js = r'''(()=>{
const p=__DATA__, root=document.getElementById('__ID__'), pages=[...root.querySelectorAll('.spm-page')];
const clamp=x=>Math.max(0,Math.min(1,x)), ease=x=>1-Math.pow(1-clamp(x),3);
const state=pages.map(n=>Object.fromEntries(['photo','label','kicker','headline','rule','edge'].map(k=>[k,n.querySelector('.spm-'+k)])));
const render=seconds=>{
 const global=Number(seconds), t=global-p.start, active=Number.isFinite(global)&&t>=0&&t<p.duration;
 root.style.visibility=active?'visible':'hidden';root.setAttribute('aria-hidden',active?'false':'true');
 let current=-1;if(active)p.pages.forEach((q,i)=>{if(t>=q.start&&t<q.start+q.duration)current=i;});
 pages.forEach((n,i)=>{
  const q=p.pages[i], age=t-q.start, next=p.pages[i+1];
  const reveal=Math.min(p.transition,q.duration/3), prior=i===current-1&&next&&Math.abs(q.start+q.duration-next.start)<1e-7&&t<next.start+Math.min(p.transition,next.duration/3);
  n.style.visibility=active&&(i===current||prior)?'visible':'hidden';
  const entry=i===0?1:(reveal===0?1:ease(age/reveal));
  n.style.clipPath=`inset(0% 0% 0% ${(1-entry)*100}%)`;
  const s=state[i], progress=clamp(age/q.duration), typeDuration=Math.min(.48,q.duration*.28);
  s.photo.style.transform=`translateX(${(i%2?12:-12)*(1-progress)}px) scale(${1.055-.04*progress})`;
  s.label.style.transform=`translateX(${-(p.frame[2]+20)*(1-ease((age-.025)/Math.min(.42,q.duration*.24)))}px)`;
  const k=ease((age-.10)/typeDuration), h=ease((age-.20)/typeDuration);
  s.kicker.style.transform=`translateY(${116*(1-k)}px)`;s.kicker.style.opacity=String(k);
  s.headline.style.transform=`translateY(${108*(1-h)}px) rotate(${3*(1-h)}deg)`;s.headline.style.opacity=String(h);
  s.rule.style.transform=`scaleX(${ease((age-.35)/typeDuration)})`;
  s.edge.style.transform=`scaleY(${entry})`;
 });
};
window.storyRenderers=window.storyRenderers||[];window.storyRenderers.push(render);
window.storyPhotoChecks=window.storyPhotoChecks||[];window.storyPhotoChecks.push(()=>{
 const issues=[];
 pages.forEach((n,i)=>{
  const label=n.querySelector('.spm-label');if(label.offsetWidth>p.frame[2])issues.push({id:'__ID__',page:i,kind:'label_overflow',width:label.offsetWidth,available:p.frame[2]});
  if(p.frame[0]+label.offsetWidth-8>1040)issues.push({id:'__ID__',page:i,kind:'label_canvas_margin',right:p.frame[0]+label.offsetWidth-8});
  [...label.children].forEach(text=>{if(text.offsetHeight>label.clientHeight)issues.push({id:'__ID__',page:i,kind:'label_height_overflow',height:text.offsetHeight,available:label.clientHeight});});
  ['kicker','headline'].forEach(k=>{const text=n.querySelector('.spm-'+k),mask=text.parentElement;
   if(text.offsetWidth>mask.clientWidth||text.offsetHeight>mask.clientHeight)issues.push({id:'__ID__',page:i,kind:k+'_overflow',actual:[text.offsetWidth,text.offsetHeight],available:[mask.clientWidth,mask.clientHeight]});});
 });return issues;
});
render(0);
})();'''.replace('__DATA__', data).replace('__ID__', ident)
    return markup, css, js
