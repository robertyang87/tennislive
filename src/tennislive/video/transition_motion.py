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


def entry_process(document_spec: dict, *, text: str, size, seconds: float, header: dict | None) -> str:
    """A spatial, seekable rule demonstration, consumed by the native card encoder."""
    from ..render.webcards import _font_css
    from .explainer import _data_uri
    from .outro_page import ICON
    from ..design_tokens import BRAND_BAR_CSS, CARD_BACKGROUND_CSS
    root = Path(__file__).resolve().parents[3]
    for name in ('SmileySans-Oblique.woff2', 'NotoSansSC-Regular-sub.ttf', 'NotoSansSC-Bold-sub.ttf'):
        if not (root / 'assets/fonts' / name).is_file():
            raise ValueError('规则动画缺少正式字体：' + name)
    if not ICON.is_file():
        raise ValueError('规则动画缺少正式账号logo')
    w, h = size
    if (w, h) != (1080, 1440):
        raise ValueError('规则过程动画使用正式1080×1440画布')
    e = html.escape
    title = '<br>'.join(e(s) for s in text.splitlines())
    head = header or {'brand': '网球时差 · 网球有故事', 'topic': '外卡参赛规则演示'}
    data = {**document_spec['case'], 'scene': document_spec['scene'], 'seconds': seconds,
            'cues': document_spec.get('cues', [.15, .4, .65, .83])}
    gsap = (VENDOR / 'gsap-3.15.0.min.js').read_text().replace('</script', r'<\/script')
    import base64
    renoise = root / 'assets/vendor/renoise-vibe-knowledge'
    util_uri = 'data:text/javascript;base64,' + base64.b64encode((renoise/'util.js').read_bytes()).decode()
    know_source = (renoise/'know.js').read_text().replace('"./util.js"', json.dumps(util_uri))
    know_uri = 'data:text/javascript;base64,' + base64.b64encode(know_source.encode()).decode()

    body = r'''
const d=__DATA__, svg=document.querySelector('#process-stage'), NS='http://www.w3.org/2000/svg';
const world=document.querySelector('#process-world');
const C={ink:'#f4fbf7',sub:'#bdcde0',blue:'#62bcff',green:'#c6f65a',red:'#ff8a8f',panel:'#172a43',line:'#31506f'};
function el(tag,attrs={},parent=svg){const n=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));parent.append(n);return n;}
function text(s,x,y,size=30,color=C.ink,parent=svg,anchor='start'){const n=el('text',{x,y,fill:color,'font-size':size,'text-anchor':anchor,'dominant-baseline':'middle',class:'process-label'},parent);n.textContent=s;return n;}
function line(x1,y1,x2,y2,color=C.line,parent=svg){return el('path',{d:`M${x1},${y1} L${x2},${y2}`,fill:'none',stroke:color,'stroke-width':3,'stroke-linecap':'round'},parent);}
function panel(x,y,w,h,label){el('rect',{x,y,width:w,height:h,rx:20,fill:C.panel,stroke:C.line,'stroke-width':2});if(label)text(label,x+24,y+35,28,C.sub);}
function person(name,x,y,color=C.blue){const g=el('g',{'data-player':name});el('circle',{cx:0,cy:-20,r:23,fill:color},g);el('path',{d:'M-38,47 Q-38,8 0,8 Q38,8 38,47 Z',fill:color},g);el('ellipse',{cx:43,cy:7,rx:12,ry:20,fill:'none',stroke:color,'stroke-width':4,transform:'rotate(28 43 7)'},g);el('path',{d:'M35 23 L20 47',stroke:color,'stroke-width':5},g);text(name,0,84,29,C.ink,g,'middle');gsap.set(g,{x,y});return g;}
function pill(label,x,y,color=C.blue,width=180){const g=el('g');el('rect',{x:-width/2,y:-27,width,height:54,rx:14,fill:color},g);text(label,0,1,30,'#0c1a2b',g,'middle');gsap.set(g,{x,y});return g;}
function arrow(x1,y1,x2,y2,color=C.blue){const g=el('g');const a=Math.atan2(y2-y1,x2-x1),z=15;line(x2,y2,x2-z*Math.cos(a-.5),y2-z*Math.sin(a-.5),color,g);line(x2,y2,x2-z*Math.cos(a+.5),y2-z*Math.sin(a+.5),color,g);
 const rail=document.createElement('div');rail.style.cssText='position:absolute;inset:0;z-index:1';world.insertBefore(rail,svg);
 const path=renoiseTrail(rail,{pts:[[x1,y1],[(x1+x2)/2,(y1+y2)/2],[x2,y2]],color,width:4,nodeR:4,labels:[]});path.svg.setAttribute('width','980');path.svg.setAttribute('height','850');
 g.__trail={rail,path,at:0};return g;}
function board(x=90,y=140,scale=1){const g=el('g',{'data-draw-size':'32'});text('名额示意',400,45,30,C.sub,g,'middle');const slots=[], rows=[];
 const layer=document.createElement('div');layer.className='renoise-seat-layer';layer.style.cssText='position:absolute;inset:0;z-index:1';world.insertBefore(layer,svg);
 for(let row=0;row<4;row++){
  const r=renoiseTokens(layer,{x:x+24*scale,y:y+(135+row*105)*scale,n:8,size:83*scale,gap:14*scale,fill:'#203a55',border:C.line,glow:'#0000'});rows.push(r);r.update(1,-2);
  r.bs.forEach((token,col)=>{token.classList.add('draw-slot');token.dataset.slot=row*8+col+1;token.style.boxShadow='0 9px 0 #0b1628,0 16px 22px #0005,inset 0 2px 0 #aacfff22';slots.push({r:token,x:x+(24+col*97+41.5)*scale,y:y+(135+row*105+41.5)*scale});});
 }
 const count=renoiseCounter(layer,{x:x+350*scale,y:y+77*scale,size:44*scale,suffix:'席',font:'TL Sans SC',align:'left',color:C.ink});
 renderers.push(t=>{count.update(t,[[-1,32],[T,32]]);});
 gsap.set(g,{x,y,scale,transformOrigin:'0px 0px'});return {g,slots};}
const captions=[], renderers=[];
const tl=gsap.timeline({paused:true}), T=Math.max(.1,d.seconds-.16), at=(n)=>d.cues[n]*T;
function show(n,t,duration=.75){tl.fromTo(n,{opacity:0},{opacity:1,duration},t);if(n.__trail){const q=n.__trail;renderers.push(now=>{q.path.update(now,t,t+Math.min(3,T*.18));q.rail.style.opacity=getComputedStyle(n).opacity;});}}
function move(n,x,y,t,duration=1.6){tl.to(n,{x,y,duration,ease:'power2.inOut'},t);}
function caption(s,t){captions.push({s,t});}
const sky='<svg viewBox="0 0 1080 1440"><path d="M-90 1000L350 480H730L1170 1000M0 1100L360 570H720L1080 1100" fill="none" stroke="#4b88b8" stroke-width="2" opacity=".13"/></svg>';
const near='<svg viewBox="0 0 1080 1440"><path d="M-50 1200L320 810H760L1130 1200M-50 1250H1130" fill="none" stroke="#7bbbf0" stroke-width="2" opacity=".08"/></svg>';
const depth=renoiseLayers(document.querySelector('#process-backdrop'),[{svg:sky,depth:.2},{svg:near,depth:.75}],{w:1080,h:1440});
renderers.push(t=>{depth.update(t,-1,T+1,{pan:[14,-8],zoom:[1,1.04],fi:0,fo:0});renoiseFocus(world,t,[[0,{x:490,y:425,s:1}],[T,{x:490,y:425,s:1.025}]],{W:980,H:850});});
const s=d.scene;
if(['identity','seeding','summary'].includes(s)){
 const b=board(90,100);const player=person(d.player,115,660,C.green);const ticket=pill('外卡 WC',300,660,C.green,160);const badge=pill(`${d.seed}号种子`,750,660,C.blue,180);
 const a=arrow(190,660,580,660);show(a,.3);show(ticket,.3);show(badge,at(2));
 move(player,b.slots[31].x,b.slots[31].y-16,at(0),2.2);tl.to(b.slots[31].r,{backgroundColor:'#446421',borderColor:C.green,duration:.5},at(0)+1.6);
 move(ticket,b.slots[31].x,620,at(1),1);move(badge,b.slots[31].x,698,at(2),1.2);
 caption('先取得参赛名额',0);caption('外卡兼任种子',at(2));
 if(s==='summary'){caption('按报名录取',0);caption('临时外卡',at(1));caption('再排种子',at(2));}
}else if(['deadline','queue'].includes(s)){
 panel(35,80,435,540,'报名球员');panel(520,80,425,540,'录取队列');const people=[];
 ['球员甲','球员乙','球员丙','球员丁'].forEach((name,i)=>{const y=190+i*116;const p=person(name,115,y-10);gsap.set(p,{scale:.58});people.push(p);const form=pill('报名',310,y,C.blue,110);show(form,T*(.02+i*.025));move(p,605,y-10,T*(.05+i*.06),Math.min(1.5,T*.12));text(`顺位 ${i+1}`,825,y+8,30,C.sub);});
 const clock=pill(`${d.deadline}截止`,490,700,C.green,320);show(clock,at(1));
 const wall=el('rect',{x:479,y:90,width:8,height:515,rx:4,fill:C.red});show(wall,at(2));
 caption('报名入队',0);caption('提前28天',at(1));caption('常规截止',at(2));
}else if(s==='late_entry'){
 panel(35,80,380,550,'已经报名的候补队列');const eligible=person('下一位',215,230);const outsider=person(d.player,180,700,C.green);const b=board(455,90,.59);const exit=person('退赛',815,610,C.sub);gsap.set(exit,{scale:.7});
 const direct=arrow(265,700,735,475,C.red);show(direct,at(0));const cross=text('×',510,580,96,C.red);show(cross,at(0));
 move(exit,875,720,at(1));tl.to(exit,{opacity:0,duration:1},at(1)+.7);const path=arrow(270,230,b.slots[6].x,b.slots[6].y);show(path,at(2));move(eligible,b.slots[6].x,b.slots[6].y-15,at(2),2);tl.to(eligible,{scale:.58,duration:1},at(2));
 caption('排名够',0);caption('候补递补',at(2));
}else if(s==='schedule'){
 panel(70,80,840,250,'原定六王表演赛');const oct=pill(d.postponed_from,280,230,C.blue,180);const dec=pill(d.postponed_to,720,230,C.sub,180);const path=arrow(410,230,590,230,C.sub);show(path,at(0));move(oct,560,230,at(0));tl.to(oct,{opacity:0,duration:.6},at(0)+1);show(dec,at(0)+.8);
 panel(70,400,840,305,'空出的赛程');const p=person(d.player,225,565,C.green);const dest=pill(d.event,740,565,C.green,220);show(dest,at(1));const route=arrow(320,565,590,565,C.green);show(route,at(1));move(p,545,545,at(2),2);
 caption('表演赛延期',0);caption('两天谈妥',at(2));
}else if(s==='motivation'){
 const court=el('g');el('path',{d:'M160 650 L330 120 H650 L820 650 Z M245 385 H735 M285 255 H695 M490 120 V650 M200 520 H780',fill:'#12394b',stroke:'#83afbd','stroke-width':4},court);
 const p=person(d.player,490,480,C.green);const ball=el('circle',{cx:580,cy:300,r:19,fill:C.green});const points=pill('赛事积分',490,150,C.green,230);const final=pill(d.goal,490,740,C.blue,250);show(points,at(0));show(final,at(2));
 tl.to(ball,{attr:{cx:410,cy:520},duration:2,ease:'sine.inOut',repeat:4,yoyo:true},1);tl.to(p,{x:400,duration:2,ease:'sine.inOut',repeat:4,yoyo:true},1);caption('争取都灵资格',0);caption('再次参赛',at(2));
}else if(['reserved','locals','insert','unused'].includes(s)){
 const b=board(90,50);for(let i=28;i<31;i++)gsap.set(b.slots[i].r,{backgroundColor:'#204d71',borderColor:C.blue});gsap.set(b.slots[31].r,{backgroundColor:'#30441f',borderColor:C.green});
 const labels=d.locals;const local=labels.map((n,i)=>{const p=person(n,210+i*260,690,C.blue);gsap.set(p,{scale:.8});return p;});
 local.forEach((p,i)=>move(p,b.slots[28+i].x,b.slots[28+i].y-15,.8+i*.7,1.6));local.forEach((p,i)=>tl.to(p,{scale:.42,duration:1.5},.8+i*.7));
 const count=pill('32席',490,805,C.sub,140);show(count,0);const wc=pill('3张常规外卡',330,610,C.blue,280);show(wc,.3);const extra=pill(s==='unused'?'预留名额':'额外 A+ 外卡',725,610,C.green,250);show(extra,at(1));
 const player=person(s==='unused'?'候补球员':d.player,s==='unused'?260:820,710,C.green);gsap.set(player,{opacity:0,scale:s==='unused'?.67:.8});show(player,at(1));
 const target=b.slots[31];
 if(s==='unused'){
  const released=pill('名额',target.x,target.y,C.green,125);
  const back=arrow(target.x,target.y+30,220,650,C.green);
  show(released,at(0));show(back,at(0));move(released,220,650,at(1),1.7);
  tl.to(released,{opacity:0,duration:.5},at(1)+1.5);tl.to(back,{opacity:0,duration:.5},at(2));
 }
 const route=arrow(s==='unused'?260:820,700,target.x,target.y+55,C.green);show(route,at(2));move(player,target.x,target.y-16,at(2),2.5);tl.to(player,{scale:.43,duration:2},at(2));tl.to(target.r,{backgroundColor:'#446421',duration:.7},at(2)+1.8);
 if(s==='unused'){caption('外卡未用',0);caption('回到报名队列',at(1));caption('候补入场',at(2));}
 else{caption('三张常规',0);caption('额外一张',at(1));caption('仍是32席',at(2));}
 if(s==='locals')caption('本土三张',0);
}else if(s==='alcaraz'){
 panel(35,80,430,620,d.event);panel(515,80,430,620,d.peer_event);const a=person(d.player,250,250,C.green),b=person(d.peer,730,250,C.blue);
 const ga=pill('外卡通道',250,440,C.green,230),gb=pill('外卡通道',730,440,C.blue,230);show(ga,at(0));show(gb,at(0));move(a,250,540,at(1),2);move(b,730,540,at(1),2);
 const sa=pill(`${d.seed}号种子`,250,760,C.green,220),sb=pill(`${d.peer_seed}号种子`,730,760,C.blue,220);show(sa,at(2));show(sb,at(2));caption('同周加赛',0);caption('外卡入场',at(1));caption('再排种子',at(2));
}
tl.to({}, {duration:.001},T);
window.transitionMotion={horizon:T,kind:'entry_process',scene:s,library:'Renoise vibe-knowledge',components:['tokens','counter','trail','layers','focus']};
window.setTransitionTime=t=>{const clamped=Math.max(0,Math.min(T,Number(t)||0));tl.seek(clamped,false);const note=captions.filter(c=>c.t<=clamped).sort((a,b)=>a.t-b.t).at(-1);document.querySelector('.process-note').textContent=note?note.s:'';renderers.forEach(fn=>fn(clamped));window.processEvidence={time:clamped,scene:s,slots:document.querySelectorAll('.draw-slot').length};return window.processEvidence;};
window.setTransitionTime(0);
'''.replace('__DATA__', _script(data))
    return f'''<!doctype html><meta charset="utf-8"><style>{_font_css()}
*{{box-sizing:border-box;margin:0}}body{{position:relative;width:{w}px;height:{h}px;overflow:hidden;background:{CARD_BACKGROUND_CSS};color:#f4fbf7;font-family:'TL Sans SC',sans-serif}}
.bar{{position:absolute;inset:0 0 auto;height:12px;background:{BRAND_BAR_CSS}}}
.head{{position:absolute;left:70px;right:70px;top:44px;display:flex;align-items:center}}
.brandwrap{{display:flex;align-items:center;gap:14px}}.brandlines{{display:flex;flex-direction:column;gap:2px}}
.brand-icon{{width:52px;height:52px;object-fit:contain}}.brand{{font-family:'TL Display SC';font-size:38px;font-weight:400;letter-spacing:1px}}
.topic{{font-family:'TL Sans SC';font-size:27px;font-weight:700;letter-spacing:1px;color:#bdcde0}}
.abs{{position:absolute}}.cn{{font-family:'TL Sans SC'}}
.process-heading{{position:absolute;top:190px;left:70px;right:70px;font-family:'TL Display SC';font-size:62px;font-weight:400;line-height:1.15;letter-spacing:1px}}
#process-backdrop{{position:absolute;inset:0;pointer-events:none}}#process-world{{position:absolute;left:50px;top:350px;width:980px;height:850px}}#process-stage{{position:absolute;left:0;top:0;width:980px;height:850px;overflow:visible;z-index:2}}.process-label{{font-family:'TL Sans SC';font-weight:400}}
.process-note{{position:absolute;left:70px;right:70px;top:1215px;height:50px;text-align:center;color:#c6f65a;font-size:31px;font-weight:700;white-space:nowrap}}
.handle{{position:absolute;bottom:28px;left:0;right:0;display:flex;align-items:center;justify-content:center;gap:14px;font-size:26px;letter-spacing:3px;color:#bdcde0;opacity:.72}}.handle img{{width:40px;height:40px}}
</style><div class="bar"></div><div class="head"><div class="brandwrap"><img class="brand-icon" src="{_data_uri(ICON)}"><div class="brandlines"><div class="brand">{e(head['brand'])}</div><span class="topic">{e(head['topic'])}</span></div></div></div>
<div id="process-backdrop"></div><h1 class="process-heading">{title}</h1><div id="process-world"><svg id="process-stage" viewBox="0 0 980 850"></svg></div><div class="process-note"></div><div class="handle"><img src="{_data_uri(ICON)}">@网球时差 · TENNIS JETLAG</div>
<script>{gsap}</script><script type="module">import {{tokens as renoiseTokens,counter as renoiseCounter,trail as renoiseTrail,layers as renoiseLayers,focus as renoiseFocus}} from "{know_uri}";try{{{body}}}catch(e){{window.transitionMotionError=String(e.stack||e)}}</script>'''
