// vibetennis EP12 抢七轮发：为什么是「一、二、二、二」——在「每分独立」模型里，一人一分和 1-2-2-2 的胜率完全一样；让抢七公平的是净胜两分。1-2-2-2 少换手、不让谁一直追，它是 Thue–Morse 序列的第一层。
// 理论与上屏数字的出处见 papers/vibetennis-tiebreak-2026/sources.md（两源规则），概率由同目录 tiebreak_math.py 复现。
// 通用底座（夜空、光点、全息字、3D 字、球场、看台、全息人体、后期）沿用 EP06–EP11；序列格、发球次数账本、天平、Thue–Morse 条码塔、球门为本集新做（src/shots.js）。


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
  hook:  {top:0x05030f,hz:0x1a1048,vi:0x3a0a3a,a:0x30e8ff,b:0xffc24a,c:0xffffff},   // 电光青＋金：中央球场之夜
  rule:  {top:0x030812,hz:0x0b2a50,vi:0x0a2030,a:0xe8f6ff,b:0x4fe3ff,c:0xffffff},   // 规则书冰白
  edge:  {top:0x0b0602,hz:0x3a2208,vi:0x2a1406,a:0xffb347,b:0xffe2a0,c:0xffffff},   // 发球占优：琥珀
  math:  {top:0x04040e,hz:0x14163a,vi:0x1a1a2e,a:0xc9d6ff,b:0x7c83ff,c:0xffffff},   // 推算：银＋靛
  why:   {top:0x06041a,hz:0x1d1250,vi:0x2b0d55,a:0xa78bfa,b:0x6fa8ff,c:0xf0e6ff},   // Thue–Morse：紫罗兰
  soccer:{top:0x020c0a,hz:0x063828,vi:0x062a2a,a:0x34f5a8,b:0x4fe3ff,c:0xeafff6},   // 足球场：翡翠
  data:  {top:0x0c0504,hz:0x3a1608,vi:0x0a3024,a:0xff7a3d,b:0x34f5a8,c:0xffffff},   // 数据：橙＋绿
  end:   {top:0x050505,hz:0x2a2008,vi:0x08202a,a:0xffc24a,b:0x4fe3ff,c:0xffffff}};  // 金＋青

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


// ==================== EP12 抢七轮发：通用物件 ====================
// 比例：特写里球放大成半径 1（画面标「放大示意」）；场地镜头里球按 1 单位 = 1 m 画真实尺寸附近。
// 所有上屏数字的出处见 papers/vibetennis-tiebreak-2026/sources.md（两源规则）；示意的形状都在画面上标「示意」。
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
const LN=[...Array(72)].map(()=>fatLine(0xffffff,3)); let lnI=0; const ln=(col,w=3,dashed=false)=>{ const l=LN[lnI++]; l.material.color.set(col); l.material.linewidth=w; l.material.dashed=dashed; return l; };
const RG=[...Array(10)].map(()=>flatRing(0xffffff)); let rgI=0; const rg=()=>RG[rgI++];
const GS=[...Array(24)].map(()=>glowSprite(0xffffff,1,0)); let gsI=0; const gs=(col,size,o)=>{ const s=GS[gsI++]; s.material.color.set(col).multiplyScalar(GLOW.k); s.scale.set(size,size,1); s.material.opacity=o; s.visible=o>0.003; return s; };
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
// 球场：1 单位 = 1 m（底座 courtG 就是 ITF 尺寸，球网在 z=0）。甲（金，SRV）站近端 z=+L 一侧面朝 -z；乙（青，RET）站远端 z=-L 一侧面朝 +z。
const SRV=makeHuman(0xffc24a), RET=makeHuman(0x4fe3ff);
const HUM=[SRV,RET];
const rkS=makeRk('carbon',{a:13.5/2*IN*0.95,b:10.5/2*IN*0.95}), rkR=makeRk('carbon',{a:13.5/2*IN*0.95,b:10.5/2*IN*0.95});
attachRacket(SRV,rkS); attachRacket(RET,rkR);
const CY=0x4fe3ff, GO=0xffc24a, RD=0xff5a4a, MT=0x34f5a8, WH=0xffffff, PJ=0x9dff5a, OR=0xffb347;
const GA=GO, GB=CY;   // 甲＝金，乙＝青（全片固定）
// 镜头坐标里的点（look() 之后调）：x、y 是画面上的偏移，d 是离相机的距离。d=9 时画面半宽约 5.5、半高约 3.1；字幕带以上 y>-1.95，品牌带以下 y<2.4
function hp(x,y,d=9){ camera.updateMatrixWorld(); return V(x,y,-d).applyQuaternion(camera.quaternion).add(camera.position); }
const rims=(a,b,i=5)=>{ rimL.intensity=i; rimR.intensity=i; rimL.color.set(a); rimR.color.set(b); rimL.position.set(-6,4,6); rimR.position.set(6,4,6); };
function place(H,x,z,yaw){ H.root.position.set(x,0,z); H.root.rotation.set(0,yaw,0); }
function lab(k,str,x,y,o,opt={}){ const t=tx(k,str,Object.assign({color:'#e8f4ff',size:0.34,glow:CYAN},opt)); if(x!==null) hud(t,x,y,opt.d||9); op(t,o); return t; }   // x=null：世界坐标（调用方设 position）
function bar(col,x0,x1,y,o,w=10,d=9){ const l=ln(col,w); setLine(l,[hp(x0,y,d),hp(Math.abs(x1-x0)<0.001?x0+0.001:x1,y,d)]); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=20; return l; }
function burst(c,k,col,spread=6,o=1){ const cc=new THREE.Color(col); for(let i=0;i<1600;i++){ const p=PTS[i]; const dir=V(p[0],p[1]*1.2,p[2]).normalize(); const sp=spread*(0.4+0.6*p[3]); const e=1-Math.pow(1-clamp(k),2.2);
  cset(pt,i,c.x+dir.x*sp*e,c.y+dir.y*sp*e-1.5*e*e,c.z+dir.z*sp*e,cc.r,cc.g,cc.b,o*(1-ss(0.55,1,k))*(0.5+0.5*p[4])); } cdone(pt); }
function shockRing(c,k,col,maxR,o=1,vertical=false){ const r=rg(); r.position.copy(c); if(vertical){ r.quaternion.copy(camera.quaternion); } else r.rotation.set(-Math.PI/2,0,0); const e=1-Math.pow(1-clamp(k),3); r.scale.setScalar(0.2+maxR*e); r.material.color.set(col).multiplyScalar(GLOW.k); r.material.opacity=o*(1-ss(0.35,1,k)); }

// ==================== EP12 抢七轮发：本集物件 ====================
// 序列：'A'＝甲、'B'＝乙。全部可在 papers/vibetennis-tiebreak-2026/tiebreak_math.py 里复现。
const SEQ={ ABAB:k=>'AB'[k%2], ABBA:k=>(((k+1)>>1)%2)?'B':'A', TM:k=>{ let c=0,x=k; while(x){ c+=x&1; x>>=1; } return 'AB'[c%2]; } };
const seqStr=(o,n)=>[...Array(n)].map((_,k)=>SEQ[o](k)).join('');
const NA=T('甲','A'), NB=T('乙','B');
// ---- 格子：金属底板＋彩色自发光（彩色件 ≤ 0.35，光晕标准）----
const TILE_G=new THREE.BoxGeometry(1,1,0.06);
const TILES=[...Array(260)].map(()=>{ const m=new THREE.Mesh(TILE_G,new THREE.MeshStandardMaterial({color:0x0a0f18,emissive:0xffffff,emissiveIntensity:GLOW.emissive,metalness:0.55,roughness:0.35,transparent:true,opacity:0,depthWrite:false,depthTest:false})); m.visible=false; m.renderOrder=18; scene.add(m); return m; });
let tI=0;
function tile(p,w,h,col,o,dim=1){ const m=TILES[tI++]; if(!m) return null; m.visible=o>0.003; m.position.copy(p); m.quaternion.copy(camera.quaternion); m.scale.set(w,h,1); m.material.emissive.set(col).multiplyScalar(dim); m.material.color.set(col).multiplyScalar(0.12); m.material.opacity=o; return m; }
// ---- 格子上的字（甲／乙、A／B、数字）：每个字一张贴图，精灵池共用 ----
const LTX={}; const BLANK=new THREE.Texture();
function letTex(ch){ if(LTX[ch]) return LTX[ch]; const c=document.createElement('canvas'); c.width=c.height=160; const g=c.getContext('2d'); const cjk=/[㐀-鿿]/.test(ch);
  g.font=(cjk?'900 104px "VT Title","Noto Sans CJK SC",sans-serif':'900 104px "Inter Display","Inter",sans-serif'); g.textAlign='center'; g.textBaseline='middle';
  g.lineJoin='round'; g.lineWidth=10; g.strokeStyle='rgba(0,0,0,0.6)'; g.strokeText(ch,80,86); g.fillStyle='#ffffff'; g.fillText(ch,80,86);
  const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; t.anisotropy=8; return LTX[ch]=t; }
const LETS=[...Array(160)].map(()=>{ const s=new THREE.Sprite(new THREE.SpriteMaterial({map:BLANK,transparent:true,depthTest:false,depthWrite:false,opacity:0,color:0xe6e6e6})); s.renderOrder=24; s.visible=false; scene.add(s); return s; });
let lI=0;
function letter(ch,p,size,o){ const s=LETS[lI++]; if(!s) return; if(NOTEXT) o=0; s.visible=o>0.003; s.material.map=letTex(ch); s.material.opacity=o; s.position.copy(p); s.scale.set(size,size,1); }
// 一排序列格（镜头空间）：k＝点亮到第几格（可小数，逐格弹出）；letters：格上写甲乙
function seqRow(seq,x0,y,cw,o,{k=999,d=9,letters=true,gapR=0.14,hl=-1,dimFrom=999,pop=0.35}={}){
  const w=cw*(1-gapR); for(let i=0;i<seq.length;i++){ const on=ss(i,i+pop,k); if(on<=0.002) continue; const a=seq[i]==='A';
    const sc=0.55+0.45*on+0.18*(i===hl?1:0); const p=hp(x0+cw*(i+0.5),y+0.12*(1-on),d);
    const dim=i>=dimFrom?0.35:1; tile(p,w*sc,w*1.06*sc,a?GA:GB,o*on,dim);
    if(letters&&w>0.16) letter(a?NA:NB,p.clone().add(new THREE.Vector3(0,0,0.05).applyQuaternion(camera.quaternion)),w*0.82*sc,o*on*dim); } }
// 发球次数累计差（甲 − 乙）折线：每格一个点（镜头空间）
function diffLine(seq,x0,y0,cw,amp,o,k,col){ const pts=[hp(x0,y0)]; let d=0; for(let i=0;i<seq.length&&i<k;i++){ d+=seq[i]==='A'?1:-1; const f=clamp(k-i); pts.push(hp(x0+cw*(i+f),y0+amp*lerp(d-(seq[i]==='A'?1:-1),d,f))); }
  if(pts.length<2) pts.push(hp(x0+0.001,y0)); const l=ln(col,6); setLine(l,pts); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=21; return d; }
// ---- 发球：一分的动作＋球的飞行（k：这一分的进度 0–1）----
const BALL=makeBall(0.11);
const STAND={A:[0.6,12.4,Math.PI],B:[-0.6,-12.4,0]};   // [x,z,朝向]
function servePoint(who,k,o=1,{ballOn=true}={}){ const S=who==='A'?SRV:RET, R=who==='A'?RET:SRV, sgn=who==='A'?1:-1;
  applyPose(S,poseAt([[0,'sToss'],[0.22,'sTrophy'],[0.36,'sHit'],[0.62,'sFollow'],[1,'ready']],k)); applyPose(R,poseAt([[0,'ready'],[0.45,'split'],[0.7,'land'],[1,'ready']],k));
  const A0=V(STAND[who][0]+0.25*sgn,2.75,STAND[who][1]-0.35*sgn), B0=V(-STAND[who][0]*1.6,0.03,-sgn*5.2), C0=V(STAND[who==='A'?'B':'A'][0],1.0,STAND[who==='A'?'B':'A'][1]*0.92);
  let p; if(k<0.36) p=V(A0.x,lerp(1.4,3.1,Math.sin(k/0.36*Math.PI*0.5)),A0.z); else if(k<0.62){ const q=(k-0.36)/0.26; p=V(lerp(A0.x,B0.x,q),lerp(A0.y,0.05,q)+Math.sin(Math.PI*q)*0.25,lerp(A0.z,B0.z,q)); } else { const q=(k-0.62)/0.38; p=V(lerp(B0.x,C0.x,q),Math.sin(Math.PI*q*0.6)*1.2,lerp(B0.z,C0.z,q)); }
  showB(BALL,p,o*(ballOn?1:0),1); const g=gs(who==='A'?GA:GB,1.2,0.45*o*(ballOn?1:0)); g.position.copy(p); return p; }
// ---- 天平（世界坐标，挂在镜头前）：θ＞0 右边沉 ----
const SCALE=(()=>{ const G=new THREE.Group(); scene.add(G); const mt=new THREE.MeshStandardMaterial({color:0x1a2230,metalness:0.85,roughness:0.25,emissive:0x0a1a2a,emissiveIntensity:0.6,transparent:true,opacity:1});
  const post=new THREE.Mesh(new THREE.CylinderGeometry(0.06,0.09,2.6,20),mt); post.position.y=1.3; G.add(post);
  const base=new THREE.Mesh(new THREE.CylinderGeometry(0.7,0.8,0.12,40),mt); G.add(base);
  const piv=new THREE.Group(); piv.position.y=2.6; G.add(piv);
  const beam=new THREE.Mesh(new THREE.BoxGeometry(4.2,0.08,0.12),mt); piv.add(beam);
  const pans=[-1,1].map(s=>{ const h=new THREE.Group(); h.position.x=s*2.0; piv.add(h); const pan=new THREE.Mesh(new THREE.CylinderGeometry(0.7,0.55,0.08,40),mt); pan.position.y=-1.3; h.add(pan);
    const lg=new THREE.BufferGeometry().setFromPoints([V(0,0,0),V(-0.6,-1.27,0),V(0,0,0),V(0.6,-1.27,0),V(0,0,0),V(0,-1.27,0.6)]); const ls=new THREE.LineSegments(lg,new THREE.LineBasicMaterial({color:0x9fd8ff,transparent:true,opacity:0.6})); h.add(ls); return {h,pan,ls}; });
  const glow=new THREE.Mesh(new THREE.TorusGeometry(0.16,0.03,10,40),new THREE.MeshBasicMaterial({color:new THREE.Color(0xffc24a).multiplyScalar(GLOW.k),transparent:true})); glow.position.y=2.6; G.add(glow);
  return {G,piv,pans,mt,glow,set(theta,o){ G.visible=o>0.003; mt.opacity=o; glow.material.opacity=o; pans.forEach(p=>{ p.ls.material.opacity=0.6*o; }); piv.rotation.z=-theta; pans.forEach(p=>p.h.rotation.z=theta); }}; })();
const panPos=(s)=>SCALE.pans[s<0?0:1].pan.getWorldPosition(new THREE.Vector3());
// ---- 足球场：球门（白色门柱＋网格）、点球点 ----
const GOAL=(()=>{ const G=new THREE.Group(); scene.add(G); const W7=7.32, H2=2.44;
  const pm=new THREE.MeshStandardMaterial({color:0xe8eef4,emissive:0xffffff,emissiveIntensity:GLOW.emissiveWhite,metalness:0.3,roughness:0.4,transparent:true});
  const cyl=(a,b)=>{ const d=b.clone().sub(a); const m=new THREE.Mesh(new THREE.CylinderGeometry(0.06,0.06,d.length(),14),pm); m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(V(0,1,0),d.normalize()); G.add(m); };
  cyl(V(-W7/2,0,0),V(-W7/2,H2,0)); cyl(V(W7/2,0,0),V(W7/2,H2,0)); cyl(V(-W7/2,H2,0),V(W7/2,H2,0));
  const nl=[]; for(let x=-W7/2;x<=W7/2+1e-3;x+=0.3){ nl.push(x,H2,0, x,H2*0.75,-1.8, x,H2*0.75,-1.8, x,0,-2.0); } for(let y=0;y<=H2;y+=0.3){ const z=-2.0*(1-y/H2)-1.8*(y/H2)*0.4; nl.push(-W7/2,y,z,W7/2,y,z); }
  const ng=new THREE.BufferGeometry(); ng.setAttribute('position',new THREE.Float32BufferAttribute(nl,3));
  const net=new THREE.LineSegments(ng,new THREE.LineBasicMaterial({color:0xcfe6ff,transparent:true,opacity:0.25,blending:THREE.AdditiveBlending})); G.add(net);
  const pc=document.createElement('canvas'); pc.width=pc.height=512; const g=pc.getContext('2d'); for(let i=0;i<16;i++){ g.fillStyle=i%2?'#0d2a16':'#103320'; g.fillRect(0,i*32,512,32); } g.strokeStyle='rgba(235,245,255,0.75)'; g.lineWidth=4; g.strokeRect(96,0,320,170); g.strokeRect(186,0,140,58); g.fillStyle='rgba(235,245,255,0.85)'; g.beginPath(); g.arc(256,113,2.5,0,7); g.fill();
  const pt2=new THREE.CanvasTexture(pc); pt2.colorSpace=THREE.SRGBColorSpace;
  const pitch=new THREE.Mesh(new THREE.PlaneGeometry(40,40),new THREE.MeshStandardMaterial({map:pt2,roughness:0.9,transparent:true})); pitch.rotation.x=-Math.PI/2; pitch.position.set(0,-0.01,20-0.0); G.add(pitch);
  const bc=document.createElement('canvas'); bc.width=256; bc.height=128; const b=bc.getContext('2d'); b.fillStyle='#f2f4f6'; b.fillRect(0,0,256,128); b.fillStyle='#1a1f28'; for(const [x,y] of [[40,40],[120,30],[200,50],[80,95],[170,100],[240,95],[10,100]]){ b.beginPath(); for(let i=0;i<5;i++){ const a=i/5*6.283; b.lineTo(x+Math.cos(a)*14,y+Math.sin(a)*14); } b.fill(); }
  const bt2=new THREE.CanvasTexture(bc); bt2.colorSpace=THREE.SRGBColorSpace;
  const ball=new THREE.Mesh(new THREE.SphereGeometry(0.11,32,20),new THREE.MeshStandardMaterial({map:bt2,roughness:0.5,transparent:true})); G.add(ball);
  return {G,pm,net,pitch,ball,set(o){ G.visible=o>0.003; pm.opacity=o; net.material.opacity=0.25*o; pitch.material.opacity=o; ball.material.opacity=o; }}; })();
// ---- 2621 个抢七：点云排成两根柱 ----
function cloudBars(k,cols,o){ for(let i=0;i<1600;i++){ const p=PTS[i]; const b=i%cols.length; const [cx,cy,w,h,col]=cols[b]; const cc=new THREE.Color(col);
    const t=hp(cx+(p[3]-0.5)*w,cy+p[4]*h,9); const s=hp(p[0]*0.7,p[1]*0.5,9+p[2]*0.4); const e=ss(0,1,k*1.3-p[3]*0.3);
    cset(pt,i,lerp(s.x,t.x,e),lerp(s.y,t.y,e),lerp(s.z,t.z,e),cc.r,cc.g,cc.b,o*(0.5+0.5*e)); } cdone(pt); }

function hideAll(){
  courtG.visible=false; courtG.userData.mat.opacity=1; courtG.rotation.set(0,0,0);
  HUM.forEach(H=>{ humanOp(H,0); H.root.position.set(0,0,0); H.root.rotation.set(0,0,0); H.root.scale.setScalar(1); });
  BALLS.forEach(b=>{ b.m.visible=false; b.gl.visible=false; }); bI=0; BALL.m.visible=false; BALL.gl.visible=false;
  LN.forEach(l=>{ l.material.opacity=0; l.material.dashed=false; }); lnI=0; RG.forEach(r=>r.material.opacity=0); rgI=0; GS.forEach(s=>{ s.material.opacity=0; s.visible=false; }); gsI=0;
  TILES.forEach(m=>{ m.visible=false; }); tI=0; LETS.forEach(s=>{ s.visible=false; }); lI=0;
  for(const k in TT) op(TT[k],0); for(const k in TB) TB[k].g.visible=false; for(const k in text3D) t3op(text3D[k],0); chide(pt);
  beamMat.uniforms.uOp.value=0; rimL.intensity=0; rimR.intensity=0; DOF.on=false; MOTE_SPEED=1; SLOW=null;
  SCALE.set(0,0); SCALE.G.position.set(0,0,0); SCALE.G.rotation.set(0,0,0); SCALE.G.scale.setScalar(1); GOAL.set(0); ST_RATE=0.0003; }
// 3D 数字（Inter Display Black 挤出）：挂在镜头空间
function num(key,str,col,size,x,y,o,d=9){ const n=t3d(key,str,col,size); hud(n,x,y,d); t3op(n,o); return n; }
// 两名球员站位（场地镜头用）
function players(o){ humanOp(SRV,o); humanOp(RET,o); place(SRV,STAND.A[0],STAND.A[1],STAND.A[2]); place(RET,STAND.B[0],STAND.B[1],STAND.B[2]); applyPose(SRV,POSE.ready); applyPose(RET,POSE.ready); }
// 按序列一分一分地发：t 是从第一分开始的秒，per 每分秒数；返回当前第几分（整数）
function rally(seq,t,per,o){ if(t<0){ return -1; } const i=Math.min(seq.length-1,Math.floor(t/per)); const k=t>=seq.length*per?1:(t-i*per)/per; servePoint(seq[i],k,o,{ballOn:t<seq.length*per}); return i; }

// ---------- 1 钩子：218 比 204 砸下 → 三个抢七 7-5 7-4 7-3 → 场上发球光点按 1-2-2-2 跳 → 和一串数列前四位相同 → 更公平吗？ ----------
function shotHook(u,D){
  const PT=ev('pts',1.0), LO=ev('lose',3.2), TB1=ev('tb',5.2), TB3=ev('tb3',7.6), OR1=ev('order',10.0), ONE=ev('one',12.4), TWO=ev('two',14.6), WHY=ev('why',16.6), SQ=ev('seq',18.8), SAME=ev('same',20.2), Q=ev('q2',22.6);
  courtG.visible=true; ST_RATE=u<OR1?0.004:0.0006; rims(GO,CY,5); beamMat.uniforms.uOp.value=0.1;
  if(u<OR1-0.3){ // 夜里的中央球场，俯冲下来；218 与 204 两块金属大数字砸在网前
    const k=ss(0,OR1,u); look(lerp(-3,3,k),lerp(7.5,4.6,k),lerp(23,18.5,k),0,1.4,2); players(1);
    const a=ss(PT-0.1,PT+0.35,u), b=ss(PT+0.35,PT+0.8,u);
    const nF=num('h218','218',GO,1.25,-2.4,0.75+(1-a)*1.6,a*(1-ss(TB1-0.4,TB1,u))); const nD=num('h204','204',CY,1.25,2.4,0.75+(1-b)*1.6,b*(1-ss(TB1-0.4,TB1,u)));
    if(u>PT+0.3&&u<PT+1.6) shockRing(hp(-2.4,0.4),(u-PT-0.3)/1.3,GO,3.5,0.8,true); if(u>PT+0.75&&u<PT+2.1) shockRing(hp(2.4,0.4),(u-PT-0.75)/1.3,CY,3.5,0.8,true);
    const lo=ss(PT+0.4,PT+0.9,u)*(1-ss(TB1-0.4,TB1,u));
    lab('hkF',T('费德勒 · 总得分','Federer · total points'),-2.4,1.95,lo,{size:0.34,color:'#ffe2a0',glow:GOLD}); lab('hkD',T('德约科维奇 · 总得分','Djokovic · total points'),2.4,1.95,lo,{size:0.34});
    lab('hkY',T('2019 温网男单决赛','2019 Wimbledon men\'s final'),0,-1.1,lo,{size:0.32,plate:true});
    const L1=ss(LO,LO+0.4,u)*(1-ss(TB1-0.4,TB1,u)); lab('hkW',T('冠军','CHAMPION'),2.4,-0.35,L1,{size:0.46,color:'#ffffff',glow:CYAN});
    lab('hkM',T('多赢 14 分，却输了','14 more points — and lost'),-2.4,-0.35,L1,{size:0.4,color:'#ffd27a',glow:GOLD});
    // 三个抢七：逐个砸下（第三个最大），德约的颜色
    const TBS=[['7-5',-3.0],['7-4',0],['7-3',3.0]];
    TBS.forEach(([s,x],i)=>{ const t0=TB1+i*0.75+(i===2?Math.max(0,TB3-TB1-1.5):0); const e=ss(t0,t0+0.35,u); const sz=i===2?0.95:0.75;
      num('htb'+i,s,CY,sz,x,0.9+(1-e)*1.8,e*(1-ss(OR1-0.6,OR1-0.3,u))); if(u>t0+0.3&&u<t0+1.5) shockRing(hp(x,0.5),(u-t0-0.3)/1.2,CY,2.4,0.7,true);
      lab('htbL'+i,[T('第一盘','set 1'),T('第三盘','set 3'),T('第五盘 · 12 平之后','set 5 · after 12-12')][i],x,-0.05,e*(1-ss(OR1-0.6,OR1-0.3,u)),{size:0.3,color:i===2?'#ffffff':'#bcd0e4'}); });
    lab('htbT',T('三个抢七，全归德约','three tiebreaks, all Djokovic'),0,2.2,ss(TB1+0.2,TB1+0.6,u)*(1-ss(OR1-0.6,OR1-0.3,u)),{size:0.36});
    return; }
  // 拉到底线后方：甲在近端、乙在远端，发球光点按 1-2-2-2 跳；上方一排格子同步亮起
  const k2=ss(OR1-0.3,WHY,u); look(lerp(5,-3.5,k2),lerp(5.2,6.0,k2),lerp(19.5,19,k2),0,0.2,3.5); players(1);
  const seq=seqStr('ABBA',8); const per=0.82; const t0=ONE-0.9;
  if(u<WHY+0.4) rally(seq,u-t0,per,1-ss(WHY,WHY+0.4,u));
  const lit=(u-t0)/per; const o=ss(OR1-0.3,OR1+0.3,u)*(1-ss(Q-0.5,Q-0.1,u));
  const rowY=lerp(1.8,1.55,ss(SQ-0.4,SQ+0.4,u)); seqRow(seq,-3.2,rowY,0.8,o,{k:Math.max(0,lit+0.6)});
  lab('hkO1',T('先发的只发 1 分','first server: 1 point'),-2.8,2.5,o*ss(ONE,ONE+0.4,u)*(1-ss(TWO-0.2,TWO,u)),{size:0.32,color:'#ffe2a0',glow:GOLD});
  lab('hkO2',T('之后每人连发 2 分','then 2 each'),0.6,2.5,o*ss(TWO,TWO+0.4,u)*(1-ss(SQ-0.4,SQ,u)),{size:0.32});
  // 「一串数列」：下面再排一行 Thue–Morse，前四位连线变绿，第五位起分开
  const s2=ss(SQ-0.2,SQ+0.5,u); if(s2>0){ const tm=seqStr('TM',8); seqRow(tm,-3.2,rowY-1.15,0.8,o*s2,{k:(u-SQ+0.2)*7});
    const m=ss(SAME,SAME+0.6,u); for(let i=0;i<8;i++){ const same=tm[i]===seq[i]; if(i>=4&&!same){ const g=gs(RD,0.7,0.35*o*ss(SAME+0.5,SAME+1.0,u)); g.position.copy(hp(-3.2+0.8*(i+0.5),rowY-0.58)); } }
    const lk=ln(MT,8); setLine(lk,[hp(-3.2+0.05,rowY-0.58),hp(-3.2+0.05+3.2*m,rowY-0.58)]); lk.material.opacity=o*m; lk.material.depthTest=false; lk.renderOrder=21;
    lab('hkS1',T('前四位：完全相同','first four: identical'),-1.6,rowY-1.95,o*ss(SAME+0.2,SAME+0.6,u),{size:0.3,color:'#b8ffd8',glow:MINT});
    lab('hkS2',T('一串研究了一百多年的数列','a sequence studied for 100+ years'),2.6,rowY-1.95,o*s2,{size:0.28,color:'#c8d8ea'}); }
  const q=bt('hkQ',T('它真的让抢七更公平吗？','Does it make the tiebreak fairer?'),{size:0.85,glow:'rgba(255,194,74,0.5)',fx:'shock'}); hud(q,0,0.4,9); q.update(u,Q,D+5,0.85);
}

// ---------- 2 规则：平时一局一人发到底 → 抢七一分一换（甲｜乙乙｜甲甲…）→ 每 6 分换边 ----------
function shotRule(u,D){
  const G=ev('game',0.3), TB=ev('tb',4.6), CH=ev('ch',11.5);
  courtG.visible=true; rims(GO,CY,4); players(1); ST_RATE=0.0005;
  look(lerp(4,-3,ss(0,D,u)),5.0,19.5,0,0.3,3.5);
  if(u<TB-0.3){ // 一局：全是甲发，6 个球连着；上方一排金格
    const seq='AAAAAA'; rally(seq,u-G-0.2,0.66,1);
    seqRow(seq,-2.4,1.45,0.8,1-ss(TB-0.6,TB-0.3,u),{k:(u-G)/0.66+0.6});
    lab('ruG',T('平时：一局从头到尾一个人发','a normal game: one server throughout'),0,2.3,ss(G,G+0.4,u)*(1-ss(TB-0.6,TB-0.3,u)),{size:0.32,plate:true});
    return; }
  const seq=seqStr('ABBA',12); const per=Math.min(0.62,(CH+1.6-TB)/7); const t=u-TB+0.2; rally(seq,t,per,1);
  const o=1-ss(D-0.6,D-0.1,u); seqRow(seq,-4.8,1.45,0.8,o,{k:t/per+0.6});
  // 分隔竖线：1 | 2 3 | 4 5 | 6 7 …
  for(const b of [1,3,5,7,9,11]){ const e=ss(TB+b*per-0.4,TB+b*per,u); const l=ln(0xffffff,3); setLine(l,[hp(-4.8+0.8*b,1.02),hp(-4.8+0.8*b,1.88)]); l.material.opacity=0.6*o*e; l.material.depthTest=false; l.renderOrder=22; }
  lab('ruT',T('抢七：一分一换','tiebreak: switch point by point'),0,2.3,ss(TB,TB+0.4,u)*o,{size:0.32,plate:true});
  // 每 6 分换边：第 6、12 格下方亮一个「换边」
  for(const [i,key] of [[5,'ruC1'],[11,'ruC2']]){ const e=ss(TB+(i+1)*per-0.2,TB+(i+1)*per+0.2,u); lab(key,T('换边','change ends'),-4.8+0.8*(i+0.5),0.72,e*o,{size:0.26,color:'#b8ffd8',glow:MINT}); }
  lab('ruR',T('国际网联《网球规则》第 5 条、第 10 条','ITF Rules of Tennis, rules 5 and 10'),0,-1.55,ss(CH,CH+0.5,u)*o,{size:0.26,color:'#aab8c8'});
}

// ---------- 3 发球占优：64% / 68.5% → 一人一分时甲每到单数分领先、乙一直在追 → 1-2-2-2 多发的人来回换 ----------
function shotEdge(u,D){
  const PC=ev('pct',0.3), DJ=ev('dj',3.2), FD=ev('fd',5.0), AB=ev('abab',8.5), CH=ev('chase',12.5), BA=ev('abba',15.5);
  rims(GO,CY,4); const a=0.12*Math.sin(u*0.15); look(Math.sin(a)*9,0.4,Math.cos(a)*9,0,0.2,0);
  if(u<AB-0.3){ // 两根发球得分率柱，带一条 50% 线
    courtG.visible=false; const o=1-ss(AB-0.7,AB-0.3,u);
    const H=3.4, y0=-1.6; const l50=ln(0xffffff,2,true); setLine(l50,[hp(-3.6,y0+H*0.5),hp(3.6,y0+H*0.5)]); l50.computeLineDistances(); l50.material.dashSize=0.15; l50.material.gapSize=0.1; l50.material.opacity=0.55*o*ss(PC,PC+0.5,u); l50.material.depthTest=false;
    lab('egH',T('50%','50%'),-4.2,y0+H*0.5,0.8*o*ss(PC,PC+0.5,u),{size:0.28,color:'#c8d8ea'});
    const e1=ss(DJ-0.2,DJ+0.8,u), e2=ss(FD-0.2,FD+0.8,u);
    const b1=ln(CY,60); setLine(b1,[hp(-1.4,y0),hp(-1.4,y0+H*0.639*e1+0.001)]); b1.material.opacity=0.8*o*ss(0,0.05,e1); b1.material.depthTest=false;
    const b2=ln(GO,60); setLine(b2,[hp(1.4,y0),hp(1.4,y0+H*0.685*e2+0.001)]); b2.material.opacity=0.8*o*ss(0,0.05,e2); b2.material.depthTest=false;
    num('eg64','64%',CY,0.5,-1.4,y0+H*0.639*e1+0.55,o*e1); num('eg68','68.5%',GO,0.5,1.4,y0+H*0.685*e2+0.55,o*e2);
    lab('egD',T('德约 · 发球得分','Djokovic · serve points won'),-1.4,y0-0.35,o*e1,{size:0.28}); lab('egF',T('费德勒 · 发球得分','Federer · serve points won'),1.4,y0-0.35,o*e2,{size:0.28,color:'#ffe2a0',glow:GOLD});
    lab('egT',T('发球的人占优','the server has the edge'),0,2.25,o*ss(PC,PC+0.4,u),{size:0.42,color:'#ffffff'});
    lab('egS',T('2019 温网决赛 · 官方技术统计','2019 Wimbledon final · official stats'),0,1.75,o*ss(FD,FD+0.5,u),{size:0.24,color:'#aab8c8'});
    return; }
  // 账本：上面一排顺序格，下面一条「甲多发几个」的折线；先一人一分，再 1-2-2-2
  const m=ss(BA-0.4,BA+0.4,u); const o=ss(AB-0.3,AB+0.3,u);
  const seq=m<0.5?seqStr('ABAB',12):seqStr('ABBA',12); const per=m<0.5?(BA-0.5-AB)/12:(D-1.0-BA)/12; const t=m<0.5?(u-AB):(u-BA); const k=t/per;
  const x0=-4.8, cw=0.8, oo=o*(1-ss(BA-0.5,BA-0.3,u)*(1-ss(BA-0.3,BA+0.1,u)));
  seqRow(seq,x0,1.45,cw,oo,{k:k+0.6,letters:true});
  const zl=ln(0x9fb8d0,2); setLine(zl,[hp(x0,-0.4),hp(x0+cw*12,-0.4)]); zl.material.opacity=0.6*oo; zl.material.depthTest=false;
  lab('egZ',T('一样多','even'),x0-0.55,-0.4,0.8*oo,{size:0.24,color:'#aab8c8'}); lab('egP',T('甲多 1','A +1'),x0-0.55,0.55,0.8*oo,{size:0.24,color:'#ffe2a0',glow:GOLD}); lab('egN',T('乙多 1','B +1'),x0-0.55,-1.35,0.8*oo*m,{size:0.24});
  const dd=diffLine(seq,x0,-0.4,cw,0.95,oo,k,m<0.5?GO:MT);
  lab('egA',T('一人一分','one each'),0,2.3,oo*(1-ss(0.3,0.5,m)),{size:0.36,plate:true}); lab('egB',T('一、二、二、二','1-2-2-2'),0,2.3,oo*ss(0.5,0.7,m),{size:0.36,plate:true});
  const chase=ss(CH,CH+0.4,u)*(1-m); lab('egC',T('后发的人：一直在追','second server: always chasing'),2.0,-1.35,oo*chase,{size:0.32,color:'#ffb0a8',glow:RED});
  if(m<0.5&&u>CH){ for(let i=0;i<12;i+=2){ if(i<k){ const g=gs(RD,0.8,0.35*oo*chase*(0.6+0.4*Math.sin(u*6))); g.position.copy(hp(x0+cw*(i+1),-0.4+0.95)); } } }
  lab('egE',T('多发一个的人，来回换','the extra serve keeps switching'),2.0,-1.35,oo*ss(BA+1.5,BA+2.0,u),{size:0.32,color:'#b8ffd8',glow:MINT});
}

// ---------- 4 反转：两种顺序都是 50% → 净胜两分 → 补打不改结果 → 前 12 分各发 6 个 → 6 平后每组各一个 → 去掉它：53.6% ----------
function shotMath(u,D){
  const M0=ev('m0',0.3), CA=ev('calc',2.6), R1=ev('r1',4.6), R2=ev('r2',8.4), MD=ev('model',11.0), KEY=ev('key',13.6), EX=ev('ex',17.0), FI=ev('fill',19.5),
        TW=ev('twelve',23.0), AF=ev('after',27.0), RC=ev('race',32.0), MO=ev('more',34.5), PC=ev('pct',38.0);
  rims(GO,CY,4);
  if(u<EX-0.3){ // 天平：两种顺序各放一边，平；50% = 50%
    const a=0.1*Math.sin(u*0.2); look(Math.sin(a)*10,2.2,Math.cos(a)*10,0,1.6,0);
    const o=ss(M0,M0+0.6,u)*(1-ss(EX-0.7,EX-0.3,u)); SCALE.set(0.18*(1-ss(R2,R2+1.2,u))*Math.cos(u*2.2)*(1-ss(R1,R2,u))+0.0,o); SCALE.G.position.set(0,-0.6,0);
    const pl=panPos(-1), pr=panPos(1);
    lab('mtA',T('一人一分','one each'),null,0,o*ss(CA,CA+0.4,u),{size:0.42}).position.copy(pl).add(V(0,1.15,0));
    lab('mtB',T('一、二、二、二','1-2-2-2'),null,0,o*ss(CA,CA+0.4,u),{size:0.42,color:'#ffe2a0',glow:GOLD}).position.copy(pr).add(V(0,1.15,0));
    const n1=t3d('mt50a','50%',CY,0.62); n1.g.position.copy(pl).add(V(0,0.55,0)); n1.g.quaternion.copy(camera.quaternion); t3op(n1,o*ss(R1,R1+0.4,u));
    const n2=t3d('mt50b','50%',GO,0.62); n2.g.position.copy(pr).add(V(0,0.55,0)); n2.g.quaternion.copy(camera.quaternion); t3op(n2,o*ss(R2,R2+0.4,u));
    lab('mtAs',T('假设：两人一样强，发球都赢 65%','assume: equal players, each wins 65% on serve'),0,2.6,o*ss(CA,CA+0.4,u),{size:0.3,plate:true});
    lab('mtEq',T('顺序，没有改变输赢','the order changes nothing'),0,-1.55,o*ss(MD,MD+0.4,u)*(1-ss(KEY-0.4,KEY,u)),{size:0.4,color:'#ffffff'});
    lab('mtMd',T('「每分独立」模型 · 按假设推算','"independent points" model · computed'),0,-2.1+0.25,o*ss(MD,MD+0.4,u),{size:0.24,color:'#aab8c8'});
    const t=bt('mtKey',T('净胜两分','WIN BY TWO'),{size:1.05,glow:'rgba(255,194,74,0.55)',fx:'shock'}); hud(t,0,-1.2,9); t.update(u,KEY,EX-0.6,0.85);
    if(u>KEY+0.3&&u<KEY+1.6) shockRing(hp(0,-1.2),(u-KEY-0.3)/1.3,GO,4,0.6,true);
    return; }
  look(0,0.3,9.5,0,0.3,0);
  if(u<RC-0.3){ // 补打不改结果：12 格，一个 7 比 4 的抢七；第 12 分补成幽灵格；下面一排写发球人
    const o=ss(EX-0.3,EX+0.3,u)*(1-ss(RC-0.7,RC-0.3,u)); const x0=-4.9, cw=0.72;
    const WIN='AABABAABABA';   // 谁赢了这一分（甲 7、乙 4：第 11 分甲 7 比 4 赢下）——画成「得分小球」，和下面的「发球格」区分开
    const kk=(u-EX)/0.22; let sa=0, sb=0;
    for(let i=0;i<12;i++){ const ghost=i===11; const on=ghost?ss(FI,FI+0.5,u):ss(i,i+0.4,kk); if(on<=0) continue; const w=ghost?'?':WIN[i];
      const p=hp(x0+cw*(i+0.5),1.55); if(!ghost){ if(w==='A') sa++; else sb++; }
      const g=gs(ghost?0x9fb8d0:(w==='A'?GA:GB),ghost?0.75:0.95,(ghost?0.25:0.55)*o*on); g.position.copy(p);
      showB(BALLS[Math.min(5,bI++)]||BALL,p,0,1);
      letter(ghost?'?':(w==='A'?NA:NB),p,cw*0.5,o*on*(ghost?0.8:0.95)); }
    lab('mxT',T('每一分是谁赢的','who won each point'),x0+1.3,2.2,o*ss(EX,EX+0.4,u)*(1-ss(TW-0.4,TW,u)),{size:0.28,color:'#c8d8ea'});
    num('mx74','7 : 4',GO,0.55,4.4,1.55,o*ss(EX+2.4,EX+2.8,u)*(1-ss(FI,FI+0.4,u)));
    num('mx75','≥ 7',GO,0.55,4.4,1.55,o*ss(FI+0.5,FI+0.9,u)*(1-ss(TW-0.4,TW,u)));
    lab('mxF',T('补完 12 分：甲照样拿到 7 分以上，结果不变','play all 12: A still has 7+, same result'),0,0.75,o*ss(FI+0.3,FI+0.7,u)*(1-ss(TW-0.4,TW,u)),{size:0.34,color:'#ffe2a0',glow:GOLD});
    // 12 分里谁发球：两种顺序各一行，右边标名字
    const s=ss(TW-0.3,TW+0.4,u); if(s>0){ const r1=seqStr('ABAB',12), r2=seqStr('ABBA',12);
      seqRow(r1,x0,0.45,cw,o*s,{k:(u-TW)*14}); seqRow(r2,x0,-0.45,cw,o*s,{k:(u-TW-0.3)*14});
      lab('mxR1',T('一人一分','one each'),x0+cw*12+0.75,0.45,o*s,{size:0.24,color:'#c8d8ea'}); lab('mxR2',T('一二二二','1-2-2-2'),x0+cw*12+0.75,-0.45,o*s,{size:0.24,color:'#c8d8ea'});
      lab('mxS',T('谁发球','who serves'),x0+1.0,1.0,o*s*(1-ss(AF-0.4,AF,u)),{size:0.26,color:'#c8d8ea'});
      lab('mxC',T('两人各发 6 个','6 serves each'),0,2.2,o*ss(TW+1.2,TW+1.6,u)*(1-ss(AF-0.4,AF,u)),{size:0.38,color:'#b8ffd8',glow:MINT}); }
    const af=ss(AF-0.2,AF+0.4,u); if(af>0){ // 6 平之后：每两分一组
      for(let j=0;j<3;j++){ const xx=-2.6+j*1.8; seqRow('AB',xx,-1.4,0.62,o*af,{k:(u-AF)*6-j*2});
        const br=ln(MT,3); setLine(br,[hp(xx,-0.98),hp(xx,-0.93),hp(xx+1.24,-0.93),hp(xx+1.24,-0.98)]); br.material.opacity=o*af*ss(j*0.33,j*0.33+0.3,(u-AF)/1.2); br.material.depthTest=false; }
      lab('mxA',T('6 平之后：每两分一组，各发一个','after 6-6: pairs, one serve each'),0,2.2,o*af,{size:0.36,color:'#b8ffd8',glow:MINT}); }
    return; }
  // 去掉净胜两分：先到 7 分，最多 13 分；第 13 格是甲的，天平往甲那边沉
  const o=ss(RC-0.3,RC+0.3,u); const x0=-4.81, cw=0.74; const r=seqStr('ABAB',13), r2=seqStr('ABBA',13);
  seqRow(r,x0,1.35,cw,o,{k:(u-RC)*16,hl:12}); seqRow(r2,x0,0.5,cw,o,{k:(u-RC-0.25)*16,hl:12});
  const hl=ss(MO,MO+0.4,u); const g=gs(GO,1.3,0.45*o*hl); g.position.copy(hp(x0+cw*12.5,0.92));
  lab('mrT',T('改成先到 7 分就赢：最多 13 分（上：一人一分 · 下：一二二二）','first to 7, no margin: at most 13 points (top: one each · bottom: 1-2-2-2)'),0,2.2,o,{size:0.3,plate:true});
  lab('mrC',T('甲发 7 个 · 乙发 6 个 · 两种顺序都一样','A serves 7 · B serves 6 · same for both orders'),0,-0.25,o*hl,{size:0.36,color:'#ffe2a0',glow:GOLD});
  const p=ss(PC-0.2,PC+0.6,u); num('mr536','53.6%',GO,0.8,-1.6,-0.95,o*p); num('mr464','46.4%',CY,0.55,2.2,-0.95,o*p*0.85);
  lab('mrA',T('先发的人','first server'),-1.6,-1.72,o*p,{size:0.28,color:'#ffe2a0',glow:GOLD}); lab('mrB',T('后发的人','second server'),2.2,-1.72,o*p,{size:0.28});
  lab('mrS',T('按发球赢 65% 推算','assuming 65% on serve'),4.3,-0.95,o*p,{size:0.24,color:'#aab8c8'});
}

// ---------- 5 那图什么：换手 11 次 vs 6 次 → 一直在追 → Thue–Morse 一层层长出来 → 每层轮流当先手 → 网球只抄第一层 ----------
function shotWhy(u,D){
  const SW=ev('sw',0.3), CN=ev('cnt',3.0), CHS=ev('ch',7.5), BU=ev('build',11.0), AB=ev('ab',13.2), AB2=ev('abba2',15.5), TM=ev('tm',19.0), HI=ev('hist',21.0),
        LY=ev('layer',26.0), EC=ev('econ',28.0), TN=ev('tennis',33.0), SP=ev('split',35.0);
  rims(GO,CY,4); const a=0.1*Math.sin(u*0.17); look(Math.sin(a)*9.5,0.3,Math.cos(a)*9.5,0,0.3,0);
  if(u<BU-0.3){ // 换手：两条轨道，球在两人之间跳；一人一分的折线来回 11 次，一二二二只有 6 次
    const o=ss(SW,SW+0.4,u)*(1-ss(BU-0.7,BU-0.3,u)); const x0=-4.6, cw=0.8;
    for(const [row,seq,yy,key,cnt] of [[0,seqStr('ABAB',12),1.3,'wyA',11],[1,seqStr('ABBA',12),-0.9,'wyB',6]]){
      const k=(u-SW-row*0.4)*7; const pts=[]; for(let i=0;i<12&&i<k;i++){ const yv=yy+(seq[i]==='A'?0.38:-0.38); pts.push(hp(x0+cw*(i+0.15),yv),hp(x0+cw*(i+0.85),yv)); }
      if(pts.length>=2){ const l=ln(row?MT:RD,7); setLine(l,pts); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=21; }
      for(const s of [-1,1]){ const r=ln(0x9fb8d0,2); setLine(r,[hp(x0,yy+s*0.38),hp(x0+cw*12,yy+s*0.38)]); r.material.opacity=0.3*o; r.material.depthTest=false; }
      lab(key+'L',row?T('一、二、二、二','1-2-2-2'):T('一人一分','one each'),x0+1.2,yy+0.95,o,{size:0.3,color:row?'#b8ffd8':'#ffb0a8',glow:row?MINT:RED});
      num(key+'N',String(cnt),row?MT:RD,0.62,4.6,yy,o*ss(CN+row*0.6,CN+row*0.6+0.4,u)); }
    lab('wyT',T('12 分里，换几次发球','server switches in 12 points'),0,2.6,o,{size:0.34,plate:true});
    lab('wyP',T('一直在追的人，可能更紧张——这个，算不出来','chasing all the time may add pressure — math can\'t see that'),0,-1.75,o*ss(CHS,CHS+0.5,u),{size:0.3,color:'#ffd27a',glow:GOLD});
    return; }
  if(u<TN-0.3){ // Thue–Morse：每一行＝上一行接上它的反面（金青对调），一层层往下长成条码塔
    const o=ss(BU-0.3,BU+0.3,u)*(1-ss(TN-0.7,TN-0.3,u)); const Wd=8.4, xL=-Wd/2;
    const lvT=[BU, AB, AB2, TM, TM+1.0, TM+1.8, TM+2.5]; const yTop=2.05, dy=0.5;
    for(let n=0;n<7;n++){ const len=1<<n; const g=ss(lvT[n]-0.2,lvT[n]+0.5,u); if(g<=0) continue; const seq=seqStr('TM',len); const cw=Wd/64*(64/len)*0.5*(n===0?1:1);
      const rowW=Math.min(Wd, 0.8*len); const c2=rowW/len; const x0=-rowW/2;
      for(let i=0;i<len;i++){ const half=i>=len/2&&n>0; const e=half?ss(0,1,(g-0.15)*1.6):1; if(e<=0) continue; const xx=x0+c2*(i+0.5)+(half?(1-e)*2.4:0);
        const p=hp(xx,yTop-n*dy-(n>3?(n-3)*0.0:0)); tile(p,c2*0.86,Math.min(0.5,c2*0.95),seq[i]==='A'?GA:GB,o*(half?e:1));
        if(c2>=0.5) letter(seq[i]==='A'?NA:NB,p.clone().add(new THREE.Vector3(0,0,0.05).applyQuaternion(camera.quaternion)),c2*0.6,o*(half?e:1)); }
      if(n>0&&n<4){ const l=ln(0xffffff,2,true); setLine(l,[hp(0,yTop-n*dy+0.32),hp(0,yTop-n*dy-0.32)]); l.computeLineDistances(); l.material.dashSize=0.06; l.material.gapSize=0.05; l.material.opacity=0.5*o*g; l.material.depthTest=false; } }
    lab('tmR',T('接上它的反面','append its mirror'),3.4,2.05-0.5,o*ss(AB,AB+0.4,u)*(1-ss(TM-0.4,TM,u)),{size:0.3,color:'#ffe2a0',glow:GOLD});
    const t=bt('tmT',T('Thue–Morse 序列','THUE–MORSE'),{size:0.78,glow:'rgba(79,227,255,0.5)',fx:'weave',thread:'#7fe4ff'}); hud(t,0,-1.55,9); t.update(u,TM,LY-0.4,0.82);
    lab('tmH',T('1851 普鲁埃 · 1906 图厄 · 1921 莫尔斯','1851 Prouhet · 1906 Thue · 1921 Morse'),3.2,2.1,o*ss(HI,HI+0.5,u)*(1-ss(LY-0.4,LY,u)),{size:0.28,color:'#c8d8ea'});
    // 每一层都轮流当先手：两两一组框起来、四四一组框起来，组首的颜色交替
    const ly=ss(LY,LY+0.5,u); if(ly>0){ const len=16, rowW=8.0, c2=rowW/len, x0=-rowW/2, y=yTop-4*dy; for(const [gsz,yo,col] of [[2,-0.32,MT],[4,-0.46,OR]]){ const e=ss(LY+(gsz===4?1.2:0),LY+(gsz===4?1.7:0.5),u);
        for(let j=0;j<len/gsz;j++){ const b=ln(col,3); const xa=x0+c2*j*gsz+0.04, xb=x0+c2*(j+1)*gsz-0.04; setLine(b,[hp(xa,y+yo+0.08),hp(xa,y+yo),hp(xb,y+yo),hp(xb,y+yo+0.08)]); b.material.opacity=o*e; b.material.depthTest=false; b.renderOrder=22; } } }
    lab('tmL',T('两个一组、四个一组：先手都在轮换','in pairs, in fours: the first mover alternates'),0,-1.55,o*ly*(1-ss(EC-0.3,EC,u)),{size:0.32,color:'#b8ffd8',glow:MINT});
    lab('tmE',T('经济学家：两人轮流比赛，顺序怎么排才公平','economists: the fair order for taking turns'),0,-1.55,o*ss(EC,EC+0.4,u),{size:0.3});
    lab('tmE2',T('Palacios-Huerta 2012','Palacios-Huerta 2012'),3.6,2.1,o*ss(EC,EC+0.4,u),{size:0.24,color:'#aab8c8'});
    return; }
  // 网球只抄了第一层：两行对齐，前四位连线，第五位起红
  const o=ss(TN-0.3,TN+0.3,u); const tm=seqStr('TM',8), te=seqStr('ABBA',8); const x0=-3.6, cw=0.9;
  seqRow(tm,x0,1.2,cw,o,{k:(u-TN)*12}); seqRow(te,x0,-0.15,cw,o,{k:(u-TN-0.3)*12});
  lab('tnA',T('Thue–Morse','Thue–Morse'),x0-0.9,1.2,o,{size:0.3,color:'#c8d8ea'}); lab('tnB',T('网球抢七','tiebreak'),x0-0.9,-0.15,o,{size:0.3,color:'#ffe2a0',glow:GOLD});
  for(let i=0;i<8;i++){ const same=tm[i]===te[i]; const e=ss(SP-1.2+i*0.12,SP-0.9+i*0.12,u); const l=ln(i<4?MT:(same?0x9fb8d0:RD),i<4?6:4); setLine(l,[hp(x0+cw*(i+0.5),0.78),hp(x0+cw*(i+0.5),0.27)]); l.material.opacity=o*e*(i<4||!same?1:0.4); l.material.depthTest=false; }
  lab('tnS',T('前四位一样 · 第五位起分开','same for four · apart from the fifth'),0,-1.35,o*ss(SP,SP+0.4,u),{size:0.36,color:'#ffffff'});
}

// ---------- 6 足球：点球大战一人一脚 → 129 次先踢六成 → IFAB 2017 试行甲乙乙甲、2018 停掉 → 540 次测不出 ----------
function shotSoccer(u,D){
  const Q=ev('q',0.3), PK=ev('pk',2.6), S6=ev('s60',6.0), IF=ev('ifab',10.0), ST=ev('stop',13.0), BG=ev('big',16.0);
  rims(0x9fffc0,CY,4); GOAL.set(1); GOAL.G.position.set(0,0,0);
  const kk=ss(0,D,u); look(lerp(-2.2,2.2,kk),lerp(1.7,2.2,kk),lerp(15.5,14.0,kk),0,1.0,0);
  // 一人一脚：甲乙甲乙……球从点球点射向球门
  const per=1.1; const t=u-PK+0.4; const i=Math.max(0,Math.floor(t/per)); const k=t<0?0:(t-i*per)/per; const side=[0.6,-0.7,0.9,-1.0,0.2,-0.4,0.8,-0.9,0.5,-0.6][i%10];
  const spot=V(0,0.11,8.83); const tgt=V(side*3.0,0.5+0.8*Math.abs(side),-0.6); const kb=ss(0.1,0.55,k);
  GOAL.ball.position.copy(t<0?spot:spot.clone().lerp(tgt,kb)).add(V(0,Math.sin(kb*Math.PI)*0.4,0)); GOAL.ball.rotation.set(kb*8,kb*3,0);
  const who=i%2?'B':'A'; if(t>=0){ const g=gs(who==='A'?GA:GB,0.9,0.4*(1-kb*0.6)); g.position.copy(GOAL.ball.position); }
  const o=1-ss(D-0.5,D-0.1,u);
  const row=u<IF+0.6?seqStr('ABAB',10):seqStr('ABBA',10); seqRow(row,-4.0,1.55,0.8,o,{k:u<IF+0.6?(t/per+1):(u-IF-0.6)*8,hl:u<IF+0.6?i:-1});
  lab('scT',T('点球大战：一人一脚','penalty shootout: one kick each'),0,2.25,o*ss(Q,Q+0.4,u)*(1-ss(IF+0.2,IF+0.6,u)),{size:0.32,plate:true}); lab('scT2',T('2017 试行：甲乙乙甲','2017 trial: ABBA'),0,2.25,o*ss(IF+0.4,IF+0.8,u),{size:0.32,plate:true,color:'#ffe2a0',glow:GOLD});
  const p6=ss(S6-0.2,S6+0.5,u)*(1-ss(IF-0.4,IF,u)); num('sc60','60%',GO,0.9,-3.2,0.6,o*p6); lab('sc60L',T('先踢的一方赢了 · 129 次点球大战（2010）','first kickers won · 129 shootouts (2010)'),-1.6,-0.35,o*p6,{size:0.3,color:'#ffe2a0',glow:GOLD});
  const sf=0; const st=bt('scStop',T('2018 · 停掉','2018 · DROPPED'),{size:0.7,glow:'rgba(255,90,74,0.5)',fx:'sag'}); hud(st,2.4,0.35,9); st.update(u,ST,BG+1.6,0.82);
  lab('scIF',T('国际足球协会理事会（IFAB）','IFAB, football\'s lawmakers'),2.4,-0.45,o*ss(IF,IF+0.4,u)*(1-ss(BG+1.2,BG+1.6,u)),{size:0.28,color:'#c8d8ea'});
  const bg=ss(BG+1.4,BG+2.0,u); if(bg>0){ cloudBars(ss(BG+1.4,BG+3.0,u),[[-1.2,-1.6,1.4,1.5*1.0,GO],[1.2,-1.6,1.4,1.5*0.95,CY]],o*bg*0.8);
    lab('scBG',T('样本扩大到 540 次：先踢的优势，测不出来了（2012）','540 shootouts: no significant first-kicker edge (2012)'),0,0.25,o*ss(BG+1.6,BG+2.0,u),{size:0.32,color:'#ffffff'}); }
}

// ---------- 7 网球的真实数据：2621 个抢七，先发后发无显著区别 → 博客统计 50.8% / 49.7% ----------
function shotData(u,D){
  const DD=ev('d',0.3), RS=ev('res',3.2), BL=ev('blog',6.6);
  courtG.visible=true; courtG.userData.mat.opacity=0.4; rims(GO,CY,4); const kk=ss(0,D,u); look(lerp(-3,3,kk),9.5,15.5,0,0.5,0);
  const o=1-ss(D-0.5,D-0.1,u);
  if(u<BL-0.3){ const e=ss(DD,DD+2.2,u); cloudBars(e,[[-1.5,-1.55,1.6,3.1,GO],[1.5,-1.55,1.6,3.1,CY]],o*(1-ss(BL-0.7,BL-0.3,u)));
    num('dt2621','2621',WH,0.75,0,2.15,o*ss(DD,DD+0.5,u)*(1-ss(BL-0.7,BL-0.3,u))); lab('dtL',T('个抢七 · 2012–2015 · 巡回赛和大满贯','tiebreaks · 2012–2015 · tour and Slams'),0,1.45,o*ss(DD+0.2,DD+0.6,u)*(1-ss(BL-0.7,BL-0.3,u)),{size:0.28,color:'#c8d8ea'});
    lab('dtA',T('先发','served first'),-1.5,-1.8,o*e*(1-ss(BL-0.7,BL-0.3,u)),{size:0.3,color:'#ffe2a0',glow:GOLD}); lab('dtB',T('后发','served second'),1.5,-1.8,o*e*(1-ss(BL-0.7,BL-0.3,u)),{size:0.3});
    lab('dtR',T('赢面：没有显著区别 · 男女都一样','win chance: no significant difference · men and women'),0,0.75,o*ss(RS,RS+0.5,u)*(1-ss(BL-0.7,BL-0.3,u)),{size:0.34,color:'#b8ffd8',glow:MINT}); return; }
  const b=ss(BL-0.3,BL+0.6,u); const H=3.2, y0=-1.6; const l50=ln(0xffffff,2,true); setLine(l50,[hp(-3.4,y0+H*0.5),hp(3.4,y0+H*0.5)]); l50.computeLineDistances(); l50.material.dashSize=0.15; l50.material.gapSize=0.1; l50.material.opacity=0.55*o*b; l50.material.depthTest=false;
  const b1=ln(CY,56); setLine(b1,[hp(-1.3,y0),hp(-1.3,y0+H*0.508*b+0.001)]); b1.material.opacity=0.8*o; b1.material.depthTest=false;
  const b2=ln(GO,56); setLine(b2,[hp(1.3,y0),hp(1.3,y0+H*0.497*b+0.001)]); b2.material.opacity=0.8*o; b2.material.depthTest=false;
  num('dt508','50.8%',CY,0.5,-1.3,y0+H*0.508*b+0.5,o*b); num('dt497','49.7%',GO,0.5,1.3,y0+H*0.497*b+0.5,o*b);
  lab('dtM',T('男子巡回赛 · 先发的人赢','ATP · first server won'),-1.3,y0-0.3,o*b,{size:0.26}); lab('dtW',T('女子巡回赛 · 先发的人赢','WTA · first server won'),1.3,y0-0.3,o*b,{size:0.26,color:'#ffe2a0',glow:GOLD});
  lab('dtH',T('50%','50%'),-3.9,y0+H*0.5,0.8*o*b,{size:0.26,color:'#c8d8ea'});
  lab('dtS',T('博客统计（Tennis Abstract，2015），非同行评审','blog analysis (Tennis Abstract, 2015), not peer-reviewed'),0,2.55,o*b,{size:0.26,color:'#aab8c8'});
}

// ---------- 8 结论＋问句：场上再发一遍 1-2-2-2，每到双数分两人的计数一样 ----------
function shotEnd(u,D){
  const N0=ev('n0',0.3), TP=ev('tip',7.5), QQ=ev('q',11.5);
  courtG.visible=true; rims(GO,CY,5); beamMat.uniforms.uOp.value=0.1; players(1); ST_RATE=0.0008;
  const a=0.25+u*0.02; look(Math.sin(a)*20,7,Math.cos(a)*20,0,1.0,0);
  const t=bt('ndT',T('公平，靠的是净胜两分','Fairness comes from winning by two'),{size:0.85,glow:'rgba(255,194,74,0.5)',fx:'write'}); hud(t,0,2.1,9); t.update(u,N0+0.2,TP-0.4,0.82);
  const seq=seqStr('ABBA',8); const per=0.75; const tt=u-TP+0.2; if(u>TP-0.3&&u<QQ+1.5){ rally(seq,tt,per,1-ss(QQ+0.5,QQ+1.5,u)); const kk=tt/per; seqRow(seq,-3.2,2.05,0.8,1-ss(QQ-0.6,QQ-0.2,u),{k:kk+0.6});
    let a2=0,b2=0; for(let i=0;i<8&&i<kk;i++){ if(seq[i]==='A') a2++; else b2++; }
    const even=a2===b2&&kk>1; num('ndA'+a2,String(a2),GO,0.55,-1.0,0.95,(1-ss(QQ-0.6,QQ-0.2,u))); num('ndB'+b2,String(b2),CY,0.55,1.0,0.95,(1-ss(QQ-0.6,QQ-0.2,u)));
    lab('ndE',T('= 一样多','= even'),0,0.95,even?(1-ss(QQ-0.6,QQ-0.2,u)):0,{size:0.32,color:'#b8ffd8',glow:MINT}); }
  const q=bt('ndQ',T('你打抢七，喜欢先发还是后发？','In a tiebreak: serve first, or second?'),{size:0.72,glow:'rgba(79,227,255,0.45)',fx:'particles'}); hud(q,0,-1.3,9); q.update(u,QQ,D+5,0.82);
}

const SHOTS={hook:shotHook,rule:shotRule,edge:shotEdge,math:shotMath,why:shotWhy,soccer:shotSoccer,data:shotData,end:shotEnd};
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
