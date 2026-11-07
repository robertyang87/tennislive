// vibetennis EP10 德约为什么是接发之王——200 km/h 的发球、人类反应的极限、预判、分腿垫步、硬地滑步：接发是一场在球落地之前就决定了的比赛。
// 理论与上屏数字的出处见 papers/vibetennis-djokovic-return-2026/sources.md（两源规则）；镜头与转场见同目录 storyboard.md。
// 通用底座（夜空、光点、全息字、3D 字、球场、后期）沿用 EP06–EP09；全息人体、时间赛跑、视线追踪、滑步接触面为本集新做。示意的动作都在画面上标「示意」。

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


// ==================== EP10 德约接发：本集物件 ====================
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
let ST_F, ST_TOP, ST_FL, ST_CR, ST_N=0; const ST_MATS=[];
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
  for(const [m,b] of ST_MATS) m.opacity=b*o;
  let rate=0.0003; if(kind==='hook'){ const a=ev('court',7.7), b=ev('run',16.5); rate=lerp(0.0003,0.006,ss(a,a+1.0,u)*(1-ss(b+1.0,b+2.5,u))); }
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
  sFollow:{y:-0.08, lean:0.6, side:0.1, twist:0.6, head:0.0, aR:[0.4,-0.3,0.3,0.6], aL:[0.5,0.3,0,1.1], lR:[0.7,0.1,0.7,0.2], lL:[0.2,0.15,0.3,0.1]}};
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
  beamMat.uniforms.uOp.value=0; rimL.intensity=0; rimR.intensity=0; DOF.on=false; MOTE_SPEED=1; SLOW=null; }
// 全息榜单行
function row(k,i,str,val,max,col,o,hl=0){ const y=1.4-i*0.75; const w=4.6*clamp(val/max); const l=ln(col,hl?14:10); setLine(l,[V(-1.2,y,0),V(-1.2+w,y,0)]); l.material.opacity=o*(0.75+0.25*hl);
  const t=tx(k,str,{color:hl?'#ffffff':'#c8d8ea',size:0.42,glow:hl?CYAN:'rgba(120,160,200,0.6)'}); t.position.set(-3.4,y,0.1); op(t,o); }

// ---------- 1 钩子：开场即砸出冲突——「7」从天而降炸开 → 炸成「接发之王」→ 甩进 2011 美网赛点接发 → 王在哪？ ----------
// 所有者 2026-11-07：「前几秒一定要抓住人……直接抛出来，然后用炸裂或者是非常爆裂的动作，或者特效把这个东西做到极致」
function burst(c,k,col,spread=6,o=1){ const cc=new THREE.Color(col); for(let i=0;i<1600;i++){ const p=PTS[i]; const dir=V(p[0],p[1]*1.2,p[2]).normalize(); const sp=spread*(0.4+0.6*p[3]); const e=1-Math.pow(1-clamp(k),2.2);
  cset(pt,i,c.x+dir.x*sp*e,c.y+dir.y*sp*e-1.5*e*e,c.z+dir.z*sp*e,cc.r,cc.g,cc.b,o*(1-ss(0.55,1,k))*(0.5+0.5*p[4])); } cdone(pt); }
function shockRing(c,k,col,maxR,o=1,vertical=false){ const r=rg(); r.position.copy(c); vertical?r.rotation.set(0,0,0):r.rotation.set(-Math.PI/2,0,0); const e=1-Math.pow(1-clamp(k),3); r.scale.setScalar(0.2+maxR*e); r.material.color.set(col).multiplyScalar(GLOW.k); r.material.opacity=o*(1-ss(0.35,1,k)); }
function shotHook(u,D){
  const SLAM=ev('slam',0.3), SEV=ev('seven',2.4), CRN=ev('crown',5.5), CT=ev('court',7.7), SV=ev('serve',11.4), RT=ev('ret',14.6), RUN=ev('run',16.5), QQ=ev('q',19.9);
  if(u<CT-0.3){ // A：巨大的「7」砸下来，冲击波＋粒子炸开；榜单在它周围拼出来 → B：「7」炸成粒子，汇成「接发之王」
    look(lerp(1.2,-0.6,ss(0,CT,u)),lerp(-0.6,0.2,ss(0,CT,u)),lerp(10.5,9.0,ss(0,CT,u)),0,0.6,0);
    const fall=clamp(u/0.55), imp=0.55; const y=lerp(4.2,0.7,fall*fall);   /* 第一帧「7」就在画面上方往下砸 */
    const seven=t3d('bigSeven','7','#ff6a55',3.2); seven.g.position.set(0,y,0); seven.g.rotation.set(0,(1-fall)*0.6+Math.sin(u*0.6)*0.08,0); t3op(seven,1-ss(CRN-0.1,CRN+0.25,u));
    if(u>imp){ const k=(u-imp)/1.4; shockRing(V(0,-1.0,0),k,RD,9); shockRing(V(0,-1.0,0),(u-imp-0.15)/1.6,GO,13,0.7); if(u<CRN) burst(V(0,-0.6,0),(u-imp)/1.6,0xff8a6a,7,0.9); const g=gs(RD,4.5,0.5*Math.exp(-(u-imp)*2.5)); g.position.set(0,-0.6,0.5); }
    const o=ss(imp+0.1,imp+0.8,u)*(1-ss(CRN-0.2,CRN+0.2,u));
    const rows=[[T('1  科里亚','1  Coria'),'171.5',2.0],[T('3  纳达尔','3  Nadal'),'167.8',1.25]];
    rows.forEach(([n,v,yy],i)=>{ const a=tx('hr'+i,n,{color:'#c8d8ea',size:0.4}); a.position.set(-5.0,yy,-1.2); op(a,o*ss(imp+0.1+i*0.15,imp+0.6+i*0.15,u)); const b=tx('hv'+i,v,{color:'#9fb8d0',size:0.36}); b.position.set(5.0,yy,-1.2); op(b,o*ss(imp+0.1+i*0.15,imp+0.6+i*0.15,u)); });
    const me=tx('hr7',T('7  德约科维奇  163.5','7  Djokovic  163.5'),{color:'#ffffff',size:0.48,glow:RED}); me.position.set(0,-1.75,0.6); op(me,ss(SEV-0.2,SEV+0.4,u)*(1-ss(CRN-0.2,CRN+0.2,u)));
    const hd=tx('hH',T('ATP 官方 · 历史接发评分','ATP official · all-time Return Rating'),{color:'#c8f4ff',size:0.4,glow:CYAN}); hud(hd,0,2.6); op(hd,o);
    if(u>SEV){ shockRing(V(0,0.7,0.4),((u-SEV)%1.2)/1.2,RD,2.6,0.6*(1-ss(CRN-0.6,CRN,u)),true); }
    if(u>CRN-0.15){ const k=(u-CRN+0.15)/1.4; burst(V(0,0.7,0),k,0xffc24a,6,1); }   /* 「7」炸成金色粒子 */
    const king=bt('kingT',T('接发之王','King of the Return'),{size:1.35,glow:GOLD,fx:'particles'}); hud(king,0,0.35,9); king.update(u,CRN+0.15,CT-0.6);
    if(u>CRN+0.8){ const r2=(u-CRN-0.8)/1.6; shockRing(V(0,0.5,0),r2,GO,6,0.6,true); }
    rims(RD,GO,6); beamMat.uniforms.uOp.value=0.06+0.1*ss(CRN,CRN+1,u); return; }
  if(u<QQ-0.3){ // C：2011 美网赛点，子弹时间的正手接发，击球点炸出冲击波，球拖着光迹贯穿全场
    courtG.visible=true; const C=SV+0.9, sf=0.65/Math.max(0.6,RT-C);
    humanOp(SRV,1); humanOp(RET,1); place(SRV,-0.8,-L2-0.3,0); place(RET,2.2,L2+0.9,Math.PI);
    applyPose(SRV,poseAt([[0,'stand'],[SV-0.6,'stand'],[SV,'sToss'],[SV+0.6,'sTrophy'],[C,'sHit'],[C+0.6,'sFollow']],u));
    const tb=(u-C)*sf; const A=V(-0.95,2.8,-L2+0.1), B=V(3.6,0,SLN-0.6), Cp=V(3.0,0.9,L2+0.7);
    applyPose(RET,poseAt([[0,'ready'],[C-0.15,'ready'],[C,'split'],[C+0.15/sf,'land'],[RT-0.35,'lungeF'],[RT+0.2,'lungeF'],[RT+1.4,'ready']],u));
    RET.root.position.x=lerp(2.2,2.7,ss(C+0.2/sf,RT-0.3,u));
    if(u>C&&tb<0.65){ const p=serveAt(tb,A,B,Cp); const b=bl(); showB(b,p,1,BS); const pts=[]; for(let i=0;i<=20;i++) pts.push(serveAt(tb*i/20,A,B,Cp)); trail(pts,GO,4,0.8); }
    if(u>=RT){ const k=clamp((u-RT)*0.9); const E=V(-3.6,0,-L2+3.2); const pos=kk=>V(lerp(Cp.x,E.x,kk),0.9+Math.sin(Math.PI*kk)*1.1,lerp(Cp.z,E.z,kk)); const b=bl(); showB(b,pos(k),1-ss(0.95,1,k),BS*1.3);
      const pts=[]; for(let i=0;i<=30;i++) pts.push(pos(k*i/30)); trail(pts,CY,9,0.95); const pts2=[]; for(let i=0;i<=30;i++) pts2.push(pos(k*i/30).add(V(0,0.05,0))); trail(pts2,WH,3,0.6);
      shockRing(Cp.clone(),(u-RT)/0.9,CY,3.2,1,true); shockRing(Cp.clone(),(u-RT-0.12)/1.1,WH,4.5,0.6,true); const g=gs(CY,2.2,0.6*Math.exp(-(u-RT)*3)); g.position.copy(Cp);
      if(k>=1){ shockRing(E.clone().setY(0.03),(u-RT-1.11)/1.2,CY,3,0.9); } }
    SLOW=[RT-0.1,RT+0.6];
    const sc=tx('hkSc',T('2011 美网半决赛 · 第五盘 3:5 · 费德勒握两个赛点','2011 US Open SF · fifth set 3-5 · Federer, 2 match points'),{color:'#ffe2a0',size:0.34,glow:GOLD,plate:true}); hud(sc,0,2.55); op(sc,ss(CT,CT+0.6,u)*(1-ss(RUN-0.3,RUN,u)));
    const sc2=tx('hkSc2',T('连赢四局 → 7:5 · 6-7 4-6 6-3 6-2 7-5','Four straight games → 7-5 · 6-7 4-6 6-3 6-2 7-5'),{color:'#c8f4ff',size:0.36,glow:CYAN,plate:true}); hud(sc2,0,2.55); op(sc2,ss(RUN,RUN+0.5,u));
    const w=tx('hkW',T('正手接发 · 直接得分','Forehand return winner'),{color:'#ffffff',size:0.56,glow:CYAN}); hud(w,0,-2.15); op(w,ss(RT+0.3,RT+0.8,u));
    const sch=tx('hkS',T('动作为示意','Motion is schematic'),{color:'#9fb8d0',size:0.24}); hud(sch,3.6,-2.95); op(sch,1);
    const tc=ss(CT,SV,u), rc=ss(RT-0.5,RT+1.5,u);
    look(lerp(7.5,5.2,tc)-rc*2.2, lerp(4.2,2.8,tc), lerp(L2+10,L2+7.2,tc)-rc*1.5, lerp(0,0.8,tc)-rc*1.4, 0.6, lerp(-2,-4,tc)+rc*-1);
    beamMat.uniforms.uOp.value=0.12; rims(GO,CY,5); DOF.on=u>C-0.3&&u<RT+1.2; DOF.focus=camera.position.distanceTo(V(3,0.9,L2)); DOF.ap=0.00005; return; }
  // D：王在哪？
  const v=u-QQ; courtG.visible=true; courtG.userData.mat.opacity=lerp(1,0.45,ss(0,0.8,v)); humanOp(RET,lerp(1,0.5,ss(0,0.8,v))); place(RET,2.7,L2+0.9,Math.PI); applyPose(RET,POSE.ready);
  look(4.0+v*0.2,2.4,L2+6.5,1.5,0.9,L2-2);
  const q=bt('hookQ',T('那这个「王」，到底王在哪？','So where does the "king" come from?'),{size:0.86,glow:GOLD,accent:T('王在哪','the "king"'),fx:'shock'}); hud(q,0,0.6); q.update(v,0.05,Infinity,0.9);
  rims(GO,CY,5); }

// ---------- 2 时间赛跑：0.65 s 的来球，0.2 s 的反应，0.19 s 就动拍 ----------
const TMAX=0.7;
function shotRace(u,D){
  const TL0=ev('tl',0.5), FL=ev('fly',5.4), RE=ev('react',7.1), JP=ev('jump',15.8), LD=ev('land',16.7), RK=ev('racket',18.2), FK=ev('fork',26.1), GU=ev('guess',31.9);
  courtG.visible=true; humanOp(SRV,1); humanOp(RET,1); place(SRV,-0.8,-L2-0.3,0); place(RET,0.6,L2+0.9,Math.PI);
  // 慢放：整段里把 0–0.7 s 循环演示（每轮 7 s，即 1/10 速），时间轴上的光标同步走
  const per=7.0, cyc=u<FL?0:((u-FL)%per)/per*TMAX+(u<FL?0:0), tb=u<FL?0:cyc;
  applyPose(SRV,tb<0.001&&u<FL?POSE.sTrophy:mixPose(POSE.sHit,POSE.sFollow,ss(0,0.25,tb)));
  const rp=tb<0.009?POSE.ready:tb<0.152?mixPose(POSE.split,POSE.land,ss(0.009,0.152,tb)):tb<0.187?POSE.land:mixPose(POSE.land,POSE.lungeF,ss(0.187,0.5,tb));
  applyPose(RET,u<JP?(u<FL?POSE.ready:mixPose(POSE.ready,POSE.ready,0)):rp);
  if(u>=FL){ const A=V(-0.95,2.8,-L2+0.1), B=V(2.4,0,SLN-0.6), Cp=V(1.6,0.9,L2+0.6); const b=bl(); if(tb<0.65){ showB(b,serveAt(tb,A,B,Cp),1,BS*1.4); } const pts=[]; for(let i=0;i<=24;i++) pts.push(serveAt(Math.min(tb,0.65)*i/24,A,B,Cp)); trail(pts,GO,4,0.7); }
  look(-23,13,0.4,0,0.0,0.4);   /* 侧面看整条来球路线：两个人都在画里；机位抬到看台前排人头上方（看台 2026-11-07 加的） */
  // 时间轴（镜头坐标里画）：0 → 0.7 s
  const x0=-4.2, x1=4.2, ty=2.15, X=t=>lerp(x0,x1,t/TMAX); const kk=ss(TL0,TL0+0.8,u);
  const ax=ln(0x9fd8ff,3); setLine(ax,[hp(x0,ty),hp(lerp(x0,x1,kk),ty)]); ax.material.opacity=0.9;
  for(let i=0;i<=7;i++){ const t=ln(0x9fd8ff,2); setLine(t,[hp(X(i*0.1),ty-0.08),hp(X(i*0.1),ty+0.08)]); t.material.opacity=0.8*kk; const s=tx('tk'+i,(i/10).toFixed(1)+'s',{color:'#9fb8d0',size:0.2}); hud(s,X(i*0.1),ty+0.28); op(s,kk); }
  const bf=ln(GO,9); setLine(bf,[hp(x0,ty-0.42),hp(X(0.65)*ss(FL,FL+1,u)+x0*(1-ss(FL,FL+1,u)),ty-0.42)]); bf.material.opacity=ss(FL,FL+0.5,u);
  const lb=tx('rBall',T('来球：发球到接发人约 0.6–0.7 秒','Ball: ~0.6–0.7 s from serve to returner'),{color:'#ffe2a0',size:0.28,glow:GOLD}); hud(lb,X(0.5),ty-0.68); op(lb,ss(FL,FL+0.6,u)*(1-ss(JP-0.6,JP,u)));
  const rr=ln(RD,9); setLine(rr,[hp(x0,ty-1.05),hp(lerp(x0,X(0.2),ss(RE,RE+0.8,u)),ty-1.05)]); rr.material.opacity=ss(RE,RE+0.4,u);
  const ll=tx('rReact',T('人的简单反应 ≈ 0.2 秒','Simple reaction ≈ 0.2 s'),{color:'#ffd2c8',size:0.28,glow:RED}); hud(ll,X(0.2)+1.9,ty-1.05); op(ll,ss(RE,RE+0.6,u)*(1-ss(JP-0.6,JP,u)));
  // 职业接发人的三个时刻
  const marks=[[0.009,JP,T('起跳','Take-off'),0],[0.152,LD,T('落地 0.15 s','Land 0.15 s'),1],[0.187,RK,T('动拍 0.19 s','Racket moves 0.19 s'),2]];
  marks.forEach(([t,e,s,i])=>{ const k=ss(e,e+0.5,u); const m=ln(CY,5); setLine(m,[hp(X(t),ty-0.3),hp(X(t),ty-1.7-i*0.0)]); m.material.opacity=k; const lb2=tx('rm'+i,s,{color:'#c8f4ff',size:0.28,glow:CYAN}); hud(lb2,X(t)+0.5+i*0.95,ty-1.95-i*0.3); op(lb2,k); });
  const cur=ln(WH,3); setLine(cur,[hp(X(tb),ty+0.15),hp(X(tb),ty-2.6)]); cur.material.opacity=u>FL?0.55:0;
  const src=tx('rSrc',T('职业球员实测（Mecheri 2019；Navia 2022）','Measured in pros (Mecheri 2019; Navia 2022)'),{color:'#9fb8d0',size:0.24}); hud(src,2.6,-2.95); op(src,ss(JP,JP+0.6,u));
  if(u>FK-0.2){ const k=ss(FK,FK+0.8,u); const c=wpos(RET.root).add(V(0,1.0,-1.0)); [-1,1].forEach((s,i)=>{ const a=ln(i?CY:GO,6,true); setLine(a,[c,c.clone().add(V(s*1.6*k,0,-1.6*k))]); a.material.opacity=k; }); const q=tx('rQ',T('往哪边？','Which way?'),{color:'#ffffff',size:0.5}); q.position.copy(c.clone().add(V(0,0.8,-1))); op(q,k*(1-ss(GU-0.4,GU,u))); }
  const g=bt('raceT',T('看清球之前，就已经猜好了','They guess before they see the ball clearly'),{size:0.62,glow:GOLD,accent:T('猜好了','guess'),fx:'streak'}); hud(g,0,-2.2); g.update(u,GU);
  rims(GO,CY,5); beamMat.uniforms.uOp.value=0.08; }

// ---------- 3 读懂发球人：抛球、持拍手臂＋球拍、上半身；眼睛先跳到落点 ----------
function shotRead(u,D){
  const BO=ev('body',0.5), TS=ev('toss',6.5), AR=ev('arm',7.2), GZ=ev('gaze',10.3), SC=ev('sacc',18.7), TI=ev('title',22.7);
  if(u<SC-0.3){ courtG.visible=true; humanOp(SRV,1); place(SRV,0,0,0); SRV.root.position.set(0,0,-L2-0.2);
    const ph=0.5+0.5*Math.sin((u-BO)*0.9); applyPose(SRV,mixPose(POSE.sToss,POSE.sTrophy,ss(0.1,0.9,ph)));
    // 抛球
    const tossH=2.4+1.0*ss(0.1,0.9,ph); const handL=wpos(SRV.armL.hand); const ball=bl(); const bp=V(handL.x,tossH,handL.z+0.15); showB(ball,bp,1,BS*1.3);
    const cues=[[TS,bp,GO,T('抛球','Ball toss'),0.7],[AR,wpos(SRV.armR.el),CY,T('持拍手臂＋球拍','Arm + racket'),0.9],[GZ,wpos(SRV.spine).add(V(0,0.4,0)),MT,T('上半身','Upper body'),1.2]];
    cues.forEach(([e,p,c,s,sz],i)=>{ const k=ss(e,e+0.6,u); const g=gs(c,sz,0.55*k); g.position.copy(p); const r=rg(); r.position.copy(p); r.rotation.set(0,0,0); r.scale.setScalar(sz*0.7*(1+0.08*Math.sin(u*4+i))); r.material.color.set(c).multiplyScalar(GLOW.k); r.material.opacity=0.8*k;
      const t=tx('cue'+i,s,{color:'#ffffff',size:0.3,glow:i===0?GOLD:i===1?CYAN:MINT}); t.position.copy(p.clone().add(V(i===0?0.7:-0.9,0.25,0.2))); op(t,k); });
    // 视线：从镜头这边（接发人的眼睛）射向线索
    if(u>GZ){ const eye=V(0.6,1.7,L2+0.6); const k=ss(GZ,GZ+0.8,u); [wpos(SRV.spine).add(V(0,0.4,0)),bp].forEach((p,i)=>{ const l=ln(MT,3,true); setLine(l,[eye,eye.clone().lerp(p,k)]); l.material.opacity=0.8*k; });
      const t=tx('gzT',T('眼动追踪：高手更多看上半身和球','Eye tracking: experts fixate the upper body and ball'),{color:'#c8ffe6',size:0.32,glow:MINT}); hud(t,0,-2.3); op(t,k); }
    const tt=tx('rdT',T('研究：高手靠抛球和持拍手臂＋球拍预判发球方向','Research: experts read the toss and arm + racket'),{color:'#ffe2a0',size:0.32,glow:GOLD}); hud(tt,0,-2.3); op(tt,ss(TS,TS+0.6,u)*(1-ss(GZ-0.3,GZ,u)));
    look(lerp(1.2,0.4,ss(0,SC,u)),1.7,-L2+lerp(6.5,5.2,ss(0,SC,u)),0,1.8,-L2-0.2); rims(GO,MT,5); DOF.on=true; DOF.focus=6; DOF.ap=0.00004; return; }
  // 板球研究：视线提前跳到落点等球
  const v=u-SC; courtG.visible=true; const per=3.2, k=(v%per)/per; const A=V(-0.6,2.6,-8), B=V(0.3,0,3.2), E=V(0.5,1.0,9.0);
  const p=k<0.6?A.clone().lerp(B,k/0.6).add(V(0,Math.sin(Math.PI*k/0.6)*0.6,0)):B.clone().lerp(E,(k-0.6)/0.4).add(V(0,Math.sin(Math.PI*(k-0.6)/0.4)*0.5,0));
  const b=bl(); showB(b,p,1,BS*1.4); const eye=V(0.5,1.7,9.6);
  const gT=k<0.35?p:B; const gl=ln(MT,4,true); setLine(gl,[eye,gT]); gl.material.opacity=0.85;
  const r=rg(); r.rotation.set(-Math.PI/2,0,0); r.position.set(B.x,0.02,B.z); r.scale.setScalar(0.8+0.2*Math.sin(v*6)); r.material.color.set(MT).multiplyScalar(GLOW.k); r.material.opacity=0.9*ss(0.3,0.36,k);
  const t=tx('scT',T('板球研究：顶级击球手的视线提前跳到落点等球','Cricket studies: elite batters\' eyes jump ahead to the bounce'),{color:'#c8ffe6',size:0.32,glow:MINT}); hud(t,0,2.5); op(t,ss(0,0.6,v)*(1-ss(TI-SC-0.4,TI-SC,v)));
  const ti=bt('readT',T('接发，在球过网之前就开始了','The return starts before the ball crosses the net'),{size:0.64,glow:GOLD,accent:T('之前','before'),fx:'write'}); hud(ti,0,-2.2); ti.update(v,TI-SC);
  look(3.2,2.4,12,0,0.8,1); rims(MT,CY,4); }

// ---------- 4 分腿垫步：快一成多；牵张-缩短循环 ----------
function spring(a,b,col,o,comp){ const l=ln(col,4); const pts=[]; const ax=b.clone().sub(a), len=ax.length(); ax.normalize(); const side=new THREE.Vector3(1,0,0).cross(ax).normalize(); const side2=ax.clone().cross(side).normalize(); const n=10, r=0.07*(1+comp*0.6);
  for(let i=0;i<=n*16;i++){ const t=i/(n*16); const ang=t*n*Math.PI*2; pts.push(a.clone().addScaledVector(ax,len*t).addScaledVector(side,Math.cos(ang)*r).addScaledVector(side2,Math.sin(ang)*r)); } setLine(l,pts); l.material.opacity=o; }
function shotSplit(u,D){
  const GOg=ev('go',0.5), HP=ev('hop',4.7), RC=ev('race',7.7), SP=ev('spring',15.5), TI=ev('title',20.1);
  courtG.visible=true;
  if(u<RC-0.3){ humanOp(RET,1); place(RET,0,L2+0.6,Math.PI); const v=u-HP; const per=2.4; const k=v<0?0:(v%per)/per;
    const P=k<0.15?mixPose(POSE.ready,POSE.split,ss(0,0.15,k)):k<0.4?mixPose(POSE.split,POSE.land,ss(0.15,0.4,k)):k<0.75?mixPose(POSE.land,POSE.lungeF,ss(0.45,0.75,k)):mixPose(POSE.lungeF,POSE.ready,ss(0.75,1,k));
    applyPose(RET,P); RET.root.position.y=k>0.15&&k<0.4?Math.sin(Math.PI*(k-0.15)/0.25)*0.12:0; RET.root.position.x=k>0.45&&k<0.75?ss(0.45,0.75,k)*1.0:k>=0.75?lerp(1,0,ss(0.75,1,k)):0;
    SLOW=[HP,RC];
    const t=tx('spT',T('分腿垫步：对手击球那一刻起跳','Split step: take off as the server strikes'),{color:'#c8f4ff',size:0.36,glow:CYAN}); hud(t,0,-2.3); op(t,ss(HP,HP+0.6,u));
    look(3.6,1.4,L2+4.2,0,0.9,L2+0.6); rims(CY,GO,5); return; }
  if(u<SP-0.3){ // 两个人比启动：垫步的先到
    const v=u-RC; humanOp(G1,1); humanOp(G2,1); const per=3.0, k=(v%per)/per;
    const go=t=>clamp((t-0.12)/0.75), go2=t=>clamp((t-0.12)/(0.75/1.125));   /* 垫步约快 12%：同样距离，用时 ÷ 1.12 */
    [[G1,-1.4,go(k),false],[G2,1.4,go2(k),true]].forEach(([H,x,g,sp])=>{ place(H,x,0,Math.PI*0.5); H.root.position.z=-g*4.5+2; applyPose(H,g>0&&g<1?mixPose(POSE.lungeF,POSE.ready,0.5*Math.sin(g*20)+0.5):POSE.ready); });
    const f1=ln(0x9fb8d0,4), f2=ln(CY,4); setLine(f1,[V(-1.4,0.02,-2.5),V(1.4,0.02,-2.5)]); f1.material.opacity=0.7; f2.material.opacity=0;
    const a=tx('spA',T('不垫步','No split step'),{color:'#c8d8ea',size:0.36}); a.position.set(-1.4,2.3,2); op(a,1);
    const b=tx('spB',T('垫步','Split step'),{color:'#c8f4ff',size:0.36,glow:CYAN}); b.position.set(1.4,2.3,2); op(b,1);
    const r=tx('spR',T('实验：快 12–13%','Lab tests: 12–13% faster'),{color:'#ffffff',size:0.46,glow:CYAN}); hud(r,0,-2.2); op(r,ss(0.3,0.9,v));
    const s=tx('spS',T('Uzu 等 2009；Nieminen 等 2014（光信号实验）','Uzu et al. 2009; Nieminen et al. 2014 (light-signal tasks)'),{color:'#9fb8d0',size:0.24}); hud(s,2.6,-2.95); op(s,1);
    look(0,4.2,7.2,0,0.6,0); rims(CY,0x9fb8d0,5); return; }
  // X 光腿：肌肉和肌腱像弹簧
  const v=u-SP; look(1.6,1.0,L2+3.0,0,0.6,L2+0.6); humanOp(RET,0.35); place(RET,0,L2+0.6,Math.PI); const per=2.2, k=(v%per)/per; const comp=k<0.4?ss(0,0.4,k):1-ss(0.4,0.55,k);
  applyPose(RET,mixPose(POSE.split,POSE.land,comp));
  [[RET.legR,0],[RET.legL,1]].forEach(([Lg,i])=>{ const hip=wpos(Lg.hp), knee=wpos(Lg.kn), an=wpos(Lg.an); spring(hip,knee,GO,0.9,comp); spring(knee,an,GO,0.9,comp); const g=gs(GO,0.5+0.5*comp,0.35*comp); g.position.copy(knee); });
  const e=ln(GO,10); setLine(e,[hp(-3.8,-1.4),hp(-3.8,-1.4+2.2*comp)]); e.material.opacity=0.9; const el=tx('spE',T('储能','Stored energy'),{color:'#ffe2a0',size:0.3}); hud(el,-3.8,-1.75); op(el,1);
  const ti=bt('ssc',T('牵张-缩短循环','Stretch-shortening cycle'),{size:0.78,glow:GOLD,fx:'sag'}); hud(ti,0,2.3); ti.update(v,TI-SP);   /* 下沉：像落地 */
  const l=tx('spL',T('落地拉长 → 像弹簧一样存能 → 立刻弹出','Landing stretches → stores energy like a spring → snaps back'),{color:'#ffffff',size:0.32}); hud(l,0,-2.3); op(l,ss(0,0.6,v));
  rims(GO,CY,6); }

// ---------- 5 硬地滑步：静摩擦 → 滑动摩擦 ----------
function shotSlide(u,D){
  const SL=ev('slide',2.3), GR=ev('grip',7.7), KN=ev('kin',11.9), CP=ev('comp',17.1);
  courtG.visible=true;
  if(u<CP-0.3){ humanOp(RET,1); place(RET,0,L2,Math.PI); const per=4.0, v=Math.max(0,u-SL), k=(v%per)/per;
    const x=k<0.55?ss(0,0.55,k)*3.2:3.2-ss(0.7,1,k)*3.2; RET.root.position.x=x; applyPose(RET,k<0.15?POSE.ready:k<0.7?mixPose(POSE.ready,POSE.lungeF,ss(0.15,0.45,k)):mixPose(POSE.lungeF,POSE.ready,ss(0.7,1,k)));
    const foot=wpos(RET.legR.ft); const sliding=k>0.3&&k<0.55; const mu=u<KN?1:(sliding?0.55:1);
    const fl=ln(u<KN?GO:CY,14); setLine(fl,[foot.clone().setY(0.06),foot.clone().setY(0.06).add(V(-1.6*mu,0,0))]); const fh=ln(u<KN?GO:CY,14); const tip=foot.clone().setY(0.06).add(V(-1.6*mu,0,0)); setLine(fh,[tip.clone().add(V(0.25,0,0.15)),tip,tip.clone().add(V(0.25,0,-0.15))]); fh.material.opacity=u>GR?0.95:0; fl.material.opacity=u>GR?0.95:0;
    const tr=ln(CY,5); setLine(tr,[V(Math.max(0,x-1.6),0.02,L2+0.15),V(x,0.02,L2+0.15)]); tr.material.opacity=sliding&&u>SL?0.6:0;
    const a=tx('slA',T('静摩擦：抓住地面','Static friction: grip'),{color:'#ffe2a0',size:0.36,glow:GOLD}); hud(a,0,-2.25); op(a,ss(GR,GR+0.6,u)*(1-ss(KN-0.3,KN,u)));
    const b=tx('slB',T('滑起来：滑动摩擦更小，一边刹车一边到位','Sliding: smaller kinetic friction, braking while reaching'),{color:'#c8f4ff',size:0.34,glow:CYAN}); hud(b,0,-2.25); op(b,ss(KN,KN+0.6,u));
    const c=tx('slC',T('摩擦力示意','Friction schematic'),{color:'#9fb8d0',size:0.24}); hud(c,3.6,-2.95); op(c,ss(GR,GR+0.6,u));
    SLOW=[SL,CP]; look(lerp(5.5,3.2,ss(0,GR,u)),lerp(1.8,0.8,ss(GR-1,GR+1,u)),L2+lerp(5.5,3.4,ss(0,GR,u)),1.6,0.4,L2); DOF.on=u>GR; DOF.focus=3.6; DOF.ap=0.00005; rims(GO,CY,5); return; }
  // 两个人比回位：滑步刹车先回到中间
  const v=u-CP; humanOp(G1,1); humanOp(G2,1); const per=3.4, k=(v%per)/per;
  [[G1,-0.9,1.0,false],[G2,0.9,1/1.08,true]].forEach(([H,dz,sc,sl])=>{ const kk=clamp(k/sc); const x=kk<0.5?ss(0,0.5,kk)*3:3-ss(0.5,1,kk)*3; place(H,x-1.5,L2+dz,Math.PI); applyPose(H,kk<0.5?mixPose(POSE.ready,POSE.lungeF,ss(0.1,0.5,kk)):mixPose(POSE.lungeF,POSE.ready,ss(0.5,1,kk))); });
  const a=tx('slD',T('普通刹车','Normal braking'),{color:'#c8d8ea',size:0.34}); a.position.set(-3.6,2.2,L2-0.9); op(a,1);
  const b=tx('slE',T('滑步刹车','Slide braking'),{color:'#c8f4ff',size:0.34,glow:CYAN}); b.position.set(-3.6,2.2,L2+0.9); op(b,1);
  const r=tx('slR',T('大学精英球员实验：滑步回位更快（Ji 等 2025）','Elite college players: sliding recovers faster (Ji et al. 2025)'),{color:'#ffffff',size:0.32}); hud(r,0,-2.25); op(r,ss(0.3,0.9,v));
  look(0,5.5,L2+6.5,0,0.5,L2); rims(CY,0x9fb8d0,4); }

// ---------- 6 数据：榜单拆开看 ----------
function shotData(u,D){
  const BD=ev('board',0.5), SM=ev('sum',5.0), AL=ev('all',9.5), HD=ev('hard',11.9), AC=ev('act',13.3), Y1=ev('y11',17.1), DP=ev('deep',23.1), HH=ev('h2h',30.5), LS=ev('last',36.3);
  if(u<Y1-0.3){ // 四项相加 → 三个名次
    look(Math.sin(u*0.2)*0.4,0.3,9,0,0.2,0); const o=ss(BD,BD+0.6,u); const comps=[[T('一发接发得分率','1st-serve return pts'),33.4,GO],[T('二发接发得分率','2nd-serve return pts'),55.0,CY],[T('接发局胜率','Return games won'),31.2,MT],[T('破发成功率','Break points converted'),43.9,0xa78bfa]];
    let acc=0; const ks=ss(SM,SM+2.0,u);
    comps.forEach(([s,val,c],i)=>{ const w=val/170*8.4; const x0=lerp(-4.2,-4.2+acc,ks), y=lerp(1.3-i*0.6,-0.3,ks); const l=ln(c,12); setLine(l,[hp(x0,y),hp(x0+w,y)]); l.material.opacity=o*ss(SM-0.2+i*0.25,SM+0.4+i*0.25,u+0.6)*(1-ss(AL-0.6,AL,u));
      const t=tx('dc'+i,s+' '+val.toFixed(1),{color:'#ffffff',size:0.26}); hud(t,x0+w/2,y+0.32); op(t,o*(1-ks)); acc+=w; });
    const sum=tx('dSum',T('= 163.5','= 163.5'),{color:'#ffe2a0',size:0.5,glow:GOLD}); hud(sum,3.9,-0.3); op(sum,ks*(1-ss(AL-0.3,AL,u)));
    const hd=tx('dH',T('ATP 接发评分 = 四项百分比相加','ATP Return Rating = four percentages added'),{color:'#c8f4ff',size:0.34,glow:CYAN}); hud(hd,0,2.5); op(hd,ss(SM,SM+0.5,u)*(1-ss(AL-0.3,AL,u)));
    const ranks=[[AL,'7',T('历史','All-time'),'#ff9a8a'],[HD,'2',T('硬地','Hard court'),'#ffd27a'],[AC,'1',T('现役','Active players'),'#7fffd0']];
    ranks.forEach(([e,n,s,c],i)=>{ const k=ss(e,e+0.5,u); const o3=t3d('rk'+n,n,c,1.3); o3.g.position.copy(hp(-3+i*3,0.2,9)); o3.g.quaternion.copy(camera.quaternion); t3op(o3,k); const t=tx('rkl'+i,s,{color:'#ffffff',size:0.4}); hud(t,-3+i*3,-1.1); op(t,k); });
    const ft=tx('dF',T('ATP 官方榜单，截至 2026 年 11 月','ATP official leaderboards, as of Nov 2026'),{color:'#9fb8d0',size:0.24}); hud(ft,2.6,-2.95); op(ft,ss(AL,AL+0.5,u));
    rims(GO,CY,4); return; }
  if(u<DP-0.3){ // 2011：38.8% 的接发局
    const v=u-Y1; const k=ss(0.2,1.8,v); const r=ln(GO,12); arc(r,V(0,0.3,0),1.6,Math.PI/2,Math.PI/2-Math.PI*2*0.388*k,'z'); r.material.opacity=0.95; const r2=ln(0x5a6a80,4); arc(r2,V(0,0.3,0),1.6,0,Math.PI*2,'z'); r2.material.opacity=0.6;
    const n=t3d('p388','38.8%','#ffd27a',0.6); n.g.position.set(0,0.3,0); t3op(n,ss(0.6,1.2,v)); const y=t3d('y2011','2011','#c8f4ff',0.45); y.g.position.set(0,2.4,0); t3op(y,ss(0,0.5,v));
    const t=tx('d11',T('接发局胜率 · 当年接发评分第一','Return games won · No. 1 that year'),{color:'#ffffff',size:0.36}); hud(t,0,-2.3); op(t,ss(0.4,1,v));
    look(0,0.5,7.2,0,0.4,0); rims(GO,CY,4); return; }
  if(u<HH-0.3){ // 回球深度：3D 球场上 100 个落点，八成落在发球线以后
    const v=u-DP; courtG.visible=true; const kd=ss(0.3,2.5,v);
    const cnt=Math.floor(100*kd); DOTS.forEach((m,i)=>{ const deep=(i%5)!==4; const h=((i*7919)%997)/997, h2=((i*104729)%991)/991; m.visible=i<cnt;   /* 100 个落点，按真实的八成落在发球线以后 */
      m.position.set(-3.6+h2*7.2,0.06,deep?-(SLN+0.4+h*(L2-SLN-0.8)):-(1.2+h*(SLN-1.6))); m.material.color.set(deep?CY:RD).multiplyScalar(0.9); });
    const sl=ln(WH,4); setLine(sl,[V(-4.1,0.03,-SLN),V(4.1,0.03,-SLN)]); sl.material.opacity=0.9*ss(0,0.5,v);
    const a=tx('dpA',T('发球线','Service line'),{color:'#ffffff',size:0.3}); a.position.set(4.6,0.4,-SLN); op(a,ss(0,0.5,v));
    const names=[[T('德约','Djokovic'),80,CY],[T('穆雷','Murray'),76,0x9fb8d0],[T('辛纳','Sinner'),76,0x9fb8d0],[T('费德勒','Federer'),75,0x9fb8d0],[T('阿加西','Agassi'),74,0x9fb8d0],[T('阿尔卡拉斯','Alcaraz'),74,0x9fb8d0],[T('纳达尔','Nadal'),69,0x9fb8d0]];
    look(-4.2,9.5,2.5,-4.2,0,-7.5);   /* 球场偏到画面右边，左边放名单 */
    names.forEach(([s,val,c],i)=>{ const k=ss(1.4+i*0.25,2.0+i*0.25,v); const y=1.9-i*0.48; const l=ln(c,i?8:12); setLine(l,[hp(-2.9,y),hp(-2.9+(val-60)/25*2.4*k,y)]); l.material.opacity=k; const t=tx('dpn'+i,s+'  '+val+'%',{color:i?'#c8d8ea':'#ffffff',size:0.28,glow:i?'rgba(120,160,200,0.6)':CYAN}); hud(t,-4.0,y); op(t,k); });
    const h=tx('dpH',T('回到发球线以后的比例（志愿者逐分统计）','Returns landing beyond the service line (volunteer charting)'),{color:'#c8f4ff',size:0.32,glow:CYAN}); hud(h,0,2.6); op(h,ss(0.3,0.9,v));
    rims(CY,GO,4); return; }
  // 对大炮发球手
  const v=u-HH; const pairs=[[T('拉奥尼奇','Raonic'),'12 – 0'],[T('伊斯内尔','Isner'),'10 – 2']];
  pairs.forEach(([s,sc],i)=>{ const k=ss(i*0.6,i*0.6+0.6,v); const o3=t3d('hh'+i,sc,i?'#ffd27a':'#7fffd0',0.75); o3.g.position.set(-2.2+i*4.4,0.4,0); t3op(o3,k*(1-ss(LS-HH-0.3,LS-HH,v))); const t=tx('hhn'+i,T('对 ','vs ')+s,{color:'#ffffff',size:0.42}); t.position.set(-2.2+i*4.4,-0.7,0); op(t,k*(1-ss(LS-HH-0.3,LS-HH,v))); });
  const h=tx('hhH',T('面对大炮发球手（ATP 交手记录）','Against big servers (ATP head-to-head)'),{color:'#c8f4ff',size:0.34,glow:CYAN}); hud(h,0,2.5); op(h,ss(0,0.5,v)*(1-ss(LS-HH-0.3,LS-HH,v)));
  const ti=bt('dataT',T('未必破发最多，却回得最深','Not the most breaks — but the deepest returns'),{size:0.66,glow:GOLD,accent:T('回得最深','deepest'),fx:'spin'}); hud(ti,0,0.3); ti.update(v,LS-HH);
  look(Math.sin(v*0.3)*0.6,0.3,8.5,0,0.2,0); rims(GO,CY,4); }

// ---------- 7 结论 ----------
function shotEnd(u,D){
  const N0=ev('n0',0.5), P1=ev('p1',5.0), P2=ev('p2',5.9), P3=ev('p3',6.5), QQ=ev('q',9.3);
  look(lerp(3,1.5,ss(0,D,u)),1.6,L2+5,0,1.0,L2); courtG.visible=true; humanOp(RET,1); place(RET,0,L2+0.6,Math.PI); applyPose(RET,poseAt([[0,'ready'],[P2,'ready'],[P2+0.3,'split'],[P2+0.6,'land'],[P3+0.4,'lungeF'],[P3+1.6,'ready']],u));
  const t0=bt('endA',T('接发比的不是反应','It\'s not about reaction speed'),{size:0.7,glow:CYAN,fx:'particles'}); hud(t0,0,2.4); t0.update(u,N0,P1-0.6);
  const pil=[[P1,T('更早看懂','Read earlier'),MT],[P2,T('及时起跳','Split in time'),CY],[P3,T('回得够深','Return deep'),GO]];
  pil.forEach(([e,s,c],i)=>{ const k=ss(e,e+0.5,u); const x=-3.2+i*3.2; const l=ln(c,10); setLine(l,[hp(x,-1.7),hp(x,-1.7+1.5*k)]); l.material.opacity=k*(1-ss(QQ-0.4,QQ,u)); const t=tx('pil'+i,s,{color:'#ffffff',size:0.42,glow:i===0?MINT:i===1?CYAN:GOLD}); hud(t,x,-2.2); op(t,k*(1-ss(QQ-0.4,QQ,u))); });
  const q=bt('endQ',T('你心中的接发之王是谁？','Who is your king of the return?'),{size:0.82,glow:GOLD,fx:'shock'}); hud(q,0,2.4); q.update(u,QQ);
  const nm=tx('endN',T('德约 · 纳达尔 · 阿加西 ……','Djokovic · Nadal · Agassi …'),{color:'#ffe2a0',size:0.5,glow:GOLD}); hud(nm,0,1.4); op(nm,ss(QQ+0.6,QQ+1.2,u));
  rims(GO,CY,5); beamMat.uniforms.uOp.value=0.1; }

const SHOTS={hook:shotHook,race:shotRace,read:shotRead,split:shotSplit,slide:shotSlide,data:shotData,end:shotEnd};
function shotTest(u,D){}
Object.assign(PAL,{
  hook: {top:0x05030f,hz:0x1a1048,vi:0x3a0a3a,a:0xffc24a},
  race: {top:0x030812,hz:0x0b2a50,vi:0x0a2030,a:0x4fe3ff},
  read: {top:0x020c0a,hz:0x063828,vi:0x062a2a,a:0x34f5a8},
  split:{top:0x03050c,hz:0x0c1a3a,vi:0x08202a,a:0x4fe3ff},
  slide:{top:0x0c0806,hz:0x3a2a08,vi:0x0a2030,a:0xffc24a},
  data: {top:0x06041a,hz:0x1d1250,vi:0x2b0d55,a:0xa78bfa},
  end:  {top:0x050505,hz:0x2a2008,vi:0x08202a,a:0xffc24a}});

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
