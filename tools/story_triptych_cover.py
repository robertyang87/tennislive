"""Reconstruct the user-selected 23-city story triptych with native TL fonts.

Reference is an imported compiled master, so this is a new compositor, not
an assertion that an unavailable historical rendering project was recovered.
No image generation, no publication, no TTS, no burned-master pixels.
"""
from pathlib import Path
import html


def render_cover(images: list[Path], titles: list[str], labels: list[tuple[str,str]], topic: str, out: Path) -> Path:
    from playwright.sync_api import sync_playwright
    import story_reference_style as R
    from tennislive.video import explainer as E
    from tennislive.chromium import launch_chromium
    if len(images)!=3 or len(labels)!=3 or len(titles)!=2:
        raise ValueError('Exact reference triptych requires 3 photos, 3 stage labels, 2 title lines')
    images=[Path(p).resolve() for p in images]
    for p in images:
        if not p.is_file():raise FileNotFoundError(p)
    icon=E._REPO/'assets/logo/brand/icon.png'
    def h(s):return html.escape(str(s))
    panels=''.join(f'<div class="panel p{i}"><img src="{E._data_uri(p)}"></div>' for i,p in enumerate(images))
    stages=''.join(f'<div class="stage s{i}"><strong>{h(a)}</strong><span>{h(b)}</span></div>' for i,(a,b) in enumerate(labels))
    title_sizes=[min(120, int(920/max(1,len(t))*1.04)) for t in titles]
    doc=f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>{R.chrome_css()}
*{{margin:0;padding:0;box-sizing:border-box}}html,body{{width:1080px;height:1440px;overflow:hidden;background:#142231;color:#f3fff6}}
body{{font-family:'TL Sans SC','Noto Sans SC',sans-serif}}
.panel{{position:absolute;left:0;width:1080px;overflow:hidden}}.panel img{{width:100%;height:100%;object-fit:cover;object-position:center 38%}}
.p0{{top:0;height:502px;clip-path:polygon(0 0,100% 0,100% 85%,0 100%)}}
.p1{{top:425px;height:507px;clip-path:polygon(0 15%,100% 0,100% 85%,0 100%)}}
.p2{{top:855px;height:585px;clip-path:polygon(0 13%,100% 0,100% 100%,0 100%)}}
.p2 img{{object-position:center 45%}}
.wash{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.1),transparent 20%,rgba(0,0,0,.18) 48%,transparent 75%,rgba(0,0,0,.32))}}
.head{{position:absolute;top:44px;left:70px;right:70px;display:flex;align-items:center;gap:14px;text-shadow:0 2px 3px #000,0 0 5px #000}}
.head img{{width:52px;height:52px;object-fit:contain;filter:drop-shadow(0 2px 5px #000)}}
.brand{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:38px;letter-spacing:1px}}
.topic{{font-size:27px;font-weight:700;letter-spacing:1px;margin-top:2px}}
.title{{position:absolute;left:70px;top:552px;font-family:'TL Display SC','TL Sans SC',sans-serif;line-height:1.07;letter-spacing:1px;text-shadow:0 3px 3px #000,2px 0 2px #000,-2px 0 2px #000}}
.title .a{{font-size:{title_sizes[0]}px}}.title .b{{font-size:{title_sizes[1]}px;color:#baf52f}}
.hook{{margin-top:7px;font-family:'TL Sans SC',sans-serif;font-size:46px;font-weight:700}}
.stage{{position:absolute;display:flex;flex-direction:column;gap:4px;text-shadow:0 2px 3px #000,0 0 5px #000}}
.stage strong{{color:#c1ef41;font-size:25px;font-weight:700}}.stage span{{font-size:27px;font-weight:700}}
.s0{{left:70px;top:365px}}.s1{{right:70px;top:748px;text-align:right}}.s2{{left:70px;bottom:30px}}
</style></head><body>{panels}<div class="wash"></div>
{R.header_html(topic)}
<div class="title"><div class="a">{h(titles[0])}</div><div class="b">{h(titles[1])}</div></div>{stages}</body></html>'''
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    out.with_suffix('.html').write_text(doc)
    with sync_playwright() as p:
        browser=launch_chromium(p)
        try:
            page=browser.new_page(viewport={'width':1080,'height':1440},device_scale_factor=1)
            page.set_content(doc);page.wait_for_function("document.fonts.status === 'loaded'",timeout=15000)
            page.screenshot(path=str(out),type='jpeg',quality=96)
        finally:browser.close()
    return out
