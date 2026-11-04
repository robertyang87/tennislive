// vibetennis EP07「发球，该往哪边发？」——博弈论：两人零和博弈的混合策略均衡（极小极大定理＝纳什均衡）
// 第 2 版（2026-11-04 所有者第二轮意见）：开场先抛问题、立刻抛原理；写实手部骨骼模型打石头剪刀布；
// Mixamo X Bot 球员；配色按段落情绪变化；用上 three.js 库里的景深、粗光线、镜头光晕、3D 立体数字、体积光。
// 球场尺寸按 ITF 标准；矩阵、比分树里的形状是示意。上屏数字的出处见 papers/vibetennis-serve-nash-2026/sources.md
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';
import { Lensflare, LensflareElement } from 'three/addons/objects/Lensflare.js';
import { FontLoader } from 'three/addons/loaders/FontLoader.js';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';
import { TL } from './shots.js';
import { rigHand } from './hand_pose.js';
import { makePlayer, READY_KEY } from './players.js';

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

// ---------- 段落配色（按情绪，不再只用金蓝） ----------
const PAL={
  hook:    {top:0x05030f,hz:0x1a1048,vi:0x3a0a3a,a:0x30e8ff,b:0xff3fd0,c:0x34f5a8},   // 电光青＋品红 → 翡翠
  arena:   {top:0x020814,hz:0x0b2a50,vi:0x0a2030,a:0xe8f6ff,b:0x4fe3ff,c:0xffffff},   // 冰白＋青
  pile:    {top:0x0c0306,hz:0x3a0d12,vi:0x401018,a:0xff5a4a,b:0xffb199,c:0xffffff},   // 警示珊瑚红
  theory:  {top:0x06041a,hz:0x1d1250,vi:0x2b0d55,a:0xa78bfa,b:0x6fa8ff,c:0xf0e6ff},   // 紫罗兰＋星蓝
  balance: {top:0x020c0a,hz:0x063828,vi:0x062a2a,a:0x34f5a8,b:0x4fe3ff,c:0xeafff6},   // 翡翠＋青
  rain:    {top:0x0b0802,hz:0x3a2608,vi:0x2a1a04,a:0xffbf47,b:0xd8f2ff,c:0xffffff},   // 琥珀＋冰白
  keypoints:{top:0x0c0504,hz:0x3a1608,vi:0x0a3024,a:0xff7a3d,b:0x34f5a8,c:0xffffff},  // 橙红＋翡翠（关键分）
  chains:  {top:0x0d0310,hz:0x3a0a32,vi:0x3a1a08,a:0xff4fd8,b:0xff9b3d,c:0xffffff},   // 洋红＋橙
  latest:  {top:0x04040e,hz:0x14163a,vi:0x1a1a2e,a:0xf2efe6,b:0x7c83ff,c:0xffffff},   // 白金＋靛
  coin:    {top:0x050505,hz:0x2a2008,vi:0x08202a,a:0xffc24a,b:0x4fe3ff,c:0xffffff}};  // 金＋青

// ---------- 背景：夜空（颜色随段落）、星点、微尘、全息地网 ----------
const skyMat=new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,uniforms:{uTop:{value:C(0x05030f)},uHz:{value:C(0x1a1048)},uVi:{value:C(0x3a0a3a)}},
  vertexShader:`varying vec3 vD; void main(){ vD=normalize(position); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,
  fragmentShader:`varying vec3 vD; uniform vec3 uTop,uHz,uVi; void main(){ float h=vD.y; float g=exp(-abs(h+0.02)*6.0); float side=0.5+0.5*vD.x; gl_FragColor=vec4(uTop+uHz*g+uVi*g*g*side*0.8,1.);} `});
const sky=new THREE.Mesh(new THREE.SphereGeometry(9000,48,24),skyMat); sky.frustumCulled=false; scene.add(sky);
const glowTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d');
  const gr=g.createRadialGradient(64,64,0,64,64,64); gr.addColorStop(0,'rgba(255,255,255,1)'); gr.addColorStop(0.15,'rgba(255,255,255,0.6)'); gr.addColorStop(0.45,'rgba(255,255,255,0.12)'); gr.addColorStop(1,'rgba(255,255,255,0)');
  g.fillStyle=gr; g.fillRect(0,0,128,128); return new THREE.CanvasTexture(c); })();
function glowSprite(color,size,op=1,group=scene){ const s=new THREE.Sprite(new THREE.SpriteMaterial({map:glowTex,color,transparent:true,opacity:op,blending:THREE.AdditiveBlending,depthWrite:false})); s.scale.set(size,size,1); group.add(s); return s; }
const ringTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=256; const g=c.getContext('2d'); g.strokeStyle='white';
  g.lineWidth=9; g.beginPath(); g.arc(128,128,104,0,Math.PI*2); g.stroke(); g.globalAlpha=0.35; g.lineWidth=3; g.beginPath(); g.arc(128,128,122,0,Math.PI*2); g.stroke(); return new THREE.CanvasTexture(c); })();
function flatRing(color,group=scene){ const m=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({map:ringTex,color,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide})); m.rotation.x=-Math.PI/2; group.add(m); return m; }
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
function textSprite(str,{color='#ffffff',size=1,font='700 120px "Noto Sans CJK SC","Inter",sans-serif',glow='rgba(120,200,255,0.9)'}={},group=scene){
  const c=document.createElement('canvas'); const g=c.getContext('2d'); g.font=font; const w=Math.ceil(g.measureText(str).width)+80; c.width=w; c.height=200;
  g.font=font; g.textAlign='center'; g.textBaseline='middle'; g.shadowColor=glow; g.shadowBlur=30; g.fillStyle=color; g.fillText(str,w/2,104); g.shadowBlur=0; g.fillText(str,w/2,104);
  const tex=new THREE.CanvasTexture(c); tex.colorSpace=THREE.SRGBColorSpace;
  const s=new THREE.Sprite(new THREE.SpriteMaterial({map:tex,transparent:true,depthWrite:false,opacity:0})); s.scale.set(size*w/200,size,1); group.add(s); return s; }
const op=(s,v)=>{ s.material.opacity=v; };
let FONT=null; const FONT_READY=new Promise(res=>new FontLoader().load('./node_modules/three/examples/fonts/helvetiker_bold.typeface.json',f=>{ FONT=f; res(); }));
const text3D={};
function t3d(key,str,color,size=1,group=scene){ // 3D 立体数字：金属挤出＋发光描边
  if(text3D[key]) return text3D[key];
  const geo=new TextGeometry(str,{font:FONT,size,depth:size*0.22,curveSegments:8,bevelEnabled:true,bevelThickness:size*0.04,bevelSize:size*0.025,bevelSegments:3}); geo.center();
  const m=new THREE.Mesh(geo,new THREE.MeshPhysicalMaterial({color:0x0c1018,metalness:0.9,roughness:0.18,clearcoat:1,emissive:C(color),emissiveIntensity:0.9,transparent:true,opacity:0}));
  const e=new THREE.LineSegments(new THREE.EdgesGeometry(geo,30),new THREE.LineBasicMaterial({color,transparent:true,opacity:0,blending:THREE.AdditiveBlending})); m.add(e);
  const g=new THREE.Group(); g.add(m); group.add(g); text3D[key]={g,m,e}; return text3D[key]; }
function t3op(o,v){ o.m.material.opacity=v; o.e.material.opacity=v*0.8; o.g.visible=v>0.003; }

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
  const band=new THREE.Mesh(new THREE.BoxGeometry(DW*2+1.8,0.07,0.02),new THREE.MeshStandardMaterial({color:0xffffff,emissive:0xffffff,emissiveIntensity:0.6})); band.position.set(0,0.99,0); net.add(band);
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

// ---------- 球（带镜头光晕） ----------
const ball=new THREE.Mesh(new THREE.SphereGeometry(0.075,32,20),new THREE.MeshPhysicalMaterial({color:0xd8f040,emissive:0x6a7a10,roughness:0.7,sheen:1,sheenColor:new THREE.Color(0xf6ff9a)})); scene.add(ball);
const ballGlow=glowSprite(0xeaff80,0.8,0.8);
const flareTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d'); const gr=g.createRadialGradient(64,64,0,64,64,64); gr.addColorStop(0,'rgba(255,255,255,0.9)'); gr.addColorStop(0.3,'rgba(255,255,255,0.25)'); gr.addColorStop(1,'rgba(255,255,255,0)'); g.fillStyle=gr; g.fillRect(0,0,128,128); return new THREE.CanvasTexture(c); })();
const hexTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d'); g.fillStyle='rgba(255,255,255,0.35)'; g.beginPath(); for(let i=0;i<6;i++){ const a=i/6*Math.PI*2; g.lineTo(64+56*Math.cos(a),64+56*Math.sin(a)); } g.fill(); return new THREE.CanvasTexture(c); })();
const flare=new Lensflare(); flare.addElement(new LensflareElement(flareTex,300,0,new THREE.Color(0xeaffff))); flare.addElement(new LensflareElement(hexTex,60,0.4,new THREE.Color(0xff4fd8))); flare.addElement(new LensflareElement(hexTex,90,0.7,new THREE.Color(0x30e8ff))); flare.addElement(new LensflareElement(hexTex,40,1.0,new THREE.Color(0x34f5a8)));
const flareLight=new THREE.PointLight(0xffffff,0,1); flareLight.add(flare); scene.add(flareLight);
const TRAIL=36, trail=cloud(TRAIL,0.12,30);
const SP=new THREE.Vector3(1.05,2.75,L+0.15);              // 击球点（平分区，发球人站在中点右侧）
const TGT={wide:new THREE.Vector3(-SW+0.35,0,-SL+0.55), T:new THREE.Vector3(-0.35,0,-SL+0.55), body:new THREE.Vector3(-SW/2-0.2,0,-SL+0.9)};
function serveAt(tg,tau){ // tau 0→1 飞到落点，1→1.7 弹起飞向接发人
  if(tau<=1){ const x=lerp(SP.x,tg.x,tau), z=lerp(SP.z,tg.z,tau); const y=SP.y*(1-tau)+0.32*Math.sin(Math.PI*tau); return new THREE.Vector3(x,y,z); }
  const k=(tau-1)/0.7; const dir=new THREE.Vector3(tg.x-SP.x,0,tg.z-SP.z).normalize();
  return new THREE.Vector3(tg.x+dir.x*k*5.5,1.15*Math.sin(Math.PI*0.62*k),tg.z+dir.z*k*5.5); }
function showBall(p,vis=true){ ball.visible=vis; ballGlow.visible=vis; if(!vis) return; ball.position.copy(p); ballGlow.position.copy(p); }
function setTrail(fn,tau,col=[0.9,1,0.5],vis=true){ if(!vis){ chide(trail); return; } for(let i=0;i<TRAIL;i++){ const tt=tau-i*0.025; if(tt<0){ cset(trail,i,0,-99,0,0,0,0,0); continue; } const p=fn(tt); const a=(1-i/TRAIL)*0.85; cset(trail,i,p.x,p.y,p.z,col[0],col[1],col[2],a);} cdone(trail); }

// ---------- 球员（X Bot）与手（generic-hand），模型加载后建 ----------
let server=null, receiver=null, ghosts=[], handL=null, handR=null;
const MODELS_READY=Promise.all([
  new Promise((res,rej)=>new GLTFLoader().load('models/male_base.glb',res,undefined,rej)),
  new Promise((res,rej)=>new GLTFLoader().load('models/hand_left.glb',res,undefined,rej)),
  new Promise((res,rej)=>new GLTFLoader().load('models/hand_right.glb',res,undefined,rej))]).then(([bot,hl,hr])=>{
  server=makePlayer(bot,0xffb347,scene); receiver=makePlayer(bot,0x4fe3ff,scene);
  ghosts=[0,1,2].map(i=>{ const g=makePlayer(bot,0x4fe3ff,scene); g.g.traverse(o=>{ if(o.isMesh&&o.material&&!o.material.wireframe){ o.material=o.material.clone(); o.material.transparent=true; o.material.opacity=0.32/(i+1); o.material.depthWrite=false; } }); return g; });
  const mkHand=(gl,col)=>{ const h=SkeletonUtils.clone(gl.scene); const holder=new THREE.Group(); const inner=new THREE.Group(); inner.add(h); holder.add(inner); scene.add(holder);
    const mat=new THREE.MeshPhysicalMaterial({color:0x101828,metalness:0.55,roughness:0.18,clearcoat:1,iridescence:1,iridescenceIOR:1.6,emissive:C(col),emissiveIntensity:0.35});
    const wire=new THREE.MeshBasicMaterial({color:col,wireframe:true,transparent:true,opacity:0.12,blending:THREE.AdditiveBlending,depthWrite:false});
    h.traverse(o=>{ if(o.isSkinnedMesh){ o.material=mat; o.frustumCulled=false; const w=new THREE.SkinnedMesh(o.geometry,wire); w.bind(o.skeleton,o.bindMatrix); w.frustumCulled=false; o.parent.add(w); } });
    h.updateMatrixWorld(true); const rig=rigHand(h);
    const up=rig.B['middle-finger-tip'].getWorldPosition(new THREE.Vector3()).sub(rig.B['wrist'].getWorldPosition(new THREE.Vector3())).normalize();
    inner.quaternion.setFromUnitVectors(up,new THREE.Vector3(0,1,0)); inner.updateMatrixWorld(true);
    const n=rig.normal.clone().transformDirection(rig.B['Armature'].matrixWorld); inner.rotateOnWorldAxis(new THREE.Vector3(0,1,0),-Math.atan2(n.x,n.z));
    const wr=rig.B['wrist'].getWorldPosition(new THREE.Vector3()); inner.position.sub(wr);
    holder.scale.setScalar(9); return {holder,rig,mat}; };
  handL=mkHand(hl,0xa78bfa); handR=mkHand(hr,0x6fa8ff);
});

// ---------- 段 1：开场的准星、分叉轨迹、天平、标题 ----------
const pathWide=fatLine(0x30e8ff,11,true), pathT=fatLine(0xff3fd0,11,true);
const reticle=new THREE.Group(); scene.add(reticle);
{ const m=new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:0.9,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide});
  reticle.add(new THREE.Mesh(new THREE.RingGeometry(0.42,0.47,48),m)); for(let i=0;i<4;i++){ const b=new THREE.Mesh(new THREE.PlaneGeometry(0.05,0.28),m); b.position.set(Math.cos(i*Math.PI/2)*0.62,Math.sin(i*Math.PI/2)*0.62,0); b.rotation.z=i*Math.PI/2; reticle.add(b); }
  reticle.userData.m=m; }
const hookQ=textSprite(T('发球，该往哪边发？','Where should you serve?'),{color:'#ffffff',size:0.9,glow:'rgba(255,80,220,0.9)'});
const hookTitle=textSprite(T('纳什均衡','Nash equilibrium'),{color:'#effffa',size:1.25,font:'900 150px "Noto Sans CJK SC","Inter",sans-serif',glow:'rgba(52,245,168,0.75)'});
const hookSub=textSprite(T('让对手往哪边猜都不占便宜','Leave the returner no good guess'),{color:'#eafff6',size:0.62,glow:'rgba(52,245,168,0.9)'});
const levelBar=fatLine(0x34f5a8,5); const shock=flatRing(0xffffff); const shock2=flatRing(0x34f5a8);
const cornerGlow={wide:flatRing(0x30e8ff),T:flatRing(0xff3fd0)};

// ---------- 段 3：落点堆积 ----------
const pileDots=cloud(60,0.45,60); const pileRing=[0,1,2,3,4,5].map(()=>flatRing(0xff5a4a));

// ---------- 段 4：年份光环、2×2 玻璃方块、最佳应对螺旋 ----------
const yearG=new THREE.Group(); scene.add(yearG);
const YEARS=[['1928',T('冯·诺依曼 · 极小极大定理','von Neumann · Minimax theorem')],['1950',T('纳什 · 纳什均衡','Nash · Nash equilibrium')],['1994',T('诺贝尔经济学奖','Nobel Prize in Economics')]];
const yearRings=YEARS.map(([y,sub],i)=>{ const g=new THREE.Group(); yearG.add(g);
  const r=new THREE.Mesh(new THREE.TorusGeometry(9+i*1.6,0.07,10,180),new THREE.MeshBasicMaterial({color:[0xa78bfa,0x6fa8ff,0xf0e6ff][i],transparent:true,opacity:0,blending:THREE.AdditiveBlending})); r.rotation.x=Math.PI/2; g.add(r);
  const sl=textSprite(sub,{color:'#ece6ff',size:0.62,glow:'rgba(167,139,250,0.9)'},g); g.userData={r,sl,i,y}; return g; });
const matG=new THREE.Group(); scene.add(matG);
const CUBE_LV=[[0.48,0.80],[0.74,0.56]]; // 示意（不上数字）：发外角／中路 × 接发猜外角／中路 时发球方赢下这一分的概率高低
const cubes=[]; for(let s=0;s<2;s++) for(let r=0;r<2;r++){ const g=new THREE.Group(); matG.add(g);
  g.add(new THREE.Mesh(new THREE.BoxGeometry(2.2,2.2,2.2),new THREE.MeshPhysicalMaterial({color:0xc9b8ff,transparent:true,opacity:0.1,roughness:0.05,metalness:0.1,clearcoat:1,side:THREE.DoubleSide,depthWrite:false})));
  g.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(2.2,2.2,2.2)),new THREE.LineBasicMaterial({color:0xd8ccff,transparent:true,opacity:0.85,blending:THREE.AdditiveBlending})));
  const liq=new THREE.Mesh(new THREE.BoxGeometry(2.0,2.0,2.0),new THREE.MeshPhysicalMaterial({color:s===0?0xa78bfa:0x6fa8ff,emissive:s===0?0x4a2a9a:0x1a4a9a,emissiveIntensity:1.0,transparent:true,opacity:0.7,roughness:0.15,clearcoat:1})); liq.geometry.translate(0,1.0,0); liq.position.y=-1.0; g.add(liq);
  g.userData={liq,s,r,lv:CUBE_LV[s][r]}; cubes.push(g); }
const matLabels=[T('发外角','Serve wide'),T('发中路','Serve T'),T('猜外角','Guess wide'),T('猜中路','Guess T')].map((s,i)=>textSprite(s,{color:i<2?'#e8dcff':'#d6e6ff',size:0.75,glow:i<2?'rgba(167,139,250,0.9)':'rgba(111,168,255,0.9)'},matG));
const matNote=textSprite(T('示意','Illustration'),{color:'#a99fd0',size:0.4},matG);
const brPanel=new THREE.Group(); scene.add(brPanel); // 最佳应对螺旋：横轴＝发球人发外角的比例，纵轴＝接发人猜外角的比例
{ const fr=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(4,4)),new THREE.LineBasicMaterial({color:0xd8ccff,transparent:true,opacity:0.7})); brPanel.add(fr);
  const bg=new THREE.Mesh(new THREE.PlaneGeometry(4,4),new THREE.MeshBasicMaterial({color:0x1a1040,transparent:true,opacity:0.35,depthWrite:false})); brPanel.add(bg); }
const brPath=fatLine(0xf0e6ff,4); const brDot=glowSprite(0xffffff,0.9,1,brPanel); const brStar=glowSprite(0x34f5a8,1.6,0,brPanel);
const brLabX=textSprite(T('发外角的比例 →','Share of wide serves →'),{color:'#d8ccff',size:0.36},brPanel), brLabY=textSprite(T('接发猜外角 →','Returner guesses wide →'),{color:'#d8ccff',size:0.36},brPanel);
const brEq=textSprite(T('均衡点','Equilibrium'),{color:'#c9ffe9',size:0.5,glow:'rgba(52,245,168,1)'},brPanel);
const rpsLabel=textSprite(T('总出石头？','Always rock?'),{color:'#ffe9a8',size:0.7,glow:'rgba(255,190,80,0.9)'});
const rpsWin=flatRing(0xa78bfa);

// ---------- 段 5：天平 ----------
const balG=new THREE.Group(); scene.add(balG);
const metal=new THREE.MeshPhysicalMaterial({color:0xd9fff2,metalness:0.9,roughness:0.18,clearcoat:1,emissive:0x0a3a2a,emissiveIntensity:0.6});
const post=new THREE.Mesh(new THREE.CylinderGeometry(0.09,0.14,3.2,24),metal); post.position.y=1.6; balG.add(post);
const beam=new THREE.Group(); beam.position.y=3.25; balG.add(beam); beam.add(new THREE.Mesh(new THREE.BoxGeometry(8.4,0.09,0.12),metal)); glowSprite(0xffffff,0.8,0.8,beam);
const pans=[-1,1].map(s=>{ const g=new THREE.Group(); g.position.x=s*4.1; beam.add(g);
  const ch=new THREE.Mesh(new THREE.CylinderGeometry(0.008,0.008,0.9,4),metal); ch.position.y=-0.45; g.add(ch);
  const pan=new THREE.Mesh(new THREE.CylinderGeometry(0.9,0.75,0.08,48),metal); pan.position.y=-0.92; g.add(pan);
  const col=new THREE.Mesh(new THREE.CylinderGeometry(0.42,0.42,1,40,1,true),new THREE.MeshBasicMaterial({color:s<0?0x34f5a8:0x4fe3ff,transparent:true,opacity:0.38,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,depthWrite:false}));
  col.geometry.translate(0,0.5,0); col.position.y=-0.88; g.add(col);
  const cap=glowSprite(s<0?0x34f5a8:0x4fe3ff,1.2,0.9,g);
  const name=textSprite(s<0?T('外角 4,111 个','Wide: 4,111'):T('中路 2,479 个','T: 2,479'),{color:'#e6fff6',size:0.5},g);
  return {g,col,cap,name,s}; });
const balDots=cloud(84,0.3,40,balG); const BAL={nL:52,nR:32,rL:0.697,rR:0.711}; /* 52:32 ≈ 4,111:2,479；得分率 69.7% vs 71.1% */ const levelFlash=flatRing(0xffffff,balG);
const balTitle=textSprite(T('辛纳 · 2023–2026 · 占先区一发','Sinner · 2023–26 · ad-court first serves'),{color:'#e6fff6',size:0.55},balG);

// ---------- 段 6：光点暴雨（三个年代） ----------
const RAIN_N=24000; const rain=cloud(RAIN_N,0.07,6,scene,0.15); const RAIN=[]; let RAIN_MODE=null;
function setupRain(mode){ if(RAIN_MODE===mode) return; RAIN_MODE=mode; RAIN.length=0; fseed=mode==='ww'?101:mode==='hawk'?202:303;
  const n=mode==='ww'?3026:RAIN_N;
  for(let i=0;i<n;i++){ const courtSide=frnd()<0.5?1:-1; const wide=mode==='ww'?(i<1622):(frnd()<0.5);
    const bx=courtSide>0?(wide?-SW+0.45:-0.45):(wide?SW-0.45:0.45);
    RAIN.push([bx+gauss()*0.32,clamp(-SL+0.7+gauss()*0.55,-SL+0.05,-0.3),frnd()*0.85,wide?1:0,(frnd()-0.5)*6,18+frnd()*14]); } }
const rainCols=[0,1].map(i=>{ const g=new THREE.Group(); scene.add(g);
  const col=new THREE.Mesh(new THREE.CylinderGeometry(0.55,0.55,1,40,1,true),new THREE.MeshBasicMaterial({color:i===0?0xffbf47:0xd8f2ff,transparent:true,opacity:0.34,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,depthWrite:false}));
  col.geometry.translate(0,0.5,0); g.add(col); const cap=glowSprite(i===0?0xffbf47:0xd8f2ff,1.6,0.9,g); const ring=flatRing(i===0?0xffbf47:0xd8f2ff,g); ring.scale.set(1.6,1.6,1);
  return {g,col,cap,ring}; });
const ERA={ww:{v:[0.64,0.65],lab:[T('发左 64%','Left 64%'),T('发右 65%','Right 65%')],title:T('1974–1997 · 10 场录像 · 3,026 个一发','1974–1997 · 10 matches · 3,026 first serves')},
  hawk:{v:[0.65,0.65],lab:null,title:T('鹰眼 2005–2009 · 3,172 场 · 近 50 万个发球 · 男子吻合','Hawk-Eye 2005–09 · 3,172 matches · ~500k serves · men fit')},
  now:{v:[0.650,0.647],lab:[T('外角 65.0%','Wide 65.0%'),T('中路 64.7%','T 64.7%')],title:T('2023–2026 · 2,151 场男子比赛 · 33.7 万个一发','2023–26 · 2,151 men’s matches · 337k first serves')}};
for(const k in ERA){ ERA[k].titleS=textSprite(ERA[k].title,{color:'#fff4dc',size:0.55,glow:'rgba(255,191,71,0.9)'}); ERA[k].labS=ERA[k].lab?ERA[k].lab.map((s,i)=>textSprite(s,{color:i?'#e6f6ff':'#ffe2a0',size:0.8,glow:i?'rgba(200,235,255,1)':'rgba(255,191,71,1)'})):null; }
const TILES=1056, TILE_REJ=56; const tileG=new THREE.Group(); scene.add(tileG); // 1,056 个发球局面，56 个在 5% 水平被拒绝（5.3%）
const tileMesh=new THREE.InstancedMesh(new THREE.BoxGeometry(0.16,0.16,0.04),new THREE.MeshStandardMaterial({color:0xffffff,emissive:0xffffff,emissiveIntensity:0.12,metalness:0.3,roughness:0.4}),TILES); tileG.add(tileMesh);
const TILE_ORDER=(()=>{ fseed=777; const a=[...Array(TILES).keys()]; for(let i=a.length-1;i>0;i--){ const j=Math.floor(frnd()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; } return a; })();
const tileBack=new THREE.Mesh(new THREE.PlaneGeometry(9.0,5.1),new THREE.MeshBasicMaterial({color:0x07060a,transparent:true,opacity:0.92,depthWrite:false})); tileBack.position.z=-0.05; tileG.add(tileBack);
const tileTitle=textSprite(T('1,056 个发球局面 · 偏离理论的只有 5.3%','1,056 server–returner matchups · only 5.3% deviate'),{color:'#fff4dc',size:0.5,glow:'rgba(255,191,71,0.9)'},tileG);
const tileNote=textSprite(T('纯随机也会有约 5%','~5% expected by pure chance'),{color:'#e8f6ff',size:0.4},tileG);
const yearCache={}; function yearSprite(y){ if(!yearCache[y]) yearCache[y]=textSprite(String(y),{color:'#fff4dc',size:1.2,font:'800 140px "Inter",sans-serif',glow:'rgba(255,191,71,1)'}); return yearCache[y]; }

// ---------- 段 7：关键分 ----------
const weakZone=new THREE.Mesh(new THREE.PlaneGeometry(SW,SL-0.2),new THREE.MeshBasicMaterial({color:0xff7a3d,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false})); weakZone.rotation.x=-Math.PI/2; scene.add(weakZone);
const kpBars=new THREE.Group(); scene.add(kpBars); // 一发比例条：外角｜追身｜中路
const kpSeg=[0xff7a3d,0x9aa4b4,0x34f5a8].map(c=>{ const m=new THREE.Mesh(new THREE.BoxGeometry(1,0.32,0.12),new THREE.MeshStandardMaterial({color:c,emissive:c,emissiveIntensity:0.9,metalness:0.2,roughness:0.3})); kpBars.add(m); return m; });
const kpLabs=[textSprite(T('其他分','Other points'),{color:'#ffe6d8',size:0.45},kpBars),textSprite(T('破发点','Break point'),{color:'#ffd2bc',size:0.5,glow:'rgba(255,122,61,1)'},kpBars)];
const kpNums=[[0.483,0.085,0.432],[0.505,0.081,0.414]];
const kpNumS=[textSprite(T('外角 48.3% → 50.5%','Wide 48.3% → 50.5%'),{color:'#ffd2bc',size:0.5,glow:'rgba(255,122,61,1)'},kpBars),textSprite(T('二发打反手 69.0% → 71.6%','2nd serves to backhand 69.0% → 71.6%'),{color:'#ffd2bc',size:0.5,glow:'rgba(255,122,61,1)'},kpBars)];
const kpWin=[textSprite(T('外角 61.8%','Wide 61.8%'),{color:'#ffd2bc',size:1.3,glow:'rgba(255,122,61,1)'}),textSprite(T('中路 62.0%','T 62.0%'),{color:'#c9ffe9',size:1.3,glow:'rgba(52,245,168,1)'})];
const kpTitle=textSprite(T('关键分上，理论还成立吗？','Does it still hold on the big points?'),{color:'#fff0e6',size:0.7,glow:'rgba(255,122,61,1)'});
const kpOpen=flatRing(0x34f5a8);
const KP_DATA=[ // 2023–26 男子一发，外角 vs 中路得分率；上排＝发球方自己的关键分，下排＝对手的关键分（发球方在挽救）
  [T('局点','Game point'),[0.662,0.659],'66.2% · 65.9%',null],[T('盘点','Set point'),[0.678,0.683],'67.8% · 68.3%',null],[T('赛点','Match point'),[0.683,0.667],'68.3% · 66.7%',null],
  [T('破发点','Break point'),[0.618,0.620],'61.8% · 62.0%',null],[T('对手盘点','Opp. set point'),[0.608,0.619],'60.8% · 61.9%',null],[T('对手赛点','Opp. match point'),[0.626,0.572],'62.6% · 57.2%',T('样本小 · 差别不显著','small sample · not significant')]];
const KP=KP_DATA.map(([nm,v,txt,note])=>{ const g=new THREE.Group(); scene.add(g);
  const panel=new THREE.Mesh(new THREE.PlaneGeometry(3.0,3.6),new THREE.MeshBasicMaterial({color:0x2a1206,transparent:true,opacity:0,depthWrite:false})); panel.position.y=1.5; g.add(panel);
  const fr=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(3.0,3.6)),new THREE.LineBasicMaterial({color:0xffb08a,transparent:true,opacity:0.6})); fr.position.y=1.5; g.add(fr);
  const cols=[0,1].map(j=>{ const m=new THREE.Mesh(new THREE.CylinderGeometry(0.36,0.36,1,40,1,true),new THREE.MeshBasicMaterial({color:j?0x34f5a8:0xff7a3d,transparent:true,opacity:0.5,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,depthWrite:false})); m.geometry.translate(0,0.5,0); m.position.set(j?0.55:-0.55,0.1,0.05); g.add(m); return m; });
  const caps=[0,1].map(j=>{ const c=glowSprite(j?0x34f5a8:0xff7a3d,0.9,0,g); c.position.x=j?0.55:-0.55; return c; });
  const name=textSprite(nm,{color:'#fff0e6',size:0.55,glow:'rgba(255,122,61,1)'},g); name.position.set(0,3.6,0.1);
  const vals=textSprite(txt,{color:'#ffffff',size:0.5,font:'800 120px "Inter",sans-serif'},g); vals.position.set(0,-0.35,0.1);
  const nt=note?textSprite(note,{color:'#ffcfb8',size:0.3},g):null; if(nt) nt.position.set(0,-0.85,0.1);
  return {g,panel,cols,caps,name,vals,note:nt,v}; });
const kpRowLab=[textSprite(T('发球方自己的关键分','The server’s own big points'),{color:'#ffd9c4',size:0.45},),textSprite(T('对手的关键分（发球方在挽救）','The returner’s big points (server saving)'),{color:'#ffd9c4',size:0.45})];
const kpLegend=textSprite(T('橙＝外角　绿＝中路　· 2023–2026 男子一发得分率','Orange = wide · Green = T · men’s first-serve win rates 2023–26'),{color:'#ffe6d8',size:0.4});

// ---------- 段 8：换边珠链 ----------
const chainG=new THREE.Group(); scene.add(chainG);
const BEADS=60; const beadGeo=new THREE.SphereGeometry(0.22,24,16);
function makeSeq(pSwitch,seed){ fseed=seed; const s=[frnd()<0.5?1:0]; for(let i=1;i<BEADS+40;i++) s.push(frnd()<pSwitch?1-s[i-1]:s[i-1]); return s; }
const SEQ=[makeSeq(0.5,913),makeSeq(0.582,4242)]; // 下：上一个发右、下一个还发右只有 41.8%（男子，GPW 2023）→ 换边概率 0.582
const chains=SEQ.map((seq,row)=>{ const beads=[]; for(let i=0;i<BEADS+40;i++){ const c=seq[i]?0xff4fd8:0xff9b3d; const m=new THREE.Mesh(beadGeo,new THREE.MeshPhysicalMaterial({color:c,emissive:c,emissiveIntensity:0.7,roughness:0.15,clearcoat:1,metalness:0.2})); chainG.add(m); beads.push(m); }
  const line=fatLine(row?0xff6fe0:0xffffff,2.5); return {beads,line,seq,row}; });
const chainLabs=[textSprite(T('真随机（抛硬币）','Truly random (coin)'),{color:'#ffe8f8',size:0.6},chainG),textSprite(T('职业球员','Pro servers'),{color:'#ffd0f0',size:0.6,glow:'rgba(255,79,216,0.9)'},chainG)];
const chainStat=textSprite(T('上一个发右，下一个还发右：41.8%（真随机 50%）','Right again after a right: 41.8% (random: 50%)'),{color:'#ffe2f4',size:0.6,glow:'rgba(255,79,216,0.9)'},chainG);
const scan=new THREE.Mesh(new THREE.PlaneGeometry(0.12,6),new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:0.5,blending:THREE.AdditiveBlending,depthWrite:false})); chainG.add(scan);

// ---------- 段 9：比分树＋保发率仪表 ----------
const treeG=new THREE.Group(); scene.add(treeG);
const NODES=[]; for(let a=0;a<=3;a++) for(let b=0;b<=3;b++){ const m=new THREE.Mesh(new THREE.SphereGeometry(0.22,24,16),new THREE.MeshPhysicalMaterial({color:0x1a1c3a,emissive:0x7c83ff,emissiveIntensity:0.2,metalness:0.4,roughness:0.2,clearcoat:1})); m.position.set((a-b)*1.25,(a+b)*1.0-0.5,0); treeG.add(m); NODES.push({m,a,b}); }
const treeEdges=fatLine(0x7c83ff,1.5); const treeFan=[0,1,2].map(i=>fatLine([0xff7a3d,0x9aa4b4,0x34f5a8][i],3));
const SCORE=['0','15','30','40'];
const nodeLabs=NODES.map(n=>textSprite(`${SCORE[n.a]}-${SCORE[n.b]}`,{color:'#e8e8ff',size:0.3,font:'700 110px "Inter",sans-serif'},treeG));
const gauge=new THREE.Mesh(new THREE.TorusGeometry(1.6,0.09,12,128,0.01),new THREE.MeshBasicMaterial({color:0xf2efe6,transparent:true,opacity:0,blending:THREE.AdditiveBlending})); scene.add(gauge);
const gaugeBg=new THREE.Mesh(new THREE.TorusGeometry(1.6,0.05,8,128),new THREE.MeshBasicMaterial({color:0x2a2d55,transparent:true,opacity:0})); scene.add(gaugeBg);
const latestTitle=textSprite(T('2025 · 把比分算进去的新研究','2025 · A study that adds the score'),{color:'#f2efe6',size:0.55,glow:'rgba(124,131,255,1)'});
// 所有者 2026-11-04：上屏的东西一定要经过验证——JPE 的 71%→91.5% 是「对手不调整」的模型推算、没有实地验证，不上屏；只上统计检验的结论
const latestRes=[textSprite(T('把比分和追身也算进来检验','Test with the score and body serves included'),{color:'#e8e9ff',size:0.5}),textSprite(T('费德勒、纳达尔、德约科维奇等多数顶尖球员','Federer, Nadal, Djokovic and most elite servers'),{color:'#f2efe6',size:0.55,glow:'rgba(124,131,255,1)'}),textSprite(T('都没有完全做到均衡','do not fully play the equilibrium'),{color:'#ffffff',size:0.75,glow:'rgba(124,131,255,1)'})];
const latestSub=textSprite('',{size:0.1});
const latestNote=textSprite(T('比分树为示意','Score tree is illustrative'),{color:'#8f93c8',size:0.32});

// ---------- 段 10：硬币 ----------
const coinTex=(s,col)=>{ const c=document.createElement('canvas'); c.width=c.height=256; const g=c.getContext('2d'); g.fillStyle=col; g.beginPath(); g.arc(128,128,124,0,7); g.fill(); g.strokeStyle='rgba(255,255,255,0.7)'; g.lineWidth=8; g.beginPath(); g.arc(128,128,108,0,7); g.stroke(); g.fillStyle='#1a1200'; g.font='800 120px "Noto Sans CJK SC",sans-serif'; g.textAlign='center'; g.textBaseline='middle'; g.fillText(s,128,136); const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; return t; };
const coin=new THREE.Mesh(new THREE.CylinderGeometry(0.32,0.32,0.04,64),[new THREE.MeshPhysicalMaterial({color:0xd9a640,metalness:1,roughness:0.2,clearcoat:1}),new THREE.MeshStandardMaterial({map:coinTex(T('左','L'),'#ffcc55'),metalness:0.6,roughness:0.3,emissive:0x4a3008}),new THREE.MeshStandardMaterial({map:coinTex(T('右','R'),'#7fe8ff'),metalness:0.6,roughness:0.3,emissive:0x0a3a48})]);
scene.add(coin); const coinGlow=glowSprite(0xffc24a,1.6,0.6);
const endLine=textSprite(T('最好的发球，是连你自己都不知道下一个发哪边','The best serve is one even you can’t predict'),{color:'#ffffff',size:0.5,glow:'rgba(255,194,74,0.9)'}); endLine.material.depthTest=false; endLine.renderOrder=10; // 别被发球人身体挡住

// ---------- 镜头与段落 ----------
const anchors={};
function proj(name,v){ const p=v.clone().project(camera); anchors[name]=[(p.x*0.5+0.5)*W,(1-(p.y*0.5+0.5))*H,(p.z<1&&p.z>-1)?1:0]; }
function look(px,py,pz,tx,ty,tz){ camera.position.set(px,py,pz); camera.lookAt(tx,ty,tz); }
const DOF={on:false,focus:10,ap:0.00012};
function hideAll(){
  courtG.visible=false; courtG.userData.mat.opacity=1; for(const f of [server,receiver,...ghosts]){ if(f){ f.g.visible=false; f.racket.visible=false; } }
  if(handL){ handL.holder.visible=false; handR.holder.visible=false; }
  showBall(null,false); chide(trail); chide(pileDots); pileRing.forEach(r=>r.material.opacity=0); shock.material.opacity=0; shock2.material.opacity=0;
  for(const l of [pathWide,pathT,levelBar,brPath,treeEdges,...treeFan,...chains.map(c=>c.line)]) l.material.opacity=0;
  reticle.visible=false; op(hookQ,0); op(hookTitle,0); op(hookSub,0); for(const k in cornerGlow) cornerGlow[k].material.opacity=0;
  yearG.visible=false; matG.visible=false; brPanel.visible=false; op(rpsLabel,0); rpsWin.material.opacity=0; balG.visible=false; chide(rain); rainCols.forEach(c=>c.g.visible=false);
  for(const k in ERA){ op(ERA[k].titleS,0); if(ERA[k].labS) ERA[k].labS.forEach(s=>op(s,0)); } for(const y in yearCache) op(yearCache[y],0);
  weakZone.material.opacity=0; kpBars.visible=false; KP.forEach(k=>{ k.g.visible=false; }); op(kpLegend,0); kpRowLab.forEach(x=>op(x,0)); tileG.visible=false; kpWin.forEach(s=>op(s,0)); op(kpTitle,0); kpOpen.material.opacity=0;
  chainG.visible=false; treeG.visible=false; gauge.material.opacity=0; gaugeBg.material.opacity=0; op(latestTitle,0); op(latestSub,0); latestRes.forEach(x=>op(x,0)); op(latestNote,0);
  coin.visible=false; coinGlow.visible=false; op(endLine,0); for(const k in text3D) t3op(text3D[k],0);
  beamMat.uniforms.uOp.value=0; flareLight.visible=false; rimL.intensity=0; rimR.intensity=0; DOF.on=false; MOTE_SPEED=1; }
function players(t,{serveK=null,lean=0,ghostK=0,ready=true}={}){
  courtG.visible=true;
  server.g.visible=true; server.racket.visible=true; server.g.position.set(0.85,0,L+0.4); server.g.rotation.y=Math.PI;
  server.pose(t, serveK===null?READY_KEY:server.serveKeys(serveK));
  receiver.g.visible=true; receiver.racket.visible=true; receiver.g.position.set(-SW+0.7+lean,0,-L-0.7); receiver.g.rotation.y=0.1; receiver.pose(t+3,READY_KEY);
  ghosts.forEach((g,i)=>{ const on=ghostK>0.02; g.g.visible=on; g.racket.visible=false; if(!on) return; g.g.position.set(receiver.g.position.x-(i+1)*0.55*ghostK,0,receiver.g.position.z); g.g.rotation.y=0.1; g.pose(t+3,READY_KEY); }); }
function tossBall(k){ // 抛球：左手送球到最高点，再落到击球点
  const s=server.g.position; const hand=new THREE.Vector3(s.x-0.15,1.35,s.z-0.35);
  if(k<0.25) return null; if(k<0.62){ const u=(k-0.25)/0.37; const apex=3.25; const y=hand.y+(apex-hand.y)*Math.sin(Math.PI*0.5*Math.min(1,u/0.7))-(u>0.7?(u-0.7)/0.3*(apex-SP.y):0); return new THREE.Vector3(lerp(hand.x,SP.x,u),y,lerp(hand.z,SP.z,u)); }
  return null; }

function shotHook(u,D){ const S=ev('slam',4.7); // 「纳什均衡」开口的时刻
  // 0–4 s：抛球升到最高点冻结；两条可能的轨迹像闪电分叉；准星在两角之间跳。4–5 s：两边一样亮，天平放平，「纳什均衡」砸进来
  players(u,{serveK:lerp(0.2,0.5,ss(0,1.4,u))}); receiver.g.visible=u>S+2.6; receiver.racket.visible=u>S+2.6; // 镜头升到够远才露出接发人，别在镜头旁露半截 MOTE_SPEED=0.15;
  const apex=new THREE.Vector3(SP.x-0.1,3.25,SP.z-0.05); const p=u<1.4?tossBall(lerp(0.3,0.5,ss(0,1.4,u)))||apex:apex;
  showBall(p); flareLight.visible=true; flareLight.position.copy(p); rimL.intensity=6; rimR.intensity=6; rimL.position.set(-6,4,-2); rimR.position.set(6,4,-2);
  const k=ss(S+0.6,D,u); const cr=k*k; look(lerp(-1.6,-6,cr),lerp(1.75,9,cr),lerp(-L-3.2,-L-9,cr),lerp(0.4,0,cr),lerp(2.1,0.5,cr),lerp(L,0,cr)); // 接发人视角：两道轨迹朝镜头扑来、一左一右分开
  DOF.on=true; DOF.focus=camera.position.distanceTo(p); DOF.ap=lerp(0.00025,0.00004,ss(S-0.7,S+2.3,u));
  const draw=ss(0.8,2.2,u);
  const curve=tg=>{ const pts=[]; for(let i=0;i<=40;i++){ const tau=i/40*draw; const q=serveAt(tg,tau); q.x+=(p.x-SP.x)*(1-tau); q.y+=(p.y-SP.y)*(1-tau); q.z+=(p.z-SP.z)*(1-tau); pts.push(q); } return pts; };
  setLine(pathWide,curve(TGT.wide)); setLine(pathT,curve(TGT.T));
  const eq=ss(S-0.7,S+0.1,u); const flick=0.6+0.4*Math.sin(u*23)*Math.sin(u*7.3);
  pathWide.material.opacity=draw*(eq>0?1:flick); pathT.material.opacity=draw*(eq>0?1:0.6+0.4*Math.sin(u*19+1)*Math.sin(u*5.1));
  pathWide.material.color.set(C(0x30e8ff).lerp(C(0x34f5a8),eq)); pathT.material.color.set(C(0xff3fd0).lerp(C(0x34f5a8),eq));
  for(const l of [pathWide,pathT]) l.material.dashOffset=-u*1.5;
  // 准星：在两个角之间来回跳（接发人在猜）
  reticle.visible=u>1.4&&u<S-0.1; reticle.scale.multiplyScalar(1);  const jump=Math.floor((u-1.4)*2.2)%2; const tg=jump?TGT.T:TGT.wide; reticle.position.set(tg.x,0.05,tg.z); reticle.rotation.x=-Math.PI/2; reticle.scale.setScalar(1+0.25*Math.sin(u*14));
  reticle.userData.m.color.set(jump?0xff3fd0:0x30e8ff);
  for(const [kk,gl] of Object.entries(cornerGlow)){ gl.position.set(TGT[kk].x,0.03,TGT[kk].z); gl.scale.setScalar(1.6+0.3*Math.sin(u*9)); gl.material.opacity=draw*(eq>0?0.9:(kk==='wide'?(jump?0.25:0.9):(jump?0.9:0.25))); if(eq>0) gl.material.color.set(0x34f5a8); else gl.material.color.set(kk==='wide'?0x30e8ff:0xff3fd0); }
  // 天平：网上一道光梁从倾斜放平
  const lvl=ss(S-0.7,S,u); const tilt=(1-lvl)*0.35*Math.sin(u*6); setLine(levelBar,[new THREE.Vector3(-DW,1.8-tilt*3,0),new THREE.Vector3(DW,1.8+tilt*3,0)]); levelBar.material.opacity=ss(S-1.1,S-0.7,u)*(1-ss(D-2,D-1,u));
  const sh=u-S; shock.position.set(0,0.05,0); shock.scale.setScalar(1+Math.max(0,sh)*40); shock.material.opacity=sh>0?Math.max(0,0.9-sh*1.2):0;
  shock2.position.set(0,0.05,0); shock2.scale.setScalar(1+Math.max(0,sh-0.12)*28); shock2.material.opacity=sh>0.12?Math.max(0,0.9-(sh-0.12)*1.4):0;
  FX_FLASH=sh>0&&sh<0.08?0.45:0; FX_SHAKE=sh>0&&sh<0.25?0.8:0;
  // 文字：问题先出，原理接着砸进来
  const front=(d,dy)=>camera.position.clone().add(new THREE.Vector3(0,dy,-d).applyQuaternion(camera.quaternion));
  hookQ.position.copy(front(7,1.75)); op(hookQ,ss(0.3,0.8,u)*(1-ss(S-0.3,S+0.1,u)));
  const slam=ss(S,S+0.3,u); hookTitle.position.copy(front(8,1.45)); const sc=lerp(2.2,1,slam); hookTitle.scale.set(hookTitle.userData.w0*sc,1.25*sc,1); op(hookTitle,slam*(1-ss(D-1.2,D-0.4,u)));
  hookSub.position.copy(front(8,0.62)); op(hookSub,ss(S+0.5,S+1.1,u)*(1-ss(D-1.2,D-0.4,u)));
  proj('ball',p);
}
function shotArena(u,D){
  // 一次发球放慢：0.45 秒拉长到约 6 秒；接发人肩后视角，景深虚化背景；时间环跟着球走一圈
  const cyc=7.5, k=(u%cyc)/cyc; const serveK=ss(0,0.6,k)*0.85; players(u,{serveK,ghostK:0});
  const tau=ss(0.55,0.95,k)*1.6; const vis=k>0.55; const p=vis?serveAt(TGT.wide,tau):(tossBall(serveK)||new THREE.Vector3(0,-9,0));
  showBall(p,k>0.25); setTrail(t=>serveAt(TGT.wide,t),tau,[0.85,0.95,1],vis&&k>0.58);
  beamMat.uniforms.uOp.value=0.22; beamMat.uniforms.uC.value.set(0xd8f2ff);
  if(u<cyc){ look(-SW-1.8,2.3,-L-5.2,0.8,1.0,2); DOF.on=true; DOF.focus=camera.position.distanceTo(p); DOF.ap=0.00018; }
  else { const a=(u-cyc)*0.04; look(21*Math.cos(0.35+a),8.5,21*Math.sin(0.35+a),0,0.5,0); }
  const ring=t3d('tlt05','< 0.5 s',0xd8f2ff,0.55); ring.g.position.copy(p).add(new THREE.Vector3(0,0.9,0)); ring.g.quaternion.copy(camera.quaternion); t3op(ring,vis?ss(0.6,0.66,k)*(1-ss(0.95,1,k)):0);
  proj('ball',p);
}
function shotPile(u,D){
  // 连发 6 个外角：落点越堆越亮（警示红）；接发残影一次比一次早；第 6 球被打回，红色冲击波
  const per=Math.max(2.2,(D-0.6)/6), n=Math.min(6,Math.floor(u/per)+1), k=(u-(n-1)*per)/per; const early=(n-1)/5;
  players(u,{serveK:ss(0,0.45,k)*0.85,lean:-1.2*early,ghostK:early});
  beamMat.uniforms.uOp.value=0.22; beamMat.uniforms.uC.value.set(0xff8a7a);
  look(-11.5+u*0.03,6.2,-15.5,-2.4,0.2,-6.5);
  const tau=ss(0.45,0.7,k); let p=serveAt(TGT.wide,tau); const back=n===6&&k>0.72;
  if(back){ const r=ss(0.72,0.86,k); p=new THREE.Vector3(lerp(TGT.wide.x-1.2,1.5,r),lerp(1.1,1.4,r)+Math.sin(Math.PI*r)*0.8,lerp(-L+0.5,L-2,r)); }
  showBall(p,k>0.4&&!(n<6&&k>0.72)); setTrail(t=>serveAt(TGT.wide,t),tau,[1,0.5,0.4],k>0.45&&k<0.72);
  for(let i=0;i<60;i++){ const j=Math.floor(i/10); const landed=j<n-1||(j===n-1&&k>0.7); if(!landed){ cset(pileDots,i,0,-99,0,0,0,0,0); continue; }
    fseed=1000+i; const x=TGT.wide.x+gauss()*0.16, z=TGT.wide.z+gauss()*0.2; const a=0.35+0.65*(j+1)/6; cset(pileDots,i,x,0.04,z,1,0.4+0.2*(1-j/6),0.3,a); } cdone(pileDots);
  pileRing.forEach((r,i)=>{ const age=u-(i*per+0.7*per); r.position.set(TGT.wide.x,0.03,TGT.wide.z); const s=0.3+age*2.2; r.scale.set(s,s,1); r.material.opacity=age>0&&age<0.7?0.85*(1-age/0.7):0; });
  if(back){ const a=k-0.86; shock.position.set(1.5,0.05,L-2); shock.material.color.set(0xff5a4a); const s=1+Math.max(0,a)*30; shock.scale.set(s,s,1); shock.material.opacity=a>0?Math.max(0,0.9-a*4):0; FX_SHAKE=a>0&&a<0.12?1:0; FX_FLASH=a>0&&a<0.05?0.35:0; }
}
function shotTheory(u,D){
  // 0–9 s 年份光环；9–19 s 写实手打石头剪刀布（总出石头 → 被布吃）；19–30 s 2×2 方块＋最佳应对螺旋收进均衡点
  const HA=ev('hands',9.5), MX=ev('matrix',19.5), CV=ev('conv',MX+6);
  courtG.visible=true; courtG.userData.mat.opacity=1-0.65*ss(HA-1.5,HA,u);
  if(u<HA){ yearG.visible=true; look(0,14,26,0,1,0);
    yearRings.forEach(g=>{ const i=g.userData.i, a=ss(0.6+i*(HA-2)/3,2.4+i*(HA-2)/3,u), out=ss(HA-1.2,HA-0.2,u);
      g.position.set(0,lerp(26,2.5+i*0.9,a),lerp(-60,0,a)); g.userData.r.material.opacity=0.9*a*(1-out); g.userData.r.rotation.z=u*0.2*(i%2?1:-1);
      const y=t3d('y'+g.userData.y,g.userData.y,[0xa78bfa,0x6fa8ff,0xf0e6ff][i],1.1,g); y.g.position.set(lerp(0,-8+i*8,a),3.6,9+i*1.6); y.g.quaternion.copy(camera.quaternion); t3op(y,a*(1-out));
      g.userData.sl.position.set(y.g.position.x,2.5,y.g.position.z); op(g.userData.sl,ss(0.6,1,a)*(1-out)); });
    return; }
  if(u<MX){ const v=u-HA, RL=(MX-HA)/2; // 石头剪刀布：两只手各自上下晃三下，第三下亮出；左手（对手）一直出布，右手连续两局出石头
    courtG.visible=false; look(0,0.3,6.2,0,0.3,0); handL.holder.visible=true; handR.holder.visible=true; DOF.on=true; DOF.focus=6.2; DOF.ap=0.00006;
    const round=v<RL?0:1, w=v-round*RL; const pump=w<2.0?Math.abs(Math.sin(w/2.0*Math.PI*3))*0.6:0; const reveal=ss(2.0,2.3,w);
    handR.holder.position.set(1.55,-1.15+pump,0); handR.holder.scale.setScalar(11); handR.holder.rotation.set(0,-0.35,0); handR.rig.set('rock');
    handL.holder.position.set(-1.55,-1.15+pump,0); handL.holder.scale.setScalar(11); handL.holder.rotation.set(0,0.35,0); handL.rig.set('rock',1,'paper',reveal);
    const win=ss(2.4,2.8,w)*(1-ss(RL-0.6,RL,w)); rpsWin.position.set(-1.55,0.25,-0.3); rpsWin.rotation.x=0; rpsWin.scale.setScalar(3+win*1.5); rpsWin.material.opacity=win*0.8;
    handR.mat.emissiveIntensity=0.35-0.25*win; handL.mat.emissiveIntensity=0.35+0.9*win;
    rpsLabel.position.set(1.55,-2.25,0.3); op(rpsLabel,ss(2.5,2.9,v)*(1-ss(2*RL-0.6,2*RL,v))); return; }
  const v=u-MX, C0=CV-MX; matG.visible=true; brPanel.visible=true;
  look(lerp(0,1.5,ss(0,4,v)),5.6,17,0.4,3.4,-1);
  cubes.forEach(g=>{ const {s,r,lv}=g.userData; const a=ss((s*2+r)*0.4,1.6+(s*2+r)*0.4,v); g.visible=a>0.01; g.position.set(-3.8+(r-0.5)*2.7,3.3+(1-s)*2.7-0.5,-1); g.scale.setScalar(a);
    g.userData.liq.scale.y=Math.max(0.001,ss(1.5,3.5,v)*lv); g.rotation.y=Math.sin(u*0.3+s+r)*0.08; });
  const la=ss(1.5,2.5,v); op(matLabels[0],la); matLabels[0].position.set(-8.0,5.0,-1); op(matLabels[1],la); matLabels[1].position.set(-8.0,2.3,-1);
  op(matLabels[2],la); matLabels[2].position.set(-5.15,6.8,-1); op(matLabels[3],la); matLabels[3].position.set(-2.45,6.8,-1); op(matNote,la*0.8); matNote.position.set(-1.3,0.8,-1);
  brPanel.position.set(4.0,3.6,-1); const pa=ss(3,4,v); brPanel.scale.setScalar(pa);
  const s=clamp((v-(C0-3))/(5.5)); const c=new THREE.Vector2(0.58,0.42); const pts=[];
  for(let i=0;i<=120;i++){ const ss_=s*i/120; const r=0.46*Math.exp(-3.2*ss_), th=2*Math.PI*3.2*ss_+0.6; pts.push(new THREE.Vector3(4.0+(c.x+r*Math.cos(th)-0.5)*4*pa,3.6+(c.y+r*Math.sin(th)-0.5)*4*pa,-0.99)); }
  setLine(brPath,pts); brPath.material.opacity=pa*(v>C0-3?1:0); brPath.material.color.set(0xf0e6ff);
  const last=pts[pts.length-1]; brDot.position.set((last.x-4.0),(last.y-3.6),0.02).divideScalar(Math.max(pa,0.001)); brDot.material.opacity=v>C0-3?1:0;
  brStar.position.set((c.x-0.5)*4,(c.y-0.5)*4,0.02); brStar.material.opacity=ss(C0+2.5,C0+3.1,v); brStar.scale.setScalar(1.6+0.4*Math.sin(u*5));
  brLabX.position.set(0,-2.4,0); op(brLabX,pa); brLabY.position.set(-2.5,0,0); brLabY.material.rotation=Math.PI/2; op(brLabY,pa);
  brEq.position.set((c.x-0.5)*4+0.1,(c.y-0.5)*4+0.55,0.05); op(brEq,ss(C0+2.7,C0+3.3,v));
}
function shotBalance(u,D){
  courtG.visible=true; balG.visible=true; look(Math.sin(u*0.08)*2.5,4.6,14.5,0,3.2,0); beamMat.uniforms.uOp.value=0.18; beamMat.uniforms.uC.value.set(0x9affd8);
  // 0–6 s：33 和 51 颗光点按次数落进托盘，天平倒向多的一边；6–12 s：得分率光柱长出来（64%／63%），天平回到水平
  const {nL,nR,rL,rR}=BAL; const PO=ev('pour',0.5), RI=ev('rise',6.5); const pour=ss(PO,PO+5,u); const rise=ss(RI,RI+3.5,u);
  const damp=u>RI+3.5?Math.exp(-(u-RI-3.5)*1.4)*Math.cos((u-RI-3.5)*5)*0.05:0;
  const ang=lerp(-0.16*pour,(rL-rR)*0.6,ss(RI+0.5,RI+4,u))+damp; beam.rotation.z=-ang; // 先按次数倒向外角（多的一边），再按得分率回到几乎水平
  pans.forEach(p=>{ p.g.rotation.z=ang; const rate=p.s<0?rL:rR; p.col.scale.y=Math.max(0.001,rise*rate*4.2); p.cap.position.y=-0.88+rise*rate*4.2; p.cap.material.opacity=rise;
    p.name.position.set(p.s*0.6,-1.75,0.6); op(p.name,ss(1,2,u));
    const num=t3d(p.s<0?'bL':'bR',p.s<0?'69.7%':'71.1%',p.s<0?0x34f5a8:0x4fe3ff,0.5); const wp=new THREE.Vector3(); p.g.getWorldPosition(wp); num.g.position.set(wp.x,wp.y-0.88+rise*rate*4.2+0.75,wp.z); num.g.quaternion.copy(camera.quaternion); t3op(num,ss(RI+2.5,RI+3.5,u)); });
  for(let i=0;i<84;i++){ const left=i<nL, j=left?i:i-nL, n=left?nL:nR; const t0=PO+5*j/n; const a=ss(t0,t0+0.4,u);
    const pw=new THREE.Vector3(); pans[left?0:1].g.getWorldPosition(pw); fseed=500+i; const ox=gauss()*0.3, oz=gauss()*0.3;
    cset(balDots,i,pw.x+ox,lerp(pw.y+4,pw.y-0.84+0.05*(j%5),a),pw.z+oz,left?0.3:0.35,left?1:0.9,left?0.7:1,a>0?1:0); } cdone(balDots);
  const lv=ss(RI+4.1,RI+4.4,u)*(1-ss(RI+4.9,RI+6,u)); levelFlash.position.set(0,3.3,0); levelFlash.rotation.x=0; const s=1+ss(RI+4.1,RI+5.5,u)*6; levelFlash.scale.set(s,s,1); levelFlash.material.opacity=lv*0.8;
  balTitle.position.set(0,6.4,0); op(balTitle,ss(0.3,1.2,u));
}
function shotRain(u,D){
  // 0–11 s：2023–26 年男子一发的光点暴雨（取样 2.4 万粒），外角／中路两根光柱长到几乎同一高度；11–20 s：1,056 块方砖铺满半空，56 块亮红（5.3%）
  courtG.visible=true; setupRain('now'); const CO=ev('cols',6), TI=ev('tiles',11), RD=ev('red',14); const fall=Math.max(2.5,CO-1.5), v=u;
  const k=ss(0,3,u); look(lerp(-0.5,1.0,k)+Math.sin(u*0.1)*0.6,lerp(6,9,k),lerp(5,4.5,k),-1.9,lerp(0.3,1.8,k),-SL-0.5);
  for(let i=0;i<RAIN_N;i++){ const [x,z,d,wide,sx,h]=RAIN[i];
    const t0=d*fall, a=clamp((v-t0)/1.2); const y=lerp(h,0.03,a*a); const c=wide?[1,0.75,0.28]:[0.8,0.92,1]; cset(rain,i,lerp(x+sx,x,a),y,lerp(z-6,z,a),c[0],c[1],c[2],v>t0?(a<1?0.9:0.55)*(1-0.85*ss(TI-0.5,TI+0.5,u)):0); } cdone(rain);
  rain.material.uniforms.uSize.value=0.07;
  const vv=ERA.now.v; const rise=ss(CO,CO+2,v);
  rainCols.forEach((c,i)=>{ c.g.visible=u<TI+0.5; c.g.position.set(i===0?-SW+0.45:-0.45,0,-SL+0.7); c.col.scale.y=Math.max(0.001,rise*vv[i]*4); c.cap.position.y=rise*vv[i]*4; c.cap.material.opacity=rise; c.ring.material.opacity=rise*0.6; });
  ERA.now.labS.forEach((s,i)=>{ s.position.set(i===0?-SW+0.2:-0.2,rise*vv[i]*4+0.8,-SL+0.7); op(s,ss(CO+1.5,CO+2.1,v)*(1-ss(TI-0.5,TI+0.2,v))); });
  const ttl=ERA.now.titleS; ttl.position.set(-1.9,3.9,-SL-4.5); // 顶部字幕在这段改放底部，不和这行抢 op(ttl,ss(0.2,0.8,v)*(1-ss(TI-0.5,TI+0.2,v)));
  const tw=ss(TI,TI+1.5,u); tileG.visible=tw>0.01; tileG.position.copy(camera.position).add(new THREE.Vector3(0,0.2,-12).applyQuaternion(camera.quaternion)); tileG.quaternion.copy(camera.quaternion);
  const cols=44, rows=24, m4=new THREE.Matrix4(), col=new THREE.Color();
  for(let i=0;i<TILES;i++){ const r=Math.floor(i/cols), c=i%cols; const appear=ss(TI+(i/TILES)*1.8,TI+0.3+(i/TILES)*1.8,u);
    m4.compose(new THREE.Vector3((c-cols/2+0.5)*0.19,(rows/2-r-0.5)*0.19,0),new THREE.Quaternion(),new THREE.Vector3(appear,appear,appear)); tileMesh.setMatrixAt(i,m4);
    const bad=TILE_ORDER.indexOf(i)<TILE_REJ; const red=bad?ss(RD,RD+1,u):0; col.setRGB(lerp(0.2,1.6,red),lerp(0.24,0.2,red),lerp(0.3,0.15,red)); if(red>0) tileMesh.material.emissiveIntensity=0.12; tileMesh.setColorAt(i,col); }
  tileMesh.instanceMatrix.needsUpdate=true; tileMesh.instanceColor.needsUpdate=true;
  tileTitle.position.set(0,2.95,0); op(tileTitle,ss(RD-0.5,RD+0.5,u)); tileNote.position.set(0,-2.95,0); op(tileNote,ss(RD+2,RD+3,u));
  proj('colWide',new THREE.Vector3(-SW+0.45,rise*vv[0]*4,-SL+0.7)); proj('colT',new THREE.Vector3(-0.45,rise*vv[1]*4,-SL+0.7));
}
function shotKeypoints(u,D){
  // 两排卡片：上排发球方自己的局点／盘点／赛点，下排对手的破发点／盘点／赛点；每张两根光柱（外角、中路）随心跳升到几乎同一高度
  courtG.visible=false; look(-1.3,3.0,20,-1.3,2.4,1.6); beamMat.uniforms.uOp.value=0.15; beamMat.uniforms.uC.value.set(0xffb08a);
  op(kpTitle,ss(0.3,1.2,u)); kpTitle.position.set(-1.3,7.9,1.6);
  KP.forEach((k,i)=>{ const row=Math.floor(i/3), c=i%3; const t0=(row?ev('row1',10.7):ev('row0',1.2))+c*0.9; const a=ss(t0,t0+0.7,u); k.g.visible=a>0.01;
    k.g.position.set(-4.0+c*4.0,row?-0.6:3.9,1.6); k.g.scale.setScalar(lerp(0.7,0.92,a));
    const beat=Math.exp(-Math.pow(((u-t0)%0.85)/0.08,2))*(u>t0&&u<t0+2.6?1:0);
    k.cols.forEach((cc,j)=>{ const h=ss(t0+0.5,t0+2,u)*k.v[j]*2.8; cc.scale.y=Math.max(0.001,h); cc.material.opacity=0.45+0.4*beat; k.caps[j].position.y=0.1+h; k.caps[j].material.opacity=ss(t0+0.5,t0+0.9,u); });
    k.panel.material.opacity=0.35*a; op(k.name,a); op(k.vals,ss(t0+2.2,t0+2.8,u)); if(k.note) op(k.note,ss(t0+2.4,t0+3,u)); });
  kpRowLab[0].position.set(-7.6,5.6,1.6); kpRowLab[0].material.rotation=0; op(kpRowLab[0],ss(1,1.8,u)); kpRowLab[1].position.set(-7.0,1.1,1.6); op(kpRowLab[1],ss(ev('row1',10.7)-0.3,ev('row1',10.7)+0.5,u));
  op(kpLegend,0); // 图例改由字幕层写在底部出处行（和下方字幕抢位置）
}
function shotLatest(u,D){
  treeG.visible=true; look(lerp(-1,1,ss(0,D,u)),2.4,12.5,1.4,2.0,0);
  // 比分树（示意）：0-0 到 40-40 一层层点亮，每个节点上的三向小扇面（外角／追身／中路）长度各不相同——每个比分的最优发法不一样
  const lit=ss(1,7,u)*6; const edges=[];
  NODES.forEach(({m,a,b},i)=>{ const on=clamp(lit-(a+b)); m.material.emissiveIntensity=0.15+1.4*on; m.scale.setScalar(0.7+0.5*on);
    nodeLabs[i].position.copy(m.position).add(new THREE.Vector3(0,-0.45,0)); op(nodeLabs[i],on);
    if(a<3) edges.push(m.position,NODES[i+4].m.position); if(b<3) edges.push(m.position,NODES[i+1].m.position); });
  treeG.position.set(-1.0,-0.9,0); const segs=[]; for(let i=0;i<edges.length;i+=2){ segs.push(edges[i].clone().add(treeG.position),edges[i+1].clone().add(treeG.position)); }
  setLine(treeEdges,segs); treeEdges.material.opacity=ss(0.5,1.5,u)*0.6;
  const focus=NODES[3*4+2]; // 40-30：示意一个节点上的三向扇面
  treeFan.forEach((l,i)=>{ const p=focus.m.position.clone().add(treeG.position); const dir=new THREE.Vector3(Math.cos(1.2+i*0.35),Math.sin(1.2+i*0.35),0); const len=[0.9,0.4,1.3][i]*ss(7,8.5,u);
    setLine(l,[p,p.clone().addScaledVector(dir,len)]); l.material.opacity=ss(7,8,u); });
  const RS=ev('res',9); latestRes.forEach((x,i)=>{ x.position.set(5.6,3.6-i*1.05,0); op(x,ss(RS-1.2+i*1.0,RS-0.4+i*1.0,u)); });
  latestTitle.position.set(1.4,5.2,0); op(latestTitle,ss(0.3,1.2,u)); latestSub.position.set(5.2,0.4,0);  latestNote.position.set(-1.0,-1.75,0); op(latestNote,ss(2,3,u));
}
function shotCoin(u,D){
  players(u,{serveK:u>6?clamp((u-6)/2.4)*0.85:0}); look(3.2,2.4,L+4.8,0.6,2.2,L-1); rimL.intensity=4; rimR.intensity=4; rimL.position.set(-3,4,L+2); rimR.position.set(4,4,L+2);
  DOF.on=u<6; DOF.focus=4.2; DOF.ap=0.00022;
  coin.visible=u<6; coinGlow.visible=u<6; const hp=server.B.LeftHand.getWorldPosition(new THREE.Vector3()); coin.position.set(hp.x,hp.y+0.6+Math.sin(Math.min(u,6)/6*Math.PI)*0.9,hp.z); coin.rotation.set(u*9,0.3,0.2); coinGlow.position.copy(coin.position);
  if(u>6){ const k=clamp((u-6)/2.4)*0.85; const tau=ss(7.3,8.6,u)*1.5; const p=tau>0?serveAt(TGT.T,tau):(tossBall(k)||new THREE.Vector3(0,-9,0)); showBall(p,u>6.4); setTrail(t=>serveAt(TGT.T,t),tau,[1,0.85,0.4],tau>0.05);
    look(lerp(3.2,9,ss(7,10,u)),lerp(2.4,6,ss(7,10,u)),lerp(L+4.8,L+9,ss(7,10,u)),0,0.8,-3); }
  endLine.position.copy(camera.position).add(new THREE.Vector3(0,-1.6,-9).applyQuaternion(camera.quaternion)); op(endLine,ss(ev('line',9)+0.3,ev('line',9)+1.3,u)*(1-ss(ev('q',99)-0.6,ev('q',99),u))); // 最后一问开口前让位
}

// ---------- 后期：景深、辉光、色差、暗角、颗粒 ----------
const composer=new EffectComposer(renderer,new THREE.WebGLRenderTarget(W,H,{samples:4,type:THREE.HalfFloatType})); composer.addPass(new RenderPass(scene,camera));
const bokeh=new BokehPass(scene,camera,{focus:10,aperture:0.0001,maxblur:0.008}); composer.addPass(bokeh);
const bloom=new UnrealBloomPass(new THREE.Vector2(W/2,H/2),0.5,0.45,0.88); composer.addPass(bloom);
const finalPass=new ShaderPass({uniforms:{tDiffuse:{value:null},uT:{value:0},uFlash:{value:0},uCA:{value:0.0016},uZoom:{value:0},uShake:{value:0}},
  vertexShader:`varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader:`uniform sampler2D tDiffuse; uniform float uT,uFlash,uCA,uZoom,uShake; varying vec2 vUv; float h(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453); }
   void main(){ vec2 uv=vUv+vec2(sin(uT*91.)*0.004,cos(uT*77.)*0.004)*uShake; vec2 c=uv-0.5; vec3 col=vec3(0.);
     if(uZoom>0.){ for(int k=0;k<10;k++){ float s=1.0-uZoom*0.05*float(k); col+=texture2D(tDiffuse,0.5+c*s).rgb; } col/=10.; }
     else col=vec3(texture2D(tDiffuse,uv+c*uCA).r,texture2D(tDiffuse,uv).g,texture2D(tDiffuse,uv-c*uCA).b);
     float vig=smoothstep(1.05,0.3,length(c*vec2(1.0,0.85))); col*=mix(0.5,1.0,vig); col+=(h(uv*vec2(1920.,1080.)+uT)-0.5)*0.022; col=mix(col,vec3(1.),uFlash); gl_FragColor=vec4(col,1.); }`});
composer.addPass(finalPass); composer.addPass(new OutputPass());
let FX_SHAKE=0, FX_FLASH=0, EV={}; const ev=(k,d)=>(EV[k]!==undefined?EV[k]:d); // 画面事件钉在旁白上（plan.py 写进 timeline 的 ev）
function setTransition(t){ let z=0,f=0; for(const sc of TL.sections){ const d=t-sc.t0; if(sc.t0>0&&d>=0&&d<0.45){ const k=1-d/0.45; z=k*k*0.9; f=Math.max(0,1-d/0.12)*0.35; } }
  finalPass.uniforms.uZoom.value=z; finalPass.uniforms.uFlash.value=Math.max(f,FX_FLASH); finalPass.uniforms.uT.value=t; finalPass.uniforms.uShake.value=FX_SHAKE; }
function setPalette(t){ // 段落开头 1 秒内从上一段的配色过渡过来
  const i=TL.sections.findIndex(s=>t>=s.t0&&t<s.t1); const cur=PAL[TL.sections[Math.max(0,i)].kind]||PAL.hook, prev=i>0?(PAL[TL.sections[i-1].kind]||cur):cur;
  const k=i>0?ss(TL.sections[i].t0,TL.sections[i].t0+1.0,t):1;
  skyMat.uniforms.uTop.value.set(prev.top).lerp(C(cur.top),k); skyMat.uniforms.uHz.value.set(prev.hz).lerp(C(cur.hz),k); skyMat.uniforms.uVi.value.set(prev.vi).lerp(C(cur.vi),k);
  scene.userData.grid.uniforms.uC.value.set(prev.a).lerp(C(cur.a),k).multiplyScalar(0.55); return C(prev.a).lerp(C(cur.a),k); }

function shotTL(t){ const sc=TL.sections.find(s=>t>=s.t0&&t<s.t1)||TL.sections[TL.sections.length-1]; const u=t-sc.t0, D=sc.t1-sc.t0;
  hideAll(); FX_SHAKE=0; FX_FLASH=0;
  EV=sc.ev||{}; ({hook:shotHook,arena:shotArena,pile:shotPile,theory:shotTheory,balance:shotBalance,rain:shotRain,keypoints:shotKeypoints,latest:shotLatest,coin:shotCoin})[sc.kind](u,D);
  return sc.kind; }
window.renderAt=(t)=>{ for(const k in anchors) delete anchors[k]; allClouds.forEach(c=>c.material.uniforms.uT.value=t);
  const s=shotTL(t); const ac=setPalette(t); setTransition(t); setMotes(t,ac);
  bokeh.enabled=DOF.on; if(DOF.on){ bokeh.uniforms.focus.value=DOF.focus; bokeh.uniforms.aperture.value=DOF.ap; bokeh.uniforms.maxblur.value=0.009; }
  composer.render(); return JSON.stringify(Object.assign({_shot:s},anchors)); };
Promise.all([FONT_READY,MODELS_READY,document.fonts.ready]).then(()=>{ hookTitle.userData.w0=hookTitle.scale.x; window.READY=true; }).catch(e=>console.error('READY failed',e));
