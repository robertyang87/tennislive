// 四大满贯中心球场：预览场景（场地材质与配色）
// 球场尺寸按 ITF 标准；场馆为示意（按真实平面形状风格化，不按座位数精确建模）
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

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
  AO: canvasTex(TW,TH,(g,w,h)=>{ // 澳网：2020、2023 年照片里场内外是同一种蓝
    g.fillStyle='#2386d1'; g.fillRect(0,0,w,h);
    noise(g,w,h,40000,['rgba(255,255,255,0.05)','rgba(0,0,0,0.06)'],1.2);
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
    else if(shape==='dodec'){ const k=Math.PI/6, a0=Math.floor((a+k/2)/k)*k-k/2, f=Math.cos(k/2)/Math.cos(a-a0-k/2); pts.push([c*rx*f,s*rz*f]); }
    else { const p=shape==='box'?40:9; pts.push([Math.sign(c)*Math.pow(Math.abs(c),2/p)*rx,Math.sign(s)*Math.pow(Math.abs(s),2/p)*rz]); } }
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
const FACADE={
  RG: canvasTex(1024,256,(g,w,h)=>{ // 夏蒂埃：白色横向遮阳百叶＋深色玻璃，分层
    g.fillStyle='#2b3138'; g.fillRect(0,0,w,h);
    for(let r=0;r<5;r++){ const y=r*h/5; g.fillStyle='#e9ebec'; g.fillRect(0,y+6,w,10); g.fillStyle='#cfd4d8'; g.fillRect(0,y+18,w,4); g.fillStyle='rgba(120,150,170,0.35)'; g.fillRect(0,y+24,w,h/5-26); }
    for(let x=0;x<w;x+=32){ g.fillStyle='rgba(230,235,238,0.55)'; g.fillRect(x,0,2,h); } }),
  WIM: canvasTex(1024,256,(g,w,h)=>{ // 中心球场：外墙爬满绿植（2017 年外观照片），露出一格格窗
    g.fillStyle='#4f6a2a'; g.fillRect(0,0,w,h); noise(g,w,h,60000,['#6e8a2e','#8a9a35','#4d6b27','#a3a347','#3c5a22','#7b5a2a'],3.5);
    g.fillStyle='rgba(30,45,40,0.85)'; for(let x=14;x<w;x+=56) for(const y of[0.2,0.5]) g.fillRect(x,h*y,34,h*0.18); }),
  AO: canvasTex(1024,256,(g,w,h)=>{ // 罗德·拉沃尔：下层通高玻璃，上层白色斜格外壳
    g.fillStyle='#e8ecef'; g.fillRect(0,0,w,h*0.55);
    g.strokeStyle='#b9c2ca'; g.lineWidth=3; for(let x=-h;x<w+h;x+=40){ g.beginPath(); g.moveTo(x,0); g.lineTo(x+h*0.55,h*0.55); g.stroke(); g.beginPath(); g.moveTo(x+h*0.55,0); g.lineTo(x,h*0.55); g.stroke(); }
    g.fillStyle='#1b2a38'; g.fillRect(0,h*0.55,w,h*0.45); g.fillStyle='rgba(255,210,150,0.35)'; for(let x=0;x<w;x+=26) g.fillRect(x+4,h*0.62,16,h*0.3); }),
  USO: canvasTex(1024,256,(g,w,h)=>{ // 阿瑟·阿什：砖红色基座
    g.fillStyle='#8a3b2c'; g.fillRect(0,0,w,h); noise(g,w,h,20000,['#7a3326','#9a4434','#843828'],3);
    g.fillStyle='#5d241b'; for(let x=10;x<w;x+=90) g.fillRect(x,h*0.15,18,h*0.75); g.fillStyle='#c9c9c4'; g.fillRect(0,0,w,8); }),
};
for(const t of Object.values(FACADE)){ t.wrapS=THREE.RepeatWrapping; t.repeat.set(5,1); }

// seat：看台座椅颜色（照片：法网灰、温网深绿、澳网蓝、美网蓝）
const VENUES=[
  {k:'RG', shape:'box',  rx:50,rz:66,H:30, glow:0xffa070, seat:0x5a5f66},
  {k:'WIM',shape:'dodec',rx:56,rz:52,H:22, glow:0x8dffa0, seat:0x1f4a2c},
  {k:'AO', shape:'round',rx:54,rz:62,H:30, glow:0x6cc0ff, seat:0x1f4f9a},
  {k:'USO',shape:'round',rx:76,rz:76,H:28, glow:0x86b0ff, seat:0x22427e},
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
  band(grp,scl(out,1.0),scl(out,1.0),0,fh,new THREE.MeshStandardMaterial({map:FACADE[v.k],roughness:0.6,metalness:0.1,side:THREE.DoubleSide}));
  if(v.k==='USO') band(grp,scl(out,1.0),scl(out,0.97),fh,top+1,new THREE.MeshStandardMaterial({color:0x3a4250,roughness:0.6,side:THREE.DoubleSide}));
  else band(grp,scl(out,0.96),scl(out,1.0),v.H-3,v.H,new THREE.MeshStandardMaterial({color:0x2a3038,roughness:0.6,side:THREE.DoubleSide}));
}
const fabric=(op=1)=>new THREE.MeshStandardMaterial({color:0xd9dee3,roughness:0.6,transparent:op<1,opacity:op,side:THREE.DoubleSide});
const steel=new THREE.MeshStandardMaterial({color:0xd4d8dc,roughness:0.35,metalness:0.6});
const steelBlue=new THREE.MeshStandardMaterial({color:0x2b4f8a,roughness:0.4,metalness:0.6});
function beam(grp,a,b,r,mat){ const d=b.clone().sub(a), m=new THREE.Mesh(new THREE.CylinderGeometry(r,r,d.length(),8),mat); m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(V3(0,1,0),d.normalize()); grp.add(m); return m; }

function roofRG(v,grp){ // 照片：顶棚合上时是一排沿长边方向的白色膜「翼」，锯齿状起伏，四周略出挑
  const n=11, W2=v.rx*1.06, len=v.rz*2.08, w=2*W2/n;
  for(let i=0;i<n;i++){ const x=-W2+w*(i+0.5);
    for(const side of[-1,1]){ const p=new THREE.Mesh(new THREE.PlaneGeometry(w*0.52,len),fabric());
      p.rotation.x=-Math.PI/2; p.rotation.y=side*0.22; p.position.set(x+side*w*0.25,v.H+3.2,0); grp.add(p); }
    beam(grp,V3(x,v.H+3.9,-len/2),V3(x,v.H+3.9,len/2),0.35,steel);
    beam(grp,V3(x-w/2,v.H+2.4,-len/2),V3(x-w/2,v.H+2.4,len/2),0.25,steel); }
  const rim=new THREE.Mesh(new THREE.BoxGeometry(W2*2+1,1.2,len+1),new THREE.MeshStandardMaterial({color:0xbfc5ca,roughness:0.5,transparent:true,opacity:0.0})); grp.add(rim);
}
function roofWIM(v,grp){ // 照片：顶棚打开时，白色拱形桁架分两束收在南北两端
  const out=shapePts('dodec',v.rx,v.rz);
  band(grp,scl(out,0.70),scl(out,1.05),v.H+5,v.H+0.6,new THREE.MeshStandardMaterial({color:0x34553e,roughness:0.7,side:THREE.DoubleSide}));
  loop(grp,scl(out,1.05),v.H+0.65,0xcfd8cf,0.9);
  const span=v.rx*1.9;
  for(const end of[-1,1]) for(let i=0;i<4;i++){ const z=end*(v.rz*0.86-i*3.2), hh=8.5-i*0.4;
    const top=[],bot=[]; for(let j=0;j<=24;j++){ const u=j/24*2-1; top.push(V3(u*span/2,v.H+4.6+(1-u*u)*hh,z)); bot.push(V3(u*span/2*0.97,v.H+4.6+(1-u*u)*(hh-3.2),z)); }
    grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(top),48,0.55,6,false),steel));
    grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(bot),48,0.4,6,false),steel));
    for(let j=1;j<24;j++) beam(grp,j%2?bot[j]:top[j],j%2?top[j+1]:bot[j+1],0.18,steel);
    if(i<3){ const geo=new THREE.BufferGeometry(), pos=[], dz=-end*3.2; for(let j=0;j<24;j++){ const a=top[j],b=top[j+1]; pos.push(a.x,a.y,a.z, b.x,b.y,b.z, b.x,b.y-0.2,b.z+dz, a.x,a.y,a.z, b.x,b.y-0.2,b.z+dz, a.x,a.y-0.2,a.z+dz); }
      geo.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); geo.computeVertexNormals(); grp.add(new THREE.Mesh(geo,fabric(0.55))); } }
}
function roofAO(v,grp){ // 照片：固定顶棚中间是长方形开口；开口两侧各一道白色弓弦桁架
  const out=shapePts('round',v.rx,v.rz), hx=v.rx*0.36, hz=v.rz*0.52;
  const sh=new THREE.Shape(scl(out,1.02).map(p=>new THREE.Vector2(p[0],p[1])));
  sh.holes.push(new THREE.Path([new THREE.Vector2(-hx,-hz),new THREE.Vector2(hx,-hz),new THREE.Vector2(hx,hz),new THREE.Vector2(-hx,hz)]));
  const r=new THREE.Mesh(new THREE.ShapeGeometry(sh),new THREE.MeshStandardMaterial({color:0x8d96a0,roughness:0.5,metalness:0.4,side:THREE.DoubleSide})); r.rotation.x=Math.PI/2; r.position.y=v.H+1; grp.add(r);
  for(const sx of[-1,1]){ const x=sx*(hx+3), L2=v.rz*1.05, top=[],bot=[];
    for(let j=0;j<=24;j++){ const u=j/24*2-1; top.push(V3(x,v.H+2+(1-u*u)*11,u*L2)); bot.push(V3(x,v.H+2,u*L2)); }
    grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(top),48,0.7,8,false),steel));
    beam(grp,bot[0],bot[24],0.45,steel);
    for(let j=1;j<24;j++) beam(grp,j%2?bot[j]:top[j],j%2?top[j+1]:bot[j+1],0.22,steel); }
}
function roofUSO(v,grp){ // 照片：圆角方形的白色膜顶像一块鼓起的「枕头」，蓝色钢桁架斜撑落在外柱上，中间可开合
  const top=v.H+14, R=v.rx*1.12;
  const out=shapePts('box',R,R).map(p=>[p[0],p[1]]), sq=shapePts('round',1,1);
  const canopyOut=shapePts('round',R,R).map((p,i)=>{ const q=out[i]; return [p[0]*0.6+q[0]*0.4,p[1]*0.6+q[1]*0.4]; });
  { const NA=canopyOut.length-1, NR=14, pos=[]; const P=(i,k)=>{ const f=0.30+0.70*k/NR, a=i/NA*Math.PI*2, c=canopyOut[i%NA];
      const dome=15*Math.sqrt(Math.max(0,1-Math.pow((f-0.30)/0.70,2))), puff=6.5*Math.pow(Math.abs(Math.cos(2*a)),3)*Math.sin(Math.PI*Math.min(1,(f-0.3)/0.7));
      return [c[0]*f, top+1.2+dome+puff, c[1]*f]; };
    for(let i=0;i<NA;i++) for(let k=0;k<NR;k++){ const A=P(i,k),B=P(i+1,k),C=P(i+1,k+1),D=P(i,k+1); pos.push(...A,...B,...C,...A,...C,...D); }
    const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.computeVertexNormals(); grp.add(new THREE.Mesh(g,fabric()));
    const lip=[]; for(let i=0;i<=NA;i++){ const q=P(i,NR); lip.push(V3(q[0],q[1],q[2])); } grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(lip,true),220,0.9,6,true),new THREE.MeshStandardMaterial({color:0xe6e9ec,roughness:0.5}))); }
  // 外柱与蓝色斜撑
  const n=8, cr=R*1.04; const ring=canopyOut;
  for(let i=0;i<n;i++){ const a=(i+0.5)/n*Math.PI*2, c=V3(Math.cos(a)*cr,0,Math.sin(a)*cr);
    beam(grp,c,V3(c.x,top,c.z),1.6,new THREE.MeshStandardMaterial({color:0x8e959c,roughness:0.6})); }
  for(let i=0;i<ring.length-1;i+=3){ const p=ring[i], q=ring[(i+6)%(ring.length-1)]; beam(grp,V3(p[0]*0.9,v.H+3,p[1]*0.9),V3(p[0],top+0.8,p[1]),0.5,steelBlue); beam(grp,V3(p[0]*0.9,v.H+3,p[1]*0.9),V3(q[0],top+0.8,q[1]),0.3,steelBlue); }
  loop(grp,scl(ring,0.9),v.H+3,0x2b4f8a,1);
}
function shellAO(v,grp){ const a=shapePts('round',v.rx*0.99,v.rz*0.99), b=shapePts('round',v.rx*1.08,v.rz*1.08), n=a.length-1, pos=[],uv=[];
  const hy=i=>v.H*(1.0+0.32*Math.max(0,Math.cos(i/n*Math.PI*2-0.5)));
  for(let i=0;i<n;i++){ const u0=i/n,u1=(i+1)/n; const A=[a[i][0],v.H*0.45,a[i][1]],B=[a[i+1][0],v.H*0.45,a[i+1][1]],C=[b[i+1][0],hy(i+1),b[i+1][1]],D=[b[i][0],hy(i),b[i][1]];
    pos.push(...A,...B,...C,...A,...C,...D); uv.push(u0,0.47,u1,0.47,u1,1,u0,0.47,u1,1,u0,1); }
  const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2)); g.computeVertexNormals();
  grp.add(new THREE.Mesh(g,new THREE.MeshStandardMaterial({map:FACADE.AO,roughness:0.5,metalness:0.1,side:THREE.DoubleSide})));
  const rim=b.map((p,i)=>V3(p[0],hy(i)+0.3,p[1])); grp.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(rim,true),200,0.6,6,true),steel)); }
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

const POS={RG:[-340,-320],WIM:[340,-320],AO:[-340,320],USO:[340,320]};
const venues=VENUES.map(v=>{ const g=new THREE.Group(); buildCore(v,g); buildBowl(v,g); ROOF[v.k](v,g); if(v.k==='AO') shellAO(v,g); g.position.set(POS[v.k][0],0,POS[v.k][1]); scene.add(g); return {...v,g}; });
// 周边：法网——布洛涅林边的树和巴黎的低层建筑；澳网——墨尔本市中心天际线；美网——地球仪雕塑
const lmRG=new THREE.Group(); lmRG.add(trees(160,85,190,0x3d5a34)); lmRG.add(paris()); lmRG.position.set(POS.RG[0],0,POS.RG[1]); scene.add(lmRG);
const lmAO=skyline(0x6cc0ff); lmAO.position.set(POS.AO[0]-150,0,POS.AO[1]-200); lmAO.scale.set(0.8,0.8,0.8); lmAO.rotation.y=0.64; scene.add(lmAO);
const lmUSO=unisphere(0x9cc2ff); lmUSO.position.set(POS.USO[0]-150,0,POS.USO[1]+60); scene.add(lmUSO);

// ---------- 后期 ----------
const composer=new EffectComposer(renderer); composer.addPass(new RenderPass(scene,camera));
composer.addPass(new UnrealBloomPass(new THREE.Vector2(W,H),0.25,0.5,0.97)); composer.addPass(new OutputPass());

// ---------- 镜头 ----------
// t=0 四座全景；t=1..4 逐个场馆外观（含地标）；t=5..8 场地材质特写；t=9 四块场地并排
const VIEW={RG:[120,115,165,0,8,-5],WIM:[90,70,115,0,10,0],AO:[105,48,150,-30,22,-60],USO:[-20,58,290,-40,30,0]};
const LM={RG:lmRG,AO:lmAO,USO:lmUSO};
function only(k){ for(const v of venues) v.g.visible=(k===null||v.k===k); for(const [kk,o] of Object.entries(LM)) o.visible=(k===null||kk===k); }
function shot(t){
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
window.renderAt=(t)=>{ const s=shot(t); composer.render(); return JSON.stringify({t,shot:s}); };
window.READY=true;
