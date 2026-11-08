// vibetennis EP11 抽筋，多半不是缺盐——腌黄瓜汁 85 秒止住抽筋、快到来不及被吸收：运动性抽筋更像神经的「油门踩死、刹车失灵」（神经肌肉控制失衡假说），对照脱水／电解质假说。
// 理论与上屏数字的出处见 papers/vibetennis-cramp-2026/sources.md（两源规则）；镜头与转场见同目录 storyboard.md。
// 通用底座（夜空、光点、全息字、3D 字、球场、看台、全息人体、后期）沿用 EP06–EP10；透明小腿、神经冲动、消化道为本集新做（anatomy.js）。解剖为示意，画面标「示意」。

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


// ==================== EP11 抽筋：本集物件 ====================
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

// ==================== EP11 抽筋：解剖资产 ====================
// 小腿特写 LEG（1 单位 ≈ 10 cm，示意，不是解剖比例尺）：膝在 y≈3.2，踝在 y≈-3，小腿肚朝 -z。
// 三条神经都通到左上方的「脊髓」段：Ia（肌梭→脊髓，油门）、Ib（高尔基腱器→脊髓，刹车）、α 运动神经（脊髓→肌纤维）。
// 神经冲动是沿通路跑的粒子：rate 决定有多少颗在跑、speed 决定跑多快；都只由 t 决定（确定性，分块渲染可续）。
const LEG=(()=>{
  const G=new THREE.Group(); scene.add(G); G.visible=false;
  const mk=(col)=>holoMat(col);
  const M={muscle:mk(0x4fe3ff), bone:mk(0xbcc8d8), tendon:mk(0xe8f4ff), foot:mk(0x9fb8d0), spine:mk(0xa78bfa)};
  const mesh=(geo,mat,x,y,z,sx=1,sy=1,sz=1)=>{ const m=new THREE.Mesh(geo,mat); m.position.set(x,y,z); m.scale.set(sx,sy,sz); G.add(m); return m; };
  const SPH=new THREE.SphereGeometry(1,40,28);
  // 骨：胫骨、腓骨（淡）
  mesh(new THREE.CylinderGeometry(0.17,0.2,6.4,16),M.bone,0,0.1,0.35); mesh(new THREE.CylinderGeometry(0.08,0.09,6.0,12),M.bone,0.42,0.0,0.05);
  mesh(SPH,M.bone,0,3.35,0.25,0.62,0.35,0.6);   // 膝（胫骨平台）
  // 肌肉：腓肠肌内外两个头、比目鱼肌
  const gL=mesh(SPH,M.muscle,-0.33,1.45,-0.55,0.55,1.75,0.55), gR=mesh(SPH,M.muscle,0.33,1.5,-0.5,0.52,1.7,0.52);
  const sol=mesh(SPH,M.muscle,0,-0.1,-0.35,0.72,1.55,0.42);
  // 跟腱、跟骨、脚
  const ach=mesh(new THREE.CylinderGeometry(0.27,0.16,1.9,16),M.tendon,0,-2.05,-0.55);
  mesh(SPH,M.bone,0,-3.25,-0.35,0.42,0.38,0.5);
  const foot=new THREE.Group(); foot.position.set(0,-3.15,0.1); G.add(foot);
  const fm=new THREE.Mesh(new THREE.CapsuleGeometry(0.42,2.0,8,16),M.foot); fm.rotation.x=Math.PI/2; fm.position.set(0,-0.15,1.0); fm.scale.set(1,1,0.55); foot.add(fm);
  // 肌纤维：70 根曲线，收缩时变短、鼓起
  const NF=70, NS=14, FIB=[]; let sd=4242; const rr=()=>{ sd=(sd*48271)%2147483647; return sd/2147483647; };
  for(let i=0;i<NF;i++){ const side=i%2?1:-1; FIB.push({x:side*(0.12+rr()*0.38), z:-0.5-rr()*0.32, top:2.9+rr()*0.35, ph:rr()*6.283}); }
  const fg=new THREE.BufferGeometry(); fg.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(NF*(NS-1)*2*3),3));
  const fibMat=new THREE.LineBasicMaterial({color:0x7fefff,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false});
  const fibers=new THREE.LineSegments(fg,fibMat); fibers.frustumCulled=false; G.add(fibers);
  // 肌梭（螺旋，油门）、高尔基腱器（腱上的网，刹车）
  const helix=[]; for(let i=0;i<=120;i++){ const a=i/120*Math.PI*14; helix.push(new THREE.Vector3(0.09*Math.cos(a),0.9+i/120*1.0,0.09*Math.sin(a))); }
  const spG=new THREE.BufferGeometry().setFromPoints(helix); const spMat=new THREE.LineBasicMaterial({color:0xffc24a,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false});
  const spindle=new THREE.Line(spG,spMat); spindle.position.set(-0.3,0,-0.62); G.add(spindle);
  const gtoMat=new THREE.MeshBasicMaterial({color:0x5aa8ff,wireframe:true,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false});
  const gto=new THREE.Mesh(new THREE.TorusKnotGeometry(0.2,0.05,80,8,2,5),gtoMat); gto.position.set(0,-1.2,-0.58); G.add(gto);
  // 脊髓段：左上方一截发光的柱子＋椎骨环
  const cordX=-3.0, cordZ=-1.6; mesh(new THREE.CylinderGeometry(0.22,0.22,3.0,20),M.spine,cordX,5.0,cordZ);
  for(let i=0;i<4;i++) mesh(new THREE.TorusGeometry(0.42,0.06,10,40),M.spine,cordX,3.9+i*0.75,cordZ).rotation.x=Math.PI/2;
  // 神经通路
  const C=(pts)=>new THREE.CatmullRomCurve3(pts.map(p=>new THREE.Vector3(...p)));
  const PATH={
    Ia:C([[-0.3,1.4,-0.62],[-0.7,2.3,-1.2],[-1.5,3.4,-1.5],[-2.4,4.6,-1.6],[cordX+0.15,5.1,cordZ]]),
    Ib:C([[0,-1.2,-0.58],[-0.6,0.0,-1.3],[-1.2,1.8,-1.7],[-2.1,3.9,-1.8],[cordX+0.15,5.6,cordZ]]),
    a :C([[cordX+0.15,4.6,cordZ],[-2.2,3.9,-1.3],[-1.2,3.0,-1.0],[-0.4,2.1,-0.85],[0.1,1.3,-0.8]])};
  const NL={}; for(const k in PATH){ const l=fatLine(k==='Ib'?0x5aa8ff:k==='Ia'?0xffc24a:0xff6a55,3); setLine(l,PATH[k].getPoints(60)); l.material.opacity=0; NL[k]=l; }
  // 冲动粒子
  const NP=600, imp=cloud(NP,0.32,16,scene,0); const ISEED=[...Array(NP)].map(()=>[rr(),rr(),rr()]);
  const st={op:0,c:0,ia:0,ib:0,mot:0,ankle:0};
  function update(t){
    G.visible=st.op>0.003; const o=st.op;
    const col=new THREE.Color(0x4fe3ff).lerp(new THREE.Color(0xff4a3a),st.c);
    for(const m of [gL,gR,sol]){ m.material.uniforms.uC.value.copy(col); }
    for(const k in M) M[k].uniforms.uOp.value=o*(k==='bone'?0.45:k==='muscle'?0.9:0.8);
    // 收缩：肌腹变短变鼓、抖动
    const sh=st.c*0.05*Math.sin(t*41)+st.c*0.03*Math.sin(t*67);
    gL.scale.set(0.55*(1+0.22*st.c)+sh,1.75*(1-0.12*st.c),0.55*(1+0.25*st.c)); gR.scale.set(0.52*(1+0.22*st.c)-sh,1.7*(1-0.12*st.c),0.52*(1+0.25*st.c));
    sol.scale.set(0.72*(1+0.1*st.c),1.55*(1-0.06*st.c),0.42*(1+0.15*st.c));
    foot.rotation.x=-st.ankle;                     // 正＝勾脚（拉伸），负＝绷脚（抽筋时脚尖被拉下）
    ach.scale.y=1+0.12*Math.max(0,st.ankle);
    const P=fg.attributes.position.array; let q=0;
    for(const f of FIB){ const top=f.top-0.35*st.c, bot=-1.25, bulge=0.12+0.22*st.c;
      let px,py,pz; for(let s=0;s<NS;s++){ const k=s/(NS-1); const y=lerp(top,bot,k); const b=Math.sin(Math.PI*k)*bulge; const x=f.x*(1-0.7*k*k), z=f.z-b+0.02*st.c*Math.sin(t*50+f.ph);
        if(s>0){ P[q++]=px;P[q++]=py;P[q++]=pz;P[q++]=x;P[q++]=y;P[q++]=z; } px=x;py=y;pz=z; } }
    fg.attributes.position.needsUpdate=true; fibMat.opacity=o*0.55; fibMat.color.copy(col).lerp(new THREE.Color(0xffffff),0.35);
    spMat.opacity=o*(0.35+0.65*st.ia); gtoMat.opacity=o*(0.25+0.75*st.ib); gto.rotation.y=t*0.6;
    NL.Ia.material.opacity=o*(0.25+0.6*st.ia); NL.Ib.material.opacity=o*(0.25+0.6*st.ib); NL.a.material.opacity=o*(0.25+0.6*st.mot);
    // 冲动：前 1/3 跑 Ia、中 1/3 跑 Ib、后 1/3 跑 α；rate 控制亮起的颗数
    const cs={Ia:[1,0.76,0.29],Ib:[0.35,0.66,1],a:[1,0.35,0.28]};
    for(let i=0;i<NP;i++){ const [s0,s1,s2]=ISEED[i]; const k=i<200?'Ia':i<400?'Ib':'a'; const rate=k==='Ia'?st.ia:k==='Ib'?st.ib:st.mot;
      const on=s1<rate; const sp=0.35+1.4*rate; const u=(s0+t*sp*0.5)%1; const p=PATH[k].getPointAt(u);
      const c=cs[k]; cset(imp,i,p.x,p.y,p.z,c[0],c[1],c[2],on?o*(0.6+0.4*s2):0); }
    cdone(imp); }
  return {G,st,update,PATH,imp,gL,gR,sol,gto,spindle,foot,cord:new THREE.Vector3(cordX,5.0,cordZ),hide(){ st.op=0; G.visible=false; for(const k in NL) NL[k].material.opacity=0; chide(imp); fibMat.opacity=0; spMat.opacity=0; gtoMat.opacity=0; }};
})();

// 消化道（挂在全息人身上，单位 m）：嘴→食道→胃→小肠；用来跟「嘴里的神经信号」比速度
const GUT=(()=>{
  const G=new THREE.Group(); scene.add(G); G.visible=false; const mat=holoMat(0x34f5a8);
  const C=(pts)=>new THREE.CatmullRomCurve3(pts.map(p=>new THREE.Vector3(...p)));
  const eso=C([[0,1.62,0.08],[0,1.5,0.02],[0,1.38,0.0],[0.02,1.28,0.02]]);
  const stomach=new THREE.Mesh(new THREE.SphereGeometry(1,28,20),mat); stomach.scale.set(0.11,0.07,0.06); stomach.position.set(0.05,1.22,0.04); G.add(stomach);
  const coil=[]; for(let i=0;i<=60;i++){ const a=i/60*Math.PI*6; coil.push([0.05+0.08*Math.cos(a)*(1-i/120),1.12-i/60*0.18,0.05+0.05*Math.sin(a)]); }
  const gut=C(coil);
  const tube=new THREE.Mesh(new THREE.TubeGeometry(gut,120,0.012,8,false),mat); G.add(tube);
  const et=new THREE.Mesh(new THREE.TubeGeometry(eso,30,0.01,8,false),mat); G.add(et);
  return {G,mat,eso,gut,stomach,set(o){ mat.uniforms.uOp.value=o; G.visible=o>0.003; }};
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
  LEG.hide(); GUT.set(0); propsHide(); if(typeof CROWD!=='undefined') chide(CROWD); HUM.forEach(H=>{ H.root.scale.setScalar(1); if(H.racket) H.racket.g.visible=true; }); ST_RATE=0.0003; courtG.userData.mat.color.set(0xffffff); }
// 全息榜单行
function row(k,i,str,val,max,col,o,hl=0){ const y=1.4-i*0.75; const w=4.6*clamp(val/max); const l=ln(col,hl?14:10); setLine(l,[V(-1.2,y,0),V(-1.2+w,y,0)]); l.material.opacity=o*(0.75+0.25*hl);
  const t=tx(k,str,{color:hl?'#ffffff':'#c8d8ea',size:0.42,glow:hl?CYAN:'rgba(120,160,200,0.6)'}); t.position.set(-3.4,y,0.1); op(t,o); }

// ---------- 1 钩子：开场即砸出冲突——「7」从天而降炸开 → 炸成「接发之王」→ 甩进 2011 美网赛点接发 → 王在哪？ ----------
// 所有者 2026-11-07：「前几秒一定要抓住人……直接抛出来，然后用炸裂或者是非常爆裂的动作，或者特效把这个东西做到极致」
function burst(c,k,col,spread=6,o=1){ const cc=new THREE.Color(col); for(let i=0;i<1600;i++){ const p=PTS[i]; const dir=V(p[0],p[1]*1.2,p[2]).normalize(); const sp=spread*(0.4+0.6*p[3]); const e=1-Math.pow(1-clamp(k),2.2);
  cset(pt,i,c.x+dir.x*sp*e,c.y+dir.y*sp*e-1.5*e*e,c.z+dir.z*sp*e,cc.r,cc.g,cc.b,o*(1-ss(0.55,1,k))*(0.5+0.5*p[4])); } cdone(pt); }
function shockRing(c,k,col,maxR,o=1,vertical=false){ const r=rg(); r.position.copy(c); vertical?r.rotation.set(0,0,0):r.rotation.set(-Math.PI/2,0,0); const e=1-Math.pow(1-clamp(k),3); r.scale.setScalar(0.2+maxR*e); r.material.color.set(col).multiplyScalar(GLOW.k); r.material.opacity=o*(1-ss(0.35,1,k)); }

// ==================== EP11 本集道具 ====================
const NEU=0x34f5a8, SALT=0xf4f7ff, PJ=0x9dff5a, YEL=0xffd84a, BLU=0x5aa8ff;
const PROPS=(()=>{
  const g=new THREE.Group(); scene.add(g);
  const arc=[]; for(let i=0;i<=24;i++){ const a=-0.9+i/24*1.8; arc.push(V(Math.sin(a)*0.9,Math.cos(a)*0.9-0.9,0)); }
  const banana=new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(arc),48,0.16,14,false),holoMat(YEL)); g.add(banana);
  const bottle=new THREE.Group(); const bm=holoMat(BLU); bottle.add(new THREE.Mesh(new THREE.CylinderGeometry(0.28,0.28,1.3,24),bm)); const cap=new THREE.Mesh(new THREE.CylinderGeometry(0.13,0.13,0.25,16),bm); cap.position.y=0.78; bottle.add(cap); g.add(bottle);
  const drop=new THREE.Mesh(new THREE.SphereGeometry(0.22,32,24),new THREE.MeshBasicMaterial({color:new THREE.Color(PJ).multiplyScalar(0.8),transparent:true})); drop.scale.set(1,1.35,1); g.add(drop);
  const vessel=new THREE.Mesh(new THREE.CylinderGeometry(0.55,0.55,9,32,1,true),holoMat(0xff6a7a)); vessel.rotation.z=Math.PI/2; g.add(vessel);
  const all=[banana,bottle,drop,vessel]; all.forEach(o=>o.visible=false);
  return {g,banana,bottle,drop,vessel,all,bm};
})();
function noRk(H){ if(H.racket) H.racket.g.visible=false; }
function propsHide(){ PROPS.all.forEach(o=>{ o.visible=false; o.position.set(0,0,0); o.rotation.set(o===PROPS.vessel?0:0,0,o===PROPS.vessel?Math.PI/2:0); o.scale.setScalar(1); }); PROPS.drop.scale.set(1,1.35,1); }
function hop(o,v){ o.visible=v>0.003; const set=(m)=>{ if(m.uniforms&&m.uniforms.uOp) m.uniforms.uOp.value=v; else { m.opacity=v; m.transparent=true; } }; o.traverse(c=>{ if(c.material) set(c.material); }); }
const calfOf=(H)=>wpos(H.legR.kn).lerp(wpos(H.legR.an),0.4);
const headOf=(H)=>wpos(H.eye);
// 粒子：沿一条折线的闪电（嘴 → 脊髓 → 腿），k 是闪电头走到哪
function bolt(pts,k,col,o=1,jit=0.06,seed=1){ const cc=new THREE.Color(col); const n=pts.length-1; for(let i=0;i<700;i++){ const f=i/700; if(f>k){ cset(pt,i,0,0,0,0,0,0,0); continue; }
    const s=f*n, a=Math.floor(Math.min(s,n-1e-6)), w=s-a; const p=pts[a].clone().lerp(pts[a+1],w); const h=Math.sin((i+seed*31)*12.9898)*43758.5453; const r=(h-Math.floor(h))-0.5;
    cset(pt,i,p.x+r*jit,p.y+r*jit*0.7,p.z-r*jit,cc.r,cc.g,cc.b,o*(0.35+0.65*ss(k-0.25,k,f))); } cdone(pt); }
// 镜头空间里的一条横向进度条（look() 之后调）
function bar(col,x0,x1,y,o,w=10,d=9){ const l=ln(col,w); setLine(l,[hp(x0,y,d),hp(Math.abs(x1-x0)<0.001?x0+0.001:x1,y,d)]); l.material.opacity=o; return l; }   // x1 可以在 x0 左边（往左长）
function lab(k,str,x,y,o,opt={}){ const t=tx(k,str,Object.assign({color:'#e8f4ff',size:0.34,glow:CYAN},opt)); if(x!==null) hud(t,x,y,opt.d||9); op(t,o); return t; }   // x=null：挂在世界坐标上（调用方自己设 position）

// ---------- 1 钩子：上海夜场，辛纳抽筋倒地 → 水、盐、香蕉飞来 → 一滴腌黄瓜汁击碎它们 → 85 秒 vs 还在胃里 → 管住了什么？ ----------
// 所有者 2026-11-07：「前几秒一定要抓住人……直接抛出来，然后用炸裂或者是非常爆裂的动作」。（不用闪白、抖屏：11-05 转场标准）
function shotHook(u,D){
  const FALL=ev('fall',2.3), CR=ev('crowd',4.5), SL=ev('salt',7.2), DR=ev('drop',11.7), CK=ev('clock',14.2), ST=ev('stomach',16.7), QQ=ev('q',19.9);
  courtG.visible=true; const H=RET; humanOp(H,1); place(H,0.4,L2-0.6,Math.PI);
  applyPose(H,poseAt([[0,'ready'],[0.9,'lungeF'],[FALL-0.2,'lungeF'],[FALL+0.5,'cramp']],u));
  ST_RATE=lerp(0.0004,0.006,ss(FALL-0.2,FALL+0.4,u)*(1-ss(CR+1,CR+3,u)));
  const C=calfOf(H);
  if(u>FALL-0.1){ const k=u-FALL; const g=gs(RD,1.6+0.4*Math.sin(u*9),0.55*ss(0,0.2,k)*(1-ss(DR,DR+0.6,u))); g.position.copy(C); shockRing(C.clone().setY(0.03),k/1.1,RD,3.5,0.9*(1-ss(DR,DR+0.5,u))); }
  H.mat.uniforms.uC.value.set(0x4fe3ff).lerp(new THREE.Color(0xff5a4a),0.55*ss(FALL,FALL+0.4,u)*(1-ss(CK,CK+1.5,u)));
  const cap=tx('hkSc',T('2025 上海大师赛第三轮 · 辛纳 6-7 7-5 2-3 抽筋退赛','2025 Shanghai Masters R3 · Sinner retires with cramps at 6-7 7-5 2-3'),{color:'#ffe2a0',size:0.32,glow:GOLD,plate:true});
  // 三样「常识」从三面飞来：水瓶、盐粒、香蕉
  const ink=ss(CR,CR+1.2,u)*(1-ss(DR+0.05,DR+0.25,u));
  const home=[V(-1.3,0.9,L2-0.3),V(1.9,1.0,L2-0.5),V(0.4,1.6,L2-1.3)];
  const from=[V(-9,4,L2+2),V(9,4,L2+2),V(0,9,L2-6)];
  const PB=PROPS.bottle, PBa=PROPS.banana;
  if(u<DR+0.3){ PB.visible=true; PB.position.copy(from[0].clone().lerp(home[0],ss(CR,CR+1.1,u))); PB.rotation.set(0.3,u*0.8,0.2); hop(PB,ink);
    PBa.visible=true; PBa.position.copy(from[2].clone().lerp(home[2],ss(CR+0.3,CR+1.4,u))); PBa.rotation.set(0.2,u*0.6,0.4); hop(PBa,ink); }
  const lbW=lab('hkW',T('缺水？','Water?'),null,0,0,{color:'#9fd0ff',glow:CYAN,size:0.42}); lbW.position.copy(home[0]).add(V(0,1.0,0)); op(lbW,ink);
  const lbS=lab('hkS',T('缺盐？','Salt?'),null,0,0,{color:'#ffffff',glow:'rgba(255,255,255,0.8)',size:0.42}); lbS.position.copy(home[1]).add(V(0,1.0,0)); op(lbS,ink*ss(SL-0.6,SL,u));
  const lbB=lab('hkB',T('香蕉？','Banana?'),null,0,0,{color:'#ffe27a',glow:GOLD,size:0.42}); lbB.position.copy(home[2]).add(V(0,0.9,0)); op(lbB,ink);
  if(u<DR+1.6){ const cc=new THREE.Color(SALT); const e=ss(SL-0.8,SL+0.3,u);   // 盐粒：一团闪着的白色晶粒聚到右边
    for(let i=0;i<500;i++){ const p=PTS[i]; const tgt=home[1].clone().add(V((p[3]-0.5)*1.2,(p[4]-0.5)*1.2,(p[0]/16)*1.2));
      let pos=V(9+p[0]*0.6,4+p[1],L2+2+p[2]).lerp(tgt,e); if(u>DR){ const k=(u-DR)/1.4; const dir=pos.clone().sub(home[1]).normalize(); pos.add(dir.multiplyScalar(5*(1-Math.pow(1-clamp(k),2)))); pos.y-=2*k*k; }
      cset(pt,i,pos.x,pos.y,pos.z,cc.r,cc.g,cc.b,e*(1-ss(DR+0.4,DR+1.4,u))*(0.4+0.6*p[4])); }
    cdone(pt); }
  // 一滴腌黄瓜汁从天而降，砸碎三样常识
  const D0=V(0.5,9,L2-0.3), D1=V(0.5,1.1,L2-0.5);
  if(u>DR-1.1 && u<CK+0.2){ const k=ss(DR-1.1,DR,u); PROPS.drop.visible=true; PROPS.drop.position.copy(D0.clone().lerp(D1,k*k)); PROPS.drop.material.opacity=1-ss(DR,DR+0.15,u); }
  if(u>DR){ const k=(u-DR); shockRing(D1.clone(),k/1.2,PJ,4,1); shockRing(D1.clone(),(k-0.15)/1.5,WH,6,0.6); if(k<1.6&&u>DR+0.2) burst(D1.clone(),k/1.6,PJ,5,0.9); const g=gs(PJ,3.5,0.6*Math.exp(-k*2.5)); g.position.copy(D1); }
  // 85 秒 ＋ 还在胃里
  const n85=t3d('n85','85',0x9dff5a,1.6); hud(n85,-2.6,0.45,9); t3op(n85,ss(CK,CK+0.3,u)*(1-ss(QQ-0.3,QQ,u)));
  const s85=lab('hk85',T('秒，就不抽了','seconds — cramp gone'),-2.6,-0.75,ss(CK+0.2,CK+0.6,u)*(1-ss(QQ-0.3,QQ,u)),{color:'#d8ffc8',glow:'rgba(157,255,90,0.8)',size:0.36});
  const sg=lab('hkSt',T('那时它大部分还在胃里','still mostly in the stomach'),2.6,-0.75,ss(ST,ST+0.4,u)*(1-ss(QQ-0.3,QQ,u)),{color:'#e8f4ff',size:0.36});
  if(u>CK-0.5){ GUT.set(ss(CK-0.5,CK+0.3,u)*(1-ss(QQ+0.3,QQ+1.2,u))); }
  const q=bt('hkQ',T('那它到底管住了什么？','So what did it actually stop?'),{size:0.9,glow:CYAN,fx:'particles'}); hud(q,0,0.2,9); q.update(u,QQ,D-0.2);
  // 机位：先全景压近倒地的人 → 抬头看三样东西 → 落滴后推近 → 问句时朝小腿钻进去
  if(u<CK-0.4){ const k=ss(0,FALL+0.8,u), k2=ss(CR,DR,u);
    look(lerp(4.0,2.2,k)+k2*0.3,lerp(1.5,0.95,k)+k2*0.55,lerp(L2+4.8,L2+2.7,k)+k2*1.6,0.4,lerp(0.85,0.45,k)+k2*0.75,L2-0.7); hud(cap,0,3.1,9); op(cap,ss(0.3,0.9,u)*(1-ss(CR+1,CR+1.6,u))); rims(CY,RD,5); }
  else { // 人体侧视：嘴、胃、腿都在画面里
    place(H,0,0,0); applyPose(H,POSE.stand); H.root.position.set(0,0,0); courtG.visible=false; noRk(H);
    GUT.G.position.set(0,0,0); const k=ss(QQ,D,u); look(lerp(2.6,0.9,k),lerp(1.2,0.5,k),lerp(0.9,0.4,k),0,lerp(1.15,0.45,k),0); rims(NEU,CY,4); hud(cap,0,3.1,9); op(cap,0); }
}

// ---------- 2 两派：左边血管里的离子变稀（脱水／电解质），右边神经在放电（神经肌肉控制） ----------
function shotCamps(u,D){
  const WA=ev('wat',4.7), NV=ev('nerve',10.2);
  look(Math.sin(u*0.1)*0.4,0.2,9.5,0,0.1,0); rims(CY,NEU,4);
  const V0=PROPS.vessel; V0.visible=true; V0.scale.set(1,0.48,1); V0.position.copy(hp(-3.0,-0.2,10)); hop(V0,0.55*ss(0.2,1.0,u)*(1-0.5*ss(NV,NV+0.8,u)));
  // 离子：钠（黄）、钾（紫），出汗后变稀
  const thin=ss(WA,WA+2.5,u); for(let i=0;i<500;i++){ const p=PTS[i]; const x=((p[3]+u*0.05*(1+p[4]))%1-0.5)*4.2; const c=new THREE.Color(i%3?0xffd84a:0xa78bfa);
    const pos=hp(-3.0+x,-0.2+(p[4]-0.5)*0.9,10+(p[2]/8)); cset(pt,i,pos.x,pos.y,pos.z,c.r,c.g,c.b,ss(0.2,1.0,u)*(p[0]/16+0.5>thin*0.85?1:0.12)*(1-0.5*ss(NV,NV+0.8,u))); }
  // 神经：右边一条折线，冲动越来越密
  const N=[]; for(let i=0;i<=10;i++) N.push(hp(1.0+i*0.42,-0.2+0.35*Math.sin(i*1.7),10));
  const l=ln(NEU,4); setLine(l,N); l.material.opacity=0.35+0.4*ss(NV,NV+0.6,u);
  const cc=new THREE.Color(NEU); for(let i=500;i<900;i++){ const p=PTS[i]; const f=(p[3]+u*(0.25+0.8*ss(NV,NV+1,u)))%1; const s=f*10, a=Math.floor(s); const q=N[a].clone().lerp(N[Math.min(10,a+1)],s-a);
    cset(pt,i,q.x,q.y,q.z,cc.r,cc.g,cc.b,ss(0.6,1.4,u)*(p[4]<0.35+0.6*ss(NV,NV+1,u)?1:0)); } cdone(pt);
  lab('cpA',T('脱水／电解质说','Dehydration / electrolytes'),-3.0,1.2,ss(0.4,1,u)*(1-0.5*ss(NV,NV+0.8,u)),{color:'#ffe2a0',glow:GOLD});
  lab('cpB',T('神经肌肉控制说','Neuromuscular control'),2.9,1.2,ss(0.8,1.4,u),{color:'#c8ffe8',glow:'rgba(52,245,168,0.8)'});
  lab('cpVs','VS',0,0.2,ss(0.8,1.4,u),{size:0.5,color:'#ffffff'});
}

// ---------- 3 腌黄瓜实验：电刺激脚底抽筋 → 水 134 秒 vs 腌黄瓜汁 85 秒 → 胃里还没动、血液里的盐没变 → 口咽神经反射（推测） ----------
function shotPickle(u,D){
  const ZP=ev('zap',4.2), CR=ev('cramp',5.2), WT=ev('water',10.7), PJt=ev('pj',13.4), GT=ev('gut',16.9), FL=ev('flat',21.2), RF=ev('reflex',28.2);
  if(u<WT-0.5){ // 小腿＋脚特写：电极、电流、脚底抽紧
    LEG.st.op=1; LEG.st.c=0.15*ss(CR,CR+0.4,u); LEG.st.mot=0.15+0.6*ss(ZP,ZP+0.3,u); LEG.st.ia=0.1; LEG.st.ib=0.1; LEG.st.ankle=-0.25*ss(CR,CR+0.4,u); LEG.update(u);
    look(4.2,-1.4,4.8,0,-2.4,0.4); rims(CY,RD,4);
    const sole=V(0,-3.55,0.9); if(u>ZP){ const k=u-ZP; const zz=[V(-0.2,-1.2,1.6),V(0.1,-1.9,1.4),V(-0.1,-2.6,1.3),sole]; bolt(zz,ss(0,0.25,k),0x9fd8ff,1-ss(WT-1.2,WT-0.6,u),0.12,3); }
    if(u>CR){ const g=gs(RD,1.4,0.55*(1-ss(WT-1.2,WT-0.6,u))); g.position.copy(sole); }
    lab('pkN',T('10 人 · 先脱水约 3% · 电刺激诱发脚底肌肉抽筋','10 men · ~3% dehydrated · cramp induced electrically in a foot muscle'),0,2.6,ss(0.6,1.2,u)*(1-ss(WT-1.2,WT-0.6,u)),{size:0.3,plate:true});
    return; }
  if(u<GT-0.4){ // 计时赛跑：两条条子一起长，绿色在 85 秒停下
    look(0,0.2,9,0,0.2,0); rims(PJ,BLU,4); const t=clamp((u-WT)/(GT-0.8-WT))*150;   // 画面上 150 秒压到这几秒里
    const X0=-3.6, SC=7.2/150; const tw=Math.min(t,133.7), tp=Math.min(t,84.6);
    bar(BLU,X0,X0+SC*tw,0.75,1,16); bar(PJ,X0,X0+SC*tp,-0.55,ss(PJt-0.6,PJt,u),16);
    lab('pkW',T('水','Water'),X0-0.6,0.75,1,{color:'#9fd0ff',size:0.4}); lab('pkP',T('腌黄瓜汁','Pickle juice'),X0-0.95,-0.55,ss(PJt-0.6,PJt,u),{color:'#d8ffc8',size:0.4,glow:'rgba(157,255,90,0.8)'});
    const nw=t3d('n134','134',0x5aa8ff,0.55); hud(nw,X0+SC*133.7+0.8,0.75,9); t3op(nw,ss(132,134,t));
    const np=t3d('n85b','85',0x9dff5a,0.55); hud(np,X0+SC*84.6+0.6,-0.55,9); t3op(np,ss(83,85,t)*ss(PJt-0.6,PJt,u));
    if(t>84.6){ const k=(t-84.6)/20; const c=hp(X0+SC*84.6,-0.55,9); shockRing(c,k,PJ,1.6,0.8,true); }
    lab('pkU',T('秒（平均）','seconds (mean)'),2.6,-1.6,ss(WT,WT+0.6,u),{size:0.3,color:'#aab8c8'});
    return; }
  // 人体透视：胃里的汁几乎不动、血液里的盐没变；然后一道神经闪电从嘴打到腿
  const H=RET; humanOp(H,0.55); noRk(H); place(H,0,0,0); applyPose(H,POSE.stand); GUT.set(0.9); GUT.G.position.set(0,0,0);
  const k=ss(GT-0.4,D,u); look(lerp(2.2,1.6,k),lerp(1.2,1.0,k),lerp(1.3,1.0,k),0,lerp(1.15,0.95,k),0); rims(NEU,CY,4);
  // 胃里的绿色液体粒子（基本不出胃）
  const st=GUT.stomach.position; const gc=new THREE.Color(PJ);
  for(let i=700;i<1000;i++){ const p=PTS[i]; const a=p[3]*6.283+u*0.4, r=0.07*Math.sqrt(p[4]); const leak=i<715?ss(GT,GT+3,u):0; const g=GUT.gut.getPointAt(clamp(leak*0.3*(p[0]/16+0.5)));
    const q=leak>0?g:V(st.x+Math.cos(a)*r,st.y-0.02+Math.sin(a)*r*0.5,st.z+(p[2]/8)*0.04); cset(pt,i,q.x,q.y,q.z,gc.r,gc.g,gc.b,0.9); }
  cdone(pt);
  lab('pkG',T('喝下 5 分钟后，几乎不再离开胃','after 5 min, almost none leaves the stomach'),0.9,0.9,ss(GT,GT+0.6,u)*(1-ss(RF-0.6,RF,u)),{size:0.3,d:3});
  lab('pkF',T('血液里的盐：没变','salt in the blood: unchanged'),0.9,0.55,ss(FL,FL+0.5,u)*(1-ss(RF-0.6,RF,u)),{size:0.3,color:'#ffb0b8',glow:'rgba(255,106,122,0.8)',d:3});
  if(u>RF-0.4){ const mouth=headOf(H).add(V(0,-0.06,0.02)); const neck=wpos(H.neck), hip=wpos(H.pelvis), C=calfOf(H);
    bolt([mouth,neck,neck.clone().lerp(hip,0.5),hip,C],ss(RF-0.4,RF+1.0,u),NEU,1,0.03,7); if(u>RF+1.0){ const g=gs(NEU,0.6,0.7*Math.exp(-(u-RF-1.0)*2)); g.position.copy(C); shockRing(C,(u-RF-1.0)/0.8,NEU,0.6,0.8,true); }
    lab('pkR',T('研究者推测：嘴和喉咙里的神经反射','researchers suspect a reflex from the mouth and throat'),-0.8,0.9,ss(RF,RF+0.6,u),{size:0.3,color:'#c8ffe8',glow:'rgba(52,245,168,0.8)',d:3}); }
}

// ---------- 4 油门与刹车：钻进透明小腿 → 肌梭（油门）、高尔基腱器（刹车）→ 累了：油门越来越灵、刹车越来越弱 → 运动神经停不下来 → 锁死 ----------
function legCam(u,az0,az1,D,y=1.5,r=13){ const a=lerp(az0,az1,ss(0,D,u)); look(-1.0+Math.sin(a)*r,y+0.8,-1.0+Math.cos(a)*r,-1.0,y,-1.0); }   // 从 +x 侧后方看：屏幕左右≈世界 z（+z 在左）   // 侧后方看：腿、三条神经、脊髓都在画面里
function shotBrake(u,D){
  const SP=ev('spindle',6.0), GA=ev('gas',8.5), GO_=ev('gto',10.5), BK=ev('brk',14.2), TI=ev('tired',18.8), SM=ev('storm',25.2), LK=ev('lock',26.5);
  LEG.st.op=ss(0,0.6,u); const tire=ss(TI,SM,u);
  LEG.st.ia=lerp(0.25,1,tire)*(u>SP-0.3?1:0.3); LEG.st.ib=lerp(0.45,0.08,tire)*(u>GO_-0.3?1:0.3); LEG.st.mot=lerp(0.3,1,ss(TI+1,LK,u));
  LEG.st.c=ss(SM-0.5,LK+0.3,u); LEG.st.ankle=-0.35*LEG.st.c; LEG.update(u);
  if(u<1.6){ const k=ss(0,1.6,u), a=1.55; const r=lerp(2.5,13,k); look(-1.0+Math.sin(a)*r,lerp(0.8,2.3,k),-1.0+Math.cos(a)*r,-1.0,lerp(0.6,1.5,k),-1.0); } else legCam(u,1.55,2.05,D);   /* 从小腿肚里退出来，看到整个回路 */
  rims(GO,BLU,4);
  const sp=V(-0.3,1.4,-0.62), gt=V(0,-1.2,-0.58);
  if(u>SP-0.3){ const g=gs(GO,0.9,0.5*ss(SP-0.3,SP+0.3,u)); g.position.copy(sp); }
  if(u>GO_-0.3){ const g=gs(BLU,0.9,0.5*ss(GO_-0.3,GO_+0.3,u)); g.position.copy(gt); }
  const a=lab('bkS',T('肌梭：感受拉长 → 让肌肉收缩','muscle spindle: senses stretch → contracts the muscle'),null,0,ss(SP,SP+0.5,u)*(1-ss(TI-0.6,TI,u)),{size:0.3,color:'#ffe2a0',glow:GOLD}); a.position.copy(sp).add(V(0,0.9,2.9));
  const b=lab('bkG',T('高尔基腱器：感受张力 → 让肌肉放松','Golgi tendon organ: senses tension → relaxes the muscle'),null,0,ss(GO_,GO_+0.5,u)*(1-ss(TI-0.6,TI,u)),{size:0.3,color:'#cfe4ff',glow:'rgba(90,168,255,0.8)'}); b.position.copy(gt).add(V(0,-0.6,3.0));
  const g1=lab('bkGas',T('油门','ACCELERATOR'),null,0,ss(GA,GA+0.4,u),{size:0.42,color:'#ffd27a',glow:GOLD}); g1.position.copy(sp).add(V(0,0.1,1.2));
  const g2=lab('bkBrk',T('刹车','BRAKE'),null,0,ss(BK,BK+0.4,u),{size:0.42,color:'#9fd0ff',glow:CYAN}); g2.position.copy(gt).add(V(0,0.1,1.2));
  const cd=lab('bkC',T('脊髓','spinal cord'),null,0,ss(SP,SP+0.6,u),{size:0.26,color:'#d8c8ff',glow:VIO}); cd.position.copy(LEG.cord).add(V(0,1.9,-0.6));
  // 累了之后：右下角两根计量条
  const o=ss(TI,TI+0.6,u); bar(GO,2.4,2.4+2.6*lerp(0.35,1,tire),-1.9,o,14); bar(BLU,2.4,2.4+2.6*lerp(0.7,0.12,tire),-2.45,o,14);
  lab('bkTa',T('油门','accelerator'),1.8,-1.9,o,{size:0.32,color:'#ffd27a'}); lab('bkTb',T('刹车','brake'),1.8,-2.45,o,{size:0.32,color:'#9fd0ff'});
  lab('bkT',T('肌肉累了','fatigue'),3.7,-1.3,o*(1-ss(SM-0.4,SM,u)),{size:0.36});
  if(u>LK){ const k=u-LK; const c=V(0,1.4,-0.6); shockRing(c,k/1.0,RD,3,0.9,true); shockRing(c,(k-0.2)/1.3,RD,4.5,0.5,true); }
  const lk=bt('bkLk',T('锁死','LOCKED'),{size:0.9,glow:RED,fx:'particles'}); hud(lk,2.4,1.6,9); lk.update(u,LK,D-0.1);
}

// ---------- 5 拉伸：勾脚尖 → 跟腱被拉紧 → 刹车（蓝）压过油门（红）→ 肌肉松开 ----------
function shotStretch(u,D){
  const FX=ev('flex',4.5), RL=ev('relief',7.3);
  const f=ss(FX-0.3,FX+1.0,u), r=ss(FX+0.3,RL+1.2,u);
  LEG.st.op=1; LEG.st.ankle=lerp(-0.35,0.55,f); LEG.st.ib=lerp(0.08,1,f); LEG.st.ia=lerp(1,0.3,r); LEG.st.mot=lerp(1,0.06,r); LEG.st.c=lerp(1,0,r); LEG.update(u);
  legCam(u,2.05,2.45,D,0.8,12); rims(BLU,GO,4);
  if(u>FX){ const c=V(0,-1.2,-0.58); const g=gs(BLU,1.4,0.6*f); g.position.copy(c); shockRing(c,(u-FX)/1.2,BLU,2.2,0.8,true); }
  const a=lab('stA',T('勾脚尖 → 跟腱拉紧','toes pulled up → tendon stretched'),-2.6,-1.6,ss(FX,FX+0.5,u),{size:0.32,color:'#cfe4ff',glow:CYAN});
  const t=bt('stT',T('刹车又起作用了','The brake kicks back in'),{size:0.8,glow:CYAN,fx:'particles'}); hud(t,0,2.0,9); t.update(u,RL,D-0.1);
}

// ---------- 6 数据：铁人三项 209 个光点，约五分之一抽筋 → 两组电解质、体重变化一样高 → 拉开的是速度 → 脱水 4.7% 也没变容易 → 香蕉太慢 ----------
const CROWD=cloud(220,0.13,16,scene,0);
function shotData(u,D){
  const CW=ev('crowd',2.9), SM=ev('same',8.5), FS=ev('fast',16.7), DH=ev('dehyd',19.7), BN=ev('banana',25.2);
  look(Math.sin(u*0.07)*0.4,0.3,9.5,0,0.2,0); rims(CY,RD,4); chide(CROWD);
  const q=bt('dtQ',T('那水和盐呢？','What about water and salt?'),{size:0.9,glow:CYAN,fx:'particles'}); hud(q,0,0.4,9); q.update(u,0.3,CW-0.2);
  if(u<DH-0.4){ // 209 人：43 红（抽筋）166 青
    const sep=ss(SM-0.6,SM+0.6,u); const o=ss(CW,CW+0.8,u)*(1-ss(DH-0.8,DH-0.4,u)); let jr=0, jc=0;
    for(let i=0;i<209;i++){ const red=(i*37)%209<43; const col=new THREE.Color(red?0xff5a4a:0x4fe3ff).lerp(new THREE.Color(0x9fb8d0),red?1-ss(CW+1.2,CW+2.2,u):0);
      const gx=(i%19-9)*0.3, gy=(Math.floor(i/19)-5)*0.3; let x, y;
      if(red){ x=lerp(gx,-4.6+(jr%8)*0.3,sep); y=lerp(gy+0.3,2.3-Math.floor(jr/8)*0.3,sep); jr++; }
      else { x=lerp(gx,0.4+(jc%15)*0.3,sep); y=lerp(gy+0.3,2.3-Math.floor(jc/15)*0.3,sep); jc++; }
      const p=hp(x,y,9.5); cset(CROWD,i,p.x,p.y,p.z,col.r,col.g,col.b,o); }
    cdone(CROWD);
    lab('dtN',T('铁人三项 209 人 · 约五分之一抽筋','209 Ironman triathletes · about 1 in 5 cramped'),0,3.05,ss(CW,CW+0.6,u)*(1-ss(DH-0.8,DH-0.4,u)),{size:0.34});
    const ob=ss(SM,SM+0.6,u)*(1-ss(DH-0.8,DH-0.4,u)); const rows=[[T('血液电解质','serum electrolytes'),0.7,0.7],[T('体重变化','body-mass change'),0.55,0.55],[T('比赛速度','race speed'),0.9,0.62]];
    rows.forEach(([nm,a,b],j)=>{ const y=-0.85-j*0.62; const oj=j<2?ob:ob*ss(FS-0.3,FS+0.3,u); bar(RD,-1.2,-1.2-2.6*a,y,oj,14); bar(CY,1.2,1.2+2.6*b,y,oj,14); lab('dtR'+j,nm,0,y,oj,{size:0.3,color:'#e8f4ff'}); });
    lab('dtA',T('抽筋的','cramped'),-3.4,2.85,ob,{size:0.32,color:'#ffb0a8'}); lab('dtB',T('没抽筋的','did not'),2.5,2.85,ob,{size:0.32,color:'#9fe8ff'});
    lab('dtS',T('看不出区别','no difference'),0,-2.85,ob*(1-ss(FS-0.3,FS,u)),{size:0.38,color:'#ffffff'});
    lab('dtF',T('真正不一样：比赛更快、以前抽过','what differed: racing faster, past cramps'),0,-2.85,ob*ss(FS,FS+0.4,u),{size:0.36,color:'#ffd27a',glow:GOLD});
    return; }
  if(u<BN-0.4){ // 脱水 4.7%：诱发抽筋需要的刺激没变低
    const o=ss(DH-0.4,DH+0.3,u)*(1-ss(BN-0.8,BN-0.4,u));
    const n=t3d('n47','4.7%',0x5aa8ff,1.1); hud(n,-2.6,0.6,9); t3op(n,o);
    lab('dhA',T('脱水（约 3.9 升汗）','dehydrated (≈3.9 L of sweat)'),-2.6,-0.65,o,{size:0.34,color:'#9fd0ff'});
    const k=ss(DH+1.0,DH+2.0,u); bar(GO,0.9,0.9+3.0*(15/16),0.75,o,18); bar(GO,0.9,0.9+3.0*(13/16),-0.15,o*k,18);
    lab('dhP',T('脱水前 15 Hz','before: 15 Hz'),2.4,1.25,o,{size:0.3,color:'#ffd27a'}); lab('dhQ',T('脱水后 13 Hz','after: 13 Hz'),2.2,0.35,o*k,{size:0.3,color:'#ffd27a'});
    lab('dhB',T('诱发抽筋需要的电刺激频率：没有显著变化','stimulus frequency needed to trigger a cramp: no significant change'),1.0,-1.3,o*ss(DH+2.0,DH+2.6,u),{size:0.28});
    return; }
  // 香蕉：钾离子慢慢进血，30–60 分钟才一点点
  const o=ss(BN-0.4,BN+0.3,u); const B=PROPS.banana; B.visible=true; B.position.copy(hp(-2.8,0.6,8)); B.rotation.set(0.2,u*0.5,0.6); B.scale.setScalar(1.2); hop(B,o);
  const Vs=PROPS.vessel; Vs.visible=true; Vs.scale.set(0.5,0.6,0.5); Vs.position.copy(hp(1.4,-0.6,9)); hop(Vs,0.5*o);
  const tm=clamp((u-BN-0.5)/(D-BN-1.2)); const cc=new THREE.Color(0xa78bfa);
  for(let i=0;i<200;i++){ const p=PTS[i]; const f=clamp(tm*1.1-p[3]*0.9); const a=hp(-2.4,0.4,8), b=hp(0.6+p[4]*2.6,-0.6+(p[0]/16)*0.4,9); const q=a.clone().lerp(b,ss(0,1,f)); cset(CROWD,i,q.x,q.y,q.z,cc.r,cc.g,cc.b,o*(f>0?0.9:0.3)); }
  cdone(CROWD);
  bar(VIO,-1.0,-1.0+4.4*tm,-2.0,o,8); lab('bnT',T('0 → 60 分钟','0 → 60 min'),-1.8,-2.0,o,{size:0.3});
  lab('bnA',T('吃 2 根：血钾要 30–60 分钟才升一点点','2 bananas: blood potassium edges up only after 30–60 min'),0.6,1.9,o*ss(BN+0.5,BN+1.1,u),{size:0.32,color:'#e0d4ff',glow:VIO});
}

// ---------- 7 盐派：17 岁网球选手，每小时出汗 2.5 升，一小时丢的钠 ≈ 他一天饮食的一半甚至更多 → 加盐后不再抽筋 ----------
function shotSalt(u,D){
  const KD=ev('kid',4.9), SW=ev('sweat',5.8), LS=ev('loss',8.2), FX=ev('fixed',12.7), HM=ev('humid',16.3);
  const t=bt('slT',T('盐派也不是没道理','The salt camp has a point'),{size:0.85,glow:GOLD,fx:'particles'}); hud(t,0,0.3,9); t.update(u,0.3,KD-0.3);
  if(u<KD-0.4){ look(0,0.3,9,0,0.3,0); return; }
  courtG.visible=true; const H=G2; humanOp(H,1); place(H,0.6,L2-0.4,Math.PI); applyPose(H,poseAt([[0,'ready'],[1.2,'lungeF'],[2.4,'ready'],[3.6,'lungeB'],[4.8,'ready']],(u-KD)%4.8));
  ST_RATE=0.0004; const k=ss(KD,D,u); look(lerp(3.4,2.4,k),lerp(1.5,1.25,k),L2+lerp(3.4,2.5,k),0.6,1.0,L2-0.4); rims(GO,RD,5);
  courtG.userData.mat.color.set(0xffffff).lerp(new THREE.Color(0xffc9a0),0.35*ss(HM-0.5,HM+0.5,u));
  // 汗滴：持续往下掉的蓝色小点；衣服上析出的盐：白色闪点
  const top=wpos(H.neck); const sc=new THREE.Color(0x9fd8ff), wc=new THREE.Color(SALT);
  for(let i=0;i<600;i++){ const p=PTS[i]; const f=((p[3]+u*0.9*(0.6+p[4]))%1); const q=top.clone().add(V((p[0]/16)*0.5,-f*1.6,(p[2]/8)*0.3)); cset(pt,i,q.x,q.y,q.z,sc.r,sc.g,sc.b,ss(SW-0.3,SW+0.3,u)*(1-f)*0.8); }
  for(let i=600;i<900;i++){ const p=PTS[i]; const q=wpos(H.spine).add(V((p[0]/16)*0.34,0.05+p[4]*0.42,0.13*(p[2]>0?1:-1))); cset(pt,i,q.x,q.y,q.z,wc.r,wc.g,wc.b,ss(LS,LS+2,u)*(p[3]<ss(LS,LS+2.5,u)?0.9:0)); }
  cdone(pt);
  lab('slK',T('17 岁网球选手 · 每小时出汗 2.5 升','17-year-old tennis player · sweats 2.5 L per hour'),0,2.7,ss(KD,KD+0.6,u),{size:0.3,plate:true});
  const o=ss(LS,LS+0.6,u)*(1-ss(HM-0.4,HM,u));
  bar(SALT,1.2,1.2+2.8*0.52,-1.9,o,14); bar(SALT,1.2+2.8*0.52,1.2+2.8*1.03,-1.9,o*0.35,14); bar(0x9fb8d0,1.2,1.2+2.8,-2.6,o*0.7,14);
  lab('slA',T('打 1 小时，汗里丢的钠（约 90 mmol）','sodium lost in 1 hour of sweat (~90 mmol)'),2.6,-1.45,o,{size:0.28}); lab('slB',T('他一天饮食里的钠（87–174 mmol）','sodium in his whole day of food (87–174 mmol)'),2.6,-3.0,o,{size:0.28,color:'#aab8c8'});
  lab('slF',T('加盐以后，不再抽筋','after adding salt: no more cramps'),-2.4,-2.4,ss(FX,FX+0.5,u)*(1-ss(HM-0.4,HM,u)),{size:0.32,color:'#ffffff'});
  if(u>FX){ const C=calfOf(H); const g=gs(CY,0.8,0.5*ss(FX,FX+0.5,u)); g.position.copy(C); }
  lab('slH',T('又湿又热、汗多又咸 → 盐确实要紧','hot, humid, heavy salty sweat → salt really matters'),0,-2.4,ss(HM,HM+0.5,u),{size:0.32,color:'#ffd27a',glow:GOLD});
}

// ---------- 8 名场面：2023 法网半决赛阿尔卡拉斯全身抽筋、赛后说「最主要的是紧张」→ 回到辛纳的上海：两样都有？ ----------
function shotBack(u,D){
  const RG_=ev('rg',3.0), CR=ev('cramp',6.1), TN=ev('tension',9.9), SH=ev('sh',11.9), BO=ev('both',16.4);
  courtG.visible=true;
  if(u<SH-0.4){ courtG.userData.mat.color.set(0xffb48a);   // 红土色调（示意）
    const H=SRV; humanOp(H,1); place(H,0.2,L2-0.5,Math.PI); applyPose(H,poseAt([[0,'ready'],[1.0,'lungeB'],[2.2,'ready'],[CR,'ready'],[CR+0.8,'cramp']],u));
    const k=ss(0,SH,u); look(lerp(3.8,2.3,k),lerp(1.7,1.1,k),L2+lerp(4.0,2.5,k),0.2,0.75,L2-0.6); rims(GO,RD,5); ST_RATE=lerp(0.0004,0.005,ss(CR,CR+0.5,u));
    H.mat.uniforms.uC.value.set(0xffc24a).lerp(new THREE.Color(0xff5a4a),0.6*ss(CR,CR+0.6,u));
    lab('bkRG',T('2023 法网半决赛 · 阿尔卡拉斯 对 德约','2023 Roland Garros SF · Alcaraz vs Djokovic'),0,2.9,ss(RG_-0.6,RG_,u),{size:0.32,color:'#ffe2a0',glow:GOLD,plate:true});
    lab('bkCr',T('第三盘开始，全身抽筋','from the third set, cramps all over'),0,-2.5,ss(CR,CR+0.5,u)*(1-ss(TN-0.4,TN,u)),{size:0.32});
    if(u>TN-0.6){ const hd=headOf(H), hip=wpos(H.pelvis); const pts=[hd,wpos(H.neck),hip,calfOf(H)]; bolt(pts,ss(TN-0.6,TN+0.6,u),NEU,1,0.05,11);
      const qq=lab('bkQ','"The main thing, it was the tension."',0,2.2,ss(TN,TN+0.5,u),{size:0.36,color:'#ffffff'}); lab('bkQz',T('「最主要的，是紧张。」','— Alcaraz, after the match'),0,1.65,ss(TN+0.3,TN+0.8,u),{size:0.34,color:'#c8ffe8',glow:'rgba(52,245,168,0.8)'}); }
    return; }
  // 回到上海：辛纳倒地；盐（白）和神经（绿）两种信号同时出现
  const H=RET; humanOp(H,1); place(H,0.4,L2-0.6,Math.PI); applyPose(H,POSE.cramp); ST_RATE=0.0015;
  const k=ss(SH-0.4,D,u); look(lerp(3.0,2.0,k),lerp(1.4,1.0,k),L2+lerp(3.2,2.2,k),0.4,0.4,L2-0.8); rims(CY,GO,5);
  lab('bkSH',T('2025 上海 · 又湿又热','Shanghai 2025 · hot and humid'),0,2.9,ss(SH-0.2,SH+0.4,u),{size:0.32,plate:true});
  const ob=ss(BO-0.4,BO+0.3,u); const C=calfOf(H), hd=headOf(H);
  if(ob>0){ bolt([hd,wpos(H.neck),wpos(H.pelvis),C],ss(BO-0.4,BO+0.6,u),NEU,ob,0.04,13);
    const wc=new THREE.Color(SALT); for(let i=700;i<1000;i++){ const p=PTS[i]; const q=wpos(H.spine).add(V((p[0]/16)*0.6,p[4]*0.7,(p[2]/8)*0.4)); cset(pt,i,q.x,q.y,q.z,wc.r,wc.g,wc.b,ob*(0.3+0.6*p[3])); } cdone(pt); }
  const b=bt('bkBo',T('两样都有？','Both?'),{size:0.8,glow:GOLD,fx:'particles'}); hud(b,2.2,1.6,9); b.update(u,BO,D-0.1);
}

// ---------- 9 结论 ＋ 问句 ----------
function shotEnd(u,D){
  const P1=ev('p1',5.9), P2=ev('p2',10.0), QQ=ev('q',12.1);
  LEG.st.op=1-ss(QQ-0.6,QQ,u); const r=ss(P1,P1+2.0,u); LEG.st.c=lerp(1,0,r); LEG.st.ia=lerp(1,0.3,r); LEG.st.ib=lerp(0.1,0.8,r); LEG.st.mot=lerp(1,0.1,r); LEG.st.ankle=lerp(-0.35,0.5,r); LEG.update(u);
  legCam(u,1.7,2.1,D,1.5,13); rims(CY,GO,4);
  const t=bt('ndT',T('油门踩死 · 刹车失灵','Accelerator stuck · brake failing'),{size:0.85,glow:RED,fx:'particles'}); hud(t,0,2.2,9); t.update(u,0.5,QQ-0.4);
  lab('ndA',T('① 先拉伸','① stretch first'),-2.6,-1.9,ss(P1,P1+0.5,u)*(1-ss(QQ-0.4,QQ,u)),{size:0.36,color:'#9fd0ff',glow:CYAN});
  lab('ndB',T('② 汗多又咸的人，再补盐','② heavy, salty sweaters: add salt'),1.6,-1.9,ss(P2,P2+0.5,u)*(1-ss(QQ-0.4,QQ,u)),{size:0.36,color:'#ffd27a',glow:GOLD});
  const q=bt('ndQ',T('你抽筋的时候，是怎么缓过来的？','When you cramp, how do you get out of it?'),{size:0.85,glow:CYAN,fx:'particles'}); hud(q,0,0.2,9); q.update(u,QQ,D+5);
}

const SHOTS={hook:shotHook,camps:shotCamps,pickle:shotPickle,brake:shotBrake,stretch:shotStretch,data:shotData,salt:shotSalt,back:shotBack,end:shotEnd};
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
