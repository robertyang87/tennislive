// vibetennis EP07「发球，该往哪边发？」——纳什均衡／极小极大定理
// 全息博弈场：深蓝夜空、蓝色全息球场；发球人金色、接发人青色；数据都长在球场上
// 球场尺寸按 ITF 标准；人形、手势、方块、天平都是示意。上屏数字的出处见 papers/vibetennis-serve-nash-2026/sources.md
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { TL } from './shots.js';

const Q=new URLSearchParams(location.search);
const W=+(Q.get('w')||1920), H=+(Q.get('h')||1080), LANG=Q.get('lang')||'zh';
const T=(zh,en)=>LANG==='en'?en:zh;
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(1); renderer.setSize(W,H);
renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.05;
renderer.outputColorSpace=THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);
const scene=new THREE.Scene(); scene.background=new THREE.Color(0x02040a);
const camera=new THREE.PerspectiveCamera(38,W/H,0.1,12000);

const GOLD=0xffc24a, CYAN=0x4fe3ff, BALL=0xd8f040, WHITE=0xffffff;
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const ss=(a,b,x)=>{ const k=clamp((x-a)/(b-a)); return k*k*(3-2*k); };
const lerp=(a,b,k)=>a+(b-a)*k;
const easeOut=k=>1-Math.pow(1-clamp(k),3);
let fseed=7007; const frnd=()=>{fseed=(fseed*48271)%2147483647;return fseed/2147483647;};
const gauss=()=>{ let u=0,v=0; while(!u) u=frnd(); v=frnd(); return Math.sqrt(-2*Math.log(u))*Math.cos(6.2831853*v); };

// ---------- 背景（与前几集一致：深蓝夜空＋地平线辉光、星点、漂浮微尘、全息地网） ----------
const skyMat=new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,
  vertexShader:`varying vec3 vD; void main(){ vD=normalize(position); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,
  fragmentShader:`varying vec3 vD; void main(){ float h=vD.y; float g=exp(-abs(h+0.02)*7.0); vec3 top=vec3(0.006,0.01,0.026); vec3 hz=vec3(0.035,0.06,0.15); vec3 vi=vec3(0.04,0.022,0.07); float side=0.5+0.5*vD.x; gl_FragColor=vec4(top+hz*g+vi*g*g*side*0.6,1.);} `});
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
function cset(p,i,x,y,z,r,gg,b,a){ const P=p.geometry.attributes.position.array, C=p.geometry.attributes.color.array, A=p.geometry.attributes.alpha.array; P[i*3]=x;P[i*3+1]=y;P[i*3+2]=z; C[i*3]=r;C[i*3+1]=gg;C[i*3+2]=b; A[i]=a; }
function cdone(p){ for(const k of ['position','color','alpha']) p.geometry.attributes[k].needsUpdate=true; }
function chide(p){ p.geometry.attributes.alpha.array.fill(0); p.geometry.attributes.alpha.needsUpdate=true; }
const stars=cloud(8000,10,3); { for(let i=0;i<8000;i++){ const r=3200+frnd()*3800, th=frnd()*Math.PI*2, ph=Math.acos(2*frnd()-1); const k=0.35+frnd()*0.6, w=frnd();
  cset(stars,i,r*Math.sin(ph)*Math.cos(th),Math.abs(r*Math.cos(ph))*0.8+60,r*Math.sin(ph)*Math.sin(th),k*(0.7+0.3*w),k*(0.75+0.2*w),k,1);} cdone(stars); }
const motes=cloud(3000,0.05,3,scene,0.6); const MOTE=[]; for(let i=0;i<3000;i++) MOTE.push([(frnd()-0.5)*50,frnd()*18,(frnd()-0.5)*50,frnd()]);
function setMotes(t){ const c=camera.position; for(let i=0;i<3000;i++){ const m=MOTE[i]; const k=0.25+0.35*m[3];
  cset(motes,i,c.x+m[0]+Math.sin(t*0.2+i)*0.6,c.y-5+((m[1]+t*0.25*(0.3+m[3]))%18),c.z-20+m[2],k*0.6,k*0.8,k,1); } cdone(motes); }

scene.add(new THREE.HemisphereLight(0xc4d8ff,0x1a2230,1.4));
const sun=new THREE.DirectionalLight(0xffffff,1.8); sun.position.set(30,60,40); scene.add(sun);
{ const m=new THREE.ShaderMaterial({transparent:true,depthWrite:false,
  vertexShader:`varying vec3 vW; void main(){ vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }`,
  fragmentShader:`varying vec3 vW; float g(vec2 p,float s){ vec2 q=abs(fract(p/s-0.5)-0.5)/fwidth(p/s); return 1.-min(min(q.x,q.y),1.);} void main(){ float d=length(vW.xz); float k=g(vW.xz,2.)*0.3+g(vW.xz,10.)*0.6; float f=exp(-d*0.02); gl_FragColor=vec4(vec3(0.25,0.55,1.)*k*f, k*f*0.5);} `});
  const p=new THREE.Mesh(new THREE.PlaneGeometry(600,600),m); p.rotation.x=-Math.PI/2; p.position.y=-0.03; scene.add(p); }

// ---------- 文字精灵（全息数字、标签） ----------
function textSprite(str,{color='#ffffff',size=1,font='700 120px "Noto Sans CJK SC","Inter",sans-serif',glow='rgba(120,200,255,0.9)'}={},group=scene){
  const c=document.createElement('canvas'); const g=c.getContext('2d'); g.font=font; const w=Math.ceil(g.measureText(str).width)+80; c.width=w; c.height=200;
  g.font=font; g.textAlign='center'; g.textBaseline='middle'; g.shadowColor=glow; g.shadowBlur=28; g.fillStyle=color; g.fillText(str,w/2,104); g.shadowBlur=0; g.fillText(str,w/2,104);
  const tex=new THREE.CanvasTexture(c); tex.colorSpace=THREE.SRGBColorSpace;
  const s=new THREE.Sprite(new THREE.SpriteMaterial({map:tex,transparent:true,depthWrite:false,opacity:0})); s.scale.set(size*w/200,size,1); group.add(s); return s; }

// ---------- 球场（ITF 尺寸，蓝色全息） ----------
const L=23.77/2, DW=10.97/2, SW=8.23/2, SL=6.40;
const courtG=new THREE.Group(); scene.add(courtG);
{ const PX=60, FW=18, FL=36, TW=FW*PX, TH=FL*PX;
  const c=document.createElement('canvas'); c.width=TW; c.height=TH; const g=c.getContext('2d');
  g.fillStyle='#16508f'; g.fillRect(0,0,TW,TH); g.fillStyle='#1d64b0'; g.fillRect(TW/2-DW*PX,TH/2-L*PX,DW*2*PX,L*2*PX);
  for(let i=0;i<30000;i++){ g.fillStyle=frnd()<0.5?'rgba(255,255,255,0.03)':'rgba(0,0,0,0.05)'; g.fillRect(frnd()*TW,frnd()*TH,1.5,1.5); }
  const cx=TW/2, cy=TH/2; g.strokeStyle='#eaf6ff'; g.lineWidth=0.05*PX;
  const R=(x0,y0,x1,y1)=>{ g.beginPath(); g.moveTo(cx+x0*PX,cy+y0*PX); g.lineTo(cx+x1*PX,cy+y1*PX); g.stroke(); };
  R(-DW,-L,DW,-L); R(-DW,L,DW,L); R(-DW,-L,-DW,L); R(DW,-L,DW,L); R(-SW,-L,-SW,L); R(SW,-L,SW,L);
  R(-SW,-SL,SW,-SL); R(-SW,SL,SW,SL); R(0,-SL,0,SL); R(0,-L,0,-L+0.10); R(0,L,0,L-0.10);
  const tex=new THREE.CanvasTexture(c); tex.colorSpace=THREE.SRGBColorSpace; tex.anisotropy=8;
  const m=new THREE.Mesh(new THREE.PlaneGeometry(FW,FL),new THREE.MeshStandardMaterial({map:tex,roughness:0.6,metalness:0.0,emissive:0x0a2a55,emissiveIntensity:0.6,transparent:true}));
  m.rotation.x=-Math.PI/2; m.renderOrder=-1; courtG.add(m); courtG.userData.mat=m.material; // 场地先画：否则半透明场地会盖住后画的光柱（光柱不写深度）
  // 边线发光描边
  const edge=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(DW*2,0.001,L*2)),new THREE.LineBasicMaterial({color:0x7fd0ff,transparent:true,opacity:0.6,blending:THREE.AdditiveBlending}));
  edge.position.y=0.01; courtG.add(edge);
  // 球网：网带＋网格
  const net=new THREE.Group(); courtG.add(net);
  const nm=new THREE.MeshBasicMaterial({color:0xbfe6ff,transparent:true,opacity:0.18,side:THREE.DoubleSide,blending:THREE.AdditiveBlending,depthWrite:false});
  const ng=new THREE.PlaneGeometry(DW*2+1.8,1.0,1,1); const np=new THREE.Mesh(ng,nm); np.position.set(0,0.5,0); net.add(np);
  const band=new THREE.Mesh(new THREE.BoxGeometry(DW*2+1.8,0.07,0.02),new THREE.MeshBasicMaterial({color:0xffffff})); band.position.set(0,0.99,0); net.add(band);
  const gridL=[]; for(let x=-DW-0.9;x<=DW+0.9;x+=0.25){ gridL.push(x,0,0,x,0.96,0); } for(let y=0.1;y<0.96;y+=0.2){ gridL.push(-DW-0.9,y,0,DW+0.9,y,0); }
  const gg=new THREE.BufferGeometry(); gg.setAttribute('position',new THREE.Float32BufferAttribute(gridL,3));
  net.add(new THREE.LineSegments(gg,new THREE.LineBasicMaterial({color:0x9fd8ff,transparent:true,opacity:0.25,blending:THREE.AdditiveBlending})));
  for(const s of [-1,1]){ const post=new THREE.Mesh(new THREE.CylinderGeometry(0.05,0.05,1.07,12),new THREE.MeshStandardMaterial({color:0xdde8f0,metalness:0.6,roughness:0.3})); post.position.set(s*(DW+0.914),0.535,0); net.add(post); }
}

// ---------- 全息人形（发球人金、接发人青） ----------
const holoMat=(color,op=0.85)=>new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,uniforms:{uC:{value:new THREE.Color(color)},uOp:{value:op},uT:{value:0}},
  vertexShader:`varying vec3 vN; varying vec3 vV; varying vec3 vW; void main(){ vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz; vN=normalize(mat3(modelMatrix)*normal); vV=normalize(cameraPosition-w.xyz); gl_Position=projectionMatrix*viewMatrix*w; }`,
  fragmentShader:`uniform vec3 uC; uniform float uOp,uT; varying vec3 vN; varying vec3 vV; varying vec3 vW; void main(){ float f=pow(1.0-abs(dot(normalize(vN),vV)),2.2); float scan=0.75+0.25*sin(vW.y*60.0-uT*6.0); float a=(0.12+0.95*f)*scan*uOp; gl_FragColor=vec4(uC*(0.5+1.4*f),a);} `});
const holoMats=[];
function figure(color){
  const g=new THREE.Group(); const mat=holoMat(color); holoMats.push(mat); g.userData.mat=mat;
  const add=(geo,x,y,z,rx=0,rz=0,parent=g)=>{ const m=new THREE.Mesh(geo,mat); m.position.set(x,y,z); m.rotation.set(rx,0,rz); parent.add(m); return m; };
  add(new THREE.CapsuleGeometry(0.2,0.55,6,14),0,1.2,0);
  add(new THREE.SphereGeometry(0.14,20,14),0,1.72,0);
  const legL=add(new THREE.CapsuleGeometry(0.09,0.7,4,10),-0.13,0.48,0,0,0.06), legR=add(new THREE.CapsuleGeometry(0.09,0.7,4,10),0.13,0.48,0,0,-0.06);
  const armL=new THREE.Group(); armL.position.set(-0.27,1.48,0); g.add(armL); add(new THREE.CapsuleGeometry(0.065,0.55,4,10),0,-0.32,0,0,0,armL);
  const armR=new THREE.Group(); armR.position.set(0.27,1.48,0); g.add(armR); add(new THREE.CapsuleGeometry(0.065,0.55,4,10),0,-0.32,0,0,0,armR);
  const rk=new THREE.Group(); rk.position.set(0,-0.62,0); armR.add(rk);
  const head=new THREE.Mesh(new THREE.TorusGeometry(0.15,0.018,8,28),mat); head.scale.set(1,1.35,1); head.position.set(0,-0.42,0); rk.add(head);
  add(new THREE.CylinderGeometry(0.018,0.018,0.26,8),0,-0.12,0,0,0,rk);
  const halo=flatRing(color,g); halo.scale.set(1.3,1.3,1); halo.position.y=0.02; halo.material.opacity=0.5;
  g.userData={mat,armL,armR,legL,legR,halo}; scene.add(g); return g; }
const server=figure(GOLD), receiver=figure(CYAN);
const ghosts=[1,2,3].map(i=>{ const f=figure(CYAN); f.userData.mat.uniforms.uOp.value=0.35/i; return f; });
function poseServe(f,k){ // k: 0 站立 → 0.5 抛球举拍 → 1 击球后
  f.userData.armL.rotation.z=lerp(0.15,2.8,ss(0,0.45,k))*(1-ss(0.6,0.9,k));
  f.userData.armR.rotation.z=lerp(-0.2,-2.9,ss(0.2,0.55,k))+ss(0.55,0.75,k)*3.6;
  f.userData.armR.rotation.x=-ss(0.55,0.8,k)*0.8; }
function poseReady(f,lean){ f.userData.armL.rotation.z=0.5; f.userData.armR.rotation.z=-0.6; f.rotation.z=lean*0.25; f.position.y=0; }

// ---------- 球与拖尾 ----------
const ball=new THREE.Mesh(new THREE.SphereGeometry(0.11,24,16),new THREE.MeshStandardMaterial({color:BALL,emissive:0x7a8a18,roughness:0.6})); scene.add(ball);
const ballGlow=glowSprite(0xe8ff70,1.1,0.9);
const TRAIL=28, trail=cloud(TRAIL,0.18,40);
const SP=new THREE.Vector3(0.9,2.85,L+0.35);           // 发球人击球点（平分区）
const TGT={wide:new THREE.Vector3(-SW+0.35,0,-SL+0.55), T:new THREE.Vector3(-0.35,0,-SL+0.55)};
function serveAt(tg,tau){ // tau 0→1 飞到落点，1→1.7 弹起飞向接发人
  if(tau<=1){ const x=lerp(SP.x,tg.x,tau), z=lerp(SP.z,tg.z,tau); const y=SP.y*(1-tau)+0.32*Math.sin(Math.PI*tau); return new THREE.Vector3(x,y,z); }
  const k=(tau-1)/0.7; const dir=new THREE.Vector3(tg.x-SP.x,0,tg.z-SP.z).normalize();
  return new THREE.Vector3(tg.x+dir.x*k*5.5,1.25*Math.sin(Math.PI*0.62*k),tg.z+dir.z*k*5.5); }
function showBall(p,vis=true){ ball.visible=vis; ballGlow.visible=vis; if(!vis) return; ball.position.copy(p); ballGlow.position.copy(p); }
function setTrail(fn,tau,vis=true){ if(!vis){ chide(trail); return; } for(let i=0;i<TRAIL;i++){ const tt=tau-i*0.03; if(tt<0){ cset(trail,i,0,-99,0,0,0,0,0); continue; } const p=fn(tt); const a=(1-i/TRAIL)*0.8; cset(trail,i,p.x,p.y,p.z,0.9,1.0,0.45,a);} cdone(trail); }

// ---------- 段 1：石头剪刀布全息手势 ----------
const rpsG=new THREE.Group(); scene.add(rpsG);
function roundRect(sh,x,y,w,h,r){ sh.moveTo(x+r,y); sh.lineTo(x+w-r,y); sh.quadraticCurveTo(x+w,y,x+w,y+r); sh.lineTo(x+w,y+h-r); sh.quadraticCurveTo(x+w,y+h,x+w-r,y+h); sh.lineTo(x+r,y+h); sh.quadraticCurveTo(x,y+h,x,y+h-r); sh.lineTo(x,y+r); sh.quadraticCurveTo(x,y,x+r,y); }
function glyph(kind,color){
  const g=new THREE.Group(); const parts=[];
  const addRR=(x,y,w,h,r,rot=0)=>{ const sh=new THREE.Shape(); roundRect(sh,-w/2,-h/2,w,h,r); const geo=new THREE.ExtrudeGeometry(sh,{depth:0.35,bevelEnabled:true,bevelThickness:0.06,bevelSize:0.05,bevelSegments:3,curveSegments:10}); geo.translate(0,0,-0.175); parts.push({geo,x,y,rot}); };
  if(kind==='rock'){ addRR(0,0,1.5,1.25,0.4); for(let i=0;i<4;i++) addRR(-0.52+i*0.35,0.62,0.33,0.36,0.15); addRR(-0.86,-0.08,0.36,0.7,0.16,0.35); }
  if(kind==='paper'){ addRR(0,-0.25,1.45,1.25,0.3); for(let i=0;i<4;i++) addRR(-0.52+i*0.35,0.95+(i===1||i===2?0.12:0),0.28,1.15,0.13); addRR(-1.0,-0.05,0.3,0.95,0.14,0.75); }
  if(kind==='scissors'){ addRR(0,-0.35,1.3,1.05,0.35); addRR(-0.22,0.85,0.28,1.35,0.13,0.22); addRR(0.22,0.85,0.28,1.35,0.13,-0.22); }
  const mat=new THREE.MeshStandardMaterial({color:0x0a1830,emissive:color,emissiveIntensity:0.55,metalness:0.3,roughness:0.35,transparent:true,opacity:0.92});
  const lm=new THREE.LineBasicMaterial({color,transparent:true,opacity:0.9,blending:THREE.AdditiveBlending});
  for(const p of parts){ const m=new THREE.Mesh(p.geo,mat); m.position.set(p.x,p.y,0); m.rotation.z=p.rot; g.add(m); const e=new THREE.LineSegments(new THREE.EdgesGeometry(p.geo,25),lm); e.position.copy(m.position); e.rotation.z=p.rot; g.add(e); }
  g.userData={mat,lm}; rpsG.add(g); return g; }
const gRock=glyph('rock',GOLD), gPaper=glyph('paper',CYAN), gSc=glyph('scissors',0xff7aa8);
const shards=cloud(2400,0.09,10,rpsG,0.3); const SHARD=[]; for(let i=0;i<2400;i++) SHARD.push([gauss()*0.45,gauss()*0.4,gauss()*0.15,gauss()*3,gauss()*3+1,gauss()*2.5]);
const rpsLabel=textSprite(T('总出石头？','Always rock?'),{color:'#ffe2a0',size:0.75,glow:'rgba(255,190,80,0.9)'},rpsG);

// ---------- 段 2/3：落点堆积、接发残影 ----------
const pileDots=cloud(60,0.55,60); const pileRing=[0,1,2,3,4,5].map(()=>flatRing(GOLD));
const timeRing=new THREE.Mesh(new THREE.TorusGeometry(1,0.03,8,96,Math.PI*2),new THREE.MeshBasicMaterial({color:GOLD,transparent:true,opacity:0,blending:THREE.AdditiveBlending}));
scene.add(timeRing); const timeLabel=textSprite('0.45 s',{color:'#fff1c4',size:0.9,font:'800 130px "Inter",sans-serif',glow:'rgba(255,190,80,1)'});
const shock=flatRing(WHITE);

// ---------- 段 4：年份光环、2×2 玻璃方块 ----------
const yearG=new THREE.Group(); scene.add(yearG);
const YEARS=[['1928',T('冯·诺依曼 · 极小极大定理','von Neumann · Minimax')],['1950',T('纳什 · 纳什均衡','Nash · Nash equilibrium')],['1994',T('诺贝尔经济学奖','Nobel Prize in Economics')]];
const yearRings=YEARS.map(([y,sub],i)=>{ const g=new THREE.Group(); yearG.add(g);
  const r=new THREE.Mesh(new THREE.TorusGeometry(9+i*1.6,0.06,8,160),new THREE.MeshBasicMaterial({color:[GOLD,CYAN,0xffffff][i],transparent:true,opacity:0,blending:THREE.AdditiveBlending})); r.rotation.x=Math.PI/2; g.add(r);
  const lab=textSprite(y,{color:'#ffffff',size:1.6,font:'800 140px "Inter",sans-serif',glow:'rgba(120,200,255,1)'},g);
  const sl=textSprite(sub,{color:'#cfe8ff',size:0.62},g); g.userData={r,lab,sl,i}; return g; });
const matG=new THREE.Group(); scene.add(matG);
const CUBE_LV=[[0.48,0.80],[0.74,0.56]]; // 示意（不上数字）：发外角/中路 × 接发猜外角/中路 时发球方赢下这一分的概率高低
const cubes=[]; for(let s=0;s<2;s++) for(let r=0;r<2;r++){ const g=new THREE.Group(); matG.add(g);
  const box=new THREE.Mesh(new THREE.BoxGeometry(2.2,2.2,2.2),new THREE.MeshPhysicalMaterial({color:0x88ccff,transparent:true,opacity:0.12,roughness:0.05,metalness:0.1,side:THREE.DoubleSide,depthWrite:false})); g.add(box);
  g.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(2.2,2.2,2.2)),new THREE.LineBasicMaterial({color:0xaee4ff,transparent:true,opacity:0.8,blending:THREE.AdditiveBlending})));
  const liq=new THREE.Mesh(new THREE.BoxGeometry(2.0,2.0,2.0),new THREE.MeshStandardMaterial({color:s===0?GOLD:0xffe08a,emissive:s===0?0x8a5a10:0x806020,emissiveIntensity:0.9,transparent:true,opacity:0.75})); liq.geometry.translate(0,1.0,0); liq.position.y=-1.0; g.add(liq);
  g.userData={box,liq,s,r,lv:CUBE_LV[s][r]}; cubes.push(g); }
const matLabels=[T('发外角','Serve wide'),T('发中路','Serve T'),T('猜外角','Guess wide'),T('猜中路','Guess T')].map((s,i)=>textSprite(s,{color:i<2?'#ffe2a0':'#bff4ff',size:0.8,glow:i<2?'rgba(255,190,80,0.9)':'rgba(80,220,255,0.9)'},matG));
const matNote=textSprite(T('示意','Illustration'),{color:'#9fb6cc',size:0.4},matG);

// ---------- 段 5：天平 ----------
const balG=new THREE.Group(); scene.add(balG);
const metal=new THREE.MeshStandardMaterial({color:0xcfe6ff,metalness:0.8,roughness:0.25,emissive:0x16324f,emissiveIntensity:0.6});
const post=new THREE.Mesh(new THREE.CylinderGeometry(0.09,0.14,3.2,16),metal); post.position.y=1.6; balG.add(post);
const beam=new THREE.Group(); beam.position.y=3.25; balG.add(beam);
beam.add(new THREE.Mesh(new THREE.BoxGeometry(8.4,0.09,0.12),metal));
const pivot=glowSprite(0xffffff,0.8,0.8,beam);
const pans=[-1,1].map(s=>{ const g=new THREE.Group(); g.position.x=s*4.1; beam.add(g);
  const ch=new THREE.Mesh(new THREE.CylinderGeometry(0.008,0.008,0.9,4),metal); ch.position.y=-0.45; g.add(ch);
  const pan=new THREE.Mesh(new THREE.CylinderGeometry(0.9,0.75,0.08,40),metal); pan.position.y=-0.92; g.add(pan);
  const col=new THREE.Mesh(new THREE.CylinderGeometry(0.42,0.42,1,32,1,true),new THREE.MeshBasicMaterial({color:s<0?GOLD:CYAN,transparent:true,opacity:0.35,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,depthWrite:false}));
  col.geometry.translate(0,0.5,0); col.position.y=-0.88; g.add(col);
  const cap=glowSprite(s<0?GOLD:CYAN,1.2,0.9,g);
  const lab=textSprite(s<0?'64%':'63%',{color:s<0?'#ffe2a0':'#bff4ff',size:0.85,font:'800 130px "Inter",sans-serif',glow:s<0?'rgba(255,190,80,1)':'rgba(80,220,255,1)'},g);
  const name=textSprite(s<0?T('发左 33 次','33 to the left'):T('发右 51 次','51 to the right'),{color:'#e6f2ff',size:0.5},g);
  return {g,col,cap,lab,name,s}; });
const balDots=cloud(84,0.3,40,balG); const levelFlash=flatRing(WHITE,balG);
const balTitle=textSprite(T('桑普拉斯 · 1997 美网 · 占先区','Sampras · 1997 US Open · ad court'),{color:'#e6f2ff',size:0.55},balG);

// ---------- 段 6/7：光点暴雨 ----------
const RAIN_N=24000; const rain=cloud(RAIN_N,0.07,6,scene,0.15); const RAIN=[];
function setupRain(mode){ RAIN.length=0; fseed=mode==='ww'?101:202; // ww：3,026 个一发（左 1,622／右 1,404）；hawk：取样 24,000 粒代表近 50 万个发球
  const n=mode==='ww'?3026:RAIN_N;
  for(let i=0;i<n;i++){ const court=frnd()<0.5?1:-1; // 1 平分区（远端左半）／-1 占先区（远端右半）
    const wide=mode==='ww'?(i<1622):(frnd()<0.5);
    const bx=court>0?(wide?-SW+0.45:-0.45):(wide?SW-0.45:0.45);
    const x=bx+gauss()*0.32, z=-SL+0.7+gauss()*0.55;
    RAIN.push([x,clamp(z,-SL+0.05,-0.3),frnd()*0.85,wide?1:0,(frnd()-0.5)*6,18+frnd()*14]); } return n; }
const rainCols=[0,1].map(i=>{ const g=new THREE.Group(); scene.add(g);
  const col=new THREE.Mesh(new THREE.CylinderGeometry(0.55,0.55,1,32,1,true),new THREE.MeshBasicMaterial({color:i===0?GOLD:CYAN,transparent:true,opacity:0.32,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,depthWrite:false}));
  col.geometry.translate(0,0.5,0); g.add(col); const cap=glowSprite(i===0?GOLD:CYAN,1.6,0.9,g); const ring=flatRing(i===0?GOLD:CYAN,g); ring.scale.set(1.6,1.6,1);
  return {g,col,cap,ring,lab:null,name:null}; });
const rainLabs={ww:[textSprite(T('发左 64%','Left 64%'),{color:'#ffe2a0',size:0.8,glow:'rgba(255,190,80,1)'}),textSprite(T('发右 65%','Right 65%'),{color:'#bff4ff',size:0.8,glow:'rgba(80,220,255,1)'})],
  hawk:[textSprite(T('外角 65.7%','Wide 65.7%'),{color:'#ffe2a0',size:0.8,glow:'rgba(255,190,80,1)'}),textSprite(T('中路 65.2%','T 65.2%'),{color:'#bff4ff',size:0.8,glow:'rgba(80,220,255,1)'})]};
const rainTitle={ww:textSprite(T('1974–1997 · 10 场 · 3,026 个一发','1974–1997 · 10 matches · 3,026 first serves'),{color:'#e6f2ff',size:0.6}),
  hawk:textSprite(T('鹰眼 2005–2009 · 3,172 场 · 近 50 万个发球','Hawk-Eye 2005–2009 · 3,172 matches · ~500,000 serves'),{color:'#e6f2ff',size:0.6}),
  now:textSprite(T('2023–2026 · 2,151 场男子比赛 · 平分区','2023–2026 · 2,151 men’s matches · deuce court'),{color:'#e6f2ff',size:0.6})};
const yearCounter=textSprite('2005',{color:'#ffffff',size:1.3,font:'800 140px "Inter",sans-serif'}); const yearCounterCache={};
function setYear(y){ if(!yearCounterCache[y]){ yearCounterCache[y]=textSprite(String(y),{color:'#ffffff',size:1.3,font:'800 140px "Inter",sans-serif'}); } for(const k in yearCounterCache) yearCounterCache[k].visible=false; yearCounter.visible=false; return yearCounterCache[y]; }

// ---------- 段 8：换边珠链 ----------
const chainG=new THREE.Group(); scene.add(chainG);
const BEADS=60; const beadGeo=new THREE.SphereGeometry(0.22,20,14);
function makeSeq(pSwitch,seed){ fseed=seed; const s=[frnd()<0.5?1:0]; for(let i=1;i<BEADS+40;i++) s.push(frnd()<pSwitch?1-s[i-1]:s[i-1]); return s; }
const SEQ=[makeSeq(0.5,913),makeSeq(0.582,4242)]; // 上：真随机硬币；下：上一个发右、下一个还发右只有 41.8%（男子，GPW 2023 表 4 下文）→ 换边概率 0.582
const chains=SEQ.map((seq,row)=>{ const beads=[]; for(let i=0;i<BEADS+40;i++){ const m=new THREE.Mesh(beadGeo,new THREE.MeshStandardMaterial({color:seq[i]?GOLD:CYAN,emissive:seq[i]?0x8a5a10:0x0f6a80,emissiveIntensity:1.0,roughness:0.3})); chainG.add(m); beads.push(m); }
  const lg=new THREE.BufferGeometry(); lg.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array((BEADS+40)*3),3));
  const line=new THREE.Line(lg,new THREE.LineBasicMaterial({color:row?0xff8fb0:0x9fd8ff,transparent:true,opacity:0.7,blending:THREE.AdditiveBlending})); chainG.add(line);
  return {beads,line,seq,row}; });
const chainLabs=[textSprite(T('真随机（抛硬币）','Truly random (coin)'),{color:'#cfe8ff',size:0.6},chainG),textSprite(T('职业球员','Pro servers'),{color:'#ffd0de',size:0.6,glow:'rgba(255,120,160,0.9)'},chainG)];
const chainStat=textSprite(T('上一个发右，下一个还发右：41.8%','After a right serve, right again: 41.8%'),{color:'#ffe2ec',size:0.62,glow:'rgba(255,120,160,0.9)'},chainG);
const scan=new THREE.Mesh(new THREE.PlaneGeometry(0.12,6),new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:0.5,blending:THREE.AdditiveBlending,depthWrite:false})); chainG.add(scan);

// ---------- 段 9：硬币 ----------
const coinTex=(s,col)=>{ const c=document.createElement('canvas'); c.width=c.height=256; const g=c.getContext('2d'); g.fillStyle=col; g.beginPath(); g.arc(128,128,124,0,7); g.fill(); g.strokeStyle='rgba(255,255,255,0.7)'; g.lineWidth=8; g.beginPath(); g.arc(128,128,108,0,7); g.stroke(); g.fillStyle='#1a1200'; g.font='800 120px "Noto Sans CJK SC",sans-serif'; g.textAlign='center'; g.textBaseline='middle'; g.fillText(s,128,136); const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; return t; };
const coin=new THREE.Mesh(new THREE.CylinderGeometry(0.5,0.5,0.06,64),[new THREE.MeshStandardMaterial({color:0xd9a640,metalness:0.9,roughness:0.25}),new THREE.MeshStandardMaterial({map:coinTex(T('左','L'),'#ffcc55'),metalness:0.6,roughness:0.3,emissive:0x4a3008}),new THREE.MeshStandardMaterial({map:coinTex(T('右','R'),'#7fe8ff'),metalness:0.6,roughness:0.3,emissive:0x0a3a48})]);
scene.add(coin); const coinGlow=glowSprite(GOLD,2.2,0.6);
const endLine=textSprite(T('最好的发球，是连你自己都不知道下一个发哪边','The best serve is one even you can’t predict'),{color:'#ffffff',size:0.5});

// ---------- 镜头 ----------
const anchors={};
function proj(name,v){ const p=v.clone().project(camera); anchors[name]=[(p.x*0.5+0.5)*W,(1-(p.y*0.5+0.5))*H,(p.z<1&&p.z>-1)?1:0]; }
function look(px,py,pz,tx,ty,tz){ camera.position.set(px,py,pz); camera.lookAt(tx,ty,tz); }
function hideAll(){
  rpsG.visible=false; courtG.visible=false; for(const f of [server,receiver,...ghosts]) f.visible=false;
  showBall(null,false); chide(trail); chide(pileDots); pileRing.forEach(r=>r.material.opacity=0); timeRing.material.opacity=0; timeLabel.material.opacity=0; shock.material.opacity=0;
  yearG.visible=false; matG.visible=false; balG.visible=false; chide(rain); rainCols.forEach(c=>c.g.visible=false);
  for(const k in rainLabs) rainLabs[k].forEach(s=>s.material.opacity=0); for(const k in rainTitle) rainTitle[k].material.opacity=0; setYear(2005);
  chainG.visible=false; coin.visible=false; coinGlow.visible=false; endLine.material.opacity=0; }
const op=(s,v)=>{ s.material.opacity=v; };

function shotRPS(u,D){
  rpsG.visible=true; look(0,0.4,9.5-u*0.12,0,0.2,0);
  gSc.visible=u<3.2; gRock.visible=true; gPaper.visible=true;
  // 0–3 s：三只手势转着亮起；3–9 s：金色连出三次石头，青色每次出布把它吞掉；第三次石头碎成粒子
  const intro=1-ss(2.6,3.4,u);
  gSc.position.set(0,1.9+intro*0.2,0); gSc.rotation.y=Math.sin(u*1.2)*0.5; gSc.scale.setScalar(0.8*intro+0.001);
  const beats=[4.0,5.6,7.2]; let punch=0, lastBeat=-1; beats.forEach((b,i)=>{ const k=Math.exp(-Math.pow((u-b)/0.18,2)); punch=Math.max(punch,k); if(u>=b-0.25) lastBeat=i; });
  gRock.position.set(-2.2+punch*0.9,0,0); gRock.rotation.set(0,0.35+Math.sin(u*0.6)*0.1,-punch*0.2); gRock.scale.setScalar(u<0.6?ss(0,0.6,u):1);
  gPaper.position.set(2.2-punch*0.9,0.1,0.15*punch); gPaper.rotation.set(0,-0.35+Math.sin(u*0.5)*0.1,punch*0.15); gPaper.scale.setScalar((u<1.0?ss(0.4,1.0,u):1)*(1+punch*0.12));
  const shat=ss(7.15,7.6,u); gRock.visible=shat<0.5; gRock.userData.mat.emissiveIntensity=0.55+punch*0.8;
  if(u>7.15){ const k=u-7.2; for(let i=0;i<2400;i++){ const s=SHARD[i]; const a=Math.max(0,1-k/2.6); cset(shards,i,-1.3+s[0]+s[3]*k,s[1]+s[4]*k-1.4*k*k,s[2]+s[5]*k,1.0,0.78,0.3,a); } cdone(shards); } else chide(shards);
  rpsLabel.position.set(-2.2,-1.35,0.6); op(rpsLabel,ss(3.2,3.8,u)*(1-ss(8.5,9.2,u)));
  // 9 s 起：镜头拉远俯下，球场在手势下方亮起——「发球，也是这个游戏」
  const k=ss(9,D,u); if(k>0){ courtG.visible=true; courtG.userData.mat.opacity=k; look(lerp(0,0,k),lerp(0.4,9,k),lerp(9.5,22,k),0,lerp(0.2,0,k),lerp(0,-2,k)); gPaper.position.y+=k*3; gPaper.scale.multiplyScalar(1-0.6*k); }
}
function placePlayers(lean,ghostK=0){
  courtG.visible=true; courtG.userData.mat.opacity=1;
  server.visible=true; server.position.set(SP.x+0.25,0,SP.z); server.rotation.y=Math.PI;
  receiver.visible=true; receiver.position.set(-SW+0.9+lean,0,-L-0.6); receiver.rotation.y=0; poseReady(receiver,lean>0?-1:lean<0?1:0);
  ghosts.forEach((g,i)=>{ g.visible=ghostK>0; g.position.set(receiver.position.x-(i+1)*0.55*ghostK,0,receiver.position.z); g.rotation.y=0; poseReady(g,1); }); }
function shotArena(u,D){
  // 一次发球放慢：0.45 秒拉长到约 6 秒；时间环绕着球的飞行路径走一圈
  const cyc=7.5, k=(u%cyc)/cyc; const tau=ss(0.18,0.85,k)*1.6; const slow=u<cyc;
  placePlayers(0, slow?ss(0.05,0.25,k)*0.9:0); poseServe(server,ss(0,0.22,k));
  const p=serveAt(TGT.wide,tau); showBall(p,k>0.12); setTrail(t=>serveAt(TGT.wide,t),tau,k>0.2);
  // 接发人肩后视角，球迎面而来
  const cam=new THREE.Vector3(-SW-2.4,3.0,-L-7.0+Math.sin(u*0.3)*0.3); look(cam.x,cam.y,cam.z,0.6,0.9,3);
  if(u>cyc){ const a=(u-cyc)*0.04; look(21*Math.cos(0.35+a),8.5,21*Math.sin(0.35+a),0,0.5,0); }
  // 时间环：跟着球走，环的弧长＝已过去的时间 / 0.45 s
  const prog=clamp(tau/1.0); timeRing.material.opacity=0.9*ss(0.15,0.25,k)*(1-ss(0.9,1,k));
  timeRing.geometry.dispose(); timeRing.geometry=new THREE.TorusGeometry(0.75,0.03,8,96,Math.PI*2*Math.max(prog,0.001));
  timeRing.position.copy(p); timeRing.lookAt(camera.position);
  timeLabel.position.copy(p).add(new THREE.Vector3(0,1.0,0)); op(timeLabel,ss(0.6,0.7,k)*(1-ss(0.95,1,k)));
  proj('ball',p);
}
function shotPile(u,D){
  // 连发 6 个外角：落点在同一个角落越堆越亮；接发残影一次比一次早；第 6 球被打回、炸开
  const per=3.2, n=Math.min(6,Math.floor(u/per)+1), k=(u-(n-1)*per)/per;
  const early=(n-1)/5; placePlayers(-1.3*ss(0,1,early*1.0+ (k>0.2?0.2:0)),early);
  look(-11.5+u*0.03,6.2,-15.5,-2.4,0.2,-6.5);
  poseServe(server,ss(0,0.25,k)); const tau=ss(0.2,0.6,k)*1.0;
  let p=serveAt(TGT.wide,tau); let back=n===6&&k>0.62;
  if(back){ const r=ss(0.62,0.8,k); p=new THREE.Vector3(lerp(TGT.wide.x-1.2,1.5,r),lerp(1.1,1.4,r)+Math.sin(Math.PI*r)*0.8,lerp(-L+0.5,L-2,r)); }
  showBall(p,k>0.15&&!(n<6&&k>0.62)); setTrail(t=>serveAt(TGT.wide,t),tau,k>0.2&&k<0.62);
  for(let i=0;i<60;i++){ const j=Math.floor(i/10); const landed=j<n-1||(j===n-1&&k>0.6); if(!landed){ cset(pileDots,i,0,-99,0,0,0,0,0); continue; }
    fseed=1000+i; const x=TGT.wide.x+gauss()*0.18, z=TGT.wide.z+gauss()*0.22; const a=0.35+0.65*(j+1)/6; cset(pileDots,i,x,0.04,z,1,0.8,0.35,a); } cdone(pileDots);
  pileRing.forEach((r,i)=>{ const age=u-(i*per+0.6*per); r.position.set(TGT.wide.x,0.03,TGT.wide.z); const s=0.3+age*2.2; r.scale.set(s,s,1); r.material.opacity=age>0&&age<0.7?0.8*(1-age/0.7):0; });
  if(back){ const a=k-0.8; shock.position.set(1.5,0.05,L-2); const s=1+Math.max(0,a)*25; shock.scale.set(s,s,1); shock.material.opacity=a>0?Math.max(0,0.9-a*4):0; FX_SHAKE=a>0&&a<0.15?1:0; FX_FLASH=a>0&&a<0.06?0.4:0; }
}
function shotMatrix(u,D){
  courtG.visible=true; courtG.userData.mat.opacity=1-0.5*ss(14,17,u); yearG.visible=true; matG.visible=true;
  // 0–13 s：1928/1950/1994 三个年份环依次飞来套上球场；13 s 起：发球区上空升起 2×2 玻璃方块
  yearRings.forEach(g=>{ const i=g.userData.i, a=ss(1+i*3.5,3.2+i*3.5,u), out=ss(13,15,u);
    g.position.set(0,lerp(26,2.5+i*0.9,a),lerp(-60,0,a)); g.userData.r.material.opacity=0.85*a*(1-out); g.userData.r.rotation.z=u*0.2*(i%2?1:-1);
    g.userData.lab.position.set(lerp(0,-8+i*8,a),3.4,9+i*1.6); op(g.userData.lab,a*(1-out)); g.userData.sl.position.set(g.userData.lab.position.x,2.3,g.userData.lab.position.z); op(g.userData.sl,ss(0.6,1,a)*(1-out)); });
  const camK=ss(12,16,u); look(lerp(0,9,camK),lerp(14,6.5,camK),lerp(26,15,camK),0,lerp(1,3,camK),lerp(0,-1,camK));
  cubes.forEach(g=>{ const {s,r,lv}=g.userData; const a=ss(14+(s*2+r)*0.6,16+(s*2+r)*0.6,u); g.visible=a>0.01;
    g.position.set((r-0.5)*2.9,3+ (1-s)*2.9 -0.5,-1); g.scale.setScalar(a);
    const fill=ss(17+(s*2+r)*0.5,19.5+(s*2+r)*0.5,u)*lv; g.userData.liq.scale.y=Math.max(0.001,fill); g.rotation.y=Math.sin(u*0.3+s+r)*0.08; });
  const la=ss(16.5,17.5,u);
  op(matLabels[0],la); matLabels[0].position.set(-4.6,5.4,-1); op(matLabels[1],la); matLabels[1].position.set(-4.3,2.5,-1);
  op(matLabels[2],la); matLabels[2].position.set(-1.45,7.2,-1); op(matLabels[3],la); matLabels[3].position.set(1.45,7.2,-1);
  op(matNote,la*0.8); matNote.position.set(3.6,0.9,-1);
}
function shotBalance(u,D){
  courtG.visible=true; courtG.userData.mat.opacity=1; balG.visible=true; balG.position.set(0,0,0);
  look(Math.sin(u*0.08)*2.5,4.2,12.5,0,2.6,0);
  // 0–6 s：33 和 51 颗光点分别落进左右托盘，天平往多的一边倒（「按次数」的直觉）
  // 6–12 s：两根得分率光柱长出来（64%／63%），天平回到水平——判据是得分率，不是次数
  const nL=33,nR=51; const pour=ss(0.5,5.5,u);
  const tiltCount=0.16*pour, rise=ss(6.5,10,u); const tiltRate=(0.64-0.63)*0.6;
  const damp=u>10?Math.exp(-(u-10)*1.4)*Math.cos((u-10)*5)*0.05:0;
  const ang=lerp(tiltCount,tiltRate,ss(7,10.5,u))+damp; beam.rotation.z=-ang;
  pans.forEach(p=>{ p.g.rotation.z=ang; const rate=p.s<0?0.64:0.63; p.col.scale.y=Math.max(0.001,rise*rate*4.2); p.cap.position.y=-0.88+rise*rate*4.2; p.cap.material.opacity=rise;
    p.lab.position.set(0,-0.88+rise*rate*4.2+0.75,0); op(p.lab,ss(9,10,u)); p.name.position.set(p.s*0.6,-1.75,0.6); op(p.name,ss(1,2,u)); });
  for(let i=0;i<84;i++){ const left=i<nL, j=left?i:i-nL, n=left?nL:nR; const t0=0.5+5*j/n; const a=ss(t0,t0+0.4,u);
    const pw=new THREE.Vector3(); pans[left?0:1].g.getWorldPosition(pw); fseed=500+i; const ox=gauss()*0.3, oz=gauss()*0.3;
    cset(balDots,i,pw.x+ox,lerp(pw.y+4,pw.y-0.84+0.05*(j%5),a),pw.z+oz,left?1:0.4,left?0.78:0.9,left?0.3:1,a>0?1:0); } cdone(balDots);
  const lv=ss(10.6,10.9,u)*(1-ss(11.4,12.5,u)); levelFlash.position.set(0,3.3,0); levelFlash.rotation.x=0; const s=1+ss(10.6,12,u)*6; levelFlash.scale.set(s,s,1); levelFlash.material.opacity=lv*0.8;
  balTitle.position.set(0,6.4,0); op(balTitle,ss(0.3,1.2,u));
  proj('balL',new THREE.Vector3(-4.1,3.25,0)); proj('balR',new THREE.Vector3(4.1,3.25,0));
}
function shotRain(u,D,mode){
  courtG.visible=true; courtG.userData.mat.opacity=1;
  const n=setupRain(mode); const fall=mode==='ww'?8:10;
  const k=ss(0,fall+2,u); look(lerp(-0.5,1.0,k)+Math.sin(u*0.1)*0.6,lerp(6,9,k),lerp(5,4.5,k),-1.9,lerp(0.3,1.8,k),-SL-0.5);
  for(let i=0;i<RAIN_N;i++){ if(i>=n){ cset(rain,i,0,-99,0,0,0,0,0); continue; } const [x,z,d,wide,sx,h]=RAIN[i];
    const t0=d*fall, a=clamp((u-t0)/1.2); const y=lerp(h,0.03,a*a); const xx=lerp(x+sx,x,a), zz=lerp(z-6,z,a);
    const c=wide?[1,0.78,0.32]:[0.35,0.9,1]; cset(rain,i,xx,y,zz,c[0],c[1],c[2],u>t0?(a<1?0.9:0.55):0); } cdone(rain);
  rain.material.uniforms.uSize.value=mode==='ww'?0.11:0.07;
  // 光柱：平分区的外角（金）／中路（青）各一根；高度＝得分率
  const v=mode==='ww'?[0.64,0.65]:[0.657,0.652]; const rise=ss(fall+1,fall+5,u);
  rainCols.forEach((c,i)=>{ c.g.visible=true; c.g.position.set(i===0?-SW+0.45:-0.45,0,-SL+0.7); c.col.scale.y=Math.max(0.001,rise*v[i]*4); c.cap.position.y=rise*v[i]*4; c.cap.material.opacity=rise; c.ring.material.opacity=rise*0.6; });
  rainLabs[mode].forEach((s,i)=>{ s.position.set(i===0?-SW+0.2:-0.2,rise*v[i]*4+0.8,-SL+0.7); op(s,ss(fall+4,fall+5,u)); });
  const ttl=rainTitle[mode]; ttl.position.set(-1.9,4.6,-SL-4.5); op(ttl,ss(0.3,1.2,u)*(mode==='hawk'?1-ss(15,16,u):1));
  if(mode==='hawk'){ const yk=ss(15,20,u); const y=Math.round(lerp(2005,2026,yk)); const ys=setYear(y); ys.visible=true; ys.position.set(3.2,3.6,-SL-3); op(ys,ss(14.5,15.5,u));
    op(rainTitle.now,ss(16,17,u)); rainTitle.now.position.set(-1.9,4.6,-SL-4.5); }
  proj('colWide',new THREE.Vector3(-SW+0.45,rise*v[0]*4,-SL+0.7)); proj('colT',new THREE.Vector3(-0.45,rise*v[1]*4,-SL+0.7));
}
function shotChains(u,D){
  chainG.visible=true; look(0,0.6,13,0,0.3,0);
  const shift=u*1.6, gap=0.62;
  chains.forEach(ch=>{ const y=ch.row?-1.6:1.9; const P=ch.line.geometry.attributes.position.array;
    ch.beads.forEach((b,i)=>{ const x=i*gap-shift-9; const yy=y+(ch.seq[i]?0.32:-0.32); b.position.set(x,yy,0); b.visible=x>-13&&x<13; P[i*3]=x;P[i*3+1]=yy;P[i*3+2]=0; });
    ch.line.geometry.attributes.position.needsUpdate=true; });
  chainLabs[0].position.set(-5.2,3.1,0); op(chainLabs[0],ss(0.3,1.2,u)); chainLabs[1].position.set(-5.8,-0.4,0); op(chainLabs[1],ss(1,2,u));
  scan.position.set(lerp(-11,11,(u*0.12)%1),-1.6,0.3); scan.scale.y=0.5;
  chainStat.position.set(0,-3.4,0); op(chainStat,ss(8,9,u));
}
function shotCoin(u,D){
  courtG.visible=true; courtG.userData.mat.opacity=1; placePlayers(0,0); server.visible=true; receiver.visible=true;
  look(4.2,2.6,L+5.5,0.6,2.2,L-1);
  coin.visible=true; coinGlow.visible=true; const flip=u<6; coin.position.set(SP.x+0.1,2.1+Math.sin(Math.min(u,6)/6*Math.PI)*1.2,SP.z-0.4); coin.rotation.set(u*9,0.3,Math.PI/2*0.2); coinGlow.position.copy(coin.position);
  if(u>6){ coin.visible=false; coinGlow.visible=false; const k=clamp((u-6)/2.2); poseServe(server,k); const tau=ss(0.25,0.75,k)*1.5; showBall(serveAt(TGT.T,tau),k>0.2); setTrail(t=>serveAt(TGT.T,t),tau,k>0.25); look(lerp(4.2,9,ss(6,9,u)),lerp(2.6,6,ss(6,9,u)),lerp(L+5.5,L+9,ss(6,9,u)),0,0.8,-3); }
  endLine.position.copy(camera.position).add(new THREE.Vector3(0,-1.6,-9).applyQuaternion(camera.quaternion)); op(endLine,ss(9,10.5,u));
}

// ---------- 后期 ----------
const composer=new EffectComposer(renderer,new THREE.WebGLRenderTarget(W,H,{samples:4,type:THREE.HalfFloatType})); composer.addPass(new RenderPass(scene,camera));
const bloom=new UnrealBloomPass(new THREE.Vector2(W/2,H/2),0.55,0.45,0.82); composer.addPass(bloom);
const finalPass=new ShaderPass({uniforms:{tDiffuse:{value:null},uT:{value:0},uFlash:{value:0},uCA:{value:0.0015},uZoom:{value:0},uShake:{value:0}},
  vertexShader:`varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader:`uniform sampler2D tDiffuse; uniform float uT,uFlash,uCA,uZoom,uShake; varying vec2 vUv; float h(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453); }
   void main(){ vec2 uv=vUv+vec2(sin(uT*91.)*0.004,cos(uT*77.)*0.004)*uShake; vec2 c=uv-0.5; vec3 col=vec3(0.);
     if(uZoom>0.){ for(int k=0;k<10;k++){ float s=1.0-uZoom*0.05*float(k); col+=texture2D(tDiffuse,0.5+c*s).rgb; } col/=10.; }
     else col=vec3(texture2D(tDiffuse,uv+c*uCA).r,texture2D(tDiffuse,uv).g,texture2D(tDiffuse,uv-c*uCA).b);
     float vig=smoothstep(1.05,0.3,length(c*vec2(1.0,0.85))); col*=mix(0.55,1.0,vig); col+=(h(uv*vec2(1920.,1080.)+uT)-0.5)*0.025; col=mix(col,vec3(1.),uFlash); gl_FragColor=vec4(col,1.); }`});
composer.addPass(finalPass); composer.addPass(new OutputPass());
let FX_SHAKE=0, FX_FLASH=0;
function setTransition(t){ let z=0,f=0; for(const sc of TL.sections){ const d=t-sc.t0; if(sc.t0>0&&d>=0&&d<0.45){ const k=1-d/0.45; z=k*k*0.9; f=Math.max(0,1-d/0.12)*0.35; } }
  finalPass.uniforms.uZoom.value=z; finalPass.uniforms.uFlash.value=Math.max(f,FX_FLASH); finalPass.uniforms.uT.value=t; finalPass.uniforms.uShake.value=FX_SHAKE; }

function shotTL(t){ const sc=TL.sections.find(s=>t>=s.t0&&t<s.t1)||TL.sections[TL.sections.length-1]; const u=t-sc.t0, D=sc.t1-sc.t0;
  hideAll(); FX_SHAKE=0; FX_FLASH=0; holoMats.forEach(m=>m.uniforms.uT.value=t);
  ({rps:shotRPS,arena:shotArena,pile:shotPile,matrix:shotMatrix,balance:shotBalance,rain_ww:(u,D)=>shotRain(u,D,'ww'),rain_hawk:(u,D)=>shotRain(u,D,'hawk'),chains:shotChains,coin:shotCoin})[sc.kind](u,D);
  return sc.kind; }
window.renderAt=(t)=>{ for(const k in anchors) delete anchors[k]; allClouds.forEach(c=>c.material.uniforms.uT.value=t); const s=shotTL(t); setTransition(t); setMotes(t); composer.render(); return JSON.stringify(Object.assign({_shot:s},anchors)); };
document.fonts.ready.then(()=>{ window.READY=true; });
