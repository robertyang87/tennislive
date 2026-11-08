// vibetennis EP11 阻力危机：网球为什么偏偏要长毛——埃菲尔 1912 年发现的阻力危机让高尔夫用凹坑把阻力砍半、让足球在临界速度乱飘；网球的绒毛却把它挡在门外，阻力一直大、一直稳。
// 理论与上屏数字的出处见 papers/vibetennis-fuzz-2026/sources.md（两源规则）；镜头与转场见同目录 storyboard.md。
// 通用底座（夜空、光点、全息字、3D 字、球场、看台、全息人体、后期）沿用 EP06–EP10；风洞烟线、Cd–Re 曲线、四种球、埃菲尔铁塔为本集新做（aero.js）。流场为示意，画面标「示意」。

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { FullScreenQuad } from 'three/addons/postprocessing/Pass.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';
import { Lensflare, LensflareElement } from 'three/addons/objects/Lensflare.js';
import { FontLoader } from 'three/addons/loaders/FontLoader.js';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';
import { TL } from './shots.js';
import { TTFLoader } from 'three/addons/loaders/TTFLoader.js';
import { TYPE, loadTypeFonts, makeTitle } from './typefx.js';   // 大字标准（字体＋粒子汇聚），engine/typefx.js
const Q=new URLSearchParams(location.search);
const W=+(Q.get('w')||1920), H=+(Q.get('h')||1080), LANG=Q.get('lang')||'zh';
const T=(zh,en)=>LANG==='en'?en:zh;
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(1); renderer.setSize(W,H);
renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.05;
renderer.outputColorSpace=THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);
const scene=new THREE.Scene(); scene.background=new THREE.Color(0x02040a);
scene.environment=new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(),0.04).texture; scene.environmentIntensity=0.12;
const camera=new THREE.PerspectiveCamera(38,W/H,0.05,12000);

const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const ss=(a,b,x)=>{ const k=clamp((x-a)/(b-a)); return k*k*(3-2*k); };
const lerp=(a,b,k)=>a+(b-a)*k;
let fseed=7007; const frnd=()=>{fseed=(fseed*48271)%2147483647;return fseed/2147483647;};
const gauss=()=>{ let u=0,v=0; while(!u) u=frnd(); v=frnd(); return Math.sqrt(-2*Math.log(u))*Math.cos(6.2831853*v); };
const C=h=>new THREE.Color(h);

// ---------- 段落配色（按情绪） ----------
const PAL={
  hook:     {top:0x05030f,hz:0x1a1048,vi:0x3a0a3a,a:0x30e8ff,b:0xffc24a,c:0xffffff},   // 电光青＋金
  gut:      {top:0x0b0602,hz:0x3a2208,vi:0x2a1406,a:0xffb347,b:0xffe2a0,c:0xffffff},   // 羊肠线琥珀
  synth:    {top:0x030812,hz:0x0b2a50,vi:0x0a2030,a:0xe8f6ff,b:0x4fe3ff,c:0xffffff},   // 尼龙冰白
  spaghetti:{top:0x0c0306,hz:0x3a0d12,vi:0x401018,a:0xff5a4a,b:0xffb199,c:0xffffff},   // 禁令红
  poly:     {top:0x04040e,hz:0x14163a,vi:0x1a1a2e,a:0xc9d6ff,b:0x7c83ff,c:0xffffff},   // 聚酯银＋靛
  power:    {top:0x020c0a,hz:0x063828,vi:0x062a2a,a:0x34f5a8,b:0x4fe3ff,c:0xeafff6},   // 翡翠
  tension:  {top:0x0c0504,hz:0x3a1608,vi:0x0a3024,a:0xff7a3d,b:0x34f5a8,c:0xffffff},   // 橙红
  tactics:  {top:0x06041a,hz:0x1d1250,vi:0x2b0d55,a:0xa78bfa,b:0x6fa8ff,c:0xf0e6ff},   // 紫罗兰
  end:      {top:0x050505,hz:0x2a2008,vi:0x08202a,a:0xffc24a,b:0x4fe3ff,c:0xffffff}};  // 金＋青

// ---------- 背景：夜空（颜色随段落）、星点、微尘、全息地网 ----------
// ---------- 光晕全局标准（所有者 2026-11-05「所有动效里的光晕都很亮……设定好一个全局标准」，docs/vibetennis.md「光晕标准」）----------
// 泛光 strength ≤ 0.25 / radius ≤ 0.35 / threshold ≥ 0.92；叠加发光（光点精灵、光环）一律乘 GLOW_K；
// 自发光 emissiveIntensity：彩色件 ≤ 0.35，白／近白件 ≤ 0.15（深色底色的自发光只提亮暗部，不受限）。成片 glow_check.py 量化把关。
const GLOW={bloom:[0.22,0.3,0.93], k:0.5, emissive:0.35, emissiveWhite:0.15};
const skyMat=new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,uniforms:{uTop:{value:C(0x05030f)},uHz:{value:C(0x1a1048)},uVi:{value:C(0x3a0a3a)}},
  vertexShader:`varying vec3 vD; void main(){ vD=normalize(position); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,
  fragmentShader:`varying vec3 vD; uniform vec3 uTop,uHz,uVi; void main(){ float h=vD.y; float g=exp(-abs(h+0.02)*6.0); float side=0.5+0.5*vD.x; gl_FragColor=vec4(uTop+uHz*g+uVi*g*g*side*0.8,1.);} `});
const sky=new THREE.Mesh(new THREE.SphereGeometry(9000,48,24),skyMat); sky.frustumCulled=false; scene.add(sky);
const glowTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d');
  const gr=g.createRadialGradient(64,64,0,64,64,64); gr.addColorStop(0,'rgba(255,255,255,1)'); gr.addColorStop(0.15,'rgba(255,255,255,0.6)'); gr.addColorStop(0.45,'rgba(255,255,255,0.12)'); gr.addColorStop(1,'rgba(255,255,255,0)');
  g.fillStyle=gr; g.fillRect(0,0,128,128); return new THREE.CanvasTexture(c); })();
function glowSprite(color,size,op=1,group=scene){ const s=new THREE.Sprite(new THREE.SpriteMaterial({map:glowTex,color:new THREE.Color(color).multiplyScalar(GLOW.k),transparent:true,opacity:op,blending:THREE.AdditiveBlending,depthWrite:false})); s.scale.set(size,size,1); group.add(s); return s; }
const ringTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=256; const g=c.getContext('2d'); g.strokeStyle='white';
  g.lineWidth=9; g.beginPath(); g.arc(128,128,104,0,Math.PI*2); g.stroke(); g.globalAlpha=0.35; g.lineWidth=3; g.beginPath(); g.arc(128,128,122,0,Math.PI*2); g.stroke(); return new THREE.CanvasTexture(c); })();
function flatRing(color,group=scene){ const m=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({map:ringTex,color:new THREE.Color(color).multiplyScalar(GLOW.k),transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide})); m.rotation.x=-Math.PI/2; group.add(m); return m; }
const allClouds=[];
function cloud(n,size,maxPx,group=scene,sparkle=0){
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(n*3),3));
  g.setAttribute('color',new THREE.Float32BufferAttribute(new Float32Array(n*3),3));
  g.setAttribute('alpha',new THREE.Float32BufferAttribute(new Float32Array(n),1));
  const ph=new Float32Array(n); for(let i=0;i<n;i++) ph[i]=frnd()*6.283; g.setAttribute('phase',new THREE.Float32BufferAttribute(ph,1));
  const m=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uSize:{value:size},uOp:{value:1},uMax:{value:maxPx},uH:{value:H},uT:{value:0},uSpark:{value:sparkle}},
   vertexShader:`attribute vec3 color; attribute float alpha; attribute float phase; varying vec3 vC; varying float vA; uniform float uSize,uMax,uH,uT,uSpark; void main(){ vC=color; vA=alpha*(1.0-uSpark*0.5+uSpark*0.5*sin(uT*3.0+phase*7.0)); vec4 mv=modelViewMatrix*vec4(position,1.); float px=uSize*uH*0.5*projectionMatrix[1][1]/-mv.z; vA*=clamp(px/max(px,uMax),0.25,1.0); gl_PointSize=clamp(px,1.0,uMax); gl_Position=projectionMatrix*mv; }`,
   fragmentShader:`uniform float uOp; varying vec3 vC; varying float vA; void main(){ float d=length(gl_PointCoord-0.5); float ta=exp(-d*d*18.0)*(1.0-smoothstep(0.4,0.5,d)); gl_FragColor=vec4(vC*ta*uOp*vA, ta*uOp*vA);} `});
  const p=new THREE.Points(g,m); p.frustumCulled=false; group.add(p); allClouds.push(p); return p; }
function cset(p,i,x,y,z,r,gg,b,a){ const P=p.geometry.attributes.position.array, Cc=p.geometry.attributes.color.array, A=p.geometry.attributes.alpha.array; P[i*3]=x;P[i*3+1]=y;P[i*3+2]=z; Cc[i*3]=r;Cc[i*3+1]=gg;Cc[i*3+2]=b; A[i]=a; }
function cdone(p){ for(const k of ['position','color','alpha']) p.geometry.attributes[k].needsUpdate=true; }
function chide(p){ p.geometry.attributes.alpha.array.fill(0); p.geometry.attributes.alpha.needsUpdate=true; }
const stars=cloud(8000,10,3); { for(let i=0;i<8000;i++){ const r=3200+frnd()*3800, th=frnd()*Math.PI*2, ph=Math.acos(2*frnd()-1); const k=0.35+frnd()*0.6, w=frnd();
  cset(stars,i,r*Math.sin(ph)*Math.cos(th),Math.abs(r*Math.cos(ph))*0.8+60,r*Math.sin(ph)*Math.sin(th),k*(0.7+0.3*w),k*(0.75+0.2*w),k,1);} cdone(stars); }
const motes=cloud(3000,0.04,3,scene,0.6); const MOTE=[]; for(let i=0;i<3000;i++) MOTE.push([(frnd()-0.5)*40,frnd()*16,(frnd()-0.5)*40,frnd()]);
let MOTE_SPEED=1;
function setMotes(t,col){ const c=camera.position; for(let i=0;i<3000;i++){ const m=MOTE[i]; const k=0.25+0.35*m[3];
  cset(motes,i,c.x+m[0]+Math.sin(t*0.2*MOTE_SPEED+i)*0.6,c.y-5+((m[1]+t*0.25*MOTE_SPEED*(0.3+m[3]))%16),c.z-18+m[2],k*col.r,k*col.g,k*col.b,1); } cdone(motes); }
scene.add(new THREE.HemisphereLight(0xc4d8ff,0x1a2230,1.2));
const sun=new THREE.DirectionalLight(0xffffff,1.6); sun.position.set(30,60,40); scene.add(sun);
const rimL=new THREE.PointLight(0xff3fd0,0,40,1.5); scene.add(rimL); const rimR=new THREE.PointLight(0x30e8ff,0,40,1.5); scene.add(rimR);
{ const m=new THREE.ShaderMaterial({transparent:true,depthWrite:false,uniforms:{uC:{value:C(0x3f8cff)}},
  vertexShader:`varying vec3 vW; void main(){ vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }`,
  fragmentShader:`varying vec3 vW; uniform vec3 uC; float g(vec2 p,float s){ vec2 q=abs(fract(p/s-0.5)-0.5)/fwidth(p/s); return 1.-min(min(q.x,q.y),1.);} void main(){ float d=length(vW.xz); float k=g(vW.xz,2.)*0.3+g(vW.xz,10.)*0.6; float f=exp(-d*0.02); gl_FragColor=vec4(uC*k*f, k*f*0.5);} `});
  const p=new THREE.Mesh(new THREE.PlaneGeometry(600,600),m); p.rotation.x=-Math.PI/2; p.position.y=-0.03; scene.add(p); scene.userData.grid=m; }

// ---------- 文字：中文用精灵（全息发光字），关键数字用 3D 立体字 ----------
function textSprite(str,{color='#ffffff',size=1,font='700 120px "Noto Sans CJK SC","Inter",sans-serif',glow='rgba(120,200,255,0.9)',plate=false}={},group=scene){
  const c=document.createElement('canvas'); const g=c.getContext('2d'); g.font=font; const w=Math.ceil(g.measureText(str).width)+80; c.width=w; c.height=200;
  g.font=font; g.textAlign='center'; g.textBaseline='middle';
  if(plate){ g.fillStyle='rgba(6,10,20,0.78)'; g.beginPath(); g.roundRect(8,40,w-16,124,24); g.fill(); }   // 压在浅色纸面（专利图）上的字垫一块深底
  // 字的光晕收小收淡、加一圈深色细描边，字本身略低于泛光阈值——所有者 2026-11-05「字体的光晕太亮，感觉看不清楚真正的文字」
  g.globalAlpha=0.45; g.shadowColor=glow; g.shadowBlur=14; g.fillStyle=color; g.fillText(str,w/2,104); g.globalAlpha=1; g.shadowBlur=0;
  g.lineJoin='round'; g.lineWidth=7; g.strokeStyle='rgba(0,0,0,0.6)'; g.strokeText(str,w/2,104); g.fillText(str,w/2,104);
  const tex=new THREE.CanvasTexture(c); tex.colorSpace=THREE.SRGBColorSpace;
  const s=new THREE.Sprite(new THREE.SpriteMaterial({map:tex,transparent:true,depthWrite:false,opacity:0,color:0xd8d8d8,depthTest:false})); s.renderOrder=20; /* 字永远压在 3D 物体上面，不被球拍挡住 */ s.scale.set(size*w/200,size,1); group.add(s); return s; }
const NOTEXT=!!Q.get('notext');   // 封面底图：3D 里的字全部不出，标题由封面脚本自己排
const op=(s,v)=>{ s.material.opacity=NOTEXT?0:v; };
let FONT=null; const FONT_READY=new Promise((res,rej)=>Object.assign(new TTFLoader(),{reversed:true}).load('./fonts/InterDisplay-Black.otf',j=>{ FONT=new FontLoader().parse(j); res(); },undefined,rej));   // 大字标准：3D 数字用 Inter Display Black，不再用 Three.js 自带的示例字体 helvetiker
const text3D={};
function t3d(key,str,color,size=1,group=scene){ // 3D 立体数字：金属挤出＋发光描边
  if(text3D[key]) return text3D[key];
  const geo=new TextGeometry(str,{font:FONT,size,depth:size*0.22,curveSegments:8,bevelEnabled:true,bevelThickness:size*0.04,bevelSize:size*0.025,bevelSegments:3}); geo.center();
  const m=new THREE.Mesh(geo,new THREE.MeshPhysicalMaterial({color:0x0c1018,metalness:0.9,roughness:0.18,clearcoat:1,emissive:C(color),emissiveIntensity:GLOW.emissive,transparent:true,opacity:0}));
  const e=new THREE.LineSegments(new THREE.EdgesGeometry(geo,30),new THREE.LineBasicMaterial({color,transparent:true,opacity:0,blending:THREE.AdditiveBlending})); m.add(e);
  const g=new THREE.Group(); g.add(m); group.add(g); text3D[key]={g,m,e}; return text3D[key]; }
function t3op(o,v){ if(NOTEXT) v=0; o.m.material.opacity=v; o.e.material.opacity=v*0.8; o.g.visible=v>0.003; }

// ---------- 球场（ITF 尺寸，蓝色、带清漆反光） ----------
const L=23.77/2, DW=10.97/2, SW=8.23/2, SL=6.40;
const courtG=new THREE.Group(); scene.add(courtG);
{ const PX=60, FW=18, FL=36, TW=FW*PX, TH=FL*PX;
  const c=document.createElement('canvas'); c.width=TW; c.height=TH; const g=c.getContext('2d');
  g.fillStyle='#14467f'; g.fillRect(0,0,TW,TH); g.fillStyle='#1b5aa3'; g.fillRect(TW/2-DW*PX,TH/2-L*PX,DW*2*PX,L*2*PX);
  for(let i=0;i<40000;i++){ g.fillStyle=frnd()<0.5?'rgba(255,255,255,0.025)':'rgba(0,0,0,0.05)'; g.fillRect(frnd()*TW,frnd()*TH,1.5,1.5); }
  const cx=TW/2, cy=TH/2; g.strokeStyle='#eef8ff'; g.lineWidth=0.05*PX;
  const R=(x0,y0,x1,y1)=>{ g.beginPath(); g.moveTo(cx+x0*PX,cy+y0*PX); g.lineTo(cx+x1*PX,cy+y1*PX); g.stroke(); };
  R(-DW,-L,DW,-L); R(-DW,L,DW,L); R(-DW,-L,-DW,L); R(DW,-L,DW,L); R(-SW,-L,-SW,L); R(SW,-L,SW,L);
  R(-SW,-SL,SW,-SL); R(-SW,SL,SW,SL); R(0,-SL,0,SL); R(0,-L,0,-L+0.10); R(0,L,0,L-0.10);
  const tex=new THREE.CanvasTexture(c); tex.colorSpace=THREE.SRGBColorSpace; tex.anisotropy=8;
  const m=new THREE.Mesh(new THREE.PlaneGeometry(FW,FL),new THREE.MeshPhysicalMaterial({map:tex,roughness:0.7,metalness:0.0,clearcoat:0.3,clearcoatRoughness:0.4,emissive:0x082650,emissiveIntensity:0.22,transparent:true}));
  m.rotation.x=-Math.PI/2; m.renderOrder=-1; courtG.add(m); courtG.userData.mat=m.material; // 场地先画：否则半透明场地会盖住后画的光柱
  const net=new THREE.Group(); courtG.add(net);
  const np=new THREE.Mesh(new THREE.PlaneGeometry(DW*2+1.8,1.0),new THREE.MeshBasicMaterial({color:0xbfe6ff,transparent:true,opacity:0.16,side:THREE.DoubleSide,blending:THREE.AdditiveBlending,depthWrite:false})); np.position.set(0,0.5,0); net.add(np);
  const band=new THREE.Mesh(new THREE.BoxGeometry(DW*2+1.8,0.07,0.02),new THREE.MeshStandardMaterial({color:0xffffff,emissive:0xffffff,emissiveIntensity:GLOW.emissiveWhite})); band.position.set(0,0.99,0); net.add(band);
  const gridL=[]; for(let x=-DW-0.9;x<=DW+0.9;x+=0.25){ gridL.push(x,0,0,x,0.96,0); } for(let y=0.1;y<0.96;y+=0.2){ gridL.push(-DW-0.9,y,0,DW+0.9,y,0); }
  const gg=new THREE.BufferGeometry(); gg.setAttribute('position',new THREE.Float32BufferAttribute(gridL,3));
  net.add(new THREE.LineSegments(gg,new THREE.LineBasicMaterial({color:0x9fd8ff,transparent:true,opacity:0.22,blending:THREE.AdditiveBlending})));
  for(const s of [-1,1]){ const post=new THREE.Mesh(new THREE.CylinderGeometry(0.05,0.05,1.07,12),new THREE.MeshStandardMaterial({color:0xdde8f0,metalness:0.7,roughness:0.25})); post.position.set(s*(DW+0.914),0.535,0); net.add(post); }
}
// 体积光：球场上方几束斜射的光柱
const beamMat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,uniforms:{uC:{value:C(0x9fd8ff)},uOp:{value:0}},
  vertexShader:`varying float vY; varying vec2 vUv; void main(){ vUv=uv; vY=position.y; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,
  fragmentShader:`varying vec2 vUv; uniform vec3 uC; uniform float uOp; void main(){ float a=pow(vUv.y,1.6)*(0.5+0.5*sin(vUv.x*6.283*3.0))*0.6+pow(vUv.y,3.0)*0.4; gl_FragColor=vec4(uC*a*uOp,a*uOp);} `});
const beams=[[-9,26,-4],[9,26,-4],[-9,26,7],[9,26,7]].map(([x,y,z])=>{ const m=new THREE.Mesh(new THREE.CylinderGeometry(0.4,5.5,30,32,1,true),beamMat); m.position.set(x*0.6,y*0.5,z); m.lookAt(0,0,z*0.4); m.rotateX(Math.PI/2); scene.add(m); return m; });

// ---------- 粗光线（Line2）：发球轨迹、准星、比例条 ----------
const lineMats=[];
function fatLine(color,width,dashed=false){ const g=new LineGeometry(); g.setPositions([0,0,0,0,0.01,0]);
  const m=new LineMaterial({color,linewidth:width,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false,dashed,dashSize:0.35,gapSize:0.2,worldUnits:false}); m.resolution.set(W,H); lineMats.push(m);
  const l=new Line2(g,m); l.frustumCulled=false; scene.add(l); return l; }
function setLine(l,pts){ const a=[]; for(const p of pts) a.push(p.x,p.y,p.z); l.geometry.dispose(); l.geometry=new LineGeometry(); l.geometry.setPositions(a); if(l.material.dashed) l.computeLineDistances(); }


// ---------- 球（带接缝纹理，看得出转） ----------
const ballTex=(()=>{ const c=document.createElement('canvas'); c.width=512; c.height=256; const g=c.getContext('2d');
  g.fillStyle='#d6ee3a'; g.fillRect(0,0,512,256); for(let i=0;i<6000;i++){ g.fillStyle=frnd()<0.5?'rgba(255,255,255,0.08)':'rgba(80,90,0,0.08)'; g.fillRect(frnd()*512,frnd()*256,2,2); }
  g.strokeStyle='#ffffff'; g.lineWidth=10; g.beginPath(); for(let x=0;x<=512;x+=4){ const y=128+70*Math.sin(x/512*Math.PI*4); x?g.lineTo(x,y):g.moveTo(x,y); } g.stroke();
  const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; return t; })();
function makeBall(r,group=scene){ const m=new THREE.Mesh(new THREE.SphereGeometry(r,48,32),new THREE.MeshPhysicalMaterial({map:ballTex,roughness:0.75,sheen:1,sheenColor:new THREE.Color(0xf6ff9a),emissive:0x2a3200,emissiveIntensity:0.25})); group.add(m); const gl=glowSprite(0xeaff80,r*5,0.35,group); return {m,gl,r}; }


// ==================== EP11 阻力危机：本集物件 ====================
// 比例：特写里球放大成半径 1（画面标「放大示意」）；场地镜头里球按 1 单位 = 1 m 画真实尺寸附近。
// 所有上屏数字的出处见 papers/vibetennis-ball-2026/sources.md（两源规则）；示意的形状都在画面上标「示意」。
const GOLD='rgba(255,194,74,0.95)', CYAN='rgba(79,227,255,0.95)', RED='rgba(255,90,74,0.95)', VIO='rgba(167,139,250,0.95)', MINT='rgba(52,245,168,0.95)', LIME='rgba(214,238,58,0.95)';
const TT={}; const tx=(k,s,o={},grp=scene)=>TT[k]||(TT[k]=textSprite(s,o,grp));
const TITLE_DIM=0.86;   // 光晕标准：纯白大字压到 86%；另加 0.2 s 淡入（同 EP08，motion_check 门槛 12）
const TB={}; const bt=(k,s,o={})=>TB[k]||(TB[k]=(t=>{ const up=t.update.bind(t); t.update=(u,IN,OUT=Infinity,mul=1)=>up(u,IN,OUT,mul*TITLE_DIM*ss(IN,IN+0.2,u)); return t; })(makeTitle(THREE,s,Object.assign({k:GLOW.k,group:scene},o))));   // 一级大字：TYPE 标准（engine/typefx.js）
const HUDQ=[];
function hud(o,x,y,d=9){ HUDQ.push([o,x,y,d]); return o; }
function flushHud(){ camera.updateMatrixWorld(); for(const [o,x,y,d] of HUDQ){ const v=new THREE.Vector3(x,y,-d).applyQuaternion(camera.quaternion).add(camera.position); if(o.isSprite) o.position.copy(v); else { o.g.position.copy(v); o.g.quaternion.copy(camera.quaternion); } } HUDQ.length=0; }
// 字的安全区：画面内、底部字幕带（y>880）以上、顶部品牌带（y<120）以下。每帧在机位定下来之后把出界的 3D 字挪回来（太宽的先缩），
// 由下往上排、横向重叠的互相让位——比逐条手调坐标稳：机位一动、字一改，都不会再出画
function layoutText(){ camera.updateMatrixWorld(); const f=1920/W, R=new THREE.Vector3(1,0,0).applyQuaternion(camera.quaternion), U=new THREE.Vector3(0,1,0).applyQuaternion(camera.quaternion), F=new THREE.Vector3(0,0,-1).applyQuaternion(camera.quaternion);
  const tanh=Math.tan(THREE.MathUtils.degToRad(camera.fov/2)); const its=[];
  for(const k in TT){ const s=TT[k]; if(!s.userData.bs) s.userData.bs=s.scale.clone(); s.scale.copy(s.userData.bs); if(!s.visible||s.material.opacity<0.004||s.userData.free) continue;
    const p=new THREE.Vector3(); s.getWorldPosition(p); const dist=p.clone().sub(camera.position).dot(F); if(dist<0.2) continue;
    const ppx=2*dist*tanh/1080;  // 每个（1080 制）像素对应的世界长度
    const q=p.clone().project(camera); let cx=(q.x*0.5+0.5)*1920, cy=(1-(q.y*0.5+0.5))*1080; let w=s.scale.x/ppx, h=s.scale.y*0.7/ppx;
    if(w>1760){ const k2=1760/w; s.scale.multiplyScalar(k2); w*=k2; h*=k2; }
    its.push({s,p,ppx,cx,cy,w,h,dx:0,dy:0}); }
  its.sort((a,b)=>b.cy-a.cy); const placed=[]; window._LT=its;
  for(const it of its){ let lim=880; for(const o of placed){ if(Math.abs(o.cx+o.dx-it.cx)<(o.w+it.w)/2+20 && o.cy>=it.cy) lim=Math.min(lim,o.cy+o.dy-o.h/2-8); }
    const y1=it.cy+it.h/2; if(y1>lim) it.dy=lim-y1; placed.push(it); }
  const up=[...its].sort((a,b)=>a.cy-b.cy), top=[];
  for(const it of up){ let lim=120; for(const o of top){ if(Math.abs(o.cx+o.dx-it.cx)<(o.w+it.w)/2+20 && o.cy<=it.cy) lim=Math.max(lim,o.cy+o.dy+o.h/2+8); }
    const y0=it.cy+it.dy-it.h/2; if(y0<lim) it.dy+=lim-y0; top.push(it); }
  for(const it of its){ const x0=it.cx-it.w/2, x1=it.cx+it.w/2; if(x0<40) it.dx=40-x0; else if(x1>1880) it.dx=1880-x1;
    if(it.dx||it.dy){ const wp=it.p.clone().addScaledVector(R,it.dx*it.ppx).addScaledVector(U,-it.dy*it.ppx); it.s.parent.worldToLocal(wp); it.s.position.copy(wp); } } }

// ---- 球拍（第二集的参数化球拍，钩子和片尾用一支现代拍） ----
const IN=0.254;                                   // 1 英寸 = 0.254 单位
const WOOD={a:10.5/2*IN, b:8.5/2*IN}, BIG={a:13.5/2*IN, b:10.5/2*IN};
// ---- 材质 ----
const woodTex=(()=>{ const c=document.createElement('canvas'); c.width=512; c.height=64; const g=c.getContext('2d');
  const cols=['#8a5a2b','#b07a3e','#6e4520','#c48a4a','#93622f','#7b4f24','#b88444'];   // 多层胶合木条（参考 Commons 木拍照片）
  for(let i=0;i<64;i++){ g.fillStyle=cols[i%cols.length]; g.fillRect(0,i,512,1); }
  for(let i=0;i<900;i++){ g.fillStyle='rgba(40,20,5,0.18)'; g.fillRect(frnd()*512,frnd()*64,8+frnd()*30,1); }
  const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(6,1); return t; })();
const carbonTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d'); g.fillStyle='#232733'; g.fillRect(0,0,128,128);
  for(let y=0;y<128;y+=16) for(let x=0;x<128;x+=16){ const on=((x+y)/16)%2; const gr=g.createLinearGradient(x,y,x+(on?16:0),y+(on?0:16)); gr.addColorStop(0,'#2c313d'); gr.addColorStop(0.5,'#66708a'); gr.addColorStop(1,'#2c313d'); g.fillStyle=gr; g.fillRect(x+1,y+1,14,14); }
  const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(40,1); return t; })();
const MATS={
  wood:()=>new THREE.MeshPhysicalMaterial({map:woodTex,roughness:0.55,clearcoat:0.6,clearcoatRoughness:0.3,emissive:0x2a1406,emissiveIntensity:0.6,transparent:true}),
  steel:()=>new THREE.MeshPhysicalMaterial({color:0xc6ccd6,metalness:1,roughness:0.22,clearcoat:0.4,emissive:0x0e1420,emissiveIntensity:0.6,transparent:true}),
  alu:()=>new THREE.MeshPhysicalMaterial({color:0x9fb0c2,metalness:0.9,roughness:0.38,emissive:0x0c1420,emissiveIntensity:0.6,transparent:true}),
  carbon:()=>new THREE.MeshPhysicalMaterial({map:carbonTex,color:0xffffff,metalness:0.25,roughness:0.32,clearcoat:1,clearcoatRoughness:0.12,emissive:0x16243c,emissiveIntensity:1.0,transparent:true}),
  glass:()=>new THREE.MeshPhysicalMaterial({color:0xffffff,metalness:0,roughness:0.05,transmission:0.9,thickness:0.4,ior:1.45,clearcoat:1,transparent:true}) };
const STRC={wood:0xf2dcb0, steel:0xe8eef8, alu:0xe8eef8, carbon:0xd9e4ff, glass:0xffffff};

// ---- 参数化球拍：拍头椭圆（半长 a、半宽 b），拍头顶端固定在 tipY；拍杆、握把在下 ----
// 球拍几何对照真实球拍定（2026-11-06 所有者「拍喉的开孔大小不对啊，你找个真实的拍子对比一下」）：
//   Babolat Pure Drive 2012 正面照（Commons，500px）：拍喉是开口三角，高约全长 10%，上口宽约拍头宽 42%；拍框从拍头两侧顺滑地分出两条臂，
//   拍面底下另有一根细横梁（yoke）封住线床——不是「整只椭圆下面挂一个 Y」。
//   Dunlop Maxply 木拍正面照（Commons）：**没有开孔**，拍喉是实心的胶合楔块，拍杆长。黑德专利 US 3,999,756 Fig.1 同样是顺滑分臂。
//   全长一律 27 英寸（6.86 单位）；握把占全长：木拍约 30%、现代拍约 28%（两张照片量的）。对照图 papers/vibetennis-racket-2026/materials/ref/throat-compare.jpg
const RK_L=27*IN;
function makeRk(kind,{a=WOOD.a,b=WOOD.b,beam=0.06}={},group=scene){
  const g=new THREE.Group(); group.add(g); const mat=MATS[kind]();
  const head=new THREE.Group(); g.add(head);
  // 线床：单位圆内的格子（随拍头一起缩放）
  const sp=[]; const nm=16, nc=19, yc=kind==='wood'?-1:-Math.cos(Math.asin(0.45))+0.02;   // 开口拍喉的线床到横梁（yoke）为止，不画到椭圆最底下
  for(let i=0;i<nm;i++){ const x=-0.9+1.8*i/(nm-1), y=Math.sqrt(1-x*x)*0.985; sp.push(x,Math.max(-y,yc),0,x,y,0); }
  for(let i=0;i<nc;i++){ const y=-0.9+1.8*i/(nc-1), x=Math.sqrt(1-y*y)*0.985; if(y>=yc) sp.push(-x,y,0,x,y,0); }
  const sg=new THREE.BufferGeometry(); sg.setAttribute('position',new THREE.Float32BufferAttribute(sp,3));
  const strings=new THREE.LineSegments(sg,new THREE.LineBasicMaterial({color:new THREE.Color(STRC[kind]).multiplyScalar(0.8),transparent:true,opacity:0.7})); head.add(strings);
  const frame=new THREE.Mesh(new THREE.BufferGeometry(),mat), yoke=new THREE.Mesh(new THREE.BufferGeometry(),mat), wedge=new THREE.Mesh(new THREE.BufferGeometry(),mat);
  g.add(frame,yoke,wedge);
  const neck=new THREE.Group(); g.add(neck);
  const shaft=new THREE.Mesh(kind==='wood'?new THREE.CylinderGeometry(0.15,0.14,1,16):new THREE.CylinderGeometry(0.1,0.095,1,12),mat); neck.add(shaft);   // 拍杆宽：木拍约拍头宽 18%（Maxply 照片量的）、现代拍约 9%（Babolat）
  const handle=new THREE.Mesh(new THREE.CylinderGeometry(0.15,0.16,1,8),new THREE.MeshPhysicalMaterial({color:kind==='wood'?0x5a3a22:0x3a3f4c,roughness:0.6,emissive:0x0c1018,emissiveIntensity:0.6,transparent:true})); neck.add(handle);
  const R={g,head,frame,yoke,wedge,strings,mat,neck,shaft,handle,kind,a,b,beam,tip:a,solid:kind==='wood'};
  setRk(R,a,b); return R; }
// 改拍头尺寸：顶端固定（tip 不动），拍面往手柄方向长（Head 专利的做法）；全长不变，拍杆跟着变短
function setRk(R,a,b,{keepTip=true}={}){ R.a=a; R.b=b; const cy=keepTip?R.tip-a:0, bm=R.beam;
  R.head.position.set(0,cy,0); R.head.scale.set(b,a,1);
  const yB=cy-a, JD=(R.solid?0.10:0.08)*RK_L, phi=Math.asin(R.solid?0.6:0.45), jw=R.solid?0.15:0.1, yJ=yB-JD;   // JD：拍喉收拢点在线床底下 10% 全长；phi：拍臂从拍头侧边分出的位置
  const E=t=>new THREE.Vector3(b*Math.cos(t),cy+a*Math.sin(t),0);
  const arm=(sgn)=>{ const tD=-Math.PI/2+sgn*phi, D=E(tD), dir=new THREE.Vector3(-b*Math.sin(tD),a*Math.cos(tD),0).multiplyScalar(-sgn).normalize(), J=new THREE.Vector3(sgn*jw,yJ,0);
    const P1=D.clone().addScaledVector(dir,0.5*D.distanceTo(J)); const pts=[]; for(let i=0;i<=16;i++){ const k=i/16; pts.push(D.clone().multiplyScalar((1-k)*(1-k)).addScaledVector(P1,2*k*(1-k)).addScaledVector(J,k*k)); } return pts; };   // 二次贝塞尔：在分出点和拍头边相切，顺滑地收进拍杆
  const armL=arm(-1), armR=arm(1);
  const hoop=[]; for(let i=0;i<=200;i++){ const t=(-Math.PI/2-phi)-(i/200)*(2*Math.PI-2*phi); hoop.push(E(t)); }   // 从左分出点往上绕过顶端，到右分出点
  const path=[...armL.slice().reverse(),...hoop.slice(1,-1),...armR];
  R.frame.geometry.dispose(); R.frame.geometry=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(path,false,'centripetal'),420,bm,12,false);
  const yk=[]; for(let i=0;i<=40;i++){ const k=i/40, P=E(-Math.PI/2-phi+k*2*phi); if(!R.solid){ const D=E(-Math.PI/2-phi); P.y=D.y-0.04*a*Math.sin(Math.PI*k); } yk.push(P); }   // 开口拍：横梁几乎是一根直杆、略往下弯（Babolat 照片）；木拍就是拍框底边
  R.yoke.geometry.dispose(); R.yoke.geometry=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(yk),60,R.solid?bm:bm*0.75,10,false);   // 线床底下那根横梁（木拍就是拍框本身）
  R.wedge.geometry.dispose();
  if(R.solid){ const sh=new THREE.Shape(); armL.slice().reverse().forEach((p,i)=>i?sh.lineTo(p.x,p.y):sh.moveTo(p.x,p.y)); yk.forEach(p=>sh.lineTo(p.x,p.y)); armR.forEach(p=>sh.lineTo(p.x,p.y)); sh.closePath();   // 木拍：拍喉是实心楔块
    R.wedge.geometry=new THREE.ExtrudeGeometry(sh,{depth:bm*1.6,bevelEnabled:false}); R.wedge.geometry.translate(0,0,-bm*0.8); R.wedge.visible=true; }
  else { R.wedge.geometry=new THREE.BufferGeometry(); R.wedge.visible=false; }
  const yTop=R.tip+bm, yButt=yTop-RK_L, GL=(R.solid?0.30:0.28)*RK_L, yG=yButt+GL;
  R.shaft.position.set(0,(yJ+yG)/2,0); R.shaft.scale.set(1,Math.max(0.2,yJ-yG),1);
  R.handle.position.set(0,(yG+yButt)/2,0); R.handle.scale.set(1,GL,1);
  R.gripY=yG-0.3; R.bot=yB; R.cy=cy; R.butt=yButt; R.junction=yJ; }
function rkOp(R,v){ R.mat.opacity=v; R.strings.material.opacity=0.7*v; R.handle.material.opacity=v; R.g.visible=v>0.003; }
// 通用池
const LN=[...Array(40)].map(()=>fatLine(0xffffff,3)); let lnI=0; const ln=(col,w=3,dashed=false)=>{ const l=LN[lnI++]; l.material.color.set(col); l.material.linewidth=w; l.material.dashed=dashed; return l; };
const RG=[...Array(6)].map(()=>flatRing(0xffffff)); let rgI=0; const rg=()=>RG[rgI++];
const GS=[...Array(10)].map(()=>glowSprite(0xffffff,1,0)); let gsI=0; const gs=(col,size,o)=>{ const s=GS[gsI++]; s.material.color.set(col).multiplyScalar(GLOW.k); s.scale.set(size,size,1); s.material.opacity=o; s.visible=o>0.003; return s; };
const BALLS=[...Array(6)].map(()=>makeBall(0.2)); let bI=0; const bl=()=>BALLS[bI++];
const showB=(b,p,o=1,s=1)=>{ b.m.visible=o>0.003; b.gl.visible=o>0.003; b.m.position.copy(p); b.gl.position.copy(p); b.m.scale.setScalar(s); b.gl.scale.setScalar(b.r*5*s); b.m.material.transparent=true; b.m.material.opacity=o; b.gl.material.opacity=0.3*o; };
function arc(l,c,r,a0,a1,axis='z',n=48){ const pts=[]; for(let i=0;i<=n;i++){ const a=lerp(a0,a1,i/n); pts.push(axis==='z'?new THREE.Vector3(c.x+Math.cos(a)*r,c.y+Math.sin(a)*r,c.z):new THREE.Vector3(c.x+Math.cos(a)*r,c.y,c.z+Math.sin(a)*r)); } setLine(l,pts); }
const V=(x,y,z)=>new THREE.Vector3(x,y,z);
const fmt=(x,d=1)=>x.toFixed(d);

const pt=cloud(1600,0.05,8,scene,0.5); const PTS=[...Array(1600)].map(()=>[(frnd()-0.5)*16,(frnd()-0.5)*9,(frnd()-0.5)*8,frnd(),frnd()]);

// ---- 球场周边：中央球场看台（所有者 2026-11-07「要把球场周边看台渲染出来，比较有沉浸感」）----
// 1 单位 = 1 m。下层看台 20 排、LED 腰带、上层看台 24 排、顶沿灯环；场边一圈发光挡板；观众是光点（同 EP01）。
// 看台跟着 courtG 一起显隐、一起淡；离镜头 3~6 m 内的东西做抖动消隐（侧面机位在看台里，不让人头糊在镜头上）。
// 赛点那几秒观众席闪光灯变密（standsTick）。全部用自带的确定性随机，不动底座 frnd 的序列。
let ST_F, ST_TOP, ST_FL, ST_CR, ST_N=0, ST_RATE=0.0003; const ST_MATS=[];
const ST=(()=>{
  let sd=90210; const rr=()=>{ sd=(sd*48271)%2147483647; return sd/2147483647; };
  const G=new THREE.Group(); courtG.add(G);
  const near=(mat,a=3.5,b=5.0)=>{ mat.onBeforeCompile=(sh)=>{
      sh.vertexShader=sh.vertexShader.replace('#include <common>','#include <common>\nvarying float vD;').replace('#include <project_vertex>','#include <project_vertex>\nvD=-mvPosition.z;');
      sh.fragmentShader=sh.fragmentShader.replace('#include <common>','#include <common>\nvarying float vD;').replace('#include <clipping_planes_fragment>',
        `#include <clipping_planes_fragment>\n{ float k=smoothstep(${a.toFixed(1)},${b.toFixed(1)},vD); float h=fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453); if(h>k) discard; }`);
      sh.fragmentShader=sh.fragmentShader.replace('#include <fog_fragment>','#include <fog_fragment>\ngl_FragColor.rgb*=mix(1.0,0.45,smoothstep(25.0,75.0,vD));');   /* 远处的看台压暗：空气感 */
    }; return mat; };
  // 圆角矩形一圈，按弧长等分 n 个点（返回 [x,z,法线x,法线z]）
  function ring(a,b,rc,n){ const P=[]; const seg=(x0,z0,x1,z1)=>{ for(let i=0;i<24;i++){ const k=i/24; P.push([lerp(x0,x1,k),lerp(z0,z1,k)]); } };
    const arc=(cx,cz,t0)=>{ for(let i=0;i<24;i++){ const t=t0+i/24*Math.PI/2; P.push([cx+rc*Math.cos(t),cz+rc*Math.sin(t)]); } };
    seg(a,-(b-rc),a,b-rc); arc(a-rc,b-rc,0); seg(a-rc,b,-(a-rc),b); arc(-(a-rc),b-rc,Math.PI/2); seg(-a,b-rc,-a,-(b-rc)); arc(-(a-rc),-(b-rc),Math.PI); seg(-(a-rc),-b,a-rc,-b); arc(a-rc,-(b-rc),Math.PI*1.5);
    const cum=[0]; for(let i=1;i<=P.length;i++){ const p=P[i%P.length], q=P[i-1]; cum.push(cum[i-1]+Math.hypot(p[0]-q[0],p[1]-q[1])); }
    const tot=cum[cum.length-1], out=[]; let j=0;
    for(let i=0;i<n;i++){ const s=i/n*tot; while(cum[j+1]<s) j++; const p=P[j], q=P[(j+1)%P.length], k=(s-cum[j])/Math.max(1e-6,cum[j+1]-cum[j]);
      const x=lerp(p[0],q[0],k), z=lerp(p[1],q[1],k), tx_=q[0]-p[0], tz=q[1]-p[1], tl=Math.hypot(tx_,tz)||1; out.push([x,z,tz/tl,-tx_/tl]); }
    return {pts:out,len:tot}; }
  // 排：[内沿 a, b, 圆角, 台面高度, 台面深度]
  const ROWS=[]; { let a=11.6,b=21.2,rc=6.0,y=1.1; for(let r=0;r<20;r++){ ROWS.push([a,b,rc,y,0.85,'lo']); a+=0.85; b+=0.85; rc+=0.85; y+=0.42; }
    const fasciaA=a, fasciaB=b, fasciaRc=rc, fasciaY=y; ST_F=[fasciaA,fasciaB,fasciaRc,fasciaY];
    a+=1.4; b+=1.4; rc+=1.4; y+=1.9; for(let r=0;r<24;r++){ ROWS.push([a,b,rc,y,0.78,'hi']); a+=0.78; b+=0.78; rc+=0.78; y+=0.56; } ST_TOP=[a,b,rc,y]; }
  // 台阶：每排一条踏面＋一条立面（同一份几何），台沿一条细光线
  { const N=480, pos=[], idx=[], edge=[]; let base=0;
    for(let r=0;r<ROWS.length;r++){ const [a,b,rc,y,dp]=ROWS[r]; const A=ring(a,b,rc,N).pts, B=ring(a+dp,b+dp,rc+dp,N).pts; const yPrev=r? (ROWS[r][5]===ROWS[r-1][5]? ROWS[r-1][3] : y-1.9) : 0;
      for(let i=0;i<N;i++){ pos.push(A[i][0],yPrev,A[i][1], A[i][0],y,A[i][1], B[i][0],y,B[i][1]); }
      for(let i=0;i<N;i++){ const i2=(i+1)%N, o=base; const p0=o+i*3, p1=o+i2*3;
        idx.push(p0,p1,p0+1, p1,p1+1,p0+1,  p0+1,p1+1,p0+2, p1+1,p1+2,p0+2);
        if(r<20||r%2===0) edge.push(A[i][0],y+0.01,A[i][1],A[i2][0],y+0.01,A[i2][1]); }
      base+=N*3; }
    const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.setIndex(idx); g.computeVertexNormals();
    const m=new THREE.Mesh(g,near(new THREE.MeshLambertMaterial({color:0x0e1a30,side:THREE.DoubleSide,transparent:true}))); m.frustumCulled=false; G.add(m);
    const eg=new THREE.BufferGeometry(); eg.setAttribute('position',new THREE.Float32BufferAttribute(edge,3));
    const el=new THREE.LineSegments(eg,new THREE.LineBasicMaterial({color:0x5fc8ff,transparent:true,opacity:0.16,blending:THREE.AdditiveBlending,depthWrite:false})); el.frustumCulled=false; G.add(el);
    ST_MATS.push([m.material,1],[el.material,0.16]); }
  // 地面（场地外一圈深色硬地）＋场边挡板（发光广告带，不印任何品牌）
  { const fl=new THREE.Mesh(new THREE.PlaneGeometry(140,160),near(new THREE.MeshLambertMaterial({color:0x070d1a,transparent:true}))); fl.rotation.x=-Math.PI/2; fl.position.y=-0.02; fl.renderOrder=-2; G.add(fl); ST_MATS.push([fl.material,1]);
    const mkWall=(a,b,rc,y0,h,color,ei)=>{ const R=ring(a,b,rc,400).pts, pos=[], idx=[]; for(let i=0;i<R.length;i++){ pos.push(R[i][0],y0,R[i][1],R[i][0],y0+h,R[i][1]); }
      for(let i=0;i<R.length;i++){ const i2=(i+1)%R.length; idx.push(i*2,i2*2,i*2+1,i2*2,i2*2+1,i*2+1); }
      const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.setIndex(idx); g.computeVertexNormals();
      const m=new THREE.Mesh(g,near(new THREE.MeshStandardMaterial({color:0x0a1426,emissive:color,emissiveIntensity:ei,roughness:0.6,side:THREE.DoubleSide,transparent:true}))); m.frustumCulled=false; G.add(m); ST_MATS.push([m.material,1]); return m; };
    mkWall(11.3,20.9,5.7,0,1.1,0x1d5fb0,GLOW.emissive*0.9);                 // 场边挡板
    mkWall(ST_F[0],ST_F[1],ST_F[2],ST_F[3]-0.1,1.5,0x0a0f1c,0);           // 下层看台顶的墙
    mkWall(ST_F[0]+0.02,ST_F[1]+0.02,ST_F[2]+0.02,ST_F[3]+0.35,0.45,0x2a8cff,GLOW.emissive*1.3);   // LED 腰带
    mkWall(ST_TOP[0],ST_TOP[1],ST_TOP[2],ST_TOP[3]-0.2,2.4,0x0a0f1c,0);   // 顶沿
  }
  // 观众：一人一个光点（同 EP01 看台：冷白／冰蓝为主、两成琥珀，亮度随机）——所有者 2026-11-07「用闪光灯或者星点来表示人比较好……颜色太乱会导致整个画面失去焦点」
  { const pos=[], col=[], ph=[], heads=[]; for(const [a,b,rc,y,dp] of ROWS){ const R0=ring(a,b,rc,8); const n=Math.floor(R0.len/0.45); const R=ring(a+dp*0.5,b+dp*0.5,rc+dp*0.5,n).pts;
      for(let i=0;i<n;i++){ const f=i/n*28; if(f-Math.floor(f)<0.05) continue; if(rr()<0.12){ rr(); continue; }
        const x=R[i][0]+(rr()-0.5)*0.12, z=R[i][1]+(rr()-0.5)*0.12, yy=y+0.95; pos.push(x,yy,z); heads.push(x-R[i][2]*0.3,yy,z-R[i][3]*0.3); ph.push(rr()*6.283);
        const b=0.22+0.78*rr()*rr(); if(rr()<0.2) col.push(b*1.0,b*0.74,b*0.42); else { const w=rr()*0.25; col.push(b*(0.55+w),b*(0.78+w*0.6),b); } } }
    const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.setAttribute('color',new THREE.Float32BufferAttribute(col,3)); g.setAttribute('aP',new THREE.Float32BufferAttribute(ph,1));
    ST_CR=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uOp:{value:1},uT:{value:0},uPx:{value:H/2}},
      vertexShader:`attribute vec3 color; attribute float aP; uniform float uPx,uT; varying vec3 vC; varying float vF;
        void main(){ vec4 mv=modelViewMatrix*vec4(position,1.); float px=0.28*uPx*projectionMatrix[1][1]/max(0.5,-mv.z); vF=clamp(px/max(px,6.0),0.25,1.0)*smoothstep(3.0,6.0,-mv.z);
          vC=color*(0.86+0.14*sin(uT*1.3+aP)); gl_PointSize=clamp(px,1.5,6.0); gl_Position=projectionMatrix*mv; }`,
      fragmentShader:`uniform float uOp; varying vec3 vC; varying float vF; void main(){ float d=length(gl_PointCoord-0.5); float a=exp(-d*d*16.0)*(1.0-smoothstep(0.42,0.5,d))*uOp*vF; gl_FragColor=vec4(vC*a*1.9,a); }`});
    const cp=new THREE.Points(g,ST_CR); cp.frustumCulled=false; G.add(cp);
    const n=heads.length/3;
    // 闪光灯：每个观众头顶一个点，uT 每 1/20 s 换一次谁在闪；uRate 是单人单步的闪光概率
    const seed=new Float32Array(n); for(let i=0;i<n;i++) seed[i]=rr()*1000;   /* 闪光点＝观众光点往场内挪 0.3 m */
    const fg=new THREE.BufferGeometry(); fg.setAttribute('position',new THREE.Float32BufferAttribute(heads,3)); fg.setAttribute('aS',new THREE.BufferAttribute(seed,1));
    ST_FL=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uT:{value:0},uRate:{value:0.0004},uOp:{value:1},uPx:{value:H/2}},
      vertexShader:`attribute float aS; uniform float uT,uRate,uPx; varying float vA; float h(float x){ return fract(sin(x)*43758.5453); }
        void main(){ vec4 mv=modelViewMatrix*vec4(position,1.); float r=h(aS*1.37+uT*17.13); vA= r<uRate ? 0.55+0.45*h(aS+uT) : 0.0; gl_PointSize= vA>0.0 ? 0.5*projectionMatrix[1][1]*uPx/max(1.0,-mv.z) : 0.0; gl_Position=projectionMatrix*mv; }`,
      fragmentShader:`uniform float uOp; varying float vA; void main(){ if(vA<=0.0) discard; vec2 p=gl_PointCoord-0.5; float d=length(p)*2.0; float a=pow(max(0.0,1.0-d),2.2); gl_FragColor=vec4(vec3(1.0,0.97,0.9)*a*vA*uOp*0.9,a*vA*uOp); }`});
    const fp=new THREE.Points(fg,ST_FL); fp.frustumCulled=false; G.add(fp); ST_N=n; }
  // 顶沿灯环：一圈灯点（小光晕），照向场内
  { const R=ring(ST_TOP[0]-0.3,ST_TOP[1]-0.3,ST_TOP[2]-0.3,64).pts; for(const [x,z] of R){ const s=glowSprite(0xdfeaff,1.6,0.32,G); s.position.set(x,ST_TOP[3]+1.4,z); ST_MATS.push([s.material,0.32]); } }
  return G; })();
// 每帧（shot 跑完之后）：看台跟 courtG 的显隐与淡出；赛点那几秒闪光灯变密
function standsTick(t,kind,u){ ST.visible=courtG.visible; if(!ST.visible) return; const o=courtG.userData.mat.opacity;
  for(const [m,b] of ST_MATS){ m.opacity=b*o;
    // 看台的实体（台阶、挡板、墙、地面）平时走不透明队列：先画、写深度，全息人（半透明、不写深度）才不会被背后的看台盖住（所有者 2026-11-07 截图：发球人上半身被挡）。只有跟着球场淡出时才切成半透明
    if(m.isMeshLambertMaterial||m.isMeshStandardMaterial){ const tr=b*o<0.999; if(m.transparent!==tr){ m.transparent=tr; m.needsUpdate=true; } } }
  const rate=ST_RATE;   /* 闪光灯密度由镜头设（hideAll 复位成 0.0003）；名场面那几秒调到 0.006 左右 */
  ST_FL.uniforms.uRate.value=rate; ST_FL.uniforms.uT.value=Math.floor(t*20); ST_FL.uniforms.uOp.value=o; ST_CR.uniforms.uOp.value=o; ST_CR.uniforms.uT.value=t; }

// ---- 全息人体（发球人／接发人）：胶囊骨骼＋菲涅尔边缘光，按关节角驱动（前向运动学）----
// 尺寸按真人（1 单位 = 1 米）：德约身高约 1.88 m。动作是示意，画面标「示意」。
const holoMat=(col)=>new THREE.ShaderMaterial({transparent:true,depthWrite:false,uniforms:{uC:{value:new THREE.Color(col)},uOp:{value:1},uK:{value:GLOW.k}},
  vertexShader:`varying vec3 vN; varying vec3 vV; void main(){ vec4 mv=modelViewMatrix*vec4(position,1.); vN=normalize(normalMatrix*normal); vV=normalize(-mv.xyz); gl_Position=projectionMatrix*mv; }`,
  fragmentShader:`uniform vec3 uC; uniform float uOp,uK; varying vec3 vN; varying vec3 vV; void main(){ float f=pow(1.0-abs(dot(normalize(vN),normalize(vV))),2.2); vec3 c=uC*(0.18+0.95*f)*uK*1.6; gl_FragColor=vec4(c,uOp*(0.22+0.7*f)); }`});
const BONE={pelvisY:0.98, spine:0.50, neck:0.10, head:0.115, shW:0.20, hipW:0.10, upArm:0.31, foreArm:0.27, thigh:0.46, shin:0.45, foot:0.24};
function makeHuman(col,group=scene){
  const mat=holoMat(col), root=new THREE.Group(); group.add(root);
  const node=(parent,y=0,x=0,z=0)=>{ const n=new THREE.Group(); n.position.set(x,y,z); parent.add(n); return n; };
  const cap=(parent,len,r)=>{ const m=new THREE.Mesh(new THREE.CapsuleGeometry(r,Math.max(0.01,len-2*r),6,14),mat); m.position.y=-len/2; parent.add(m); return m; };
  const pelvis=node(root,BONE.pelvisY); const hipBox=new THREE.Mesh(new THREE.CapsuleGeometry(0.12,0.14,6,14),mat); hipBox.rotation.z=Math.PI/2; pelvis.add(hipBox);
  const spine=node(pelvis,0.02); const torso=new THREE.Mesh(new THREE.CapsuleGeometry(0.15,BONE.spine-0.26,6,16),mat); torso.position.y=BONE.spine/2; torso.scale.set(1.15,1,0.75); spine.add(torso);
  const neck=node(spine,BONE.spine); const head=new THREE.Mesh(new THREE.SphereGeometry(BONE.head,20,16),mat); head.position.y=BONE.neck+BONE.head; neck.add(head);
  const eye=node(neck,BONE.neck+BONE.head,0,0.09);   // 视线起点
  const arm=(s)=>{ const sh=node(spine,BONE.spine-0.04,s*BONE.shW); const up=node(sh); cap(up,BONE.upArm,0.05); const el=node(up,-BONE.upArm); cap(el,BONE.foreArm,0.043); const hand=node(el,-BONE.foreArm); const hm=new THREE.Mesh(new THREE.SphereGeometry(0.05,12,10),mat); hand.add(hm); return {sh,up,el,hand}; };
  const leg=(s)=>{ const hp=node(pelvis,-0.02,s*BONE.hipW); cap(hp,BONE.thigh,0.075); const kn=node(hp,-BONE.thigh); cap(kn,BONE.shin,0.058); const an=node(kn,-BONE.shin); const ft=new THREE.Mesh(new THREE.CapsuleGeometry(0.045,BONE.foot-0.09,6,10),mat); ft.rotation.x=Math.PI/2; ft.position.set(0,-0.04,0.07); an.add(ft); return {hp,kn,an,ft}; };
  const H={root,pelvis,spine,neck,head,eye,mat,armR:arm(-1),armL:arm(1),legR:leg(-1),legL:leg(1),racket:null};
  return H; }
// 姿势：关节角（弧度）。arm:[肩前屈, 肩外展, 肩内外旋, 肘屈]；leg:[髋屈, 髋外展, 膝屈, 踝]；躯干:[前倾, 侧倾, 扭转]
const POSE={
  stand:{y:0, lean:0.05, side:0, twist:0, head:0, aR:[0.1,0.15,0,0.3], aL:[0.1,0.15,0,0.3], lR:[0,0.05,0.05,0], lL:[0,0.05,0.05,0]},
  ready:{y:-0.16, lean:0.42, side:0, twist:0, head:-0.25, aR:[0.9,0.25,0.4,1.3], aL:[0.9,0.25,-0.4,1.3], lR:[0.75,0.28,1.15,0.4], lL:[0.75,0.28,1.15,0.4]},
  split:{y:0.06, lean:0.3, side:0, twist:0, head:-0.15, aR:[0.8,0.3,0.4,1.2], aL:[0.8,0.3,-0.4,1.2], lR:[0.35,0.42,0.45,0.2], lL:[0.35,0.42,0.45,0.2]},
  land:{y:-0.24, lean:0.45, side:0, twist:0, head:-0.2, aR:[0.85,0.3,0.4,1.2], aL:[0.85,0.3,-0.4,1.2], lR:[0.95,0.45,1.5,0.5], lL:[0.95,0.45,1.5,0.5]},
  lungeF:{y:-0.42, lean:0.35, side:-0.25, twist:-0.7, head:-0.1, aR:[0.4,1.3,0.2,0.25], aL:[0.6,0.6,0,0.8], lR:[0.9,0.95,1.1,0.4], lL:[0.15,0.15,0.2,0.1]},   // 正手（右侧）大跨步／滑步
  lungeB:{y:-0.42, lean:0.35, side:0.25, twist:0.8, head:-0.1, aR:[0.9,-0.2,0.6,0.5], aL:[0.7,0.2,0,0.9], lR:[0.15,0.15,0.2,0.1], lL:[0.9,0.95,1.1,0.4]},   // 反手（左侧）
  sToss:{y:0, lean:0.05, side:-0.1, twist:-0.5, head:0.35, aR:[0.3,0.6,0.2,0.6], aL:[2.9,0.2,0,0.05], lR:[0.15,0.15,0.2,0.1], lL:[0.15,0.1,0.25,0.1]},   // 发球抛球
  sTrophy:{y:-0.22, lean:-0.25, side:-0.35, twist:-0.9, head:0.55, aR:[1.4,1.4,1.6,1.9], aL:[2.8,0.25,0,0.1], lR:[0.6,0.15,1.1,0.4], lL:[0.6,0.1,1.1,0.4]},
  sHit:{y:0.18, lean:0.0, side:0.15, twist:0.25, head:0.45, aR:[3.0,0.15,-0.4,0.05], aL:[0.9,0.4,0,0.9], lR:[0.05,0.05,0.05,-0.4], lL:[0.05,0.08,0.05,-0.4]},
  sFollow:{y:-0.08, lean:0.6, side:0.1, twist:0.6, head:0.0, aR:[0.4,-0.3,0.3,0.6], aL:[0.5,0.3,0,1.1], lR:[0.7,0.1,0.7,0.2], lL:[0.2,0.15,0.3,0.1]},
  // EP11：抽筋坐地（右腿伸直、脚尖被拉下，双手去够右小腿）、坐姿拉伸（勾脚尖、身体前倾够脚）
  cramp:{y:-0.84, lean:0.6, side:0.05, twist:0.15, head:-0.35, aR:[1.25,0.25,0.3,0.45], aL:[1.25,0.25,-0.3,0.45], lR:[1.45,0.08,0.05,-0.6], lL:[1.15,0.35,1.7,0.3]},
  stretchS:{y:-0.84, lean:0.9, side:0.0, twist:0.0, head:-0.2, aR:[1.6,0.12,0.2,0.08], aL:[1.6,0.12,-0.2,0.08], lR:[1.45,0.05,0.0,0.6], lL:[1.15,0.35,1.7,0.3]}};
function mixPose(a,b,k){ const o={}; for(const key in a){ if(Array.isArray(a[key])) o[key]=a[key].map((v,i)=>lerp(v,b[key][i],k)); else o[key]=lerp(a[key],b[key],k); } return o; }
// keys:[[t,poseName],...]（段内秒）→ 当前姿势；两帧之间 smoothstep
function poseAt(keys,u){ if(u<=keys[0][0]) return POSE[keys[0][1]]; for(let i=0;i<keys.length-1;i++){ const [t0,a]=keys[i], [t1,b]=keys[i+1]; if(u<t1) return mixPose(POSE[a],POSE[b],ss(t0,t1,u)); } return POSE[keys[keys.length-1][1]]; }
function applyPose(H,P,mirror=false){ const m=mirror?-1:1;   // mirror：左右镜像（左手持拍）
  H.pelvis.position.y=BONE.pelvisY+P.y; H.pelvis.rotation.set(0,0,P.side*m*0.4);
  H.spine.rotation.set(P.lean,P.twist*m,P.side*m);
  H.neck.rotation.set(P.head,-P.twist*m*0.5,0);
  const arm=(A,v,s)=>{ A.up.rotation.set(-v[0],v[2]*s,v[1]*s); A.el.rotation.set(-v[3],0,0); };
  const R=mirror?H.armL:H.armR, L=mirror?H.armR:H.armL; arm(R,P.aR,-m); arm(L,P.aL,m);
  const leg=(G,v,s)=>{ G.hp.rotation.set(-v[0],0,v[1]*s); G.kn.rotation.set(v[2],0,0); G.an.rotation.set(-v[3]*0.5,0,0); };
  const LR=mirror?H.legL:H.legR, LL=mirror?H.legR:H.legL; leg(LR,P.lR,-m); leg(LL,P.lL,m); }
function humanOp(H,o){ H.mat.uniforms.uOp.value=o; H.root.visible=o>0.003; if(H.racket) rkOp(H.racket,o); }
// 把球拍挂到持拍手上（球拍几何是 1 单位 = 10 cm，挂到人身上缩到 0.1）
function attachRacket(H,R,mirror=false){ const hand=(mirror?H.armL:H.armR).hand; hand.add(R.g); R.g.scale.setScalar(0.1); R.g.rotation.set(Math.PI,0,0); R.g.position.set(0,(R.butt+0.6)*0.1,0); H.racket=R; }   /* 拍子尖朝手臂延长方向；握点在拍尾往上 6 cm */
const wpos=(o)=>o.getWorldPosition(new THREE.Vector3());

// ==================== EP11 阻力危机：空气动力资产 ====================
// FLOW：绕球的烟线（二维势流绕圆柱近似 + 分离点之后的尾流），sep＝分离角（从迎风驻点量，度）。
//   层流（光滑球、低速）约 80°：尾流宽；湍流（过了阻力危机）约 120°：尾流窄——示意，画面标「示意」。
// CURVE：阻力系数 Cd 对雷诺数 Re 的经典曲线（光滑球带「悬崖」、高尔夫提前跳崖、网球一路平），点在线上滑。
// BL：光滑球、高尔夫球（凹坑）、足球（拼块）、网球（绒毛壳）。TOWER：埃菲尔铁塔线框。
const FLOW=(()=>{
  const NS=34, PTS_PER=46, LEN=7.0; const lines=[];
  // 预先积分流线：圆柱半径 1，来流沿 +x，速度 1；分离后沿分离处切线方向直行、再慢慢回正
  function streamline(y0,sepDeg){ const pts=[]; let x=-LEN, y=y0; const dt=0.04; const sep=sepDeg*Math.PI/180; let sepd=false, vy0=0;
    for(let i=0;i<900 && x<LEN;i++){ const r2=x*x+y*y; const r4=r2*r2;
      let u=1-(x*x-y*y)/r4, v=-2*x*y/r4;
      const ang=Math.atan2(Math.abs(y),-x);   // 从迎风驻点（-x 方向）量起的角度
      if(!sepd && r2<1.9 && ang>sep && x>-0.2){ sepd=true; vy0=v; }
      if(sepd){ u=1; v=vy0*Math.exp(-(x)*0.6); }
      x+=u*dt; y+=v*dt; if(r2<1.0005){ const s=Math.sqrt(1.0005/r2); x*=s; y*=s; }
      if(i%3===0) pts.push([x,y]); }
    return pts; }
  function build(sepDeg){ const out=[]; for(let i=0;i<NS;i++){ const y0=(i/(NS-1)-0.5)*4.4; if(Math.abs(y0)<0.04) continue; out.push(streamline(y0,sepDeg)); } return out; }
  const cache={}; const get=(s)=>cache[s]||(cache[s]=build(s));
  // 流线本身画成细线（同一分离角共用一份几何），粒子在线上流动
  const LG=new THREE.Group(); scene.add(LG); const LMAT=new THREE.LineBasicMaterial({color:0x6fc8ff,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false});
  const lcache={}; function lineObj(sep){ if(lcache[sep]) return lcache[sep]; const L=get(sep), seg=[]; for(const ln of L){ for(let i=0;i<ln.length-1;i++) seg.push(ln[i][0],ln[i][1],0,ln[i+1][0],ln[i+1][1],0); }
    const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(seg,3)); const o=new THREE.LineSegments(g,LMAT); o.frustumCulled=false; o.visible=false; LG.add(o); lcache[sep]=o; return o; }
  const P=cloud(2600,0.09,9,scene,0); let sd=777; const rr=()=>{ sd=(sd*48271)%2147483647; return sd/2147483647; };
  const SEED=[...Array(2600)].map(()=>[rr(),rr(),rr(),rr()]);
  // c：球心；R：球半径（世界单位）；sep：分离角；turb：尾流的乱度；o：透明度；t：时间；col：颜色；z0：烟线所在的面（离球心的深度偏移）
  function draw(c,R,sep,turb,o,t,col=0x9fd8ff,speed=0.45,lineO=0.3,skew=0){ const L=get(Math.round(sep)); for(const k in lcache) lcache[k].visible=false; const lo=lineObj(Math.round(sep)); lo.visible=o>0.003; lo.position.copy(c); lo.scale.setScalar(R); LMAT.opacity=o*lineO; const cc=new THREE.Color(col), wc=new THREE.Color(0xffd27a);
    const wake=Math.sin(sep*Math.PI/180);   // 尾流半宽（以 R 计）
    for(let i=0;i<2600;i++){ const s=SEED[i]; if(i<2000){ const line=L[i%L.length]; const f=(s[0]+t*speed*(0.9+0.2*s[1]))%1; const k=f*(line.length-1), a=Math.floor(k), w=k-a; const p0=line[a], p1=line[Math.min(line.length-1,a+1)];
        const x=lerp(p0[0],p1[0],w), y=lerp(p0[1],p1[1],w); const fade=Math.min(1,f*6,(1-f)*6);
        cset(P,i,c.x+x*R,c.y+y*R,c.z,cc.r,cc.g,cc.b,o*fade*0.95); }
      else { // 尾流里的涡：在分离之后、宽度 wake 的区域里打转
        const f=(s[0]+t*0.35)%1; const x=0.4+f*5.0; const amp=wake*(0.75+0.25*Math.sin(x*1.3)); const ph=s[1]*6.283+t*(2+3*turb)+x*1.7;
        const y=Math.sin(ph)*amp*(0.25+0.75*s[2])*(1+0.15*turb*Math.sin(t*7+s[3]*20)); const z=Math.cos(ph)*amp*0.5*s[2];
        cset(P,i,c.x+x*R,c.y+(y+skew*x*0.35)*R,c.z+z*R,wc.r,wc.g,wc.b,o*0.7*(1-f)*Math.min(1,f*8)); } }
    cdone(P); }
  return {draw,hide(){ chide(P); for(const k in lcache) lcache[k].visible=false; }};
})();

// Cd–Re 曲线（屏幕上的全息图表；数据点按文献量级手描，画面标「示意」，具体数字只在 sources.md 核过的才上屏）
const CURVE=(()=>{
  const smooth=[[4.0,0.5],[4.6,0.5],[5.0,0.5],[5.3,0.49],[5.4,0.44],[5.47,0.25],[5.53,0.12],[5.6,0.1],[5.9,0.12],[6.2,0.16]];
  const golf=[[4.0,0.47],[4.4,0.46],[4.6,0.40],[4.75,0.27],[4.9,0.24],[5.1,0.25],[5.4,0.27],[5.7,0.28],[6.2,0.29]];
  const tennis=[[4.0,0.66],[4.6,0.65],[5.0,0.63],[5.2,0.6],[5.4,0.59],[5.6,0.58],[5.9,0.58],[6.2,0.58]];
  const at=(arr,lx)=>{ for(let i=0;i<arr.length-1;i++){ const [a,b]=[arr[i],arr[i+1]]; if(lx<=b[0]) return lerp(a[1],b[1],clamp((lx-a[0])/(b[0]-a[0]))); } return arr[arr.length-1][1]; };
  return {smooth,golf,tennis,at};
})();
// 把曲线画到镜头空间：x 轴 log10(Re) 4.0–6.2 映到 [x0,x1]，y 轴 Cd 0–0.7 映到 [y0,y1]
function curvePts(arr,x0,x1,y0,y1,k=1,d=9){ const pts=[]; const lx1=lerp(4.0,6.2,k); for(let lx=4.0;lx<=lx1+1e-6;lx+=0.02){ pts.push(hp(lerp(x0,x1,(lx-4)/2.2),lerp(y0,y1,CURVE.at(arr,lx)/0.7),d)); } if(pts.length<2) pts.push(pts[0].clone().add(V(0.001,0,0))); return pts; }

const BL=(()=>{
  const g=new THREE.Group(); scene.add(g);
  const mk=(mat,r=1)=>{ const m=new THREE.Mesh(new THREE.SphereGeometry(r,64,48),mat); m.visible=false; g.add(m); return m; };
  // 高尔夫：画布上画凹坑做法线感（用暗点 + 高光近似）
  const golfTex=(()=>{ const c=document.createElement('canvas'); c.width=1024; c.height=512; const x=c.getContext('2d'); x.fillStyle='#e9eef2'; x.fillRect(0,0,1024,512);
    for(let j=0;j<18;j++) for(let i=0;i<40;i++){ const cx=(i+(j%2)*0.5)*25.6, cy=j*28.4+14; const gr=x.createRadialGradient(cx-3,cy-3,1,cx,cy,11); gr.addColorStop(0,'#b8c0c8'); gr.addColorStop(1,'#eef2f5'); x.fillStyle=gr; x.beginPath(); x.arc(cx,cy,10,0,6.283); x.fill(); }
    const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; return t; })();
  const footTex=(()=>{ const c=document.createElement('canvas'); c.width=1024; c.height=512; const x=c.getContext('2d'); x.fillStyle='#f4f4f4'; x.fillRect(0,0,1024,512); x.strokeStyle='#2a3240'; x.lineWidth=5;
    for(let i=0;i<8;i++){ x.beginPath(); for(let k=0;k<=64;k++){ const yy=k/64*512; const xx=i*128+40*Math.sin(yy/512*Math.PI*2+i); k?x.lineTo(xx,yy):x.moveTo(xx,yy); } x.stroke(); }
    x.beginPath(); x.moveTo(0,256); for(let k=0;k<=128;k++) x.lineTo(k*8,256+40*Math.sin(k/16)); x.stroke(); const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; return t; })();
  const smooth=mk(new THREE.MeshPhysicalMaterial({color:0xb0c430,roughness:0.25,clearcoat:1,emissive:0x2a3200,emissiveIntensity:0.2}));
  const golf=mk(new THREE.MeshStandardMaterial({map:golfTex,color:0xb8b8b8,roughness:0.5,emissive:0x101418,emissiveIntensity:0.2}));
  const foot=mk(new THREE.MeshStandardMaterial({map:footTex,roughness:0.45,emissive:0x101418,emissiveIntensity:0.2}));
  const tennis=mk(new THREE.MeshPhysicalMaterial({map:ballTex,color:0xc8c8c8,roughness:0.85,sheen:1,sheenColor:new THREE.Color(0xf6ff9a),emissive:0x2a3200,emissiveIntensity:0.25}));
  // 绒毛：网球外面一层短毛（粒子壳），fuzz 0–1 控制毛的长短（磨秃＝0）
  const FZ=cloud(1800,0.035,5,g,0); let sd=31337; const rr=()=>{ sd=(sd*48271)%2147483647; return sd/2147483647; };
  const FD=[...Array(1800)].map(()=>{ const u=rr()*2-1, a=rr()*6.283, s=Math.sqrt(1-u*u); return [s*Math.cos(a),u,s*Math.sin(a),rr()]; });
  function fuzz(c,R,amt,o,col=0xeaff80){ const cc=new THREE.Color(col).multiplyScalar(0.5);   /* 光晕标准：毛是叠加发光，压一半 */ for(let i=0;i<1800;i++){ const d=FD[i]; const rr_=R*(1+amt*0.06*(0.3+0.7*d[3])); cset(FZ,i,c.x+d[0]*rr_,c.y+d[1]*rr_,c.z+d[2]*rr_,cc.r,cc.g,cc.b,o*amt*(0.4+0.6*d[3])); } cdone(FZ); }
  const tennis2=mk(new THREE.MeshPhysicalMaterial({map:ballTex,color:0xc8c8c8,roughness:0.9,sheen:1,sheenColor:new THREE.Color(0xf6ff9a),emissive:0x2a3200,emissiveIntensity:0.25}));
  const all=[smooth,golf,foot,tennis,tennis2];
  return {g,smooth,golf,foot,tennis,tennis2,all,fuzz,hide(){ all.forEach(m=>{ m.visible=false; m.scale.setScalar(1); m.rotation.set(0,0,0); m.material.opacity=1; m.material.transparent=false; }); chide(FZ); }};
})();
function showBall(m,c,R,o=1,spin=0){ m.visible=o>0.003; m.position.copy(c); m.scale.setScalar(R); m.rotation.set(0.3,spin,0.2); m.material.transparent=o<1; m.material.opacity=o; }

// 埃菲尔铁塔（线框，约 3 单位高；1 单位≈100 m）：四条弧形腿＋三层平台＋交叉斜撑
const TOWER=(()=>{
  const g=new THREE.Group(); scene.add(g); g.visible=false; const segs=[];
  const halfW=(y)=>{ const h=y/3.0; return 0.62*Math.pow(1-h,2.2)+0.025; };
  const corner=(y,sx,sz)=>[sx*halfW(y),y,sz*halfW(y)];
  const C=[[1,1],[1,-1],[-1,-1],[-1,1]];
  for(const [sx,sz] of C){ for(let i=0;i<60;i++){ const y0=i/60*3.0, y1=(i+1)/60*3.0; segs.push(...corner(y0,sx,sz),...corner(y1,sx,sz)); } }
  for(let i=0;i<=24;i++){ const y=i/24*2.7; for(let k=0;k<4;k++){ const a=corner(y,...C[k]), b=corner(y,...C[(k+1)%4]); segs.push(...a,...b);
      const y2=Math.min(2.7,y+2.7/24); const a2=corner(y2,...C[(k+1)%4]); segs.push(...a,...a2); } }
  for(const yy of [0.57,1.15,2.76]){ for(let k=0;k<4;k++){ const w=halfW(yy)+0.06; const a=[C[k][0]*w,yy,C[k][1]*w], b=[C[(k+1)%4][0]*w,yy,C[(k+1)%4][1]*w]; segs.push(...a,...b); } }
  // 底部拱
  for(let k=0;k<4;k++){ const [sx,sz]=C[k], [tx2,tz2]=C[(k+1)%4]; for(let i=0;i<20;i++){ const f0=i/20, f1=(i+1)/20; const P=(f)=>{ const x=lerp(sx*halfW(0.1),tx2*halfW(0.1),f), z=lerp(sz*halfW(0.1),tz2*halfW(0.1),f); return [x,0.1+0.32*Math.sin(Math.PI*f),z]; }; segs.push(...P(f0),...P(f1)); } }
  const geo=new THREE.BufferGeometry(); geo.setAttribute('position',new THREE.Float32BufferAttribute(segs,3));
  const mat=new THREE.LineBasicMaterial({color:0xffc24a,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false});
  const L=new THREE.LineSegments(geo,mat); L.frustumCulled=false; g.add(L);
  return {g,mat,set(o){ mat.opacity=o*0.7; g.visible=o>0.003; }};
})();

// ================== 镜头 ==================
const anchors={};
function proj(name,v){ camera.updateMatrixWorld(); const p=v.clone().project(camera); anchors[name]=[(p.x*0.5+0.5)*W,(1-(p.y*0.5+0.5))*H,(p.z<1&&p.z>-1)?1:0]; }
const MOVE={push:0.06, orbit:0.06, xf:0.6, xfPush:0.04};
let CAMMOVE=null; const UPV=new THREE.Vector3(0,1,0);
function look(px,py,pz_,tx_,ty,tz){ const P=new THREE.Vector3(px,py,pz_), Tg=new THREE.Vector3(tx_,ty,tz);
  if(CAMMOVE){ const k=ss(0,1,CAMMOVE.u/CAMMOVE.L); const d=P.clone().sub(Tg); d.applyAxisAngle(UPV,(k-0.5)*MOVE.orbit*CAMMOVE.dir); d.multiplyScalar(1-MOVE.push*k); P.copy(Tg).add(d); }
  camera.position.copy(P); camera.lookAt(Tg); }
const DOF={on:false,focus:10,ap:0.00012};
let SLOW=null, SEC_U=0;   // 子弹时间窗口：在 renderAt 里做累积运动模糊


// ==================== 本集镜头 ====================
// 球场：1 单位 = 1 m（底座 courtG 就是 ITF 尺寸，球网在 z=0）。发球人在 z=-L 那一侧，接发人（德约，青色）在 z=+L 一侧，面朝 -z。
// 接发人是右手：面朝 -z 时他的右手在 +x；平分区在他右边（+x）。
const SRV=makeHuman(0xffc24a), RET=makeHuman(0x4fe3ff), G1=makeHuman(0x9fb8d0), G2=makeHuman(0x4fe3ff);
const HUM=[SRV,RET,G1,G2];
const DOTS=[...Array(100)].map(()=>{ const m=new THREE.Mesh(new THREE.SphereGeometry(0.09,12,8),new THREE.MeshBasicMaterial({color:0x4fe3ff})); m.visible=false; scene.add(m); return m; });
const rkS=makeRk('carbon',{a:13.5/2*IN*0.95,b:10.5/2*IN*0.95}), rkR=makeRk('carbon',{a:13.5/2*IN*0.95,b:10.5/2*IN*0.95});
attachRacket(SRV,rkS); attachRacket(RET,rkR);
const ALLRK=[rkS,rkR];
const BS=0.25;   // 通用池的球半径 0.2；这里缩到 0.05（真实 3.3 cm，画大一点，画面标「示意」）
function particles(k,cx,cy,cz,w,h,col,o=1){ const cc=new THREE.Color(col); for(let i=0;i<1600;i++){ const p=PTS[i]; const tx_=cx+(p[3]-0.5)*w, ty=cy+(p[4]-0.5)*h; const e=ss(0,1,k*(1+p[3]*0.4)-p[3]*0.2);
    cset(pt,i,lerp(cx+p[0],tx_,e),lerp(cy+p[1],ty,e),lerp(cz+p[2],cz,e),cc.r,cc.g,cc.b,o*(1-0.75*e)); } cdone(pt); }
const CY=0x4fe3ff, GO=0xffc24a, RD=0xff5a4a, MT=0x34f5a8, WH=0xffffff;
// 镜头坐标里的点（look() 之后调）：x、y 是画面上的偏移，d 是离相机的距离
function hp(x,y,d=9){ camera.updateMatrixWorld(); return V(x,y,-d).applyQuaternion(camera.quaternion).add(camera.position); }
const rims=(a,b,i=5)=>{ rimL.intensity=i; rimR.intensity=i; rimL.color.set(a); rimR.color.set(b); rimL.position.set(-6,4,6); rimR.position.set(6,4,6); };
function place(H,x,z,yaw,mirror=false){ H.root.position.set(x,0,z); H.root.rotation.set(0,yaw,0); }
// 发球轨迹（真实秒）：击球点 → 落点（0.40 s，Cross 阻力模型）→ 接发人击球点（约 0.65 s）
const L2=23.77/2, SLN=6.40;
function serveAt(t,A,B,Cp){ const T1=0.40, T2=0.65; if(t<=T1){ const k=t/T1; return V(lerp(A.x,B.x,k),lerp(A.y,0,k)+Math.sin(Math.PI*k)*0.15,lerp(A.z,B.z,k)); }
  const k=clamp((t-T1)/(T2-T1)); return V(lerp(B.x,Cp.x,k),Math.sin(Math.PI*k*0.5)*Cp.y+0.0*k,lerp(B.z,Cp.z,k)); }
function trail(pts,col,w,o){ const l=ln(col,w); setLine(l,pts); l.material.opacity=o; return l; }
function hideAll(){
  courtG.visible=false; courtG.userData.mat.opacity=1;
  HUM.forEach(H=>{ humanOp(H,0); H.root.position.set(0,0,0); H.root.rotation.set(0,0,0); H.mat.uniforms.uC.value.set(H===SRV?0xffc24a:H===RET?0x4fe3ff:H===G1?0x9fb8d0:0x4fe3ff); });
  BALLS.forEach(b=>{ b.m.visible=false; b.gl.visible=false; }); bI=0; DOTS.forEach(m=>m.visible=false);
  LN.forEach(l=>{ l.material.opacity=0; l.material.dashed=false; }); lnI=0; RG.forEach(r=>r.material.opacity=0); rgI=0; GS.forEach(s=>{ s.material.opacity=0; s.visible=false; }); gsI=0;
  for(const k in TT) op(TT[k],0); for(const k in TB) TB[k].g.visible=false; for(const k in text3D) t3op(text3D[k],0); chide(pt);
  beamMat.uniforms.uOp.value=0; rimL.intensity=0; rimR.intensity=0; DOF.on=false; MOTE_SPEED=1; SLOW=null;
  FLOW.hide(); BL.hide(); TOWER.set(0); TOWER.g.scale.setScalar(1); TOWER.g.position.set(0,0,0); WIRE.material.opacity=0; BL.smooth.material.color.set(0xb0c430); HUM.forEach(H=>{ H.root.scale.setScalar(1); if(H.racket) H.racket.g.visible=true; }); ST_RATE=0.0003; courtG.userData.mat.color.set(0xffffff); }
// 全息榜单行
function row(k,i,str,val,max,col,o,hl=0){ const y=1.4-i*0.75; const w=4.6*clamp(val/max); const l=ln(col,hl?14:10); setLine(l,[V(-1.2,y,0),V(-1.2+w,y,0)]); l.material.opacity=o*(0.75+0.25*hl);
  const t=tx(k,str,{color:hl?'#ffffff':'#c8d8ea',size:0.42,glow:hl?CYAN:'rgba(120,160,200,0.6)'}); t.position.set(-3.4,y,0.1); op(t,o); }

// ---------- 1 钩子：开场即砸出冲突——「7」从天而降炸开 → 炸成「接发之王」→ 甩进 2011 美网赛点接发 → 王在哪？ ----------
// 所有者 2026-11-07：「前几秒一定要抓住人……直接抛出来，然后用炸裂或者是非常爆裂的动作，或者特效把这个东西做到极致」
function burst(c,k,col,spread=6,o=1){ const cc=new THREE.Color(col); for(let i=0;i<1600;i++){ const p=PTS[i]; const dir=V(p[0],p[1]*1.2,p[2]).normalize(); const sp=spread*(0.4+0.6*p[3]); const e=1-Math.pow(1-clamp(k),2.2);
  cset(pt,i,c.x+dir.x*sp*e,c.y+dir.y*sp*e-1.5*e*e,c.z+dir.z*sp*e,cc.r,cc.g,cc.b,o*(1-ss(0.55,1,k))*(0.5+0.5*p[4])); } cdone(pt); }
function shockRing(c,k,col,maxR,o=1,vertical=false){ const r=rg(); r.position.copy(c); vertical?r.rotation.set(0,0,0):r.rotation.set(-Math.PI/2,0,0); const e=1-Math.pow(1-clamp(k),3); r.scale.setScalar(0.2+maxR*e); r.material.color.set(col).multiplyScalar(GLOW.k); r.material.opacity=o*(1-ss(0.35,1,k)); }



// ==================== EP11 本集镜头工具 ====================
const PJ=0x9dff5a, BLU=0x5aa8ff, OR=0xffb347;
function lab(k,str,x,y,o,opt={}){ const t=tx(k,str,Object.assign({color:'#e8f4ff',size:0.34,glow:CYAN},opt)); if(x!==null) hud(t,x,y,opt.d||9); op(t,o); return t; }   // x=null：世界坐标（调用方设 position）
function bar(col,x0,x1,y,o,w=10,d=9){ const l=ln(col,w); setLine(l,[hp(x0,y,d),hp(Math.abs(x1-x0)<0.001?x0+0.001:x1,y,d)]); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=20; return l; }
// Cd–Re 图表（镜头空间）：k＝画到哪（0–1）
const CH={x0:-4.3,x1:-0.3,y0:-2.6,y1:0.9};
function chart(o,parts,d=9){ const {x0,x1,y0,y1}=CH;
  const ax=ln(0x9fb8d0,2); setLine(ax,[hp(x0,y1+0.2,d),hp(x0,y0,d),hp(x1+0.2,y0,d)]); ax.material.opacity=o*0.7; ax.material.depthTest=false;
  lab('chY',T('阻力系数','drag coefficient'),x0+0.1,y1+0.45,o,{size:0.24,color:'#aab8c8'}); lab('chX',T('雷诺数（≈ 速度 × 球的大小）→','Reynolds number (≈ speed × size) →'),(x0+x1)/2,y0-0.4,o,{size:0.24,color:'#aab8c8'});
  for(const [arr,col,k] of parts){ if(k<=0) continue; const l=ln(new THREE.Color(col).multiplyScalar(0.55),5); setLine(l,curvePts(arr,x0,x1,y0,y1,k,d)); l.material.opacity=o*0.85; l.material.depthTest=false; l.renderOrder=20; } }   // 光晕标准：曲线是叠加发光，压暗
const chartP=(lx,cd,d=9)=>hp(lerp(CH.x0,CH.x1,(lx-4)/2.2),lerp(CH.y0,CH.y1,cd/0.7),d);
function dotAt(lx,cd,col,o,s=0.5){ const g=gs(col,s*0.8,o*0.55); g.position.copy(chartP(lx,cd)); g.renderOrder=21; g.material.depthTest=false; return g; }
const L10=(v_kmh)=>Math.log10(v_kmh/3.6*0.067/1.5e-5);   // 6.7 cm 球的 log10(Re)
// 在镜头空间画一颗球（大小以屏幕单位计）
function hball(m,x,y,R,d=9,o=1,spin=0){ showBall(m,hp(x,y,d),R,o,spin); }

// ---------- 1 钩子：网球为什么要长毛？→ 剃光 → 同一记 200 km/h 的发球：光球忽快忽慢、网球稳稳 118 → 刹车，更是稳定器 → 铁塔 ----------
function shotHook(u,D){
  const SH=ev('shave',3.6), SV=ev('serve',5.2), FK=ev('fork',7.6), WB=ev('wobble',13.1), SD=ev('steady',16.7), BR=ev('brake',22.4), STb=ev('stab',23.5), TW=ev('tower',25.8);
  if(u<SV-0.2){ // 微距：毛茸茸的网球自转 → 毛被一阵风剃飞
    look(Math.sin(u*0.3)*0.4,0.1,lerp(4.8,4.2,ss(0,SV,u)),0,0,0); rims(PJ,CY,4);
    const c=V(0,0,0); showBall(BL.tennis,c,1.0,1,u*0.6); const fz=1-ss(SH,SH+0.6,u); BL.fuzz(c,1.0,Math.max(0.02,fz)*1.6,1);
    if(u>SH){ const k=(u-SH)/1.4; burst(c.clone().add(V(0.3,0,0)),k,0xeaff80,4,0.9); showBall(BL.smooth,c,1.002,ss(SH+0.1,SH+0.5,u),u*0.6); BL.tennis.visible=ss(SH+0.1,SH+0.5,u)<0.999; /* 有毛的球保持不透明垫在下面，光球淡入盖住再撤：两颗都半透明会一起变暗、中间一帧几乎全空（motion_check 3.87s 跳变） */ }
    const q=bt('hkQ',T('网球为什么要长毛？','Why does a tennis ball wear fuzz?'),{size:0.95,glow:'rgba(214,238,58,0.55)',fx:'particles'}); hud(q,0,1.75,9); q.update(u,0.2,SH+0.4,0.85);
    return; }
  // 侧上方看球场：两条球道，同一记 200 km/h 的发球（按 v=v0/(1+k v0 t) 的阻力规律慢放）；光球两个幽灵＝悬崖前（Cd 0.5）/悬崖后（Cd 0.1）
  courtG.visible=true; ST_RATE=0.0005; const v=u-SV; const per=3.4; const L2_=11.885;
  look(19,9.5,1.5,0,1.4,0.5); rims(CY,GO,5);
  const k=(Math.max(0,v)%per)/per;
  const zAt=(cd)=>{ const kk=0.5*1.21*cd*Math.PI*0.0335*0.0335/0.0577; return Math.min(L2_+2,-L2_+Math.log(1+kk*55.6*k*0.55)/kk); };
  const o=ss(SV-0.2,SV+0.3,u)*(1-ss(TW-0.6,TW,u)); const ol=o*(1-ss(BR-0.7,BR-0.1,u));   // 大字出来前，标签先退场
  const flick=(Math.sin(u*11)+Math.sin(u*17.3))>0;
  const xS=0, xT=0, yb=1.0, yS=3.0;
  const zS=zAt(u<FK?0.5:(flick?0.1:0.5)), zT=zAt(0.6);
  showBall(BL.smooth,V(xS,yS,zS),0.42,o,u*3); showBall(BL.tennis,V(xT,yb,zT),0.42,o,u*3); BL.fuzz(V(xT,yb,zT),0.42,1.2,o); const gS=gs(0xffffff,1.6,0.3*o); gS.position.set(xS,yS,zS); const gT=gs(PJ,1.6,0.35*o); gT.position.set(xT,yb,zT);
  const tr1=ln(0xffffff,3); setLine(tr1,[V(xS,yS,-L2_),V(xS,yS,zS)]); tr1.material.opacity=0.5*o; const tr2=ln(PJ,3); setLine(tr2,[V(xT,yb,-L2_),V(xT,yb,zT)]); tr2.material.opacity=0.6*o;
  if(u>FK){ const g=0.4+0.6*Math.abs(Math.sin(u*9)); const gA=gs(0xffffff,1.4,0.35*o*g); gA.position.set(xS,yS,zAt(0.5)); const gB=gs(0xffffff,1.4,0.35*o*(1-g)); gB.position.set(xS,yS,zAt(0.1)); }
  const vS=u<FK?'—':(flick?'≈ 183':'≈ 129');
  lab('hkL1',T('光溜溜的球','bald ball'),null,0,ol,{size:1.2,color:'#ffffff'}).position.set(0,yS+1.3,-L2_+1.5);
  lab('hkL2',T('网球（有毛）','tennis ball (fuzz)'),null,0,ol,{size:1.2,color:'#d8ffc8',glow:'rgba(157,255,90,0.7)'}).position.set(0,yb-1.2,-L2_+1.5);
  lab('hkV0',T('同一记发球：出手 200 km/h','same serve: launched at 200 km/h'),0,3.0,o*ss(SV,SV+0.4,u),{size:0.34,color:'#ffe2a0',glow:GOLD,plate:true});
  const t1=tx('hkVS'+vS,T('到对面 '+vS+' km/h','at the far end '+vS+' km/h'),{color:'#ffffff',size:1.2,glow:CYAN}); t1.position.set(0,yS+1.3,L2_-3.0); op(t1,ol*ss(FK,FK+0.3,u));
  lab('hkVT',T('到对面 ≈ 118 km/h，每次都一样','at the far end ≈ 118 km/h, every time'),null,0,ol*ss(SD-0.4,SD+0.2,u),{size:1.1,color:'#d8ffc8',glow:'rgba(157,255,90,0.7)'}).position.set(0,yb-1.2,L2_-3.5);
  lab('hkWB',T('忽快忽慢','fast, then slow'),0,2.35,o*ss(WB,WB+0.4,u)*(1-ss(BR-0.5,BR,u)),{size:0.5,color:'#ffb0a8',glow:RED});
  const b1=bt('hkB',T('刹车','A BRAKE'),{size:1.0,glow:'rgba(214,238,58,0.5)',fx:'particles'}); hud(b1,-2.2,1.2,9); b1.update(u,BR,TW-0.4,0.82);
  const b2=bt('hkS',T('稳定器','A STABILISER'),{size:1.0,glow:'rgba(79,227,255,0.5)',fx:'particles'}); hud(b2,2.4,1.2,9); b2.update(u,STb,TW-0.4,0.82);
  if(u>TW-0.6){ TOWER.set(ss(TW-0.6,TW+0.8,u)); TOWER.g.position.set(0,0,0); TOWER.g.scale.setScalar(1.6); look(lerp(17,10,ss(TW-0.6,D,u)),lerp(15,3,ss(TW-0.6,D,u)),lerp(2,6,ss(TW-0.6,D,u)),0,lerp(0,2.4,ss(TW-0.6,D,u)),0); }
}

// ---------- 2 埃菲尔：铁塔拔地而起 → 风洞里的球 → 阻力突然掉 → 悬崖 0.5 → 0.1 → 阻力危机 → 普朗特的细线 ----------
const WIRE=new THREE.Mesh(new THREE.TorusGeometry(1.0,0.012,8,96),new THREE.MeshBasicMaterial({color:0xffe2a0,transparent:true,opacity:0})); WIRE.rotation.y=Math.PI/2; scene.add(WIRE);
function shotEiffel(u,D){
  const TN=ev('tunnel',2.8), DR=ev('drop',10.3), CL=ev('cliff',12.5), NM=ev('name',17.4), WR=ev('wire',21.9);
  rims(GO,CY,4); const a=0.15*Math.sin(u*0.2);
  TOWER.set(ss(0,1.4,u)); TOWER.g.position.set(-4.2,-2.6,-3); TOWER.g.scale.set(1.7,1.7*ss(0,1.6,u),1.7);
  look(Math.sin(a)*10,0.6,Math.cos(a)*10,0.2,0.4,0);
  // 风洞里的球：右上；风速随时间加快 → 过了悬崖分离角从 80° 跳到 120°
  const c=V(1.4,1.1,0), R=0.75; const speed=ss(TN,DR+1.5,u); const crisis=ss(DR-0.2,DR+0.6,u); const wired=ss(WR,WR+0.6,u);
  const sep=lerp(80,120,Math.max(crisis*(1-ss(WR-1.2,WR-0.4,u)),wired));
  if(u>TN-0.4){ FLOW.draw(c,R,sep,0.3,ss(TN-0.4,TN+0.4,u),u,0x9fd8ff,0.3+0.6*speed); showBall(BL.smooth,c,R,1,0); }
  WIRE.material.opacity=wired; WIRE.position.copy(c); WIRE.scale.setScalar(R*1.01);
  lab('eiY',T('1912 · 埃菲尔的风洞','1912 · Eiffel’s wind tunnel'),0.8,3.0,ss(0.6,1.2,u),{size:0.32,color:'#ffe2a0',glow:GOLD,plate:true});
  // 右下的 Cd–Re 图（只画光滑球那条），点随风速滑；到悬崖掉下去
  const o=ss(DR-1.0,DR-0.3,u); CH.x0=0.4; CH.x1=4.4; CH.y0=-2.7; CH.y1=-0.3;
  chart(o,[[CURVE.smooth,0xffffff,ss(DR-1.0,CL+1.0,u)]]);
  const lx=lerp(4.6,5.75,ss(DR-0.8,CL+1.0,u)); dotAt(lx,CURVE.at(CURVE.smooth,lx),0xffffff,o*0.8,0.6);
  lab('eiA',T('约 0.5','≈ 0.5'),CH.x0+0.9,lerp(CH.y0,CH.y1,0.5/0.7)+0.3,o*ss(CL,CL+0.4,u),{size:0.3});
  lab('eiB',T('约 0.1','≈ 0.1'),CH.x0+3.0,lerp(CH.y0,CH.y1,0.1/0.7)+0.25,o*ss(CL+0.6,CL+1.0,u),{size:0.3,color:'#ffd27a'});
  CH.x0=-4.3; CH.x1=-0.3; CH.y0=-2.6; CH.y1=0.9;
  const t=bt('eiT',T('阻力危机','DRAG CRISIS'),{size:1.05,glow:'rgba(255,90,74,0.5)',fx:'particles'}); hud(t,-0.2,1.9,9); t.update(u,NM,WR-0.3,0.82);
  lab('eiW',T('1914 · 普朗特：绑一圈细线，阻力也掉了','1914 · Prandtl: a thin wire ring, and drag drops too'),0.8,2.4,ss(WR,WR+0.5,u),{size:0.3,color:'#ffe2a0',glow:GOLD});
}

// ---------- 3 边界层：钻到球面 → 层流早分离、尾流宽 → 湍流贴得更久、尾流窄 → 雷诺数 ----------
function shotLayer(u,D){
  const BLt=ev('bl',3.4), LM=ev('lam',6.7), SP=ev('sep',8.4), TB=ev('turb',16.0), NR=ev('narrow',21.0), RE=ev('re',25.8);
  rims(CY,OR,4); const k=ss(0,2.0,u); look(lerp(0.2,0.0,k),lerp(0.6,0.3,k),lerp(4.0,9.5,k),1.2,0.0,0);
  const c=V(0,0,0), R=1.4; const tt=ss(TB-0.3,TB+1.6,u); const sep=lerp(80,120,tt);
  FLOW.draw(c,R,sep,0.2+0.8*(1-tt),1,u,0x9fd8ff,0.45,0.32); showBall(BL.smooth,c,R,1,0);
  // 边界层：贴着球面的一圈细亮线
  const bl=ln(CY,4); const pts=[]; for(let i=0;i<=40;i++){ const a=Math.PI-i/40*(sep*Math.PI/180); pts.push(V(Math.cos(a)*R*1.05,Math.sin(a)*R*1.05,0)); } setLine(bl,pts); bl.material.opacity=ss(BLt,BLt+0.5,u);
  const bl2=ln(CY,4); setLine(bl2,pts.map(p=>V(p.x,-p.y,0))); bl2.material.opacity=ss(BLt,BLt+0.5,u);
  lab('lyB',T('边界层','boundary layer'),null,0,ss(BLt,BLt+0.5,u),{size:0.34}).position.set(-1.6,1.55,0.2);
  // 分离点
  const sa=Math.PI-sep*Math.PI/180; const spP=V(Math.cos(sa)*R*1.05,Math.sin(sa)*R*1.05,0);
  if(u>SP-0.3){ const g=gs(OR,0.6,0.6*ss(SP-0.3,SP+0.3,u)); g.position.copy(spP); const g2=gs(OR,0.6,0.6*ss(SP-0.3,SP+0.3,u)); g2.position.copy(V(spP.x,-spP.y,0));
    const l=lab('lyS',T('分离点','separation'),null,0,ss(SP,SP+0.4,u),{size:0.3,color:'#ffd27a',glow:GOLD}); l.position.copy(spP).add(V(0.2,0.45,0.2)); }
  lab('lyL',T('层流：早早脱开，尾流宽','laminar: separates early, wide wake'),3.0,2.4,ss(LM,LM+0.5,u)*(1-ss(TB-0.3,TB,u)),{size:0.32});
  lab('lyT',T('湍流：贴得更久，尾流变窄','turbulent: hugs longer, narrow wake'),3.0,2.4,ss(TB,TB+0.5,u),{size:0.32,color:'#ffd27a',glow:GOLD});
  // 尾流宽度标尺 + 阻力条
  const w=Math.sin(sep*Math.PI/180)*R; const ox=c.x+R*2.6; const l1=ln(OR,3); setLine(l1,[V(ox,w,0),V(ox,-w,0)]); l1.material.opacity=ss(NR-0.4,NR+0.3,u);
  const dragK=lerp(1,0.25,tt); bar(RED,-4.2,-4.2+3.2*dragK,-2.5,ss(LM,LM+0.6,u),16); lab('lyD',T('阻力','drag'),-4.7,-2.5,ss(LM,LM+0.6,u),{size:0.3,color:'#ffb0a8'});
  const r=lab('lyR',T('雷诺数 ≈ 速度 × 球的大小 ÷ 空气的黏性','Reynolds number ≈ speed × size ÷ air viscosity'),0,-1.9,ss(RE,RE+0.5,u),{size:0.32,plate:true});
  lab('lyR2',T('约 30 万：悬崖在这里','≈ 300,000: the cliff is here'),0,-2.55,ss(RE+1.5,RE+2.0,u),{size:0.34,color:'#ffd27a',glow:GOLD});
}

// ---------- 4 高尔夫：凹坑里的小涡 → 曲线左移 → 出手就在悬崖下 ----------
function shotGolf(u,D){
  const DM=ev('dimple',3.9), SF=ev('shift',7.0), DV=ev('drive',9.8);
  rims(CY,GO,4); look(Math.sin(u*0.1)*0.5,0.3,9.5,0.6,0.2,0);
  const c=V(1.6,1.0,0), R=0.9; FLOW.draw(c,R,120,0.3,1,u,0x9fd8ff,0.55,0.3); showBall(BL.golf,c,R,1,u*0.3);
  if(u>DM){ const cc=new THREE.Color(0xffd27a); for(let i=0;i<300;i++){ const p=PTS[i]; const a=Math.PI*(0.25+0.75*p[3])*(p[4]>0.5?1:-1); const s=0.03+0.02*Math.sin(u*9+i); const q=V(c.x+Math.cos(a)*R*(1.03+s),c.y+Math.sin(a)*R*(1.03+s),c.z+(p[2]/8)*0.2); cset(pt,i,q.x,q.y,q.z,cc.r,cc.g,cc.b,ss(DM,DM+0.6,u)*0.8); } cdone(pt); }
  lab('gfD',T('凹坑：把边界层提前搅乱','dimples trip the boundary layer early'),null,0,ss(DM,DM+0.5,u),{size:0.3,color:'#ffd27a',glow:GOLD}).position.copy(c).add(V(0,R+0.55,0));
  CH.x0=-4.6; CH.x1=-0.6; CH.y0=-2.7; CH.y1=0.5; const o=ss(SF-0.6,SF,u);
  chart(o,[[CURVE.smooth,0xffffff,1],[CURVE.golf,0xffd27a,ss(SF,SF+1.2,u)]]);
  lab('gfS',T('光滑球','smooth'),CH.x1-0.4,lerp(CH.y0,CH.y1,0.16/0.7)+0.3,o,{size:0.26}); lab('gfG',T('高尔夫','golf'),CH.x0+1.6,lerp(CH.y0,CH.y1,0.3/0.7)+0.2,o*ss(SF+0.6,SF+1.2,u),{size:0.26,color:'#ffd27a'});
  if(u>DV){ const lx=Math.log10(75*0.0411/1.5e-5); dotAt(lx,CURVE.at(CURVE.golf,lx),0xffd27a,ss(DV,DV+0.4,u),0.7); lab('gfV',T('一记开球：已经在悬崖下面','a drive: already past the cliff'),CH.x0+2.0,CH.y1+0.6,ss(DV,DV+0.4,u),{size:0.3,color:'#ffd27a'}); }
  CH.x0=-4.3; CH.x1=-0.3; CH.y0=-2.6; CH.y1=0.9;
}

// ---------- 5 足球：卡在悬崖边 → 不转时尾流忽左忽右 → 电梯球 ----------
function shotFootball(u,D){
  const ED=ev('edge',4.6), KN=ev('knuckle',8.2);
  rims(CY,RED,4); look(0,0.4,9.5,0,0.2,0);
  const sk=ss(KN-0.5,KN+0.5,u)*Math.sin(u*3.1)*0.9; const c=V(-0.6+sk*0.12,0.6+sk*0.25,0), R=0.95;
  FLOW.draw(c,R,lerp(80,110,ss(ED,ED+1,u)),0.8,1,u,0x9fd8ff,0.5,0.3,sk); showBall(BL.foot,c,R,1,0);
  if(u>KN){ const tr=ln(0xffffff,3); const pts=[]; for(let i=0;i<=40;i++){ const x=-5+i*0.25; pts.push(hp(x,-2.0+0.35*Math.sin(i*0.6+u*2)*ss(KN,KN+1,u),9)); } setLine(tr,pts); tr.material.opacity=0.6*ss(KN,KN+0.6,u); tr.material.depthTest=false; }
  lab('fbE',T('足球的速度：正好卡在悬崖边','a football’s speed sits right at the cliff edge'),0,2.6,ss(ED,ED+0.5,u),{size:0.32});
  lab('fbK',T('不转时，尾流忽左忽右 → 电梯球','no spin: the wake flips side to side → knuckleball'),0,-2.6,ss(KN,KN+0.5,u),{size:0.32,color:'#ffb0a8',glow:RED});
}

// ---------- 6 网球：职业球速段正好压在光滑球的悬崖上 → 没毛就时上时下 → 毛把悬崖抹平（约 0.6）→ 三组测量 → 一来一回 ----------
function shotTennis(u,D){
  const BD=ev('band',6.0), FP=ev('flip',12.8), FL=ev('flat',17.1), FZ=ev('fuzz',17.9), CD=ev('cd',21.7), LB=ev('labs',24.7), RL=ev('rally',31.8);
  const q=bt('tnQ',T('那网球呢？','And the tennis ball?'),{size:0.9,glow:'rgba(214,238,58,0.5)',fx:'particles'}); hud(q,0,0.4,9); q.update(u,0.3,2.6,0.85);
  if(u<RL-0.4){
    rims(PJ,CY,4); look(Math.sin(u*0.06)*0.4,0.3,9.5,0,0.3,0);
    const o=ss(2.4,3.2,u)*(1-ss(RL-0.9,RL-0.4,u));
    CH.x0=-3.6; CH.x1=3.6; CH.y0=-2.5; CH.y1=1.3;
    chart(o,[[CURVE.smooth,0xffffff,1],[CURVE.tennis,PJ,ss(FL,FL+1.5,u)]]);
    // 职业球速段 100–250 km/h
    if(u>BD){ const a=L10(100), b=L10(250); const ob=o*ss(BD,BD+0.6,u); const xa=lerp(CH.x0,CH.x1,(a-4)/2.2), xb=lerp(CH.x0,CH.x1,(b-4)/2.2);
      for(let i=0;i<14;i++){ const x=lerp(xa,xb,i/13); const l=ln(GO,2); setLine(l,[hp(x,CH.y0,9),hp(x,CH.y1,9)]); l.material.opacity=ob*0.25; l.material.depthTest=false; }
      lab('tnBd',T('职业比赛的球速 100–250 km/h','pro ball speeds 100–250 km/h'),(xa+xb)/2,CH.y1+0.45,ob,{size:0.3,color:'#ffd27a',glow:GOLD}); }
    if(u>FP && u<FL+0.5){ const f=(Math.sin(u*6)+Math.sin(u*9.7))>0; const lx=L10(230); dotAt(lx,f?0.1:0.48,0xffffff,0.9*ss(FP,FP+0.4,u)*(1-ss(FL,FL+0.5,u)),0.7);
      lab('tnFp',T('没毛的网球：一会儿在悬崖上，一会儿掉下去','without fuzz: on the cliff, then off it'),0,-3.05,ss(FP,FP+0.4,u)*(1-ss(FL,FL+0.5,u)),{size:0.3,color:'#ffffff'}); }
    if(u>FL){ for(const v of [100,160,230]){ const lx=L10(v); dotAt(lx,CURVE.at(CURVE.tennis,lx),PJ,ss(FL+1,FL+1.5,u),0.55); } }
    lab('tnCd',T('网球：约 0.6，没有悬崖','tennis ball: ≈ 0.6, no cliff'),lerp(CH.x0,CH.x1,0.75),lerp(CH.y0,CH.y1,0.6/0.7)+0.45,ss(CD,CD+0.5,u)*o,{size:0.36,color:'#d8ffc8',glow:'rgba(157,255,90,0.7)'});
    lab('tnLb',T('三组风洞与理论测量，结论一致','three independent measurements agree'),0,-3.05,ss(LB,LB+0.5,u)*o,{size:0.3});
    // 绒毛显微：右上角一颗大网球，毛尖拖出小涡
    const fo=ss(FZ-0.3,FZ+0.6,u)*(1-ss(LB-0.4,LB,u)); if(fo>0){ const c=hp(2.75,1.75,7); showBall(BL.tennis,c,0.55,fo,u*0.3); BL.fuzz(c,0.55,2.2,fo);
      const cc=new THREE.Color(0xeaff80).multiplyScalar(0.5); for(let i=0;i<500;i++){ const p=PTS[i]; const a=(p[3]-0.5)*Math.PI*1.2+Math.PI*0.5*(p[4]>0.5?1:-1); const r=0.55*(1.12+0.05*Math.sin(u*8+i)); const sw=0.05*Math.sin(u*6+i*1.3);
        const q=c.clone().add(V(Math.cos(a)*r+sw+((u*0.6+p[0])%1)*0.4,Math.sin(a)*r,0)); cset(pt,i,q.x,q.y,q.z,cc.r,cc.g,cc.b,fo*0.6); } cdone(pt);
      lab('tnFz',T('每根毛自己都在挡风','every fibre adds its own drag'),3.1,0.6,fo,{size:0.3,color:'#eaff80',glow:'rgba(214,238,58,0.6)'}); }
    CH.x0=-4.3; CH.x1=-0.3; CH.y0=-2.6; CH.y1=0.9; return; }
  // 一来一回：带看台的球场，网球在两端之间稳稳往返
  courtG.visible=true; ST_RATE=0.0008; const k=ss(RL-0.4,D,u); look(lerp(9,7,k),lerp(4.5,3.8,k),lerp(13,11,k),0,0.6,0); rims(PJ,CY,5);
  const per=1.6, f=((u-RL)%per)/per, dir=Math.floor((u-RL)/per)%2; const z=lerp(-10,10,dir?1-f:f); const y=0.5+1.4*Math.sin(Math.PI*f);
  const p=V(0.6*Math.sin(u),y,z); showBall(BL.tennis,p,0.12,1,u*4); BL.fuzz(p,0.12,1,1); const g=gs(PJ,0.6,0.35); g.position.copy(p);
  const t=bt('tnR',T('慢一点、稳一点，才有一来一回','Slower, steadier — that’s what makes a rally'),{size:0.7,glow:'rgba(214,238,58,0.45)',fx:'particles'}); hud(t,0,2.3,9); t.update(u,RL+0.2,D-0.1,0.82);
}

// ---------- 7 毛的状态：紧的毛 vs 蓬的毛 → 尾流与阻力 → 球员挑球 → 帕特·卡什 ----------
function shotFluff(u,D){
  const FLc=ev('fl',2.6), PK=ev('pick',8.2), CS=ev('cash',11.2);
  rims(PJ,GO,4); look(0,0.4,9.5,0,0.3,0);
  if(u<PK-0.3){ const o=ss(0,0.6,u); const a=hp(-2.4,0.6,9.5), b=hp(2.4,0.6,9.5);
    showBall(BL.tennis,a,0.8,o,u*0.4); showBall(BL.tennis2,b,0.8,o,u*0.4); BL.fuzz(b,0.8,3.2,o);
    // 右边那颗用另一份毛壳：蓬
    FLOW.draw(b,0.8,85,0.6,o*ss(FLc,FLc+0.6,u),u,0x9fd8ff,0.4,0.2);
    const cc=new THREE.Color(0xeaff80).multiplyScalar(0.5); for(let i=0;i<900;i++){ const p=PTS[i%1600]; const uu=p[3]*2-1, ang=p[4]*6.283, s=Math.sqrt(1-uu*uu); const r=0.8*(1+0.22*(0.2+0.8*((i*7)%10)/10)+0.02*Math.sin(u*5+i)); cset(pt,700+i%900,b.x+s*Math.cos(ang)*r,b.y+uu*r,b.z+s*Math.sin(ang)*r,cc.r,cc.g,cc.b,o); }
    cdone(pt); const tb=BL.tennis.clone();
    lab('flA',T('毛紧','tight felt'),-2.4,-0.7,o,{size:0.34,color:'#d8ffc8'}); lab('flB',T('毛蓬','fluffed-up felt'),2.4,-0.7,o,{size:0.34,color:'#ffd27a'});
    lab('flD',T('毛越蓬，阻力越大','the fluffier, the more drag'),0,2.4,ss(FLc,FLc+0.5,u),{size:0.38,color:'#ffffff'});
    return; }
  // 挑球：全息球员在底线前，三颗球悬在手前，挑出毛紧的那颗
  courtG.visible=true; ST_RATE=0.0004; const H=RET; humanOp(H,1); place(H,0.3,11.0,Math.PI); applyPose(H,POSE.stand);
  look(2.6,1.6,14.4,0.3,1.1,11.0); rims(PJ,CY,5);
  const hand=V(0.3,1.15,10.4); const pp=[]; for(let i=0;i<3;i++){ const p=hand.clone().add(V((i-1)*0.22,0.05*Math.sin(u*2+i)+(i===1?ss(PK+0.8,PK+1.6,u)*0.25:0),0)); pp.push(p); }
  showBall(BL.tennis,pp[1],0.06,1,u); BL.fuzz(pp[1],0.06,0.8,1); showBall(BL.smooth,pp[0],0.062,0.9,u); showBall(BL.golf,pp[2],0.001,0,0);
  const cc=new THREE.Color(0xeaff80); for(const [q,amt] of [[pp[0],1.6],[pp[2],1.6]]){ for(let i=0;i<120;i++){ const p=PTS[i]; const uu=p[3]*2-1, ang=p[4]*6.283, s2=Math.sqrt(1-uu*uu); const r=0.062*(1+0.25*amt*0.5); cset(pt,(q===pp[0]?0:200)+i,q.x+s2*Math.cos(ang)*r,q.y+uu*r,q.z+s2*Math.sin(ang)*r,cc.r,cc.g,cc.b,0.8); } } cdone(pt);
  const sel=pp[1]; const g=gs(PJ,0.4,0.5*ss(PK+0.8,PK+1.4,u)); g.position.copy(sel);
  lab('flP',T('发球前，挑一颗毛不蓬的','before serving: pick the one with tight felt'),0,2.5,ss(PK,PK+0.5,u),{size:0.34});
  lab('flC',T('「发球，你要一颗没起毛的球。」——帕特·卡什，1987 温网冠军','“If you’re serving, you want a ball that isn’t fluffed up.” — Pat Cash, 1987 Wimbledon champion'),0,-2.4,ss(CS,CS+0.6,u),{size:0.3,color:'#ffe2a0',glow:GOLD,plate:true});
}

// ---------- 8 国际网联 3 号球：大约 6%，重量不变 → 迎风面积大、阻力大 ----------
function shotItf(u,D){
  const BG=ev('big',4.0), AR=ev('area',9.7);
  rims(CY,GO,4); look(0,0.4,9.5,0,0.3,0); const o=ss(0,0.6,u);
  const a=hp(-2.0,0.4,9.5), b=hp(2.0,0.4,9.5); const s=lerp(1.0,1.066,ss(BG,BG+1.0,u));
  showBall(BL.tennis,a,0.9,o,u*0.3); BL.fuzz(a,0.9,1,o);
  showBall(BL.tennis2,b,0.9*s,o,u*0.3);
  const r1=rg(); r1.position.copy(a); r1.rotation.set(0,0,0); r1.scale.setScalar(0.9*1.02); r1.material.opacity=0.6*ss(AR,AR+0.5,u);
  const r2=rg(); r2.position.copy(b); r2.rotation.set(0,0,0); r2.scale.setScalar(0.9*s*1.02); r2.material.opacity=0.8*ss(AR,AR+0.5,u);
  lab('itA',T('标准球（2 号）','standard ball (type 2)'),-2.0,-1.0,o,{size:0.32}); lab('itB',T('3 号球：大约 6%，重量不变','type 3: about 6% bigger, same weight'),2.0,-1.0,ss(BG,BG+0.5,u),{size:0.32,color:'#ffd27a',glow:GOLD});
  lab('itC',T('给快场地、海拔 1219 米以上用','for fast courts and altitude above 1,219 m'),2.0,-1.55,ss(BG+1.0,BG+1.5,u),{size:0.28,color:'#aab8c8'});
  lab('itD',T('迎风面积大了 → 阻力大了 → 球慢了','bigger frontal area → more drag → slower ball'),0,2.4,ss(AR,AR+0.5,u),{size:0.36});
}

// ---------- 9 结论 ＋ 问句 ----------
function shotEnd(u,D){
  const SL=ev('slow',5.9), QQ=ev('q',10.7);
  rims(PJ,CY,5); const a=0.3+u*0.03; look(Math.sin(a)*6,0.4,Math.cos(a)*6,0,0,0);
  const c=V(0,0,0); FLOW.draw(c,1.1,118,0.2,1-ss(QQ-0.5,QQ,u),u,0x9fd8ff,0.45,0.25); showBall(BL.tennis,c,1.1,1,u*0.4); BL.fuzz(c,1.1,1.4,1);
  const t=bt('ndT',T('网球的毛：刹车，也是稳定器','The fuzz: a brake, and a stabiliser'),{size:0.85,glow:'rgba(214,238,58,0.45)',fx:'particles'}); hud(t,0,2.3,9); t.update(u,0.5,QQ-0.4,0.8);
  const q=bt('ndQ',T('你发球前，会挑毛不蓬的那一颗吗？','Before you serve, do you pick the tight one?'),{size:0.75,glow:'rgba(79,227,255,0.45)',fx:'particles'}); hud(q,0,-2.0,9); q.update(u,QQ,D+5,0.82);
}

const SHOTS={hook:shotHook,eiffel:shotEiffel,layer:shotLayer,golf:shotGolf,football:shotFootball,tennis:shotTennis,fluff:shotFluff,itf:shotItf,end:shotEnd};
function shotTest(u,D){ look(0,0,8,0,0,0); }

// ---------- 后期 ----------
const composer=new EffectComposer(renderer,new THREE.WebGLRenderTarget(W,H,{samples:4,type:THREE.HalfFloatType})); composer.addPass(new RenderPass(scene,camera));
const bokeh=new BokehPass(scene,camera,{focus:10,aperture:0.0001,maxblur:0.008}); composer.addPass(bokeh);
const bloom=new UnrealBloomPass(new THREE.Vector2(W/2,H/2),...GLOW.bloom); composer.addPass(bloom); if(Q.get('bloom')==='0') bloom.enabled=false;   // 光晕全局标准：glow_check 用开／关泛光两帧相减量光晕
const finalPass=new ShaderPass({uniforms:{tDiffuse:{value:null},uT:{value:0},uFlash:{value:0},uCA:{value:0.0016},uZoom:{value:0},uShake:{value:0}},
  vertexShader:`varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader:`uniform sampler2D tDiffuse; uniform float uT,uFlash,uCA,uZoom,uShake; varying vec2 vUv; float h(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453); }
   void main(){ vec2 uv=vUv+vec2(sin(uT*91.)*0.004,cos(uT*77.)*0.004)*uShake; vec2 c=uv-0.5; vec3 col=vec3(0.);
     if(uZoom>0.){ for(int k=0;k<10;k++){ float s=1.0-uZoom*0.05*float(k); col+=texture2D(tDiffuse,0.5+c*s).rgb; } col/=10.; }
     else col=vec3(texture2D(tDiffuse,uv+c*uCA).r,texture2D(tDiffuse,uv).g,texture2D(tDiffuse,uv-c*uCA).b);
     float vig=smoothstep(1.05,0.3,length(c*vec2(1.0,0.85))); col*=mix(0.5,1.0,vig); col+=(h(uv*vec2(1920.,1080.)+uT)-0.5)*0.022; col=mix(col,vec3(1.),uFlash); gl_FragColor=vec4(col,1.); }`});
composer.addPass(finalPass); composer.addPass(new OutputPass());
const rtPrev=new THREE.WebGLRenderTarget(W,H,{type:THREE.HalfFloatType});
const accRT=[0,1].map(()=>new THREE.WebGLRenderTarget(W,H,{type:THREE.HalfFloatType}));
const blendQuad=new FullScreenQuad(new THREE.ShaderMaterial({uniforms:{tA:{value:null},tB:{value:null},k:{value:0.5}},vertexShader:`varying vec2 vUv; void main(){ vUv=uv; gl_Position=vec4(position.xy,0.,1.); }`,fragmentShader:`uniform sampler2D tA,tB; uniform float k; varying vec2 vUv; void main(){ gl_FragColor=mix(texture2D(tA,vUv),texture2D(tB,vUv),k); }`}));
const copyQuad=new FullScreenQuad(new THREE.ShaderMaterial({uniforms:{tDiffuse:{value:null}},vertexShader:`varying vec2 vUv; void main(){ vUv=uv; gl_Position=vec4(position.xy,0.,1.); }`,fragmentShader:`uniform sampler2D tDiffuse; varying vec2 vUv; void main(){ gl_FragColor=texture2D(tDiffuse,vUv); }`}));
const xfPass=new ShaderPass({uniforms:{tDiffuse:{value:null},tPrev:{value:null},uMix:{value:1},uPush:{value:0}},
  vertexShader:`varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader:`uniform sampler2D tDiffuse,tPrev; uniform float uMix,uPush; varying vec2 vUv; void main(){ vec4 cur=texture2D(tDiffuse,vUv); vec4 pre=texture2D(tPrev,0.5+(vUv-0.5)*(1.0-uPush)); gl_FragColor=mix(pre,cur,uMix); }`});
xfPass.uniforms.tPrev.value=rtPrev.texture;   // ShaderPass 会克隆 uniforms，渲染目标的贴图克隆不过去，得事后再挂
xfPass.enabled=false; composer.addPass(xfPass);
let FX_SHAKE=0, FX_FLASH=0, EV={}; const ev=(k,d)=>(EV[k]!==undefined?EV[k]:d);
function setTransition(t){ const z=0,f=0;   // 2026-11-05 起切换一律交叉溶解（见 renderAt），不再闪白＋径向模糊
  finalPass.uniforms.uZoom.value=z; finalPass.uniforms.uFlash.value=Math.max(f,FX_FLASH); finalPass.uniforms.uT.value=t; finalPass.uniforms.uShake.value=FX_SHAKE; }
function setPalette(t){ const i=TL.sections.findIndex(s=>t>=s.t0&&t<s.t1); const cur=PAL[TL.sections[Math.max(0,i)].kind]||PAL.hook, prev=i>0?(PAL[TL.sections[i-1].kind]||cur):cur;
  const k=i>0?ss(TL.sections[i].t0,TL.sections[i].t0+1.0,t):1;
  skyMat.uniforms.uTop.value.set(prev.top).lerp(C(cur.top),k); skyMat.uniforms.uHz.value.set(prev.hz).lerp(C(cur.hz),k); skyMat.uniforms.uVi.value.set(prev.vi).lerp(C(cur.vi),k);
  scene.userData.grid.uniforms.uC.value.set(prev.a).lerp(C(cur.a),k).multiplyScalar(0.55); if(NOTEXT) scene.userData.grid.uniforms.uC.value.set(0x000000);   /* 封面底图：地网在高分辨率下穿过球心成一条横带，封面不要它 */
  return C(prev.a).lerp(C(cur.a),k); }
function shotTL(t){ const sc=TL.sections.find(s=>t>=s.t0&&t<s.t1)||TL.sections[TL.sections.length-1]; const u=t-sc.t0, D=sc.t1-sc.t0;
  hideAll(); FX_SHAKE=0; FX_FLASH=0; EV=sc.ev||{}; SEC_U=u;
  (SHOTS[sc.kind]||shotTest)(u,D); standsTick(t,sc.kind,u);
  if(Q.get('cam')){ const c=Q.get('cam').split(',').map(Number); look(...c); }   // 封面机位覆盖
  flushHud(); layoutText();
  return sc.kind; }
// 镜头切换点：载入时按机位跳变自动找（粗扫 10 fps、跳变附近细到 1/240 s），再并上段落起点
let CUTS=[];
function rawCam(t){ CAMMOVE=null; shotTL(t); return [camera.position.clone(), new THREE.Vector3(0,0,-1).applyQuaternion(camera.quaternion)]; }
function jumped(a,b,dp,da){ return a[0].distanceTo(b[0])>dp || a[1].angleTo(b[1])>da; }
function findCuts(){ const out=new Set(TL.sections.filter(s=>s.t0>0).map(s=>+s.t0.toFixed(4))); const step=0.1; let prev=rawCam(0);
  for(let t=step;t<TL.total;t+=step){ const cur=rawCam(t);
    if(jumped(prev,cur,0.6,0.12)){ let lo=t-step, hi=t, pl=rawCam(lo);   // 二分到 1/240 s
      while(hi-lo>1/240){ const m=(lo+hi)/2, pm=rawCam(m); if(jumped(pl,pm,0.6*(m-lo)/step+0.05,0.12*(m-lo)/step+0.01)){ hi=m; } else { lo=m; pl=pm; } }
      if(jumped(rawCam(lo),rawCam(hi),0.15,0.03)) out.add(+hi.toFixed(4)); }
    prev=cur; }
  const v=[...out].sort((x,y)=>x-y); return v.filter((c,i)=>i===0||c-v[i-1]>0.1); }
function segOf(t){ let a=0,b=TL.total,i=0; for(const c of CUTS){ if(c<=t){ a=c; i++; } else { b=c; break; } } return {a,b,i}; }
function setState(t){ for(const k in anchors) delete anchors[k]; allClouds.forEach(c=>c.material.uniforms.uT.value=t);
  const g=segOf(t); CAMMOVE={u:t-g.a,L:Math.max(1,g.b-g.a),dir:(g.i%2?1:-1)};
  const s=shotTL(t); const ac=setPalette(t); setTransition(t); setMotes(t,ac);
  bokeh.enabled=DOF.on; if(DOF.on){ bokeh.uniforms.focus.value=DOF.focus; bokeh.uniforms.aperture.value=DOF.ap; bokeh.uniforms.maxblur.value=0.009; }
  return s; }
window.renderAt=(t)=>{
  const c=CUTS.find(c=>t>=c-0.01&&t<c+MOVE.xf);   // 提前 0.01 s：切换点只精确到 1/240 s，免得正好落在切换后的那一帧先硬切
  if(c!==undefined){ // 交叉溶解：切换前最后一帧缓缓推近、淡出，新镜头淡入
    setState(c-0.02); xfPass.enabled=false; composer.renderToScreen=false; composer.render();
    copyQuad.material.uniforms.tDiffuse.value=composer.readBuffer.texture; renderer.setRenderTarget(rtPrev); copyQuad.render(renderer); renderer.setRenderTarget(null);
    composer.renderToScreen=true; const k=ss(-0.01,MOVE.xf,t-c); xfPass.enabled=true; xfPass.uniforms.uMix.value=k; xfPass.uniforms.uPush.value=MOVE.xfPush*k; }
  else xfPass.enabled=false;
  let s=setState(t);
  if(SLOW&&!xfPass.enabled&&SEC_U>=SLOW[0]&&SEC_U<=SLOW[1]&&Q.get('blur')!=='0'){ // 子弹时间：窗口内（段内秒 SLOW=[a,b]）累积 6 个子帧做运动模糊
    const N=6, dt=1/40; composer.renderToScreen=false;
    for(let i=0;i<N;i++){ s=setState(t-dt*(i/(N-1))); composer.render(); copyQuad.material.uniforms.tDiffuse.value=composer.readBuffer.texture; renderer.setRenderTarget(accRT[i%2]); if(i===0){ copyQuad.render(renderer); } else { blendQuad.material.uniforms.tA.value=accRT[(i+1)%2].texture; blendQuad.material.uniforms.tB.value=composer.readBuffer.texture; blendQuad.material.uniforms.k.value=1/(i+1); blendQuad.render(renderer); } }
    renderer.setRenderTarget(null); copyQuad.material.uniforms.tDiffuse.value=accRT[(N-1)%2].texture; copyQuad.render(renderer); composer.renderToScreen=true; s=setState(t); }
  else composer.render();
  return JSON.stringify(Object.assign({_shot:s},anchors)); };
window.CUTS=()=>CUTS;
Promise.all([FONT_READY,document.fonts.ready,loadTypeFonts()]).then(()=>{ CUTS=findCuts(); window.READY=true; }).catch(e=>console.error('READY failed',e));
// 自检：可见的 3D 字有没有出画、压进底部字幕带（y>880）或顶部标题带（y<120）——review_pack 前先跑 tools 里的 textcheck
window.textCheck=()=>{ camera.updateMatrixWorld(); const out=[]; const R=new THREE.Vector3(1,0,0).applyQuaternion(camera.quaternion);
  for(const k in TT){ const s=TT[k]; if(!s.visible||s.material.opacity<0.15) continue; const p=new THREE.Vector3(); s.getWorldPosition(p);
    const hw=s.scale.x*0.5*(s.parent&&s.parent.scale?s.parent.scale.x:1), hh=s.scale.y*0.35; const pr=v=>{ const q=v.clone().project(camera); return [(q.x*0.5+0.5)*W,(1-(q.y*0.5+0.5))*H,q.z]; };
    const a=pr(p.clone().addScaledVector(R,-hw)), b=pr(p.clone().addScaledVector(R,hw)), c=pr(p), up=pr(p.clone().add(new THREE.Vector3(0,hh,0).applyQuaternion(camera.quaternion))), dn=pr(p.clone().add(new THREE.Vector3(0,-hh,0).applyQuaternion(camera.quaternion)));
    if(c[2]>1) continue; const x0=Math.min(a[0],b[0]), x1=Math.max(a[0],b[0]), y0=Math.min(up[1],dn[1]), y1=Math.max(up[1],dn[1]);
    const f=1920/W; if(x0*f<37||x1*f>1883||y0*f<117||y1*f>883) out.push([k,Math.round(x0*f),Math.round(x1*f),Math.round(y0*f),Math.round(y1*f)]); }
  return out; };
