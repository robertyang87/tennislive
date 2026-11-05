// vibetennis 大字标准（TYPE）：一级大字＋数据大数字的字体、清晰度、出场动效。各集 r3d/ 里软链接本文件。
// 来路：所有者 2026-11-05「视频里的大字字体也很 low，不精致，出现的时候也没特别的动效，比如粒子汇聚之类的效果」。
// 量过的根子：思源黑体只装了 Regular/Bold，「900」退成普通 Bold；字先画在 120~150 px 的 canvas 上再放大，发虚；
// 3D 数字用 Three.js 自带的示例字体 helvetiker；出场只有透明度淡入。
//
// 用法（scene.js）：
//   import { TYPE, loadTypeFonts, makeTitle } from './typefx.js';
//   await loadTypeFonts();                       // READY 之前
//   const q=makeTitle(THREE,'是线，改变了网球吗？',{tier:'title',color:'#fff',glow:GOLD,size:1.0});
//   hud(q,0,2.0); q.update(u, IN, OUT);           // IN：开始汇聚的时刻；OUT：开始散开的时刻（不散就给 Infinity）
// 约束：粒子是叠加发光，亮度乘 GLOW.k（光晕标准）；汇聚和散开都是连续运动、不闪白（转场与运镜标准，motion_check）。
export const TYPE={
  // 一级大字（钩子问句、段落标题、公式、片尾问句）
  title:{ family:'"VT Title","Noto Sans CJK SC",sans-serif', weight:900, px:300, track:-0.02, en:'"Inter Display","Inter",sans-serif', enWeight:900 },
  // 数据大数字（39.5%、95%……）
  number:{ family:'"Inter Display","Inter",sans-serif', weight:900, px:300, track:-0.01 },
  // 出场：粒子汇聚 IN 秒（逐字从左到右错开 STAGGER）；落定后实体字淡入、粒子熄灭；一道光扫过；退场散成粒子 OUT 秒
  IN:1.25, STAGGER:0.35, OUTDUR:0.8, SWEEP:0.9, particles:6000, spread:[2.2,5.0], pointPx:5.5,
};
// 一级大字的中文字体：2026-11-05 出过三选一样片（A 得意黑 / B 思源宋体 Black / C 思源黑体 Black），定 C——和所有者选的封面 B 同一款字。
// ?type=A|B 仍可切回去对比。
const TITLE_FONTS={ A:{url:'./fonts/SmileySans-Oblique.ttf', weight:'400', name:'得意黑'},
                    B:{url:'./fonts/NotoSerifSC-Black-sub.ttf', weight:'900', name:'思源宋体 Black'},
                    C:{url:'./fonts/NotoSansSC-Black-sub.ttf', weight:'900', name:'思源黑体 Black'} };
export const TITLE_FONT=(new URLSearchParams(location.search).get('type')||'C').toUpperCase();
export async function loadTypeFonts(){
  const f=TITLE_FONTS[TITLE_FONT]; const ff=new FontFace('VT Title',`url(${f.url})`,{weight:'100 900'});
  document.fonts.add(await ff.load());
  await Promise.all([document.fonts.load('900 100px "VT Title"','是'),document.fonts.load('900 100px "Inter Display"','0')]);
}
const ss=(a,b,x)=>{ const t=Math.min(1,Math.max(0,(x-a)/(b-a))); return t*t*(3-2*t); };
function hash(i,k){ const x=Math.sin(i*12.9898+k*78.233)*43758.5453; return x-Math.floor(x); }

// 把一行字画进高分辨率 canvas：竖向渐变（亮白→略冷的银）＋一圈深色细描边＋很淡的辉光。返回 canvas 与它在世界里的宽高。
function drawText(str,{tier='title',color='#ffffff',glow='rgba(255,194,74,0.9)',accent=null,accentColor='#ffc24a'}){
  const T=TYPE[tier]; const cjk=/[㐀-鿿＀-￯]/.test(str);
  const fam=tier==='title'&&!cjk?T.en:T.family; const wt=tier==='title'&&!cjk?T.enWeight:T.weight; const px=T.px;
  const c=document.createElement('canvas'); let g=c.getContext('2d'); const font=`${wt} ${px}px ${fam}`; g.font=font; g.letterSpacing=`${T.track*px}px`;
  const w=Math.ceil(g.measureText(str).width)+px*0.5, h=Math.ceil(px*1.45); c.width=w; c.height=h; g=c.getContext('2d');
  g.font=font; g.letterSpacing=`${T.track*px}px`; g.textAlign='center'; g.textBaseline='middle'; const y=h*0.53;
  g.shadowColor=glow; g.shadowBlur=px*0.05; g.globalAlpha=0.22;   // 辉光只留一层很淡的，字边要锐（封面 B 是不带辉光的实字）
  g.fillStyle=color; g.fillText(str,w/2,y); g.globalAlpha=1; g.shadowBlur=0;
  g.lineJoin='round'; g.lineWidth=px*0.045; g.strokeStyle='rgba(4,8,16,0.65)'; g.strokeText(str,w/2,y);
  const gr=g.createLinearGradient(0,y-px*0.5,0,y+px*0.5); gr.addColorStop(0,'#ffffff'); gr.addColorStop(0.55,color); gr.addColorStop(1,'#b9c6d8');
  g.fillStyle=gr; g.fillText(str,w/2,y);
  if(accent&&str.includes(accent)){   // 重点字换品牌金（同封面 B「是【线】，改变了网球吗？」）：按前缀宽度定位、覆盖重画
    const i=str.indexOf(accent), x0=w/2-g.measureText(str).width/2+g.measureText(str.slice(0,i)).width;
    g.textAlign='left'; const ga=g.createLinearGradient(0,y-px*0.5,0,y+px*0.5); ga.addColorStop(0,'#ffe08a'); ga.addColorStop(1,accentColor);
    g.fillStyle=ga; g.fillText(accent,x0,y); g.textAlign='center'; }
  return {c,w,h};
}
// 从字形上采样粒子的落点（只取字心：alpha 高且不在描边上）
function sample(c,n){
  const g=c.getContext('2d'); const {width:W,height:H}=c; const d=g.getImageData(0,0,W,H).data; const pts=[]; const step=Math.max(2,Math.round(Math.sqrt(W*H/(n*6))));
  for(let y=0;y<H;y+=step) for(let x=0;x<W;x+=step){ const i=(y*W+x)*4; if(d[i+3]>200 && d[i]+d[i+1]+d[i+2]>300) pts.push([x,y]); }
  const out=[]; for(let i=0;i<n;i++){ const p=pts[Math.floor(hash(i,3)*pts.length)]||[W/2,H/2]; out.push([p[0]+(hash(i,4)-0.5)*step,p[1]+(hash(i,5)-0.5)*step]); } return out;
}
const PVS=`attribute vec3 aStart; attribute vec3 aCtrl; attribute float aDelay; attribute float aSeed;
uniform float uIn; uniform float uOut; uniform float uPx; uniform float uStag; varying float vA; varying float vSeed;
vec3 bez(vec3 a,vec3 b,vec3 c,float t){ float s=1.0-t; return s*s*a+2.0*s*t*b+t*t*c; }
void main(){
  float k=clamp((uIn-aDelay)/(1.0-uStag),0.0,1.0); float e=1.0-pow(1.0-k,3.0);
  vec3 p=bez(aStart,aCtrl,position,e);
  float o=clamp(uOut,0.0,1.0); vec3 drift=normalize(aStart-position+vec3(0.0,0.6,0.0))*(o*o*1.8)+vec3(0.0,o*0.5,0.0);
  p+=drift*(0.6+aSeed);
  vA=smoothstep(0.0,0.25,k)*(1.0-smoothstep(0.8,1.15,uIn+0.0*k))   // 汇聚时亮，实体字出来后熄灭
     +smoothstep(0.0,0.08,o)*(1.0-smoothstep(0.35,1.0,o));         // 散开时重新亮起再熄灭
  vSeed=aSeed; vec4 mv=modelViewMatrix*vec4(p,1.0); gl_Position=projectionMatrix*mv;
  gl_PointSize=uPx*(0.6+aSeed*0.8)*(9.0/max(0.5,-mv.z)); }`;
const PFS=`uniform vec3 uC1; uniform vec3 uC2; uniform float uK; varying float vA; varying float vSeed;
void main(){ vec2 q=gl_PointCoord-0.5; float r=dot(q,q); if(r>0.25) discard; float f=exp(-r*10.0);
  gl_FragColor=vec4(mix(uC1,uC2,vSeed)*f*uK*1.6, vA*f); }`;
const TVS=`varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;
const TFS=`uniform sampler2D map; uniform float uOp; uniform float uSweep; varying vec2 vUv;
void main(){ vec4 c=texture2D(map,vUv); float band=exp(-pow((vUv.x-uSweep)*6.0,2.0))*0.35*c.a;   // 一道斜光扫过
  gl_FragColor=vec4(c.rgb+band, c.a*uOp); }`;
export function makeTitle(THREE,str,o={}){
  const {size=1,color='#ffffff',glow='rgba(255,194,74,0.9)',tier='title',k=0.5,c1='#ffd27a',c2='#7fe4ff',group=null,n=TYPE.particles,accent=null}=o;
  const {c,w,h}=drawText(str,{tier,color,glow,accent}); const HU=size*0.87, WU=HU*w/h;   // 字高占比和旧 textSprite 一致（120/200）
  const g=new THREE.Group();
  const tex=new THREE.CanvasTexture(c); tex.colorSpace=THREE.SRGBColorSpace; tex.anisotropy=8;
  const tm=new THREE.ShaderMaterial({uniforms:{map:{value:tex},uOp:{value:0},uSweep:{value:-1}},vertexShader:TVS,fragmentShader:TFS,transparent:true,depthTest:false,depthWrite:false});
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(WU,HU),tm); mesh.renderOrder=21; g.add(mesh);
  const P=sample(c,n), pos=new Float32Array(n*3), st=new Float32Array(n*3), ct=new Float32Array(n*3), de=new Float32Array(n), sd=new Float32Array(n);
  const [r0,r1]=TYPE.spread;
  for(let i=0;i<n;i++){ const x=(P[i][0]/w-0.5)*WU, y=(0.5-P[i][1]/h)*HU; pos.set([x,y,0],i*3);
    const th=hash(i,1)*Math.PI*2, ph=(hash(i,2)-0.5)*1.2, r=r0+(r1-r0)*hash(i,6);
    const sx=x+Math.cos(th)*Math.cos(ph)*r, sy=y+Math.sin(ph)*r*0.7, sz=Math.sin(th)*Math.cos(ph)*r*0.8; st.set([sx,sy,sz],i*3);
    ct.set([(sx+x)/2-(sy-y)*0.35,(sy+y)/2+(sx-x)*0.35,sz*0.4],i*3);   // 控制点偏到一侧：粒子走弧线、整体带一点旋涡
    de[i]=(x/WU+0.5)*TYPE.STAGGER+hash(i,7)*0.06; sd[i]=hash(i,8); }
  const pg=new THREE.BufferGeometry(); pg.setAttribute('position',new THREE.BufferAttribute(pos,3)); pg.setAttribute('aStart',new THREE.BufferAttribute(st,3));
  pg.setAttribute('aCtrl',new THREE.BufferAttribute(ct,3)); pg.setAttribute('aDelay',new THREE.BufferAttribute(de,1)); pg.setAttribute('aSeed',new THREE.BufferAttribute(sd,1));
  const pm=new THREE.ShaderMaterial({uniforms:{uIn:{value:0},uOut:{value:0},uPx:{value:TYPE.pointPx},uStag:{value:TYPE.STAGGER},uK:{value:k},
    uC1:{value:new THREE.Color(c1)},uC2:{value:new THREE.Color(c2)}},vertexShader:PVS,fragmentShader:PFS,transparent:true,depthTest:false,depthWrite:false,blending:THREE.AdditiveBlending});
  const pts=new THREE.Points(pg,pm); pts.renderOrder=22; pts.frustumCulled=false; g.add(pts);
  if(group) group.add(g);
  const notext=new URLSearchParams(location.search).get('notext');
  const obj={g,mesh,pts,isSprite:false,w:WU,h:HU,
    // u：本段时间；IN：开始汇聚；OUT：开始散开（不散给 Infinity）；mul：外部再乘一层透明度（切镜头时）
    update(u,IN,OUT=Infinity,mul=1){
      const a=(u-IN)/TYPE.IN, b=(u-OUT)/TYPE.OUTDUR;
      pm.uniforms.uIn.value=a; pm.uniforms.uOut.value=Math.max(0,b);
      tm.uniforms.uOp.value=(notext?0:1)*mul*ss(0.72,1.0,a)*(1-ss(0.0,0.45,b));
      tm.uniforms.uSweep.value=-0.3+1.6*ss(0.95,0.95+TYPE.SWEEP/TYPE.IN,a);
      pts.visible=!notext && mul>0.003 && a>0 && (a<1.2 || (b>0&&b<1.05)); pm.uniforms.uK.value=k*mul;
      g.visible=a>0 && b<1.05; return this; },
  };
  return obj;
}
