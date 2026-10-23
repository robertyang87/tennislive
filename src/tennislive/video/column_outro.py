"""Shared, deterministic three-column brand ending approved on 2026-10-23.

Render the rigid official logo once, then reuse per-column masters. No JS
libraries, network, new speech, loudness processing or frame-dependent timers.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import subprocess
import tempfile
from pathlib import Path

from tennislive.design_tokens import BRAND_BAR_CSS, CARD_BACKGROUND_CSS, DARK
from tennislive.render.webcards import _font_css
from tennislive.video.explainer import _data_uri

ROOT = Path(__file__).resolve().parents[3]
COLUMNS = {
    "赛场之上": ("match", "看见每一次转折"),
    "赛后开麦": ("interview", "听见胜负之外"),
    "网球有故事": ("story", "把热爱留在场上"),
}
ICON = ROOT / "assets/logo/brand/account/icon-transparent-1024.png"
SETTLED_AT = 3.2
MIN_LENGTH = SETTLED_AT + .9


def normalize_column(column: str) -> str:
    """Allow a brand-prefixed column label, reject unrelated/ambiguous values."""
    column = column.strip()
    if column.startswith("网球时差"):
        column = column.removeprefix("网球时差").lstrip(" ·・")
    if column not in COLUMNS:
        raise ValueError(f"片尾栏目不明确：{column!r}")
    return column


def master_path(column: str) -> Path:
    key, _ = COLUMNS[normalize_column(column)]
    return ROOT / "assets/brand" / f"outro_{key}.mp4"


def court_svg() -> str:
    """36×78ft court projected into the approved background trapezoid.

    Singles width 27ft; service lines 21ft either side of the net. The centre
    service line ends at those lines. The dashed net is not a painted court line.
    """
    def point(x: float, y: float) -> tuple[float, float]:
        t = y / 78
        denominator = 1 - (5 / 18) * t
        return (380 + (x / 36 - .5) * 520 / denominator,
                20 + 600 * (13 / 18) * t / denominator)

    def line(a, b) -> str:
        x, y = point(*a)
        xx, yy = point(*b)
        return f"M{x:.3f} {y:.3f}L{xx:.3f} {yy:.3f}"

    singles = " ".join(line((x, 0), (x, 78)) for x in (4.5, 31.5))
    service = " ".join(line((4.5, y), (31.5, y)) for y in (18, 60))
    center = line((18, 18), (18, 60))
    x, y = point(0, 39)
    xx, _ = point(36, 39)
    return f'''<svg class="court" viewBox="0 0 760 640" fill="none"
 stroke="{DARK['muted-foreground']}" stroke-width="3" aria-hidden="true">
<path data-court="doubles-boundary" d="M120 20H640L740 620H20Z"/>
<path data-court="singles-sidelines" d="{singles}"/>
<path data-court="service-lines" d="{service}"/>
<path data-court="centre-service-line" d="{center}"/>
<path data-court="net" d="M{x-14:.3f} {y:.3f}H{xx+14:.3f}"
 stroke-dasharray="9 8" stroke-opacity=".8"/></svg>'''


def page_html(column: str) -> str:
    from .outro_page import HANDLE, TAGLINE

    column = normalize_column(column)
    _, kicker = COLUMNS[column]
    logo = _data_uri(ICON)
    # Exact 944px visible circle in the 1024px original, displayed at 320px.
    angle = (540 - 170) / (472 * 320 / 1024) * 180 / math.pi
    script = '''
// Shared cubic-bezier clock for position and rotation: no slipping, no squash.
function ease(u){u=Math.max(0,Math.min(1,u));let lo=0,hi=1;
 for(let i=0;i<30;i++){let s=(lo+hi)/2,x=3*(1-s)*(1-s)*s*.2+3*(1-s)*s*s*.3+s*s*s;if(x<u)lo=s;else hi=s;}
 let s=(lo+hi)/2;return 3*(1-s)*(1-s)*s*.7+3*(1-s)*s*s+s*s*s;}
function out(u){u=Math.max(0,Math.min(1,u));return 1-Math.pow(1-u,3);}
window.setOutroTime=function(t){
 const p=ease((t-.2)/1.72),logo=document.getElementById('logo');
 logo.style.transform=`translate(${170+370*p-160}px,490px) rotate(${START_ANGLE*(1-p)}deg)`;
 logo.style.opacity=out(t/.32);
 const g=document.getElementById('ground');g.style.opacity=out((t-.1)/.65)*(1-out((t-2)/.65));
 g.style.transform=`scaleX(${out((t-.1)/.65)})`;
 const q=out((t-2.35)/.85),title=document.getElementById('title');title.style.opacity=q;
 title.style.transform=`translateY(${24*(1-q)}px)`;
};window.setOutroTime(0);
'''.replace('START_ANGLE', str(-angle))
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>
{_font_css()}
*{{box-sizing:border-box;margin:0}}body{{width:1080px;height:1440px;overflow:hidden;
background:{CARD_BACKGROUND_CSS};color:{DARK['foreground']};font-family:'TL Sans SC',sans-serif}}
.bar{{position:absolute;inset:0 0 auto;height:12px;background:{BRAND_BAR_CSS}}}
.court{{position:absolute;left:490px;top:900px;width:760px;height:640px;opacity:.1}}
.kicker{{position:absolute;top:118px;left:90px;width:900px;text-align:center;color:{DARK['muted-foreground']};font-size:31px;letter-spacing:3px}}
.kicker span{{display:inline-block;padding:13px 26px;border:1px solid {DARK['muted-foreground']}50;border-radius:5px;background:{DARK['card']}}}
#logo{{position:absolute;left:0;top:0;width:320px;height:320px;transform-origin:center}}
#ground{{position:absolute;left:90px;top:797.5px;width:900px;height:2px;background:{DARK['muted-foreground']};transform-origin:center}}
#title{{position:absolute;left:90px;top:1010px;width:900px;text-align:center}}
h1{{font:400 88px/1.3 'TL Display SC','TL Sans SC',sans-serif;white-space:nowrap}}
.tag{{margin-top:18px;color:{DARK['primary']};font-size:34px;letter-spacing:4px}}
.footer{{position:absolute;bottom:28px;width:1080px;display:flex;align-items:center;justify-content:center;gap:12px;color:{DARK['muted-foreground']};font-size:26px;letter-spacing:1px}}
.footer img{{width:40px;height:40px;object-fit:contain}}
</style><div class="bar"></div>{court_svg()}
<div class="kicker"><span>{kicker}</span></div><div id="ground"></div>
<img id="logo" src="{logo}" alt="网球时差">
<div id="title"><h1>网球时差 · {column}</h1><div class="tag">{TAGLINE.replace('，', ' ')}</div></div>
<div class="footer"><img src="{logo}">{HANDLE}</div><script>{script}</script></html>'''


def render_picture(out: Path, column: str, seconds: float, fps_expr: str,
                   chromium: str) -> Path:
    """Offline frame-seeking; hold the settled frame without more browser work."""
    from fractions import Fraction

    from PIL import Image
    from playwright.sync_api import sync_playwright

    if not math.isfinite(seconds) or seconds < MIN_LENGTH - .001:
        raise ValueError(f"品牌片尾至少需要 {MIN_LENGTH:.2f} 秒，不能截断入场与停留")
    fps = float(Fraction(fps_expr))
    if not 1 <= fps <= 120:
        raise ValueError("片尾帧率必须在 1 到 120 之间")
    column = normalize_column(column)
    document = page_html(column)
    key = hashlib.sha256((document + str(seconds) + fps_expr
                         + Path(__file__).read_text()).encode()).hexdigest()
    receipt = out.with_suffix('.outro.json')
    if out.is_file() and receipt.is_file():
        old = json.loads(receipt.read_text())
        if old.get('key') == key and old.get('sha256') == hashlib.sha256(out.read_bytes()).hexdigest():
            return out
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(out.stem + '.tmp.mp4')
    with tempfile.TemporaryDirectory(prefix='tennis-column-outro-') as directory:
        source = Path(directory) / 'outro.html'
        source.write_text(document)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=chromium, args=['--no-sandbox'])
            try:
                page = browser.new_page(viewport={'width':1080, 'height':1440}, device_scale_factor=1)
                page.goto(source.as_uri())
                page.evaluate('document.fonts.ready')
                page.wait_for_function('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
                page.evaluate('window.setOutroTime(3.2)')
                evidence = page.evaluate('''()=>{let e=document.querySelector('h1'),r=e.getBoundingClientRect();
                 return {text:e.textContent,width:r.width,scroll:e.scrollWidth,fonts:document.fonts.check("88px 'TL Display SC'")};}''')
                if evidence['scroll'] > evidence['width'] + 1 or not evidence['fonts']:
                    raise ValueError(f"片尾主标题字体或边界错误：{evidence}")
                page.screenshot(path=str(out.with_suffix('.jpg')), type='jpeg', quality=96)
                process = subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
                    '-s','1080x1440','-r',fps_expr,'-i','-','-an','-c:v','libx264','-preset','fast',
                    '-crf','12','-threads','2','-pix_fmt','yuv420p','-color_range','tv',
                    '-movflags','+faststart',str(temporary)],stdin=subprocess.PIPE)
                try:
                    last = None
                    for frame in range(math.ceil(seconds * fps - 1e-6)):
                        t = min(frame / fps, SETTLED_AT)
                        if t < SETTLED_AT or last is None:
                            page.evaluate('(t)=>{window.setOutroTime(t);}', t)
                            last = Image.open(io.BytesIO(page.screenshot(type='jpeg',quality=97))).convert('RGB').tobytes()
                        process.stdin.write(last)
                    process.stdin.close()
                    if process.wait():
                        raise RuntimeError('片尾画面编码失败')
                except BaseException:
                    process.kill()
                    process.wait()
                    temporary.unlink(missing_ok=True)
                    raise
            finally:
                browser.close()
    temporary.replace(out)
    receipt.write_text(json.dumps({'column':column,'key':key,'seconds':seconds,'fps':fps_expr,
        'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'browser':evidence},ensure_ascii=False,indent=2))
    return out


def render_clip(outdir: Path, seconds: float, *, column: str, fps_expr: str,
                chromium: str, dest: Path, audio_rate: str, preset: str, crf: str,
                audio_bitrate='160k', audio_channels=1, tail=0.0, voice=None,
                runner=None) -> Path:
    column = normalize_column(column)
    total = seconds + tail
    key, _ = COLUMNS[column]
    picture = render_picture(outdir / f'_outro_{key}_picture.mp4', column, total, fps_expr, chromium)
    args = ['ffmpeg','-y','-v','error','-i',str(picture)]
    if voice is None:
        layout = 'stereo' if audio_channels == 2 else 'mono'
        args += ['-f','lavfi','-i',f'anullsrc=channel_layout={layout}:sample_rate={audio_rate}']
    else:
        args += ['-i',str(voice)]
    args += ['-map','0:v:0','-map','1:a:0','-af',f'apad,atrim=0:{total:.9f},asetpts=PTS-STARTPTS',
             '-t',f'{total:.9f}','-vf','setsar=1','-c:v','libx264','-preset',preset,'-crf',crf,
             '-pix_fmt','yuv420p','-color_range','tv','-r',fps_expr,'-c:a','aac',
             '-b:a',audio_bitrate,'-ar',audio_rate,'-ac',str(audio_channels),str(dest)]
    (runner or subprocess.run)(args,check=True)
    return dest
