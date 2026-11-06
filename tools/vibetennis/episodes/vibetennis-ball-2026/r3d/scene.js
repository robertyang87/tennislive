// vibetennis 器材三部曲 ③ 球——球是什么（充了气的橡胶壳＋两片毛毡）、怎么演化、被打中的那几毫秒、实验室怎么管它、为什么改球就能调比赛的速度、现在的争议和未来。
// 理论与上屏数字的出处见 papers/vibetennis-ball-2026/sources.md（两源规则）。
// 通用底座（夜空、光点、全息字、3D 字、球场、后期）沿用 EP06–EP08；球的剖面、毛毡、压机、实验台、球堆为本集新做。示意的形状都在画面上标「示意」。
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


// ==================== EP09 球：本集物件 ====================
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
const rkA=makeRk('carbon',{a:BIG.a*0.95,b:BIG.b*0.95});
const ALLRK=[rkA];

// ---- 球：新球贴图、各年代的球、剖面球 ----
const mkTex=(w,h,fn)=>{ const c=document.createElement('canvas'); c.width=w; c.height=h; const g=c.getContext('2d'); fn(g,w,h); const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; t.anisotropy=8; return t; };
const SEAM=(x,w,h)=>h/2+h*0.27*Math.sin(x/w*Math.PI*4);   // 网球接缝：经纬图上一条两个周期的正弦——两片哑铃形毛毡的分界
const feltTex=(base,line)=>mkTex(1024,512,(g,w,h)=>{ g.fillStyle=base; g.fillRect(0,0,w,h);
  for(let i=0;i<26000;i++){ const v=frnd(); g.fillStyle=v<0.5?'rgba(255,255,255,0.07)':'rgba(40,40,0,0.08)'; g.fillRect(frnd()*w,frnd()*h,1+frnd()*2.5,1); }
  if(line){ g.strokeStyle=line; g.lineWidth=12; g.beginPath(); for(let x=0;x<=w;x+=4){ const y=SEAM(x,w,h); x?g.lineTo(x,y):g.moveTo(x,y); } g.stroke(); } });
const TEX={yellow:feltTex('#d8ef3c','#f6f6ee'), white:feltTex('#eeece4','#c9c3b2'), black:feltTex('#1b1c20','#55565c'),
  leather:mkTex(512,256,(g,w,h)=>{ g.fillStyle='#7a4a24'; g.fillRect(0,0,w,h); for(let i=0;i<9000;i++){ g.fillStyle=frnd()<0.5?'rgba(255,220,170,0.05)':'rgba(30,10,0,0.12)'; g.fillRect(frnd()*w,frnd()*h,2,2); }
    g.strokeStyle='#e8d2a6'; g.lineWidth=3; g.setLineDash([7,6]); for(const x of [w*0.25,w*0.75]){ g.beginPath(); g.moveTo(x,0); g.lineTo(x,h); g.stroke(); } g.beginPath(); g.moveTo(0,h/2); g.lineTo(w,h/2); g.stroke(); }),
  rubber:mkTex(256,128,(g,w,h)=>{ g.fillStyle='#8f8a86'; g.fillRect(0,0,w,h); for(let i=0;i<3000;i++){ g.fillStyle=frnd()<0.5?'rgba(255,255,255,0.05)':'rgba(0,0,0,0.08)'; g.fillRect(frnd()*w,frnd()*h,2,2); } }),
  flannel:mkTex(1024,512,(g,w,h)=>{ g.fillStyle='#f1eee6'; g.fillRect(0,0,w,h); for(let i=0;i<20000;i++){ g.fillStyle=frnd()<0.5?'rgba(255,255,255,0.08)':'rgba(60,50,30,0.06)'; g.fillRect(frnd()*w,frnd()*h,2,1); }
    g.strokeStyle='#8c7a5a'; g.lineWidth=5; g.setLineDash([10,8]); g.beginPath(); for(let x=0;x<=w;x+=4){ const y=SEAM(x,w,h); x?g.lineTo(x,y):g.moveTo(x,y); } g.stroke(); }),
  rubberIn:mkTex(64,64,(g,w,h)=>{ g.fillStyle='#3a3734'; g.fillRect(0,0,w,h); }) };
// 两片毛毡的透明度遮罩：接缝上方一片、下方一片（错开 90 度、形状相同）
const feltMask=(top)=>mkTex(1024,512,(g,w,h)=>{ g.fillStyle='#000'; g.fillRect(0,0,w,h); g.fillStyle='#fff'; g.beginPath(); g.moveTo(0,top?0:h); for(let x=0;x<=w;x+=4) g.lineTo(x,SEAM(x,w,h)+(top?3:-3)); g.lineTo(w,top?0:h); g.closePath(); g.fill(); });
const feltMat=(map)=>new THREE.MeshPhysicalMaterial({map,roughness:0.85,sheen:1,sheenRoughness:0.6,sheenColor:new THREE.Color(0xf6ffa0),emissive:0x1a2000,emissiveIntensity:0.25,transparent:true});
function makeHero(r=1,map=TEX.yellow){ const g=new THREE.Group(); scene.add(g); const m=new THREE.Mesh(new THREE.SphereGeometry(r,96,64),feltMat(map)); g.add(m); return {g,m,r}; }
const hero=makeHero(1), hero2=makeHero(1), hero3=makeHero(1);
const HEROS=[hero,hero2,hero3];
function heroOp(H,o,map){ if(map&&H.m.material.map!==map){ H.m.material.map=map; H.m.material.needsUpdate=true; } H.m.material.opacity=o; H.g.visible=o>0.003; }
// 毛绒：球面外的一层纤维点云，fl 越大越蓬（0 = 磨秃）
function makeFuzz(n,group){ const p=cloud(n,0.012,3,group); const D=[...Array(n)].map(()=>{ const z=2*frnd()-1, a=frnd()*6.283, s=Math.sqrt(1-z*z); return [s*Math.cos(a),z,s*Math.sin(a),frnd()]; }); return {p,D}; }
function setFuzz(F,c,r,fl,col,o){ const cc=new THREE.Color(col); for(let i=0;i<F.D.length;i++){ const d=F.D[i]; const rr=r*(1+fl*d[3]); cset(F.p,i,c.x+d[0]*rr,c.y+d[1]*rr,c.z+d[2]*rr,cc.r,cc.g,cc.b,o*(0.4+0.6*d[3])); } cdone(F.p); }
const fuzzA=makeFuzz(5000,scene), fuzzB=makeFuzz(5000,scene);

// 剖面球：橡胶壳（内外两层球面 + 切口圆环）、毛毡层、两半壳可以分开
const cutG=new THREE.Group(); scene.add(cutG);
function halfShell(r0,r1,col,inCol,thetaStart){ const g=new THREE.Group();
  const geo=(r,side)=>new THREE.SphereGeometry(r,72,36,0,Math.PI*2,thetaStart,Math.PI/2);
  const out=new THREE.Mesh(geo(r1),new THREE.MeshPhysicalMaterial({color:col,roughness:0.6,clearcoat:0.3,emissive:col,emissiveIntensity:0.08,transparent:true,side:THREE.FrontSide}));
  const inn=new THREE.Mesh(geo(r0),new THREE.MeshPhysicalMaterial({color:inCol,roughness:0.8,emissive:inCol,emissiveIntensity:0.15,transparent:true,side:THREE.BackSide}));
  const ring=new THREE.Mesh(new THREE.RingGeometry(r0,r1,96),new THREE.MeshBasicMaterial({color:0xff9a5a,transparent:true,side:THREE.DoubleSide,depthWrite:false})); ring.rotation.x=-Math.PI/2;
  g.add(out,inn,ring); g.userData={out,inn,ring}; return g; }
const shellT=halfShell(0.86,1.0,0x4a4440,0x2a2624,0), shellB=halfShell(0.86,1.0,0x4a4440,0x2a2624,Math.PI/2); cutG.add(shellT,shellB);
const thickT=halfShell(0.70,1.0,0x5a5450,0x2a2624,0), thickB=halfShell(0.70,1.0,0x5a5450,0x2a2624,Math.PI/2); cutG.add(thickT,thickB);   // 无压球：壁更厚（示意）
function shellOp(S,o){ S.visible=o>0.003; for(const k of ['out','inn']) S.userData[k].material.opacity=o; S.userData.ring.material.opacity=o*0.9; }
const feltT=new THREE.Mesh(new THREE.SphereGeometry(1.04,96,64),Object.assign(feltMat(TEX.yellow),{alphaMap:feltMask(true),alphaTest:0.5})), feltB=new THREE.Mesh(new THREE.SphereGeometry(1.04,96,64),Object.assign(feltMat(TEX.yellow),{alphaMap:feltMask(false),alphaTest:0.5}));
feltT.material.side=feltB.material.side=THREE.DoubleSide; scene.add(feltT,feltB);
const gas=cloud(2400,0.03,5,scene,0.8); const GAS=[...Array(2400)].map(()=>[frnd(),frnd(),frnd(),frnd()]);
const steam=cloud(1800,0.12,14,scene,0.3); const STM=[...Array(1800)].map(()=>[frnd(),frnd(),frnd(),frnd()]);

// 压机：上下两块模板，中间一个半球形的模腔，受热发橙光
const pressG=new THREE.Group(); scene.add(pressG);
const pressMat=()=>new THREE.MeshPhysicalMaterial({color:0x7d8794,metalness:0.95,roughness:0.3,emissive:0xff6a1a,emissiveIntensity:0,transparent:true});
const plateU=new THREE.Mesh(new THREE.BoxGeometry(5.2,0.7,3),pressMat()), plateD=new THREE.Mesh(new THREE.BoxGeometry(5.2,0.7,3),pressMat()); pressG.add(plateU,plateD);
const rods=[-2.3,2.3].map(x=>{ const m=new THREE.Mesh(new THREE.CylinderGeometry(0.12,0.12,6,16),pressMat()); m.position.x=x; pressG.add(m); return m; });

// 纸片／全息面板（引语、年份卡）
function panel(w,h,col){ const g=new THREE.Group(); const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({color:new THREE.Color(col).multiplyScalar(0.18),transparent:true,opacity:0,depthWrite:false,side:THREE.DoubleSide}));
  const e=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(w,h)),new THREE.LineBasicMaterial({color:col,transparent:true,opacity:0,blending:THREE.AdditiveBlending})); g.add(m,e); scene.add(g); g.userData={m,e}; return g; }
function pnOp(P,o){ P.visible=o>0.003; P.userData.m.material.opacity=0.8*o; P.userData.e.material.opacity=0.8*o; }
const PN=[...Array(4)].map(()=>panel(6.4,2.2,0x4fe3ff)); const tvP=panel(6,3.6,0x9fd8ff);

// 展台（演化博物馆）
const pedG=new THREE.Group(); scene.add(pedG);
const peds=[...Array(5)].map((_,i)=>{ const m=new THREE.Mesh(new THREE.CylinderGeometry(0.9,1.05,0.5,48),new THREE.MeshPhysicalMaterial({color:0x101722,metalness:0.6,roughness:0.25,clearcoat:1,emissive:0x0a1a30,emissiveIntensity:0.6,transparent:true}));
  const r=flatRing(0x4fe3ff,pedG); r.position.y=0.27; r.scale.set(2.1,2.1,1); m.add(r); m.userData.ring=r; pedG.add(m); return m; });
const MUS=[TEX.leather,TEX.rubber,TEX.flannel,TEX.white,TEX.yellow];
const musB=MUS.map(t=>makeHero(0.6,t));

// 墙、线床、实验台
const wall=new THREE.Mesh(new THREE.BoxGeometry(0.4,5,5),new THREE.MeshPhysicalMaterial({color:0x2a3240,metalness:0.2,roughness:0.5,emissive:0x0a1420,emissiveIntensity:0.6,transparent:true})); scene.add(wall);
const bedG=new THREE.Group(); scene.add(bedG);
{ const sp=[]; for(let i=-10;i<=10;i++){ sp.push(i*0.25,-2.6,0,i*0.25,2.6,0, -2.6,i*0.25,0,2.6,i*0.25,0); } const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(sp,3));
  bedG.add(new THREE.LineSegments(g,new THREE.LineBasicMaterial({color:0xd9e4ff,transparent:true,opacity:0.6}))); }
const granite=new THREE.Mesh(new THREE.BoxGeometry(3,0.5,3),new THREE.MeshPhysicalMaterial({color:0x3a3c44,roughness:0.35,clearcoat:0.8,emissive:0x0c0e14,emissiveIntensity:0.6,transparent:true})); scene.add(granite);
const drum=new THREE.Mesh(new THREE.CylinderGeometry(1.6,1.6,2.2,48,1,true),new THREE.MeshPhysicalMaterial({color:0x8a94a6,metalness:0.9,roughness:0.35,side:THREE.DoubleSide,transparent:true,emissive:0x0c1420,emissiveIntensity:0.6})); drum.rotation.z=Math.PI/2; scene.add(drum);
const piston=new THREE.Mesh(new THREE.CylinderGeometry(0.9,0.9,2.4,48),new THREE.MeshPhysicalMaterial({color:0xb8c2cf,metalness:1,roughness:0.2,transparent:true,emissive:0x0c1420,emissiveIntensity:0.6})); scene.add(piston);

// 计分块（换球节奏）、ATP 粒子、球堆
const tiles=[...Array(25)].map(()=>{ const m=new THREE.Mesh(new THREE.BoxGeometry(0.42,0.42,0.12),new THREE.MeshPhysicalMaterial({color:0x14243a,emissive:0x4fe3ff,emissiveIntensity:0,metalness:0.3,roughness:0.3,clearcoat:1,transparent:true})); scene.add(m); return m; });
const PILE_N=1400; const pile=new THREE.InstancedMesh(new THREE.SphereGeometry(0.33,16,12),new THREE.MeshPhysicalMaterial({map:TEX.yellow,roughness:0.85,sheen:1,sheenColor:new THREE.Color(0xf6ffa0),emissive:0x1a2000,emissiveIntensity:0.2,transparent:true}),PILE_N); pile.frustumCulled=false; scene.add(pile);   /* 实例化网格的包围球只在第一次渲染时按当时的实例算——分块渲染从不同时刻起步，算出来不一样，一块里球堆被剔掉、下一块又在（240.1 s 跳变 48） */
const PILE=[...Array(PILE_N)].map((_,i)=>{ const a=frnd()*6.283, r=Math.sqrt(frnd())*7; const h=Math.max(0,(1-r/7))*4.2*frnd()**0.4; return [Math.cos(a)*r,0.33+h,Math.sin(a)*r,frnd()*6.283,frnd()]; });
const layer=new THREE.Mesh(new THREE.BoxGeometry(18,0.5,18),new THREE.MeshPhysicalMaterial({color:0x1b5aa3,roughness:0.7,emissive:0x082650,emissiveIntensity:0.4,transparent:true})); scene.add(layer);
const crumbs=cloud(4000,0.12,6,scene); const CR=[...Array(4000)].map(()=>[frnd(),frnd(),frnd(),frnd()]);
const grass=new THREE.Mesh(new THREE.PlaneGeometry(40,40),new THREE.MeshPhysicalMaterial({color:0x1d4a1c,roughness:0.95,emissive:0x061806,emissiveIntensity:0.4,transparent:true})); grass.rotation.x=-Math.PI/2; scene.add(grass);
const nest=new THREE.Mesh(new THREE.SphereGeometry(0.33,48,32,0,Math.PI*2,0,Math.PI),feltMat(TEX.yellow)); scene.add(nest);
const nestHole=new THREE.Mesh(new THREE.CircleGeometry(0.1,32),new THREE.MeshBasicMaterial({color:0x050302,transparent:true})); nest.add(nestHole); nestHole.position.set(0,0.05,0.335);
// 拼图三块（线／拍／球）：第二集片尾那三块，球那一块这集点亮
const plateMat=c=>new THREE.MeshPhysicalMaterial({color:c,emissive:c,emissiveIntensity:GLOW.emissive,metalness:0.3,roughness:0.3,clearcoat:1,transparent:true});
const pzG=new THREE.Group(); scene.add(pzG);
const pz=[0xb9c8ff,0xffc24a,0x34f5a8].map((c,i)=>{ const m=new THREE.Mesh(new THREE.BoxGeometry(2.2,2.2,0.35),plateMat(c)); m.position.x=(i-1)*2.25; pzG.add(m); return m; });

// 通用池
const LN=[...Array(40)].map(()=>fatLine(0xffffff,3)); let lnI=0; const ln=(col,w=3,dashed=false)=>{ const l=LN[lnI++]; l.material.color.set(col); l.material.linewidth=w; l.material.dashed=dashed; return l; };
const RG=[...Array(6)].map(()=>flatRing(0xffffff)); let rgI=0; const rg=()=>RG[rgI++];
const GS=[...Array(10)].map(()=>glowSprite(0xffffff,1,0)); let gsI=0; const gs=(col,size,o)=>{ const s=GS[gsI++]; s.material.color.set(col).multiplyScalar(GLOW.k); s.scale.set(size,size,1); s.material.opacity=o; s.visible=o>0.003; return s; };
const BALLS=[...Array(6)].map(()=>makeBall(0.2)); let bI=0; const bl=()=>BALLS[bI++];
const showB=(b,p,o=1,s=1)=>{ b.m.visible=o>0.003; b.gl.visible=o>0.003; b.m.position.copy(p); b.gl.position.copy(p); b.m.scale.setScalar(s); b.gl.scale.setScalar(b.r*5*s); b.m.material.transparent=true; b.m.material.opacity=o; b.gl.material.opacity=0.3*o; };
function arc(l,c,r,a0,a1,axis='z',n=48){ const pts=[]; for(let i=0;i<=n;i++){ const a=lerp(a0,a1,i/n); pts.push(axis==='z'?new THREE.Vector3(c.x+Math.cos(a)*r,c.y+Math.sin(a)*r,c.z):new THREE.Vector3(c.x+Math.cos(a)*r,c.y,c.z+Math.sin(a)*r)); } setLine(l,pts); }
const V=(x,y,z)=>new THREE.Vector3(x,y,z);
const fmt=(x,d=1)=>x.toFixed(d);

// 绕球的气流：势流绕球的流线（球外）＋尾流的乱流（球后），用光线画；flow 让虚线往后走
function streams(c,R,o,turb,flow){ for(let j=0;j<9;j++){ const y0=(j-4)*0.34*R; if(Math.abs(y0)<0.06) continue; const l=ln(0x9fe8ff,2,true); const pts=[];
    for(let i=0;i<=60;i++){ const x=-4.2*R+8.4*R*i/60; const r2=x*x+y0*y0; let y=y0*(1+R*R*R/(2*Math.pow(Math.max(r2,R*R*1.05),1.5))*1.0);
      if(x>0.4*R) y+=Math.sin(x*3.2+j*1.7+flow*6)*turb*R*0.35*ss(0.4*R,2.5*R,x)*Math.exp(-Math.abs(y0)/(1.4*R)); pts.push(V(c.x+x,c.y+y,c.z)); }
    setLine(l,pts); l.material.dashSize=0.5; l.material.gapSize=0.25; l.material.dashOffset=-flow*3; l.material.opacity=o*(0.35+0.4*Math.exp(-Math.abs(y0)/R)); } }
// 剖面轮廓（二维）：外壳被压平 d，内壁往里翻成泡 b（0..1）
function squashProfile(lo,li,c,R,d,b,th){ const out=[], inn=[]; for(let i=0;i<=96;i++){ const a=-Math.PI/2+i/96*Math.PI*2; let x=Math.cos(a)*R, y=Math.sin(a)*R; const fy=-R+d; if(y<fy){ y=fy; } x*=1+0.25*(d/R)*Math.max(0,1-Math.abs(Math.sin(a))); out.push(V(c.x+y,c.y-x,c.z));
    let xi=Math.cos(a)*(R-th), yi=Math.sin(a)*(R-th); const fyi=fy+th; if(yi<fyi) yi=fyi; const bub=b*R*0.55*Math.exp(-Math.pow(xi/(R*0.42),2)); if(yi<fyi+bub*1.0&&Math.sin(a)<0) yi=fyi+bub; xi*=1+0.25*(d/R)*Math.max(0,1-Math.abs(Math.sin(a))); inn.push(V(c.x+yi,c.y-xi,c.z)); }
  setLine(lo,out); setLine(li,inn); }

const pt=cloud(1600,0.05,8,scene,0.5); const PTS=[...Array(1600)].map(()=>[(frnd()-0.5)*16,(frnd()-0.5)*9,(frnd()-0.5)*8,frnd(),frnd()]);

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
  courtG.visible=false; courtG.position.set(0,0,0); courtG.userData.mat.opacity=1; granite.scale.set(1,1,1); layer.scale.set(1,1,1); ALLRK.forEach(R=>{ R.g.position.set(0,0,0); R.g.rotation.set(0,0,0); R.g.scale.setScalar(1); rkOp(R,0); });
  HEROS.forEach(H=>{ H.g.position.set(0,0,0); H.g.rotation.set(0,0,0); H.g.scale.set(1,1,1); heroOp(H,0,TEX.yellow); H.m.material.color.set(0xffffff); });
  musB.forEach(H=>{ heroOp(H,0); H.g.scale.set(1,1,1); }); pedG.visible=false;
  chide(fuzzA.p); chide(fuzzB.p); chide(gas); chide(steam); chide(crumbs); chide(pt);
  cutG.visible=false; cutG.position.set(0,0,0); cutG.rotation.set(0,0,0); cutG.scale.setScalar(1); [shellT,shellB,thickT,thickB].forEach(S=>{ shellOp(S,0); S.position.set(0,0,0); });
  [feltT,feltB].forEach(f=>{ f.visible=false; f.position.set(0,0,0); f.rotation.set(0,0,0); f.scale.setScalar(1); f.material.opacity=1; });
  pressG.visible=false; [plateU,plateD,...rods].forEach(m=>m.material.emissiveIntensity=0);
  PN.forEach(p=>{ pnOp(p,0); p.position.set(0,0,0); p.rotation.set(0,0,0); }); pnOp(tvP,0);
  wall.visible=false; wall.scale.set(1,1,1); bedG.visible=false; granite.visible=false; drum.visible=false; piston.visible=false; tiles.forEach(t=>t.visible=false);
  pile.visible=false; layer.visible=false; grass.visible=false; nest.visible=false; pzG.visible=false;
  BALLS.forEach(b=>{ b.m.visible=false; b.gl.visible=false; b.m.scale.setScalar(1); b.m.material.color.set(0xffffff); }); bI=0;
  LN.forEach(l=>{ l.material.opacity=0; l.material.dashed=false; l.material.dashOffset=0; }); lnI=0; RG.forEach(r=>r.material.opacity=0); rgI=0; GS.forEach(s=>{ s.material.opacity=0; s.visible=false; }); gsI=0;
  for(const k in TT) op(TT[k],0); for(const k in TB) TB[k].g.visible=false; for(const k in text3D) t3op(text3D[k],0);
  beamMat.uniforms.uOp.value=0; rimL.intensity=0; rimR.intensity=0; rimL.color.set(0xff3fd0); rimR.color.set(0x30e8ff); DOF.on=false; MOTE_SPEED=1; SLOW=null; }
const rims=(a,b,i=5)=>{ rimL.intensity=i; rimR.intensity=i; rimL.color.set(a); rimR.color.set(b); rimL.position.set(-4,3,4); rimR.position.set(4,3,4); };
// 规格环：绕球的一圈光环＋标签
function specRing(i,c,r,tilt,ang,k,label,col){ const l=ln(col,2); const pts=[]; const q=new THREE.Quaternion().setFromEuler(new THREE.Euler(tilt,ang,0));
  for(let j=0;j<=72;j++){ const a=j/72*6.283*k; pts.push(V(Math.cos(a)*r,0,Math.sin(a)*r).applyQuaternion(q).add(c)); } setLine(l,pts); l.material.opacity=0.55*Math.min(1,k*3);
  if(label){ const s=tx('spec'+i,label,{color:'#ffffff',size:0.34,glow:col===0xffc24a?GOLD:CYAN}); s.position.copy(V(r*1.02,0,0).applyQuaternion(q).add(c)); op(s,ss(0.3,0.8,k)); } }

// ---------- 1 钩子：一颗不到 60 克的球，被写了六项数字 ----------
function shotHook(u,D){
  const SP=ev('spin',0.3), SC=ev('specs',5.9), RK=ev('rk',10.5), QQ=ev('q',13.9);
  if(u<RK-0.3){ // 黑场里一颗球慢转着亮起来，六道规格环一道道套上去
    heroOp(hero,ss(SP,SP+1.2,u)); hero.g.rotation.set(0.3,u*0.5,0.15); setFuzz(fuzzA,V(0,0,0),1.0,0.05,0xeaff80,0.5*ss(SP,SP+1.2,u));
    const w=tx('hkW',T('56.0–59.4 克','56.0–59.4 g'),{color:'#fff3c8',size:0.55,glow:GOLD}); w.position.set(0,-1.75,0); op(w,ss(SP+0.8,SP+1.5,u)*(1-ss(SC-0.4,SC,u)));
    const labs=[T('重量','mass'),T('直径','size'),T('弹跳','rebound'),T('前向形变','forward deformation'),T('回复形变','return deformation'),T('耐久','durability')];
    labs.forEach((s,i)=>{ const k=ss(SC+i*0.42,SC+i*0.42+0.7,u); if(k>0) specRing(i,V(0,0,0),1.45+i*0.13,0.5+i*0.33,i*1.05+u*0.08,k,s,i%2?0x4fe3ff:0xffc24a); });
    look(lerp(0.4,-0.6,ss(0,RK,u)),lerp(0.3,0.9,ss(0,RK,u)),lerp(4.4,6.6,ss(SC-0.5,RK,u)),0,0,0); rims(0xffc24a,0x4fe3ff,6);
    DOF.on=true; DOF.focus=camera.position.length(); DOF.ap=0.00006; proj('ball',V(0,0,0)); return; }
  // 对照：左边球被六道环套着，右边一支球拍只有一个尺寸框
  const v=u-RK; heroOp(hero,1); hero.g.position.set(-2.4,0.2,0); hero.g.rotation.set(0.3,u*0.5,0.15);
  for(let i=0;i<6;i++) specRing(i,V(-2.4,0.2,0),1.4+i*0.12,0.5+i*0.33,i*1.05+u*0.08,1,'',i%2?0x4fe3ff:0xffc24a);
  const R=rkA; rkOp(R,ss(0,0.6,v)); R.g.position.set(2.6,-R.cy*0.15-0.4,0); R.g.scale.setScalar(0.62); R.g.rotation.y=Math.sin(u*0.4)*0.25;
  const top=R.tip*0.62-0.4+0.25, bot=R.butt*0.62-0.4-0.15, hw=R.b*0.62+0.25; const bx=ln(0xffffff,2,true); const kb=ss(0.4,1.2,v);
  setLine(bx,[V(2.6-hw,bot,0),V(2.6+hw,bot,0),V(2.6+hw,top,0),V(2.6-hw,top,0),V(2.6-hw,bot,0)]); bx.material.opacity=0.55*kb;
  const la=tx('hkRk',T('球拍：只限尺寸','Racket: size limits only'),{color:'#e8f0ff',size:0.5,glow:CYAN}); la.position.set(2.6,bot-0.45,0.2); op(la,kb*(1-ss(QQ-RK+1.6,QQ-RK+2.2,v)));
  const lb=tx('hkBl',T('球：六项数字','Ball: six numbers'),{color:'#fff3c8',size:0.5,glow:GOLD}); lb.position.set(-2.4,-1.85,0.2); op(lb,ss(0.2,0.8,v)*(1-ss(QQ-RK+1.6,QQ-RK+2.2,v)));
  const q=bt('hookQ',T('一颗球，凭什么管得这么严？','Why is one ball regulated so tightly?'),{size:0.9,glow:GOLD,accent:T('这么严','so tightly'),fx:'shock'}); hud(q,0,2.3); q.update(v,QQ-RK,Infinity,0.86);   /* 光晕：这一行字大、白字多，再压一档（glow_check gain 1.06 → 门槛内） */   /* 冲击：一记重音 */
  look(lerp(-0.6,0.6,ss(0,D-RK,v)),0.5,lerp(10.5,9.6,ss(0,D-RK,v)),0,0.1,0); rims(0xffc24a,0x4fe3ff,5); beamMat.uniforms.uOp.value=0.08; }

// ---------- 2 演化：五个展台 ----------
function shotOrigin(u,D){
  const E=[ev('leather',0.5),ev('rubber',5.5),ev('cloth',9.5),ev('melton',13.5),ev('hollow',17.4)];
  pedG.visible=true; const cur=E.reduce((a,t,i)=>u>=t-0.2?i:a,0);
  const labs=[[T('皮／布，塞碎布、马毛','Leather or cloth, stuffed'),''],[T('1870 年代 · 橡胶','1870s · rubber'),''],[T('外裹一层布','Cloth cover'),''],[T('麦尔登呢 · 硫化胶缝','Melton cloth · vulcanised seam'),''],[T('空心 · 充气','Hollow · pressurised'),'']];
  peds.forEach((p,i)=>{ p.position.set(i*4.2,-0.9,0); const k=ss(E[i]-0.2,E[i]+0.6,u); p.material.opacity=0.35+0.65*k; p.userData.ring.material.opacity=0.6*k*(i===cur?1:0.4);
    const H=musB[i]; heroOp(H,k); H.g.position.set(i*4.2,0.25+Math.sin(u*1.2+i)*0.05,0); H.g.rotation.set(0.25,u*0.6+i,0.1); H.g.scale.setScalar(i===cur?1.12:1);
    const s=tx('mus'+i,labs[i][0],{color:'#ffffff',size:0.4,glow:GOLD}); s.position.set(i*4.2,-1.55,0.6); op(s,i===cur?k:0); });   /* 只标当前这一颗：旁边几颗的字会挤进同一行 */
  // 第一颗：皮球里露出填充（马毛的纤维）；最后一颗：剖开看到空心里的气
  if(u<E[1]){ setFuzz(fuzzA,V(0,0.25,0),0.45,0.35,0xd8b07a,0.6*ss(E[0]+1,E[0]+2,u)*(1-ss(E[1]-0.6,E[1],u))); }
  if(u>E[4]-0.3){ const k=ss(E[4],E[4]+0.8,u); heroOp(musB[4],1-k*0.75); cutG.visible=true; cutG.position.set(4*4.2,0.25,0); cutG.scale.setScalar(0.6*1.12); cutG.rotation.set(0.25,u*0.6,0);
    shellOp(shellT,k); shellOp(shellB,k); shellT.position.y=0.25*k; shellB.position.y=-0.25*k;
    for(let i=0;i<500;i++){ const g_=GAS[i]; const r=Math.cbrt(g_[0])*0.45, a=g_[1]*6.283, z=2*g_[2]-1, s=Math.sqrt(1-z*z); cset(gas,i,4*4.2+Math.cos(a+u)*s*r,0.25+z*r,Math.sin(a+u)*s*r,0.4,0.9,1,k*0.8); } cdone(gas); }
  const cx=cur*4.2;   /* 每个展台一个镜头：说到哪一颗就切到哪一颗（交叉溶解），镜头里缓缓横移 */
  look(lerp(cx-1.5,cx+1.2,ss(E[cur],E[cur]+4,u)),0.9,5.6,cx,0.1,0); rims(0xffb347,0x4fe3ff,5); beamMat.uniforms.uOp.value=0.06; DOF.on=true; DOF.focus=5.6; DOF.ap=0.0001; }

// ---------- 3 拆开一颗球：压壳、充气、包毡、蒸汽 ----------
function shotMake(u,D){
  const PR=ev('press',0.5), HT=ev('heat',2.6), JN=ev('join',6.7), GA=ev('gas',8.7), PP=ev('pr',10.9), FE=ev('felt',15.5), CR=ev('cross',17.5), ST=ev('steam',20.7), PL=ev('pl',24.9), SW=ev('sweater',32.7);
  if(u<FE-0.3){ cutG.visible=true; cutG.scale.setScalar(1); cutG.rotation.set(0.35,u*0.25,0);
    if(u<JN){ // 压机：上下模板合拢，模腔发热（150 度、2 分半）
      pressG.visible=true; const c=ss(PR,PR+1.6,u); plateU.position.y=lerp(3.2,1.35,c); plateD.position.y=lerp(-3.2,-1.35,c); const h=ss(HT,HT+1.2,u)*(1-ss(JN-1,JN-0.3,u));
      [plateU,plateD,...rods].forEach(m=>{ m.material.emissiveIntensity=0.22*h; m.material.opacity=1; });
      shellOp(shellT,ss(PR+0.6,PR+1.4,u)); shellOp(shellB,ss(PR+0.6,PR+1.4,u)); shellT.position.y=0.55; shellB.position.y=-0.55;
      const t1=tx('mkT',T('150 度 · 2 分半','150 °C · 2½ min'),{color:'#ffd2a8',size:0.5,glow:'rgba(255,140,60,0.9)'}); t1.position.set(0,-2.6,1.6); op(t1,h);
      const t0=tx('mkS',T('国际网联介绍的工艺 · 示意','Process as described by the ITF · schematic'),{color:'#cfe8ff',size:0.28}); hud(t0,0,-2.9); op(t0,ss(PR,PR+0.6,u));
      pressG.scale.setScalar(0.8); look(lerp(1.5,-1.0,ss(0,JN,u)),1.4,lerp(11,9.8,ss(0,JN,u)),0,0,0); rims(0xff7a3d,0x4fe3ff,5); return; }
    // 两半合上，同时充气：气体粒子从缝里灌进去，压力表的弧走满
    const j=ss(JN,JN+0.9,u); const tr=1-0.55*ss(GA-0.3,GA+0.6,u); shellOp(shellT,tr); shellOp(shellB,tr);   /* 充气时壳变半透明，看得见里面的气 */ shellT.position.y=lerp(0.55,0,j); shellB.position.y=lerp(-0.55,0,j);
    const g=ss(GA-0.3,GA+1.6,u);
    for(let i=0;i<2400;i++){ const p=GAS[i]; const life=(p[3]+u*0.6)%1; const inside=i<2400*g; const a=p[1]*6.283, z=2*p[2]-1, s=Math.sqrt(1-z*z);
      if(inside){ const r=Math.cbrt(p[0])*0.82; const jit=Math.sin(u*9+i)*0.03; cset(gas,i,Math.cos(a+u*0.8)*s*r+jit,z*r,Math.sin(a+u*0.8)*s*r,0.4,0.9,1,0.75); }
      else { const r=lerp(3.4,1.0,life); cset(gas,i,Math.cos(a)*r,(z*0.25)*r,Math.sin(a)*r,0.4,0.9,1,0.5*g*(1-life)); } } cdone(gas);
    const kp=ss(PP,PP+1.4,u); const ga=ln(0x4fe3ff,6); arc(ga,V(-2.6,0.2,0.3),0.7,Math.PI*1.1,Math.PI*1.1-kp*Math.PI*1.2,'z'); ga.material.opacity=kp;
    const gb=ln(0x4fe3ff,2); arc(gb,V(-2.6,0.2,0.3),0.7,Math.PI*1.1,-Math.PI*0.1,'z'); gb.material.opacity=0.35*kp;
    const t2=tx('mkP',T('比外面多将近 1 个大气压','Nearly one atmosphere above outside'),{color:'#c8f4ff',size:0.36,glow:CYAN}); t2.position.set(-2.6,-0.95,0.3); op(t2,kp);
    look(lerp(-1.0,0.4,ss(JN,FE,u)),0.6,lerp(7.4,6.6,ss(JN,FE,u)),-0.9,0,0); rims(0xff7a3d,0x4fe3ff,5); DOF.on=true; DOF.focus=5; DOF.ap=0.00006; return; }
  if(u<PL-0.3){ // 两片哑铃形毛毡错开 90 度飞来合拢；蒸汽一喷，毛绒蓬起
    const v=u-FE; cutG.visible=true; cutG.rotation.set(0.35,u*0.25,0); shellOp(shellT,1-ss(CR+1.5,CR+2.5,u)); shellOp(shellB,1-ss(CR+1.5,CR+2.5,u));
    const k=ss(FE,CR+1.2,u); feltT.visible=feltB.visible=true;
    feltT.rotation.set(0.35,u*0.25+lerp(1.6,0,k),0); feltB.rotation.set(0.35,u*0.25-lerp(1.6,0,k),0); feltT.position.set(0,lerp(2.6,0,k),lerp(1,0,k)); feltB.position.set(0,lerp(-2.6,0,k),lerp(1,0,k));
    const lb=tx('mkF',T('两片哑铃形毛毡 · 错开 90 度','Two dumb-bell felts · 90° apart'),{color:'#f3ffc8',size:0.36,glow:LIME}); lb.position.set(0,-1.85,0.5); op(lb,ss(FE,FE+0.6,u)*(1-ss(ST-0.4,ST,u)));
    const s=ss(ST,ST+1.5,u);
    for(let i=0;i<1800;i++){ const p=STM[i]; const life=(p[3]+u*0.35)%1; const a=p[1]*6.283, r=1.1+life*2.4*p[0]; cset(steam,i,Math.cos(a)*r*0.6,-1.4+life*4.5,Math.sin(a)*r*0.6,0.85,0.9,0.95,0.16*s*(1-ss(0.6,1,life))*(1-ss(PL-1.2,PL-0.3,u))); } cdone(steam);
    setFuzz(fuzzA,V(0,0,0),1.04,0.08*s,0xeaff80,0.6*s);
    const ls=tx('mkSt',T('过一遍蒸汽 · 毛绒蓬起','Steamed · the nap fluffs up'),{color:'#ffffff',size:0.36}); ls.position.set(0,-1.85,0.5); op(ls,ss(ST,ST+0.6,u));
    look(lerp(0.8,-0.6,ss(FE,PL,u)),lerp(0.4,0.9,ss(FE,PL,u)),lerp(5.4,4.6,ss(FE,PL,u)),0,0,0); rims(0xd6ee3a,0x4fe3ff,5); return; }
  // 有压球 vs 无压球：两个剖面并排；最后一句「穿毛衣」
  const v=u-PL; cutG.visible=true; cutG.rotation.set(0.42,0,0); cutG.position.set(0,0,0);
  shellOp(shellT,1); shellOp(shellB,1); shellT.position.set(-1.7,0.3,0); shellB.position.set(-1.7,-0.3,0);
  shellOp(thickT,ss(0,0.8,v)); shellOp(thickB,ss(0,0.8,v)); thickT.position.set(1.7,0.3,0); thickB.position.set(1.7,-0.3,0);
  for(let i=0;i<1200;i++){ const p=GAS[i]; const a=p[1]*6.283, z=2*p[2]-1, s=Math.sqrt(1-z*z), r=Math.cbrt(p[0])*0.8, side=i<700; const w=new THREE.Vector3((side?-1.7:1.7)+Math.cos(a+u)*s*r,z*r,Math.sin(a+u)*s*r).applyEuler(cutG.rotation);
    const jit=side?0.025:0.004; cset(gas,i,w.x+Math.sin(u*11+i)*jit,w.y,w.z,side?0.4:0.6,side?0.9:0.7,1,side?0.8:0.35); } cdone(gas);
  const la=tx('plA',T('有压球：里面多一口气','Pressurised: extra air inside'),{color:'#c8f4ff',size:0.32,glow:CYAN}); la.position.set(-1.7,-1.75,0.6); op(la,ss(0,0.6,v)*(1-ss(SW-PL-1,SW-PL-0.5,v)));
  const lb=tx('plB',T('无压球：里外一样，壁更厚','Pressureless: same pressure, thicker wall'),{color:'#ffe2a0',size:0.32,glow:GOLD}); lb.position.set(1.7,-1.75,0.6); op(lb,ss(0.5,1.1,v)*(1-ss(SW-PL-1,SW-PL-0.5,v)));
  const st=tx('plS',T('壁厚为示意','Wall thickness schematic'),{color:'#9fb8d0',size:0.24}); hud(st,3.2,-2.9); op(st,ss(0.5,1.1,v));
  const sw=bt('mkT2',T('充了气的橡胶壳，穿一件毛衣','An air-filled rubber shell in a sweater'),{size:0.7,glow:LIME,accent:T('毛衣','sweater'),fx:'weave',thread:'#e8ff9a'}); hud(sw,0,2.4); sw.update(v,SW-PL-0.3);   /* 编织：毛衣 */
  if(v>SW-PL-0.5){ const k=ss(SW-PL-0.5,SW-PL+0.6,v); feltT.visible=feltB.visible=true; [feltT,feltB].forEach(f=>{ f.position.set(-1.7,0,0).applyEuler(cutG.rotation); f.rotation.copy(cutG.rotation); f.scale.setScalar(lerp(1.5,1,k)); f.material.opacity=k; }); }
  look(0,0.6,lerp(8.6,8.0,ss(0,D-PL,v)),0,-0.1,0); rims(0xffc24a,0x4fe3ff,5); }

// ---------- 4 颜色：白／黑 → 1972 电视 → 温网 1986 ----------
function shotColor(u,D){
  const WB=ev('wb',0.5), TV=ev('tv',3.7), YE=ev('yel',5.7), WI=ev('wim',8.9);
  if(u<WI-0.3){ heroOp(hero,1); hero.g.rotation.set(0.3,u*0.7,0.1);
    /* 白、黑、黄三颗同位叠放、透明度交叉过渡（原来按 1.2 s 换贴图，motion_check 在 75–78 s 量到 14–15 的跳变） */
    const blk=u<TV?0.5-0.5*Math.cos(Math.PI*Math.max(0,u-WB)/1.2):lerp(0.5-0.5*Math.cos(Math.PI*(TV-WB)/1.2),0,ss(TV,TV+0.8,u)), yel=ss(YE-0.4,YE+0.4,u);
    const flash=ss(YE,YE+0.25,u)*(1-ss(YE+0.25,YE+0.9,u));
    heroOp(hero,1,TEX.white); heroOp(hero2,blk*(1-yel),TEX.black); heroOp(hero3,yel,TEX.yellow);
    [hero,hero2,hero3].forEach((H,i)=>{ H.g.rotation.copy(hero.g.rotation); H.g.scale.setScalar((1+0.08*flash)*(1+0.003*i)); });
    const lb=tx('cWB',T('白，或黑：看场地的颜色','White or black, depending on the court'),{color:'#ffffff',size:0.36}); lb.position.set(0,-1.7,0.5); op(lb,ss(WB,WB+0.6,u)*(1-ss(TV-0.4,TV,u)));
    pnOp(tvP,ss(TV,TV+0.6,u)); tvP.position.set(0,0,-0.3);
    const y=t3d('y1972','1972','#ffd27a',0.7); y.g.position.set(-2.1,1.25,0.2); t3op(y,ss(TV+0.2,TV+0.8,u));
    const l2=tx('cTV',T('为了电视上看得清','So it shows up on TV'),{color:'#c8f4ff',size:0.34,glow:CYAN}); l2.position.set(0,-1.7,0.5); op(l2,ss(TV+0.3,TV+0.9,u));
    look(Math.sin(u*0.3)*0.5,0.3,lerp(5.8,5.0,ss(0,WI,u)),0,0,0); rims(0xffffff,0xd6ee3a,5); return; }
  // 温网：草地上一颗黄球落下弹起
  const v=u-WI; grass.visible=true; grass.material.opacity=1; heroOp(hero,1,TEX.yellow); hero.g.scale.setScalar(0.5);
  const b=Math.abs(Math.sin(v*3.2))*Math.exp(-v*0.6)*1.6; hero.g.position.set(0,0.5+b,0); hero.g.rotation.set(0,v,0);
  const y=t3d('y1986','1986','#c8ffd8',0.8); y.g.position.set(0,2.6,-0.5); t3op(y,ss(0.3,0.9,v));
  const lb=tx('cWi',T('温网换成黄球','Wimbledon goes yellow'),{color:'#ffffff',size:0.4,glow:MINT}); hud(lb,0,-2.4); op(lb,ss(0.5,1.1,v));
  look(lerp(2.5,1.2,ss(0,D-WI,v)),1.0,5.5,0,1.2,0); rims(0x34f5a8,0xd6ee3a,5); beamMat.uniforms.uOp.value=0.1; }

// ---------- 5 那几毫秒：线床、撞墙、内壁翻泡、气闸、毛绒、冷、高海拔 ----------
function shotImpact(u,D){
  const SR=ev('str',0.5), WA=ev('wall',5.3), SQ=ev('squash',7.6), BU=ev('bub',15.2), AI=ev('air',18.5), SE=ev('serve',21.7), FL=ev('fluff',25.8), BA=ev('bald',29.3), CO=ev('cold',32.0), AL=ev('alt',38.5);
  if(u<WA-0.3){ // 线床上停留：慢放、毫秒计数
    SLOW=[SR+0.2,SR+1.0]; bedG.visible=true; bedG.rotation.y=0.5; bedG.position.set(0,0,0);
    const ms=clamp((u-SR-0.8)/3.2)*4.5; const inC=u>SR+0.8&&ms<4.5; const z=u<SR+0.8?lerp(3.0,0.95,ss(SR,SR+0.8,u)):(ms<4.5?0.95-0.35*Math.sin(ms/4.5*Math.PI):0.95+(u-SR-4)*4);
    heroOp(hero,1); hero.g.position.set(0,0,0).add(V(Math.sin(0.5)*z,0,Math.cos(0.5)*z)); const sq=inC?0.35*Math.sin(ms/4.5*Math.PI):0; hero.g.rotation.set(0,0.5,0); hero.g.scale.set(1+sq*0.4,1+sq*0.4,1-sq);
    const n=Math.min(9,Math.round(ms*2)); const c=tx('ms'+n,T(fmt(n/2)+' 毫秒',fmt(n/2)+' ms'),{color:'#ffffff',size:0.6,glow:GOLD}); hud(c,-3.2,1.9); op(c,ss(SR+0.6,SR+1,u));
    const l=tx('pStr',T('在线床上：4 到 5 毫秒','On the strings: 4–5 ms'),{color:'#ffe2a0',size:0.36,glow:GOLD}); hud(l,-3.2,1.2); op(l,ss(SR+1.4,SR+2,u));
    const sc=tx('pSc',T('放大示意','Magnified schematic'),{color:'#9fb8d0',size:0.24}); hud(sc,3.6,-2.9); op(sc,1);
    look(4.2,1.2,3.4,0,0,0.6); rims(0xffc24a,0x4fe3ff,5); DOF.on=true; DOF.focus=5.4; DOF.ap=0.00007; return; }
  if(u<AI-0.3){ // 撞墙压扁到一半；剖面：内壁往里翻成泡
    const v=u-WA; wall.visible=true; wall.position.set(-1.2,0,0); wall.scale.set(0.6,0.62,0.6); wall.material.opacity=0.9;
    const cyc=ss(SQ-WA-0.6,SQ-WA+0.9,v); const d=0.95*cyc*(1-ss(BU-WA+3.5,BU-WA+4.5,v)); const b=ss(BU-WA,BU-WA+1.0,v)*(1-ss(BU-WA+2.2,BU-WA+3.2,v));
    const lo=ln(0xd6ee3a,6), li=ln(0xffa060,4); squashProfile(lo,li,V(0,0,0),1,d,b,0.14); lo.material.opacity=li.material.opacity=1;
    wall.position.x=-1+d-0.12;   /* 剖面在竖直面上，墙在左；墙面贴着被压平的那一面 */
    const ms=t3d('half','≈ 1/2','#ffd27a',0.5); ms.g.position.set(1.9,1.3,0); t3op(ms,ss(SQ-WA,SQ-WA+0.8,v)*(1-ss(BU-WA-0.5,BU-WA,v)));
    const l1=tx('pW',T('每秒 30 米撞硬墙 · 压扁到约一半','30 m/s into a wall · squashed to about half'),{color:'#ffffff',size:0.34}); hud(l1,0,-2.5); op(l1,ss(0.2,0.8,v)*(1-ss(BU-WA-0.5,BU-WA,v)));
    const l2=tx('pB',T('0.2 毫秒后：内壁往里翻成一个泡','After 0.2 ms the inner wall buckles into a bubble'),{color:'#ffd2a8',size:0.34,glow:'rgba(255,160,96,0.9)'}); hud(l2,0,-2.5); op(l2,ss(BU-WA,BU-WA+0.6,v));
    const sc=tx('pSc2',T('剖面示意','Cross-section schematic'),{color:'#9fb8d0',size:0.24}); hud(sc,3.6,-2.9); op(sc,1);
    look(0.4,0,lerp(5.4,4.8,ss(0,AI-WA,v)),0.4,0,0); rims(0xffa060,0x4fe3ff,5); return; }
  if(u<CO-0.3){ // 气闸：流线绕球、尾流；发球落地剩约 3/4；毛绒蓬起 vs 磨秃
    const v=u-AI; const fl=u<FL?0.06:(u<BA?lerp(0.06,0.22,ss(FL,FL+1.5,u)):lerp(0.22,0.0,ss(BA,BA+1.2,u)));
    heroOp(hero,1); hero.g.rotation.set(0,-u*2,0.2); setFuzz(fuzzA,V(0,0,0),1.0,fl,0xeaff80,0.7);
    hero.g.scale.setScalar(1+fl*0.25);
    streams(V(0,0,0),1+fl*0.4,ss(0,0.8,v),0.6+fl*3,u*0.6);
    if(u>SE-0.2&&u<FL-0.2){ const k=ss(SE,SE+2.2,u); const b1=ln(0xffc24a,10), b2=ln(0x34f5a8,10);
      setLine(b1,[V(-3,-1.9,0.5),V(1,-1.9,0.5)]); setLine(b2,[V(-3,-2.35,0.5),V(-3+4*lerp(1,0.75,k),-2.35,0.5)]); b1.material.opacity=b2.material.opacity=ss(SE,SE+0.5,u)*(1-ss(FL-0.7,FL-0.2,u));
      const a1=tx('pOut',T('出手','At launch'),{color:'#ffe2a0',size:0.3}); a1.position.set(-3.7,-1.9,0.5); op(a1,b1.material.opacity);
      const a2=tx('pLand',T('落地 ≈ 3/4','At the bounce ≈ 3/4'),{color:'#c8ffe6',size:0.3}); a2.position.set(-3+4*lerp(1,0.75,k)+1.2,-2.35,0.5); op(a2,b1.material.opacity); }
    const lA=tx('pAir',T('毛绒：一道气闸','The fuzz: an air brake'),{color:'#c8f4ff',size:0.4,glow:CYAN}); hud(lA,0,2.4); op(lA,ss(0.2,0.8,v)*(1-ss(FL-AI-0.5,FL-AI,v)));
    const lF=tx('pFl',T('蓬起来：阻力更大，球更慢','Fluffed: more drag, slower'),{color:'#ffe2a0',size:0.38,glow:GOLD}); hud(lF,0,2.4); op(lF,ss(FL,FL+0.6,u)*(1-ss(BA-0.4,BA,u)));
    const lB=tx('pBa',T('磨秃了：阻力变小','Worn bald: less drag'),{color:'#c8ffe6',size:0.38,glow:MINT}); hud(lB,0,2.4); op(lB,ss(BA,BA+0.6,u));
    look(Math.sin(v*0.2)*1.2,0.6,lerp(7.2,6.4,ss(0,CO-AI,v)),0.2,-0.1,0); rims(0x4fe3ff,0xd6ee3a,5); return; }
  // 冷：两颗球同高落下，0 度那颗弹得低；高海拔：山上的一颗太活
  const v=u-CO; const drop=(t,H,e)=>{ const g=3.43; const t1=Math.sqrt(2*H/g); if(t<t1) return H-0.5*g*t*t; t-=t1; let vv=e*Math.sqrt(2*g*H); for(let i=0;i<5;i++){ const tb=2*vv/g; if(t<tb) return vv*t-0.5*g*t*t; t-=tb; vv*=e; } return 0; };   /* 落球：每次弹起按恢复系数 e 掉速 */
  if(u<AL-0.3){ courtG.visible=false; granite.visible=true; granite.position.set(0,-0.25,0); granite.scale.set(3,1,1); granite.material.opacity=1;
    const t_=Math.max(0,v-0.6); const b1=bl(), b2=bl(); showB(b1,V(-1.5,0.2+drop(t_,3.2,0.76),0),1,2.2); showB(b2,V(1.5,0.2+drop(t_,3.2,0.68),0),1,2.2);
    b2.m.material.color.set(0xc8e6ff); b1.m.material.color.set(0xffffff);
    const t20=tx('c20',T('20 度','20 °C'),{color:'#ffe2a0',size:0.42,glow:GOLD}); t20.position.set(-1.5,-0.95,0.6); op(t20,ss(0.2,0.8,v));
    const t0=tx('c0',T('0 度：弹得低 20% 以上','0 °C: bounces 20%+ lower'),{color:'#c8f4ff',size:0.42,glow:CYAN}); t0.position.set(1.5,-0.95,0.6); op(t0,ss(0.6,1.2,v));
    for(let i=0;i<1500;i++){ const p=STM[i]; const y=(4-((p[1]*4+v*0.4)%4)); cset(steam,i,1.5+(p[0]-0.5)*3,y,(p[2]-0.5)*2,0.8,0.9,1,0.1*ss(0.5,1.5,v)); } cdone(steam);
    look(0,1.6,7.6,0,1.2,0); rims(0xffc24a,0x4fe3ff,5); return; }
  const w=u-AL; const lines=[]; const m1=ln(0x9fd8ff,3); const pts=[]; for(let i=0;i<=60;i++){ const x=-6+12*i/60; pts.push(V(x,-1.5+3.2*Math.exp(-x*x/6)+0.4*Math.sin(x*2.3)*Math.exp(-x*x/10),-1)); } setLine(m1,pts); m1.material.opacity=ss(0,0.6,w);
  const bb=bl(); showB(bb,V(0,1.9+Math.abs(Math.sin(w*4))*1.2,-0.6),1,1.6);
  const la=tx('pAlt',T('海拔 1219 米以上：专用的高海拔球','Above 1,219 m: a dedicated high-altitude ball'),{color:'#ffffff',size:0.36,glow:CYAN}); hud(la,0,-2.4); op(la,ss(0.3,0.9,w));
  look(0,1.2,lerp(9,8,ss(0,D-AL,w)),0,1,0); rims(0x4fe3ff,0xffffff,5); beamMat.uniforms.uOp.value=0.08; }

// ---------- 6 实验室：落球、压、磨、九局 ----------
function shotLab(u,D){
  const LO=ev('lon',0.5), DR=ev('drop',4.5), HF=ev('half',10.3), PS=ev('press',12.1), WE=ev('wear',17.3), NI=ev('nine',21.7), WI=ev('wim',24.6), TW=ev('two',32.1);
  if(u<PS-0.3){ // 落球架：254 cm 刻度，弹回落在 135–147 的带里
    granite.visible=true; granite.position.set(0,-0.25,0); granite.scale.set(1,1,1); granite.material.opacity=1; const S=1/40;   // 1 单位 = 40 cm
    const rl=ln(0x9fd8ff,3); setLine(rl,[V(-1.2,0,0),V(-1.2,254*S,0)]); rl.material.opacity=0.9;
    for(const h of [0,50,100,150,200,254]){ const t=ln(0x9fd8ff,2); setLine(t,[V(-1.35,h*S,0),V(-1.05,h*S,0)]); t.material.opacity=0.7; }
    const band=ln(0x34f5a8,14); setLine(band,[V(-1.2,135*S,0),V(-1.2,147*S,0)]); band.material.opacity=ss(DR+1,DR+1.6,u);
    const l1=tx('l254',T('254 厘米','254 cm'),{color:'#ffffff',size:0.46}); l1.position.set(-2.3,254*S,0); op(l1,ss(DR,DR+0.6,u));
    const l2=tx('l135',T('135–147 厘米','135–147 cm'),{color:'#c8ffe6',size:0.46,glow:MINT}); l2.position.set(-2.6,141*S,0); op(l2,ss(DR+1,DR+1.6,u));
    const t=Math.max(0,u-DR-0.3); const g=9.8/40*0.4*40; let y; const H=254*S, H2=141*S; const tf=Math.sqrt(2*H/g); if(t<tf) y=H-0.5*g*t*t; else { const s=t-tf, vu=Math.sqrt(2*g*H2), tu=2*vu/g; const ss_=s%tu; y=vu*ss_-0.5*g*ss_*ss_; if(s>tu*1.5) y=Math.min(y,H2); }
    const b=bl(); showB(b,V(0,0.33+(u<DR?H:y),0),ss(LO,LO+0.6,u),1.7);
    const lon=tx('lLon',T('伦敦 · 国际网联技术中心','London · ITF Technical Centre'),{color:'#c8f4ff',size:0.46,glow:CYAN}); hud(lon,0,2.5); op(lon,ss(LO,LO+0.6,u)*(1-ss(DR-0.4,DR,u)));
    const hf=bt('labH',T('只弹回一半多','Barely more than half'),{size:0.62,glow:GOLD,fx:'sag'}); hud(hf,2.6,1.2); hf.update(u,HF-0.2);   /* 下沉：落下去弹不回来 */
    look(lerp(1.6,0.6,ss(0,PS,u)),3.3,lerp(8.4,7.6,ss(0,PS,u)),0.4,3.2,0); rims(0x4fe3ff,0x34f5a8,5); return; }
  if(u<NI-0.3){ // 压：活塞压下、回弹；磨：滚筒里翻九局
    const v=u-PS;
    if(u<WE-0.3){ piston.visible=true; heroOp(hero,1); hero.g.position.set(0,0,0); const c=0.5+0.5*Math.sin((v-0.8)*2.2); const k=ss(0.8,1.4,v)*c; piston.position.y=2.2-0.35*k; hero.g.scale.set(1+0.12*k,1-0.22*k,1+0.12*k); hero.g.rotation.set(0.2,v*0.3,0);
      granite.visible=true; granite.position.set(0,-1.25,0); granite.material.opacity=1;
      const l=tx('lPr',T('压上固定重量：量压下去多少、弹回多少','Fixed load: measure squash and recovery'),{color:'#ffffff',size:0.34}); hud(l,0,-2.5); op(l,ss(0.2,0.8,v));
      look(2.6,1.4,6.2,0,0.3,0); rims(0xffc24a,0x4fe3ff,5); return; }
    drum.visible=true; drum.rotation.set(0,0,Math.PI/2); drum.rotateY(u*2.2); const w=u-WE; heroOp(hero,1); hero.g.scale.setScalar(0.6); const a=-u*2.2*0.6; hero.g.position.set(0,-0.9+Math.abs(Math.sin(u*3))*0.3,0.1); hero.g.rotation.set(0,0,u*3);
    setFuzz(fuzzA,hero.g.position,0.6,lerp(0.05,0.25,ss(0,3,w)),0xeaff80,0.6);
    const n=t3d('nine','9','#ffd27a',1.4); n.g.position.set(2.8,0.4,0); n.g.rotation.y=-0.3; t3op(n,ss(0.3,0.9,w));
    const l=tx('lWe',T('模拟九局比赛的磨损','Simulates nine games of wear'),{color:'#ffe2a0',size:0.36,glow:GOLD}); hud(l,0,-2.5); op(l,ss(0.2,0.8,w));
    look(-0.8,1.2,lerp(7,6.2,ss(0,NI-WE,w)),0.8,0,0); rims(0xffc24a,0x4fe3ff,5); return; }
  // 一盘局数排成一排：热身+前 7 局一批，之后每 9 局换一次
  const v=u-NI; const N=25; tiles.forEach((t,i)=>{ t.visible=true; const row=Math.floor(i/13), col=i%13; t.position.set((col-6)*0.62,0.8-row*0.75,0); const lit=ss(i*0.06,i*0.06+0.3,v); t.material.opacity=lit;
    const grp=i<7?0:(i<16?1:2); const on=ss(WI-NI+grp*0.9,WI-NI+grp*0.9+0.5,v); t.material.emissive.set([0xffc24a,0x4fe3ff,0x34f5a8][grp]); t.material.emissiveIntensity=0.1+0.25*on; });
  [6,15,24].forEach((i,j)=>{ const t=tiles[i]; const b=bl(); const on=ss(WI-NI+j*0.9+0.3,WI-NI+j*0.9+0.8,v); showB(b,t.position.clone().add(V(0.32,0.45,0.15)),on,0.9); });
  const lw=tx('lWU',T('热身 + 前 7 局','Warm-up + first 7 games'),{color:'#ffe2a0',size:0.3,glow:GOLD}); lw.position.set(-2.0,1.45,0.2); op(lw,ss(WI-NI,WI-NI+0.6,v));
  const l9=tx('l9',T('之后每 9 局换一次','Then every 9 games'),{color:'#c8f4ff',size:0.3,glow:CYAN}); l9.position.set(2.2,1.45,0.2); op(l9,ss(WI-NI+0.9,WI-NI+1.5,v));
  const lt=tx('lWim',T('温网的换球节奏','Wimbledon\'s ball changes'),{color:'#ffffff',size:0.38}); hud(lt,0,2.6); op(lt,ss(WI-NI,WI-NI+0.6,v));
  const two=bt('labTwo',T('第一次提前两局：热身也在磨它','First change two games early: the warm-up wears it too'),{size:0.56,glow:GOLD,accent:T('热身','warm-up'),fx:'write'}); hud(two,0,-2.3); two.update(v,TW-NI-0.2);   /* 书写：规则原文 */
  look(lerp(-0.8,0.8,ss(0,D-NI,v)),0.5,lerp(7.8,7.2,ss(0,D-NI,v)),0,0.3,0); rims(0xffc24a,0x34f5a8,5); }

// ---------- 7 调速：大球、三种球速、发球赛跑、给球场测速 ----------
function shotDial(u,D){
  const BG=ev('big',0.5), VO=ev('vote',5.8), TY=ev('types',10.3), T3=ev('t3',13.2), RA=ev('race',17.9), IN_=ev('init',25.7), CT=ev('court',29.4), FI=ev('fire',32.9), KN=ev('knob',35.6);
  if(u<RA-0.3){ // 三颗球并排：1 号、2 号、3 号（大 6%，按真实比例），量规环比大小；下方一个场速表
    const ks=[1,1,1.06]; HEROS.forEach((H,i)=>{ const k=ss(TY+i*0.4-0.2,TY+i*0.4+0.4,u); const show=u<VO?(i===2?ss(BG,BG+0.8,u):0):Math.max(k,i===2?1:0);
      heroOp(H,show); H.g.position.set(i===2?lerp(0,2.8,ss(VO-0.2,VO+0.8,u)):(i-1)*2.8,0.3,0); H.g.scale.setScalar(ks[i]*0.95); H.g.rotation.set(0.3,u*0.5+i,0.1); });
    if(u<VO-0.2){ const g_=ln(0xffffff,2,true); arc(g_,V(0,0.3,0.4),0.95*1.06+0.05,0,6.283); g_.material.opacity=ss(BG+0.5,BG+1.2,u)*0.7; const g2=ln(0x4fe3ff,2); arc(g2,V(0,0.3,0.42),0.95,0,6.283); g2.material.opacity=ss(BG+0.8,BG+1.5,u)*0.7;
      const l=tx('dBig',T('更大的球 · 让比赛慢下来','A bigger ball · to slow the game'),{color:'#ffe2a0',size:0.38,glow:GOLD}); hud(l,0,-2.4); op(l,ss(BG+0.3,BG+0.9,u)); }
    else { const y=t3d('y2001','2001','#ffd27a',0.6); y.g.position.set(0,2.4,0); t3op(y,ss(VO,VO+0.6,u)*(1-ss(TY-0.3,TY,u)));
      const names=[T('1 号 · 快','Type 1 · fast'),T('2 号 · 中速','Type 2 · medium'),T('3 号 · 慢 · 大 6%','Type 3 · slow · 6% bigger')];
      const courts=[T('配慢场','for slow courts'),T('配中速场','for medium courts'),T('配快场','for fast courts')];
      names.forEach((s,i)=>{ const k=ss(TY+i*0.4,TY+i*0.4+0.6,u); const a=tx('ty'+i,s,{color:'#ffffff',size:0.34,glow:i===2?GOLD:CYAN}); a.position.set((i-1)*2.8,-1.05,0.4); op(a,k);
        const b=tx('tc'+i,courts[i],{color:i===2?'#ffe2a0':'#c8f4ff',size:0.3}); b.position.set((i-1)*2.8,-1.5,0.4); op(b,k); });
      if(u>T3-0.3){ const g_=ln(0xffc24a,3); arc(g_,V(2.8,0.3,0.6),1.06*0.95+0.08,0,6.283*ss(T3,T3+0.8,u)); g_.material.opacity=1; } }
    look(lerp(-0.5,0.5,ss(0,RA,u)),0.7,lerp(8.6,8.0,ss(0,RA,u)),0,0.3,0); rims(0xffc24a,0x4fe3ff,5); return; }
  if(u<CT-0.3){ // 发球赛跑：同一记发球，标准球和大球并排飞向底线，大球晚到
    const v=u-RA; courtG.visible=true; courtG.userData.mat.opacity=1; const L2=23.77/2; const T1=1.1, T2=1.1*1.016;
    const pos=(s,lane)=>{ const k=clamp(s); return V(lane, 2.8*(1-k)+0.3+Math.sin(k*Math.PI)*0.3, -L2+2*L2*k); };
    const s=Math.max(0,v-0.6); const kA=s/T1, kB=s/T2; const bA=bl(), bB=bl(); showB(bA,pos(kA,-1.2),1,1.8); showB(bB,pos(kB,1.2),1,1.8*1.06);
    const tA=ln(0x4fe3ff,4), tB=ln(0xffc24a,4); const pa=[], pb=[]; for(let i=0;i<=20;i++){ pa.push(pos(Math.min(kA,1)*i/20,-1.2)); pb.push(pos(Math.min(kB,1)*i/20,1.2)); } setLine(tA,pa); setLine(tB,pb); tA.material.opacity=tB.material.opacity=0.9;
    const r1=tx('rA',T('标准球','Standard ball'),{color:'#c8f4ff',size:0.9,glow:CYAN}); r1.position.set(-1.2,1.6,L2+1.2); op(r1,ss(0.4,0.9,v));
    const r2=tx('rB',T('大球','Bigger ball'),{color:'#ffe2a0',size:0.9,glow:GOLD}); r2.position.set(1.2,0.6,L2+1.2); op(r2,ss(0.4,0.9,v));
    const d=t3d('ms10','+10 ms','#ffd27a',1.0); d.g.position.set(0,3.4,L2-1); d.g.rotation.y=Math.PI/2-0.25; t3op(d,ss(T2+0.7,T2+1.2,v)*(1-ss(IN_-RA-0.4,IN_-RA,v)));
    const sub=tx('rSim',T('一项模拟：一发 +10 毫秒，二发最多 +16 毫秒','A simulation: +10 ms first serve, up to +16 ms second'),{color:'#ffffff',size:0.32}); hud(sub,0,-2.5); op(sub,ss(1.2,1.8,v)*(1-ss(IN_-RA-0.4,IN_-RA,v)));
    const sub2=tx('rIn',T('另一项实测：发出去的初速没有变慢','A measured study: serve speed off the racket unchanged'),{color:'#c8ffe6',size:0.32,glow:MINT}); hud(sub2,0,-2.5); op(sub2,ss(IN_-RA,IN_-RA+0.6,v));
    if(v>IN_-RA){ const g1=ln(0x34f5a8,8), g2=ln(0x34f5a8,8); const k=ss(IN_-RA,IN_-RA+0.8,v); setLine(g1,[V(-3,1.2,-L2+0.5),V(-3+2.2*k,1.2,-L2+0.5)]); setLine(g2,[V(-3,0.8,-L2+0.5),V(-3+2.2*k,0.8,-L2+0.5)]); g1.material.opacity=g2.material.opacity=k; }
    look(lerp(17,15.5,ss(0,CT-RA,v)),4.6,lerp(1.5,-0.5,ss(0,CT-RA,v)),0,1.0,0); beamMat.uniforms.uOp.value=0.12; rims(0xffc24a,0x4fe3ff,4); return; }
  // 给球场测速：一颗球以每秒 30 米、16° 射向地面；最后球变成一只旋钮＋一把尺
  const v=u-CT; courtG.visible=true; courtG.userData.mat.opacity=1;
  if(u<KN-0.3){ SLOW=[FI-CT+0.4,FI-CT+1.4]; const s=Math.max(0,(v-(FI-CT)+0.3))*0.5; const a=16*Math.PI/180; const P0=V(-6,6*Math.tan(a),-5); let p;
    if(s<1){ p=P0.clone().lerp(V(0,0.12,-5),s); } else { const r=s-1; p=V(r*6*0.85,0.12+r*6*Math.tan(a)*0.6,-5); }
    const b=bl(); showB(b,p,ss(FI-CT-0.3,FI-CT,v),2.0); const tr=ln(0xffc24a,4,true); setLine(tr,[P0,V(0,0.12,-5)]); tr.material.opacity=0.8*ss(FI-CT,FI-CT+0.5,v);
    const ang=ln(0x4fe3ff,3); arc(ang,V(0,0.05,-5),1.6,Math.PI,Math.PI-a,'z'); ang.material.opacity=ss(FI-CT+0.6,FI-CT+1,v);
    const l=tx('ctL',T('国际网联测场地：每秒 30 米、16° 射一颗球','The ITF tests a court: a ball fired at 30 m/s, 16°'),{color:'#ffffff',size:0.34}); hud(l,0,-2.5); op(l,ss(0.3,0.9,v));
    const l2=tx('ctB',T('量它弹起前后的速度','Measure its speed before and after the bounce'),{color:'#c8f4ff',size:0.3,glow:CYAN}); hud(l2,0,2.5); op(l2,ss(FI-CT+1,FI-CT+1.6,v));
    look(lerp(-1,1,ss(0,KN-CT,v)),2.6,2.0,-1.2,0.4,-5); beamMat.uniforms.uOp.value=0.1; rims(0xffc24a,0x4fe3ff,4); return; }
  const w=u-KN; courtG.visible=false; heroOp(hero,1); hero.g.rotation.set(0.2,w*0.8,0); hero.g.position.set(0,0.2,0);
  const ruler=ln(0x4fe3ff,3); setLine(ruler,[V(-3,-1.35,0),V(3,-1.35,0)]); ruler.material.opacity=ss(0,0.5,w); for(let i=0;i<=12;i++){ const t=ln(0x4fe3ff,2); setLine(t,[V(-3+i*0.5,-1.35,0),V(-3+i*0.5,-1.35+(i%3?0.15:0.3),0)]); t.material.opacity=ss(0,0.5,w)*0.8; }
  const knob=ln(0xffc24a,5); arc(knob,V(0,0.2,0),1.35,Math.PI*1.25,Math.PI*1.25-ss(0.6,2.2,w)*Math.PI*1.5,'z'); knob.material.opacity=ss(0.6,1,w);
  const q=bt('dialK',T('场地快不快，用球量；比赛太快，改球调','Court speed is measured with the ball; the game is slowed by changing the ball'),{size:0.56,glow:GOLD,accent:T('用球量','measured with the ball'),fx:'spin'}); hud(q,0,2.45); q.update(w,0.1);   /* 旋转：旋钮 */
  look(0,0.2,lerp(6.4,5.8,ss(0,D-KN,w)),0,0,0); rims(0xffc24a,0x4fe3ff,6); }

// ---------- 8 现在：抱怨、每周不一样、统一挑球 ----------
function shotNow(u,D){
  const CP=ev('complain',0.5), Q1=ev('q1',3.8), Q2=ev('q2',8.8), WK=ev('weeks',13.1), AT=ev('atp',17.0), ON=ev('one',23.4);
  if(u<WK-0.3){ heroOp(hero,1); hero.g.position.set(0,0,-1.2); hero.g.scale.setScalar(0.8); hero.g.rotation.set(0.2,u*0.4,0); setFuzz(fuzzA,V(0,0,-1.2),0.8,0.05+0.2*ss(Q1,Q1+2,u),0xeaff80,0.6);
    const quotes=[[T('2023 · 梅德韦杰夫：新球几局就变得特别毛','2023 · Medvedev: new balls get very fluffy within games'),Q1],[T('2026 · 佩古拉：换作别的运动，不会接受','2026 · Pegula: no other sport would accept it'),Q2]];
    quotes.forEach(([s,t],i)=>{ const p=PN[i]; pnOp(p,ss(t,t+0.6,u)*0.6); p.position.set(i?1.3:-1.3,i?-1.9:1.9,0.2); p.rotation.y=i?-0.1:0.1; p.scale.set(0.82,0.36,1);
      const a=tx('nq'+i,s,{color:'#ffffff',size:0.32}); a.position.set(i?1.3:-1.3,i?-1.9:1.9,0.35); op(a,ss(t+0.2,t+0.8,u)); });
    const l=tx('nC',T('抱怨最多的，恰恰是球','The loudest complaints: the ball'),{color:'#ffd2a8',size:0.4,glow:RED}); hud(l,0,2.6); op(l,ss(CP,CP+0.6,u)*(1-ss(Q1-0.3,Q1,u)));
    look(Math.sin(u*0.25)*0.8,0.2,7.2,0,0,0); rims(0xff5a4a,0x4fe3ff,5); return; }
  if(u<AT-0.3){ // 这一周、下一周：一排球颜色、毛度都不一样
    const v=u-WK; for(let i=0;i<6;i++){ const b=bl(); const hue=[0xffffff,0xf0ffa0,0xe0ff70,0xfff0a0,0xd8ff60,0xffffc0][i]; showB(b,V((i-2.5)*1.5,0.3+Math.sin(v*2+i)*0.08,0),ss(i*0.15,i*0.15+0.5,v),2.4); b.m.material.color.set(hue); b.m.scale.set(2.4*(1+0.05*Math.sin(i*2.1)),2.4,2.4); }
    for(let i=0;i<6;i++){ const s=tx('wk'+i,T('第 '+(i+1)+' 周','Week '+(i+1)),{color:'#c8f4ff',size:0.28}); s.position.set((i-2.5)*1.5,-0.6,0.2); op(s,ss(i*0.15,i*0.15+0.5,v)); }
    const l=tx('nW',T('要的是：每周打同一种球','What players want: the same ball every week'),{color:'#ffe2a0',size:0.38,glow:GOLD}); hud(l,0,2.4); op(l,ss(0.6,1.2,v));
    look(lerp(-1,1,ss(0,AT-WK,v)),0.8,7.4,0,0.2,0); rims(0xffc24a,0x4fe3ff,5); return; }
  // ATP：3500 多个粒子（问卷）汇成一颗球；2027
  const v=u-AT; const k=ss(0.6,4.5,v);
  for(let i=0;i<1600;i++){ const p=PTS[i]; const z=2*p[3]-1, a=p[4]*6.283, s=Math.sqrt(1-z*z); const tgt=V(s*Math.cos(a),z,s*Math.sin(a)); const st=V(p[0]*1.2,p[1]*1.1,p[2]); const e=ss(0,1,k*(1+p[3]*0.5)-p[3]*0.3); const P=st.lerp(tgt,e);
    cset(pt,i,P.x,P.y,P.z,0.6+0.4*e,0.9,1-0.6*e,0.8*(1-0.7*ss(0.85,1,k))); } cdone(pt);
  heroOp(hero,ss(3.6,4.6,v)); hero.g.rotation.set(0.2,v*0.5,0);
  const n=t3d('n3500','3500+','#c8f4ff',0.55); n.g.position.set(-3.2,1.7,0); t3op(n,ss(0.4,1,v)*(1-ss(ON-AT-0.4,ON-AT,v)));
  const l=tx('nA',T('ATP 2025 起统一挑球 · 3500 多份球员问卷','ATP centralised ball selection from 2025 · 3,500+ player surveys'),{color:'#ffffff',size:0.32}); hud(l,0,-2.5); op(l,ss(0.3,0.9,v)*(1-ss(ON-AT-0.4,ON-AT,v)));
  const y=t3d('y2027','2027','#ffd27a',0.7); y.g.position.set(2.8,1.6,0); t3op(y,ss(ON-AT,ON-AT+0.6,v));
  const l2=tx('nO',T('同一段赛季，只用一种球','One ball per stretch of the season'),{color:'#ffe2a0',size:0.38,glow:GOLD}); hud(l2,0,-2.5); op(l2,ss(ON-AT+0.2,ON-AT+0.8,v));
  look(Math.sin(v*0.3)*1.5,0.4,lerp(8,6.8,ss(0,D-AT,v)),0,0.2,0); rims(0xffc24a,0x4fe3ff,5); }

// ---------- 9 未来：数以亿计、填埋、碾进球场、巢鼠、两件事 ----------
function shotFuture(u,D){
  const PI_=ev('pile',0.5), FI=ev('fill',3.7), NO=ev('none',8.5), GR=ev('grind',13.6), NE=ev('nest',18.1), SP=ev('split',20.6), TW=ev('two',26.4);
  const dummy=new THREE.Object3D();
  if(u<GR-0.3){ pile.visible=true; pile.material.opacity=1; const k=ss(PI_,PI_+2.3,u); const sink=ss(FI,FI+2.5,u)*2.0;
    for(let i=0;i<PILE_N;i++){ const p=PILE[i]; const show=p[4]<k; const drop=show?Math.max(0,(1-ss(p[4]*2.3+PI_,p[4]*2.3+PI_+1.0,u)))*1.6:20;   /* 落差 6 → 1.6、每颗 1 s：1400 颗一起高速下落，motion_check 在 237–239 s 量到 22 */ dummy.position.set(p[0],p[1]+drop-sink,p[2]); dummy.rotation.set(p[3],p[3]*2,0); dummy.scale.setScalar(show?1:0.0001); dummy.updateMatrix(); pile.setMatrixAt(i,dummy.matrix); }
    pile.instanceMatrix.needsUpdate=true;
    if(u>FI-0.3){ layer.visible=true; layer.material.color.set(0x3a2a1c); layer.material.emissive.set(0x140a04); layer.position.set(0,lerp(-2,0.6,ss(FI,FI+2.5,u)),0); layer.material.opacity=0.95*ss(FI-0.3,FI+0.6,u); }   /* 淡入（原来整块突然出现，240.1 s 跳变 44） */
    const l=tx('fP',T('每年生产：数以亿计','Made every year: hundreds of millions'),{color:'#ffffff',size:0.44,plate:true}); hud(l,0,2.5); op(l,ss(PI_,PI_+0.6,u)*(1-ss(FI-0.3,FI,u)));
    const l2=tx('fF',T('橡胶和毛毡拆不开 · 大多填埋','Rubber and felt can\'t be separated · mostly landfill'),{color:'#ffd2a8',size:0.4,glow:RED,plate:true}); hud(l2,0,2.5); op(l2,ss(FI,FI+0.6,u)*(1-ss(NO-0.3,NO,u)));
    const l3=tx('fN',T('威尔逊 2023：职业标准、又能完全回收的球，还没有','Wilson, 2023: no fully recyclable ball meets elite specs yet'),{color:'#ffe2a0',size:0.38,glow:GOLD,plate:true}); hud(l3,0,2.5); op(l3,ss(NO,NO+0.6,u));
    look(lerp(14,10,ss(0,GR,u)),lerp(9,7,ss(0,GR,u)),lerp(14,11,ss(0,GR,u)),0,1,0); rims(0xffc24a,0xff5a4a,4); return; }
  if(u<SP-0.3){ // 碾碎：颗粒落下铺成球场底层；温网旧球给巢鼠做窝
    const v=u-GR;
    if(u<NE-0.3){ layer.visible=true; layer.material.color.set(0x1b5aa3); layer.material.emissive.set(0x082650); layer.position.set(0,-0.25,0); layer.scale.set(1,lerp(0.05,1,ss(0.5,3.5,v)),1); layer.material.opacity=1;
      for(let i=0;i<4000;i++){ const p=CR[i]; const life=(p[3]+v*0.4)%1; cset(crumbs,i,(p[0]-0.5)*14,lerp(6,0.1,life),(p[1]-0.5)*14,0.85,0.95,0.4,0.6*(1-ss(0.9,1,life))*ss(0,0.6,v)); } cdone(crumbs);
      /* 不再叠球场：球网是不透明的，跟着 v>1.5 一下子冒出来（251.2 s 跳变 49）；底层自己就是蓝色球场面 */
      const l=tx('fG',T('旧球碾碎，铺进球场底层','Old balls ground into a court\'s base layer'),{color:'#ffffff',size:0.38}); hud(l,0,2.5); op(l,ss(0.2,0.8,v));
      look(lerp(9,7,ss(0,NE-GR,v)),5,9,0,0,0); rims(0xd6ee3a,0x4fe3ff,4); return; }
    const w=u-NE; grass.visible=true; grass.material.opacity=1; nest.visible=true; nest.position.set(0,0.33,0); nest.rotation.y=-0.3+w*0.1; nest.scale.setScalar(3);
    const gl=gs(0xffd27a,1.2,0.5*ss(0.4,1.2,w)); gl.position.set(0.3,1.1,1.0);
    const l=tx('fNe',T('温网的旧球：给巢鼠做窝','Old Wimbledon balls: nests for harvest mice'),{color:'#c8ffe6',size:0.38,glow:MINT}); hud(l,0,2.5); op(l,ss(0.2,0.8,w));
    look(1.8,1.4,lerp(4.6,4,ss(0,SP-NE,w)),0,0.9,0); rims(0x34f5a8,0xffc24a,5); return; }
  // 张力：少用球、拉长间隔 ⟷ 换得更勤；最后两件事
  const v=u-SP; if(u<TW-0.3){ for(let r=0;r<2;r++){ const n=r?12:6; for(let i=0;i<=n;i++){ const t=ln(r?0xff7a3d:0x34f5a8,4); const x=-4+8*i/n; setLine(t,[V(x,0.8-r*1.6,0),V(x,1.3-r*1.6,0)]); t.material.opacity=ss(r*0.8,r*0.8+0.6,v); } const base=ln(0x9fd8ff,2); setLine(base,[V(-4,0.8-r*1.6,0),V(4,0.8-r*1.6,0)]); base.material.opacity=ss(r*0.8,r*0.8+0.6,v)*0.6; }
    const a=tx('fA',T('国际网联在研究：少用球、拉长间隔','ITF research: fewer balls, longer intervals'),{color:'#c8ffe6',size:0.32,glow:MINT}); a.position.set(0,1.8,0); op(a,ss(0,0.6,v));
    const b=tx('fB',T('有比赛在试：换得更勤','Some events are trialling more frequent changes'),{color:'#ffd2a8',size:0.32,glow:'rgba(255,122,61,0.9)'}); b.position.set(0,-1.35,0); op(b,ss(0.8,1.4,v));
    look(0,0.2,lerp(8.2,7.4,ss(0,TW-SP,v)),0,0.1,0); rims(0x34f5a8,0xff7a3d,4); return; }
  const w=u-TW; for(let i=0;i<5;i++){ const b=bl(); showB(b,V(-3.2+i*1.1,0.6,0),ss(i*0.1,i*0.1+0.4,w),1.8); }
  const loop=ln(0x34f5a8,4); arc(loop,V(0,-0.7,0),1.2,Math.PI*0.15,Math.PI*0.15+ss(1.2,2.4,w)*Math.PI*1.7,'z'); loop.material.opacity=ss(1.2,1.6,w);
  const t1=bt('fT1',T('每一颗都一样','Every ball the same'),{size:0.62,glow:GOLD,fx:'particles'}); hud(t1,-2.6,2.3); t1.update(w,0.2);
  const t2=bt('fT2',T('用完还能回去','And able to go back'),{size:0.62,glow:MINT,c1:'#a8ffd8',c2:'#7fe4ff',fx:'particles'}); hud(t2,2.6,2.3); t2.update(w,1.3);
  look(0,0.4,lerp(8,7.2,ss(0,D-TW,w)),0,0,0); rims(0xffc24a,0x34f5a8,5); }

// ---------- 10 片尾：三部曲拼图合上 ----------
function shotEnd(u,D){
  const TR=ev('tri',0.5), SR=ev('sr',3.5), BA=ev('ball',7.3), RU=ev('rule',11.3), QQ=ev('q',17.3);
  if(u<RU-0.3){ pzG.visible=true; pzG.rotation.y=Math.sin(u*0.4)*0.2; const gap=lerp(0.6,0,ss(TR,TR+1.6,u));
    const litB=ss(BA,BA+0.8,u); pz.forEach((m,i)=>{ m.position.x=(i-1)*(2.25+gap); m.material.opacity=1; m.material.emissiveIntensity=i===2?lerp(0.05,GLOW.emissive,litB):GLOW.emissive*(u<BA?1:0.55+0.45*(1-litB)); });
    const labs=[T('线','Strings'),T('拍','Racket'),T('球','Ball')]; labs.forEach((s,i)=>{ const t=tx('pz'+i,s,{color:'#ffffff',size:0.7}); t.position.set((i-1)*2.25,0,0.4); op(t,i===2?0.35+0.65*litB:ss(TR,TR+0.6,u)); });
    const a=tx('pzA',T('能把球打成什么样','What you can do with the ball'),{color:'#e0e8ff',size:0.34}); a.position.set(-1.12,-1.6,0.4); op(a,ss(SR,SR+0.6,u));
    const b=tx('pzB',T('这项运动按什么速度进行','How fast the game is played'),{color:'#c8ffe6',size:0.34,glow:MINT}); b.position.set(2.25,-1.6,0.4); op(b,ss(BA,BA+0.6,u));
    if(u>BA){ const gl=gs(0x34f5a8,4,0.4*litB); gl.position.set(2.25,0,0.3); }
    look(0,0.3,lerp(8.6,7.8,ss(0,RU,u)),0,0,0); rims(0xffc24a,0x34f5a8,5); return; }
  const v=u-RU; heroOp(hero,1); hero.g.position.set(-2.2,0.2,0); hero.g.rotation.set(0.3,u*0.5,0.1);
  for(let i=0;i<6;i++) specRing(i,V(-2.2,0.2,0),1.4+i*0.12,0.5+i*0.33,i*1.05+u*0.08,1,'',i%2?0x4fe3ff:0xffc24a);
  const R=rkA; rkOp(R,1); R.g.scale.setScalar(0.62); R.g.position.set(2.6,-0.4,0); R.g.rotation.y=Math.sin(u*0.4)*0.25;
  const t=bt('endR',T('管拍子只管尺寸；管球，管到每一克、每一厘米','The racket: size only. The ball: every gram, every centimetre'),{size:0.54,glow:GOLD,accent:T('每一克、每一厘米','every gram, every centimetre'),fx:'write'}); hud(t,0,2.5); t.update(v,0.1,QQ-RU-0.6);
  const q=bt('endQ',T('你打球，多久换一次新球？','How often do you open a new can?'),{size:0.78,glow:LIME,c1:'#eaff80',fx:'streak'}); hud(q,0,2.4); q.update(v,QQ-RU);   /* 疾驰：一颗新球飞进来 */
  if(v>QQ-RU){ const b=bl(); const k=ss(QQ-RU,QQ-RU+1.2,v); showB(b,V(lerp(-8,0,k),-1.3+Math.abs(Math.sin(k*8))*(1-k)*0.8,1.5),1,1.6); }
  look(0,0.4,lerp(9.6,8.8,ss(0,D-RU,v)),0,0.2,0); rims(0xffc24a,0x4fe3ff,5); beamMat.uniforms.uOp.value=0.08; }

// ---------- 段落配色（按情绪） ----------
Object.assign(PAL,{
  hook:  {top:0x05030f,hz:0x1a1048,vi:0x2a2a0a,a:0xd6ee3a},
  origin:{top:0x0b0602,hz:0x3a2208,vi:0x2a1406,a:0xffb347},
  make:  {top:0x0c0504,hz:0x3a1608,vi:0x0a2030,a:0xff7a3d},
  color: {top:0x050505,hz:0x2a2a10,vi:0x0a2a10,a:0xd6ee3a},
  impact:{top:0x030812,hz:0x0b2a50,vi:0x0a2030,a:0x4fe3ff},
  lab:   {top:0x03050c,hz:0x0c1a3a,vi:0x08202a,a:0x34f5a8},
  dial:  {top:0x0c0806,hz:0x3a2a08,vi:0x401018,a:0xffc24a},
  now:   {top:0x0c0306,hz:0x3a0d12,vi:0x2a0a2a,a:0xff5a4a},
  future:{top:0x020c0a,hz:0x063828,vi:0x062a2a,a:0x34f5a8},
  end:   {top:0x050505,hz:0x2a2008,vi:0x08202a,a:0xffc24a}});

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
  ({hook:shotHook,origin:shotOrigin,make:shotMake,color:shotColor,impact:shotImpact,lab:shotLab,dial:shotDial,now:shotNow,future:shotFuture,end:shotEnd})[sc.kind](u,D);
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
