"""Approved report motion: real offline GSAP/D3, shared with HyperFrames export.

Receives validated fact relationships and the existing native typography/layout.
Sources remain in metadata; never print a credit/qualifier below a photograph.
"""
from __future__ import annotations
import html
import json
from pathlib import Path
import re
from ..design_tokens import DARK

VENDOR = Path(__file__).resolve().parents[3] / 'assets/vendor/motion'
MOTION_SECONDS = 6.0


def _script(value):
    return json.dumps(value, ensure_ascii=False).replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')


def enhance(document: str, p: dict, *, size, seconds: float) -> str:
    """Keep native semantic title, footer and story rail; replace only motion."""
    w, h = size
    horizon = min(MOTION_SECONDS, max(.1, seconds - .3))
    groups = p.get('groups', [])
    if p['kind'] == 'comparison' and all(re.fullmatch(r'\d+(?:\.\d+)?', n['value']) for n in p['nodes']):
        groups = [{'metric': p['content']['comparison']['metric'], 'nodes': p['nodes']}]
    if groups:
        proof_h = p['proof_h']
        panel = f'<section class="transition-proof motion-chart" style="height:{proof_h}px"><svg id="comparison-chart" viewBox="0 0 {w-180} {proof_h}"></svg></section>'
        document = re.sub(r'<section class="transition-proof .*?</section>', lambda _: panel, document, count=1, flags=re.S)
        if 'id="comparison-chart"' not in document:
            document += panel
    summary = p['content'].get('summary')
    if summary:
        document += (f'<div class="motion-summary" style="top:{p["proof_y"]+p["proof_h"]-156}px">'
                     f'<div class="summary-value">{html.escape(summary["value"])}</div>'
                     f'<div class="summary-label">{html.escape(summary["label"])}</div></div>')
    result = p['content'].get('photo', {}).get('result') if p.get('photo') else None
    if result:
        document += (f'<div class="motion-result" style="top:{p["photo"]["top"]+p["photo"]["height"]-105}px">'
                     f'<div class="result-value">{html.escape(result["value"])}</div>'
                     + (f'<div class="result-label">{html.escape(result["label"])}</div>' if result.get('label') else '') + '</div>')
    from .column_outro import court_svg
    document = re.sub(r'<svg class="tc-court".*?</svg>', lambda _: court_svg().replace('class="court"', 'class="tc-court"'), document, flags=re.S)
    document += f'''<style>
/* v2: approved motion language; metadata is never a visible photo footnote. */
.transition-line,.transition-node,.node-value,.wrap .kicker,.transition-photo,.tc-court,.tc-glow,em:after{{animation:none!important}}
.tc-court{{inset:auto;left:{w*.454:g}px;top:{h*.625:g}px;width:{w*.704:g}px;height:{h*.444:g}px;opacity:.1;stroke:{DARK['muted-foreground']};stroke-width:3;stroke-dasharray:none;stroke-dashoffset:0}}
.tc-glow{{opacity:.35}}
.transition-line{{color:{DARK['foreground']}}}
.transition-line:last-child:not(:first-child){{color:{DARK['primary']}}}
.score_progress.horizontal .transition-node{{height:218px;border:1px solid #cfe6d82b;border-radius:18px;padding:24px 12px;background:{DARK['card']}}}
.score_progress.horizontal .node-value{{font-size:96px;color:{DARK['primary']}}}
.score_progress:after,.chronology:after{{animation:none;opacity:.45}}
.chronology .transition-node{{height:{p.get('node_height',86)}px;padding-left:40px}}
.chronology .transition-node:before{{content:'';position:absolute;left:-8px;top:50%;width:16px;height:16px;border-radius:50%;background:{DARK['primary']}}}
.chronology .node-value{{font-size:40px}}
.transition-photo{{border:2px solid {DARK['primary']};border-radius:12px}}
.motion-summary{{position:absolute;left:90px;width:{w-180}px;text-align:center}}
.summary-value{{font-family:'TL Numeral','TL Sans SC',sans-serif;font-size:90px;color:{DARK['primary']};line-height:1.2}}
.summary-label{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:40px;margin-top:12px}}
.motion-result{{position:absolute;left:{w*.148:g}px;width:{w*.704:g}px;padding:18px 20px;text-align:center;border-radius:14px;border:1px solid {DARK['primary']};background:{DARK['card']}}}
.result-value{{font-family:'TL Numeral','TL Sans SC',sans-serif;font-size:76px;color:{DARK['primary']};line-height:1.3}}
.result-label{{font-family:'TL Sans SC',sans-serif;font-size:28px;line-height:1.4;margin-top:8px}}
.motion-chart svg{{width:100%;height:100%;overflow:visible}}
</style>'''
    libraries = ''.join('<script>'+ (VENDOR/name).read_text().replace('</script', r'<\/script') +'</script>'
                        for name in ['gsap-3.15.0.min.js', 'd3-7.9.0.min.js'])
    data = {'groups': groups, 'width': w-180, 'height': p['proof_h'], 'horizon': horizon,
            'compact': h < 1200, 'nodes': len(p['nodes']), 'hasPhoto': bool(p.get('photo'))}
    script = r'''
const data=__DATA__;
const tl=gsap.timeline({paused:true});
tl.fromTo('.transition-line',{y:60,opacity:0},{y:0,opacity:1,duration:.75,stagger:.22,ease:'power3.out'},.15)
 .fromTo('.wrap .kicker',{y:-18,opacity:0},{y:0,opacity:1,duration:.5,ease:'power2.out'},.1)
 .fromTo('.transition-node',{y:60,opacity:0},{y:0,opacity:1,duration:.8,stagger:.65,ease:'power3.out'},1.25)
 .fromTo('.transition-photo',{y:80,opacity:0,scale:.96},{y:0,opacity:1,scale:1,duration:1.15,ease:'power3.out'},1.1)
 .fromTo('.motion-summary',{y:45,opacity:0},{y:0,opacity:1,duration:.8,ease:'power3.out'},4.4)
 .fromTo('.motion-result',{y:70,opacity:0},{y:0,opacity:1,duration:.9,ease:'power3.out'},4.3);
const bars=[];
if(data.groups.length){
 const svg=d3.select('#comparison-chart').attr('font-family','TL Sans SC');
 const measure=svg.append('text').attr('font-size',27).attr('visibility','hidden');
 const labels=data.groups.flatMap(g=>g.nodes.map(n=>n.label));
 const labelWidth=d3.max(labels,name=>{measure.text(name);return measure.node().getComputedTextLength();});
 if(labelWidth>240)throw new Error('对照姓名过长 请使用完整官方简称或拆卡');
 const left=Math.max(120,labelWidth+20), width=data.width-left-112;
 measure.remove();
 const gh=data.height/data.groups.length;
 data.groups.forEach((g,i)=>{
  const group=svg.append('g').attr('transform',`translate(0,${i*gh})`);
  group.append('text').attr('class','metric-title').attr('x',0).attr('y',30).attr('fill','#f4fbf7').attr('font-size',data.compact?28:30)
   .text([g.scope,g.metric,g.unit].filter(Boolean).join(' '));
  const comparable=data.groups.filter(other=>other.unit===g.unit && other.scope===g.scope).flatMap(other=>other.nodes);
  const scale=d3.scaleLinear().domain([0,d3.max(comparable,n=>Number(n.value))||1]).range([0,width]);
  const rows=group.selectAll('g').data(g.nodes).join('g').attr('transform',(d,j)=>`translate(0,${52+j*(gh-60)/g.nodes.length})`);
  rows.append('text').attr('class','chart-label').attr('y',29).attr('font-size',27).attr('fill','#cfe6d8').text(n=>n.label);
  rows.append('rect').attr('x',left).attr('width',width).attr('height',data.compact?26:34).attr('rx',7).attr('fill','#cfe6d811');
  rows.append('rect').attr('class','chart-bar').attr('x',left).attr('height',data.compact?26:34).attr('rx',7).attr('fill',(d,j)=>j?'#cfe6d8':'#c6f65a');
  rows.append('text').attr('class','chart-value').attr('y',36).attr('font-family','TL Numeral').attr('font-size',data.compact?40:48).attr('fill',(d,j)=>j?'#f4fbf7':'#c6f65a').text(n=>n.value);
  bars.push({rows,scale,i,left});
 });
}
function updateBars(canonical){
 bars.forEach(({rows,scale,i,left})=>{
  const progress=d3.easeCubicOut(Math.max(0,Math.min(1,(canonical-1.6-i*1.5)/1.1)));
  rows.select('.chart-bar').attr('width',n=>scale(Number(n.value))*progress);
  rows.select('.chart-value').attr('x',n=>left+12+scale(Number(n.value))*progress);
 });
}
// A real-time master clock drives the canonical scene and D3 together.
tl.to({}, {duration:.01},5.99);
const clock={value:0};
const master=gsap.timeline({paused:true}).to(clock,{value:6,duration:data.horizon,ease:'none',onUpdate:()=>{tl.seek(clock.value,false);updateBars(clock.value);}});
window.setTransitionTime=(seconds)=>{master.seek(Math.min(data.horizon,Math.max(0,seconds)),false);tl.seek(clock.value,false);updateBars(clock.value);};
window.__timelines=window.__timelines||{};window.__timelines.main=master;
window.transitionMotion={engine:'GSAP 3.15.0 + D3 7.9.0',horizon:data.horizon};
window.setTransitionTime(0);gsap.ticker.sleep();
'''.replace('__DATA__', _script(data))
    return document + libraries + '<script>document.fonts.ready.then(()=>{'+script+'}).catch(error=>{window.transitionMotionError=error.message;});</script>'
