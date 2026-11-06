// vibetennis 器材三部曲 ② 球拍的演变——木 → 钢／铝 → 大拍面 → 碳纤维，拍子改了什么、背后的物理（甜点三个点、扭转惯量、刚度、挥拍重量），和打法能不能对上。
// 理论与上屏数字的出处见 papers/vibetennis-racket-2026/sources.md（两源规则）；镜头动效表见 papers/vibetennis-racket-2026/motion.md。
// 通用底座（夜空、光点、全息字、3D 字、球场、后期）沿用 EP06；球拍、线床、图表为本集新做。示意的形状都在画面上标「示意」。
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


// ==================== EP08 球拍：本集物件 ====================
// 比例：1 单位 = 10 cm。木拍拍面按 Head 专利背景「长轴约 10½ 英寸、短轴约 8½ 英寸」（≈ 70 平方英寸）；
// 大拍面按专利首选「13½ × 10½ 英寸」画形状，但片中不念这个面积（只说「大了 40% 以上」，两源）。示意的东西画面上标「示意」。
const IN=0.254;                                   // 1 英寸 = 0.254 单位
const WOOD={a:10.5/2*IN, b:8.5/2*IN}, BIG={a:13.5/2*IN, b:10.5/2*IN};
const GOLD='rgba(255,194,74,0.95)', CYAN='rgba(79,227,255,0.95)', RED='rgba(255,90,74,0.95)', VIO='rgba(167,139,250,0.95)', MINT='rgba(52,245,168,0.95)';
const TT={}; const tx=(k,s,o={},grp=scene)=>TT[k]||(TT[k]=textSprite(s,o,grp));
const TITLE_DIM=0.86;   // 光晕标准：纯白大字满不透明度会越过泛光阈值（0.93），钩子和片尾两行问句 glow_check 超标（gain 2.15 / 3.09）；整体压到 86%
const TB={}; const bt=(k,s,o={})=>TB[k]||(TB[k]=(t=>{ const up=t.update.bind(t); t.update=(u,IN,OUT=Infinity,mul=1)=>up(u,IN,OUT,mul*TITLE_DIM); return t; })(makeTitle(THREE,s,Object.assign({k:GLOW.k,group:scene},o))));   // 一级大字：TYPE 标准（engine/typefx.js）；不叫 BIG——那个名字是大拍面尺寸
const HUDQ=[];   // hud() 在 look() 之前调也行：先记下，等这一帧机位定了再放
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
const BIGF='900 150px "Noto Sans CJK SC","Inter",sans-serif';

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
function makeRk(kind,{a=WOOD.a,b=WOOD.b,beam=0.06}={},group=scene){
  const g=new THREE.Group(); group.add(g); const mat=MATS[kind]();
  const head=new THREE.Group(); g.add(head);
  const ring=new THREE.EllipseCurve(0,0,1,1,0,Math.PI*2).getPoints(180).map(p=>new THREE.Vector3(p.x,p.y,0));
  const frame=new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(ring,true),220,1,12,true),mat); head.add(frame);
  // 线床：单位圆内的格子（随拍头一起缩放）
  const sp=[]; const nm=16, nc=19;
  for(let i=0;i<nm;i++){ const x=-0.9+1.8*i/(nm-1), y=Math.sqrt(1-x*x)*0.985; sp.push(x,-y,0,x,y,0); }
  for(let i=0;i<nc;i++){ const y=-0.9+1.8*i/(nc-1), x=Math.sqrt(1-y*y)*0.985; sp.push(-x,y,0,x,y,0); }
  const sg=new THREE.BufferGeometry(); sg.setAttribute('position',new THREE.Float32BufferAttribute(sp,3));
  const strings=new THREE.LineSegments(sg,new THREE.LineBasicMaterial({color:new THREE.Color(STRC[kind]).multiplyScalar(0.8),transparent:true,opacity:0.7})); head.add(strings);
  const neck=new THREE.Group(); g.add(neck);
  const nmat=mat; const th=[]; for(const s of [-1,1]){ const m=new THREE.Mesh(new THREE.CylinderGeometry(beam*0.9,beam*0.9,1,10),nmat); neck.add(m); th.push(m); }
  const shaft=new THREE.Mesh(new THREE.CylinderGeometry(beam*1.6,beam*1.5,1,10),nmat); neck.add(shaft);
  const handle=new THREE.Mesh(new THREE.CylinderGeometry(0.15,0.16,1.8,8),new THREE.MeshPhysicalMaterial({color:0x3a3f4c,roughness:0.6,emissive:0x0c1018,emissiveIntensity:0.6,transparent:true})); neck.add(handle);
  const R={g,head,frame,strings,mat,neck,th,shaft,handle,kind,a,b,beam,tip:a};
  setRk(R,a,b); return R; }
// 改拍头尺寸：顶端固定（tip 不动），拍面往手柄方向长（Head 专利的做法）。拍杆、握把跟着往下挪
function setRk(R,a,b,{keepTip=true}={}){ R.a=a; R.b=b; const cy=keepTip?R.tip-a:0;
  R.head.position.set(0,cy,0); R.head.scale.set(b,a,1); R.frame.scale.set(1,1,R.beam*8);
  R.frame.geometry.dispose(); const ring=new THREE.EllipseCurve(0,0,b,a,0,Math.PI*2).getPoints(180).map(p=>new THREE.Vector3(p.x,p.y,0));
  R.frame.geometry=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(ring,true),220,R.beam,12,true); R.frame.scale.set(1/b,1/a,1);
  const bot=cy-a, thY=bot-0.55;   // 拍喉收拢点
  R.th.forEach((m,i)=>{ const s=i?1:-1; const p0=new THREE.Vector3(s*b*Math.sin(0.75),cy-a*Math.cos(0.75),0), p1=new THREE.Vector3(s*0.1,thY,0);
    m.position.copy(p0).lerp(p1,0.5); m.scale.set(1,p0.distanceTo(p1),1); m.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),p1.clone().sub(p0).normalize()); });
  R.shaft.position.set(0,thY-0.45,0); R.shaft.scale.set(1,0.9,1); R.handle.position.set(0,thY-0.9-0.9,0); R.gripY=thY-1.2; R.bot=bot; R.cy=cy; }
function rkOp(R,v){ R.mat.opacity=v; R.strings.material.opacity=0.7*v; R.handle.material.opacity=v; R.g.visible=v>0.003; }

// ---- 一批球拍与物件 ----
const rkA=makeRk('carbon',{a:BIG.a*0.95,b:BIG.b*0.95});      // 钩子、片尾用的现代拍
const rkW=makeRk('wood');                                   // 木拍（主角）
const rkS=makeRk('steel'), rkAl=makeRk('alu',{a:WOOD.a*1.03,b:WOOD.b*1.03}), rkC=makeRk('carbon',{a:BIG.a*0.92,b:BIG.b*0.92}), rkB=makeRk('alu',{a:BIG.a,b:BIG.b});
const rkW2=makeRk('wood');                                  // 分屏用的第二支木拍
const ghosts=[0,1,2].map(()=>makeRk('wood'));               // 重影
const ALLRK=[rkA,rkW,rkS,rkAl,rkC,rkB,rkW2,...ghosts];
const ball=makeBall(0.33), ball2=makeBall(0.33), ball3=makeBall(0.2);
const showB=(b,p,vis=true,o=1)=>{ b.m.visible=vis; b.gl.visible=vis; if(vis){ b.m.position.copy(p); b.gl.position.copy(p); b.m.material.transparent=true; b.m.material.opacity=o; b.gl.material.opacity=0.35*o; } };
const LN=[...Array(14)].map((_,i)=>fatLine(0xffffff,3));    // 通用光线池
let lnI=0; const ln=(col,w=3,dashed=false)=>{ const l=LN[lnI++]; l.material.color.set(col); l.material.linewidth=w; l.material.dashed=dashed; return l; };
const RG=[...Array(6)].map(()=>flatRing(0xffffff)); let rgI=0; const rg=()=>RG[rgI++];
const GS=[...Array(8)].map(()=>glowSprite(0xffffff,1,0)); let gsI=0; const gs=(col,size,o)=>{ const s=GS[gsI++]; s.material.color.set(col).multiplyScalar(GLOW.k); s.scale.set(size,size,1); s.material.opacity=o; s.visible=o>0.003; return s; };
function arc(l,c,r,a0,a1,axis='z',n=40){ const pts=[]; for(let i=0;i<=n;i++){ const a=lerp(a0,a1,i/n); pts.push(axis==='z'?new THREE.Vector3(c.x+Math.cos(a)*r,c.y+Math.sin(a)*r,c.z):new THREE.Vector3(c.x+Math.cos(a)*r,c.y,c.z+Math.sin(a)*r)); } setLine(l,pts); }
function bar3(l,p,len,dir=new THREE.Vector3(1,0,0)){ setLine(l,[p.clone(),p.clone().addScaledVector(dir,len)]); }

// ---- 档案灯箱：纸页（贴图），放大镜圈 ----
const TEXL=new THREE.TextureLoader(); const texP=[]; const ltex=f=>{ const t=TEXL.load('./assets/'+f); t.colorSpace=THREE.SRGBColorSpace; texP.push(new Promise(r=>{ const iv=setInterval(()=>{ if(t.image&&t.image.complete){ clearInterval(iv); r(); } },50); })); return t; };
const PAGES={p1893:ltex('1893.jpg'),fig5:ltex('head-fig5.jpg'),lac:ltex('lacoste.jpg'),alu:ltex('alu.jpg'),head1:ltex('head-sheet1.jpg')};
const pageG=new THREE.Group(); scene.add(pageG);
const page=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({map:PAGES.p1893,transparent:true,opacity:0,toneMapped:false,color:0xb8b4ac})); pageG.add(page);
const page2=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({map:PAGES.fig5,transparent:true,opacity:0,toneMapped:false,color:0xb8b4ac,depthWrite:false})); scene.add(page2);
const lightTable=new THREE.Mesh(new THREE.PlaneGeometry(26,16),new THREE.MeshBasicMaterial({color:0x223048,transparent:true,opacity:0,depthWrite:false})); lightTable.position.z=-0.05;   // depthWrite 关掉：透明度 0 的平面照样写深度，会把转过来的球拍挡掉半边（审片包里 54/123/212/218 s 的「半个拍框」） pageG.add(lightTable);
function showPage(p,tex,w,o){ p.material.map=tex; p.material.needsUpdate=true; const im=tex.image; const ar=im&&im.width?im.height/im.width:1.4; p.scale.set(w,w*ar,1); p.material.opacity=o; p.visible=o>0.003; }

// ---- 截面（拉科斯特双梁＋腹板；三腔铝型材；碳纤维管）：按专利附图的形状示意 ----
const secG=new THREE.Group(); scene.add(secG);
function extr(shape,d,mat){ const m=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:d,bevelEnabled:true,bevelThickness:0.02,bevelSize:0.02,bevelSegments:2,curveSegments:24}),mat); m.geometry.center(); return m; }
const circ=(x,y,r,hole=false)=>{ const s=hole?new THREE.Path():new THREE.Shape(); s.absarc(x,y,r,0,Math.PI*2,hole); return s; };
const steelM=MATS.steel(), aluM=MATS.alu();
const beadT=(()=>{ const s=circ(0,0.55,0.32); s.holes.push(circ(0,0.55,0.2,true)); return extr(s,2.4,steelM); })();
const beadB=(()=>{ const s=circ(0,-0.55,0.32); s.holes.push(circ(0,-0.55,0.2,true)); return extr(s,2.4,steelM); })();
const web=extr((()=>{ const s=new THREE.Shape(); s.moveTo(-0.06,-0.5); s.lineTo(0.06,-0.5); s.lineTo(0.06,0.5); s.lineTo(-0.06,0.5); s.closePath(); return s; })(),2.4,steelM);
beadT.position.y=0.55; beadB.position.y=-0.55; [beadT,beadB,web].forEach(m=>secG.add(m));
const holePlate=(()=>{ const sh=new THREE.Shape(); sh.moveTo(-4.5,-1.4); sh.lineTo(4.5,-1.4); sh.lineTo(4.5,1.4); sh.lineTo(-4.5,1.4); sh.closePath(); sh.holes.push(circ(0,0,0.34,true));
  const m=new THREE.Mesh(new THREE.ExtrudeGeometry(sh,{depth:0.55,bevelEnabled:false,curveSegments:64}),MATS.steel()); m.geometry.translate(0,0,-0.275); m.visible=false; scene.add(m); return m; })();
const aluSec=(()=>{ const s=new THREE.Shape(); s.absellipse(0,0,0.5,1.05,0,Math.PI*2); [-0.62,0,0.62].forEach(y=>{ const h=new THREE.Path(); h.absellipse(0,y,0.34,0.24,0,Math.PI*2,true); s.holes.push(h); }); return extr(s,2.4,aluM); })(); secG.add(aluSec);
const aluCells=[-0.62,0,0.62].map(y=>{ const m=new THREE.Mesh(new THREE.CylinderGeometry(0.3,0.3,2.3,24),new THREE.MeshBasicMaterial({color:0x4fe3ff,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false})); m.rotation.x=Math.PI/2; m.scale.set(1.1,1,0.78); m.position.y=y; secG.add(m); return m; });
// 碳纤维管：外层纤维壳＋泡沫芯（US 4,061,520 的做法，示意）
const tubeG=new THREE.Group(); scene.add(tubeG);
const shell=new THREE.Mesh(new THREE.CylinderGeometry(1,1,6,64,1,true),MATS.carbon()); shell.material.side=THREE.DoubleSide; tubeG.add(shell);
const foam=cloud(2600,0.09,6,tubeG); { for(let i=0;i<2600;i++){ const r=Math.sqrt(frnd())*0.88, a=frnd()*6.283, y=(frnd()-0.5)*6; cset(foam,i,Math.cos(a)*r,y,Math.sin(a)*r,0.55,0.62,0.7,0.8); } cdone(foam); }
const fibers=[]; for(let k=0;k<3;k++) for(let j=0;j<10;j++){ const l=fatLine(k===1?0x8fb8ff:0xb9c6dd,1.6); const pts=[]; const ang=(k-1)*0.7, r=1.0+k*0.04;
  for(let i=0;i<=60;i++){ const y=-3+6*i/60, a=j/10*6.283+Math.tan(ang)*y/r; pts.push(new THREE.Vector3(Math.cos(a)*r,y,Math.sin(a)*r)); } setLine(l,pts); scene.remove(l); tubeG.add(l); fibers.push(l); }

// ---- 球场（俯视轨迹用） ----
// courtG 沿用底座

// ---- 天平（模拟 vs 实测；碳纤维 vs 钢） ----
const balG=new THREE.Group(); scene.add(balG);
const balMat=new THREE.MeshPhysicalMaterial({color:0x9aa6b8,metalness:0.9,roughness:0.25,emissive:0x0a1220,emissiveIntensity:0.6,transparent:true});
const balPost=new THREE.Mesh(new THREE.CylinderGeometry(0.08,0.14,3.2,16),balMat); balPost.position.y=-1.6; balG.add(balPost);
const balBeam=new THREE.Group(); balG.add(balBeam); balBeam.add(new THREE.Mesh(new THREE.BoxGeometry(6,0.08,0.12),balMat));
const pans=[-1,1].map(s=>{ const p=new THREE.Group(); p.position.x=s*3; balBeam.add(p); const d=new THREE.Mesh(new THREE.CylinderGeometry(0.9,0.75,0.08,40),balMat); d.position.y=-1.2; p.add(d);
  const st=new THREE.Mesh(new THREE.CylinderGeometry(0.01,0.01,1.2,6),balMat); st.position.y=-0.6; p.add(st); return p; });
const steelBar=new THREE.Mesh(new THREE.BoxGeometry(1.2,0.18,0.18),MATS.steel()); pans[0].add(steelBar); steelBar.position.y=-1.05;
const fibBundle=new THREE.Mesh(new THREE.CylinderGeometry(0.22,0.22,1.2,24),MATS.carbon()); fibBundle.rotation.z=Math.PI/2; pans[1].add(fibBundle); fibBundle.position.y=-0.95;

// ---- 实物数据：发光片堆 ----
const stackG=new THREE.Group(); scene.add(stackG);
const plateMat=c=>new THREE.MeshPhysicalMaterial({color:c,emissive:c,emissiveIntensity:GLOW.emissive,metalness:0.3,roughness:0.3,clearcoat:1,transparent:true});
const swPl=[...Array(10)].map((_,i)=>{ const m=new THREE.Mesh(new THREE.BoxGeometry(1.6,0.16,1.6),plateMat(0xffc24a)); m.position.set(-1.6,0.1+i*0.2,0); stackG.add(m); return m; });
const spStack=new THREE.Mesh(new THREE.BoxGeometry(1.6,1,1.6),plateMat(0x4fe3ff)); stackG.add(spStack);
const spSliver=new THREE.Mesh(new THREE.BoxGeometry(1.6,1,1.6),plateMat(0xffffff)); stackG.add(spSliver);

// ---- 拼图三块（线／拍／球） ----
const pzG=new THREE.Group(); scene.add(pzG);
const pz=[0xb9c8ff,0xffc24a,0x34f5a8].map((c,i)=>{ const m=new THREE.Mesh(new THREE.BoxGeometry(2.2,2.2,0.35),plateMat(c)); m.position.x=(i-1)*2.25; pzG.add(m); return m; });

// ---- 粒子拼字 / 散开 ----
const pt=cloud(1600,0.05,8,scene,0.5); const PTS=[...Array(1600)].map(()=>[(frnd()-0.5)*16,(frnd()-0.5)*9,(frnd()-0.5)*8,frnd(),frnd()]);
function particles(k,cx,cy,cz,w,h,col,o=1){ // k:0 散在空中 → 1 汇成 w×h 的字块
  const cc=new THREE.Color(col); for(let i=0;i<1600;i++){ const p=PTS[i]; const tx_=cx+(p[3]-0.5)*w, ty=cy+(p[4]-0.5)*h; const e=ss(0,1,k*(1+p[3]*0.4)-p[3]*0.2);
    cset(pt,i,lerp(cx+p[0],tx_,e),lerp(cy+p[1],ty,e),lerp(cz+p[2],cz,e),cc.r,cc.g,cc.b,o*(1-0.75*e)); } cdone(pt); }

// ---- 扫描光带（HUD） ----
const scanBand=new THREE.Mesh(new THREE.PlaneGeometry(1,0.12),new THREE.MeshBasicMaterial({color:new THREE.Color(0x4fe3ff).multiplyScalar(GLOW.k),transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false})); scene.add(scanBand);
// 面积填充（新旧拍面之间多出来的一圈）
const fillRing=new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape()),new THREE.MeshBasicMaterial({color:new THREE.Color(0xffc24a).multiplyScalar(GLOW.k),transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide})); scene.add(fillRing);
function setFill(c0,a0,b0,c1,a1,b1){ const s=new THREE.Shape(); s.absellipse(0,c1,b1,a1,0,Math.PI*2); const h=new THREE.Path(); h.absellipse(0,c0,b0,a0,0,Math.PI*2,true); s.holes.push(h); fillRing.geometry.dispose(); fillRing.geometry=new THREE.ShapeGeometry(s,96); }
// 等高线热区（专利 FIG.5 的样子：一圈圈）
const iso=[...Array(4)].map(()=>fatLine(0xffc24a,3));

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

function hideAll(){
  courtG.visible=false; ALLRK.forEach(R=>{ R.g.position.set(0,0,0); R.g.rotation.set(0,0,0); R.g.scale.setScalar(1); rkOp(R,0); R.frame.material.emissive&&R.frame.material.emissive.set(R.kind==='wood'?0x2a1406:0x0a1420); });
  for(const b of [ball,ball2,ball3]){ b.m.visible=false; b.gl.visible=false; b.m.scale.set(1,1,1); }
  LN.forEach(l=>{ l.material.opacity=0; l.material.dashed=false; }); lnI=0; RG.forEach(r=>r.material.opacity=0); rgI=0; GS.forEach(s=>{ s.material.opacity=0; s.visible=false; }); gsI=0;
  for(const k in TT) op(TT[k],0); for(const k in TB) TB[k].g.visible=false; for(const k in text3D) t3op(text3D[k],0); chide(pt);
  page.visible=false; page2.visible=false; page.material.opacity=0; page2.material.opacity=0; lightTable.material.opacity=0; pageG.position.set(0,0,0); pageG.rotation.set(0,0,0);
  holePlate.visible=false; secG.visible=false; [beadT,beadB,web].forEach(m=>{ m.visible=false; m.position.x=0; }); aluSec.visible=false; aluCells.forEach(c=>c.material.opacity=0);
  tubeG.visible=false; balG.visible=false; steelBar.visible=fibBundle.visible=true; stackG.visible=false; pzG.visible=false; scanBand.material.opacity=0; fillRing.material.opacity=0;
  beamMat.uniforms.uOp.value=0; rimL.intensity=0; rimR.intensity=0; DOF.on=false; MOTE_SPEED=1; SLOW=null; }

// 偏心击球后的扭转（绕拍子长轴，阻尼振荡），k：击球后的秒数
const twistAng=(k,amp)=>k<0?0:amp*Math.sin(Math.min(k*9,Math.PI/2))*Math.exp(-Math.max(0,k-0.17)*1.4);

// ---------- 1 钩子 ----------
function shotHook(u,D){
  const HIT=ev('hit',0.3), FLY=ev('fly',5.8), ROW=ev('row',9.5), QQ=ev('q',13.7);
  if(u<ROW-0.3){ // 子弹时间：球打在拍面边缘，拍子绕长轴扭转，球照原方向飞
    SLOW=[FLY,FLY+1.6];   // 运动模糊只开在恢复常速、球高速飞出那 1.6 s（慢放里球走得慢，开了只是白花 6 倍渲染）
    const R=rkA; rkOp(R,1); R.g.position.set(0,0,0); const s=(u-HIT-0.6)*0.18+(u>FLY?(u-FLY)*0.9:0);   // 慢放时间：0.18 倍速，第二句开口后回到常速
    const tw=twistAng(s-0.5,0.32); R.g.rotation.set(0,tw,0);
    const hitP=new THREE.Vector3(R.b*0.82,R.cy+0.15,0);
    let bp; if(s<0.5){ bp=new THREE.Vector3(hitP.x,hitP.y,lerp(9,0.33,ss(0,0.5,s))); } else bp=new THREE.Vector3(hitP.x+(s-0.5)*0.12,hitP.y,0.33+(s-0.5)*14);
    showB(ball,bp,true,1-ss(FLY+1.5,FLY+2.2,u));
    if(s>0.5){ const l=ln(0xffc24a,5); setLine(l,[hitP.clone().setZ(0.35),bp]); l.material.opacity=0.85*(1-ss(FLY+1.5,FLY+2.4,u));
      const l2=ln(0x4fe3ff,2,true); setLine(l2,[hitP.clone().setZ(0.35),hitP.clone().setZ(9)]); l2.material.opacity=0.5*ss(FLY,FLY+0.6,u)*(1-ss(FLY+1.5,FLY+2.4,u)); }
    // 扭转量规：拍子下方一段弧，跟着扭
    const gl=ln(0xffffff,3); arc(gl,new THREE.Vector3(0,R.gripY,0),0.9,Math.PI/2,Math.PI/2+tw*2.2,'y'); gl.material.opacity=0.8*ss(0.45,0.6,s)*(1-ss(FLY+1.5,FLY+2.2,u));
    const ax=ln(0x4fe3ff,2,true); setLine(ax,[new THREE.Vector3(0,R.cy+R.a+0.6,0),new THREE.Vector3(0,R.gripY-1.2,0)]); ax.material.opacity=0.6*ss(0.4,0.6,s)*(1-ss(FLY+1.5,FLY+2.2,u));
    const lab=tx('hkExp',T('一次实验（Cross 2010）· 画面为示意','One experiment (Cross 2010) · schematic'),{color:'#cfe8ff',size:0.32}); hud(lab,3.6,-2.6); op(lab,ss(FLY,FLY+0.6,u)*(1-ss(FLY+1.5,FLY+2.2,u)));
    look(lerp(2.6,4.2,ss(0,FLY,u)),lerp(0.6,1.4,ss(0,FLY,u)),lerp(4.2,6.5,ss(0,FLY+2,u)),0.6,R.cy,lerp(0,1.5,ss(FLY,FLY+2,u)));
    rimL.intensity=4; rimR.intensity=4; rimL.position.set(-3,2,3); rimR.position.set(4,3,3); DOF.on=true; DOF.focus=camera.position.distanceTo(new THREE.Vector3(0.6,R.cy,0)); DOF.ap=0.00008;
    proj('hit',hitP); return; }
  // 一排五支拍：木 → 钢 → 铝 → 大拍面 → 碳纤维，依次亮起、逐支变大
  const row=[rkW,rkS,rkAl,rkB,rkC]; const v=u-ROW;
  row.forEach((R,i)=>{ const k=ss(i*0.45,i*0.45+0.6,v); rkOp(R,k); R.g.position.set((i-2)*2.9,0,-i*0.2); R.g.rotation.y=Math.sin(v*0.4+i)*0.15; });
  const yrs=[T('木','Wood'),T('钢','Steel'),T('铝','Aluminium'),T('大拍面','Oversize'),T('碳纤维','Graphite')];
  row.forEach((R,i)=>{ const s=tx('row'+i,yrs[i],{color:'#ffffff',size:0.42,glow:CYAN}); s.position.set((i-2)*2.9,R.gripY-1.0,0.3); op(s,ss(i*0.45+0.2,i*0.45+0.8,v)*(1-ss(QQ-ROW-0.3,QQ-ROW,v))); });
  const qk=ss(QQ-ROW-0.6,QQ-ROW+0.5,v); particles(qk,0,2.6,1,7,1.3,0xffc24a,qk>0?1-ss(QQ-ROW+0.8,QQ-ROW+1.4,v):0);
  const q=bt('hookQ',T('是球拍，改写了网球吗？','Did the racket change tennis?'),{size:1.0,glow:GOLD,accent:T('球拍','racket'),fx:'shock'}); hud(q,0,2.15); q.update(v,QQ-ROW+0.3);   /* 冲击：钩子是一记击球 */
  look(lerp(-3,3,ss(0,QQ-ROW,v)),0.4,lerp(13,11.5,ss(0,D-ROW,v)),0,0.3,0); beamMat.uniforms.uOp.value=0.1; rimL.intensity=4; rimR.intensity=4; rimL.position.set(-6,3,4); rimR.position.set(6,3,4);
}

// ---------- 2 木拍一百年 ----------
function shotWood(u,D){
  const LT=ev('lt',0.5), BE=ev('bend',2.8), YR=ev('years',6.5), SC=ev('scan',12.3), CR=ev('crack',17.6);
  if(u<YR-0.3){ // 灯箱：1893 年插图；一条木条从图里弯出来，绕成拍框
    showPage(page,PAGES.p1893,4.2,ss(LT,LT+0.6,u)); page.position.set(-3.2,0,0); lightTable.material.opacity=0.55*ss(LT,LT+0.6,u);
    const cap=tx('p1893',T('1893 年的网球书插图（公有领域）','Illustration from an 1893 tennis book (public domain)'),{color:'#ffe9c8',size:0.34,plate:true}); cap.position.set(-3.2,-3.85,0.2); op(cap,ss(LT+0.4,LT+1,u));
    const lens=rg(); lens.material.color.set(0xffffff).multiplyScalar(GLOW.k); lens.rotation.set(0,0,0); lens.position.set(-3.95,-0.95,0.2); lens.scale.setScalar(1.7); lens.material.opacity=0.8*ss(LT+0.5,LT+1,u)*(1-ss(BE+1.5,BE+2,u));
    // 木条：从直条弯成椭圆
    const k=ss(BE,BE+2.4,u), R=rkW; const pts=[]; const n=60;
    for(let i=0;i<=n;i++){ const f=i/n; const a=-Math.PI/2+f*2*Math.PI*k; const ex=Math.cos(a)*R.b, ey=Math.sin(a)*R.a; const sx=lerp(-3.4,3.4,f), sy=-R.a;
      pts.push(new THREE.Vector3(lerp(sx,ex,k)+2.6,lerp(sy,ey,k),0)); }
    const wl=ln(0xd7a35f,9); setLine(wl,pts); wl.material.opacity=ss(BE-0.3,BE+0.2,u)*(1-ss(YR-1.2,YR-0.5,u));
    R.g.position.set(2.6,-R.cy,0); rkOp(R,ss(BE+2.0,BE+2.9,u)); R.strings.material.opacity=0.7*ss(BE+2.6,BE+3.4,u);
    look(0,0.2,10.5,0,0,0); return; }
  if(u<SC-0.4){ // 年代光轨：1880 → 1970 刻度飞过，拍子外形一直不变（重影叠成一摞）
    const v=u-YR, R=rkW; rkOp(R,1); R.g.position.set(0,-R.cy,0); R.g.rotation.y=Math.sin(v*0.5)*0.2;
    ghosts.forEach((G,i)=>{ rkOp(G,0.22*ss(0.3+i*0.3,0.8+i*0.3,v)); G.g.position.set(0,-G.cy,-1.2*(i+1)); G.g.rotation.y=R.g.rotation.y; });
    const YRS=[1880,1900,1920,1940,1960,1970]; YRS.forEach((y,i)=>{ const s=tx('y'+y,String(y),{color:'#ffe2a0',size:0.55,glow:GOLD}); s.userData.free=true; const z=lerp(-30,6,ss(0,SC-YR,v-i*0.35)); s.position.set(-3.6,1.8,z); op(s,ss(-30,-24,z)*(1-ss(3,6,z))); });
    const rail=ln(0xffc24a,2); setLine(rail,[new THREE.Vector3(-3.6,1.5,-30),new THREE.Vector3(-3.6,1.5,6)]); rail.material.opacity=0.5;
    look(4.5,1.2,7.5,0,0.3,-1); return; }
  // 规格扫描 → 试着变大、框上爬红光、缩回
  const v=u-SC, R=rkW; rkOp(R,1); R.g.position.set(0,-R.cy,0);
  const grow=u>CR-0.5?Math.sin(Math.PI*ss(CR-0.5,CR+1.6,u))*0.12:0; setRk(R,WOOD.a*(1+grow),WOOD.b*(1+grow)); R.g.position.set(0,-R.cy,0);
  const sb=ss(0,1.6,v); scanBand.position.set(0,lerp(R.a+0.3,-R.a-0.3,sb),0.15); scanBand.scale.set(R.b*2.4,1,1); scanBand.material.opacity=0.8*Math.sin(Math.PI*sb);
  const corners=[[-1,1],[1,1],[-1,-1],[1,-1]]; const shrink=lerp(1.5,1.08,ss(0.3,1.4,v));
  corners.forEach(([sx,sy])=>{ const l=ln(0x4fe3ff,3); const cx=sx*R.b*shrink, cy=sy*R.a*shrink; setLine(l,[new THREE.Vector3(cx-sx*0.4,cy,0.1),new THREE.Vector3(cx,cy,0.1),new THREE.Vector3(cx,cy-sy*0.4,0.1)]); l.material.opacity=0.9*ss(0.2,0.6,v)*(1-ss(CR-SC-0.6,CR-SC,v)); });
  const rd=tx('rd70',T('拍面 约 70 平方英寸','Strung area ≈ 70 sq in'),{color:'#ffffff',size:0.6,glow:CYAN}); rd.position.set(R.b+2.6,0.6,0.2); op(rd,ss(1.0,1.6,v));
  const rs=tx('rd70s',T('Head 专利 · 名人堂 · Taraborrelli 2019','Head patent · Tennis Hall of Fame · Taraborrelli 2019'),{color:'#cfe8ff',size:0.28}); rs.position.set(R.b+2.6,0.05,0.2); op(rs,ss(1.4,2,v));
  const crk=ss(CR-0.2,CR+0.6,u)*(1-ss(CR+1.4,CR+2.2,u)); R.frame.material.emissive.set(0x2a1406).lerp(C(0xff2a10),crk*0.8);
  if(crk>0){ const s=gs(0xff5a3a,1.2,0.6*crk); s.position.set(R.b*0.7,R.a*0.75,0.1); const s2=gs(0xff5a3a,1.0,0.5*crk); s2.position.set(-R.b*0.85,-R.a*0.4,0.1); }
  const cm=tx('compro',T('尺寸 = 木头为了耐用做的妥协（国际网联）','Size = a compromise for durability (ITF)'),{color:'#ffd9c8',size:0.46,glow:RED}); cm.position.set(0,-R.a-1.0,0.3); op(cm,0);   // 字幕 w3 已经照国际网联原句讲了，3D 里不再重复一遍
  look(lerp(0.8,1.6,ss(0,D-SC,v)),0.5,7.6,0.9,0,0); }

// ---------- 3 金属拍 ----------
function shotMetal(u,D){
  const HO=ev('hole',3.9), PA=ev('patent',7.3), LF=ev('lift',11.2), JO=ev('join',14.7), AL=ev('alu',21.8), SA=ev('same',25.7);
  if(u<PA-0.3){ // 孔口特写：钢框上打的穿线孔（看得见板厚），绷紧的线从孔里穿过、压在孔边上，孔边一圈闪红
    holePlate.visible=true; holePlate.material.opacity=ss(0,0.5,u); holePlate.rotation.set(0,0,0);
    const tens=ss(0.6,2.4,u), sag=lerp(1.1,0.0,tens);   // 线被拉紧：两头从斜着变成笔直，压在孔的上沿
    const st=ln(0xf2f6ff,7); setLine(st,[new THREE.Vector3(0,0.3+sag,-4.5),new THREE.Vector3(0,0.3,-0.28),new THREE.Vector3(0,0.3,0.28),new THREE.Vector3(0,0.3+sag*0.6,4.5)]); st.material.opacity=ss(0.3,0.8,u);
    const hot=ss(HO,HO+0.4,u)*(0.65+0.35*Math.sin(u*12));
    const ring=rg(); ring.material.color.set(0xff3a28).multiplyScalar(GLOW.k); ring.rotation.set(0,0,0); ring.position.set(0,0,0.29); ring.scale.setScalar(0.95); ring.material.opacity=0.85*hot;
    const r1=gs(0xff3a28,0.7,0.6*hot); r1.position.set(0,0.33,0.3); const r2=gs(0xff3a28,0.7,0.6*hot); r2.position.set(0,0.33,-0.3);
    const lb=tx('sharp',T('孔边太锋利，和绷紧的线合不来（国际网联）','Sharp hole edges vs tensioned strings (ITF)'),{color:'#ffd9c8',size:0.36,glow:RED}); lb.position.set(0,-1.0,0.5); op(lb,ss(HO+0.3,HO+1,u));
    const sch=tx('holeS',T('示意','Schematic'),{color:'#cfe8ff',size:0.24}); hud(sch,4.2,2.3); op(sch,ss(0.5,1,u));
    look(lerp(3.4,2.2,ss(0,PA,u)),lerp(1.6,1.1,ss(0,PA,u)),lerp(4.4,3.6,ss(0,PA,u)),0,0.1,0); proj('hole',new THREE.Vector3(0,0,0.3)); return; }
  if(u<JO-0.3){ // 专利原件滑入 → 截面从纸面浮起 → 沿轴拆开
    const v=u-PA; showPage(page,PAGES.lac,5.2,ss(0,0.6,v)*(1-ss(LF-PA+1.2,LF-PA+2.2,v)*0.7)); page.position.set(-3.5,0,0); lightTable.material.opacity=0.5*ss(0,0.6,v);
    const pc=tx('pLac',T('美国专利 US 3,086,777 · 拉科斯特 · 1963 年授权','US Patent 3,086,777 · Lacoste · granted 1963'),{color:'#ffe9c8',size:0.34,plate:true}); pc.position.set(-3.5,-4.0,0.2); op(pc,ss(0.4,1,v));
    secG.visible=true; [beadT,beadB,web].forEach(m=>m.visible=true); web.scale.set(1,1,1); const lift=ss(LF-PA-0.4,LF-PA+1.2,v), sep=ss(LF-PA+1.4,LF-PA+2.6,v);
    secG.position.set(lerp(-3.5,2.6,lift),lerp(0.5,0.2,lift),lerp(0.1,1.2,lift)); secG.rotation.set(lerp(0,0.4,lift),lerp(0,-0.7,lift)+v*0.05,0); secG.scale.setScalar(lerp(0.5,1.3,lift));
    [beadT,beadB,web].forEach(m=>{ m.material.opacity=ss(LF-PA-0.5,LF-PA,v); }); beadT.position.y=0.55+sep*0.7; beadB.position.y=-0.55-sep*0.7;
    const l1=tx('beam',T('两道梁','Two beads'),{color:'#ffffff',size:0.42,glow:CYAN}); l1.position.set(5.4,1.9,1.4); op(l1,sep); const l2=tx('webT',T('中间一层薄壁','A web between'),{color:'#ffffff',size:0.42,glow:CYAN}); l2.position.set(5.4,0.2,1.4); op(l2,sep);
    const sm=tx('schem1',T('截面：照专利附图示意','Section: schematic after the patent drawing'),{color:'#cfe8ff',size:0.28}); sm.position.set(2.6,-2.2,1.4); op(sm,lift);
    look(0,0.6,10,0,0.2,0); proj('section',secG.position); return; }
  if(u<AL-0.3){ // 合拢成一支钢拍，框边一圈亮起
    const v=u-JO, R=rkS; rkOp(R,ss(0,0.8,v)); R.g.position.set(0,-R.cy,0); R.g.rotation.y=-0.6+v*0.12;
    const hl=ss(0.8,1.6,v); R.frame.material.emissive.set(0x0e1420).lerp(C(0x4fe3ff),0.35*hl*(0.6+0.4*Math.sin(v*3)));
    const t2=tx('t2000',T('授权给威尔逊 → T2000 · 康纳斯用了很多年','Licensed to Wilson → T2000 · Connors used it for years'),{color:'#ffffff',size:0.48,glow:CYAN}); t2.position.set(0,-R.a-1.1,0.4); op(t2,ss(1,1.6,v));
    const ts=tx('t2000s',T('国际网联 · 国际网球名人堂','ITF · International Tennis Hall of Fame'),{color:'#cfe8ff',size:0.28}); ts.position.set(0,-R.a-1.65,0.4); op(ts,ss(1.4,2,v));
    look(lerp(3,1.5,ss(0,AL-JO,v)),0.8,7.4,0,0,0); return; }
  if(u<SA-0.3){ // 截面变成三腔铝型材，三格依次亮
    const v=u-AL; secG.visible=true; secG.position.set(0,0,0); secG.rotation.set(0.35,-0.6+v*0.08,0); secG.scale.setScalar(1.6); aluSec.visible=true; aluSec.material.opacity=ss(0,0.6,v);
    aluCells.forEach((c,i)=>{ c.material.opacity=0.35*ss(0.6+i*0.4,1.0+i*0.4,v); });
    showPage(page2,PAGES.alu,4.2,0.75*ss(0.2,0.8,v)); page2.position.set(-4.6,0,-1);
    const ac=tx('pAlu',T('挤压三腔铝框 · 美国专利 US 3,752,478（1973）','Extruded tri-hollow aluminium · US 3,752,478 (1973)'),{color:'#ffe9c8',size:0.34,plate:true}); ac.position.set(-4.6,-3.3,0); op(ac,ss(0.5,1.1,v));
    look(1.2,0.8,8,-0.4,0,0); return; }
  // 金属拍和木拍叠在一起：拍面轮廓完全重合
  const v=u-SA; rkOp(rkW,0.55); rkOp(rkS,0.9); rkW.g.position.set(0,-rkW.cy,0); rkS.g.position.set(0,-rkS.cy,0.15);
  const ol=ln(0x4fe3ff,3); const pts=new THREE.EllipseCurve(0,0,WOOD.b,WOOD.a,0,Math.PI*2).getPoints(100).map(p=>new THREE.Vector3(p.x,p.y,0.3)); setLine(ol,pts); ol.material.opacity=0.8*ss(0.3,0.8,v);
  const sm=tx('same',T('拍面：还是约 70 平方英寸','Strung area: still ≈ 70 sq in'),{color:'#ffffff',size:0.55,glow:CYAN}); sm.position.set(WOOD.b+2.4,0.4,0.3); op(sm,ss(0.4,1,v));
  look(0.6,0.3,7.6,0.6,0,0); }

// ---------- 4 大拍面 ----------
function shotOversize(u,D){
  const PA=ev('patent',0.5), CO=ev('cop',6.1), HI=ev('hits',11.1), ST=ev('stretch',16.9), AR=ev('area',22.1);
  if(u<CO-0.4){ showPage(page,PAGES.head1,5.4,ss(PA,PA+0.6,u)); page.position.set(-2.4,0,0); lightTable.material.opacity=0.5*ss(PA,PA+0.6,u);
    const pc=tx('pHead',T('美国专利 US 3,999,756 · 霍华德·黑德 · 1976-12-28 授权','US Patent 3,999,756 · Howard Head · granted 28 Dec 1976'),{color:'#ffe9c8',size:0.36,plate:true}); pc.position.set(-2.4,-4.2,0.2); op(pc,ss(PA+0.4,PA+1,u));
    const st=rg(); st.material.color.set(0xffc24a).multiplyScalar(GLOW.k); st.rotation.set(0,0,0); st.position.set(-0.6,3.3,0.2); st.scale.setScalar(lerp(3,1.3,ss(PA+1.2,PA+1.6,u))); st.material.opacity=0.9*ss(PA+1.2,PA+1.5,u);
    look(0,0.2,lerp(11,9.5,ss(0,CO,u)),-1.2,0,0); return; }
  const R=rkW; rkOp(R,1); const v=u-CO;
  // 拍面往手柄方向拉长（顶端固定），留几道残影
  const sk=ss(ST-CO,ST-CO+3.2,v); const a=lerp(WOOD.a,BIG.a,sk), b=lerp(WOOD.b,BIG.b,sk); setRk(R,a,b); R.g.position.set(0,0,0);
  ghosts.forEach((G,i)=>{ const kk=ss(ST-CO+i*0.7,ST-CO+i*0.7+0.4,v)*(1-ss(ST-CO+3.4,ST-CO+4,v)); setRk(G,lerp(WOOD.a,BIG.a,i/3),lerp(WOOD.b,BIG.b,i/3)); rkOp(G,0.18*kk); });
  // 打击中心（不震手的那个点）：旧拍靠近拍喉 → 世界坐标固定；拉长后落进拍面中央
  const copY=WOOD.a-WOOD.a*2*0.82; const cop=new THREE.Vector3(0,copY,0.12);
  const cg=gs(0xff5a7a,0.9,0.85*ss(0.2,0.6,v)); cg.position.copy(cop); const cr=rg(); cr.material.color.set(0xff5a7a).multiplyScalar(GLOW.k); cr.rotation.set(0,0,0); cr.position.copy(cop); cr.scale.setScalar(0.6+0.08*Math.sin(v*5)); cr.material.opacity=0.8*ss(0.2,0.6,v);
  const ct=tx('cop',T('不震手的那个点（打击中心）','The no-jar point (centre of percussion)'),{color:'#ffd0dc',size:0.42,glow:RED}); ct.position.set(-3.2,copY-0.2,0.2); op(ct,ss(0.3,0.9,v)*(1-ss(ST-CO+3.5,ST-CO+4,v)));
  const gl=ln(0xff5a7a,2,true); setLine(gl,[cop,new THREE.Vector3(-1.9,copY-0.2,0.15)]); gl.material.opacity=0.6*ss(0.3,0.9,v)*(1-ss(ST-CO+3.5,ST-CO+4,v));
  // 一串击球点落在拍面正中
  const hk=ss(HI-CO,HI-CO+1.6,v); if(hk>0){ for(let i=0;i<40;i++){ const g=gauss()*0.18, h=gauss()*0.22, f=ss(i/40,i/40+0.1,hk); cset(pt,i,g,WOOD.a-WOOD.a+h*0.9,0.14,1,0.85,0.4,f*(1-ss(ST-CO+3,ST-CO+3.6,v))); } for(let i=40;i<1600;i++) cset(pt,i,0,0,0,0,0,0,0); cdone(pt); }
  const dl=ln(0xffffff,2,true); setLine(dl,[new THREE.Vector3(0.35,0,0.14),new THREE.Vector3(0.35,copY,0.14)]); dl.material.opacity=0.7*ss(HI-CO+1,HI-CO+1.6,v)*(1-ss(ST-CO+0.5,ST-CO+1.5,v));
  const ht=tx('hits',T('大多数人打在这里','Most players hit here'),{color:'#fff1c8',size:0.42,glow:GOLD}); ht.position.set(2.9,0.2,0.2); op(ht,ss(HI-CO+0.4,HI-CO+1,v)*(1-ss(ST-CO+3,ST-CO+3.6,v)));
  // 专利 FIG.5 线稿浮起比对
  showPage(page2,PAGES.fig5,3.6,0.7*ss(ST-CO+1.2,ST-CO+2.2,v)); page2.position.set(4.6,-0.6,-0.4);
  const fc=tx('fig5',T('专利附图 FIG.5：大拍面（左）vs 旧式拍（右）','Patent FIG.5: oversize (left) vs prior art (right)'),{color:'#ffe9c8',size:0.3,plate:true}); fc.position.set(4.6,-3.6,0); op(fc,ss(ST-CO+1.6,ST-CO+2.4,v));
  // 面积：多出来的一圈填亮
  const ak=ss(AR-CO,AR-CO+0.8,v); if(ak>0){ setFill(WOOD.a-WOOD.a,WOOD.a,WOOD.b,R.cy,R.a,R.b); fillRing.position.set(0,0,0.11); fillRing.material.opacity=0.35*ak; }
  const ol=ln(0xffffff,2,true); setLine(ol,new THREE.EllipseCurve(0,0,WOOD.b,WOOD.a,0,Math.PI*2).getPoints(100).map(p=>new THREE.Vector3(p.x,p.y,0.13))); ol.material.opacity=0.6*ss(ST-CO+0.5,ST-CO+1.2,v);
  const ar=bt('area',T('拍面 大了 40% 以上','Strung area: 40%+ larger'),{size:0.6,glow:GOLD,accent:'40%',fx:'shock'}); hud(ar,-3.7,1.75); ar.update(v,AR-CO);   /* 冲击：面积一下子撑大 */
  const as=tx('areas',T('《Harvard Crimson》1981 · Inside Tennis','Harvard Crimson 1981 · Inside Tennis'),{color:'#cfe8ff',size:0.28}); as.position.set(-3.6,0.6,0.3); op(as,ak);
  look(lerp(0.4,0.9,ss(0,D-CO,v)),0.2,lerp(9.2,9.8,ss(ST-CO,D-CO,v)),0.6,-0.4,0); proj('cop',cop); }

// ---------- 5 甜点有三个 ----------
const P3=[[0.0,'#ffc24a',T('回弹最快的点','Max rebound')],[0.35,'#4fe3ff',T('振动节点','Vibration node')],[-0.55,'#ff6a8a',T('打击中心','Centre of percussion')]];   // 拍面上的高度占 a 的比例，示意
function shotSweet(u,D){
  const SP=ev('split',2.3), P1=ev('p1',4.5), P2=ev('p2',6.0), P3_=ev('p3',7.7), NO=ev('node',15.7), GR=ev('grip',17.6);
  const R=rkB; setRk(R,BIG.a,BIG.b); R.g.position.set(0,-R.cy,0); rkOp(R,1);
  if(u<SP+0.3){ const k=ss(0,SP,u); const s=bt('sweetW',T('「甜点」','"Sweet spot"'),{size:0.9,glow:GOLD,fx:'particles'}); hud(s,0,0); s.update(u,0.5,SP);   /* 粒子：聚成「甜点」，在 SP 散开、正好接上三颗光点分飞 */ look(0,0,7.5,0,0,0); return; }
  const v=u-SP;
  P3.forEach(([fy,col,lab],i)=>{ const p=new THREE.Vector3(0,fy*R.a,0.15); const k=ss(0.1+i*0.15,0.6+i*0.15,v); const from=new THREE.Vector3(0,0,0.4);
    const pos=from.clone().lerp(p,k); const dim=(u>NO&&i!==1)?0.25:1; const s=gs(col,0.9,0.9*k*dim); s.position.copy(pos);
    const t=tx('p3'+i,lab,{color:col,size:0.42,glow:'rgba(255,255,255,0.4)'}); t.position.set(i===1?3.1:-3.1,fy*R.a+0.1,0.2); op(t,ss(0.8,1.3,v)*dim); });
  // ① 回弹最快：一根速度条
  const p1k=ss(P1-SP,P1-SP+0.6,v)*(1-ss(P2-SP,P2-SP+0.3,v)*0.5); const b1=ln(0xffc24a,9); bar3(b1,new THREE.Vector3(R.b+0.4,0.0,0.2),2.2*p1k); b1.material.opacity=p1k;
  // ② 振动：拍框侧面弯曲驻波，节点处静止（示意）
  const p2k=ss(P2-SP,P2-SP+0.6,v); if(p2k>0){ const wl=ln(0x4fe3ff,4); const pts=[]; const top=R.a, bot=R.gripY-0.9; const amp=0.22*(u>NO?0.35:1);
    for(let i=0;i<=60;i++){ const s=i/60, y=lerp(top,bot,s); const mode=Math.cos(Math.PI*2*(s-0.5))*0.9+0.1; pts.push(new THREE.Vector3(-R.b-0.6+amp*Math.sin(u*14)*mode,y,0)); } setLine(wl,pts); wl.material.opacity=p2k*0.9;
    const nd=gs(0x4fe3ff,0.6,p2k*(u>NO?1:0.6)); nd.position.set(-R.b-0.6,0.35*R.a,0); }
  // ③ 打击中心：握把处受力箭头为零
  const p3k=ss(P3_-SP,P3_-SP+0.6,v); const fa=ln(0xff6a8a,6); bar3(fa,new THREE.Vector3(0.5,R.gripY,0.3),0.9*p3k*(0.15),new THREE.Vector3(1,0,0)); fa.material.opacity=p3k;
  const f0=tx('f0',T('握把受力 ≈ 0','Force at grip ≈ 0'),{color:'#ffd0dc',size:0.36}); f0.position.set(1.9,R.gripY,0.3); op(f0,p3k*(u<GR?1:0));
  // 节点最舒服；握在手里时打击中心没那么重要：两组相反的受力箭头
  const nk=ss(NO-SP,NO-SP+0.6,v); const nt=tx('nodeBest',T('手感最好的，通常是节点（Cross 2004）','The best-feeling spot is usually the node (Cross 2004)'),{color:'#ffffff',size:0.46,glow:CYAN}); nt.position.set(0,R.a+0.9,0.3); op(nt,nk*(1-ss(GR-SP,GR-SP+0.4,v)));
  const gk=ss(GR-SP,GR-SP+0.6,v); if(gk>0){ const up=ln(0xff6a8a,6), dn=ln(0xff6a8a,6); bar3(up,new THREE.Vector3(-0.5,R.gripY+0.4,0.3),0.8*gk,new THREE.Vector3(-1,0,0)); bar3(dn,new THREE.Vector3(0.5,R.gripY-0.4,0.3),0.8*gk,new THREE.Vector3(1,0,0)); up.material.opacity=dn.material.opacity=gk;
    const gt=tx('gripT',T('打击中心：手的上下两半受力相互抵消','At the COP: forces on upper and lower hand cancel'),{color:'#ffd0dc',size:0.38}); gt.position.set(0,R.gripY-1.2,0.3); op(gt,gk); }
  const sc=tx('sw3s',T('三个点的位置为示意','Point positions are schematic'),{color:'#cfe8ff',size:0.26}); sc.position.set(3.1,-R.a-0.4,0.2); op(sc,ss(0.8,1.3,v));
  look(lerp(0,-0.6,ss(0,D,u)),lerp(0.4,-0.4,ss(GR,GR+1,u)),lerp(9.5,10.5,ss(0,D,u)),0,lerp(0,-1.2,ss(GR,GR+1,u)),0); }

// ---------- 6 宽拍头防扭转 ----------
function shotTwist(u,D){
  const SPL=ev('split',0.5), HB=ev('hitboth',3.8), SPD=ev('speed',10.8), CT=ev('court',13.3), OUT=ev('out',20.7);
  if(u<CT-0.3){ SLOW=[SPD,SPD+1.5];   // 同上：只在提速飞出那段
    const L_=rkW2, Rb=rkB; setRk(L_,WOOD.a,WOOD.b); setRk(Rb,BIG.a,BIG.b); rkOp(L_,ss(SPL,SPL+0.6,u)); rkOp(Rb,ss(SPL,SPL+0.6,u));
    const s=(u-HB)*0.22+(u>SPD?(u-SPD)*0.6:0); const k=s-0.4;
    [[L_,-2.6,0.42,WOOD],[Rb,2.6,0.16,BIG]].forEach(([R,x,amp,dim],i)=>{ R.g.position.set(x,-R.cy,0); const tw=twistAng(k,amp); R.g.rotation.set(0,tw,0);
      const hp=new THREE.Vector3(x+dim.b*0.8,R.cy-R.cy,0); const b=i?ball2:ball; let bp; if(s<0.4) bp=new THREE.Vector3(hp.x,0,lerp(8,0.33,ss(-0.4,0.4,s))); else bp=new THREE.Vector3(hp.x,0,0.33+(s-0.4)*(i?13:9.5));
      showB(b,bp,u>HB-0.4,1-ss(3,5.5,bp.z));   // 飞向镜头的球淡出，别糊满半屏 const ax=ln(0x4fe3ff,2,true); setLine(ax,[new THREE.Vector3(x,dim.a+0.5,0),new THREE.Vector3(x,R.gripY-R.cy-1.2,0)]); ax.material.opacity=0.6*ss(HB-0.6,HB,u);
      const g=ln(0xffffff,3); arc(g,new THREE.Vector3(x,R.gripY-R.cy,0),0.85,Math.PI/2,Math.PI/2+tw*2.4,'y'); g.material.opacity=0.85*ss(HB+0.4,HB+0.8,u);
      // 出球速度条（偏心的那支明显短一截，示意）
      const sk=ss(SPD,SPD+0.7,u); const sb=ln(i?0x34f5a8:0xffc24a,10); bar3(sb,new THREE.Vector3(x-1.2,-dim.a-1.3,0.3),(i?2.4:1.75)*sk); sb.material.opacity=sk; });
    const t1=tx('narrow',T('窄拍头','Narrow head'),{color:'#ffe2a0',size:0.42}); t1.position.set(-2.6,WOOD.a+0.9,0); op(t1,ss(SPL+0.3,SPL+0.9,u));
    const t2=tx('wide',T('宽拍头','Wide head'),{color:'#c8fff0',size:0.42}); t2.position.set(2.6,WOOD.a+0.9,0); op(t2,ss(SPL+0.3,SPL+0.9,u));
    const t3=tx('axis',T('绕长轴转','Twist about the long axis'),{color:'#cfe8ff',size:0.36}); t3.position.set(0,2.7,0); op(t3,ss(HB-0.4,HB+0.2,u)*(1-ss(SPD-0.5,SPD,u)));
    const t4=tx('slower',T('打偏了：左右几乎不偏，球速明显变慢（Cross 2010 · Spurr 2017）','Off-centre: barely deflected sideways, clearly slower (Cross 2010 · Spurr 2017)'),{color:'#ffffff',size:0.44,glow:MINT}); t4.position.set(0,-BIG.a-2.0,0.3); op(t4,ss(SPD+0.3,SPD+1,u));
    look(0,lerp(0.3,-0.3,ss(SPD,SPD+1,u)),lerp(10.5,11.5,ss(0,CT,u)),0,lerp(0,-0.8,ss(SPD,SPD+1,u)),0); return; }
  // 俯视球场：中心击球落在场内，偏心的更高更远、落在底线外
  courtG.visible=true; courtG.userData.mat.opacity=1; const v=u-CT; const L2=23.77/2;
  const tr=(hgt,len,k)=>{ const pts=[]; for(let i=0;i<=40;i++){ const s=i/40*k; pts.push(new THREE.Vector3(lerp(-1.5,1.5,s)*0,0.9+Math.sin(Math.PI*s)*hgt,lerp(L2-0.5,L2-0.5-len,s))); } return pts; };
  const ka=ss(0.2,1.8,v), kb=ss(1.0,2.8,v); const a1=ln(0x34f5a8,5), a2=ln(0xffc24a,5);
  setLine(a1,tr(2.2,19.5,ka)); a1.material.opacity=ka>0?0.95:0; setLine(a2,tr(3.6,24.6,kb)); a2.material.opacity=kb>0?0.95:0;
  const r1=rg(); r1.material.color.set(0x34f5a8).multiplyScalar(GLOW.k); r1.position.set(0,0.02,L2-0.5-19.5); r1.scale.setScalar(1.4); r1.material.opacity=0.9*ss(1.8,2.1,v);
  const outF=ss(OUT-CT,OUT-CT+0.3,v)*(0.6+0.4*Math.sin(v*10)); const r2=rg(); r2.material.color.set(outF>0?0xff3a28:0xffc24a).multiplyScalar(GLOW.k); r2.position.set(0,0.02,L2-0.5-24.6); r2.scale.setScalar(1.4); r2.material.opacity=0.9*ss(2.8,3.1,v);
  const tc=tx('center',T('打在中间','Centre hit'),{color:'#c8fff0',size:0.5}); tc.position.set(-2.4,0.5,L2-0.5-19.5); op(tc,ss(1.8,2.3,v));
  const to=tx('offc',T('打偏了：飞得更高、更远','Off-centre: higher and longer'),{color:'#ffe2a0',size:0.5}); to.position.set(3.2,4.2,-6); op(to,ss(2.6,3.2,v));
  const ts=tx('spurr',T('模型：Spurr 2017（一千多次实测撞击）· 轨迹为示意','Model: Spurr 2017 (1,000+ measured impacts) · paths schematic'),{color:'#cfe8ff',size:0.3}); ts.position.set(0,6.4,-6); op(ts,ss(2.2,2.8,v));
  const ot=tx('outT',T('出界','Out'),{color:'#ffd0c8',size:0.6,glow:RED}); ot.position.set(1.6,0.6,L2-0.5-24.6); op(ot,outF>0?1:0);
  look(lerp(14,12,ss(0,D-CT,v)),lerp(9,8,ss(0,D-CT,v)),lerp(10,6,ss(0,D-CT,v)),0,0,-3); }

// ---------- 7 碳纤维 ----------
function shotCarbon(u,D){
  const SC=ev('scale',0.5), Y8=ev('y1980',5.9), NO=ev('noah',10.3), MI=ev('micro',16.1), WV=ev('wave',18.9), HT=ev('heat',25.7), SV=ev('serve',30.4), ST=ev('stack',33.6), GR=ev('grow',35.2);
  if(u<Y8-0.3){ balG.visible=true; balG.position.set(0,0.4,0); const tilt=0; balBeam.rotation.z=tilt; [balPost,...balBeam.children].forEach(()=>{}); balMat.opacity=ss(SC,SC+0.6,u);
    const t1=tx('sameW',T('同样重','Same weight'),{color:'#ffffff',size:0.44}); t1.position.set(0,1.0,0); op(t1,ss(SC+0.4,SC+1,u));
    const k=ss(SC+1.2,SC+3.2,u); const b1=ln(0x9aa6b8,10), b2=ln(0x8fb8ff,10); bar3(b1,new THREE.Vector3(-3.6,-2.9,0.3),0.9*k); bar3(b2,new THREE.Vector3(2.4,-2.9,0.3),3.4*k); b1.material.opacity=b2.material.opacity=k;
    const t2=tx('stiff',T('强度、刚度：碳纤维是钢的好几倍（国际网联）','Strength and stiffness: several times steel (ITF)'),{color:'#ffffff',size:0.44,glow:CYAN}); t2.position.set(0,-3.6,0.3); op(t2,ss(SC+2,SC+2.6,u));
    const ls=tx('lsteel',T('钢','Steel'),{color:'#dfe6f0',size:0.42}); ls.position.set(-3,1.9,0); op(ls,ss(SC+0.6,SC+1.2,u)); const lc=tx('lcarb',T('碳纤维','Carbon fibre'),{color:'#c8dcff',size:0.42}); lc.position.set(3,1.9,0); op(lc,ss(SC+0.6,SC+1.2,u));
    look(0,0.2,10,0,-0.4,0); return; }
  if(u<MI-0.3){ const v=u-Y8;
    if(u<NO-0.3){ const rw=[rkW,rkW2,ghosts[0]]; rw.forEach((R,i)=>{ setRk(R,WOOD.a,WOOD.b); R.g.position.set((i-1)*2.6,-R.cy,-1); rkOp(R,0.9*(1-ss(0.6+i*0.2,1.6+i*0.2,v))); });
      const R=rkC; R.g.position.set(0,lerp(-4,-R.cy,ss(0.8,2.2,v)),0.8); rkOp(R,ss(0.8,1.6,v)); R.g.rotation.y=v*0.3;
      const y=tx('y80',T('1980 年前后：复合材料成主流','Around 1980: composites take over'),{color:'#ffffff',size:0.55,glow:CYAN}); y.position.set(0,BIG.a+1.0,0.8); op(y,ss(1.2,1.8,v));
      const ys=tx('y80s',T('国际网联 · 名人堂 · Taraborrelli 2019','ITF · Hall of Fame · Taraborrelli 2019'),{color:'#cfe8ff',size:0.28}); ys.position.set(0,BIG.a+0.45,0.8); op(ys,ss(1.6,2.2,v));
      look(0,0.6,9,0,0,0); return; }
    // 诺阿：一支木拍在红土色光里转一圈，落定为剪影
    const w=u-NO, R=rkW; setRk(R,WOOD.a,WOOD.b); rkOp(R,1); R.g.position.set(0,-R.cy,0); R.g.rotation.y=lerp(0,Math.PI*2,ss(0,4.5,w));
    rimL.intensity=6; rimR.intensity=4; rimL.color.set(0xff7a3d); rimR.color.set(0xffb070); rimL.position.set(-3,2,2); rimR.position.set(3,1,-2); R.frame.material.emissive.set(0x3a1206);
    const nt=tx('noah',T('1983 年法网：诺阿，被普遍认为是最后一个用木拍赢大满贯的人','1983 French Open: Noah — widely seen as the last Slam won with wood'),{color:'#ffe2c8',size:0.46,glow:'rgba(255,122,61,0.9)'}); nt.position.set(0,-R.a-1.2,0.3); op(nt,ss(0.5,1.1,w));
    const ns=tx('noahs',T('SI 2013 · Tennis Majors','SI 2013 · Tennis Majors'),{color:'#cfe8ff',size:0.28}); ns.position.set(0,-R.a-1.75,0.3); op(ns,ss(0.9,1.5,w));
    look(0,0.3,7.2,0,-0.3,0); return; }
  if(u<HT-0.3){ const v=u-MI;
    if(u<WV-0.2){ // 显微镜一路放大进拍框：碳纤维壳＋泡沫芯（示意）
      tubeG.visible=true; tubeG.rotation.set(0.25,v*0.2,0.15); const zz=ss(0,2.6,v); shell.material.opacity=lerp(1,0.25,ss(0.8,2.2,v)); fibers.forEach(f=>f.material.opacity=ss(0.6,1.4,v)*0.85);
      foam.material.uniforms.uOp.value=ss(1.0,2.0,v);
      const mag=tx('mag'+Math.min(3,Math.floor(zz*3.99)),[T('放大 ×10（示意）','×10 (schematic)'),T('放大 ×100（示意）','×100 (schematic)'),T('放大 ×1000（示意）','×1000 (schematic)'),T('碳纤维壳＋泡沫芯（US 4,061,520）','Carbon shell + foam core (US 4,061,520)')][Math.min(3,Math.floor(zz*3.99))],{color:'#cfe8ff',size:0.34}); hud(mag,-3.6,2.6); op(mag,1);
      look(0,0,lerp(18,5.5,zz),0,0,0); return; }
    // 两条振动波形丝带：旧拍慢、新拍快（频率读数爬升）
    const w=u-WV; const k=ss(0,1.2,w); const wv=[[0x9aa6b8,100,1.3,T('木拍：约 80–120 赫兹','Wood: ≈ 80–120 Hz')],[0x4fe3ff,180,-1.3,T('今天：约 100–180 赫兹','Today: ≈ 100–180 Hz')]];
    wv.forEach(([c,f,y,lab],i)=>{ const l=ln(c,4); const pts=[]; for(let j=0;j<=200;j++){ const s=j/200, x=lerp(-6,6,s); const tt=s*0.06*k*6; pts.push(new THREE.Vector3(x,y+Math.sin(2*Math.PI*f*tt*0.6-w*3)*0.7*Math.exp(-s*1.8),0)); } setLine(l,pts); l.material.opacity=k;
      const t=tx('wv'+i,lab,{color:i?'#c8f4ff':'#e6ecf4',size:0.46}); t.position.set(-3.9,y+1.05,0); op(t,ss(0.5,1.1,w)); });
    const s1=tx('wvs',T('Allen 2016 · Taraborrelli 2021 · Brody 等 2002 · 波形为示意','Allen 2016 · Taraborrelli 2021 · Brody et al. 2002 · waveforms schematic'),{color:'#cfe8ff',size:0.28}); s1.position.set(0,-3.0,0); op(s1,ss(0.8,1.4,w));
    const ref=tx('wvref',T('参照：宽体拍专利 Fig.4 的拍框振动曲线','After the frame-vibration trace in the widebody patent, Fig.4'),{color:'#ffe9c8',size:0.3}); ref.position.set(0,3.1,0); op(ref,ss(1,1.6,w));
    look(0,0,9.5,0,0,0); return; }
  if(u<ST-0.3){ // 热区：节点附近两支拍一样；拍头、拍喉处硬拍更好；发球打在拍头附近
    const v=u-HT; const A_=rkW2, B_=rkC; setRk(A_,BIG.a*0.92,BIG.b*0.92); setRk(B_,BIG.a*0.92,BIG.b*0.92); A_.mat.color&&A_.mat.color.set(0xffffff); rkOp(A_,1); rkOp(B_,1);
    A_.g.position.set(-2.4,-A_.cy,0); B_.g.position.set(2.4,-B_.cy,0);
    const rows=[[0.75,0.7,0.9],[0.0,1,1],[-0.6,0.72,0.9]]; rows.forEach(([fy,a,b],i)=>{ const k=ss(0.3+i*0.3,0.9+i*0.3,v); const la=ln(0xffc24a,8), lb=ln(0x34f5a8,8);
      bar3(la,new THREE.Vector3(-4.6,fy*BIG.a*0.92,0.2),1.6*a*k); bar3(lb,new THREE.Vector3(0.2,fy*BIG.a*0.92,0.2),1.6*b*k); la.material.opacity=lb.material.opacity=k; });
    const ta=tx('flex',T('较软的拍框','Flexible frame'),{color:'#ffe2a0',size:0.4}); ta.position.set(-2.4,BIG.a+0.9,0); op(ta,ss(0,0.6,v)); const tb=tx('stiffF',T('较硬的拍框','Stiff frame'),{color:'#c8fff0',size:0.4}); tb.position.set(2.4,BIG.a+0.9,0); op(tb,ss(0,0.6,v));
    const nt=tx('nodeEq',T('打在节点附近：几乎一样','Near the node: almost the same'),{color:'#ffffff',size:0.4}); nt.position.set(0,-BIG.a-1.0,0.3); op(nt,ss(1.2,1.8,v));
    const sv=ss(SV-HT,SV-HT+0.5,v); const sg=gs(0xffc24a,0.9,0.9*sv); sg.position.set(2.4,0.75*BIG.a*0.92,0.3);
    const st=tx('serveT',T('发球多打在拍头附近 · 打不准的人受益最大（Allen 2016）','Serves hit near the tip · off-centre hitters gain most (Allen 2016)'),{color:'#ffffff',size:0.42,glow:GOLD}); st.position.set(0,-BIG.a-1.6,0.3); op(st,sv);
    look(0,0,10.5,0,-0.3,0); return; }
  // 实物数据：挥拍重量抽掉 10%，挥速只长出薄薄一片（约 3%）
  const v=u-ST; stackG.visible=true; stackG.rotation.y=-0.4+v*0.05; const rm=ss(0.3,1.0,v);
  swPl.forEach((p,i)=>{ p.material.opacity=1; p.position.set(-1.6,0.1+i*0.2,i===9?lerp(0,4,rm):0); p.material.opacity=i===9?1-rm:1; });
  spStack.scale.set(1,2.0,1); spStack.position.set(1.6,1.0,0); const gk=ss(GR-ST,GR-ST+0.8,v); spSliver.scale.set(1,2.0*0.03*gk+0.001,1); spSliver.position.set(1.6,2.0+0.03*gk,0); spSliver.material.opacity=gk;
  const a=tx('swT',T('挥拍重量 −10%','Swing weight −10%'),{color:'#ffe2a0',size:0.44}); a.position.set(-1.6,2.6,0); op(a,ss(0.2,0.8,v)); const b=tx('spT',T('挥速 +约 3%','Swing speed ≈ +3%'),{color:'#c8f4ff',size:0.44}); b.position.set(1.6,2.6,0); op(b,gk);
  const s=tx('swS',T('Cross & Bower 2006：挥速 ∝ 挥拍重量^−0.27 · Allen 2016','Cross & Bower 2006: speed ∝ swing weight^−0.27 · Allen 2016'),{color:'#cfe8ff',size:0.3}); s.position.set(0,-0.6,0.5); op(s,ss(0.6,1.2,v));
  look(0,2.4,7.5,0,1.0,0); }

// ---------- 8 规则 ----------
function shotRules(u,D){
  const BX=ev('box',3.1), SH=ev('shrink',6.6), DM=ev('dims',8.8), SK=ev('strike',9.8);
  const R=rkB; setRk(R,BIG.a,BIG.b); rkOp(R,1); R.g.position.set(0,-R.cy+0.6,0);
  const full=29*IN, cur=lerp(32,29,ss(SH,SH+1.2,u))*IN; const top=R.a+0.6-R.cy*0+0.05; const w=12.5*IN/2;
  const k=ss(BX,BX+1.0,u); const sc=lerp(1.8,1,k); const yT=R.tip+0.6-R.cy+0.05, yB=yT-cur;
  const box=[[-w*sc,yT],[w*sc,yT],[w*sc,yB],[-w*sc,yB],[-w*sc,yT]].map(([x,y])=>new THREE.Vector3(x,y,0.2)); const bl=ln(0x4fe3ff,4); setLine(bl,box); bl.material.opacity=k;
  const dl=ln(0xffffff,2); setLine(dl,[new THREE.Vector3(w+0.6,yT,0.2),new THREE.Vector3(w+0.6,yB,0.2)]); dl.material.opacity=ss(SH-0.4,SH,u);
  const lt=tx('len'+(u<SH+0.6?'32':'29'),u<SH+0.6?T('长 32 英寸','Length 32 in'):T('长 29 英寸 = 73.7 cm','Length 29 in = 73.7 cm'),{color:'#ffffff',size:0.44,glow:CYAN}); lt.position.set(w+2.4,(yT+yB)/2,0.3); op(lt,ss(SH-0.4,SH,u));
  const ls=tx('lenS',T('国际网联规则（1990 年代后期起）· ISO 11416:1995','ITF Rules (from the late 1990s) · ISO 11416:1995'),{color:'#cfe8ff',size:0.28}); ls.position.set(w+2.4,(yT+yB)/2-0.55,0.3); op(ls,ss(SH,SH+0.6,u));
  const dm=[[T('宽 ≤ 31.7 cm','Width ≤ 31.7 cm'),-w-2.2,yT-1],[T('拍面 ≤ 39.4 × 29.2 cm','Strung face ≤ 39.4 × 29.2 cm'),-w-2.2,yT-2]];
  dm.forEach(([s,x,y],i)=>{ const t=tx('dm'+i,s,{color:'#ffffff',size:0.42}); t.position.set(x,y,0.3); op(t,ss(DM+i*0.4,DM+i*0.4+0.5,u)); });
  const nw=[[T('重量','Weight'),-w-2.2,yT-3.2],[T('材料','Material'),-w-2.2,yT-3.9]];
  nw.forEach(([s,x,y],i)=>{ const t=tx('nw'+i,s,{color:'#ffd0c8',size:0.42}); t.position.set(x,y,0.3); const k2=ss(SK+i*0.3,SK+i*0.3+0.4,u); op(t,k2); const st=ln(0xff3a28,4); setLine(st,[new THREE.Vector3(x-0.7,y,0.35),new THREE.Vector3(x-0.7+1.4*ss(SK+i*0.3+0.4,SK+i*0.3+0.8,u),y,0.35)]); st.material.opacity=k2; });
  const rs=tx('rulesS',T('国际网联《2026 网球规则》附录二','ITF Rules of Tennis 2026, Appendix II'),{color:'#cfe8ff',size:0.28}); rs.position.set(-w-2.2,yT-4.6,0.3); op(rs,ss(DM+0.6,DM+1.2,u));
  look(0,lerp(0.4,-0.6,ss(0,D,u)),lerp(12.5,13.2,ss(0,D,u)),0,-0.6,0); }

// ---------- 9 打法 ----------
function shotStyle(u,D){
  const QU=ev('quote',0.5), PW=ev('power',4.1), WH=ev('why',6.5), SI=ev('sim',14.1), RE=ev('real',11.3), PZ=ev('puzzle',16.3);
  if(u<SI-0.3){ const up=ss(WH-0.2,WH+0.8,u);   // 讲到原因时引语整体上移，腾出下面两行「原因 → 结果」
    const a=tx('kq1',T('现代球拍让比赛从','Modern rackets moved the game from'),{color:'#e8ecf6',size:0.5}); hud(a,0,1.55+0.5*up); op(a,ss(QU,QU+0.6,u)*(1-0.6*up));
    const b=bt('kq2',T('「技术」','"technique"'),{size:0.95,glow:CYAN,fx:'write'}); hud(b,0,0.55+0.75*up); b.update(u,QU+0.6,Infinity,1-0.7*ss(PW,PW+0.6,u));   /* 书写：技术 */
    const c=bt('kq3',T('转向「力量和旋转」','to "power and spin"'),{size:0.95,glow:GOLD,accent:T('力量和旋转','power and spin'),fx:'spin'}); hud(c,0,-0.75+1.0*up); c.update(u,PW);   /* 旋转：力量和旋转 */
    // 国际网联给的机制（History of Rackets and Strings 第 5 页）：两行依次出，箭头左边是拍子改了什么、右边是网球里的结果
    [[T('拍头更大  →  打偏的球更好控制','Bigger head  →  better control of off-centre hits'),'#c8f4ff',0],[T('拍框更硬  →  被框吸走的能量更少，出球更快','Stiffer frame  →  less energy lost, faster ball'),'#ffe2a0',1.6]].forEach(([str,col,dt],i)=>{
      const m=tx('why'+i,str,{color:col,size:0.46,glow:i?GOLD:CYAN}); hud(m,0,-0.7-0.58*i); op(m,ss(WH+0.6+dt,WH+1.2+dt,u)); });
    const s=tx('kqs',T('Miller 2006《英国运动医学杂志》（作者来自国际网联）· 国际网联《History of Rackets and Strings》','Miller 2006, Br J Sports Med (ITF author) · ITF, History of Rackets and Strings'),{color:'#cfe8ff',size:0.28}); hud(s,0,-2.05); op(s,ss(QU+1,QU+1.6,u));
    look(0,0,lerp(9,8.2,ss(0,SI,u)),0,0,0); return; }
  if(u<PZ-0.3){ balG.visible=true; balG.position.set(0,0.8,0); balMat.opacity=1; steelBar.visible=fibBundle.visible=false;   // 这里托盘上放的是「模拟」「实测」，不是上一节的钢条和碳纤维束
    const tilt=lerp(0,0.18,ss(SI,SI+1,u))*(1-ss(RE+0.6,RE+1.8,u)); balBeam.rotation.z=tilt;
    const ls=tx('simT',T('模拟：换上今天的拍和球，发得更快（Haake 等 2007，拍和球一起算）','Simulation: today\'s racket + ball serve faster (Haake et al. 2007, racket and ball together)'),{color:'#ffe2a0',size:0.38}); ls.position.set(-3.0,-2.6,0); op(ls,ss(SI,SI+0.6,u));
    const rs=tx('realT',T('实测：老木拍发球几乎一样快（Brody 等 2002 书中，Cross）','Measured: old wood serves almost as fast (Cross, in Brody et al. 2002)'),{color:'#c8f4ff',size:0.38}); rs.position.set(3.0,-3.3,0); op(rs,ss(RE,RE+0.6,u));
    // 两个托盘上方各有一段发球轨迹，球沿轨迹循环飞（周期相同＝一样快；模拟那边只有一条更亮的「快」轨迹）
    const p0=pans[0].getWorldPosition(new THREE.Vector3()), p1=pans[1].getWorldPosition(new THREE.Vector3());
    const arcP=(c,h,dy)=>{ const P=[]; for(let i=0;i<=32;i++){ const k=i/32; P.push(new THREE.Vector3(c.x-1.15+2.3*k,c.y-0.95+dy+h*4*k*(1-k),c.z+0.25)); } return P; };
    const fly=(b,P,ph,o)=>{ const k=((u*0.9+ph)%1+1)%1, i=Math.min(31,Math.floor(k*32)), f=k*32-i; showB(b,P[i].clone().lerp(P[i+1],f),o>0.01,o*ss(0,0.08,k)*(1-ss(0.92,1,k))); b.m.scale.setScalar(0.14/b.r); };
    const ks=ss(SI,SI+0.6,u), kr=ss(RE,RE+0.6,u);
    const A1=arcP(p0,0.75,0); const t1=ln(0xffc24a,5); setLine(t1,A1); t1.material.opacity=0.9*ks; fly(ball,A1,0,ks);
    const A2=arcP(p1,0.72,0), A3=arcP(p1,0.7,-0.06); const t2=ln(0x4fe3ff,4), t3=ln(0xd9a066,4); setLine(t2,A2); setLine(t3,A3); t2.material.opacity=t3.material.opacity=0.9*kr;
    fly(ball2,A2,0.0,kr); fly(ball3,A3,0.02,kr);
    const lp=tx('panSim',T('模拟','Simulated'),{color:'#ffe2a0',size:0.5,glow:GOLD}); lp.position.set(p0.x,p0.y-2.1,0.3); op(lp,ks);
    const lr=tx('panReal',T('实测','Measured'),{color:'#c8f4ff',size:0.5,glow:CYAN}); lr.position.set(p1.x,p1.y-2.1,0.3); op(lr,kr);
    const lw=tx('panWood',T('老木拍','Old wood'),{color:'#f0c890',size:0.3}); lw.position.set(p1.x+1.55,p1.y-1.15,0.3); op(lw,kr);
    const lm=tx('panMod',T('现代拍','Modern'),{color:'#c8f4ff',size:0.3}); lm.position.set(p1.x+1.55,p1.y-0.6,0.3); op(lm,kr);
    look(0,0.6,10,0,-0.6,0); return; }
  // 三块拼图：线和拍咬在一起拆不开，球那块暗着
  const v=u-PZ; pzG.visible=true; pzG.rotation.y=Math.sin(v*0.5)*0.2; const gap=lerp(0.4,0,ss(0.2,1.4,v));
  pz.forEach((m,i)=>{ m.position.x=(i-1)*(2.25+gap); m.material.opacity=i===2?0.25:1; m.material.emissiveIntensity=i===2?0.05:GLOW.emissive; });
  const labs=[T('线','Strings'),T('拍','Racket'),T('球','Ball')]; labs.forEach((s,i)=>{ const t=tx('pz'+i,s,{color:'#ffffff',size:0.7}); t.position.set((i-1)*2.25,0,0.4); op(t,i===2?0.35:ss(0.2,0.8,v)); });
  const tq=bt('pzT',T('时间对得上，作用分不开','The timing fits; the effects can\'t be separated'),{size:0.62,glow:VIO,fx:'weave',thread:'#c9b8ff'}); hud(tq,0,-1.75); tq.update(v,0.8);   /* 编织：线、拍、球缠在一起分不开 */
  const tn=tx('pzN',T('第三集：球','Episode 3: the ball'),{color:'#c8ffe6',size:0.42}); tn.position.set(2.25,1.6,0.4); op(tn,ss(1.6,2.2,v));
  look(0,0.3,8,0,0,0); }

// ---------- 10 片尾 ----------
function shotEnd(u,D){
  const RP=ev('replay',3.3), GL=ev('glass',5.9), BA=ev('ball',11.5);
  if(u<GL-0.3){ SLOW=[1.0,2.6];   // 回放那一球离开拍面的 1.6 s   // 回放开场那一球：宽拍头偏心时的速度条明显比窄拍长
    const R=rkA; rkOp(R,1); const s=u*0.3; R.g.rotation.set(0,twistAng(s-0.3,0.16),0); R.g.position.set(0,0,0);
    const hp=new THREE.Vector3(R.b*0.8,R.cy+0.15,0.33); { const bz=s<0.3?lerp(8,0.33,ss(0,0.3,s)):0.33+(s-0.3)*12; showB(ball,hp.clone().setZ(bz),true,s<0.3?ss(0,0.15,s):1-ss(3,5.5,bz)); }
    const k=ss(RP,RP+0.8,u); const b1=ln(0xffc24a,10), b2=ln(0x34f5a8,10); bar3(b1,new THREE.Vector3(-2.6,R.gripY-0.6,0.3),1.75*k); bar3(b2,new THREE.Vector3(-2.6,R.gripY-1.1,0.3),2.4*k); b1.material.opacity=b2.material.opacity=k;
    const t=bt('endT',T('它至少改写了：打偏的代价','At least it changed: the cost of a miss-hit'),{size:0.66,glow:GOLD,accent:T('打偏的代价','the cost of a miss-hit'),fx:'shock'}); hud(t,0,2.45); t.update(u,RP);   /* 冲击：回到开场那一球 */
    look(3.4,1,6.4,0.4,R.cy,0.8); return; }
  // 玻璃光：木拍与现代拍并排慢转；最后一颗球从光柱落下
  const v=u-GL; const A_=rkW, B_=rkC; setRk(A_,WOOD.a,WOOD.b); setRk(B_,BIG.a*0.92,BIG.b*0.92); rkOp(A_,1); rkOp(B_,1);
  A_.g.position.set(-1.8,-A_.cy,0); B_.g.position.set(1.8,-B_.cy,0); A_.g.rotation.y=v*0.4; B_.g.rotation.y=-v*0.4;
  beamMat.uniforms.uOp.value=0.16; rimL.intensity=6; rimR.intensity=6; rimL.color.set(0xffc24a); rimR.color.set(0x4fe3ff); rimL.position.set(-4,3,3); rimR.position.set(4,3,3);
  [[T('你的拍子拍面多大？','How big is your racket head?'),2.35],[T('打偏的时候，你感觉得到吗？','Can you feel a miss-hit?'),1.5]].forEach(([str,y],i)=>{ const q=bt('endQ'+i,str,{size:0.72,glow:GOLD,fx:'particles'}); hud(q,0,y); q.update(v,0.3+i*0.5,BA-GL-0.8); });   /* 片尾问句分两行（一行放不下），粒子汇聚、球落下之前散开 */
  const bk=ss(BA-GL,BA-GL+1.2,v); showB(ball3,new THREE.Vector3(0,lerp(6,-1.6,bk)+Math.abs(Math.sin(bk*9))*(1-bk)*0.6,1.2),bk>0,1);
  const nx=bt('nextB',T('下一集：球','Next: the ball'),{size:0.85,glow:MINT,accent:T('球','ball'),fx:'streak'}); hud(nx,0,2.2); nx.update(v,BA-GL+0.8);   /* 疾驰：球飞进来 */
  look(0,0.2,lerp(9.5,8.5,ss(0,D-GL,v)),0,-0.2,0); }

// ---------- 段落配色（按情绪） ----------
Object.assign(PAL,{
  hook:    {top:0x05030f,hz:0x1a1048,vi:0x3a0a3a,a:0x30e8ff},
  wood:    {top:0x0b0602,hz:0x3a2208,vi:0x2a1406,a:0xffb347},
  metal:   {top:0x030812,hz:0x0b2a50,vi:0x0a2030,a:0xc9d6ff},
  oversize:{top:0x0c0806,hz:0x3a2a08,vi:0x401018,a:0xffc24a},
  sweet:   {top:0x04040e,hz:0x14163a,vi:0x2a0a2a,a:0xff6a8a},
  twist:   {top:0x020c0a,hz:0x063828,vi:0x062a2a,a:0x34f5a8},
  carbon:  {top:0x03050c,hz:0x0c1a3a,vi:0x08202a,a:0x4fe3ff},
  rules:   {top:0x030812,hz:0x0b2a50,vi:0x0a2030,a:0x4fe3ff},
  style:   {top:0x06041a,hz:0x1d1250,vi:0x2b0d55,a:0xa78bfa},
  end:     {top:0x050505,hz:0x2a2008,vi:0x08202a,a:0xffc24a}});

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
  scene.userData.grid.uniforms.uC.value.set(prev.a).lerp(C(cur.a),k).multiplyScalar(0.55); return C(prev.a).lerp(C(cur.a),k); }
function shotTL(t){ const sc=TL.sections.find(s=>t>=s.t0&&t<s.t1)||TL.sections[TL.sections.length-1]; const u=t-sc.t0, D=sc.t1-sc.t0;
  hideAll(); FX_SHAKE=0; FX_FLASH=0; EV=sc.ev||{}; SEC_U=u;
  ({hook:shotHook,wood:shotWood,metal:shotMetal,oversize:shotOversize,sweet:shotSweet,twist:shotTwist,carbon:shotCarbon,rules:shotRules,style:shotStyle,end:shotEnd})[sc.kind](u,D);
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
Promise.all([FONT_READY,document.fonts.ready,loadTypeFonts(),...texP]).then(()=>{ CUTS=findCuts(); window.READY=true; }).catch(e=>console.error('READY failed',e));
// 自检：可见的 3D 字有没有出画、压进底部字幕带（y>880）或顶部标题带（y<120）——review_pack 前先跑 tools 里的 textcheck
window.textCheck=()=>{ camera.updateMatrixWorld(); const out=[]; const R=new THREE.Vector3(1,0,0).applyQuaternion(camera.quaternion);
  for(const k in TT){ const s=TT[k]; if(!s.visible||s.material.opacity<0.15) continue; const p=new THREE.Vector3(); s.getWorldPosition(p);
    const hw=s.scale.x*0.5*(s.parent&&s.parent.scale?s.parent.scale.x:1), hh=s.scale.y*0.35; const pr=v=>{ const q=v.clone().project(camera); return [(q.x*0.5+0.5)*W,(1-(q.y*0.5+0.5))*H,q.z]; };
    const a=pr(p.clone().addScaledVector(R,-hw)), b=pr(p.clone().addScaledVector(R,hw)), c=pr(p), up=pr(p.clone().add(new THREE.Vector3(0,hh,0).applyQuaternion(camera.quaternion))), dn=pr(p.clone().add(new THREE.Vector3(0,-hh,0).applyQuaternion(camera.quaternion)));
    if(c[2]>1) continue; const x0=Math.min(a[0],b[0]), x1=Math.max(a[0],b[0]), y0=Math.min(up[1],dn[1]), y1=Math.max(up[1],dn[1]);
    const f=1920/W; if(x0*f<37||x1*f>1883||y0*f<117||y1*f>883) out.push([k,Math.round(x0*f),Math.round(x1*f),Math.round(y0*f),Math.round(y1*f)]); }
  return out; };
