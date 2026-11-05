// vibetennis 器材三部曲 ① 拍线的演变——四代线（羊肠 → 合成 → 聚酯 → 混搭）改变了什么，和打法能不能对上。
// 理论：牛顿碰撞定律（恢复系数）、库仑摩擦定律、应力松弛（麦克斯韦「弛豫时间」）。上屏数字的出处见 papers/vibetennis-strings-2026/sources.md。
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
function textSprite(str,{color='#ffffff',size=1,font='700 120px "Noto Sans CJK SC","Inter",sans-serif',glow='rgba(120,200,255,0.9)'}={},group=scene){
  const c=document.createElement('canvas'); const g=c.getContext('2d'); g.font=font; const w=Math.ceil(g.measureText(str).width)+80; c.width=w; c.height=200;
  g.font=font; g.textAlign='center'; g.textBaseline='middle';
  // 字的光晕收小收淡、加一圈深色细描边，字本身略低于泛光阈值——所有者 2026-11-05「字体的光晕太亮，感觉看不清楚真正的文字」
  g.globalAlpha=0.45; g.shadowColor=glow; g.shadowBlur=14; g.fillStyle=color; g.fillText(str,w/2,104); g.globalAlpha=1; g.shadowBlur=0;
  g.lineJoin='round'; g.lineWidth=7; g.strokeStyle='rgba(0,0,0,0.6)'; g.strokeText(str,w/2,104); g.fillText(str,w/2,104);
  const tex=new THREE.CanvasTexture(c); tex.colorSpace=THREE.SRGBColorSpace;
  const s=new THREE.Sprite(new THREE.SpriteMaterial({map:tex,transparent:true,depthWrite:false,opacity:0,color:0xd8d8d8,depthTest:false})); s.renderOrder=20; /* 字永远压在 3D 物体上面，不被球拍挡住 */ s.scale.set(size*w/200,size,1); group.add(s); return s; }
const NOTEXT=!!Q.get('notext');   // 封面底图：3D 里的字全部不出，标题由封面脚本自己排
const op=(s,v)=>{ s.material.opacity=NOTEXT?0:v; };
let FONT=null; const FONT_READY=new Promise(res=>new FontLoader().load('./node_modules/three/examples/fonts/helvetiker_bold.typeface.json',f=>{ FONT=f; res(); }));
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

// ---------- 球拍与线床 ----------
// 拍头半长 A、半宽 B（单位随场景放大，球半径按真实比例：拍头长 34 cm、球径 6.7 cm）
const A=1.7, B=1.3;
const STR={gut:0xffb347, nylon:0xe8f6ff, poly:0xb9c8ff, hybridM:0xffb347, hybridC:0xb9c8ff, spag:0xff8a7a};
function makeRacket(group=scene,{nm=16,nc=19}={}){
  const g=new THREE.Group(); group.add(g);
  const frameMat=new THREE.MeshPhysicalMaterial({color:0x1a1f2e,metalness:0.85,roughness:0.22,clearcoat:1,emissive:0x0a1a3a,emissiveIntensity:0.5,transparent:true});
  const curve=new THREE.EllipseCurve(0,0,B+0.06,A+0.06,0,Math.PI*2); const pts=curve.getPoints(160).map(p=>new THREE.Vector3(p.x,p.y,0));
  const frame=new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts,true),200,0.075,12,true),frameMat); g.add(frame);
  const edge=new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts,true),200,0.085,8,true),new THREE.MeshBasicMaterial({color:0x4fe3ff,wireframe:true,transparent:true,opacity:0.12,blending:THREE.AdditiveBlending,depthWrite:false})); g.add(edge);
  // 拍喉照真拍子（所有者 2026-11-05「拍喉那块和真实的不一样」，对照 Commons「Tennis racket and ball.JPG」）：
  // 两根拍杆从拍框两侧约 4 点半／7 点半处顺着拍框切线分出来，往下收拢成拍喉，拍框底边（拍桥）和两根拍杆围出一个开口三角；
  // 再接粗握把（八角）和略大的底盖。比例按 27 英寸球拍：拍框外高 3.52（约 34 cm），全长约 7.1。
  const TH=-A-0.75; // 两杆收拢处（下面拍杆沿切线走到 x=±0.15 时 y≈-A-0.746）
  const neck=new THREE.Group(); g.add(neck);   // 库仑横截面那一镜把拍子放平，只留拍框和线床
  // 2026-11-05 第二轮（所有者「弧度是拍面的切线」「开孔太大了」，对照 Safin 签名 Head 拍与 Wilson 拍的正面照）：
  // 拍杆从拍框约 4 点／8 点处沿拍框的切线方向直着出去，收拢点只比拍框底低 0.75（开口高约拍面宽的 1/4）
  const DL=0.85, bx=B+0.06, ay=A+0.06;
  for(const s of [-1,1]){ const el=d=>new THREE.Vector3(s*bx*Math.sin(d),-ay*Math.cos(d),0);
    const p0=el(DL), pre=el(DL+0.12); const dir=new THREE.Vector3(-s*bx*Math.cos(DL),-ay*Math.sin(DL),0).normalize();
    const L=(Math.abs(p0.x)-0.15)/Math.abs(dir.x); const end=p0.clone().addScaledVector(dir,L);
    const th=new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([pre,p0,p0.clone().lerp(end,0.5),end]),48,0.1,12),frameMat); th.scale.z=0.7; neck.add(th); }
  const throat=new THREE.Mesh(new THREE.CylinderGeometry(0.22,0.19,0.9,10),frameMat); throat.position.y=TH-0.4; neck.add(throat);
  const gripMat=new THREE.MeshPhysicalMaterial({color:0x464e63,metalness:0.15,roughness:0.55,emissive:0x101828,emissiveIntensity:0.6,transparent:true});
  const handle=new THREE.Mesh(new THREE.CylinderGeometry(0.19,0.2,1.95,8),gripMat); handle.position.y=TH-0.85-0.975; neck.add(handle);
  const butt=new THREE.Mesh(new THREE.CylinderGeometry(0.23,0.21,0.13,8),gripMat); butt.position.y=TH-0.85-1.95-0.065; neck.add(butt);
  const mx=[...Array(nm).keys()].map(i=>-B*0.86+i*(2*B*0.86)/(nm-1)), cy=[...Array(nc).keys()].map(i=>-A*0.86+i*(2*A*0.86)/(nc-1));
  const mains=mx.map(x=>({x,line:fatLine(0xffffff,2.2)})), crosses=cy.map(y=>({y,line:fatLine(0xffffff,2.2)}));
  [...mains,...crosses].forEach(s=>{ scene.remove(s.line); g.add(s.line); });
  return {g,frame,frameMat,handle,neck,mains,crosses,mx,cy}; }
const yAt=x=>A*Math.sqrt(Math.max(0,1-(x/B)**2))-0.04, xAt=y=>B*Math.sqrt(Math.max(0,1-(y/A)**2))-0.04;
// 线床：color 主线／横线颜色；slide(x,y) 主线在 (x,y) 处的横向位移；zm／zc 主线横线所在平面（意大利面拍两层分开）；ncUse 只画前几根横线
function setBed(R,{cm=0xffffff,cc=cm,opm=1,opc=1,slide=null,zm=0.0,zc=0.0,crossSet=null,width=2.2}={}){
  R.mains.forEach(s=>{ const y0=yAt(s.x), pts=[]; for(let k=0;k<=24;k++){ const y=-y0+2*y0*k/24; const dx=slide?slide(s.x,y):0; pts.push(new THREE.Vector3(s.x+dx,y,zm)); }
    setLine(s.line,pts); s.line.material.color.set(cm); s.line.material.opacity=opm; s.line.material.linewidth=width; });
  R.crosses.forEach((s,i)=>{ const on=crossSet?crossSet.includes(i):true; const x0=xAt(s.y);
    setLine(s.line,[new THREE.Vector3(-x0,s.y,zc),new THREE.Vector3(x0,s.y,zc)]); s.line.material.color.set(cc); s.line.material.opacity=on?opc:0; s.line.material.linewidth=width; }); }
function hideBed(R){ [...R.mains,...R.crosses].forEach(s=>s.line.material.opacity=0); }
// 主线滑开再弹回的位移场：k 0→1 一次撞击（0–0.5 滑开，0.5–1 弹回，弹回很快）
const slideField=(amp,cx=0,cy=0,k=0)=>{ const a=k<0.55?ss(0,0.55,k):1-ss(0.55,0.7,k); return (x,y)=>amp*a*Math.exp(-Math.pow((x-cx)/0.42,2))*Math.max(0,1-Math.pow((y-cy)/1.0,2)); };

// ---------- 柱状图（发球上网占比） ----------
// 原创计算：Match Charting Project 男子逐分（志愿者标注，非官方），去掉 ACE；脚本 papers/vibetennis-strings-2026/data/mcp_serve_volley_trend.py
const SV_ERA=[['1990–99',39.5,73.1],['2000–04',17.1,41.0],['2005–09',5.7,10.3],['2010–14',4.0,8.3],['2015–19',5.2,9.7],['2020–26',4.3,6.2]];
function makeBars(group,{w=0.9,gap=0.55,hmax=6,colors=[0xa78bfa,0x6fa8ff]}={}){
  const g=new THREE.Group(); group.add(g); const bars=SV_ERA.map((e,i)=>{ const x=(i-(SV_ERA.length-1)/2)*(w*2+gap);
    const mk=(c,dx)=>{ const m=new THREE.Mesh(new THREE.BoxGeometry(w,1,w),new THREE.MeshPhysicalMaterial({color:c,emissive:c,emissiveIntensity:GLOW.emissive,transparent:true,opacity:0.85,roughness:0.2,clearcoat:1})); m.geometry.translate(0,0.5,0); m.position.set(x+dx,0,0); g.add(m); return m; };
    const all=mk(colors[0],-w*0.52), wim=mk(colors[1],w*0.52);
    const lab=textSprite(e[0],{color:'#e8e2ff',size:0.42,font:'700 110px "Inter","Noto Sans CJK SC",sans-serif'},g); lab.position.set(x,-0.45,0.6);
    const va=textSprite(e[1].toFixed(1)+'%',{color:'#efe6ff',size:0.42,font:'800 110px "Inter",sans-serif',glow:'rgba(167,139,250,1)'},g);
    const vw=textSprite(e[2].toFixed(1)+'%',{color:'#dfeaff',size:0.36,font:'700 110px "Inter",sans-serif',glow:'rgba(111,168,255,1)'},g);
    return {x,all,wim,lab,va,vw,e}; });
  const base=new THREE.Mesh(new THREE.BoxGeometry(SV_ERA.length*(w*2+gap)+0.6,0.05,1.4),new THREE.MeshBasicMaterial({color:0x8f86d8,transparent:true,opacity:0.5})); g.add(base);
  return {g,bars,hmax}; }
function setBars(Bc,k,{lab=1,wim=1}={}){ Bc.bars.forEach((b,i)=>{ const a=ss(i*0.12,0.4+i*0.12,k); const ha=Math.max(0.001,a*b.e[1]/100*Bc.hmax), hw=Math.max(0.001,a*b.e[2]/100*Bc.hmax);
  b.all.scale.y=ha; b.wim.scale.y=hw; b.wim.visible=wim>0.01; b.wim.material.opacity=0.85*wim; b.all.material.opacity=0.85;
  op(b.lab,a*lab); b.va.position.set(b.x-0.48,ha+0.42,0.5); op(b.va,a*lab); b.vw.position.set(b.x+0.48,hw+0.38,0.5); op(b.vw,a*lab*wim); }); }

// ================== 物件 ==================
const rk=makeRacket();                       // 主球拍（大多数段落用它）
const rkPow=[0,1,2].map(()=>makeRacket());   // 力量段：三种线并排
const ball=makeBall(0.33); const ball2=makeBall(0.33);
const powBalls=[0,1,2].map(()=>makeBall(0.22));
const arrowIn=fatLine(0x4fe3ff,6), arrowOut=fatLine(0xffc24a,6), arrowF=fatLine(0xff5a4a,7), arrowN=fatLine(0xffffff,5);
const spinRing=flatRing(0xffc24a), spinRing2=flatRing(0x4fe3ff), hitRing=flatRing(0xffffff), stampRing=flatRing(0xff3a28);
const sweat=cloud(260,0.06,14);   // 合成线段：水珠
const sparks=cloud(400,0.05,10);  // 磨损火花
const TT={}; const tx=(k,s,o={},grp=scene)=>TT[k]||(TT[k]=textSprite(s,o,grp));
// HUD：贴着镜头放（x,y 是镜头前 d 处的平面坐标；d=9 时可见范围约 ±5.5 × ±3.1）。标题放顶部 y≈2.35、第二行 y≈1.85；底部留给字幕
function hud(o,x,y,d=9){ const v=new THREE.Vector3(x,y,-d).applyQuaternion(camera.quaternion).add(camera.position); if(o.isSprite) o.position.copy(v); else { o.g.position.copy(v); o.g.quaternion.copy(camera.quaternion); } return o; }
const hr=(i,k=0)=>{ const x=Math.sin(i*12.9898+k*78.233+1.7)*43758.5453; return x-Math.floor(x); };   // 文字缓存：键→精灵
const GOLD='rgba(255,194,74,0.95)', CYAN='rgba(79,227,255,0.95)', RED='rgba(255,90,74,0.95)', VIO='rgba(167,139,250,0.95)', MINT='rgba(52,245,168,0.95)';
// 钩子：四代线的标签
const GEN=[['gut',T('1874 · 羊肠线','1874 · Natural gut'),STR.gut,STR.gut],['nylon',T('合成线（尼龙为主）','Synthetic (mostly nylon)'),STR.nylon,STR.nylon],['poly',T('1997 · 聚酯线','1997 · Polyester'),STR.poly,STR.poly],['hyb',T('混搭：主线横线各用一种','Hybrid: two strings, mains vs crosses'),STR.hybridM,STR.hybridC]];
const genLab=GEN.map(([k,s])=>tx('gen_'+k,s,{color:'#ffffff',size:0.62,glow:GOLD}));
const barsG=new THREE.Group(); scene.add(barsG); const bars=makeBars(barsG);
const barsTitle=tx('barsT',T('男子 · 发球上网占比（去掉 ACE）','Men · serve-and-volley share (aces excluded)'),{color:'#efe6ff',size:0.5,glow:VIO},barsG);
const barsNote=tx('barsN',T('紫＝全部标注比赛　蓝＝温网　· Match Charting Project 逐分自算，志愿者标注、非官方','Violet = all charted · Blue = Wimbledon · Match Charting Project, volunteer-charted'),{color:'#cfc8f0',size:0.3},barsG);
// 战术段：聚酯线普及的时间带、同期变化
const bandMesh=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({color:0xb9c8ff,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false})); barsG.add(bandMesh);
const bandLab=tx('band',T('聚酯线普及','Polyester spreads'),{color:'#e6ecff',size:0.48,glow:'rgba(185,200,255,1)'},barsG);
const CONF=[[T('线','Strings'),0xb9c8ff],[T('球拍：大拍面专利 1976','Rackets: oversize patent 1976'),0xffc24a],[T('球：快、中、慢三种','Balls: fast / medium / slow'),0x34f5a8],[T('场地','Courts'),0xff7a3d],[T('体能','Fitness'),0xff4fd8]];
const confG=new THREE.Group(); scene.add(confG);
const confNodes=CONF.map(([s,c],i)=>{ const n=new THREE.Mesh(new THREE.SphereGeometry(0.32,32,20),new THREE.MeshPhysicalMaterial({color:c,emissive:c,emissiveIntensity:GLOW.emissive,roughness:0.2,clearcoat:1,transparent:true})); confG.add(n);
  const lab=textSprite(s,{color:'#ffffff',size:0.42,glow:'rgba(255,255,255,0.6)'},confG); const th=fatLine(c,3); return {n,lab,th,c,i}; });
const knot=glowSprite(0xffffff,2.2,0,confG);
// 掉磅段：张力—log(时间) 曲线（示意形状，按 Cross 2000 实测「随时间的对数线性下降」）
const tenG=new THREE.Group(); scene.add(tenG);
const tenAxis=[fatLine(0xffffff,2),fatLine(0xffffff,2)]; const tenCurves=[['gut',STR.gut,0.040],['nylon',STR.nylon,0.055],['poly',STR.poly,0.085]].map(([k,c,s])=>({k,c,s,l:fatLine(c,5)}));
const tenTicks=[['10 s',1],['100 s',2],[T('15 分钟','15 min'),2.95],[T('1 天','1 d'),4.94],[T('3 天','3 d'),5.41]].map(([s,lx])=>({lx,sp:textSprite(s,{color:'#ffe6d8',size:0.38},tenG)}));
// 场上：线一松，出球更高、往界外飞（示意）
const flyGood=fatLine(0x34f5a8,5,true), flyDead=fatLine(0xff5a4a,5,true);
// 换拍：球拍架
const rackG=new THREE.Group(); scene.add(rackG); const rackR=[0,1,2,3,4,5].map(()=>{ const r=makeRacket(rackG,{nm:10,nc:12}); r.g.scale.setScalar(0.42); return r; });

// ================== 镜头 ==================
const anchors={};
function proj(name,v){ camera.updateMatrixWorld(); const p=v.clone().project(camera); anchors[name]=[(p.x*0.5+0.5)*W,(1-(p.y*0.5+0.5))*H,(p.z<1&&p.z>-1)?1:0]; }
// 运镜全局标准（所有者 2026-11-05「动画的转场和运镜要做的丝滑且有吸引力」，docs/vibetennis.md「转场与运镜」）：
// 每个镜头（两次切换之间）在镜头自己的机位上再缓缓推近 MOVE.push、绕目标转 MOVE.orbit 弧度——不许有静止不动的机位
const MOVE={push:0.06, orbit:0.06, xf:0.6, xfPush:0.04};
let CAMMOVE=null; const UPV=new THREE.Vector3(0,1,0);
function look(px,py,pz,tx_,ty,tz){ const P=new THREE.Vector3(px,py,pz), Tg=new THREE.Vector3(tx_,ty,tz);
  if(CAMMOVE){ const k=ss(0,1,CAMMOVE.u/CAMMOVE.L); const d=P.clone().sub(Tg); d.applyAxisAngle(UPV,(k-0.5)*MOVE.orbit*CAMMOVE.dir); d.multiplyScalar(1-MOVE.push*k); P.copy(Tg).add(d); }
  camera.position.copy(P); camera.lookAt(Tg); }
const DOF={on:false,focus:10,ap:0.00012};
const allRk=[rk,...rkPow,...rackR];

// ---------- 显微镜示意（所有者 2026-11-05「加一个示意的显微镜镜头」）----------
// 三种线的截面：羊肠线＝一缕缕胶原纤维绞成（Wikipedia「Strings (tennis)」：取自肠的浆膜、含胶原）；
// 多股线＝很多根尼龙细丝（同上 Multi-filament 一节）；单丝线＝实心的一根（同上：合成羊肠线几乎都是单丝）。
// 后半：线和线交叉处磨出凹槽（Lindsey, Tennis Warehouse「How Tennis Strings Go Dead」）。全部是示意，不按比例。
const micG=new THREE.Group(); scene.add(micG);
const micMat=(c,o=1)=>new THREE.MeshPhysicalMaterial({color:c,emissive:c,emissiveIntensity:(new THREE.Color(c).getHSL({}).l>0.8?GLOW.emissiveWhite:0.25),metalness:0.1,roughness:0.35,clearcoat:0.8,transparent:true,opacity:o});
// 天然肠线：按美国专利 US 4,449,353（Tayebi 1984）背景节写的「常规肠线」——16 条牛肠衣带，中心 1 条、中层 6 条、外层 9 条，
// 外层螺旋角约 20.4°（图 3、第 5–6 栏）；成品通常有涂层防散开（Wikipedia「Strings (tennis)」）。截面上画成圆股，示意。
const GUT_HELIX=20.4*Math.PI/180;
function helixBundle(rad,len,col,fr){ const g=new THREE.Group(), mat=micMat(col);
  const slots=[[0,0]]; for(let i=0;i<6;i++) slots.push([0.36,i/6]); for(let i=0;i<9;i++) slots.push([0.72,i/9+0.05]);
  const turns=Math.tan(GUT_HELIX)*len/(2*Math.PI*0.72*rad);   // 外层螺旋角 20.4°
  for(const [ring,f] of slots){ const a0=f*Math.PI*2;
    const pts=[]; for(let k=0;k<=40;k++){ const y=-len/2+len*k/40, a=a0+turns*2*Math.PI*k/40; pts.push(new THREE.Vector3(Math.cos(a)*rad*ring,y,Math.sin(a)*rad*ring)); }
    g.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),60,fr,12),mat));
    // 只给剥开的上端一个平切面（下端藏在涂层里）：切面朝向沿这一股的切线
    const tg=pts[40].clone().sub(pts[39]).normalize(); const cap=new THREE.Mesh(new THREE.CircleGeometry(fr,20),mat);
    cap.position.copy(pts[40]); cap.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),tg); g.add(cap); }
  return g; }
// 涂层套：包住下面大半截，上端剥开露出里面的结构（像剪开的电缆）
function coatSleeve(group,rad,len,frac,col,opa){ const h=len*frac, m=new THREE.Mesh(new THREE.CylinderGeometry(rad,rad,h,64),
    new THREE.MeshPhysicalMaterial({color:col,metalness:0.05,roughness:0.45,clearcoat:0.6,transparent:true,opacity:opa}));
  m.position.y=-len/2+h/2; group.add(m); return m; }
const micGut=helixBundle(1.0,3.2,0xffc27a,0.24); micG.add(micGut); coatSleeve(micGut,1.0,3.2,0.6,0xd9a35c,0.85);
const micMulti=new THREE.Group(); micG.add(micMulti);
// 多股丝：所有者 2026-11-05「多股线的光晕太亮了」——白色＋自发光＋端面正对光源会冲过泛光阈值，压暗颜色、去掉自发光、降低光泽
const mfMat=new THREE.MeshPhysicalMaterial({color:0x9fb8cc,emissive:0x0c1822,emissiveIntensity:1,metalness:0.05,roughness:0.6,clearcoat:0.2,transparent:true});
// 多股线：很多根尼龙细丝（Wikipedia「Strings (tennis)」Multi-filament 节，根数示意），外面一层耐磨涂层（同页：nylon 线、尤其多股线常见）
{ const r=0.11; for(let q=-6;q<=6;q++) for(let w=-6;w<=6;w++){ const x=(q+w*0.5)*r*2.05, z=w*r*1.78; if(Math.hypot(x,z)>0.98) continue;
    const m=new THREE.Mesh(new THREE.CylinderGeometry(r,r,3.2,10),mfMat); m.position.set(x,0,z); micMulti.add(m); }
  coatSleeve(micMulti,1.08,3.2,0.6,0x6f8396,0.92); }
const micMono=new THREE.Mesh(new THREE.CylinderGeometry(1.05,1.05,3.2,48),new THREE.MeshPhysicalMaterial({color:0xc9b8ff,emissive:0x5a46a8,emissiveIntensity:0.35,metalness:0.2,roughness:0.12,clearcoat:1,transparent:true})); micG.add(micMono);
// 交叉处：主线竖、横线压在上面，主线表面一道凹槽（示意）
const micMain=new THREE.Mesh(new THREE.CylinderGeometry(0.7,0.7,9,48),micMat(0xaec4d6)); micG.add(micMain);   // 整根占半屏，纯白会把 bright 冲过 5%
const micCross=new THREE.Mesh(new THREE.CylinderGeometry(0.7,0.7,9,48),micMat(0x9aa8dc)); micCross.rotation.z=Math.PI/2; micG.add(micCross);
const micGrooveH=new THREE.Group(); micG.add(micGrooveH); micGrooveH.rotation.y=-Math.PI/6;
const micGroove=new THREE.Mesh(new THREE.TorusGeometry(0.7,0.16,14,64,Math.PI*2/3),new THREE.MeshBasicMaterial({color:new THREE.Color(0xffb347).multiplyScalar(GLOW.k*1.6),transparent:true,blending:THREE.AdditiveBlending,depthWrite:false})); micGroove.rotation.x=Math.PI/2; micGrooveH.add(micGroove);
const micLens=new THREE.Mesh(new THREE.RingGeometry(0.64,2.2,128),new THREE.MeshBasicMaterial({color:0x000000,transparent:true,opacity:0.9,depthTest:false})); micLens.renderOrder=999; scene.add(micLens);
const micRim=new THREE.Mesh(new THREE.RingGeometry(0.632,0.642,160),new THREE.MeshBasicMaterial({color:0x4fe3ff,transparent:true,opacity:0.6,depthTest:false})); micRim.renderOrder=1000; scene.add(micRim);
function shotMicro(v,TG,TM,TO,TN){ // v：从这一镜开始的秒数；TG/TM/TO：三种线依次亮出；TN：切到交叉凹槽
  micG.visible=true; rimL.intensity=5; rimL.color.set(0xbfe8ff); rimL.position.set(-3,3,4); rimR.intensity=3; rimR.position.set(4,1,3); DOF.on=false;
  const notch=ss(TN-0.3,TN+0.4,v);
  if(notch<1){ look(0,0.0,lerp(11.5,10.5,ss(0,TN,v)),0,0,0);
    [[micGut,-2.25,TG],[micMulti,0,TM],[micMono,2.25,TO]].forEach(([o,x,t])=>{ o.visible=true; o.position.set(x,0.35,0); o.rotation.set(0.85,v*0.25,0.18); o.scale.setScalar(0.62*ss(t-0.2,t+0.5,v)*(1-notch)+0.0001); });
    micMain.visible=micCross.visible=false; micGroove.visible=false;
    const labs=[['mlg',T('天然肠线','Natural gut'),'#ffd9a8',-2.25,TG],['mlm',T('多股线','Multifilament'),'#eaf6ff',0,TM],['mlo',T('单丝线','Monofilament'),'#ddd2ff',2.25,TO]];
    labs.forEach(([k,str,c,x,t])=>{ const l=tx(k,str,{color:c,size:LANG==='en'?0.3:0.4}); l.position.set(LANG==='en'?x*0.9:x,-1.25,0.5); op(l,ss(t,t+0.5,v)*(1-notch)); });
  } else { micGut.visible=micMulti.visible=micMono.visible=false; }
  if(notch>0){ const w=v-TN; look(3.6,2.8,8.2,0,0.15,0);
    micMain.visible=micCross.visible=true; micGroove.visible=true; micMain.position.set(0,0,0);
    const lift=ss(1.6,2.6,w); micCross.position.set(0,lift*3.2,1.38+lift*2.5); micCross.material.opacity=1-lift;
    micGroove.material.opacity=0.95*ss(1.8,2.6,w)*(0.75+0.25*Math.sin(w*5));
  }
  const t=tx('micT',T('放大看（示意）','Magnified (illustrative)'),{color:'#ffffff',size:0.5,glow:CYAN}); hud(t,0,2.05); op(t,ss(0.2,0.8,v));
  // 显微镜圆视场：最后放，跟着这一帧的机位
  camera.updateMatrixWorld(); const fwd=new THREE.Vector3(); camera.getWorldDirection(fwd);
  for(const m of [micLens,micRim]){ m.visible=true; m.position.copy(camera.position).addScaledVector(fwd,2.0); m.quaternion.copy(camera.quaternion); }
  micLens.material.opacity=ss(0,0.6,v); micRim.material.opacity=0.6*ss(0,0.6,v);
}
function hideAll(){
  courtG.visible=false; allRk.forEach(r=>{ r.g.visible=false; r.g.position.set(0,0,0); r.g.rotation.set(0,0,0); r.g.scale.setScalar(r.g.parent===rackG?0.42:1); r.frameMat.opacity=1; });
  for(const b of [ball,ball2,...powBalls]){ b.m.visible=false; b.gl.visible=false; b.m.scale.set(1,1,1); b.m.material.opacity=1; b.gl.material.opacity=0.35; }
  for(const l of [arrowIn,arrowOut,arrowF,arrowN,flyGood,flyDead,...tenAxis,...tenCurves.map(c=>c.l),...confNodes.map(c=>c.th)]) l.material.opacity=0;
  for(const r of [spinRing,spinRing2,hitRing,stampRing]) r.material.opacity=0; chide(sweat); chide(sparks);
  for(const k in TT) op(TT[k],0); genLab.forEach(s=>op(s,0));
  micG.visible=false; micLens.visible=false; micRim.visible=false; barsG.visible=false; bandMesh.material.opacity=0; confG.visible=false; knot.material.opacity=0; tenG.visible=false; rackG.visible=false;
  for(const k in text3D) t3op(text3D[k],0); beamMat.uniforms.uOp.value=0; rimL.intensity=0; rimR.intensity=0; DOF.on=false; MOTE_SPEED=1; }
const showB=(b,p,vis=true)=>{ b.m.visible=vis; b.gl.visible=vis; if(vis){ b.m.position.copy(p); b.gl.position.copy(p); } };
// 一次斜向撞击：球从 dir 方向斜着撞向线床中心，压扁、带着转离开。k 0→1；返回球心（拍子本地坐标）
function impact(R,b,k,{spin=1,ang=0.75,squash=0.35}={}){
  const r=b.r, inDir=new THREE.Vector3(Math.sin(ang),0,Math.cos(ang)), out=new THREE.Vector3(-Math.sin(ang)*0.55,0,Math.cos(ang));
  let p; if(k<0.45){ const u=k/0.45; p=inDir.clone().multiplyScalar(lerp(5.5,r,u)); b.m.scale.set(1,1,1); }
  else if(k<0.55){ const u=(k-0.45)/0.1; const sq=Math.sin(Math.PI*u)*squash; p=new THREE.Vector3(0,0,r*(1-sq)); b.m.scale.set(1+sq*0.6,1+sq*0.6,1-sq); }
  else { const u=(k-0.55)/0.45; p=out.clone().multiplyScalar(lerp(r,6.5,u)); b.m.scale.set(1,1,1); }
  b.m.rotation.y=(k>0.5?(k-0.5)*30*spin:0); b.m.rotation.x=0.4;
  const w=p.clone().applyMatrix4(R.g.matrixWorld); showB(b,w);
  const fade=ss(0,0.1,k)*(1-ss(0.9,1,k)); b.m.material.transparent=true; b.m.material.opacity=fade; b.gl.material.opacity=0.35*fade;   // 循环首尾淡入淡出，不瞬移
  return w; }

function shotHook(u,D){
  const DR=ev('drop',5.3), QQ=ev('q',9.8);
  rk.g.visible=true; R_spin(rk,u); const shrink=ss(DR-0.3,DR+0.9,u);
  rk.g.position.set(lerp(0,-6.2,shrink),lerp(0,0.6,shrink),0); rk.g.scale.setScalar(lerp(1.15,0.8,shrink));
  look(0,0.4,lerp(9.5,13,shrink),lerp(0,0,shrink),0.3,0); beamMat.uniforms.uOp.value=0.12; rimL.intensity=5; rimR.intensity=5; rimL.position.set(-4,3,4); rimR.position.set(4,3,4);
  const gi=clamp(Math.floor((u-0.4)/((DR-0.4)/4)),0,3); const gk=((u-0.4)/((DR-0.4)/4))%1; const [,lab,cm,cc]=GEN[gi];
  setBed(rk,{cm,cc,opm:ss(0,0.6,u),opc:ss(0,0.6,u)});
  genLab.forEach((s,i)=>{ hud(s,0,2.05); op(s,(i===gi?ss(0,0.15,gk)*(u<DR?1:1-ss(DR,DR+0.4,u)):0)); });
  barsG.visible=u>DR-0.2; barsG.position.set(1.9,-1.7,0); barsG.scale.setScalar(0.74); setBars(bars,ss(DR,DR+2.6,u)); barsTitle.position.set(0,6.6,0); op(barsTitle,ss(DR+0.2,DR+0.9,u)*(1-ss(QQ-0.3,QQ+0.2,u)));
  barsNote.position.set(0,-1.1,0.5); op(barsNote,ss(DR+1,DR+1.8,u));
  const q=tx('hookQ',T('是线，改变了网球吗？','Did the strings change tennis?'),{color:'#ffffff',size:1.0,font:'900 150px "Noto Sans CJK SC","Inter",sans-serif',glow:GOLD});
  hud(q,0,2.0); op(q,ss(QQ,QQ+0.5,u)); proj('racket',rk.g.position);
}
function R_spin(R,u,amp=0.35){ R.g.rotation.y=Math.sin(u*0.45)*amp; R.g.rotation.x=-0.08; }
function shotGut(u,D){
  const HI=ev('hit',3.2), CO=ev('cor',10.2);
  rk.g.visible=true; rk.g.rotation.set(0,-0.55,0); rk.g.position.set(1.2,0,0); look(lerp(4.6,3.8,ss(0,D,u)),1.2,8.8,0.4,0.35,0); DOF.on=true; DOF.focus=9.2; DOF.ap=0.00006; rk.g.updateMatrixWorld(true);
  rimL.intensity=6; rimL.position.set(-3,2,3); rimL.color.set(0xffb347);
  setBed(rk,{cm:STR.gut,cc:STR.gut,width:2.8});
  const t1=tx('gut1874',T('1874 · 第一批草地网球拍：羊肠衣','1874 · First lawn-tennis rackets: sheep gut'),{color:'#ffe9c8',size:0.5,glow:GOLD}); hud(t1,0,2.05); op(t1,ss(0.3,1,u)*(1-ss(HI-0.5,HI,u)));
  const t1s=tx('gut1874s',T('国际网联资料','ITF'),{color:'#d8c09a',size:0.3}); hud(t1s,0,1.55); op(t1s,ss(0.6,1.2,u)*(1-ss(HI-0.5,HI,u)));
  // 撞击循环：慢放，一次 4 秒
  const k=u<HI?0:((u-HI)%4.2)/4.2; rk.g.updateMatrixWorld(true);
  if(u>=HI){ const p=impact(rk,ball,k,{spin:0.25,ang:0.0,squash:0.32});
    const c=new THREE.Vector3(0,0,0).applyMatrix4(rk.g.matrixWorld); const nrm=new THREE.Vector3(0,0,1).transformDirection(rk.g.matrixWorld);
    const vin=k<0.45?ss(0,0.2,k):1-ss(0.45,0.5,k), vout=ss(0.55,0.75,k)*(1-ss(0.9,1,k));
    setLine(arrowIn,[c.clone().addScaledVector(nrm,3.3),c.clone().addScaledVector(nrm,0.55)]); arrowIn.material.opacity=vin*0.9;
    setLine(arrowOut,[c.clone().addScaledVector(nrm,0.55),c.clone().addScaledVector(nrm,0.55+2.75*0.75)]); arrowOut.material.opacity=vout*0.9;
    const l1=tx('v1',T('撞上 v₁','In  v₁'),{color:'#bff4ff',size:0.42,glow:CYAN}); l1.position.copy(c.clone().addScaledVector(nrm,3.0).add(new THREE.Vector3(0,0.55,0))); op(l1,vin);
    const l2=tx('v2',T('弹开 v₂','Out  v₂'),{color:'#ffe6b0',size:0.42,glow:GOLD}); l2.position.copy(c.clone().addScaledVector(nrm,2.3).add(new THREE.Vector3(0,-0.6,0))); op(l2,vout);
    const hk=k>0.45&&k<0.6?1-Math.abs(k-0.5)/0.1:0; hitRing.position.copy(c); hitRing.quaternion.copy(rk.g.quaternion); hitRing.rotateX(Math.PI/2); hitRing.scale.setScalar(0.6+hk*1.6); hitRing.material.opacity=hk*0.8;
    proj('ball',p); }
  const f=tx('corF',T('恢复系数 e ＝ v₂ ÷ v₁','Coefficient of restitution  e = v₂ / v₁'),{color:'#ffffff',size:0.78,font:'900 140px "Noto Sans CJK SC","Inter",sans-serif',glow:GOLD}); hud(f,0,2.0); op(f,ss(CO-0.2,CO+0.5,u)); op(t1,0); op(t1s,0);
  const fn=tx('corN',T('牛顿最早测量这个比值 · 《自然哲学的数学原理》1687','First measured by Newton · Principia, 1687'),{color:'#ffe9c8',size:0.38}); hud(fn,0,1.55); op(fn,ss(CO+0.3,CO+1,u));
}
function shotSynth(u,D){
  const MI=ev('micro',99); if(u>=MI-0.2){ const b=MI-0.2; shotMicro(u-b,ev('mgut',MI+0.5)-b,ev('mmulti',MI+2)-b,ev('mmono',MI+4)-b,ev('notch',MI+7)-b); return; }
  const SW_=ev('swap',4.0); rk.g.visible=true; R_spin(rk,u,0.25); look(0,0.55,9.6,0,0.55,0); rimL.intensity=4; rimL.position.set(-3,2,3);
  const k=ss(SW_-0.2,SW_+1.2,u); const cmix=C(STR.gut).lerp(C(STR.nylon),k).getHex();
  setBed(rk,{cm:cmix,cc:cmix,width:2.6});
  // 水珠挂在线上（怕潮）、交叉点冒火花（磨损）——换成合成线后消失
  rk.g.updateMatrixWorld(true); for(let i=0;i<260;i++){ const x=(hr(i,1)-0.5)*2*B*0.8, y=(hr(i,2)-0.5)*2*A*0.8; const p=new THREE.Vector3(x,y-((u*0.3+hr(i,3))%1)*0.25,0.05).applyMatrix4(rk.g.matrixWorld);
    cset(sweat,i,p.x,p.y,p.z,0.6,0.85,1,(1-k)*ss(0.3,1.2,u)*0.9); } cdone(sweat);
  for(let i=0;i<400;i++){ const p=new THREE.Vector3((hr(i,4)-0.5)*2.2,(hr(i,5)-0.5)*2.8,0.08+((u*1.7+hr(i,6))%1)*0.6).applyMatrix4(rk.g.matrixWorld); cset(sparks,i,p.x,p.y,p.z,1,0.7,0.3,(1-k)*ss(1,1.8,u)*(hr(i,7)<0.5?1:0.3)); } cdone(sparks);
  const a=tx('gutBad',T('羊肠线：贵 · 不耐磨 · 怕潮','Natural gut: costly · wears · hates moisture'),{color:'#ffe9c8',size:0.55,glow:GOLD}); hud(a,0,2.05); op(a,ss(0.3,1,u)*(1-ss(SW_-0.3,SW_+0.2,u)));
  const b=tx('synGood',T('合成线：尼龙为主，也有聚酯、凯夫拉','Synthetics: mostly nylon; also polyester, Kevlar'),{color:'#eaf6ff',size:0.55,glow:CYAN}); hud(b,0,2.05); op(b,ss(SW_+0.3,SW_+1,u));
  const s=tx('synSrc',T('国际网联资料','ITF'),{color:'#a8c4d8',size:0.3}); hud(s,0,1.55); op(s,ss(0.5,1.2,u));
}
function shotSpag(u,D){
  const PA=ev('patent',0.5), SL_=ev('slide',6.5), BA=ev('ban',14.2), RO=ev('roll',17.1);
  const banK=ss(BA+0.6,BA+2.2,u);
  if(u<RO){
    rk.g.visible=true; rk.g.position.set(0.9,0,0); rk.g.rotation.set(-0.12,lerp(-0.75,-0.45,ss(0,SL_,u)),0); look(lerp(4.6,3.6,ss(0,D,u)),1.0,7.6,0.3,0.0,0); DOF.on=true; DOF.focus=8.2; DOF.ap=0.00006;
    rimL.intensity=6; rimL.color.set(0xff5a4a); rimL.position.set(-3,2,3);
    const z=lerp(0.11,0,banK); const k=u<SL_?0:((u-SL_)%3.6)/3.6; rk.g.updateMatrixWorld(true);
    const sl=u>=SL_&&u<BA+0.6?slideField(0.55*(1-banK),0,0,k):null;
    setBed(rk,{cm:STR.spag,cc:STR.spag,zm:z,zc:-z,crossSet:banK<0.5?[2,6,9,12,16]:null,slide:sl,width:2.8});
    if(u>=SL_&&u<BA+0.6){ const p=impact(rk,ball,k,{spin:3.0,ang:0.95,squash:0.25});
      spinRing.position.copy(p); spinRing.quaternion.copy(camera.quaternion); spinRing.scale.setScalar(1.3+0.2*Math.sin(u*20)); spinRing.material.opacity=0.9*ss(0.5,0.6,k)*(1-ss(0.9,1,k)); proj('ball',p); }
    const pt=tx('pat',T('美国专利 US 4,273,331 · 发明人 Werner Fischer（联邦德国）· 1977 年申请','US Patent 4,273,331 · Werner Fischer (W. Germany) · filed 1977'),{color:'#ffe0da',size:0.42,glow:RED}); hud(pt,0,2.05); op(pt,ss(PA,PA+0.8,u)*(1-ss(SL_-0.3,SL_,u)));
    const pt2=tx('pat2',T('主线和横线不编织，分在两层','Mains and crosses not interlaced — two layers'),{color:'#ffffff',size:0.5,glow:RED}); hud(pt2,0,1.55); op(pt2,ss(PA+1,PA+1.8,u)*(1-ss(SL_-0.3,SL_,u)));
    const x2=tx('x2',T('转速 ≈ 普通球拍的 2 倍（实验室）','Spin ≈ 2× a conventional racket (lab)'),{color:'#ffe6b0',size:0.6,glow:GOLD}); hud(x2,0,2.05); op(x2,ss(SL_+1.5,SL_+2.3,u)*(1-ss(BA-0.3,BA,u)));
    const x2s=tx('x2s',T('Goodwill & Haake 2002','Goodwill & Haake 2002'),{color:'#d8c09a',size:0.3}); hud(x2s,0,1.55); op(x2s,ss(SL_+2,SL_+2.6,u)*(1-ss(BA-0.3,BA,u)));
    const bn=tx('ban',T('1978 · 国际网联：主线横线必须交错编织或粘合','1978 · ITF: strings must be interlaced or bonded'),{color:'#ffffff',size:0.55,glow:RED}); hud(bn,0,2.05); op(bn,ss(BA,BA+0.6,u)*(1-ss(RO-0.4,RO,u)));
    const st=tx('stamp',T('禁','BANNED'),{color:'#ffd8d2',size:2.2,font:'900 170px "Noto Sans CJK SC","Inter",sans-serif',glow:'rgba(255,60,40,1)'}); hud(st,1.2,-0.2,8); const sk=ss(BA+0.05,BA+0.65,u);   // 盖章 0.6 s 落下（原 0.25 s，相邻帧差冲到 25） st.scale.set(st.userData.w0||(st.userData.w0=st.scale.x),2.2,1); st.material.rotation=-0.2; op(st,sk*(1-ss(BA+2.6,BA+3.2,u)));
    stampRing.position.copy(st.position); stampRing.quaternion.copy(camera.quaternion); stampRing.scale.setScalar(lerp(6,3.2,sk)); stampRing.material.opacity=sk*(1-ss(BA+2.6,BA+3.2,u))*0.9;
    // 不闪白、不抖屏：闪白在线性空间里混，0.1 到屏上就是三成多的亮度跳变（motion_check 抓到 65.5 s 相邻帧差 90 → 25），盖章本身的落下和光环已经够有冲击
    return; }
  // 库仑：横截面慢放——球贴着线滑（摩擦力∝压力），接触点停住后滚起来
  const v=u-RO; look(0,0.6,6.2,0,0.4,0); DOF.on=false;
  const strip=rk; strip.g.visible=true; strip.g.rotation.set(-Math.PI/2+0.02,0,0); strip.g.position.set(0,0.1,0); strip.g.scale.setScalar(1.6); strip.neck.visible=false; setBed(strip,{cm:0xff8a7a,cc:0xff8a7a,width:3}); strip.frameMat.opacity=0.25;
  const k=clamp(v/6.0); const xs=lerp(-2.6,2.6,k); const rol=ss(0.45,0.55,k); const by=0.1+0.53+0.02;
  showB(ball,new THREE.Vector3(xs,by,0)); ball.m.scale.setScalar(1.6); ball.m.rotation.z=-(rol>0?(xs-lerp(-2.6,2.6,0.5))/0.53:0)-(1-rol)*0.2*k;
  const fOn=1-rol; setLine(arrowF,[new THREE.Vector3(xs,-0.06,0.3),new THREE.Vector3(xs-1.3*fOn-0.01,-0.06,0.3)]); arrowF.material.opacity=0.95*fOn*ss(0,0.1,k);
  setLine(arrowN,[new THREE.Vector3(xs,by+1.3,0.3),new THREE.Vector3(xs,by+0.55,0.3)]); arrowN.material.opacity=0.8*ss(0,0.1,k);
  const lf=tx('fric',T('摩擦力 ∝ 压力（库仑）','Friction ∝ normal force (Coulomb)'),{color:'#ffd2c8',size:0.5,glow:RED}); lf.position.set(clamp(xs-0.4,-1.6,1.6),0.45,0.9); op(lf,fOn*ss(0,0.1,k));
  const ph=tx(rol>0.5?'roll':'slide',rol>0.5?T('接触点停住 → 滚起来','Contact point stops → rolling'):T('先滑','Sliding first'),{color:'#ffffff',size:0.62,glow:GOLD}); hud(ph,0,2.05); op(ph,ss(0,0.1,k));
  const src=tx('rollSrc',T('所有线的摩擦都大到让球在撞击中滚起来 · Goodwill & Haake 2004','All strings grip enough for the ball to roll · Goodwill & Haake 2004'),{color:'#d8c09a',size:0.32}); hud(src,0,1.55); op(src,ss(0.5,0.6,k));
  proj('ball',new THREE.Vector3(xs,by,0));
}
function shotPoly(u,D){
  const Y1=ev('y1997',0.5), Y2=ev('y2010',5.0), PR=ev('pro',11.2), CN=ev('con',12.9), SN=ev('snap',18.9);
  rk.g.visible=true; rimL.intensity=5; rimL.color.set(0x7c83ff); rimL.position.set(-3,2,3); rimR.intensity=4; rimR.color.set(0xc9d6ff); rimR.position.set(3,2,3);
  if(u<PR-0.2){ rk.g.rotation.set(-0.1,Math.sin(u*0.4)*0.3,0); look(0,0.3,8.4,0,0.2,0); setBed(rk,{cm:STR.poly,cc:STR.poly,width:2.6});
    const y1=t3d('y1997','1997',0xc9d6ff,0.9); hud(y1,-3.6,1.2); t3op(y1,ss(Y1,Y1+0.6,u)*(1-ss(Y2-0.4,Y2,u)));
    const l1=tx('p1997',T('库尔滕用 Luxilon 聚酯线拿下法网','Kuerten wins Roland-Garros on Luxilon polyester'),{color:'#e6ecff',size:0.5,glow:'rgba(185,200,255,1)'}); hud(l1,0,2.05); op(l1,ss(Y1+0.4,Y1+1,u)*(1-ss(Y2-0.4,Y2,u)));
    const y2=t3d('y2010','2010',0xc9d6ff,0.9); hud(y2,-3.6,1.2); t3op(y2,ss(Y2,Y2+0.6,u)*(1-ss(PR-0.6,PR-0.2,u)));
    const l2=tx('p2010',T('温网：男选手都用聚酯线（据温网穿线师）','Wimbledon: all men on polyester (per the head stringer)'),{color:'#e6ecff',size:0.5,glow:'rgba(185,200,255,1)'}); hud(l2,0,2.05); op(l2,ss(Y2+0.4,Y2+1,u)*(1-ss(PR-0.6,PR-0.2,u)));
    return; }
  if(u<SN-0.2){ // 正反两方
    rk.g.visible=false; look(0,1.0,11,0,1.0,0);
    const pro=ss(PR,PR+0.6,u), con=ss(CN,CN+0.6,u);
    const pc=t3d('pro20','+20%',0xffc24a,1.1); pc.g.position.set(-3.6,2.4,0); pc.g.quaternion.copy(camera.quaternion); t3op(pc,pro);
    const pl=tx('proL',T('聚酯比尼龙多转（实验室）','Polyester out-spins nylon (lab)'),{color:'#ffe6b0',size:0.5,glow:GOLD}); pl.position.set(-3.6,0.9,0); op(pl,pro);
    const ps=tx('proS',T('Tennis Warehouse 科普站 · 非同行评审','Tennis Warehouse University · not peer-reviewed'),{color:'#d8c09a',size:0.32}); ps.position.set(-3.6,0.25,0); op(ps,pro);
    const cc=t3d('con0','0',0x4fe3ff,1.1); cc.g.position.set(3.6,2.4,0); cc.g.quaternion.copy(camera.quaternion); t3op(cc,con);
    const cl=tx('conL',T('线材、粗细、磅数都不影响转速','Material, gauge, tension: no effect on spin'),{color:'#d8f6ff',size:0.5,glow:CYAN}); cl.position.set(3.6,0.9,0); op(cl,con);
    const cs=tx('conS',T('Goodwill & Haake 2004（同行评审）· 国际网联','Goodwill & Haake 2004 (peer-reviewed) · ITF'),{color:'#a8c4d8',size:0.32}); cs.position.set(3.6,0.25,0); op(cs,con);
    const vs=tx('vs',T('两边结论相反','The two disagree'),{color:'#ffffff',size:0.62,glow:'rgba(255,255,255,0.7)'}); vs.position.set(0,-1.2,0); op(vs,ss(CN+1,CN+1.8,u));
    return; }
  // 共识：线能不能滑开再弹回
  const v=u-SN; rk.g.rotation.set(-0.15,-0.6,0); look(5.0,1.2,7.6,0,0.2,0); DOF.on=true; DOF.focus=8.6; DOF.ap=0.00007;
  const k=(v%3.4)/3.4; rk.g.updateMatrixWorld(true); setBed(rk,{cm:STR.poly,cc:STR.poly,slide:slideField(0.28,0,0,k),width:2.6});
  const p=impact(rk,ball,k,{spin:2.0,ang:0.95,squash:0.25}); spinRing.position.copy(p); spinRing.quaternion.copy(camera.quaternion); spinRing.scale.setScalar(1.2); spinRing.material.opacity=0.8*ss(0.5,0.6,k)*(1-ss(0.9,1,k));
  const t=tx('snapT',T('大家都认的：线滑开 → 千分之一秒内弹回','Agreed: strings slide → snap back within 1 ms'),{color:'#ffffff',size:0.55,glow:'rgba(185,200,255,1)'}); hud(t,0,2.05); op(t,ss(0.3,1,v));
  const t2=tx('snapS',T('减少横线、给线润滑，转速也会增加（实验室）','Fewer crosses or lubricated strings also add spin (lab)'),{color:'#c8d2f0',size:0.34}); hud(t2,0,1.55); op(t2,ss(1,1.6,v));
  proj('ball',p);
}
function shotPower(u,D){
  const BA_=ev('bars',1.5); look(0,0.2,13.5,0,0.0,0); rimL.intensity=4; rimL.color.set(0x34f5a8); rimL.position.set(-4,3,4);
  [['gut',STR.gut,T('羊肠线','Gut')],['nylon',STR.nylon,T('尼龙','Nylon')],['poly',STR.poly,T('聚酯','Polyester')]].forEach(([k_,c,nm],i)=>{ const R=rkPow[i]; R.g.visible=true; R.g.position.set((i-1)*4.3,0.4,0); R.g.scale.setScalar(0.72); R.g.rotation.set(0,-0.25,0); R.g.updateMatrixWorld(true);
    setBed(R,{cm:c,cc:c,width:2.0}); const k=u<BA_?0:((u-BA_+i*0.15)%3.0)/3.0; impact(R,powBalls[i],k,{spin:0.3,ang:0.0,squash:0.3});
    const bar=t3d('pw'+i,'95%',c,0.42); bar.g.position.set((i-1)*4.3,-2.6,0.5); bar.g.quaternion.copy(camera.quaternion); t3op(bar,ss(BA_+0.6,BA_+1.4,u));
    const n=tx('pwn'+i,nm,{color:'#ffffff',size:0.5}); n.position.set((i-1)*4.3,1.85,0.3); op(n,ss(0.2,0.8,u)); });
  const a=tx('pwA',T('实验室：换线材，球速变化很小','Lab: changing string material barely changes ball speed'),{color:'#eafff6',size:0.58,glow:MINT}); hud(a,0,2.05); op(a,ss(BA_,BA_+0.7,u));
  const b=tx('pwB',T('各种线都能把吃进去的能量还回约 95% · 90 种线实测差别可忽略（Cross 等 2000）','Strings return ~95% of energy · 90 strings tested (Cross et al. 2000)'),{color:'#bfe8d8',size:0.32}); hud(b,0,1.55); op(b,ss(BA_+1.2,BA_+1.9,u));
}
function shotTension(u,D){
  const CU=ev('curve',2.6), FL=ev('fly',10.2), SWP=ev('swap',13.6);
  if(u<FL-0.3){ // 张力随 log(时间)
    tenG.visible=true; look(0,1.8,11.5,0,1.8,0); tenG.position.set(-3.6,-0.15,0);
    const X=x=>x*1.45, Y=y=>y*(LANG==='en'?3.85:4.3);   // 英文标题更宽，会压到曲线起点：纵向压矮一点            // x：log10(秒)（0→1 秒）；y：张力占设定的比例
    setLine(tenAxis[0],[new THREE.Vector3(0,0,0),new THREE.Vector3(X(5.6),0,0)].map(p=>p.add(tenG.position))); setLine(tenAxis[1],[new THREE.Vector3(0,0,0),new THREE.Vector3(0,Y(1.05),0)].map(p=>p.add(tenG.position)));
    tenAxis.forEach(a=>a.material.opacity=0.7*ss(0,0.6,u));
    tenTicks.forEach(tk=>{ tk.sp.position.set(X(tk.lx),-0.35,0); op(tk.sp,ss(0.3,0.9,u)); });
    const top=tx('t100',T('拉线机设定 100%','Set: 100%'),{color:'#ffe6d8',size:0.34},tenG); top.position.set(-1.35,Y(0.84),0); op(top,ss(0.3,0.9,u));
    const dr=ss(CU,CU+4,u);
    tenCurves.forEach(c=>{ const pts=[new THREE.Vector3(0,Y(1),0)]; for(let i=0;i<=40;i++){ const lx=1+i/40*4.41*dr; const y=0.72-c.s*(lx-1); pts.push(new THREE.Vector3(X(lx),Y(y),0)); }
      setLine(c.l,pts.map(p=>p.add(tenG.position))); c.l.material.opacity=ss(CU,CU+0.4,u); });
    const d30=tx('d30',T('刚穿好：比设定低约 30%（Cross & Bower 2001）','Right after stringing: ~30% below pull tension'),{color:'#ffd2bc',size:0.4,glow:'rgba(255,122,61,1)'},tenG); d30.position.set(X(2.6),Y(0.86),0); op(d30,ss(CU+0.4,CU+1.2,u));
    const nm=[[T('羊肠线','Gut'),'#ffd28a'],[T('尼龙','Nylon'),'#eaf6ff'],[T('聚酯 掉得最快','Polyester — fastest'),'#c9d6ff']];
    tenCurves.forEach((c,i)=>{ const s=tx('tn'+i,nm[i][0],{color:nm[i][1],size:0.36},tenG); s.position.set(X(5.6)+0.9,Y(0.72-c.s*4.41*dr),0); op(s,ss(CU+3,CU+4,u)); });
    const note=tx('tnote',T('曲线形状为示意：实测是随时间的对数线性下降（Cross 等 2000）','Shape illustrative: tension falls linearly with log(time) (Cross et al. 2000)'),{color:'#c8a898',size:0.3},tenG); note.visible=false;
    const rel=tx('relax',T('应力松弛 · 麦克斯韦最早提出「弛豫时间」','Stress relaxation · Maxwell\'s “time of relaxation”'),{color:'#ffffff',size:0.5,glow:'rgba(255,122,61,1)'});
    const yl=tx('tenY',T('张力','Tension'),{color:'#ffe6d8',size:0.36},tenG); yl.position.set(-0.6,Y(0.55),0); op(yl,ss(0.3,0.9,u));
    const xl=tx('tenX',T('时间（对数刻度）','Time (log scale)'),{color:'#ffe6d8',size:0.34},tenG); xl.position.set(X(5.6)+1.1,0.35,0); op(xl,ss(0.3,0.9,u)); hud(rel,0,2.05); op(rel,ss(0.4,1.1,u));
    return; }
  if(u<SWP-0.2){ // 场上：线一松，出球角度变高，往界外飞（示意）
    courtG.visible=true; look(-27,7.5,-0.5,0,1.2,-0.5); beamMat.uniforms.uOp.value=0.15; beamMat.uniforms.uC.value.set(0xffb08a);
    const v=u-FL; const k=clamp(v/2.6);
    const traj=(ang,land)=>{ const pts=[]; const p0=new THREE.Vector3(0.5,1.0,L-1.0); for(let i=0;i<=40;i++){ const s=i/40*k; const z=lerp(p0.z,land,s); pts.push(new THREE.Vector3(lerp(p0.x,-1.0,s),p0.y+Math.sin(Math.PI*s)*ang,z)); } return pts; };
    setLine(flyGood,traj(2.0,-L+2.0)); flyGood.material.opacity=0.95; setLine(flyDead,traj(3.0,-L-1.6)); flyDead.material.opacity=0.95; flyGood.material.dashOffset=-u; flyDead.material.dashOffset=-u;
    const a=tx('flyA',T('磅数一掉：球在线床上停得更久、出球角度变高','Lower tension: longer dwell, higher launch angle'),{color:'#ffffff',size:0.5,glow:'rgba(255,122,61,1)'}); hud(a,0,2.05); op(a,ss(0.2,0.9,v));
    const b=tx('flyB',T('示意 · Lindsey（Tennis Warehouse）测量','Illustrative · Lindsey, Tennis Warehouse'),{color:'#c8a898',size:0.32}); hud(b,0,1.55); op(b,ss(0.6,1.2,v));
    const o=tx('out',T('出界','OUT'),{color:'#ff8a7a',size:0.9,glow:RED}); o.position.set(-1,1.0,-L-1.6); op(o,ss(0.85,0.95,k));
    return; }
  // 换拍：一排刚穿好的拍子
  const v=u-SWP; rackG.visible=true; look(0,0.6,9,0,0.2,0); rimL.intensity=5; rimL.color.set(0xffb08a); rimL.position.set(-3,2,3);
  rackR.forEach((r,i)=>{ r.g.visible=true; r.g.position.set((i-2.5)*1.3,1.45,0); r.g.rotation.set(0,Math.sin(v*0.5+i)*0.2,0); r.g.scale.setScalar(0.3); setBed(r,{cm:STR.poly,cc:STR.poly,width:1.4,opm:ss(i*0.25,i*0.25+0.5,v),opc:ss(i*0.25,i*0.25+0.5,v)}); });
  const a=tx('swA',T('每换一次新球，就换一支刚穿好的拍子','A fresh racket at every ball change'),{color:'#ffffff',size:0.6,glow:'rgba(255,122,61,1)'}); hud(a,0,2.05); op(a,ss(0.2,0.9,v));
  const b=tx('swB',T('「大多数时候不是断线，是为了保持同样的磅数」· 2025 加拿大大师赛穿线主管','“Not broken strings — the same tension” · Canadian Open head stringer, 2025'),{color:'#ffe0d0',size:0.36}); b.position.set(0,-0.45,0); op(b,ss(0.8,1.5,v));
  const c=tx('swC',T('穿线房一天 130–200 支','130–200 rackets strung a day'),{color:'#ffd2bc',size:0.5,glow:'rgba(255,122,61,1)'}); c.position.set(0,-1.0,0); op(c,ss(1.6,2.3,v));
}
function shotTactics(u,D){
  const BR=ev('bars',1.5), BD=ev('band',8.0), CF=ev('conf',12.5), NO=ev('none',17.5);
  if(u<CF-0.2){ barsG.visible=true; barsG.position.set(0,-1.5,0); barsG.scale.setScalar(0.82); look(0,1.4,14.5,0,1.0,0); setBars(bars,ss(BR,BR+3.2,u));
    barsTitle.position.set(0,6.6,0); op(barsTitle,ss(BR,BR+0.7,u)); barsNote.position.set(0,-1.1,0.5); op(barsNote,ss(BR+1,BR+1.8,u));
    const bk=ss(BD,BD+0.8,u); bandMesh.position.set((bars.bars[1].x+bars.bars[2].x)/2,3.6,-0.6); bandMesh.scale.set((bars.bars[2].x-bars.bars[1].x)+2.4,7.6,1); bandMesh.material.opacity=0.07*bk;
    bandLab.position.set(bandMesh.position.x,8.0,0); op(bandLab,bk);
    const bs=tx('bandS',T('库尔滕 1997 · 约 2005 年后流行（Cross）· 2010 温网男子都用','Kuerten 1997 · popular after ~2005 (Cross) · all Wimbledon men by 2010'),{color:'#cfd8f0',size:0.3},barsG); bs.position.set(bandMesh.position.x,7.35,0); op(bs,bk);
    return; }
  // 同期变化：五股线缠成一个结，解不开
  confG.visible=true; look(0,0.5,11,0,0.3,0); const v=u-CF;
  confNodes.forEach(c=>{ const a0=c.i/5*Math.PI*2+v*0.2; const rad=lerp(3.7,3.5,ss(0,2,v)); const pos=new THREE.Vector3(Math.cos(a0)*rad*1.35,Math.sin(a0)*rad*0.48+0.6,0);
    c.n.position.copy(pos); c.n.material.opacity=ss(c.i*0.3,c.i*0.3+0.6,v); c.lab.position.copy(pos).add(new THREE.Vector3(0,-0.7,0.2)); op(c.lab,ss(c.i*0.3+0.2,c.i*0.3+0.8,v));
    const pts=[]; for(let j=0;j<=30;j++){ const s=j/30; const wob=Math.sin(s*Math.PI*3+c.i*1.3+v)*0.35*(1-s); pts.push(pos.clone().lerp(new THREE.Vector3(0,0.6,0),s).add(new THREE.Vector3(wob,wob*0.7,0))); }
    setLine(c.th,pts.map(p=>p.add(confG.position))); c.th.material.opacity=ss(c.i*0.3+0.3,c.i*0.3+1,v); });
  knot.position.set(0,0.6,0); knot.material.opacity=ss(1.5,2.5,v)*(0.7+0.3*Math.sin(u*4));
  const t=tx('confT',T('同一时期也在变','Changing at the same time'),{color:'#efe6ff',size:0.6,glow:VIO}); hud(t,0,2.05); op(t,ss(0.2,0.9,v)*(1-ss(NO-CF-0.4,NO-CF,v)));
  const n=tx('noneT',T('至今没有研究能把线的作用单独算出来','No study has yet isolated the strings\' effect'),{color:'#ffffff',size:0.62,glow:VIO}); hud(n,0,2.05); op(n,ss(NO-CF,NO-CF+0.7,v));
}
function shotEnd(u,D){
  const QQ=ev('q',7.0); rk.g.visible=true; R_spin(rk,u,0.5); look(0,0.3,lerp(8.5,10,ss(0,D,u)),0,0.2,0); rimL.intensity=5; rimR.intensity=5; rimL.position.set(-4,3,4); rimR.position.set(4,3,4); rimL.color.set(0xffc24a); rimR.color.set(0x4fe3ff);
  const gi=Math.floor(u/1.6)%4; const [,,cm,cc]=GEN[gi]; setBed(rk,{cm,cc,width:2.6});
  const a=tx('endA',T('手感 · 磅数 · 穿线规则：线改了这些','Feel · tension · stringing rules: what strings changed'),{color:'#ffffff',size:0.5,glow:GOLD}); hud(a,0,2.05); op(a,ss(0.3,1,u)*(1-ss(QQ-0.5,QQ,u)));
  const q=tx('endQ',T('你现在用的是什么线？','What strings do you play?'),{color:'#ffffff',size:0.95,font:'900 150px "Noto Sans CJK SC","Inter",sans-serif',glow:GOLD}); hud(q,0,2.0); op(q,ss(QQ,QQ+0.6,u));
}

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
  hideAll(); FX_SHAKE=0; FX_FLASH=0; rk.neck.visible=true; EV=sc.ev||{};
  ({hook:shotHook,gut:shotGut,synth:shotSynth,spaghetti:shotSpag,poly:shotPoly,power:shotPower,tension:shotTension,tactics:shotTactics,end:shotEnd})[sc.kind](u,D);
  if(Q.get('cam')){ const c=Q.get('cam').split(',').map(Number); look(...c); }   // 封面机位覆盖
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
  const s=setState(t); composer.render(); return JSON.stringify(Object.assign({_shot:s},anchors)); };
window.CUTS=()=>CUTS;
Promise.all([FONT_READY,document.fonts.ready]).then(()=>{ CUTS=findCuts(); window.READY=true; }).catch(e=>console.error('READY failed',e));
