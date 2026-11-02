// 四大满贯中心球场：预览场景（场地材质与配色）
// 球场尺寸按 ITF 标准；场馆为示意（按真实平面形状风格化，不按座位数精确建模）
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { TL } from './shots.js';

const Q=new URLSearchParams(location.search);
const W=+(Q.get('w')||1920), H=+(Q.get('h')||1080);
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(1); renderer.setSize(W,H);
renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.05;
renderer.outputColorSpace=THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);
const scene=new THREE.Scene(); scene.background=new THREE.Color(0x02040a);
scene.fog=new THREE.FogExp2(0x02040a,0.0005);
const camera=new THREE.PerspectiveCamera(36,W/H,0.5,6000);

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
    else { const p=shape==='box'?40:(shape==='rr'?3.4:9); pts.push([Math.sign(c)*Math.pow(Math.abs(c),2/p)*rx,Math.sign(s)*Math.pow(Math.abs(s),2/p)*rz]); } }
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
    g.fillStyle='#8f989f'; g.fillRect(0,0,w,h); // 航拍：浅灰色，一层层白色楼板挑出来，楼板之间是灰玻璃
    for(let r=0;r<5;r++){ const y=r*h/5; g.fillStyle='#f1f2f2'; g.fillRect(0,y+4,w,12); g.fillStyle='#d6dadd'; g.fillRect(0,y+16,w,4); g.fillStyle='rgba(70,82,92,0.55)'; g.fillRect(0,y+22,w,h/5-24); }
    for(let x=0;x<w;x+=32){ g.fillStyle='rgba(230,235,238,0.55)'; g.fillRect(x,0,2,h); } }),
  WIM: canvasTex(1024,256,(g,w,h)=>{ // 中心球场：外墙爬满绿植（2017 年外观照片），露出一格格窗
    g.fillStyle='#4f6a2a'; g.fillRect(0,0,w,h); noise(g,w,h,60000,['#6e8a2e','#8a9a35','#4d6b27','#a3a347','#3c5a22','#7b5a2a'],3.5);
    g.fillStyle='rgba(30,45,40,0.85)'; for(let x=14;x<w;x+=56) for(const y of[0.2,0.5]) g.fillRect(x,h*y,34,h*0.18); }),
  AO: canvasTex(1024,256,(g,w,h)=>{ // 罗德·拉沃尔上层：白色横向分层（航拍与 2013/2020 外观照片）
    g.fillStyle='#e9ebe8'; g.fillRect(0,0,w,h); for(let r=0;r<4;r++){ const y=h*(0.12+r*0.24); g.fillStyle='#b8bfc4'; g.fillRect(0,y,w,5); g.fillStyle='rgba(40,60,80,0.45)'; g.fillRect(0,y+8,w,h*0.07); }
    for(let x=0;x<w;x+=64){ g.fillStyle='rgba(150,160,168,0.6)'; g.fillRect(x,0,3,h); } }),
  USO: canvasTex(1024,256,(g,w,h)=>{ // 阿瑟·阿什：砖红色基座
    g.fillStyle='#8a3b2c'; g.fillRect(0,0,w,h); noise(g,w,h,20000,['#7a3326','#9a4434','#843828'],3);
    g.fillStyle='#5d241b'; for(let x=10;x<w;x+=90) g.fillRect(x,h*0.15,18,h*0.75); g.fillStyle='#c9c9c4'; g.fillRect(0,0,w,8); }),
};
for(const t of Object.values(FACADE)){ t.wrapS=THREE.RepeatWrapping; t.repeat.set(5,1); }

// seat：看台座椅颜色（照片：法网灰、温网深绿、澳网蓝、美网蓝）
const VENUES=[
  {k:'RG', shape:'box',  rx:54.5,rz:54.5,H:30, glow:0xffa070, seat:0x9aa0a6},
  {k:'WIM',shape:'chamf',rx:63.5,rz:55,H:22, glow:0x8dffa0, seat:0x1f4a2c},
  {k:'AO', shape:'rr',rx:55.5,rz:63,H:30, glow:0x6cc0ff, seat:0x1f4f9a},
  {k:'USO',shape:'round',rx:74,rz:74,H:28, glow:0x86b0ff, seat:0x22427e},
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
    for(const side of[-1,1]){ const p=new THREE.Mesh(new THREE.PlaneGeometry(W2*2,w*0.5/Math.cos(tilt)),fabric());
      p.rotation.x=-Math.PI/2+side*tilt; p.position.set(0,1.2,side*w*0.25); wg.add(p); }
    beam(wg,V3(-W2,1.2+w*0.25*Math.tan(tilt),0),V3(W2,1.2+w*0.25*Math.tan(tilt),0),0.3,steel);
    RGW.push({g:wg, zc:-L2+w*(i+0.5), zo:-L2+w*0.5+i*w*0.22, yo:(n-1-i)*0.55, y0}); grp.add(wg); } // 航拍（dupleix0 2024）：打开后 11 片翼收成一大片白色肋板，盖满北看台、约占进深三分之一，朝北一侧更高
  const fas=new THREE.MeshStandardMaterial({color:0xc9cfd4,roughness:0.45,metalness:0.4}), fh=2.6;
  for(const [sx,sz,lx,lz] of [[0,-L2,W2*2+0.6,0.6],[0,L2,W2*2+0.6,0.6],[-W2,0,0.6,L2*2+0.6],[W2,0,0.6,L2*2+0.6]]){
    const m=new THREE.Mesh(new THREE.BoxGeometry(lx,fh,lz),fas); m.position.set(sx,y0+0.9,sz); grp.add(m); }
  setRGRoof(0);
}
// 打开时从南往北依次收拢（最南的一片最先动）
function setRGRoof(p){ const n=RGW.length; RGW.forEach((r,i)=>{ const k=Math.max(0,Math.min(1,(p*1.6-(n-1-i)/(n-1)*0.6))); const e=k*k*(3-2*k);
  r.g.position.set(0,r.y0+r.yo*e,r.zc+(r.zo-r.zc)*e); }); }
function roofWIM(v,grp){ // 照片：顶棚打开时，白色拱形桁架分两束收在南北两端
  const out=shapePts(v.shape,v.rx,v.rz);
  band(grp,scl(out,0.70),scl(out,1.05),v.H+5,v.H+0.6,new THREE.MeshStandardMaterial({color:0x34553e,roughness:0.7,side:THREE.DoubleSide}));
  loop(grp,scl(out,1.05),v.H+0.65,0xcfd8cf,0.9);
  // 拱桁架收在南北两端的看台上方；跨度取该处建筑的实际宽度，两端落在坡屋面外缘
  for(const end of[-1,1]) for(let i=0;i<4;i++){ const z=end*(v.rz*0.66-i*3.0), hw=(v.rx-Math.max(0,Math.abs(z)-v.rz*0.76))*0.95, /* 切角处按 45° 收窄 */ hh=13.5-i*0.5, yb=v.H+2.0; // 拱要整根架在坡屋面之上：下弦在屋面内沿（0.70R、高 H+5）处也要高出屋面，脚落在外沿屋面上
    const top=[],bot=[]; for(let j=0;j<=24;j++){ const u=j/24*2-1; top.push(V3(u*hw,yb+(1-u*u)*hh,z)); bot.push(V3(u*hw*0.97,yb+(1-u*u)*(hh-2.8),z)); }
    grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(top),48,0.55,6,false),steel));
    grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(bot),48,0.4,6,false),steel));
    for(let j=1;j<24;j++) beam(grp,j%2?bot[j]:top[j],j%2?top[j+1]:bot[j+1],0.18,steel);
    for(const sx of[-1,1]){ const f=top[sx<0?0:24]; const pad=new THREE.Mesh(new THREE.BoxGeometry(2.2,1.2,2.2),steel); pad.position.set(f.x,yb-0.4,z); grp.add(pad); }
    if(i<3){ const geo=new THREE.BufferGeometry(), pos=[], dz=-end*3.0; for(let j=0;j<24;j++){ const a=top[j],b=top[j+1]; pos.push(a.x,a.y,a.z, b.x,b.y,b.z, b.x,b.y-0.2,b.z+dz, a.x,a.y,a.z, b.x,b.y-0.2,b.z+dz, a.x,a.y-0.2,a.z+dz); }
      geo.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); geo.computeVertexNormals(); grp.add(new THREE.Mesh(geo,fabric(0.6))); } }
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
  const out=shapePts('box',R,R).map(p=>[p[0],p[1]]), sq=shapePts('round',1,1);
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
LANES.forEach(ln=>{ const t=SURF[ln.k].clone(); t.needsUpdate=true; t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(2.2,0.3);
  const m=new THREE.Mesh(new THREE.PlaneGeometry(60,6),new THREE.MeshStandardMaterial({map:t,roughness:0.8})); m.rotation.x=-Math.PI/2; m.position.set(10,0,ln.z); labG.add(m);
  ln.ball=new THREE.Mesh(new THREE.SphereGeometry(0.34,24,16),new THREE.MeshStandardMaterial({color:0xd8f040,emissive:0x7a8a18,roughness:0.6})); labG.add(ln.ball);
  ln.trail=new THREE.Mesh(new THREE.BufferGeometry(),glowMat(ln.col,0.95)); labG.add(ln.trail);
  ln.ring=new THREE.Mesh(new THREE.RingGeometry(0.3,0.5,32),glowMat(ln.col,0)); ln.ring.rotation.x=-Math.PI/2; ln.ring.position.set(0,0.03,ln.z); labG.add(ln.ring); });
// 小球在 τ 秒的位置（τ<0 来球，τ≥0 弹出），落点在 x=0
function lanePos(ln,tau){ if(tau<0) return V3(ln.vx*tau,0.22+(-ln.vy*tau-0.5*G*tau*tau),ln.z);
  return V3(ln.vx2*tau,0.22+ln.vy2*tau-0.5*G*tau*tau,ln.z); }
function setLanes(tau,show){ LANES.forEach((ln,i)=>{ ln.ball.visible=ln.trail.visible=!!show[i]; const pts=[]; for(let k=0;k<=60;k++){ const tt=-0.9+(tau+0.9)*k/60; pts.push(lanePos(ln,tt)); }
  ln.trail.geometry.dispose(); ln.trail.geometry=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),80,0.07,6,false); ln.ball.position.copy(lanePos(ln,tau));
  ln.ring.material.opacity=show[i]&&tau>=0?Math.max(0,0.9-tau*1.2):0; const sc=1+Math.max(0,tau)*4; ln.ring.scale.set(sc,sc,sc);
  if(show[i]){ const w=labG.localToWorld(lanePos(ln,Math.min(tau,0.75)).clone()); proj('lane_'+ln.k,w); proj('lane_'+ln.k+'_hit',labG.localToWorld(V3(0,0,ln.z))); } }); }
// --- 落地慢镜：一个大球压在地面上，先滑后咬住；摩擦（金）向后、支持力（青）向上
const SLO=V3(0,0,1600), sloG=new THREE.Group(); sloG.position.copy(SLO); scene.add(sloG);
{ const t=SURF.AO.clone(); t.needsUpdate=true; t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(0.6,0.6);
  const fl=new THREE.Mesh(new THREE.PlaneGeometry(40,24),new THREE.MeshStandardMaterial({map:t,roughness:0.75})); fl.rotation.x=-Math.PI/2; sloG.add(fl); }
const BR=2.0, bigBall=new THREE.Group(); sloG.add(bigBall);
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
  arF.position.set(x,0.25,1.2); setArrow(arF,fr); arN.position.set(x,0.05,-1.2); setArrow(arN,nr);
  patch.position.x=x; patch.material.opacity=(phase==='slide'||phase==='grip')?0.75:0; patch.material.color.set(phase==='grip'?0x5fe0ff:0xffb347);
  proj('slo_ball',sloG.localToWorld(V3(x,y+BR,0))); proj('slo_contact',sloG.localToWorld(V3(x,0,0))); proj('slo_fr',sloG.localToWorld(V3(x-fr-0.4,0.25,1.2))); proj('slo_nr',sloG.localToWorld(V3(x,nr+0.6,-1.2)));
  return phase; }
// --- 指数光柱：立在并排的四块场地上（2015–2026，见 papers/.../data/speed_result.json）
const IDX={RG:0.748,USO:1.02,WIM:1.086,AO:1.119}, pillars={};
for(const k of ['RG','WIM','AO','USO']){ const c={RG:0xff8a4a,WIM:0x7dff8a,AO:0x5fc2ff,USO:0x6f8cff}[k];
  const m=new THREE.Mesh(new THREE.BoxGeometry(6,1,6),glowMat(c,0.55)); const e=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(6,1,6)),lineM(c,1)); m.add(e); m.visible=false; scene.add(m); pillars[k]=m; }
const ref1=new THREE.Mesh(new THREE.PlaneGeometry(96,0.25),glowMat(0xffffff,0.6)); ref1.visible=false; scene.add(ref1);
function setPillars(p,hi){ const SC=26; ['RG','WIM','AO','USO'].forEach((k,i)=>{ const v=venues.find(z=>z.k===k), h=Math.max(0.01,IDX[k]*SC*p), m=pillars[k];
  m.visible=p>0; m.scale.y=h; m.position.set(v.g.position.x,h/2+0.5,v.g.position.z); m.material.opacity=(hi&&!hi.includes(k))?0.15:0.55; m.children[0].material.opacity=(hi&&!hi.includes(k))?0.25:1;
  if(p>0.08) proj('pil_'+k,V3(v.g.position.x,h+3,v.g.position.z)); });
  ref1.visible=p>0.98; ref1.position.set(0,SC*1+0.5,0); ref1.rotation.x=0; if(p>0.98) proj('pil_ref',V3(-50,SC+0.5,0)); }
// --- 法网逐年（2015–2025；2020 在秋天、换了比赛用球）
const RGY={2015:0.755,2016:0.793,2017:0.823,2018:0.818,2019:0.743,2020:0.597,2021:0.842,2022:0.737,2023:0.635,2024:0.715,2025:0.721};
const YRS=Object.keys(RGY).map(Number), yrG=new THREE.Group(); yrG.position.set(0,0,2000); scene.add(yrG); const ybars={};
{ const t=SURF.RG.clone(); t.needsUpdate=true; t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(1.5,0.4);
  const fl=new THREE.Mesh(new THREE.PlaneGeometry(90,30),new THREE.MeshStandardMaterial({map:t,roughness:0.9})); fl.rotation.x=-Math.PI/2; yrG.add(fl); }
YRS.forEach((y,i)=>{ const c=0xff9a5a; const m=new THREE.Mesh(new THREE.BoxGeometry(4.6,1,4.6),glowMat(c,0.6)); m.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(4.6,1,4.6)),lineM(c,1))); m.position.x=(i-5)*7; yrG.add(m); ybars[y]=m; });
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
  layers.forEach(([c,h])=>{ const m=new THREE.Mesh(new THREE.BoxGeometry(30,h,8),new THREE.MeshStandardMaterial({color:c,roughness:0.7})); m.position.y=y+h/2; acrG.add(m); y+=h; });
  acrG.userData.top=y; const top=y, d=new THREE.Object3D();
  const coarse=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.11,0),new THREE.MeshStandardMaterial({color:0xd8cfb8,roughness:0.6,flatShading:true}),900);
  const fine=new THREE.InstancedMesh(new THREE.SphereGeometry(0.045,8,6),new THREE.MeshStandardMaterial({color:0xe6dfcc,roughness:0.5}),2600);
  for(let i=0;i<900;i++){ d.position.set(-14.5+rnd()*13.5,top+0.04,(rnd()-0.5)*7.6); d.rotation.set(rnd()*6,rnd()*6,rnd()*6); d.scale.setScalar(0.7+rnd()*0.7); d.updateMatrix(); coarse.setMatrixAt(i,d.matrix); }
  for(let i=0;i<2600;i++){ d.position.set(1+rnd()*13.5,top+0.02,(rnd()-0.5)*7.6); d.rotation.set(0,0,0); d.scale.setScalar(0.8+rnd()*0.4); d.updateMatrix(); fine.setMatrixAt(i,d.matrix); }
  acrG.add(coarse,fine); const div=new THREE.Mesh(new THREE.PlaneGeometry(0.06,1.2),glowMat(0xffffff,0.7)); div.position.set(0,top+0.6,4); acrG.add(div); }
const fuzzTex=canvasTex(256,128,(g,w,h)=>{ g.fillStyle='#d6ee3c'; g.fillRect(0,0,w,h); noise(g,w,h,9000,['#c3dc2c','#e9f86a','#b5cd24'],2); });
const acrBalls=[-1,1].map(sx=>{ const b=new THREE.Mesh(new THREE.SphereGeometry(1.4,40,28),new THREE.MeshStandardMaterial({map:fuzzTex,roughness:0.95})); acrG.add(b); return b; });
function setAcryl(q){ const top=acrG.userData.top; acrBalls.forEach((b,i)=>{ const slow=i===0; const x0=(i===0?-13:2), dist=slow?7:11.5; const x=x0+dist*Math.min(1,q); b.position.set(x,top+1.4*0.96,0); b.rotation.z=-x/1.4*(slow?1:0.6);
  proj(i===0?'acr_coarse':'acr_fine',acrG.localToWorld(V3(i===0?-7.5:7.5,top+5.2,0))); proj(i===0?'acr_ball0':'acr_ball1',acrG.localToWorld(V3(x,top+2.9,0))); });
  proj('acr_layers',acrG.localToWorld(V3(-15,1.0,4))); }
// --- 澳网逐年（2015–2026；2020 年起 GreenSet）
const AOY={2015:1.124,2016:1.222,2017:1.156,2018:1.074,2019:1.191,2020:1.020,2021:1.189,2022:1.090,2023:1.076,2024:1.094,2025:1.103,2026:1.064};
const AYRS=Object.keys(AOY).map(Number), aoG=new THREE.Group(); aoG.position.set(0,0,2800); scene.add(aoG); const abars={};
{ const t=SURF.AO.clone(); t.needsUpdate=true; t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(1.5,0.4);
  const fl=new THREE.Mesh(new THREE.PlaneGeometry(96,30),new THREE.MeshStandardMaterial({map:t,roughness:0.6})); fl.rotation.x=-Math.PI/2; aoG.add(fl); }
AYRS.forEach((y,i)=>{ const m=new THREE.Mesh(new THREE.BoxGeometry(4.6,1,4.6),glowMat(0x7cc8ff,0.6)); m.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(4.6,1,4.6)),lineM(0x7cc8ff,1))); m.position.x=(i-5.5)*7.2; aoG.add(m); abars[y]=m; });
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
  ln.ghosts=[1,2,3,4,5].map(i=>{ const g=new THREE.Mesh(new THREE.SphereGeometry(0.34,16,10),glowMat(0xe8ff60,0.35/i)); labG.add(g); return g; });
  const n=90, geo=new THREE.BufferGeometry(), pos=new Float32Array(n*3); geo.setAttribute('position',new THREE.BufferAttribute(pos,3));
  ln.spark={pts:new THREE.Points(geo,new THREE.PointsMaterial({color:ln.col,size:0.14,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false})),pos,seeds:[]};
  for(let i=0;i<n;i++){ const a=rnd()*Math.PI*2, v=2+rnd()*5; ln.spark.seeds.push([Math.cos(a)*v,1+rnd()*4,Math.sin(a)*v*0.6]); } labG.add(ln.spark.pts); });
function setFX(tau,show,u){ LANES.forEach((ln,i)=>{ const on=!!show[i]; ln.halo.visible=on; ln.ghosts.forEach(g=>g.visible=on&&tau>-0.85); ln.spark.pts.visible=on;
  if(!on) return; ln.halo.geometry.dispose();
  { const pts=[]; for(let k=0;k<=60;k++){ const tt=-0.9+(tau+0.9)*k/60; pts.push(lanePos(ln,tt)); } ln.halo.geometry=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),80,0.26,8,false); }
  ln.ghosts.forEach((g,j)=>g.position.copy(lanePos(ln,tau-(j+1)*0.035)));
  const st=tau; ln.spark.pts.material.opacity=(st>=0&&st<0.6)?(1-st/0.6):0; ln.spark.seeds.forEach((sd,j)=>{ ln.spark.pos[j*3]=sd[0]*st; ln.spark.pos[j*3+1]=Math.max(0.02,sd[1]*st-4.9*st*st); ln.spark.pos[j*3+2]=ln.z+sd[2]*st; }); ln.spark.pts.geometry.attributes.position.needsUpdate=true; });
  const w=((u||0)*0.35)%1; sweep.position.x=-20+w*60; sweep.material.uniforms.uA.value=Math.sin(Math.PI*w)*0.35; }

// ---------- 后期 ----------
const composer=new EffectComposer(renderer); composer.addPass(new RenderPass(scene,camera));
composer.addPass(new UnrealBloomPass(new THREE.Vector2(W,H),0.25,0.5,0.97)); composer.addPass(new OutputPass());

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
  for(const o of Object.values(LM)) o.visible=true; Object.values(pillars).forEach(m=>m.visible=false); ref1.visible=false; setRGRoof(1); setLanes(-5,[0,0,0]); }
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
    const per=4.0, tau=cl(((u%per)-1.0)*0.55,-0.9,1.3);
    camLook(LX+lerp(-1,3,sm(u/D)),lerp(12,10,sm(u/D)),LZ+lerp(21,19,sm(u/D)),LX+3.5,0.2,LZ-1.5,42); setLanes(tau,[1,1,1]); setDust(tau); setFX(tau,[1,1,1],u); return k; }
  if(k==='lane_RG'||k==='lane_WIM'){ const per=4.6, tau=cl(((u%per)-1.2)*0.45,-0.9,1.3), show=k==='lane_RG'?[1,0,0]:[1,1,0];
    const ln=k==='lane_RG'?LANES[0]:LANES[1]; camLook(LX+2+Math.sin(u*0.15)*1.5,6.5,LZ+ln.z+15,LX+4,0.6,LZ+ln.z,42); setLanes(tau,show); setDust(tau); setFX(tau,show,u); return k; }
  if(k==='venues'){ // 法网（顶棚打开）→ 温网 → 澳网 → 美网 → 并排
    const t1=at(sec,'s1')-sec.t0, t2=at(sec,'s2')-sec.t0, t3=at(sec,'s3')-sec.t0, t25=(t2+t3)/2;
    if(u<t1){ only('RG'); const q=u/t1; setRGRoof(sm((q-0.25)/0.6)); const P=POS.RG; orbit(P[0],P[1],230-50*q,140-30*q,0.9+0.5*q,6); return 'v_RG'; }
    if(u<t2){ only('WIM'); const q=(u-t1)/(t2-t1), P=POS.WIM; orbit(P[0],P[1],170-30*q,80,0.7+0.6*q,8); return 'v_WIM'; }
    if(u<t25){ only('AO'); const q=(u-t2)/(t25-t2), P=POS.AO; orbit(P[0],P[1],170,55,1.0+0.4*q,18); return 'v_AO'; }
    if(u<t3){ only('USO'); const q=(u-t25)/(t3-t25), P=POS.USO; orbit(P[0],P[1],260,75,1.45+0.35*q,25); return 'v_USO'; }
    lineupWorld(); const q=sm((u-t3)/2.5); camLook(0,lerp(110,62,q),lerp(120,58,q),0,0,0,34); return 'lineup'; }
  if(k==='lineup'){ lineupWorld(); camLook(Math.sin(u*0.2)*6,62-u*2,58-u*2,0,0,0,34); return k; }
  if(k==='slow'){ // 慢镜：p0 来球 → p1 滑 → p2 咬住 → p3 弹出；p4 起再放一遍，停在咬住处展示两支箭头
    const T=f=>at(sec,f)-sec.t0, k1=T('p1'), k2=T('p2'), k3=T('p3'), k4=T('p4');
    let q; if(u<k1) q=0.25*u/k1; else if(u<k2) q=0.25+0.25*(u-k1)/(k2-k1); else if(u<k3) q=0.5+0.22*(u-k2)/(k3-k2); else if(u<k4) q=0.72+0.28*(u-k3)/(k4-k3); else q=Math.min(0.66,0.66*(u-k4)/3.0);
    const SX=SLO.x, SZ=SLO.z; camLook(SX+lerp(-2,3,sm(u/D)),3.0,SZ+15,SX+1.5,1.8,SZ,30); const ph=setSlow(q); return 'slow_'+ph; }
  if(k==='pillars'||k==='pillars_hi'){ lineupWorld(); const g=k==='pillars'?sm((u-(at(sec,'d2')-sec.t0)+1.0)/3.5):1; 
    camLook(0,lerp(70,58,sm(u/D)),lerp(110,96,sm(u/D)),0,16,0,36); setPillars(g,k==='pillars_hi'?['WIM','AO']:null); return k; }
  if(k==='wim'){ only('WIM'); const P=POS.WIM; orbit(P[0],P[1],150,60,2.2+0.5*u/D,6); return k; }
  if(k==='years'){ const T=f=>at(sec,f)-sec.t0, drop=sm((u-T('r8'))/1.2); const Y=yrG.position;
    camLook(Y.x+lerp(-8,6,sm(u/D)),30,Y.z+105,Y.x,11,Y.z,36); setYears(sm(u/2.0),drop); return k; }
  if(k==='acryl'){ const T=f=>at(sec,f)-sec.t0, q=sm((u-T('k3'))/4.5); const A=ACR;
    camLook(A.x+lerp(-3,3,sm(u/D)),lerp(5.5,4.2,sm(u/D)),A.z+lerp(24,20,sm(u/D)),A.x,1.8,A.z,40); setAcryl(q); return k; }
  if(k==='ao_years'){ const T=f=>at(sec,f)-sec.t0; const Y=aoG.position; camLook(Y.x+lerp(-8,6,sm(u/D)),28,Y.z+100,Y.x,10,Y.z,36); setAOYears(sm(u/2.0),u>=T('k6')-0.2); return k; }
  if(k==='outro'){ only(null); Object.values(LM).forEach(o=>o.visible=false); venues.forEach(v=>v.g.position.set(POS[v.k][0]*0.40,0,POS[v.k][1]*0.40));
    const q=sm(u/D); camLook(0,lerp(420,640,q),lerp(520,760,q),0,-10,lerp(25,40,q),lerp(30,24,q)); return k; }
  return k; }
const PREVIEW=Q.get('preview')==='1';
window.renderAt=(t)=>{ for(const k in anchors) delete anchors[k]; const s=PREVIEW?previewShot(t):shotTL(t); composer.render(); return JSON.stringify(Object.assign({_shot:s},anchors)); };
window.READY=true;
