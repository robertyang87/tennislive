// 四大满贯中心球场：预览场景（场地材质与配色）
// 球场尺寸按 ITF 标准；场馆为示意（按真实平面形状风格化，不按座位数精确建模）
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { TL } from './shots.js';

const Q=new URLSearchParams(location.search);
const W=+(Q.get('w')||1920), H=+(Q.get('h')||1080);
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(1); renderer.setSize(W,H);
renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.05;
renderer.outputColorSpace=THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);
const scene=new THREE.Scene(); scene.background=new THREE.Color(0x02040a);
const camera=new THREE.PerspectiveCamera(36,W/H,0.3,12000);
renderer.localClippingEnabled=true; const CLIP=new THREE.Plane(new THREE.Vector3(0,-1,0),1e5); // 场馆「从地面扫描建起来」
// 背景与第 4 集一致（所有者：背景颜色用前几期那个）：深蓝夜空＋地平线辉光、星点、漂浮微尘
const skyMat=new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,fog:false,uniforms:{uWarm:{value:0}},
  vertexShader:`varying vec3 vD; void main(){ vD=normalize(position); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,
  fragmentShader:`varying vec3 vD; uniform float uWarm; void main(){ float h=vD.y; float g=exp(-abs(h+0.02)*7.0); vec3 top=vec3(0.006,0.01,0.026); vec3 hz=mix(vec3(0.035,0.06,0.15),vec3(0.07,0.04,0.012),uWarm); vec3 vi=vec3(0.04,0.022,0.07); float side=0.5+0.5*vD.x; gl_FragColor=vec4(top+hz*g+vi*g*g*side*0.6*(1.-uWarm),1.);} `});
const sky=new THREE.Mesh(new THREE.SphereGeometry(9000,48,24),skyMat); sky.frustumCulled=false; scene.add(sky);


// ---------- 粒子与光效工具（照第 4 集：点云着色器、光晕精灵、环形冲击波） ----------
let fseed=4242; const frnd=()=>{fseed=(fseed*48271)%2147483647;return fseed/2147483647;}; // 特效专用随机数，不动场景那串
const glowTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d');
  const gr=g.createRadialGradient(64,64,0,64,64,64); gr.addColorStop(0,'rgba(255,255,255,1)'); gr.addColorStop(0.15,'rgba(255,255,255,0.6)'); gr.addColorStop(0.45,'rgba(255,255,255,0.12)'); gr.addColorStop(1,'rgba(255,255,255,0)');
  g.fillStyle=gr; g.fillRect(0,0,128,128); return new THREE.CanvasTexture(c); })();
function glowSprite(color,size,op=1,group=scene){ const s=new THREE.Sprite(new THREE.SpriteMaterial({map:glowTex,color,transparent:true,opacity:op,blending:THREE.AdditiveBlending,depthWrite:false,fog:false})); s.scale.set(size,size,1); group.add(s); return s; }
const ringTexF=(()=>{ const c=document.createElement('canvas'); c.width=c.height=256; const g=c.getContext('2d'); g.strokeStyle='white';
  g.lineWidth=9; g.beginPath(); g.arc(128,128,104,0,Math.PI*2); g.stroke(); g.globalAlpha=0.35; g.lineWidth=3; g.beginPath(); g.arc(128,128,122,0,Math.PI*2); g.stroke(); return new THREE.CanvasTexture(c); })();
function flatRing(color,group){ const m=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({map:ringTexF,color,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide})); m.rotation.x=-Math.PI/2; group.add(m); return m; }
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
// 星点、漂浮微尘（跟着镜头走，任何场景里都在）
const stars=cloud(9000,10,3); { for(let i=0;i<9000;i++){ const r=3200+frnd()*3800, th=frnd()*Math.PI*2, ph=Math.acos(2*frnd()-1); const k=0.35+frnd()*0.6, w=frnd();
  cset(stars,i,r*Math.sin(ph)*Math.cos(th),Math.abs(r*Math.cos(ph))*0.8+60,r*Math.sin(ph)*Math.sin(th),k*(0.7+0.3*w),k*(0.75+0.2*w),k,1);} cdone(stars); }
const motes=cloud(4000,0.06,3,scene,0.6); const MOTE=[]; { for(let i=0;i<4000;i++){ MOTE.push([(frnd()-0.5)*60,frnd()*22,(frnd()-0.5)*60,frnd()]); } }
function setMotes(t,scale=1){ const c=camera.position; for(let i=0;i<4000;i++){ const m=MOTE[i]; const k=0.25+0.35*m[3];
  cset(motes,i,c.x+m[0]*scale+Math.sin(t*0.2+i)*0.6*scale,c.y-6*scale+((m[1]+t*0.25*(0.3+m[3]))%22)*scale,c.z-24*scale+m[2]*scale,k*0.6,k*0.8,k,1); } motes.material.uniforms.uSize.value=0.06*scale; cdone(motes); }

// 灯光：顶部主光 + 冷色环境，突出材质
scene.add(new THREE.HemisphereLight(0xc4d8ff,0x1a2230,1.5));
const sun=new THREE.DirectionalLight(0xffffff,2.1); sun.position.set(40,90,30); scene.add(sun);

// 全息地网
{ const m=new THREE.ShaderMaterial({transparent:true,depthWrite:false,
  vertexShader:`varying vec3 vW; void main(){ vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }`,
  fragmentShader:`varying vec3 vW; float g(vec2 p,float s){ vec2 q=abs(fract(p/s-0.5)-0.5)/fwidth(p/s); return 1.-min(min(q.x,q.y),1.);} void main(){ float d=length(vW.xz); float k=g(vW.xz,4.)*0.3+g(vW.xz,20.)*0.6; float f=exp(-d*0.008); gl_FragColor=vec4(vec3(0.25,0.55,1.)*k*f, k*f*0.5);} `});
  const p=new THREE.Mesh(new THREE.PlaneGeometry(3000,3000),m); p.rotation.x=-Math.PI/2; p.position.y=-0.6; scene.add(p); }

// ---------- 程序纹理 ----------
let seed=7; const rnd=()=>{seed=(seed*16807)%2147483647;return seed/2147483647;};
function canvasTex(w,h,draw){ const c=document.createElement('canvas'); c.width=w; c.height=h; draw(c.getContext('2d'),w,h); const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; t.anisotropy=8; return t; }
function noise(g,w,h,n,cols,rmax){ for(let i=0;i<n;i++){ g.fillStyle=cols[(rnd()*cols.length)|0]; const r=rnd()*rmax+0.5; g.fillRect(rnd()*w,rnd()*h,r,r);} }

// 场地全尺寸（含缓冲区）：长 36.6 m、宽 18.3 m（大满贯中心球场的常见量级，示意）
const FL=36.6, FW=18.3;
const L=23.77/2, DW=10.97/2, SW=8.23/2, SL=6.40;
const PX=40; // 每米像素
function drawLines(g,w,h,col,lw){ // 以场地中心为原点画标准线
  const cx=w/2, cy=h/2, s=PX; g.strokeStyle=col; g.lineWidth=lw*s;
  const R=(x0,y0,x1,y1)=>{ g.beginPath(); g.moveTo(cx+x0*s,cy+y0*s); g.lineTo(cx+x1*s,cy+y1*s); g.stroke(); };
  R(-DW,-L,DW,-L); R(-DW,L,DW,L); R(-DW,-L,-DW,L); R(DW,-L,DW,L); R(-SW,-L,-SW,L); R(SW,-L,SW,L);
  R(-SW,-SL,SW,-SL); R(-SW,SL,SW,SL); R(0,-SL,0,SL); R(0,-L,0,-L+0.10); R(0,L,0,L-0.10);
}
const TW=FW*PX, TH=FL*PX;
const SURF={
  RG: canvasTex(TW,TH,(g,w,h)=>{ // 红土：砖红底 + 细砂颗粒 + 刷痕
    g.fillStyle='#b9562f'; g.fillRect(0,0,w,h);
    noise(g,w,h,90000,['#c8653a','#a94b28','#d27446','#9c4423'],2.2);
    g.globalAlpha=0.08; for(let i=0;i<260;i++){ g.strokeStyle=rnd()<0.5?'#e08a5a':'#8a3a1c'; g.lineWidth=1+rnd()*3; g.beginPath(); const y=rnd()*h; g.moveTo(0,y); g.bezierCurveTo(w*0.3,y+rnd()*40-20,w*0.7,y+rnd()*40-20,w,y+rnd()*30-15); g.stroke(); } g.globalAlpha=1;
    drawLines(g,w,h,'#f4efe6',0.05); }),
  WIM: canvasTex(TW,TH,(g,w,h)=>{ // 草地：割草条纹 + 草叶噪点
    const n=16; for(let i=0;i<n;i++){ g.fillStyle=i%2?'#3f7431':'#4b843a'; g.fillRect(0,i*h/n,w,h/n+1); }
    noise(g,w,h,120000,['#355f2a','#5a9446','#3f7533','#64a04c'],1.6);
    drawLines(g,w,h,'#f7f7f2',0.05); }),
  AO: canvasTex(TW,TH,(g,w,h)=>{ // 澳网：场内略深的蓝、四周更亮的青蓝（2020、2023 年照片取色；2008 年起的双色方案，对比很弱）
    g.fillStyle='#2a9bd9'; g.fillRect(0,0,w,h);
    g.fillStyle='#3486b8'; g.fillRect(w/2-DW*PX,h/2-L*PX,DW*2*PX,L*2*PX);
    noise(g,w,h,40000,['rgba(255,255,255,0.04)','rgba(0,0,0,0.05)'],1.2);
    drawLines(g,w,h,'#ffffff',0.05); }),
  USO: canvasTex(TW,TH,(g,w,h)=>{ // 美网：场内蓝、四周绿（2005 年起）
    g.fillStyle='#3d8a57'; g.fillRect(0,0,w,h);
    g.fillStyle='#2f64b3'; g.fillRect(w/2-DW*PX,h/2-L*PX,DW*2*PX,L*2*PX);
    noise(g,w,h,40000,['rgba(255,255,255,0.05)','rgba(0,0,0,0.06)'],1.2);
    drawLines(g,w,h,'#ffffff',0.05); }),
};
const ROUGH={RG:0.97,WIM:0.92,AO:0.55,USO:0.55};

// ---------- 场馆外观（示意：按真实建筑的平面形状与标志性结构风格化，尺寸不精确） ----------
// 依据（2026-11-02 查）：
//  · 菲利普·夏蒂埃：2020 年加装可开合顶棚，11 片钢桁架「翼」，覆膜，收起时叠放在北看台上方，造型呼应飞行员罗兰·加洛斯的双翼机
//  · 温网中心球场：固定顶棚沿用 1922 年的十二边形；2009 年加装折叠式（手风琴）织物顶棚，钢桁架支撑半透明膜
//  · 阿瑟·阿什：2016 年顶棚，球场外 8 根钢柱撑起独立的上部结构，两块活动顶板；旁边是 1964 年世博会的地球仪雕塑 Unisphere
//  · 罗德·拉沃尔：1988 年启用即有可开合顶棚；墨尔本公园紧邻市中心（天际线为城市背景示意）
const V3=(x,y,z)=>new THREE.Vector3(x,y,z);
function shapePts(shape,rx,rz,n=192){ const pts=[];
  for(let i=0;i<=n;i++){ const a=i/n*Math.PI*2, c=Math.cos(a), s=Math.sin(a);
    if(shape==='round') pts.push([c*rx,s*rz]);
    else if(shape==='chamf'){ const ch=0.24, V=[[1,1-ch],[1-ch*rz/rx,1],[-(1-ch*rz/rx),1],[-1,1-ch],[-1,-(1-ch)],[-(1-ch*rz/rx),-1],[1-ch*rz/rx,-1],[1,-(1-ch)]];
      let best=1e9; for(let j=0;j<8;j++){ const A=V[j],B=V[(j+1)%8], ax=A[0]*rx,az=A[1]*rz,bx=B[0]*rx,bz=B[1]*rz, ex=bx-ax,ez=bz-az, den=c*ez-s*ex; if(Math.abs(den)<1e-9) continue; const t=(ax*ez-az*ex)/den; if(t>0&&t<best) best=t; } pts.push([c*best,s*best]); }
    else if(shape==='oct'){ const k=Math.PI/4, a0=Math.floor((a+k/2)/k)*k-k/2, f=Math.cos(k/2)/Math.cos(a-a0-k/2); pts.push([c*rx*f,s*rz*f]); }
    else if(shape==='dodec'){ const k=Math.PI/6, a0=Math.floor((a+k/2)/k)*k-k/2, f=Math.cos(k/2)/Math.cos(a-a0-k/2); pts.push([c*rx*f,s*rz*f]); }
    else if(shape==='boxp'){ const p=40; pts.push([Math.sign(c)*Math.pow(Math.abs(c),2/p)*rx,Math.sign(s)*Math.pow(Math.abs(s),2/p)*rz]); } // 旧参数化，只给美网膜顶内缘用（膜面按它对齐过）
    else { const p=shape==='box'?40:(shape==='rr'?3.4:9), r=Math.pow(Math.pow(Math.abs(c),p)+Math.pow(Math.abs(s),p),-1/p); pts.push([c*r*rx,s*r*rz]); } } // 极坐标形式的超椭圆：旧写法 sign(c)·|c|^(2/p) 在 cos≈1e-16 处跳成 0.15，看台缺一块楔形（所有者 2026-11-02 截图）
  return pts; }
const lineM=(col,op)=>new THREE.LineBasicMaterial({color:col,transparent:true,opacity:op});
function loop(grp,pts,y,col,op){ grp.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts.map(p=>V3(p[0],y,p[1]))),lineM(col,op))); }
function band(grp,a,b,ya,yb,mat){ // 两条闭合轮廓之间的带状面
  const pos=[],uv=[], n=a.length-1; for(let i=0;i<n;i++){ const A=a[i],B=a[i+1],C=b[i+1],D=b[i], u0=i/n, u1=(i+1)/n;
    pos.push(A[0],ya,A[1], B[0],ya,B[1], C[0],yb,C[1], A[0],ya,A[1], C[0],yb,C[1], D[0],yb,D[1]);
    uv.push(u0,0, u1,0, u1,1, u0,0, u1,1, u0,1); }
  const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2)); g.computeVertexNormals();
  const m=new THREE.Mesh(g,mat); grp.add(m); return m; }
const scl=(pts,k)=>pts.map(p=>[p[0]*k,p[1]*k]);
function edgesOf(mesh,col,op){ const e=new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry,25),lineM(col,op)); e.position.copy(mesh.position); e.rotation.copy(mesh.rotation); return e; }

// 外墙贴图（按 Commons 实拍照片取色与分格，2026-11-02 对照）
const GLASS_AO=canvasTex(1024,128,(g,w,h)=>{ g.fillStyle='#16222e'; g.fillRect(0,0,w,h); for(let x=0;x<w;x+=16){ g.fillStyle='rgba(255,214,160,0.28)'; g.fillRect(x+3,h*0.18,10,h*0.62); g.fillStyle='#0d151d'; g.fillRect(x,0,2,h);} g.fillStyle='#c9d0d6'; g.fillRect(0,h*0.06,w,3); });
GLASS_AO.wrapS=THREE.RepeatWrapping; GLASS_AO.repeat.set(16,1);
const DIAG_AO=canvasTex(1024,256,(g,w,h)=>{ g.fillStyle='#eef1f3'; g.fillRect(0,0,w,h); g.strokeStyle='#aeb8c0'; g.lineWidth=4; for(let x=-w;x<w*2;x+=56){ g.beginPath(); g.moveTo(x,0); g.lineTo(x+h,h); g.stroke(); g.beginPath(); g.moveTo(x+h,0); g.lineTo(x,h); g.stroke(); } });
DIAG_AO.wrapS=THREE.RepeatWrapping;
const FACADE={
  RG: canvasTex(1024,256,(g,w,h)=>{ // 夏蒂埃：白色横向遮阳百叶＋深色玻璃，分层
    g.fillStyle='#b4bbc0'; g.fillRect(0,0,w,h); // 航拍：浅灰色，一层层白色楼板挑出来，楼板之间是灰玻璃
    for(let r=0;r<5;r++){ const y=r*h/5; g.fillStyle='#f1f2f2'; g.fillRect(0,y+4,w,12); g.fillStyle='#d6dadd'; g.fillRect(0,y+16,w,4); g.fillStyle='rgba(88,100,110,0.45)'; g.fillRect(0,y+22,w,h/5-24); }
    for(let x=0;x<w;x+=32){ g.fillStyle='rgba(230,235,238,0.55)'; g.fillRect(x,0,2,h); } }),
  WIM: canvasTex(1024,256,(g,w,h)=>{ // 中心球场：外墙爬满绿植（2017 年外观照片），露出一格格窗
    g.fillStyle='#4f6a2a'; g.fillRect(0,0,w,h); noise(g,w,h,60000,['#6e8a2e','#8a9a35','#4d6b27','#a3a347','#3c5a22','#7b5a2a'],3.5);
    g.fillStyle='rgba(30,45,40,0.85)'; for(let x=14;x<w;x+=56) for(const y of[0.32,0.58]) g.fillRect(x,h*y,34,h*0.16);
    g.fillStyle='#1d2a2c'; g.fillRect(0,0,w,h*0.2); g.fillStyle='rgba(150,180,190,0.25)'; for(let x=0;x<w;x+=20) g.fillRect(x,h*0.02,14,h*0.16); }), // 航拍：外墙最上一圈是深色玻璃带
  AO: canvasTex(1024,256,(g,w,h)=>{ // 罗德·拉沃尔上层：白色横向分层（航拍与 2013/2020 外观照片）
    g.fillStyle='#e9ebe8'; g.fillRect(0,0,w,h); for(let r=0;r<4;r++){ const y=h*(0.12+r*0.24); g.fillStyle='#b8bfc4'; g.fillRect(0,y,w,5); g.fillStyle='rgba(40,60,80,0.45)'; g.fillRect(0,y+8,w,h*0.07); }
    for(let x=0;x<w;x+=64){ g.fillStyle='rgba(150,160,168,0.6)'; g.fillRect(x,0,3,h); } }),
  USO: canvasTex(1024,256,(g,w,h)=>{ // 阿瑟·阿什：砖红色基座
    g.fillStyle='#8a3b2c'; g.fillRect(0,0,w,h); noise(g,w,h,20000,['#7a3326','#9a4434','#843828'],3);
    g.fillStyle='#5d241b'; for(let x=10;x<w;x+=90) g.fillRect(x,h*0.15,18,h*0.75); g.fillStyle='#c9c9c4'; g.fillRect(0,0,w,8); }),
};
for(const t of Object.values(FACADE)){ t.wrapS=THREE.RepeatWrapping; t.repeat.set(5,1); }

// 温网：所有者 2026-11-02「长边更长一些，现在看起来像正方形」——127×110 m 的外轮廓带切角后读成方形，长边沿球场方向（和顶棚收在南北两端一致），长短边比放大到 1.34
// 美网：所有者 2026-11-02「看台围成的也是八边形，不是圆形」
// seat：看台座椅颜色（照片：法网灰、温网深绿、澳网蓝、美网蓝）
const VENUES=[
  {k:'RG', shape:'box',  rx:54.5,rz:54.5,H:30, glow:0xffa070, seat:0x9aa0a6},
  {k:'WIM',shape:'chamf',rx:53,rz:71,H:22, glow:0x8dffa0, seat:0x1f4a2c},
  {k:'AO', shape:'rr',rx:55.5,rz:63,H:30, glow:0x6cc0ff, seat:0x1f4f9a},
  {k:'USO',shape:'oct',rx:74,rz:74,H:28, glow:0x86b0ff, seat:0x22427e},
];
function buildCore(v,grp){ // 球场＋球网（并排镜头只保留这些）
  const court=new THREE.Mesh(new THREE.PlaneGeometry(FW,FL),new THREE.MeshStandardMaterial({map:SURF[v.k],roughness:ROUGH[v.k],metalness:0}));
  court.rotation.x=-Math.PI/2; court.userData.core=1; grp.add(court);
  const netM=new THREE.Mesh(new THREE.PlaneGeometry(12.8,0.95),new THREE.MeshStandardMaterial({color:0x111418,transparent:true,opacity:0.75,side:THREE.DoubleSide}));
  netM.position.set(0,0.48,0); netM.userData.core=1; grp.add(netM);
  const tape=new THREE.Mesh(new THREE.BoxGeometry(12.8,0.07,0.04),new THREE.MeshStandardMaterial({color:0xffffff})); tape.position.set(0,0.95,0); tape.userData.core=1; grp.add(tape);
}
function buildBowl(v,grp){
  const col=new THREE.Color(v.glow), out=shapePts(v.shape,v.rx,v.rz);
  const apron=new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape(scl(out,0.36).map(p=>new THREE.Vector2(p[0],p[1])))),new THREE.MeshStandardMaterial({color:0x14181e,roughness:0.9}));
  apron.rotation.x=Math.PI/2; apron.position.y=-0.02; grp.add(apron);
  const rows=24, seat=new THREE.MeshStandardMaterial({color:v.seat,roughness:0.85,side:THREE.DoubleSide}), riser=new THREE.MeshStandardMaterial({color:0x22262c,roughness:0.9,side:THREE.DoubleSide});
  const top=v.k==='USO'?v.H+14:v.H-3;
  for(let r=0;r<rows;r++){ const s0=0.36+0.6*r/rows, s1=0.36+0.6*(r+1)/rows, y=1+(top-1)*r/rows, y1=1+(top-1)*(r+1)/rows;
    band(grp,scl(out,s0),scl(out,s0),y,y1,riser); band(grp,scl(out,s0),scl(out,s1),y1,y1,seat); }
  const fh=v.k==='USO'?v.H:v.H;
  if(v.k==='RG'){ for(const [px,pz,ry,len] of [[0,v.rz,0,v.rx*2],[0,-v.rz,Math.PI,v.rx*2],[v.rx,0,Math.PI/2,v.rz*2],[-v.rx,0,-Math.PI/2,v.rz*2]]){
      const t=FACADE.RG.clone(); t.needsUpdate=true; t.wrapS=THREE.RepeatWrapping; t.repeat.set(len/40,1);
      const m=new THREE.Mesh(new THREE.PlaneGeometry(len,fh),new THREE.MeshStandardMaterial({map:t,roughness:0.75,metalness:0.05})); m.position.set(px,fh/2,pz); m.rotation.y=ry; grp.add(m); } }
  else if(v.k==='AO') band(grp,scl(out,1.0),scl(out,1.0),0,v.H*0.47,new THREE.MeshStandardMaterial({map:GLASS_AO,emissiveMap:GLASS_AO,emissive:0x6a5a44,roughness:0.2,metalness:0.4,side:THREE.DoubleSide}));
  else band(grp,scl(out,1.0),scl(out,1.0),0,fh,new THREE.MeshStandardMaterial({map:FACADE[v.k],roughness:0.6,metalness:0.1,side:THREE.DoubleSide}));
  if(v.k==='USO') band(grp,scl(out,1.0),scl(out,0.97),fh,top+1,new THREE.MeshStandardMaterial({color:0x3a4250,roughness:0.6,side:THREE.DoubleSide}));
  else band(grp,scl(out,0.96),scl(out,1.0),v.H-3,v.H,new THREE.MeshStandardMaterial({color:0x2a3038,roughness:0.6,side:THREE.DoubleSide}));
}
const fabric=(op=1)=>new THREE.MeshStandardMaterial({color:0xd9dee3,roughness:0.6,transparent:op<1,opacity:op,side:THREE.DoubleSide});
const steel=new THREE.MeshStandardMaterial({color:0xd4d8dc,roughness:0.35,metalness:0.6});
const steelBlue=new THREE.MeshStandardMaterial({color:0x2b4f8a,roughness:0.4,metalness:0.6});
function beam(grp,a,b,r,mat){ const d=b.clone().sub(a), m=new THREE.Mesh(new THREE.CylinderGeometry(r,r,d.length(),8),mat); m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(V3(0,1,0),d.normalize()); grp.add(m); return m; }

// 法网顶棚：11 片「翼」横跨球场（沿 x，跨过两条边线方向），沿球场长度方向（z）一片接一片排开；
// 打开时收拢叠放到北看台上方（-z 一端）。依据：场内照片（翼从一侧边线跨到另一侧）、官方「每片桁架跨度约 105 米、收起叠在北看台」
const RGW=[];
function roofRG(v,grp){
  const n=11, ov=1.6, W2=v.rx+ov, L2=v.rz+ov, w=2*L2/n, y0=v.H+0.4, tilt=0.22;
  for(let i=0;i<n;i++){ const wg=new THREE.Group();
    { // 航拍（dupleix0 2024）：每片翼截面是上拱的弧，收拢后一片压一片，顶面成一道道白色波纹，朝球场一侧的收边呈波浪形
      const NZ=14, pos=[], hA=1.9; for(let k=0;k<NZ;k++){ const z0=-w/2*1.04+w*1.04*k/NZ, z1=-w/2*1.04+w*1.04*(k+1)/NZ, y0=1.0+hA*Math.cos(Math.PI*z0/(w*1.04)), y1=1.0+hA*Math.cos(Math.PI*z1/(w*1.04));
        pos.push(-W2,y0,z0, W2,y0,z0, W2,y1,z1, -W2,y0,z0, W2,y1,z1, -W2,y1,z1); }
      const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.computeVertexNormals();
      wg.add(new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:0xc8cdd1,roughness:0.55,metalness:0.1,side:THREE.DoubleSide})));
      beam(wg,V3(-W2,1.0+hA+0.1,0),V3(W2,1.0+hA+0.1,0),0.28,new THREE.MeshStandardMaterial({color:0x7d858c,roughness:0.5,metalness:0.5})); }
    RGW.push({g:wg, zc:-L2+w*(i+0.5), zo:-L2+w*0.45+i*w*0.24, yo:(n-1-i)*0.6, y0}); grp.add(wg); } // 航拍（dupleix0 2024）：打开后 11 片翼收成一大片白色肋板，盖满北看台、约占进深三分之一，朝北一侧更高
  const fas=new THREE.MeshStandardMaterial({color:0xc9cfd4,roughness:0.45,metalness:0.4}), fh=3.6; // 航拍：屋顶一圈是顶棚滑轨的钢框，比较厚
  for(const [sx,sz,lx,lz] of [[0,-L2,W2*2+0.6,0.6],[0,L2,W2*2+0.6,0.6],[-W2,0,0.6,L2*2+0.6],[W2,0,0.6,L2*2+0.6]]){
    const m=new THREE.Mesh(new THREE.BoxGeometry(lx,fh,lz),fas); m.position.set(sx,y0+0.9,sz); grp.add(m); }
  setRGRoof(0);
}
// 打开时从南往北依次收拢（最南的一片最先动）
function setRGRoof(p){ const n=RGW.length; RGW.forEach((r,i)=>{ const k=Math.max(0,Math.min(1,(p*1.6-(n-1-i)/(n-1)*0.6))); const e=k*k*(3-2*k);
  r.g.position.set(0,r.y0+r.yo*e,r.zc+(r.zo-r.zc)*e);  }); } // 收拢时每片翼外侧抬起，像瓦片一样叠，一道道肋露出来（航拍）
function roofWIM(v,grp){ // 照片：顶棚打开时，白色拱形桁架分两束收在南北两端
  const out=shapePts(v.shape,v.rx,v.rz);
  band(grp,scl(out,0.76),scl(out,1.05),v.H+4.5,v.H+0.6,new THREE.MeshStandardMaterial({color:0x34553e,roughness:0.7,side:THREE.DoubleSide}));
  loop(grp,scl(out,1.05),v.H+0.65,0xcfd8cf,0.9);
  // 所有者给的航拍（AELTC 俯拍）：10 道白色桁架打开时每端收 5 道，桁架之间的白色膜像手风琴一样折起、往下垂成一个个鼓包，
  // 两端各成一大团白色膜堆，盖住开口的南北两头；跨度取该处建筑实际宽度，两脚落在坡屋面外缘
  for(const end of[-1,1]){ const T=[];
    for(let i=0;i<5;i++){ const z=end*(v.rz*0.82-i*2.3), hw=v.rx*0.82, hh=2.6, yb=v.H+4.2; // 所有者 2026-11-02：收起后再紧一点（5 道桁架间距 5.2→2.3 m、整体贴到两端；同日第二次要求「再紧一点」）；顶棚不要冒出来——收拢的膜堆贴着坡屋面，只略高一点
      const top=[],bot=[]; for(let j=0;j<=24;j++){ const u=j/24*2-1; top.push(V3(u*hw,yb+(1-u*u)*hh,z)); bot.push(V3(u*hw*0.97,yb+(1-u*u)*(hh-1.2),z)); }
      grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(top),48,0.5,6,false),steel));
      grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(bot),48,0.35,6,false),steel));
      for(let j=1;j<24;j++) beam(grp,j%2?bot[j]:top[j],j%2?top[j+1]:bot[j+1],0.16,steel);
      for(const sx of[-1,1]){ const f=top[sx<0?0:24]; const pad=new THREE.Mesh(new THREE.BoxGeometry(2.2,1.2,2.6),steel); pad.position.set(f.x,yb-0.4,z); grp.add(pad); }
      T.push(top.map(q=>V3(q.x,q.y-0.3,q.z))); }
    const geo=new THREE.BufferGeometry(), pos=[];
    for(let i=0;i<4;i++){ const A=T[i],B=T[i+1]; const M=A.map((a,j)=>{ const b=B[j], u=j/24*2-1; return V3((a.x+b.x)/2,(a.y+b.y)/2-0.9*(1-u*u)-0.3,(a.z+b.z)/2); });
      for(let j=0;j<24;j++){ for(const [P,Q] of [[A,M],[M,B]]){ const a=P[j],b=P[j+1],c=Q[j+1],d=Q[j]; pos.push(a.x,a.y,a.z,b.x,b.y,b.z,c.x,c.y,c.z, a.x,a.y,a.z,c.x,c.y,c.z,d.x,d.y,d.z); } } }
    geo.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); geo.computeVertexNormals(); grp.add(new THREE.Mesh(geo,new THREE.MeshStandardMaterial({color:0xf2f3ef,roughness:0.55,metalness:0.05,side:THREE.DoubleSide}))); }
  // 外墙上的钟（2017 年外观照片）
  const clock=new THREE.Mesh(new THREE.CircleGeometry(1.6,40),new THREE.MeshStandardMaterial({color:0xf3f0e6})); clock.position.set(0,v.H*0.7,v.rz*0.99+0.15); grp.add(clock);
}
function roofAO(v,grp){ // 澳网官方《RLA gets a roof upgrade》（2019）俯拍：顶棚打开时两片可移动顶板退到长轴两端、架高在固定屋面上；
  // 中间露出近方形的开口；白色弓形桁架横跨短边（每端两道），两脚落到外沿
  const out=shapePts(v.shape,v.rx,v.rz), hx=v.rx*0.60, hz=v.rz*0.33, yR=v.H*1.18, pz=v.rz*0.40, px=v.rx*0.66;
  const sh=new THREE.Shape(scl(out,1.02).map(p=>new THREE.Vector2(p[0],p[1])));
  sh.holes.push(new THREE.Path([new THREE.Vector2(-hx,-hz),new THREE.Vector2(hx,-hz),new THREE.Vector2(hx,hz),new THREE.Vector2(-hx,hz)]));
  const r=new THREE.Mesh(new THREE.ShapeGeometry(sh),new THREE.MeshStandardMaterial({color:0xcfd2d0,roughness:0.6,metalness:0.2,side:THREE.DoubleSide})); r.rotation.x=Math.PI/2; r.position.y=yR; grp.add(r);
  const panM=new THREE.MeshStandardMaterial({color:0xe4e4de,roughness:0.55,metalness:0.15}), rib=new THREE.MeshStandardMaterial({color:0xb9bcb8,roughness:0.6});
  for(const sz of[-1,1]){ const zc=sz*(hz+pz/2);
    const pan=new THREE.Mesh(new THREE.BoxGeometry(px*2,1.6,pz),panM); pan.position.set(0,yR+2.2,zc); grp.add(pan);
    for(let q=-5;q<=5;q++) beam(grp,V3(q*px/5.5,yR+3.05,zc-pz/2),V3(q*px/5.5,yR+3.05,zc+pz/2),0.14,rib);
    for(const f of[0.22,0.78]){ const z=sz*(hz+pz*f), w=Math.sqrt(Math.max(0,1-(Math.abs(z)/v.rz)**3))*v.rx*0.98, yb=yR+0.4, top=[],bot=[];
      for(let j=0;j<=24;j++){ const u=j/24*2-1; top.push(V3(u*w,yb+(1-u*u)*9,z)); bot.push(V3(u*w*0.97,yb+(1-u*u)*5.5,z)); }
      grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(top),48,0.55,8,false),steel));
      grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(bot),48,0.38,8,false),steel));
      for(let j=1;j<24;j++) beam(grp,j%2?bot[j]:top[j],j%2?top[j+1]:bot[j+1],0.18,steel);
      for(const sx of[-1,1]){ const m=top[sx<0?0:24]; beam(grp,V3(m.x,v.H*0.3,m.z),m,0.5,steel); } } } // 外沿落地的白柱
}
function roofUSO(v,grp){ // 照片：圆角方形的白色膜顶像一块鼓起的「枕头」，蓝色钢桁架斜撑落在外柱上，中间可开合
  const top=v.H+14, R=v.rx*1.06; // 膜顶外缘 ≈ OSM 建筑轮廓 157 m
  const out=shapePts('boxp',R,R).map(p=>[p[0],p[1]]), sq=shapePts('round',1,1);
  const oc=shapePts('oct',R*1.04,R*1.04); // 俯拍（Constructify 2025）：膜顶外缘是切了角的八边形
  const canopyOut=shapePts('round',R,R).map((p,i)=>{ const q=oc[i]; return [p[0]*0.25+q[0]*0.75,p[1]*0.25+q[1]*0.75]; });
  { const NA=canopyOut.length-1, NR=14, pos=[]; const F0=0.56; const P=(i,k)=>{ const f=F0+(1-F0)*k/NR, a=i/NA*Math.PI*2, c=canopyOut[i%NA];
      const dome=15*Math.sqrt(Math.max(0,1-Math.pow((f-F0)/(1-F0),2))), puff=6.5*Math.pow(Math.abs(Math.cos(2*a)),3)*Math.sin(Math.PI*Math.min(1,(f-F0)/(1-F0)));
      const t=(f-F0)/(1-F0), q=out[i%NA]; // 无人机俯拍（Invincible Storm Films 2020）：开口是方角的正方形，外缘才是圆鼓的枕头
      return [q[0]*F0*0.92*(1-t)+c[0]*t, top+1.2+dome+puff, q[1]*F0*0.92*(1-t)+c[1]*t]; };
    for(let i=0;i<NA;i++) for(let k=0;k<NR;k++){ const A=P(i,k),B=P(i+1,k),C=P(i+1,k+1),D=P(i,k+1); pos.push(...A,...B,...C,...A,...C,...D); }
    const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.computeVertexNormals(); grp.add(new THREE.Mesh(g,fabric()));
    const lip=[]; for(let i=0;i<=NA;i++){ const q=P(i,NR); lip.push(V3(q[0],q[1],q[2])); } grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(lip,true),220,0.9,6,true),new THREE.MeshStandardMaterial({color:0xe6e9ec,roughness:0.5})));  { const inner=[]; for(let i=0;i<=NA;i++){ const q=P(i,0); inner.push(V3(q[0],q[1],q[2])); } grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(inner,true),220,0.7,6,true),steelBlue)); } }
  // 外柱与蓝色斜撑
  // 照片（Commons「Arthur Ashe Stadium with retractible roof」）：顶棚由一圈蓝色钢柱托着，柱子贴着砖红基座外侧落地，
  // 柱间是从地面斜拉到顶棚外缘的大 X 形蓝色斜撑——不是离开建筑、单独立着的灰色细杆
  const n=8, cr=v.rx*1.005; const ring=canopyOut;
  for(let i=0;i<n;i++){ const a=(i+0.5)/n*Math.PI*2, c=V3(Math.cos(a)*cr,0,Math.sin(a)*cr), T=V3(c.x,top+0.8,c.z);
    beam(grp,c,T,0.8,steelBlue);
    for(const s of [-1,1]){ const b=a+s*Math.PI/n*0.95, e=V3(Math.cos(b)*cr*1.02,v.H*0.55,Math.sin(b)*cr*1.02);
      beam(grp,V3(c.x,v.H*0.12,c.z),e,0.4,steelBlue); beam(grp,e,V3(Math.cos(b)*R*0.98,top+0.8,Math.sin(b)*R*0.98),0.4,steelBlue); } }
  // 蓝色钢桁架层：基座顶部到膜顶外缘，上下两道环梁＋竖杆＋交叉斜撑（照片里很密）
  const ringE=(()=>{ const P=ring.slice(0,ring.length-1), d=[0]; for(let i=1;i<=P.length;i++){ const a=P[i-1],b=P[i%P.length]; d.push(d[i-1]+Math.hypot(b[0]-a[0],b[1]-a[1])); }
    const T=d[P.length], out=[]; let j=0; for(let k=0;k<96;k++){ const t=k/96*T; while(d[j+1]<t) j++; const f=(t-d[j])/(d[j+1]-d[j]), a=P[j], b=P[(j+1)%P.length]; out.push([a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f]); } out.push(out[0]); return out; })();
  const NA=ringE.length-1, yL=v.H+1, yU=top+0.8, mid=(yL+yU)/2;
  for(const [k,y] of [[0.90,yL],[0.95,mid],[1.0,yU]]) grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(ringE.slice(0,NA).map(p=>V3(p[0]*k,y,p[1]*k)),true),200,0.45,6,true),steelBlue));
  for(let i=0;i<NA;i+=1){ const p=ringE[i], q=ringE[(i+1)%NA];
    beam(grp,V3(p[0]*0.90,yL,p[1]*0.90),V3(p[0],yU,p[1]),0.35,steelBlue);
    beam(grp,V3(p[0]*0.90,yL,p[1]*0.90),V3(q[0]*0.95,mid,q[1]*0.95),0.22,steelBlue);
    beam(grp,V3(q[0]*0.95,mid,q[1]*0.95),V3(p[0],yU,p[1]),0.22,steelBlue); }
}
function shellAO(v,grp){ // 外墙：下层通高玻璃（buildBowl 里），上层白色横向分层；斜格的白色弧形外壳只在一侧入口（2020 年 Commons 照片）
  const o=shapePts(v.shape,v.rx,v.rz), n=o.length-1, yR=v.H*1.18;
  band(grp,scl(o,1.0),scl(o,1.0),v.H*0.47,yR,new THREE.MeshStandardMaterial({map:FACADE.AO,roughness:0.5,metalness:0.1,side:THREE.DoubleSide}));
  // 一侧入口的斜格外壳：所有者 2026-11-02 要求拿掉
  grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(scl(o,1.01).map(p=>V3(p[0],yR+0.2,p[1])),true),200,0.6,6,true),steel)); }
const ROOF={RG:roofRG,WIM:roofWIM,AO:roofAO,USO:roofUSO};

// ---------- 周边 ----------
function trees(n,R0,R1,col){ const g=new THREE.Group(); const m=new THREE.MeshStandardMaterial({color:col,roughness:0.9});
  for(let i=0;i<n;i++){ const a=rnd()*Math.PI*2, r=R0+rnd()*(R1-R0), s=3+rnd()*3.5; const t=new THREE.Mesh(new THREE.SphereGeometry(s,10,8),m); t.position.set(Math.cos(a)*r,s*1.3,Math.sin(a)*r); t.scale.y=1.2; g.add(t); } return g; }
function paris(){ const g=new THREE.Group(); seed=99; const m=new THREE.MeshStandardMaterial({color:0x8f8778,roughness:0.9}), r=new THREE.MeshStandardMaterial({color:0x6d7680,roughness:0.6});
  for(let i=0;i<70;i++){ const w=14+rnd()*16, d=12+rnd()*14, h=16+rnd()*12; const x=(rnd()-0.5)*700, z=-230-rnd()*260;
    const b=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),m); b.position.set(x,h/2,z); g.add(b); const t=new THREE.Mesh(new THREE.BoxGeometry(w,3,d),r); t.position.set(x,h+1.5,z); g.add(t); } return g; }
function unisphere(col){ const g=new THREE.Group(), R=17, m=lineM(col,0.85);
  for(let i=1;i<9;i++){ const y=R*Math.cos(i/9*Math.PI), r=R*Math.sin(i/9*Math.PI); const pts=[]; for(let j=0;j<=64;j++){ const a=j/64*Math.PI*2; pts.push(V3(Math.cos(a)*r,y,Math.sin(a)*r)); } g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),m)); }
  for(let i=0;i<12;i++){ const pts=[]; for(let j=0;j<=48;j++){ const b=j/48*Math.PI; pts.push(V3(Math.sin(b)*Math.cos(i/12*Math.PI*2)*R,Math.cos(b)*R,Math.sin(b)*Math.sin(i/12*Math.PI*2)*R)); } g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),m)); }
  for(const tilt of[0.5,-0.4,1.2]){ const t=new THREE.Mesh(new THREE.TorusGeometry(R*1.28,0.18,8,96),steel); t.rotation.set(Math.PI/2+tilt,tilt*0.6,0); g.add(t); }
  const ped=new THREE.Mesh(new THREE.CylinderGeometry(1.2,3.5,12,16),steel); ped.position.y=-R-4; g.add(ped);
  const pool=new THREE.Mesh(new THREE.CircleGeometry(36,64),new THREE.MeshStandardMaterial({color:0x10304f,roughness:0.15,metalness:0.6})); pool.rotation.x=-Math.PI/2; pool.position.y=-R-9.9; g.add(pool);
  g.position.y=R+10; return g; }
function skyline(col){ const g=new THREE.Group(); seed=4242;
  for(let i=0;i<46;i++){ const w=8+rnd()*14, d=8+rnd()*14, h=30+Math.pow(rnd(),1.6)*170; const x=(i-23)*15+rnd()*6, z=-rnd()*70;
    const b=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),new THREE.MeshStandardMaterial({color:0x2a3646,roughness:0.3,metalness:0.7}));
    b.position.set(x,h/2,z); g.add(b); g.add(edgesOf(b,col,0.3)); }
  return g; }

const POS={AO:[-340,-320],RG:[340,-320],WIM:[-340,320],USO:[340,320]}; // 按一年里的大满贯顺序：澳网 → 法网 → 温网 → 美网
const RG_ROOF={};
const venues=VENUES.map(v=>{ const g=new THREE.Group(); buildCore(v,g); buildBowl(v,g);
  ROOF[v.k](v,g); if(v.k==='AO') shellAO(v,g); g.position.set(POS[v.k][0],0,POS[v.k][1]); scene.add(g); return {...v,g}; });
// 周边：法网——布洛涅林边的树和巴黎的低层建筑；澳网——墨尔本市中心天际线；美网——地球仪雕塑
const lmRG=new THREE.Group(); lmRG.add(paris()); lmRG.position.set(POS.RG[0],0,POS.RG[1]); scene.add(lmRG); // 所有者：法网旁边不画树
const lmAO=skyline(0x6cc0ff); lmAO.position.set(POS.AO[0]-150,0,POS.AO[1]-200); lmAO.scale.set(0.8,0.8,0.8); lmAO.rotation.y=0.64; scene.add(lmAO);
const lmUSO=unisphere(0x9cc2ff); lmUSO.position.set(POS.USO[0]-150,0,POS.USO[1]+60); scene.add(lmUSO);


// ================= 实验场：三种地面的落地对比 / 落地慢镜 / 指数光柱 / 法网逐年 =================
const anchors={};
function proj(name,v){ const p=v.clone().project(camera); anchors[name]=[(p.x*0.5+0.5)*W,(1-(p.y*0.5+0.5))*H,(p.z<1&&p.z>-1)?1:0]; }
const glowMat=(c,o=1)=>new THREE.MeshBasicMaterial({color:c,transparent:true,opacity:o,blending:THREE.AdditiveBlending,depthWrite:false});
// --- 落地对比：来球 25 m/s、入射 16°；摩擦与弹性取 Cross（Physics Today 2008）：红土 μ 可达 0.9、e≈0.85；草地 μ 0.5–0.6、e 0.6–0.75；硬地 e≈0.75
// 水平出速 vx'=max(vx−μ(1+e)vy, 0.55·vx)（滑动到咬住为止）；硬地 μ 无公开数，只作示意、不上屏
const LAB=V3(0,0,1300), LANES=[{k:'RG',mu:0.9,e:0.85,col:0xff8a4a},{k:'WIM',mu:0.55,e:0.67,col:0x7dff8a},{k:'AO',mu:0.65,e:0.75,col:0x5fc2ff}];
const VIN=25, ANG=16*Math.PI/180, G=9.81;
LANES.forEach((ln,i)=>{ const vx=VIN*Math.cos(ANG), vy=VIN*Math.sin(ANG); ln.vx2=Math.max(vx-ln.mu*(1+ln.e)*vy,0.55*vx); ln.vy2=ln.e*vy; ln.vx=vx; ln.vy=vy; ln.z=(i-1)*7; ln.out=Math.atan2(ln.vy2,ln.vx2)*180/Math.PI; });
const labG=new THREE.Group(); labG.position.copy(LAB); scene.add(labG);
// 泳道 60×6 m（x −20…40）。所有者：标线要和来球方向一致、一条泳道就是一块场地从左到右——
// 整块单打场沿 x 摆：左底线 −18、球网 −6、右发球线 0.4（落点 x=0 就在发球线附近）、右底线 5.77；宽度压到泳道内（示意）
const NETX=-6;
function laneTex(k){ const P2=40, w=60*P2, h=6*P2, X=x=>(x+20)*P2, Z=z=>(z+3)*P2;
  return canvasTex(w,h,(g)=>{
    if(k==='RG'){ g.fillStyle='#b9562f'; g.fillRect(0,0,w,h); noise(g,w,h,60000,['#c8653a','#a94b28','#d27446','#9c4423'],2.2); }
    else if(k==='WIM'){ for(let i=0;i<20;i++){ g.fillStyle=i%2?'#3f7431':'#4b843a'; g.fillRect(i*w/20,0,w/20+1,h); } noise(g,w,h,80000,['#355f2a','#5a9446','#3f7533','#64a04c'],1.6); }
    else { g.fillStyle='#2a9bd9'; g.fillRect(0,0,w,h); g.fillStyle='#3486b8'; g.fillRect(X(NETX-L),Z(-2.7),L*2*P2,5.4*P2); noise(g,w,h,30000,['rgba(255,255,255,0.04)','rgba(0,0,0,0.05)'],1.2); }
    // 所有者：双打线要画上，画半块场就行——泳道宽 6 m ≈ 半场宽 5.49 m（中线→双打边线），按真实尺寸画
    g.strokeStyle=k==='RG'?'#f4efe6':'#ffffff'; g.lineWidth=0.05*P2; const R=(x0,z0,x1,z1)=>{ g.beginPath(); g.moveTo(X(x0),Z(z0)); g.lineTo(X(x1),Z(z1)); g.stroke(); };
    const b0=NETX-L, b1=NETX+L, zc=-2.74, zs=zc+SW, zd=zc+DW;
    R(b0,zd,b1,zd); R(b0,zs,b1,zs); R(b0,zc,b0,zd); R(b1,zc,b1,zd); R(NETX-SL,zc,NETX-SL,zs); R(NETX+SL,zc,NETX+SL,zs); R(NETX-SL,zc,NETX+SL,zc);
    g.setLineDash([0.3*P2,0.3*P2]); g.globalAlpha=0.35; R(b0,zc,NETX-SL,zc); R(NETX+SL,zc,b1,zc); g.setLineDash([]); g.globalAlpha=1; }); }
LANES.forEach(ln=>{ const t=laneTex(ln.k);
  const m=new THREE.Mesh(new THREE.PlaneGeometry(60,6),new THREE.MeshStandardMaterial({map:t,roughness:0.8})); m.rotation.x=-Math.PI/2; m.position.set(10,0,ln.z); labG.add(m);
  const net=new THREE.Mesh(new THREE.PlaneGeometry(6.2,0.914),new THREE.MeshStandardMaterial({color:0x111418,transparent:true,opacity:0.6,side:THREE.DoubleSide})); net.rotation.y=Math.PI/2; net.position.set(NETX,0.457,ln.z); labG.add(net);
  const tp=new THREE.Mesh(new THREE.BoxGeometry(0.05,0.06,6.2),new THREE.MeshStandardMaterial({color:0xffffff})); tp.position.set(NETX,0.914,ln.z); labG.add(tp);
  ln.ball=new THREE.Mesh(new THREE.SphereGeometry(0.2,24,16),new THREE.MeshStandardMaterial({color:0xd8f040,emissive:0x7a8a18,roughness:0.6})); labG.add(ln.ball); ln.glow=glowSprite(0xe8ff70,1.6,0.9,labG);
  ln.trail=new THREE.Mesh(new THREE.BufferGeometry(),glowMat(ln.col,0.95)); labG.add(ln.trail);
  ln.ring=new THREE.Mesh(new THREE.RingGeometry(0.3,0.5,32),glowMat(ln.col,0)); ln.ring.rotation.x=-Math.PI/2; ln.ring.position.set(0,0.03,ln.z); labG.add(ln.ring); });
// 所有者：草地也要有标线——草叶会把贴图上的线盖住，在草尖高度另铺一层白线
{ const ln=LANES[1], m=new THREE.MeshBasicMaterial({color:0xf4f8f0,transparent:true,opacity:0.9}), b0=NETX-L, b1=NETX+L, zc=-2.74, zs=zc+SW, zd=zc+DW, y=0.36;
  const S=(x0,z0,x1,z1)=>{ const w=0.06, len=Math.hypot(x1-x0,z1-z0), g=new THREE.PlaneGeometry(Math.abs(x1-x0)>0.01?len:w,Math.abs(x1-x0)>0.01?w:len); const me=new THREE.Mesh(g,m); me.rotation.x=-Math.PI/2; me.position.set((x0+x1)/2,y,ln.z+(z0+z1)/2); labG.add(me); };
  S(b0,zd,b1,zd); S(b0,zs,b1,zs); S(b0,zc,b0,zd); S(b1,zc,b1,zd); S(NETX-SL,zc,NETX-SL,zs); S(NETX+SL,zc,NETX+SL,zs); S(NETX-SL,zc,NETX+SL,zc); }
// 小球在 τ 秒的位置（τ<0 来球，τ≥0 弹出），落点在 x=0
function lanePos(ln,tau){ if(tau<0) return V3(ln.vx*tau,0.2+(-ln.vy*tau-0.5*G*tau*tau),ln.z);
  return V3(ln.vx2*tau,0.2+ln.vy2*tau-0.5*G*tau*tau,ln.z); }
function setLanes(tau,show){ LANES.forEach((ln,i)=>{ ln.ball.visible=ln.trail.visible=!!show[i]; const pts=[]; for(let k=0;k<=60;k++){ const tt=-0.9+(tau+0.9)*k/60; pts.push(lanePos(ln,tt)); }
  ln.trail.geometry.dispose(); ln.trail.geometry=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),80,0.045,6,false); ln.ball.position.copy(lanePos(ln,tau)); ln.glow.visible=!!show[i]; ln.glow.position.copy(ln.ball.position);
  ln.ring.material.opacity=show[i]&&tau>=0?Math.max(0,0.9-tau*1.2):0; const sc=1+Math.max(0,tau)*4; ln.ring.scale.set(sc,sc,sc);
  if(show[i]){ const w=labG.localToWorld(lanePos(ln,Math.min(tau,0.75)).clone()); proj('lane_'+ln.k,w); proj('lane_'+ln.k+'_hit',labG.localToWorld(V3(0,0,ln.z))); } }); }
// --- 落地慢镜：一个大球压在地面上，先滑后咬住；摩擦（金）向后、支持力（青）向上
const SLO=V3(0,0,1600), sloG=new THREE.Group(); sloG.position.copy(SLO); scene.add(sloG);
{ // 所有者：球太大、地面不够宽也不够深——地面铺到很远（240×160），只留一条白线做参照，往远处渐隐进黑底
  const t=canvasTex(1024,1024,(g,w,h)=>{ g.fillStyle='#2f8fc8'; g.fillRect(0,0,w,h); noise(g,w,h,60000,['rgba(255,255,255,0.05)','rgba(0,0,0,0.06)'],1.4); }); t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(24,16);
  const fade=canvasTex(16,512,(g,w,h)=>{ const gr=g.createLinearGradient(0,0,0,h); gr.addColorStop(0,'#000'); gr.addColorStop(0.30,'#000'); gr.addColorStop(0.52,'#fff'); gr.addColorStop(1,'#fff'); g.fillStyle=gr; g.fillRect(0,0,w,h); }); fade.colorSpace=THREE.NoColorSpace;
  const fl=new THREE.Mesh(new THREE.PlaneGeometry(240,160),new THREE.MeshStandardMaterial({map:t,alphaMap:fade,transparent:true,roughness:0.75})); fl.rotation.x=-Math.PI/2; sloG.add(fl);
  const ln=new THREE.Mesh(new THREE.PlaneGeometry(120,0.35),new THREE.MeshBasicMaterial({color:0xf2f6f8,alphaMap:fade,transparent:true})); ln.rotation.x=-Math.PI/2; ln.position.set(0,0.01,2.6); sloG.add(ln); }
const BR=1.3, bigBall=new THREE.Group(); sloG.add(bigBall);
{ const tex=canvasTex(512,256,(g,w,h)=>{ g.fillStyle='#d6ee3c'; g.fillRect(0,0,w,h); noise(g,w,h,30000,['#c8e030','#e2f55a','#b9d128'],2); g.strokeStyle='#f6f8ee'; g.lineWidth=10; g.beginPath(); for(let x=0;x<=w;x+=4){ const y=h/2+Math.sin(x/w*Math.PI*4)*h*0.28; x?g.lineTo(x,y):g.moveTo(x,y);} g.stroke(); });
  bigBall.add(new THREE.Mesh(new THREE.SphereGeometry(BR,48,32),new THREE.MeshStandardMaterial({map:tex,roughness:0.85}))); }
function arrow(col){ const g=new THREE.Group(); const m=glowMat(col,0.95); const sh=new THREE.Mesh(new THREE.CylinderGeometry(0.09,0.09,1,10),m); sh.position.y=0.5; const hd=new THREE.Mesh(new THREE.ConeGeometry(0.28,0.6,16),m); hd.position.y=1.15; g.add(sh,hd); g.userData={sh,hd}; sloG.add(g); return g; }
function setArrow(a,len){ a.visible=len>0.05; a.userData.sh.scale.y=len; a.userData.sh.position.y=len/2; a.userData.hd.position.y=len+0.3; }
const arF=arrow(0xffb347), arN=arrow(0x5fe0ff); arF.rotation.z=Math.PI/2; // 指向 -x
const patch=new THREE.Mesh(new THREE.CircleGeometry(0.6,32),glowMat(0xffb347,0)); patch.rotation.x=-Math.PI/2; patch.position.y=0.02; sloG.add(patch);
// q∈[0,1]：0–0.25 来球；0.25–0.5 滑动；0.5–0.72 咬住；0.72–1 弹出
function setSlow(q){ const xIn=-9, ang=16*Math.PI/180; let x,y,sq=1,rot,phase;
  if(q<0.25){ const k=q/0.25; x=xIn*(1-k); y=BR+(-xIn)*(1-k)*Math.tan(ang); phase='in'; }
  else if(q<0.5){ const k=(q-0.25)/0.25; x=k*1.6; y=BR*(1-0.10*Math.sin(k*Math.PI/2)); sq=1-0.10*Math.sin(k*Math.PI/2); phase='slide'; }
  else if(q<0.72){ const k=(q-0.5)/0.22; x=1.6+k*0.9; y=BR*0.9; sq=0.9; phase='grip'; }
  else { const k=(q-0.72)/0.28; x=2.5+k*7; y=BR*0.9+k*k*0+ k*7*Math.tan(22*Math.PI/180); sq=0.9+0.1*Math.min(1,k*3); phase='out'; }
  bigBall.position.set(x,y,0); bigBall.scale.set(1/Math.sqrt(sq),sq,1/Math.sqrt(sq));
  // 旋转：滑动时转得比滚动慢，咬住后转速追上
  rot=-(phase==='in'?0: phase==='slide'?(x)*0.25/BR : phase==='grip'?(1.6*0.25+(x-1.6))/BR : (1.6*0.25+0.9+(x-2.5)*0.8)/BR); bigBall.rotation.z=rot;
  const fr=phase==='slide'?3.2:phase==='grip'?1.6*(1-(q-0.5)/0.22)+0.4:0, nr=(phase==='slide'||phase==='grip')?4.2:0;
  arF.position.set(x,0.25,1.2); setArrow(arF,fr*0.75); arN.position.set(x,0.05,-1.2); setArrow(arN,nr*0.7);
  patch.position.x=x; patch.material.opacity=(phase==='slide'||phase==='grip')?0.75:0; patch.material.color.set(phase==='grip'?0x5fe0ff:0xffb347);
  proj('slo_ball',sloG.localToWorld(V3(x,y+BR,0))); proj('slo_contact',sloG.localToWorld(V3(x,0,0))); proj('slo_fr',sloG.localToWorld(V3(x-fr-0.4,0.25,1.2))); proj('slo_nr',sloG.localToWorld(V3(x,nr+0.6,-1.2)));
  return phase; }
// --- 指数光柱：立在并排的四块场地上（2015–2026，见 papers/.../data/speed_result.json）
const IDX={RG:0.748,USO:1.02,WIM:1.086,AO:1.119}, pillars={};
for(const k of ['RG','WIM','AO','USO']){ const c={RG:0xff8a4a,WIM:0x7dff8a,AO:0x5fc2ff,USO:0x6f8cff}[k];
  const m=new THREE.Mesh(new THREE.BoxGeometry(6,1,6),glowMat(c,0.3)); const e=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(6,1,6)),lineM(c,1)); m.add(e); m.visible=false; scene.add(m); pillars[k]=m; }
const ref1=new THREE.Mesh(new THREE.PlaneGeometry(96,0.25),glowMat(0xffffff,0.6)); ref1.visible=false; scene.add(ref1);
function setPillars(p,hi){ const SC=26; ['RG','WIM','AO','USO'].forEach((k,i)=>{ const v=venues.find(z=>z.k===k), h=Math.max(0.01,IDX[k]*SC*p), m=pillars[k];
  m.visible=p>0; m.scale.y=h; m.position.set(v.g.position.x,h/2+0.5,v.g.position.z); m.material.opacity=(hi&&!hi.includes(k))?0.1:0.3; m.children[0].material.opacity=(hi&&!hi.includes(k))?0.25:1;
  if(p>0.08) proj('pil_'+k,V3(v.g.position.x,h+3,v.g.position.z)); });
  ref1.visible=p>0.98; ref1.position.set(0,SC*1+0.5,0); ref1.rotation.x=0; if(p>0.98) proj('pil_ref',V3(-50,SC+0.5,0)); }
// --- 法网逐年（2015–2025；2020 在秋天、换了比赛用球）
const RGY={2015:0.755,2016:0.793,2017:0.823,2018:0.818,2019:0.743,2020:0.597,2021:0.842,2022:0.737,2023:0.635,2024:0.715,2025:0.721};
const YRS=Object.keys(RGY).map(Number), yrG=new THREE.Group(); yrG.position.set(0,0,2000); scene.add(yrG); const ybars={};
{ const t=SURF.RG.clone(); t.needsUpdate=true; t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(1.5,0.4);
  const fl=new THREE.Mesh(new THREE.PlaneGeometry(90,30),new THREE.MeshStandardMaterial({map:t,roughness:0.9})); fl.rotation.x=-Math.PI/2; yrG.add(fl); }
YRS.forEach((y,i)=>{ const c=0xff9a5a; const m=new THREE.Mesh(new THREE.BoxGeometry(4.6,1,4.6),glowMat(c,0.28)); m.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(4.6,1,4.6)),lineM(c,1))); m.position.x=(i-5)*7; yrG.add(m); ybars[y]=m; });
function setYears(p,drop){ YRS.forEach((y,i)=>{ const k=Math.max(0,Math.min(1,p*1.5-i*0.05)); const v=RGY[y]; if(y===2020){ const c0=new THREE.Color(0xff9a5a), c1=new THREE.Color(0xff3a3a); ybars[y].material.color.lerpColors(c0,c1,drop); ybars[y].children[0].material.color.lerpColors(c0,c1,drop); }
  const h=Math.max(0.01,v*30*k), m=ybars[y]; m.scale.y=h; m.position.y=h/2; proj('yr_'+y,yrG.localToWorld(V3((i-5)*7,h+2.5,0))); proj('yrb_'+y,yrG.localToWorld(V3((i-5)*7,-1.5,3))); }); }


seed=20260502;
// --- 红土落地扬尘、草叶（让红土和草地有实感）
const dust=(()=>{ const n=260, g=new THREE.BufferGeometry(), pos=new Float32Array(n*3); g.setAttribute('position',new THREE.BufferAttribute(pos,3));
  const m=new THREE.PointsMaterial({color:0xd9764a,size:0.16,transparent:true,opacity:0,depthWrite:false}); const p=new THREE.Points(g,m); labG.add(p);
  const seeds=[]; for(let i=0;i<n;i++) seeds.push([ (rnd()-0.3)*3.2, rnd()*1.6+0.4, (rnd()-0.5)*2.6 ]); return {p,m,pos,seeds}; })();
function setDust(tau){ const ln=LANES[0]; if(tau<0||tau>1.4||!ln.ball.visible){ dust.m.opacity=0; return; }
  dust.seeds.forEach((s,i)=>{ dust.pos[i*3]=s[0]*tau*1.6; dust.pos[i*3+1]=Math.max(0,s[1]*tau-2.2*tau*tau)+0.05; dust.pos[i*3+2]=ln.z+s[2]*tau; });
  dust.p.geometry.attributes.position.needsUpdate=true; dust.m.opacity=Math.max(0,0.9-tau*0.7); }
{ const ln=LANES[1], N=48000, geo=new THREE.PlaneGeometry(0.05,0.30,1,2); geo.translate(0,0.15,0);
  const m=new THREE.MeshStandardMaterial({color:0xffffff,roughness:0.75,side:THREE.DoubleSide,emissive:0x0c2a08}), blades=new THREE.InstancedMesh(geo,m,N), d=new THREE.Object3D();
  for(let i=0;i<N;i++){ d.position.set(-14+rnd()*46,0,ln.z+(rnd()-0.5)*5.9); d.rotation.set((rnd()-0.5)*0.35,rnd()*Math.PI,(rnd()-0.5)*0.35); const k=0.6+rnd()*0.8; d.scale.set(1,k,1); d.updateMatrix(); blades.setMatrixAt(i,d.matrix);
    const band=Math.floor((d.position.x+20)/3)%2; blades.setColorAt(i,new THREE.Color().setHSL(0.27+rnd()*0.04,0.50+rnd()*0.12,0.40+band*0.08+rnd()*0.10)); }
  labG.add(blades); }
// --- 硬地剖面：几层丙烯酸涂层；左边颗粒大、有棱角，右边更细、更圆（Laykold：前者 M3 中速，后者 M4 中快）
const ACR=V3(0,0,2400), acrG=new THREE.Group(); acrG.position.copy(ACR); scene.add(acrG);
{ const layers=[[0x5b5f66,1.4,'基层'],[0x2b3138,0.5,'缓冲层'],[0x245fa8,0.25,'色层'],[0x2f73c4,0.18,'面漆']]; let y=0;
  layers.forEach(([c,h],li)=>{ const bg=new THREE.BoxGeometry(30,h,8); const m=new THREE.Mesh(bg,new THREE.MeshStandardMaterial({color:[0x1a2a44,0x22385c,0x245fa8,0x2f73c4][li],roughness:0.7,emissive:[0x050c1a,0x07122a,0x0a1e44,0x0e2a5c][li]})); m.position.y=y+h/2; acrG.add(m);
    const e=new THREE.LineSegments(new THREE.EdgesGeometry(bg),new THREE.LineBasicMaterial({color:0x7fd8ff,transparent:true,opacity:0.55})); e.position.copy(m.position); acrG.add(e); y+=h; });
  acrG.userData.top=y; const top=y, d=new THREE.Object3D();
  const coarse=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.11,0),new THREE.MeshStandardMaterial({color:0xd8cfb8,roughness:0.6,flatShading:true}),900);
  const fine=new THREE.InstancedMesh(new THREE.SphereGeometry(0.045,8,6),new THREE.MeshStandardMaterial({color:0xe6dfcc,roughness:0.5}),2600);
  for(let i=0;i<900;i++){ d.position.set(-14.5+rnd()*13.5,top+0.04,(rnd()-0.5)*7.6); d.rotation.set(rnd()*6,rnd()*6,rnd()*6); d.scale.setScalar(0.7+rnd()*0.7); d.updateMatrix(); coarse.setMatrixAt(i,d.matrix); }
  for(let i=0;i<2600;i++){ d.position.set(1+rnd()*13.5,top+0.02,(rnd()-0.5)*7.6); d.rotation.set(0,0,0); d.scale.setScalar(0.8+rnd()*0.4); d.updateMatrix(); fine.setMatrixAt(i,d.matrix); }
  acrG.add(coarse,fine); const div=new THREE.Mesh(new THREE.PlaneGeometry(0.06,1.2),glowMat(0xffffff,0.7)); div.position.set(0,top+0.6,4); acrG.add(div); }
const fuzzTex=canvasTex(256,128,(g,w,h)=>{ g.fillStyle='#d6ee3c'; g.fillRect(0,0,w,h); noise(g,w,h,9000,['#c3dc2c','#e9f86a','#b5cd24'],2); });
const acrBalls=[-1,1].map(sx=>{ const b=new THREE.Mesh(new THREE.SphereGeometry(1.4,40,28),new THREE.MeshStandardMaterial({map:fuzzTex,roughness:0.95})); acrG.add(b); return b; });
function setAcryl(q){ const top=acrG.userData.top; acrBalls.forEach((b,i)=>{ const slow=i===0; const x0=(i===0?-13:2), dist=slow?7:11.5; const x=x0+dist*Math.min(1,q); b.position.set(x,top+1.4*0.96,0); b.rotation.z=-x/1.4*(slow?1:0.6);
  proj(i===0?'acr_coarse':'acr_fine',acrG.localToWorld(V3(i===0?-7.5:7.5,top+3.9,0))); proj(i===0?'acr_ball0':'acr_ball1',acrG.localToWorld(V3(x,top+2.9,0))); });
  proj('acr_layers',acrG.localToWorld(V3(-15,1.0,4))); }
// --- 澳网逐年（2015–2026；2020 年起 GreenSet）
const AOY={2015:1.124,2016:1.222,2017:1.156,2018:1.074,2019:1.191,2020:1.020,2021:1.189,2022:1.090,2023:1.076,2024:1.094,2025:1.103,2026:1.064};
const AYRS=Object.keys(AOY).map(Number), aoG=new THREE.Group(); aoG.position.set(0,0,2800); scene.add(aoG); const abars={};
{ const t=SURF.AO.clone(); t.needsUpdate=true; t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(1.5,0.4);
  const fl=new THREE.Mesh(new THREE.PlaneGeometry(96,30),new THREE.MeshStandardMaterial({map:t,roughness:0.6})); fl.rotation.x=-Math.PI/2; aoG.add(fl); }
AYRS.forEach((y,i)=>{ const m=new THREE.Mesh(new THREE.BoxGeometry(4.6,1,4.6),glowMat(0x7cc8ff,0.28)); m.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(4.6,1,4.6)),lineM(0x7cc8ff,1))); m.position.x=(i-5.5)*7.2; aoG.add(m); abars[y]=m; });
function setAOYears(p,hi){ AYRS.forEach((y,i)=>{ const k=Math.max(0,Math.min(1,p*1.5-i*0.05)), h=Math.max(0.01,AOY[y]*24*k), m=abars[y]; m.scale.y=h; m.position.y=h/2;
  const on=hi&&(y===2020||y===2021); m.material.color.set(on?0xffc04a:0x7cc8ff); m.children[0].material.color.set(on?0xffd27a:0x7cc8ff);
  proj('ay_'+y,aoG.localToWorld(V3((i-5.5)*7.2,h+2.5,0))); proj('ayb_'+y,aoG.localToWorld(V3((i-5.5)*7.2,-1.5,3))); }); }


// --- 泳道特效：光晕拖尾、残影、落地火花、扫光、全息网格（只用固定种子随机）
seed=8080;
{ const m=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
  vertexShader:`varying vec2 vP; void main(){ vP=position.xy; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader:`varying vec2 vP; float g(vec2 p,float s){ vec2 q=abs(fract(p/s-0.5)-0.5)/fwidth(p/s); return 1.-min(min(q.x,q.y),1.);} void main(){ float k=g(vP,1.0)*0.25+g(vP,5.0)*0.55; float f=exp(-length(vP*vec2(0.025,0.06))); gl_FragColor=vec4(vec3(0.3,0.65,1.0)*k*f,k*f*0.6);} `});
  const gp=new THREE.Mesh(new THREE.PlaneGeometry(120,60),m); gp.rotation.x=-Math.PI/2; gp.position.set(10,-0.05,0); labG.add(gp); }
const sweep=new THREE.Mesh(new THREE.PlaneGeometry(4.0,24),new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uA:{value:0}},
  vertexShader:`varying vec2 vU; void main(){ vU=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader:`uniform float uA; varying vec2 vU; void main(){ float k=exp(-pow((vU.x-0.5)*5.0,2.0)); gl_FragColor=vec4(vec3(0.55,0.85,1.0)*k*uA,k*uA); }`}));
sweep.rotation.x=-Math.PI/2; sweep.position.y=0.04; labG.add(sweep);
LANES.forEach(ln=>{ ln.halo=new THREE.Mesh(new THREE.BufferGeometry(),glowMat(ln.col,0.22)); labG.add(ln.halo);
  ln.ghosts=[1,2,3,4,5].map(i=>{ const g=new THREE.Mesh(new THREE.SphereGeometry(0.2,16,10),glowMat(0xe8ff60,0.35/i)); labG.add(g); return g; });
  const n=90, geo=new THREE.BufferGeometry(), pos=new Float32Array(n*3); geo.setAttribute('position',new THREE.BufferAttribute(pos,3));
  ln.spark={pts:new THREE.Points(geo,new THREE.PointsMaterial({color:ln.col,size:0.14,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false})),pos,seeds:[]};
  for(let i=0;i<n;i++){ const a=rnd()*Math.PI*2, v=2+rnd()*5; ln.spark.seeds.push([Math.cos(a)*v,1+rnd()*4,Math.sin(a)*v*0.6]); } labG.add(ln.spark.pts); });
function setFX(tau,show,u){ LANES.forEach((ln,i)=>{ const on=!!show[i]; ln.halo.visible=on; ln.ghosts.forEach(g=>g.visible=on&&tau>-0.85); ln.spark.pts.visible=on;
  if(!on) return; ln.halo.geometry.dispose();
  { const pts=[]; for(let k=0;k<=60;k++){ const tt=-0.9+(tau+0.9)*k/60; pts.push(lanePos(ln,tt)); } ln.halo.geometry=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),80,0.16,8,false); }
  ln.ghosts.forEach((g,j)=>g.position.copy(lanePos(ln,tau-(j+1)*0.035)));
  const st=tau; ln.spark.pts.material.opacity=(st>=0&&st<0.6)?(1-st/0.6):0; ln.spark.seeds.forEach((sd,j)=>{ ln.spark.pos[j*3]=sd[0]*st; ln.spark.pos[j*3+1]=Math.max(0.02,sd[1]*st-4.9*st*st); ln.spark.pos[j*3+2]=ln.z+sd[2]*st; }); ln.spark.pts.geometry.attributes.position.needsUpdate=true; });
  const w=((u||0)*0.35)%1; sweep.position.x=-20+w*60; sweep.material.uniforms.uA.value=Math.sin(Math.PI*w)*0.35; }

// --- 落地粒子：红土扬尘（慢慢升起、悬着）、草地草屑＋水珠、硬地火花（短促、带拖影）
const IMP=LANES.map((ln,i)=>{ const n=[1600,900,800][i], P=cloud(n,[0.2,0.12,0.09][i],[14,8,6][i],labG,0.2), sd=[];
  for(let j=0;j<n;j++){ const a=frnd()*Math.PI*2;
    if(ln.k==='RG'){ const r=Math.pow(frnd(),0.6)*2.2; sd.push([ Math.cos(a)*r, 0.3+frnd()*2.4, Math.sin(a)*r*0.8, 0.8+frnd()*1.4, frnd() ]); }
    else if(ln.k==='WIM') sd.push([ 1.5+frnd()*5, 0.8+frnd()*3.2, Math.cos(a)*(0.4+frnd()*1.8), 0.4+frnd()*0.6, frnd() ]);
    else sd.push([ 3+frnd()*9, 0.5+frnd()*3.5, Math.cos(a)*(0.6+frnd()*2.8), 0.15+frnd()*0.35, frnd() ]); }
  const ring=flatRing(ln.col,labG), ring2=flatRing(0xffffff,labG), flash=glowSprite(ln.col,1,0,labG); return {ln,P,sd,ring,ring2,flash}; });
function setImpacts(tau,show){ IMP.forEach((im,i)=>{ const on=!!show[i]&&tau>=0; const ln=im.ln; if(!on){ chide(im.P); im.ring.material.opacity=0; im.ring2.material.opacity=0; im.flash.material.opacity=0; return; }
  const t=tau; for(let j=0;j<im.sd.length;j++){ const d=im.sd[j]; let x,y,z,a,r,g,b;
    if(ln.k==='RG'){ const drag=1-Math.exp(-t*2.4); x=d[0]*drag+1.2*drag; y=Math.max(0.03,d[1]*drag*0.6*(1-0.25*drag)); z=ln.z+d[2]*drag; a=Math.max(0,1-t/(1.6*d[3]))*0.9; const k=0.6+0.4*d[4]; r=1.0*k; g=0.8*k; b=0.6*k; }
    else if(ln.k==='WIM'){ x=d[0]*t; y=Math.max(0.02,d[1]*t-4.9*t*t); z=ln.z+d[2]*t; a=Math.max(0,1-t/(d[3]+0.6)); const wet=d[4]>0.8; r=wet?0.9:0.7; g=wet?0.97:1.0; b=wet?1.0:0.55; }
    else { x=d[0]*t; y=Math.max(0.02,d[1]*t-4.9*t*t); z=ln.z+d[2]*t; a=Math.max(0,1-t/d[3]); r=0.85; g=0.97; b=1.0; }
    cset(im.P,j,x,y,z,r,g,b,a); } cdone(im.P);
  const s1=0.6+t*9, s2=0.4+t*5; im.ring.scale.set(s1,s1,1); im.ring.position.set(0,0.04,ln.z); im.ring.material.opacity=Math.max(0,0.95-t*1.5);
  im.ring2.scale.set(s2,s2,1); im.ring2.position.set(0,0.05,ln.z); im.ring2.material.opacity=Math.max(0,0.7-t*2.2);
  im.flash.position.set(0,0.4,ln.z); const f=Math.max(0,1-t*5); im.flash.scale.set(3+6*(1-f),3+6*(1-f),1); im.flash.material.opacity=f; }); }
// 时间斜坡：落地前后放慢（0.4 倍），远离落地时正常速度——落地那一下看得清
const ramp=s=>0.55*(s-0.24*Math.tanh(s/0.4));


// --- 第 3 集同款背景：实验场四周一圈全息看台（光点排成的一层层看台），跟着当前实验场走
const BOWL=new THREE.Group(); scene.add(BOWL); { const n=36000, P=cloud(n,0.5,4,BOWL,0.25); let i=0;
  for(let r=0;r<40&&i<n;r++){ const R=70+r*2.4, y=1+r*1.3, m=Math.floor(2*Math.PI*R*1.3/1.6); for(let j=0;j<m&&i<n;j++,i++){ const a=j/m*Math.PI*2+(r%2)*0.01; const k=0.35+0.4*frnd();
    cset(P,i,Math.cos(a)*R*1.3,y,Math.sin(a)*R,0.7*k,0.85*k,1.0*k,frnd()<0.85?1.0:0.3); } }
  for(;i<n;i++) cset(P,i,0,-999,0,0,0,0,0); cdone(P);
  const haze=new THREE.Mesh(new THREE.CylinderGeometry(150,150,70,64,1,true),new THREE.ShaderMaterial({transparent:true,depthWrite:false,side:THREE.BackSide,blending:THREE.AdditiveBlending,
    vertexShader:`varying vec2 vU; void main(){ vU=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
    fragmentShader:`varying vec2 vU; void main(){ float k=exp(-pow((vU.y-0.25)*3.0,2.0)); gl_FragColor=vec4(vec3(0.05,0.09,0.22)*k,k*0.22); }`}));
  haze.scale.set(1.3,1,1); haze.position.y=30; BOWL.add(haze); }
// 所有者（看着第 3 集的画面）：「把场地换掉，周边的环境不动」——照第 3 集：一大片饱和的深蓝地面，细细的白色发光长线一直延伸到地平线，地平线一圈亮线
{ const fl=new THREE.Mesh(new THREE.PlaneGeometry(900,900),new THREE.ShaderMaterial({depthWrite:true,
    vertexShader:`varying vec3 vW; void main(){ vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }`,
    fragmentShader:`varying vec3 vW; uniform vec3 uC; uniform float uK; float ln(float v,float s,float w){ float q=abs(fract(v/s-0.5)-0.5)*s; return 1.0-smoothstep(0.0,w*fwidth(v)*1.5+0.02,q); }
      void main(){ float d=length((vW.xz-uC.xz)*vec2(0.75,1.0))/uK; vec3 base=mix(vec3(0.003,0.010,0.12),vec3(0.03,0.045,0.13),smoothstep(60.,300.,d));
        float g=max(ln(vW.x-uC.x,23.77,1.0),ln(vW.z-uC.z,10.97,1.0))*0.22*exp(-d*0.006);
        gl_FragColor=vec4(base+vec3(0.35,0.5,0.9)*g,1.0); }`,uniforms:{uC:{value:new THREE.Vector3()},uK:{value:1}}}));
  fl.rotation.x=-Math.PI/2; fl.position.y=-0.08; BOWL.add(fl); BOWL.userData.floor=fl;
  const hz=new THREE.Mesh(new THREE.TorusGeometry(1,0.004,6,180),new THREE.MeshBasicMaterial({color:0x9fc8ff,transparent:true,opacity:0.45,blending:THREE.AdditiveBlending,depthWrite:false})); hz.rotation.x=Math.PI/2; hz.scale.set(240*1.3,240,240); hz.position.y=0.2; BOWL.add(hz); }
function setBowl(center,sc=1){ BOWL.visible=!!center; if(center){ BOWL.position.copy(center); BOWL.scale.setScalar(sc); BOWL.userData.floor.material.uniforms.uK.value=sc; BOWL.updateMatrixWorld(true); BOWL.userData.floor.material.uniforms.uC.value.copy(center); } }

// --- 2020 秋天的法网：天冷——雪花／冷雾落在逐年柱上（r7 起）
const SNOW=cloud(5000,0.5,8,scene,0.5), SNS=[]; for(let i=0;i<5000;i++) SNS.push([(frnd()-0.5)*110,frnd()*60,(frnd()-0.5)*70,0.6+frnd()*0.8,frnd()*6.28]);
function setSnow(te,Y){ if(te<0||!Y){ SNOW.visible=false; return; } SNOW.visible=true; const a=Math.min(1,te/1.2);
  for(let i=0;i<5000;i++){ const d=SNS[i]; const y=((d[1]-te*3.2*d[3])%60+60)%60; cset(SNOW,i,Y.x+d[0]+Math.sin(te*0.8+d[4])*1.5,Y.y+y,Y.z+d[2],0.75,0.88,1.0,a*0.75); } cdone(SNOW); }


// --- 全息地球（2026-11-02，讲故事的主线：一年四站——墨尔本 1 月 → 巴黎 5–6 月 → 伦敦 6–7 月 → 纽约 8–9 月；开场点亮、片尾拉回）
const GLB=V3(0,0,4200), globeG=new THREE.Group(), globeR=new THREE.Group(); globeG.position.copy(GLB); globeG.add(globeR); scene.add(globeG); const GRAD=40;
// 所有者：「要用真实的地球，现在这个太丑了」——NASA Blue Marble 白天地表＋ Earth at Night 城市夜光（公有领域，见 tex/SOURCE.md），带昼夜分界、海面高光、大气辉光
const TEXL=new THREE.TextureLoader(); const EARTH_READY=Promise.all(['tex/earth_bluemarble_4096.jpg','tex/earth_night_2048.jpg'].map(f=>new Promise(res=>TEXL.load(f,t=>{ t.colorSpace=THREE.SRGBColorSpace; t.anisotropy=8; res(t); }))));
const earthMat=new THREE.ShaderMaterial({uniforms:{uDay:{value:null},uNight:{value:null},uSun:{value:new THREE.Vector3(0.6,0.35,0.7).normalize()}},
  vertexShader:`varying vec2 vUv; varying vec3 vN,vW,vV; void main(){ vUv=uv; vN=normalize(mat3(modelMatrix)*normal); vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz; vV=normalize(cameraPosition-w.xyz); gl_Position=projectionMatrix*viewMatrix*w; }`,
  fragmentShader:`uniform sampler2D uDay,uNight; uniform vec3 uSun; varying vec2 vUv; varying vec3 vN,vW,vV;
    void main(){ vec3 n=normalize(vN), v=normalize(vV); vec3 day=texture2D(uDay,vUv).rgb, night=texture2D(uNight,vUv).rgb; float nd=dot(n,uSun);
      float dl=smoothstep(-0.18,0.25,nd); float ocean=smoothstep(0.02,0.10,day.b-max(day.r,day.g)*0.85);
      vec3 h=normalize(uSun+v); float spec=pow(max(dot(n,h),0.0),60.0)*ocean*0.25*(1.0-smoothstep(0.35,0.6,max(day.r,max(day.g,day.b))));
      vec3 col=day*(0.06+0.95*max(nd,0.0))*dl + night*vec3(1.0,0.82,0.55)*1.6*(1.0-dl)*(1.0-ocean*0.8) + vec3(1.0,0.95,0.85)*spec*dl;
      float fr=pow(1.0-clamp(dot(n,v),0.0,1.0),3.0); col+=vec3(0.25,0.5,1.0)*fr*0.7*(0.3+0.7*dl);
      gl_FragColor=vec4(col,1.0); }`});
EARTH_READY.then(([d,n])=>{ earthMat.uniforms.uDay.value=d; earthMat.uniforms.uNight.value=n; });
const earth=new THREE.Mesh(new THREE.SphereGeometry(GRAD,128,64),earthMat); globeR.add(earth);
{ const atm=new THREE.Mesh(new THREE.SphereGeometry(GRAD*1.06,96,48),new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.BackSide,
    vertexShader:`varying vec3 vN,vV; void main(){ vN=normalize(mat3(modelMatrix)*normal); vec4 w=modelMatrix*vec4(position,1.); vV=normalize(cameraPosition-w.xyz); gl_Position=projectionMatrix*viewMatrix*w; }`,
    fragmentShader:`varying vec3 vN,vV; void main(){ float d=clamp(dot(normalize(vN),normalize(vV)),0.0,1.0); float f=clamp(pow(d,3.0)*1.4,0.0,1.0); gl_FragColor=vec4(vec3(0.3,0.6,1.0)*f,f); }`})); globeG.add(atm); }
const llv=(la,lo,r=GRAD)=>{ la*=Math.PI/180; lo*=Math.PI/180; return V3(r*Math.cos(la)*Math.cos(lo),r*Math.sin(la),-r*Math.cos(la)*Math.sin(lo)); };
const CITY=[{k:'AO',la:-37.82,lo:144.98,c:0x5fc2ff},{k:'RG',la:48.85,lo:2.25,c:0xff8a4a},{k:'WIM',la:51.43,lo:-0.21,c:0x7dff8a},{k:'USO',la:40.75,lo:-73.85,c:0x6f8cff}];
CITY.forEach(C=>{ C.p=llv(C.la,C.lo); C.glow=glowSprite(C.c,9,0,globeR); C.glow.position.copy(llv(C.la,C.lo,GRAD*1.02));
  const dir=C.p.clone().normalize(); C.beam=new THREE.Mesh(new THREE.CylinderGeometry(0.25,0.6,12,10,1,true),glowMat(C.c,0)); C.beam.position.copy(dir.clone().multiplyScalar(GRAD+6)); C.beam.quaternion.setFromUnitVectors(V3(0,1,0),dir); globeR.add(C.beam);
  C.ring=new THREE.Mesh(new THREE.RingGeometry(1.2,1.7,40),glowMat(C.c,0)); C.ring.position.copy(dir.clone().multiplyScalar(GRAD*1.01)); C.ring.quaternion.setFromUnitVectors(V3(0,0,1),dir); globeR.add(C.ring); });
const GARC=[]; for(let i=0;i<4;i++){ const A=CITY[i], B=CITY[(i+1)%4], a=A.p.clone().normalize(), b=B.p.clone().normalize(), om=Math.acos(Math.min(1,a.dot(b))), pts=[];
  for(let j=0;j<=80;j++){ const u=j/80, v=a.clone().multiplyScalar(Math.sin((1-u)*om)/Math.sin(om)).add(b.clone().multiplyScalar(Math.sin(u*om)/Math.sin(om))); pts.push(v.multiplyScalar(GRAD*(1.01+0.28*Math.sin(Math.PI*u)*om/Math.PI))); }
  const geo=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),120,i===1?0.09:0.35,8,false) /* 巴黎→伦敦只在俯冲时近看，细一点 */, m=new THREE.Mesh(geo,glowMat(0xbfe2ff,0.85)); globeR.add(m); const dot=glowSprite(0xffffff,5,0,globeR); GARC.push({m,n:geo.index.count,curve:new THREE.CatmullRomCurve3(pts),dot}); }
const thetaOf=C=>-C.lo*Math.PI/180-Math.PI/2;
// q：0–1 依次点亮四站（第 i 站在 i/4 处亮起，弧线在两站之间画出）；loop=true 时第 4 段弧连回墨尔本
function setGlobe(q,t,{loop=false,active=-1}={}){ globeG.visible=q>=0; if(q<0) return; const seg=q*4;
  CITY.forEach((C,i)=>{ const on=cl((seg-i)*3); C.glow.material.opacity=on; const pul=1+0.25*Math.sin(t*5+i); C.glow.scale.set(9*pul,9*pul,1); C.beam.material.opacity=0; C.beam.visible=false; C.ring.material.opacity=on*0.8*(0.6+0.4*Math.sin(t*3+i)); const sc=1+((t*0.9+i*0.3)%1)*2.5; C.ring.scale.set(sc,sc,1);
    proj('city_'+C.k,globeR.localToWorld(llv(C.la,C.lo,GRAD*1.08))); val('city_on_'+C.k,on); });
  GARC.forEach((A,i)=>{ A.m.material.opacity=0.85; const f=i<3?cl(seg-i-0.4):(loop?cl(seg-3.2):0); A.m.geometry.setDrawRange(0,Math.floor(A.n*f/3)*3); A.m.visible=f>0; A.dot.material.opacity=(f>0&&f<1)?1:0; if(f>0) A.dot.position.copy(A.curve.getPoint(f)); });
  // 镜头绕着地球飞：从当前一站的方向看过去，慢慢转到下一站（地球本身不转，保证亮起的城市在画面中间）
  const idx=active>=0?active:Math.min(3,Math.floor(seg)), fr=cl(seg-idx), C0=CITY[idx], C1=CITY[Math.min(3,idx+1)], a=C0.p.clone().normalize(), b=C1.p.clone().normalize();
  const w=sm((fr-0.45)*1.8), om=Math.acos(Math.min(1,a.dot(b))); GLOBE_DIR.copy(om<1e-3?a:a.clone().multiplyScalar(Math.sin((1-w)*om)/Math.sin(om)).add(b.clone().multiplyScalar(Math.sin(w*om)/Math.sin(om)))).normalize();
  { const LOW=68, hop=LOW+75*om, fly=lerp(LOW,hop,Math.sin(Math.PI*w)); GFLY=seg<0.4?lerp(185,fly,sm(seg/0.4)):fly; GIDX=idx; }
  globeR.rotation.set(0,0,0); globeR.updateMatrixWorld(true); }
let GFLY=150, GIDX=0; // 所有者 2026-11-02「不应该固定一个高度的视角」：高度随每一跳的远近变（墨尔本→巴黎飞得最高，巴黎→伦敦贴着飞）
const GLOBE_DIR=new THREE.Vector3(0,0,1);
function globeCam(dist,up=0.25,fov=34){ const d=GLOBE_DIR.clone(); d.y+=up; d.normalize(); val('globe_alt',Math.round((dist-GRAD)/GRAD*6371)); val('globe_lat',CITY.reduce((m,C)=>m,0)); { const side=new THREE.Vector3().crossVectors(V3(0,1,0),d).normalize(); earthMat.uniforms.uSun.value.copy(d).addScaledVector(side,-1.7).add(V3(0,0.3,0)).normalize(); } /* 太阳从画面左上侧打过来：看得到昼夜分界和右侧的城市夜光 */ camLook(GLB.x+d.x*dist,GLB.y+d.y*dist,GLB.z+d.z*dist,GLB.x,GLB.y,GLB.z,fov); 
  { const k=Math.min(1,Math.max(0.25,(dist-GRAD)/100)); CITY.forEach(C=>{ C.glow.scale.multiplyScalar(k); C.ring.scale.multiplyScalar(k); }); GARC.forEach(A=>A.dot.scale.set(5*k,5*k,1)); } /* 俯冲到低空时光点别糊满屏 */
  camera.updateMatrixWorld(true); CITY.forEach(C=>{ const w=globeR.localToWorld(llv(C.la,C.lo,GRAD*1.02)); proj('city_'+C.k,w); /* 镜头移完再投影：setGlobe 里那次用的是上一帧的机位，标签全飞到画面外 */
    if(w.clone().sub(GLB).normalize().dot(camera.position.clone().sub(w).normalize())<0.12) anchors['city_'+C.k][2]=0; }); }
function val(n,v){ anchors[n]=v; }

// --- 画板式拆解的节拍表（红土 15.3 s / 草地 6.8 s；与 overlay.py 的 tele 画线一一对应）
function telePlan(RG,sec,u,D){ const T=f=>at(sec,f)-sec.t0;
  if(RG){ const n2=T('n2'), n3=T('n3');
    if(u<4.6) return {mode:'live',cam:'far',tau:cl(ramp((u%4.6)-1.2)*0.85,-0.9,1.3)};
    if(u<5.2){ const w=sm((u-4.6)/0.6); return {mode:'rewind',cam:'near',tau:lerp(1.1,-0.7,w)}; }
    if(u<n2){ const w=(u-5.2)/(n2-5.2); return {mode:'slow',cam:'near',tau:lerp(-0.7,0.015,sm(w)),k:w}; }
    if(u<n3-0.6){ const w=u-n2; return {mode:'freeze',cam:'near',tau:0.015,fid:1,punch:sm(w/0.35),flash:Math.max(0,1-w/0.1)*0.7,k:cl(w/0.8)}; }
    if(u<n3){ const w=(u-(n3-0.6))/0.6; return {mode:'slow',cam:'side',side:sm(w),tau:lerp(0.015,0.5,w)}; }
    if(u<n3+2.6){ const w=u-n3; return {mode:'freeze',cam:'side',tau:0.5,fid:2,flash:Math.max(0,1-w/0.1)*0.7,k:cl(w/0.8)}; }
    return {mode:'live',cam:'near',tau:cl(ramp(((u-n3-2.6)%4.6)-1.2)*0.85,-0.9,1.3)}; }
  if(u<2.4) return {mode:'live',cam:'far',tau:cl(ramp(u-0.9)*0.85,-0.9,1.3)};
  if(u<2.9){ const w=(u-2.4)/0.5; return {mode:'slow',cam:'side',side:sm(w),tau:lerp(0.0,0.5,w)}; }
  const w=u-2.9; return {mode:'freeze',cam:'side',tau:0.5,fid:3,flash:Math.max(0,1-w/0.1)*0.7,k:cl(w/0.8)}; }

// --- 发球指数做成实物（Lemo-Opuscar「Data Physicalization」）：1 片金属圆片＝0.05，每第 10 片换成黄铜当刻度；指数升起时一片片落下叠起来
const STK={}, PLATE=0.05, PH=1.3; const ENV=new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(),0.04).texture; { const g=new THREE.CylinderGeometry(2.6,2.6,PH*0.86,40), d=new THREE.Object3D();
  const mats={RG:0xc8673a,WIM:0x6fae63,AO:0x5aa8d8,USO:0x5a73c8}, brass=new THREE.MeshStandardMaterial({color:0xe0b85a,metalness:0.9,roughness:0.28,envMap:ENV,envMapIntensity:1.2});
  ['RG','WIM','AO','USO'].forEach(k=>{ const n=Math.ceil(IDX[k]/PLATE); const m=new THREE.MeshStandardMaterial({color:mats[k],metalness:0.6,roughness:0.3,envMap:ENV,envMapIntensity:1.3}); const im=new THREE.InstancedMesh(g,m,n), ib=new THREE.InstancedMesh(g,brass,n); im.count=0; ib.count=0; scene.add(im,ib);
    const jit=[]; for(let i=0;i<n;i++) jit.push([(frnd()-0.5)*0.12,(frnd()-0.5)*0.12,frnd()*6.28]); STK[k]={im,ib,n,jit}; }); }
function setStacks(p,hi,t){ ['RG','WIM','AO','USO'].forEach(k=>{ const S=STK[k], v=venues.find(z=>z.k===k), d=new THREE.Object3D(); let a=0,b=0; const shown=p*S.n, dim=(hi&&!hi.includes(k));
    for(let i=0;i<S.n;i++){ const f=cl(shown-i); if(f<=0) break; const drop=(1-sm(f))*8, frac=(i===S.n-1)?(IDX[k]/PLATE-(S.n-1)):1;
      d.position.set(v.g.position.x+S.jit[i][0],0.6+i*PH+PH*0.43+drop,v.g.position.z+S.jit[i][1]); d.rotation.set(0,S.jit[i][2],0); d.scale.set(1,frac,1); d.updateMatrix();
      if((i+1)%10===0){ S.ib.setMatrixAt(b++,d.matrix); } else S.im.setMatrixAt(a++,d.matrix); }
    S.im.count=a; S.ib.count=b; S.im.instanceMatrix.needsUpdate=true; S.ib.instanceMatrix.needsUpdate=true; S.im.material.transparent=!!dim; S.im.material.opacity=dim?0.25:1;
    const h=0.6+IDX[k]/PLATE*PH*Math.min(1,p); if(p>0.08) proj('pil_'+k,V3(v.g.position.x,h+3,v.g.position.z)); }); }
function hideStacks(){ for(const k in STK){ STK[k].im.count=0; STK[k].ib.count=0; } }

// ================= 2026-11-02 重做的特效层（所有者：「整体不精致……要有酷炫的动画、粒子动效，比例和物理也要合理」） =================
const MOTE_SCALE={v_RG:7,v_WIM:7,v_AO:7,v_USO:8,lineup:3,pillars:3,pillars_hi:3,wim:6,outro:22,years:2.5,ao_years:2.5,acryl:0.6,slow:0.5};

// --- 粒子聚字（第 4 集同款）：挂在镜头前方，提问、关键数字、片尾金句由粒子聚成、再散开
scene.add(camera); const MG=new THREE.Group(); camera.add(MG);
const NM=12000, MORPH=cloud(NM,0.16,6,MG,0.35); MORPH.material.depthTest=false; MORPH.renderOrder=999; const LANG=Q.get('lang')||'zh'; // 字挂在镜头前，镜头往下看时别被地面挡住
const MSH={}; const mDel=new Float32Array(NM), mPh=new Float32Array(NM); for(let i=0;i<NM;i++){ mDel[i]=frnd(); mPh[i]=frnd()*6.283; }
const NUMF='800 300px "Inter","Noto Sans CJK SC",sans-serif', SERIF='900 300px "Noto Serif CJK SC",serif';
function textShape(str,font,width,col,{y=0,jitter=0.03}={}){ const c=document.createElement('canvas'); c.width=2048; c.height=512; const g=c.getContext('2d');
  g.fillStyle='#000'; g.fillRect(0,0,2048,512); g.fillStyle='#fff'; g.font=font; g.textAlign='center'; g.textBaseline='middle';
  const mw=g.measureText(str).width; if(mw>1900){ g.font=font.replace('300px',Math.floor(300*1900/mw)+'px'); } g.fillText(str,1024,262);
  const d=g.getImageData(0,0,2048,512).data, pts=[]; let minx=1e9,maxx=-1e9; for(let yy=0;yy<512;yy+=3) for(let xx=0;xx<2048;xx+=3){ if(d[(yy*2048+xx)*4]>140){ pts.push([xx,yy]); minx=Math.min(minx,xx); maxx=Math.max(maxx,xx); } }
  const sc=width/(maxx-minx), p=new Float32Array(NM*3), cc=new Float32Array(NM*3); for(let i=pts.length-1;i>0;i--){ const j=Math.floor(frnd()*(i+1)); [pts[i],pts[j]]=[pts[j],pts[i]]; }
  for(let i=0;i<NM;i++){ const k=1.2+frnd()*0.6;
    if(i<pts.length*1.6){ const q=pts[i%pts.length]; p[i*3]=(q[0]-1024)*sc+(frnd()-0.5)*jitter; p[i*3+1]=-(q[1]-262)*sc+y+(frnd()-0.5)*jitter; p[i*3+2]=(frnd()-0.5)*jitter*4; cc[i*3]=col.r*k; cc[i*3+1]=col.g*k; cc[i*3+2]=col.b*k; }
    else { const a=frnd()*6.283, r=width*(0.55+frnd()*0.9); p[i*3]=Math.cos(a)*r; p[i*3+1]=Math.sin(a)*r*0.3+y; p[i*3+2]=(frnd()-0.5)*6; const kk=0.12*k; cc[i*3]=col.r*kk; cc[i*3+1]=col.g*kk; cc[i*3+2]=col.b*kk; } }
  return {p,c:cc}; }
function burstShape(R,col){ const p=new Float32Array(NM*3), cc=new Float32Array(NM*3); for(let i=0;i<NM;i++){ const a=frnd()*6.283, b=Math.acos(2*frnd()-1), r=R*Math.cbrt(frnd()); p[i*3]=Math.sin(b)*Math.cos(a)*r; p[i*3+1]=Math.cos(b)*r*0.6; p[i*3+2]=Math.sin(b)*Math.sin(a)*r*0.4; const k=0.25+frnd()*0.35; cc[i*3]=col.r*k; cc[i*3+1]=col.g*k; cc[i*3+2]=col.b*k; } return {p,c:cc}; }
const CGOLD=new THREE.Color(1.0,0.66,0.22), CCYAN=new THREE.Color(0.38,0.86,1.0), CCLAY=new THREE.Color(1.0,0.55,0.3), CGRASS=new THREE.Color(0.5,1.0,0.55), CWHITE=new THREE.Color(1,1,1);
const EN=LANG==='en';
MSH.void=burstShape(40,CCYAN);
MSH.q=textShape(EN?'How can the ground change a match?':'地面，凭什么能左右一场比赛？',SERIF,EN?44:40,CWHITE);
MSH.idx=textShape(EN?'SERVE INDEX':'发球指数',SERIF,EN?30:24,CGOLD);
MSH.mu9=textShape('μ  0.9',NUMF,16,CCLAY);
MSH.mu56=textShape('μ  0.5–0.6',NUMF,22,CGRASS);
MSH.four=textShape(EN?'Four courts, four games':'四块场地，四种比赛',SERIF,EN?40:36,CWHITE);
MSH.end=textShape(EN?'The ground is a player too':'球场的地面，也是比赛的一方',SERIF,EN?44:38,CGOLD);
const ioe=x=>{x=cl(x); return x<0.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;};
// keys：[[时刻,形状,过渡秒数,旋涡],...]；mz 为离镜头的距离，my 为上下偏移
function setMorph(keys,t,{op=1,mz=60,my=0,mx=0}={}){ MORPH.visible=op>0.001; if(!MORPH.visible) return; MG.position.set(mx,my,-mz);
  let k=0; while(k+1<keys.length && t>=keys[k+1][0]) k++; const A=MSH[keys[k][1]], nx=keys[k+1];
  const P=MORPH.geometry.attributes.position.array, C=MORPH.geometry.attributes.color.array, AL=MORPH.geometry.attributes.alpha.array;
  for(let i=0;i<NM;i++){ let x=A.p[i*3],y=A.p[i*3+1],z=A.p[i*3+2], r=A.c[i*3],g=A.c[i*3+1],b=A.c[i*3+2];
    if(nx && t>=nx[0]){ const B=MSH[nx[1]], span=Math.max(nx[2],0.001), dl=mDel[i]*span*0.45, u=ioe((t-nx[0]-dl)/(span*0.55)), sw=Math.sin(u*Math.PI)*(nx[3]||0);
      x+=(B.p[i*3]-x)*u; y+=(B.p[i*3+1]-y)*u; z+=(B.p[i*3+2]-z)*u; if(sw){ const a=mPh[i]+u*5; x+=Math.cos(a)*sw*5; y+=Math.sin(a*1.3)*sw*3; z+=Math.sin(a)*sw*6; }
      r+=(B.c[i*3]-r)*u; g+=(B.c[i*3+1]-g)*u; b+=(B.c[i*3+2]-b)*u; }
    const br=0.03*Math.sin(t*2.1+mPh[i]*3); P[i*3]=x+br; P[i*3+1]=y+br*0.7; P[i*3+2]=z; C[i*3]=r; C[i*3+1]=g; C[i*3+2]=b; AL[i]=op; }
  MORPH.material.uniforms.uSize.value=0.22*mz/60; cdone(MORPH); }

// --- 场馆「扫描建起」：裁剪面从地面升到楼顶，切口处一圈光环＋粒子
[...venues.map(v=>v.g),lmRG,lmAO,lmUSO].forEach(g=>g.traverse(o=>{ if(o.material){ (Array.isArray(o.material)?o.material:[o.material]).forEach(m=>{ m.clippingPlanes=[CLIP]; }); } }));
const SCAN={}; venues.forEach(v=>{ const g=new THREE.Group(); v.g.add(g); g.userData.core=0;
  const out=shapePts(v.shape,v.rx*1.04,v.rz*1.04); const pos=[]; for(let i=0;i<out.length-1;i++){ const a=out[i],b=out[i+1]; pos.push(a[0],0,a[1],b[0],0,b[1],b[0],0.9,b[1],a[0],0,a[1],b[0],0.9,b[1],a[0],0.9,a[1]); }
  const geo=new THREE.BufferGeometry(); geo.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); const ring=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({color:v.glow,transparent:true,opacity:0.9,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide})); g.add(ring);
  const n=2600, P=cloud(n,0.55,6,g,0.5), sd=[]; for(let j=0;j<n;j++){ const q=out[(frnd()*(out.length-1))|0], k=0.55+frnd()*0.5; sd.push([q[0]*k,q[1]*k,frnd()*4,frnd()]); }
  SCAN[v.k]={g,ring,P,sd,col:new THREE.Color(v.glow)}; g.visible=false; });
function scanFX(k,y,a=1){ for(const kk in SCAN) SCAN[kk].g.visible=false; if(!k) return; const S=SCAN[k]; S.g.visible=true; S.ring.position.y=y; S.ring.material.opacity=0.9*a;
  for(let j=0;j<S.sd.length;j++){ const d=S.sd[j]; cset(S.P,j,d[0],y+d[2]*d[3]*1.5,d[1],S.col.r,S.col.g,S.col.b,a*(1-d[3])*0.9); } cdone(S.P); }
const VTOP={RG:48,WIM:40,AO:52,USO:72}; // 美网膜顶鼓包最高到约 65 m：扫描面到 62 就停会把鼓包削出四个洞（2026-11-02 俯拍才看出来）
function buildVenue(k,te){ const q=sm(te/2.2); const y=lerp(-2,VTOP[k],q); if(q<1){ CLIP.constant=y; scanFX(k,y,1); } else { CLIP.constant=1e5; scanFX(k,VTOP[k],Math.max(0,1-(te-2.2)/0.5)); } }
// --- 慢镜：滑动时接触点向后喷出摩擦火花，接触点发热（橙）→ 咬住（青）
const SLO_P=cloud(1600,0.12,12,sloG,0.3), SLO_SD=[]; for(let j=0;j<1600;j++) SLO_SD.push([frnd(),3+frnd()*7,0.6+frnd()*2.8,(frnd()-0.5)*3.2,frnd()]);
const SLO_HEAT=glowSprite(0xffa040,3,0,sloG);
function setSloFX(q){ if(q<0.25||q>=0.72){ chide(SLO_P); SLO_HEAT.material.opacity=0; return; } const x=bigBall.position.x, grip=q>=0.5, k=grip?1-(q-0.5)/0.22:1;
  for(let j=0;j<SLO_SD.length;j++){ const d=SLO_SD[j], age=((q*14+d[0])%1)*0.35; cset(SLO_P,j,x-d[1]*age*(grip?0.4:1),Math.max(0.02,d[2]*age-4.9*age*age),d[3]*age*3,grip?0.7:1.0,grip?0.95:0.8,grip?1.0:0.45,(1-age/0.35)*k); } cdone(SLO_P);
  SLO_HEAT.position.set(x,0.15,0); SLO_HEAT.material.color.set(grip?0x5fe0ff:0xffa040); SLO_HEAT.material.opacity=0.8*k; const sc=2.2+Math.sin(q*60)*0.3; SLO_HEAT.scale.set(sc,sc,1); }
// --- 指数光柱：柱子里粒子往上涌，柱顶一团光，柱脚一圈冲击波
const PIL_FX={}; ['RG','WIM','AO','USO'].forEach(k=>{ const col=new THREE.Color({RG:0xff8a4a,WIM:0x7dff8a,AO:0x5fc2ff,USO:0x6f8cff}[k]); const P=cloud(700,0.5,8,scene,0.4), sd=[]; for(let j=0;j<700;j++) sd.push([(frnd()-0.5)*5,(frnd()-0.5)*5,frnd(),0.3+frnd()*0.7]);
  PIL_FX[k]={P,sd,col,cap:glowSprite(col,10,0),ring:flatRing(col,scene)}; });
function setPilFX(p,hi,t=0){ ['RG','WIM','AO','USO'].forEach(k=>{ const F=PIL_FX[k], m=pillars[k]; const on=p>0.02&&m.visible; if(!on){ chide(F.P); F.cap.material.opacity=0; F.ring.material.opacity=0; return; }
  const h=m.scale.y, x=m.position.x, z=m.position.z, dim=(hi&&!hi.includes(k))?0.25:1;
  for(let j=0;j<F.sd.length;j++){ const d=F.sd[j], yy=((d[2]+t*0.35*d[3])%1)*h; cset(F.P,j,x+d[0],yy+0.5,z+d[1],0.5+0.5*F.col.r,0.5+0.5*F.col.g,0.5+0.5*F.col.b,dim*0.9*(0.4+0.6*yy/h)); } cdone(F.P);
  F.cap.position.set(x,h+0.8,z); F.cap.material.opacity=0.9*dim; const r=((t*0.8)%1); F.ring.position.set(x,0.6,z); F.ring.scale.set(6+r*16,6+r*16,1); F.ring.material.opacity=(1-r)*0.7*dim; }); }
// --- 逐年柱：同款粒子流（法网逐年 / 澳网逐年）
const BAR_FX={}; [['RG',yrG,ybars,0xff9a5a],['AO',aoG,abars,0x7cc8ff]].forEach(([k,grp,bars,c])=>{ const P=cloud(3600,0.4,8,grp,0.4), sd=[]; for(let j=0;j<3600;j++) sd.push([(frnd()-0.5)*4,(frnd()-0.5)*4,frnd(),0.3+frnd()*0.7,(frnd()*Object.keys(bars).length)|0]);
  const caps={}; Object.keys(bars).forEach(y=>{ caps[y]=glowSprite(c,6,0,grp); }); BAR_FX[k]={P,sd,bars,caps,col:new THREE.Color(c)}; });
function setBarFX(k,t=0,hiY=null){ for(const kk in BAR_FX){ if(kk!==k){ chide(BAR_FX[kk].P); Object.values(BAR_FX[kk].caps).forEach(c=>c.material.opacity=0); } } if(!k) return; const F=BAR_FX[k], ys=Object.keys(F.bars).map(Number);
  for(let j=0;j<F.sd.length;j++){ const d=F.sd[j], y=ys[d[4]], m=F.bars[y], h=m.scale.y, yy=((d[2]+t*0.3*d[3])%1)*h; const hot=hiY&&hiY.includes(y), c=hot?new THREE.Color(m.material.color):F.col;
    cset(F.P,j,m.position.x+d[0],yy,d[1],0.5+0.5*c.r,0.5+0.5*c.g,0.5+0.5*c.b,0.85*(0.3+0.7*yy/Math.max(h,0.01))); } cdone(F.P);
  ys.forEach(y=>{ const m=F.bars[y], cp=F.caps[y]; cp.position.set(m.position.x,m.scale.y+0.4,0); cp.material.color.copy(m.material.color); cp.material.opacity=m.scale.y>0.2?0.9:0; }); }
// --- 片尾：四座场馆之间连起光弧，光点沿弧跑动
const ARC_G=new THREE.Group(); scene.add(ARC_G); const ARCS=[]; { const order=['AO','RG','USO','WIM'], P=k=>V3(POS[k][0]*0.4,0,POS[k][1]*0.4);
  for(let i=0;i<4;i++){ const a=P(order[i]), b=P(order[(i+1)%4]), mid=a.clone().add(b).multiplyScalar(0.5); mid.y=90; const cur=new THREE.QuadraticBezierCurve3(a.clone().setY(30),mid,b.clone().setY(30));
    const tube=new THREE.Mesh(new THREE.TubeGeometry(cur,80,0.9,8,false),glowMat(0x8fd0ff,0.5)); ARC_G.add(tube); const dot=glowSprite(0xffffff,22,0,ARC_G); ARCS.push({cur,tube,dot}); } }
function setArcs(q,t=0){ ARC_G.visible=q>0; ARCS.forEach((A,i)=>{ A.tube.material.opacity=0.45*q; A.dot.material.opacity=q; A.dot.position.copy(A.cur.getPoint(((t*0.25)+i*0.25)%1)); }); }

// ---------- 后期 ----------
const composer=new EffectComposer(renderer,new THREE.WebGLRenderTarget(W,H,{samples:4,type:THREE.HalfFloatType})); composer.addPass(new RenderPass(scene,camera));
const bloom=new UnrealBloomPass(new THREE.Vector2(W/2,H/2),0.4,0.4,0.9); composer.addPass(bloom);
const finalPass=new ShaderPass({uniforms:{tDiffuse:{value:null},uT:{value:0},uFlash:{value:0},uCA:{value:0.0015},uZoom:{value:0},uShake:{value:0},uGlitch:{value:0},uFreeze:{value:0},uTilt:{value:0}},
  vertexShader:`varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader:`uniform sampler2D tDiffuse; uniform float uT,uFlash,uCA,uZoom,uShake,uGlitch,uFreeze,uTilt; varying vec2 vUv;
   float h(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453); }
   void main(){ vec2 uv=vUv; uv+=vec2(sin(uT*91.)*0.004,cos(uT*77.)*0.004)*uShake;
     if(uGlitch>0.){ float band=floor(uv.y*28.+floor(uT*24.)); float o=(h(vec2(band,floor(uT*30.)))-0.5)*0.06*uGlitch*step(0.55,h(vec2(band*1.7,floor(uT*30.)))); uv.x+=o; }
     vec2 c=uv-0.5; vec3 col=vec3(0.);
     if(uZoom>0.){ for(int k=0;k<10;k++){ float s=1.0-uZoom*0.05*float(k); col+=texture2D(tDiffuse,0.5+c*s).rgb; } col/=10.; }
     else { float ca=uCA+uGlitch*0.012+uFreeze*0.004; col=vec3(texture2D(tDiffuse,uv+c*ca).r,texture2D(tDiffuse,uv).g,texture2D(tDiffuse,uv-c*ca).b); }
     if(uTilt>0.){ // 移轴微缩（Lemo-Opuscar「Tilt-Shift」）：中间一条清晰带，上下越远越虚，饱和度提一点
       float r=uTilt*0.014*pow(max(0.,abs(uv.y-0.52)-0.13)/0.39,1.25); if(r>0.0004){ vec3 acc=col; float wsum=1.; for(int i=0;i<16;i++){ float a=float(i)*2.39996; float rr=r*sqrt((float(i)+.5)/16.); vec2 o=vec2(cos(a),sin(a)*1.7778)*rr; acc+=texture2D(tDiffuse,uv+o).rgb; wsum+=1.; } col=acc/wsum; }
       float l=dot(col,vec3(0.3,0.59,0.11)); col=mix(vec3(l),col,1.0+0.28*uTilt); }
     if(uFreeze>0.){ float l=dot(col,vec3(0.3,0.59,0.11)); col=mix(col,vec3(l*0.75,l*0.95,l*1.25),uFreeze*0.45); col*=1.0+uFreeze*0.06*sin(uv.y*1080.*1.2); }
     if(uGlitch>0.){ col.r+=uGlitch*0.08*step(0.92,h(vec2(floor(uv.y*90.),floor(uT*20.)))); }
     float vig=smoothstep(1.05,0.3,length(c*vec2(1.0,0.85))); col*=mix(0.55,1.0,vig);
     col+=(h(uv*vec2(1920.,1080.)+uT)-0.5)*0.025; col=mix(col,vec3(1.),uFlash); gl_FragColor=vec4(col,1.); }`});
composer.addPass(finalPass); composer.addPass(new OutputPass());
// 转场：每段开头 0.45 s 径向推镜模糊＋一下闪白（第 4 集同款）
function setTransition(t){ let z=0,f=0; for(const sc of TL.sections){ const d=t-sc.t0; if(sc.t0>0&&d>=0&&d<0.45){ const k=1-d/0.45; z=k*k*0.9; f=Math.max(0,1-d/0.12)*0.35; } }
  finalPass.uniforms.uZoom.value=z; finalPass.uniforms.uFlash.value=Math.max(f,FX_FLASH); finalPass.uniforms.uT.value=t; finalPass.uniforms.uShake.value=FX_SHAKE; finalPass.uniforms.uGlitch.value=FX_GLITCH; finalPass.uniforms.uFreeze.value=FX_FREEZE; finalPass.uniforms.uTilt.value=FX_TILT; }
let FX_SHAKE=0, FX_GLITCH=0, FX_FREEZE=0, FX_FLASH=0, FX_TILT=0;

// ---------- 镜头 ----------
// t=0 四座全景；t=1..4 逐个场馆外观（含地标）；t=5..8 场地材质特写；t=9 四块场地并排
const VIEW={RG:[120,115,165,0,8,-5],WIM:[90,70,115,0,10,0],AO:[105,48,150,-30,22,-60],USO:[-20,58,290,-40,30,0]};
const LM={RG:lmRG,AO:lmAO,USO:lmUSO};
function only(k){ for(const v of venues) v.g.visible=(k===null||v.k===k); for(const [kk,o] of Object.entries(LM)) o.visible=(k===null||kk===k); }
function previewShot(t){
  for(const v of venues) v.g.children.forEach(c=>c.visible=true); // 每个镜头先复位，避免上一个镜头的隐藏状态带过来
  const rgOpen=t>=9.5&&t<10.5; setRGRoof(rgOpen?1:0);
  if(rgOpen){ only('RG'); const x=POS.RG[0], z=POS.RG[1]; camera.fov=36; camera.updateProjectionMatrix(); camera.position.set(x+95,120,z+150); camera.lookAt(x,0,z-5); return 'RG roof open'; }
  if(t>=8.5){ only(null); for(const v of venues){ v.g.children.forEach(c=>{ if(!c.userData.core) c.visible=false; }); }
    [lmRG,lmAO,lmUSO].forEach(o=>o.visible=false);
    camera.position.set(0,62,58); camera.lookAt(0,0,0); venues.forEach((v,i)=>v.g.position.set((i-1.5)*22,0,0)); return 'lineup'; }
  venues.forEach(v=>v.g.position.set(POS[v.k][0],0,POS[v.k][1]));
  if(t<0.5){ only(null); Object.values(LM).forEach(o=>o.visible=false);
    venues.forEach(v=>v.g.position.set(POS[v.k][0]*0.40,0,POS[v.k][1]*0.40));
    camera.fov=24; camera.updateProjectionMatrix(); camera.position.set(0,640,760); camera.lookAt(0,-10,40); return 'overview'; }
  camera.fov=36; camera.updateProjectionMatrix();
  const i=Math.floor(t-1)%4, v=venues[i], x=v.g.position.x, z=v.g.position.z;
  if(t<4.5){ only(v.k); const c=VIEW[v.k]; camera.position.set(x+c[0],c[1],z+c[2]); camera.lookAt(x+c[3],c[4],z+c[5]); return 'venue '+v.k; }
  only(v.k); camera.position.set(x+7,4.2,z-L-5.5); camera.lookAt(x+1,0,z-L+3.5); return 'surface '+v.k;
}

// ================= 正式时间轴（r3d/shots.js 由 plan.py 按配音生成） =================
const cl=(x,a=0,b=1)=>Math.max(a,Math.min(b,x)), sm=x=>{x=cl(x);return x*x*(3-2*x);}, lerp=(a,b,k)=>a+(b-a)*k;
function camLook(px,py,pz,tx,ty,tz,fov=36){ camera.fov=fov; camera.updateProjectionMatrix(); camera.position.set(px,py,pz); camera.lookAt(tx,ty,tz); camera.updateMatrixWorld(true); }
function orbit(cx,cz,r,h,ang,ty=10,fov=36){ camLook(cx+Math.cos(ang)*r,h,cz+Math.sin(ang)*r,cx,ty,cz,fov); }
function resetWorld(){ for(const v of venues){ v.g.visible=true; v.g.position.set(POS[v.k][0],0,POS[v.k][1]); v.g.children.forEach(c=>c.visible=true); }
  for(const o of Object.values(LM)) o.visible=true; Object.values(pillars).forEach(m=>m.visible=false); ref1.visible=false; setRGRoof(1); setLanes(-5,[0,0,0]); setImpacts(-1,[0,0,0]); CLIP.constant=1e5; setBowl(null); scanFX(null); MORPH.visible=false; hideStacks(); FX_SHAKE=FX_GLITCH=FX_FREEZE=FX_FLASH=FX_TILT=0; setSnow(-1); setGlobe(-1,0); setSloFX(-1); setPilFX(0); setBarFX(null); setArcs(0); }
function lineupWorld(){ only(null); for(const v of venues) v.g.children.forEach(c=>{ if(!c.userData.core) c.visible=false; }); Object.values(LM).forEach(o=>o.visible=false);
  venues.forEach((v,i)=>v.g.position.set((['AO','RG','WIM','USO'].indexOf(v.k)-1.5)*22,0,0)); } // 大满贯顺序，澳网在最左
function at(sec,f){ return sec.lines[f]; }
function hideWorld(){ for(const v of venues) v.g.visible=false; Object.values(LM).forEach(o=>o.visible=false); }
function shotTL(t){
  resetWorld(); const sec=TL.sections.find(s=>t>=s.t0&&t<s.t1)||TL.sections[TL.sections.length-1]; const u=t-sec.t0, D=sec.t1-sec.t0, k=sec.kind;
  const LX=LAB.x, LZ=LAB.z;
  const LABS={lanes_all:labG,lane_RG:labG,lane_WIM:labG,slow:sloG,years:yrG,acryl:acrG,ao_years:aoG}; [labG,sloG,yrG,acrG,aoG].forEach(g=>g.visible=(LABS[k]===g));
  setDust(-1); if(['lanes_all','lane_RG','lane_WIM','slow','years','acryl','ao_years'].includes(k)) hideWorld();
  if(k==='lanes_all'){ // 三条泳道一起：同一颗球砸向三种地面（0.6 倍慢放，循环）
    const per=4.0, H1=at(sec,'h1')-sec.t0, H2=at(sec,'h2')-sec.t0, BT=u>=H1&&u<H2-0.2; let tau=cl(ramp((u%per)-1.0),-0.9,1.3); if(BT) tau=0.13; /* 子弹时间：h1 那句话时间冻结在落地后 0.13 s，镜头绕三个落点转半圈 */
    setBowl(LAB); if(COVER) camLook(LX+3.5,27,LZ+25,LX+3.5,0,LZ-4,40); /* 所有者 2026-11-02：球场线往右扩，右边别空 */ else if(BT){ const q=sm((u-H1)/(H2-0.2-H1)); const a=lerp(-1.25,1.25,q); camLook(LX+0.6+Math.sin(a)*15,lerp(6,9,Math.sin(q*Math.PI)),LZ+Math.cos(a)*15,LX+0.6,0.4,LZ,40); } else if(u<per){ const q=sm(u/per); camLook(LX+34-6*q,lerp(7,5,q),LZ+lerp(10,6,q),LX-14,0.6,LZ,36); /* 所有者：先从远处打过来（从接球一端看球飞来），再切近景 */ } else camLook(LX+3+lerp(-0.6,0.6,sm(u/D)),lerp(21,19,sm(u/D)),LZ+lerp(21,19,sm(u/D)),LX+3,0,LZ-0.8,40); /* 所有者：场地朝屏幕倾斜（正前方俯看），不是左右斜 */ setLanes(tau,[1,1,1]); setDust(-1); setFX(tau,[1,1,1],u); setImpacts(tau,[1,1,1]); if(BT){ FX_FREEZE=Math.min(1,(u-H1)/0.25,(H2-0.2-u)/0.25); } else FX_SHAKE=(tau>=0&&tau<0.18)?(1-tau/0.18)*0.9:0; if(u>=H2&&!COVER){ labG.visible=false; setBowl(null); FX_SHAKE=0; const q0=cl((u-H2-0.15)/(D-H2-1.0)), q=q0<0.18?q0/0.18*0.25:(q0<0.68?0.25+(q0-0.18)/0.5*0.4:0.65+(q0-0.68)/0.32*0.35); setGlobe(q,t); { globeCam(GFLY,0.04+0.26*cl((GFLY-68)/110)); const low=cl((GFLY-68)/70); GARC.forEach((A,i)=>{ if(i<GIDX) A.m.material.opacity=0.85*low*low; }); } /* 法网→温网那一段多给时间 */; /* 讲到「一年四个大满贯」：拉到地球，按赛季顺序点亮四站 */ }
    setMorph([[0,'void',0],[H2+0.1,'four',1.1,0.5],[D-0.9,'void',0.8,0.4]],u,{mz:60,my:15.5}); return k; }
  if(k==='lane_RG'||k==='lane_WIM'){ // 画板式拆解（Lemo-Opuscar「Sports Telestrator」的剪辑语法）：先看一遍 → 倒带 → 慢放 → 定格画线 → 再慢放 → 定格量角度
    const RG=k==='lane_RG', show=RG?[1,0,0]:[1,1,0], ln=RG?LANES[0]:LANES[1]; setBowl(LAB); const P=telePlan(RG,sec,u,D); let tau=P.tau;
    const near=V3(LX+3.6,0.5,LZ+ln.z), far=()=>camLook(LX+30,5,LZ+ln.z+4,LX-12,0.6,LZ+ln.z,34);
    if(P.cam==='far') far(); else if(P.fid===2||P.fid===3||P.cam==='side'){ const w=P.side!==undefined?P.side:1; const sz=RG?-1:1; camLook(LX+lerp(3,4,w),lerp(10,1.1,w),LZ+ln.z+lerp(11,10*sz,w),LX+lerp(3.5,4,w),lerp(0.3,1.0,w),LZ+ln.z,40); /* 红土从外侧（看台那边）看，前景不被草挡住 */ /* 量出射角要从侧面看（换机位） */ } else { const pz=P.punch||0; camLook(LX+3+lerp(0,-1.0,pz),lerp(10,6.2,pz),LZ+ln.z+lerp(11,7,pz),LX+lerp(3.5,1.2,pz),0.3,LZ+ln.z,42); }
    setLanes(tau,show); setDust(-1); setFX(tau,show,u); setImpacts(tau,show);
    FX_SHAKE=(P.mode==='live'&&tau>=0&&tau<0.18)?(1-tau/0.18)*0.7:(P.mode==='rewind'?0.5:0); FX_FLASH=P.flash||0; FX_FREEZE=P.mode==='freeze'?0.35:0;
    val('tele_mode',P.mode); val('tele_k',P.k||0); val('tele_freeze',P.fid||0);
    const L0=labG.localToWorld(V3(0,0,ln.z)); proj('tele_hit',L0); proj('tele_rx',labG.localToWorld(V3(1.4,0,ln.z))); proj('tele_rz',labG.localToWorld(V3(0,0,ln.z+1.4)));
    proj('tele_gx',labG.localToWorld(V3(6,0,ln.z))); proj('tele_out',labG.localToWorld(lanePos(ln,0.5).sub(V3(0,0.2,0))));
    if(!RG){ const R=LANES[0]; const pts=[]; for(let q=0;q<=8;q++) pts.push(labG.localToWorld(V3(R.vx2*0.06*q,0.0+R.vy2*0.06*q-0.5*G*(0.06*q)**2,ln.z))); pts.forEach((w,q)=>proj('tele_ghost'+q,w)); }
    if(RG) setMorph([[0,'void',0],[0.3,'mu9',1.0,0.4],[4.2,'void',0.8,0.4]],u,{mz:60,mx:13,my:9}); else setMorph([[0,'void',0],[0.3,'mu56',1.0,0.4],[1.8,'void',0.8,0.4]],u,{mz:60,mx:11,my:9});
    return k; }
  if(k==='venues'){ // 法网（顶棚打开）→ 温网 → 澳网 → 美网 → 并排
    const t1=at(sec,'s1')-sec.t0, t2=at(sec,'s2')-sec.t0, t3=at(sec,'s3')-sec.t0, t25=(t2+t3)/2;
    if(u<t1){ only('RG'); const q=u/t1; buildVenue('RG',u); FX_TILT=1; setBowl(V3(POS.RG[0],0,POS.RG[1]),1.5); setRGRoof(sm((q-0.25)/0.6)); const P=POS.RG; orbit(P[0],P[1],105-20*q,265-15*q,2.95-0.45*q,0); return 'v_RG'; /* 从侧面看，收拢的顶棚落在画面左侧（同航拍机位） */ }
    if(u<t2){ only('WIM'); const q=(u-t1)/(t2-t1), P=POS.WIM; buildVenue('WIM',u-t1); FX_TILT=1; setBowl(V3(P[0],0,P[1]),1.5); orbit(P[0],P[1],100-15*q,290,0.7+0.6*q,0); return 'v_WIM'; }
    if(u<t25){ only('AO'); const q=(u-t2)/(t25-t2), P=POS.AO; buildVenue('AO',u-t2); FX_TILT=1; setBowl(V3(P[0],0,P[1]),1.5); orbit(P[0],P[1],95,265,1.0+0.4*q,0); return 'v_AO'; }
    if(u<t3){ only('USO'); const q=(u-t25)/(t3-t25), P=POS.USO; buildVenue('USO',u-t25); FX_TILT=1; setBowl(V3(P[0],0,P[1]),1.6); orbit(P[0],P[1],115,320,1.45+0.35*q,0); return 'v_USO'; }
    lineupWorld(); setBowl(V3(0,0,0),1); const q=sm((u-t3)/2.5); camLook(0,lerp(110,62,q),lerp(120,58,q),0,0,0,34); return 'lineup'; }
  if(k==='lineup'){ lineupWorld(); setBowl(V3(0,0,0),1); camLook(Math.sin(u*0.2)*6,62-u*2,58-u*2,0,0,0,34); setMorph([[0,'void',0],[0.05,'q',1.2,0.6],[D-0.9,'void',0.9,0.5]],u,{mz:60,my:12}); return k; }
  if(k==='slow'){ // 慢镜：p0 来球 → p1 滑 → p2 咬住 → p3 弹出；p4 起再放一遍，停在咬住处展示两支箭头
    const T=f=>at(sec,f)-sec.t0, k1=T('p1'), k2=T('p2'), k3=T('p3'), k4=T('p4');
    let q; if(u<k1) q=0.25*u/k1; else if(u<k2) q=0.25+0.25*(u-k1)/(k2-k1); else if(u<k3) q=0.5+0.22*(u-k2)/(k3-k2); else if(u<k4) q=0.72+0.28*(u-k3)/(k4-k3); else q=Math.min(0.66,0.66*(u-k4)/3.0);
    setBowl(SLO); const SX=SLO.x, SZ=SLO.z; const ph=setSlow(q); const bx=bigBall.position.x; if(u>=k2&&u<k3){ const w=sm((u-k2)/(k3-k2)); const a=lerp(0.0,1.9,w); camLook(SX+bx+Math.sin(a)*9,lerp(3.2,2.4,Math.sin(w*Math.PI)),SZ+Math.cos(a)*9,SX+bx,0.9,SZ,32); FX_FREEZE=Math.min(1,(u-k2)/0.3,(k3-u)/0.3)*0.6; } else camLook(SX+lerp(-1.5,2.5,sm(u/D)),4.6,SZ+13,SX+1.2,0.9,SZ-1,32); setSloFX(q); proj('slo_reticle',sloG.localToWorld(V3(bx,0.05,0))); return 'slow'; }
  if(k==='pillars'||k==='pillars_hi'){ lineupWorld(); setBowl(V3(0,0,0),1); const g=k==='pillars'?sm((u-(at(sec,'d2')-sec.t0)+1.0)/3.5):1; 
    camLook(0,lerp(70,58,sm(u/D)),lerp(110,96,sm(u/D)),0,16,0,36); setPillars(g,k==='pillars_hi'?['WIM','AO']:null); Object.values(pillars).forEach(m=>m.visible=false); setPilFX(0); setStacks(g,k==='pillars_hi'?['WIM','AO']:null,u); ref1.position.y=0.6+1/PLATE*PH; if(g>0.98) proj('pil_ref',V3(-50,0.6+1/PLATE*PH,0)); if(k==='pillars') setMorph([[0,'void',0],[0.3,'idx',1.1,0.5],[5.4,'void',0.9,0.5]],u,{mz:60,my:9}); return k; }
  if(k==='wim'){ only('WIM'); FX_TILT=1; const P=POS.WIM; setBowl(V3(P[0],0,P[1]),1.5); { const g=u-(at(sec,'r3')-sec.t0); FX_GLITCH=(g>=0&&g<0.5)?(1-g/0.5)*0.7:0; } orbit(P[0],P[1],150,60,2.2+0.5*u/D,6); return k; }
  if(k==='years'){ const T=f=>at(sec,f)-sec.t0, drop=sm((u-T('r8'))/1.2); const Y=yrG.position; setBowl(Y);
    camLook(Y.x+lerp(-8,6,sm(u/D)),30,Y.z+105,Y.x,11,Y.z,36); setYears(sm(u/2.0),drop); setBarFX('RG',u,drop>0.5?[2020]:null); setSnow(u-T('r7'),Y); { const g=u-T('r8'); FX_GLITCH=(g>=0&&g<0.6)?(1-g/0.6):0; FX_SHAKE=(g>=0&&g<0.4)?(1-g/0.4)*0.6:0; } return k; }
  if(k==='acryl'){ const T=f=>at(sec,f)-sec.t0, q=sm((u-T('k3'))/4.5); const A=ACR; setBowl(ACR);
    camLook(A.x+lerp(-4,4,sm(u/D)),lerp(11,8.5,sm(u/D)),A.z+lerp(33,29,sm(u/D)),A.x,0.6,A.z,40); setAcryl(q); return k; }
  if(k==='ao_years'){ const T=f=>at(sec,f)-sec.t0; const Y=aoG.position; setBowl(Y); camLook(Y.x+lerp(-8,6,sm(u/D)),28,Y.z+100,Y.x,10,Y.z,36); setAOYears(sm(u/2.0),u>=T('k6')-0.2); setBarFX('AO',u,u>=T('k6')-0.2?[2020,2021]:null); return k; }
  if(k==='outro'){ only(null); setBowl(V3(0,0,0),3.4); Object.values(LM).forEach(o=>o.visible=false); venues.forEach(v=>v.g.position.set(POS[v.k][0]*0.40,0,POS[v.k][1]*0.40));
    const q=sm(u/D); camLook(0,lerp(420,640,q),lerp(520,760,q),0,-10,lerp(25,40,q),lerp(30,24,q)); setArcs(sm(u/2.0),u); { const e1=at(sec,'e1')-sec.t0, e2=at(sec,'e2')-sec.t0; setMorph([[0,'void',0],[e1-0.3,'end',1.2,0.6],[e2-0.5,'void',0.9,0.5]],u,{mz:60,my:2}); } { const e2=at(sec,'e2')-sec.t0; if(u>=e2-0.3){ only(null); for(const v of venues) v.g.visible=false; setArcs(0); setBowl(null); const w=sm((u-e2+0.3)/(D-e2)); setGlobe(lerp(0.85,1.06,sm((u-e2+0.3)/2.0)),t,{active:2,loop:true}); globeCam(lerp(135,170,w),0.45); } } return k; }
  return k; }
const PREVIEW=Q.get('preview')==='1', COVER=Q.get('cover')==='1'; // 封面用：镜头再退远一点，三条泳道都装进画面下半部
window.renderAt=(t)=>{ for(const k in anchors) delete anchors[k]; allClouds.forEach(c=>c.material.uniforms.uT.value=t); const s=PREVIEW?previewShot(t):shotTL(t); setTransition(t); setMotes(t,MOTE_SCALE[s]||1); motes.visible=!globeG.visible; composer.render(); return JSON.stringify(Object.assign({_shot:s},anchors)); };
EARTH_READY.then(()=>{ window.READY=true; });
