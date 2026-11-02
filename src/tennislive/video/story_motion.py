"""Composable story blocks on the shared transition-card clock.

Blocks describe independently timed editorial relationships, never a whole-film
recipe. Authentic match footage stays in native source segments and its review
pipeline; this module accepts photography and graphics only.
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

from ..design_tokens import DARK


def number(value, name, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError(f'{name} 必须为不小于 {minimum} 的有限数字')
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} 必须为非空文字')
    return value


def frame(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError('frame 必须为 x y width height')
    x, y, w, h = [number(v, 'frame') for v in value]
    if w <= 0 or h <= 0 or x+w > 1080 or y+h > 1244 or y < 160:
        raise ValueError('组件必须留出顶部160与底部字幕1244安全区')
    return x, y, w, h


def validate_scene(scene, *, seconds=None):
    if not isinstance(scene, dict) or set(scene) != {'blocks'}:
        raise ValueError('scene 只接受 blocks；顺序与时间由本段内容决定')
    blocks = scene['blocks']
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 12:
        raise ValueError('scene 需要1到12个可组合组件')
    for block in blocks:
        if not isinstance(block, dict) or block.get('kind') not in {'headline', 'nodes', 'photo', 'timeline'}:
            raise ValueError('未知故事组件')
        start = number(block.get('start'), 'start')
        duration = number(block.get('duration'), 'duration', .1)
        if seconds is not None and start+duration > seconds + .041:
            raise ValueError('组件超过实际配音窗口 请调整组件时序')
        if 'frame' in block:
            frame(block['frame'])
        if 'exit' in block:
            exit_ = block['exit']
            if (not isinstance(exit_, dict) or set(exit_) != {'style', 'duration'}
                    or exit_.get('style') not in {'slide', 'fold', 'fade'}):
                raise ValueError('exit 需要 slide/fold/fade 与 duration')
            if number(exit_['duration'], 'exit.duration', .1) > duration:
                raise ValueError('退场不能长于组件')
        if block['kind'] in {'headline', 'nodes'}:
            allowed = {'kind', 'start', 'duration', 'frame', 'exit', 'lines', 'kicker', 'nodes', 'source'}
            if block.keys() - allowed:
                raise ValueError('标题或节点有未知字段')
            if block['kind'] == 'headline':
                lines = block.get('lines')
                if not isinstance(lines, list) or not 1 <= len(lines) <= 2:
                    raise ValueError('标题需1到2个完整语义行')
                for line in lines:
                    text(line, 'line')
                    if '\n' in line:
                        raise ValueError('语义行不能再拆行')
                if 'kicker' in block:
                    text(block['kicker'], 'kicker')
            else:
                nodes = block.get('nodes')
                if not isinstance(nodes, list) or not 2 <= len(nodes) <= 5:
                    raise ValueError('晋级节点需要2到5项')
                for node in nodes:
                    if not isinstance(node, dict) or set(node) != {'label', 'value', 'source'}:
                        raise ValueError('节点需要 label value source')
                    for key in node:
                        text(node[key], key)
            text(block.get('source'), '组件source')
        elif block['kind'] == 'photo':
            from .story_photo_motion import validate_block
            normalized = validate_block({k: v for k, v in block.items() if k not in {'kind', 'exit'}})
            for page in normalized['pages']:
                path = Path(page['path'])
                if path.is_absolute() or ':' in page['path'] or '..' in path.parts or path.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}:
                    raise ValueError('摄影必须为仓库相对图片路径 不接受视频')
        else:
            from .story_timeline_motion import validate_block
            validate_block({k: v for k, v in block.items() if k != 'exit'})
    return json.loads(json.dumps(scene, ensure_ascii=False))


def _basic(block, index):
    name = f'story-basic-{index}'
    kind = block['kind']
    x, y, w, h = frame(block.get('frame', [70, 300, 940, 360] if kind == 'headline' else [90, 600, 900, 580]))
    esc = html.escape
    if kind == 'headline':
        content = (f'<p class="story-kicker" data-story-text>{esc(block.get("kicker", ""))}</p>'
                   + ''.join(f'<div class="story-line" data-story-text>{esc(line)}</div>' for line in block['lines']))
    else:
        content = '<div class="story-route"></div>' + ''.join(f'<div class="story-node"><i>{i+1:02}</i><span data-story-text>{esc(n["label"])}</span>'
                          f'<strong data-story-text>{esc(n["value"])}</strong></div>' for i,n in enumerate(block['nodes']))
    markup = f'<section id="{name}" class="story-basic {kind}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">{content}</section>'
    css = f'''#{name}{{position:absolute;overflow:hidden;display:flex;flex-direction:column;justify-content:center;gap:24px}}
#{name} .story-kicker{{font-size:32px;letter-spacing:4px;color:{DARK['info']};margin:0 0 16px;white-space:nowrap}}
#{name} .story-line{{font-family:'TL Display SC';font-size:76px;line-height:1.3;white-space:nowrap}}
#{name} .story-line:last-child{{color:{DARK['primary']}}}
#{name} .story-route{{position:absolute;top:24px;bottom:24px;left:26px;width:2px;background:{DARK['info']};transform-origin:top;opacity:.4}}
#{name} .story-node{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid {DARK['muted-foreground']}44;padding:20px 20px 20px 78px;gap:24px;transform-origin:left;perspective:900px}}
#{name} .story-node i{{position:absolute;left:6px;background:{DARK['card']};border:1px solid {DARK['info']};width:42px;height:42px;border-radius:50%;display:grid;place-items:center;font-family:'TL Numeral';font-size:23px;font-style:normal;color:{DARK['primary']}}}
#{name} .story-node span{{font-size:34px;white-space:nowrap}}
#{name} .story-node strong{{font-family:'TL Numeral','TL Sans SC';font-size:40px;white-space:nowrap;color:{DARK['primary']}}}'''
    js = f'''{{const el=document.getElementById('{name}');const parts=[...el.querySelectorAll('.story-kicker,.story-line,.story-node')];
window.storyRenderers.push(t=>{{const local=t-{block['start']};el.style.visibility=local>=0&&local<{block['duration']}?'visible':'hidden';
parts.forEach((p,i)=>{{const a=Math.min(1,Math.max(0,(local-.08-i*.22)/.6));const e=1-Math.pow(1-a,3);p.style.opacity=a;p.style.transform=`translateY(${{(1-e)*44}}px) rotateX(${{(1-e)*-28}}deg)`;}});
const route=el.querySelector('.story-route');if(route)route.style.transform=`scaleY(${{Math.min(1,Math.max(0,local/1.6))}})`;}});}}'''
    return markup, css, js


def build_scene(scene, *, base, seconds, root: Path):
    """Extend the existing branded HTML; same seek API for preview and export."""
    from .explainer import _data_uri
    from .story_photo_motion import photo_blocks_html
    from .story_timeline_motion import timeline_blocks_html
    from .transition_motion import VENDOR

    scene = validate_scene(scene, seconds=seconds)

    def asset_uri(value):
        path = Path(value)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('摄影必须为仓库相对路径')
        target = (root/path).resolve()
        if not target.is_relative_to(root.resolve()) or target.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}:
            raise ValueError('组件只接受真实摄影图片 不接视频或外部路径')
        from PIL import Image
        with Image.open(target) as im:
            im.verify()
        return _data_uri(target)

    markup, styles, scripts = [], [], []
    factories = {'headline': _basic, 'nodes': _basic}
    for i, block in enumerate(scene['blocks']):
        clean = {k: v for k, v in block.items() if k != 'exit'}
        if block['kind'] == 'photo':
            clean.pop('kind')
            fragment = photo_blocks_html(clean, i, asset_uri)
        elif block['kind'] == 'timeline':
            fragment = timeline_blocks_html(clean, i, asset_uri)
        else:
            fragment = factories[block['kind']](clean, i)
        body, css, js = fragment
        markup.append(f'<div id="story-block-{i}" class="story-block">{body}</div>')
        styles.append(css)
        scripts.append(js)
        if 'exit' in block:
            e = block['exit']
            scripts.append(f'''{{const el=document.getElementById('story-block-{i}');window.storyRenderers.push(t=>{{
const a=Math.max(0,Math.min(1,(t-{block['start']+block['duration']-e['duration']})/{e['duration']}));
el.style.opacity=1-a;el.style.transform={'`translateX(${a*150}px)`' if e['style']=='slide' else '`scaleY(${1-a*.92})`' if e['style']=='fold' else "'none'"};}});}}''')
    gsap = (VENDOR/'gsap-3.15.0.min.js').read_text().replace('</script', r'<\/script')
    preview_time = max(b['start'] + min(b['duration']*.7, b['duration']-b.get('exit',{}).get('duration',0)*.7) for b in scene['blocks'])
    clock = '''document.fonts.ready.then(()=>{try{window.storyRenderers=[];
__INSTALL__
window.setTransitionTime=(t)=>{if(!Number.isFinite(t))throw new Error('invalid story time');window.storyRenderers.forEach(fn=>fn(Math.max(0,t)));};
window.transitionMotion={engine:'composable-story',horizon:__SECONDS__,previewTime:__PREVIEW__};window.setTransitionTime(0);gsap.ticker.sleep();
}catch(e){window.transitionMotionError=String(e);}});'''.replace('__INSTALL__', '\n'.join(scripts)).replace('__SECONDS__', str(seconds)).replace('__PREVIEW__', str(preview_time))
    reset = f'''*{{box-sizing:border-box}}.wrap,.glow{{display:none!important}}.story-block{{position:absolute;inset:0;transform-origin:center;pointer-events:none}}
.story-stage{{position:absolute;inset:0;overflow:hidden;color:{DARK['foreground']};font-family:'TL Sans SC'}}
.bar,.handle,.explainer-head{{z-index:30}}'''
    return base + '<style>' + reset + '\n'.join(styles) + '</style><div class="story-stage">' + ''.join(markup) + '</div><script>' + gsap + '</script><script>' + clock + '</script>'


def check_scene_page(page):
    """Check actual visible text after each sampled clock position."""
    # Sliding photo date tabs intentionally start behind their masks, outside
    # the viewport. Their natural geometry is checked by storyPhotoChecks.
    boxes = page.evaluate('''()=>[...document.querySelectorAll('[data-story-text]')].filter(e=>!e.closest('.spm-label')&&e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})).map(e=>({text:e.textContent,scroll:e.scrollWidth,width:e.clientWidth,rect:e.getBoundingClientRect().toJSON()}))''')
    issues = page.evaluate('()=> (window.storyPhotoChecks||[]).flatMap(check=>check())')
    if issues:
        raise ValueError('摄影组件排版溢出：'+str(issues))
    clipped = page.evaluate('''()=>[...document.querySelectorAll('.story-basic')].filter(e=>e.checkVisibility({checkVisibilityCSS:true})).flatMap(e=>[...e.children].filter(c=>!c.classList.contains('story-route')).map(c=>({top:c.offsetTop,bottom:c.offsetTop+c.offsetHeight,height:e.clientHeight,left:c.offsetLeft,right:c.offsetLeft+c.offsetWidth,width:e.clientWidth}))).filter(e=>e.top<0||e.bottom>e.height+1||e.left<0||e.right>e.width+1)''')
    if clipped:
        raise ValueError('故事组件frame裁掉内容：'+str(clipped))
    if any(b['scroll'] > b['width']+1 or b['rect']['left'] < 40 or b['rect']['right'] > 1040
           or b['rect']['top'] < 160 or b['rect']['bottom'] > 1244 for b in boxes):
        raise ValueError('故事组件真实文字溢出或侵入品牌/字幕安全区：'+str(boxes))
    return {'visible_text': boxes}
