"""Story styling reconstructed from the user's approved 24-crown/23-city film.

The reference is a compiled historic film, not a rerunnable repository project.
Use repository font/logo assets and measured reference layout, never reel boards.
"""
from pathlib import Path
import html
from tennislive.video import explainer as E
from tennislive.render.webcards import _font_css
from tennislive.design_tokens import DARK, CARD_BACKGROUND_CSS

W,H=1080,1440
REFERENCE_SLUG='medvedev-24-titles-23-cities'
REFERENCE_SHA256='5af14197ef8a2dd2c93ae53ec3870ad8992e9b6b2b2ccfde7af254c8c0512c31'
REFERENCE_POSTER_SHA256='981467f8f8674acbe78c93a78f6d91b8526cfad033ca87f12466b7b3f8facab6'
# Exact reference ASS, including the historic font and upper anchor.
SUBTITLE_KWARGS=dict(height=H,margin_v=1240,outline=4,shadow=1)

def screenshot(doc: str,out:Path,*,height=H,transparent=False):
    from playwright.sync_api import sync_playwright
    from tennislive.chromium import launch_chromium
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=launch_chromium(p)
        try:
            page=browser.new_page(viewport={'width':W,'height':height},device_scale_factor=1)
            page.set_content(doc)
            page.wait_for_function("document.fonts.status==='loaded'")
            page.wait_for_function('Array.from(document.images).every(i=>i.complete)')
            page.screenshot(path=str(out),omit_background=transparent)
        finally:browser.close()
    return out

def chrome_css():
    # Coordinates measured on the approved 1080x1440 poster, no top colour bar.
    return _font_css()+'''
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1440px;background:transparent}
body{font-family:'TL Sans SC','Noto Sans SC',sans-serif;color:#f7fbf4}
.story-head{position:absolute;left:70px;top:44px;display:flex;align-items:center;gap:14px;text-shadow:0 2px 3px #07130f,0 0 6px #07130f}
.story-icon{width:52px;height:52px;filter:drop-shadow(0 2px 3px #07130f)}
.story-brand{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:38px;line-height:1.25;letter-spacing:1px;font-weight:400;-webkit-text-stroke:1px #07130f;paint-order:stroke fill}
.story-topic{font-size:27px;line-height:1.25;font-weight:700;letter-spacing:1px}
'''

def header_html(topic):
    icon=E._REPO/'assets/logo/brand/icon.png'
    return '<div class="story-head"><img class="story-icon" src="'+E._data_uri(icon)+'"><div><div class="story-brand">网球时差 · 网球有故事</div><div class="story-topic">'+html.escape(topic)+'</div></div></div>'

def render_header(topic,out):
    doc='<html><head><meta charset="utf-8"><style>'+chrome_css()+'</style></head><body>'+header_html(topic)+'</body></html>'
    return screenshot(doc,Path(out),height=200,transparent=True)

def write_subtitles(cues,out):
    return E.write_subtitles(cues,Path(out),**SUBTITLE_KWARGS)

def reference_record():
    return {'slug':REFERENCE_SLUG,'film_sha256':REFERENCE_SHA256,'poster_sha256':REFERENCE_POSTER_SHA256,'layout_source':'actual approved film and poster plus episode subtitles.ass','original_project_recovered':False,'subtitle_options':SUBTITLE_KWARGS}

def stage_html(stage,detail,*,note=''):
    # The approved film's upper-right transparent information hierarchy.
    lines=str(detail).split('\n')
    focus=''.join('<div class="stage-focus">'+html.escape(line)+'</div>' for line in lines)
    return '<div class="story-stage"><div class="stage-label">'+html.escape(str(stage))+'</div>'+focus+('<div class="stage-note">'+html.escape(note)+'</div>' if note else '')+'</div>'

def stage_css():
    return '''
.story-stage{position:absolute;right:70px;top:162px;max-width:680px;border-right:6px solid #c6f65a;padding-right:20px;text-align:right;text-shadow:0 2px 3px #07130f,0 0 6px #07130f;color:#f7fbf4}
.stage-label{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:38px;line-height:1.25;letter-spacing:.4px;-webkit-text-stroke:1px #07130f;paint-order:stroke fill}
.stage-focus{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:52px;line-height:1.22;color:#c6f65a;letter-spacing:.5px;-webkit-text-stroke:1px #07130f;paint-order:stroke fill}
.stage-note{font-size:27px;line-height:1.4;font-weight:700}
'''

def render_stage_overlay(topic,stage,detail,out,*,note=''):
    doc='<html><head><meta charset="utf-8"><style>'+chrome_css()+stage_css()+'</style></head><body>'+header_html(topic)+stage_html(stage,detail,note=note)+'</body></html>'
    return screenshot(doc,Path(out),height=500,transparent=True)

def render_photo_stage(image,topic,stage,detail,out,*,note='',photo_context=''):
    image=Path(image)
    doc='<html><head><meta charset="utf-8"><style>'+chrome_css()+stage_css()+'''
.photo{position:absolute;inset:0;width:1080px;height:1440px;object-fit:cover;object-position:center}
.context{position:absolute;bottom:48px;left:70px;right:70px;font-size:27px;text-shadow:0 2px 3px #07130f,0 0 6px #07130f;color:#f7fbf4}
</style></head><body><img class="photo" src="'''+E._data_uri(image)+'">'+header_html(topic)+stage_html(stage,detail,note=note)+('<div class="context">'+html.escape(photo_context)+'</div>' if photo_context else '')+'</body></html>'
    return screenshot(doc,Path(out))
