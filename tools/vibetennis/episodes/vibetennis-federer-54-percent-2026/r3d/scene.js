// vibetennis 第 4 集《费德勒只赢了 54% 的分，凭什么赢了八成多的比赛？》3D 场景。
// 资料包：papers/vibetennis-federer-54-percent-2026/sources.md（每个上屏数字的官方来源＋独立来源、模型推导、场景设计）。
// 场景：星系（1526 场）/ 粒子变形（数字、理论大标题）/ 全息天平 / 比分河道（吸收型马尔可夫链，边宽＝真实流量）
//      / 套娃链（局→盘→场）/ S 曲线全息图 / 双影柱（模型 vs 真实）/ 2019 中央球场 / 23.6 万分的星海。
// 所有动画都是时间 t 的纯函数（分段并行渲染）。
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';
import { SHOTS } from './shots.js';

const Q=new URLSearchParams(location.search); const LANG=Q.get('lang')||'zh';
const W=+(Q.get('w')||1920), H=+(Q.get('h')||1080);
const renderer=new THREE.WebGLRenderer({antialias:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
renderer.setPixelRatio(1); renderer.setSize(W,H); renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.0;
document.body.appendChild(renderer.domElement);
const scene=new THREE.Scene(); scene.background=new THREE.Color(0x02040a);
const camera=new THREE.PerspectiveCamera(40,W/H,0.05,9000);
const skyMat=new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,uniforms:{uWarm:{value:0},uOp:{value:1}},
  vertexShader:`varying vec3 vD; void main(){ vD=normalize(position); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,
  fragmentShader:`varying vec3 vD; uniform float uWarm,uOp; void main(){ float h=vD.y; float g=exp(-abs(h+0.02)*7.0); vec3 top=vec3(0.006,0.01,0.024); vec3 hz=mix(vec3(0.018,0.032,0.075),vec3(0.07,0.04,0.012),uWarm); vec3 vi=vec3(0.04,0.022,0.07); float side=0.5+0.5*vD.x; gl_FragColor=vec4((top+hz*g+vi*g*g*side*0.6*(1.-uWarm))*uOp,1.);} `});
scene.add(new THREE.Mesh(new THREE.SphereGeometry(6000,48,24),skyMat));

const GOLD=new THREE.Color(1.0,0.66,0.22), CYAN=new THREE.Color(0.38,0.86,1.0), WHITE=new THREE.Color(1,1,1),
      BLUE=new THREE.Color(0.32,0.5,1.0), BALLC=new THREE.Color(0.80,1.0,0.22), RED=new THREE.Color(1.0,0.3,0.28), DIMB=new THREE.Color(0.2,0.3,0.6);
let seed=20261101; const rnd=()=>{seed=(seed*16807)%2147483647;return seed/2147483647;};
const V=(x,y,z)=>new THREE.Vector3(x,y,z);
const clamp01=x=>Math.min(1,Math.max(0,x));
const ease=x=>{x=clamp01(x); return x*x*(3-2*x);};
const easeIO=x=>{x=clamp01(x); return x<0.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;};
const easeOutBack=x=>{x=clamp01(x); const c1=1.70158,c3=c1+1; return 1+c3*Math.pow(x-1,3)+c1*Math.pow(x-1,2);};

// ---------- helpers ----------
const lineMats=[];
function lineMat(color,width,opacity,{dashed=false,dash=1,world=false}={}){
  const m=new LineMaterial({color,linewidth:width,transparent:true,opacity,depthWrite:false,blending:THREE.AdditiveBlending,worldUnits:world,dashed,dashSize:dash,gapSize:dash*0.7});
  m.resolution.set(W,H); lineMats.push(m); return m;
}
function fatLine(pts,color,width,opacity=1,group=scene,opt={}){
  const g=new LineGeometry(); g.setPositions(pts.flatMap(p=>[p.x,p.y,p.z]));
  const l=new Line2(g,lineMat(color,width,opacity,opt)); l.computeLineDistances(); l.frustumCulled=false; group.add(l); return l;
}
function setLine(l,pts){ l.geometry.setPositions(pts.flatMap(p=>[p.x,p.y,p.z])); l.computeLineDistances(); }
const glowTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d');
  const gr=g.createRadialGradient(64,64,0,64,64,64); gr.addColorStop(0,'rgba(255,255,255,1)'); gr.addColorStop(0.15,'rgba(255,255,255,0.6)'); gr.addColorStop(0.45,'rgba(255,255,255,0.12)'); gr.addColorStop(1,'rgba(255,255,255,0)');
  g.fillStyle=gr; g.fillRect(0,0,128,128); return new THREE.CanvasTexture(c); })();
function glowSprite(color,size,op=1,group=scene){ const s=new THREE.Sprite(new THREE.SpriteMaterial({map:glowTex,color,transparent:true,opacity:op,blending:THREE.AdditiveBlending,depthWrite:false})); s.scale.set(size,size,1); group.add(s); return s; }
const ringTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=256; const g=c.getContext('2d'); g.strokeStyle='white';
  g.lineWidth=7; g.beginPath(); g.arc(128,128,108,0,Math.PI*2); g.stroke(); g.globalAlpha=0.3; g.lineWidth=2; g.beginPath(); g.arc(128,128,124,0,Math.PI*2); g.stroke(); return new THREE.CanvasTexture(c); })();
function ringSprite(color,size,op=1,group=scene){ const s=new THREE.Sprite(new THREE.SpriteMaterial({map:ringTex,color,transparent:true,opacity:op,blending:THREE.AdditiveBlending,depthWrite:false})); s.scale.set(size,size,1); group.add(s); return s; }
function addMat(color,opacity){return new THREE.MeshBasicMaterial({color,transparent:true,opacity,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide});}
// 点云：size 为世界尺寸，uMax 限像素；每点颜色＋不透明度；sparkle 让粒子闪烁
function pointCloud(n,size,maxPx,group=scene,sparkle=0){
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(n*3),3));
  g.setAttribute('color',new THREE.Float32BufferAttribute(new Float32Array(n*3),3));
  g.setAttribute('alpha',new THREE.Float32BufferAttribute(new Float32Array(n).fill(1),1));
  const ph=new Float32Array(n); for(let i=0;i<n;i++) ph[i]=rnd()*6.283; g.setAttribute('phase',new THREE.Float32BufferAttribute(ph,1));
  const m=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uSize:{value:size},uOp:{value:1},uMax:{value:maxPx},uH:{value:H},uT:{value:0},uSpark:{value:sparkle}},
   vertexShader:`attribute vec3 color; attribute float alpha; attribute float phase; varying vec3 vC; varying float vA; uniform float uSize,uMax,uH,uT,uSpark; void main(){ vC=color; vA=alpha*(1.0-uSpark*0.5+uSpark*0.5*sin(uT*3.0+phase*7.0)); vec4 mv=modelViewMatrix*vec4(position,1.); float px=uSize*uH*0.5*projectionMatrix[1][1]/-mv.z; vA*=clamp(px/max(px,uMax),0.25,1.0); gl_PointSize=clamp(px,1.0,uMax); gl_Position=projectionMatrix*mv; }`,
   fragmentShader:`uniform float uOp; varying vec3 vC; varying float vA; void main(){ float d=length(gl_PointCoord-0.5); float ta=exp(-d*d*18.0)*(1.0-smoothstep(0.4,0.5,d)); gl_FragColor=vec4(vC*ta*uOp*vA, ta*uOp*vA);} `});
  const p=new THREE.Points(g,m); p.frustumCulled=false; group.add(p); return p;
}
function cloudSet(p,i,x,y,z,r,gg,b,a){ const P=p.geometry.attributes.position.array, C=p.geometry.attributes.color.array, A=p.geometry.attributes.alpha.array; P[i*3]=x;P[i*3+1]=y;P[i*3+2]=z; C[i*3]=r;C[i*3+1]=gg;C[i*3+2]=b; A[i]=a; }
function cloudHide(p,i){ p.geometry.attributes.alpha.array[i]=0; }
function cloudDone(p){ for(const k of ['position','color','alpha']) p.geometry.attributes[k].needsUpdate=true; }
const allClouds=[];
function cloud(n,size,maxPx,group=scene,sparkle=0){ const c=pointCloud(n,size,maxPx,group,sparkle); allClouds.push(c); return c; }

// ---------- 背景：星点、尘埃、网格地面 ----------
const stars=cloud(9000,10,3); { for(let i=0;i<9000;i++){ const r=2600+rnd()*2800, th=rnd()*Math.PI*2, ph=Math.acos(2*rnd()-1); const k=0.35+rnd()*0.6, w=rnd();
  cloudSet(stars,i,r*Math.sin(ph)*Math.cos(th),r*Math.cos(ph)*0.8,r*Math.sin(ph)*Math.sin(th),k*(0.7+0.3*w),k*(0.75+0.2*w),k,1);} cloudDone(stars); }
const dust=cloud(5000,0.3,3,scene,0.6); { for(let i=0;i<5000;i++){ const k=0.2+rnd()*0.4; cloudSet(dust,i,(rnd()-0.5)*500,(rnd()-0.5)*260,(rnd()-0.5)*500,k*0.6,k*0.8,k,1);} cloudDone(dust); }
const gridMat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,uniforms:{uOp:{value:1},uC:{value:new THREE.Color(0.25,0.55,1.0)},uS:{value:4}},
 vertexShader:`varying vec3 vW; void main(){ vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }`,
 fragmentShader:`varying vec3 vW; uniform float uOp,uS; uniform vec3 uC;
  float grid(vec2 p,float s){ vec2 g=abs(fract(p/s-0.5)-0.5)/fwidth(p/s); return 1.-min(min(g.x,g.y),1.); }
  void main(){ float d=length(vW.xz); float g=grid(vW.xz,uS)*0.35+grid(vW.xz,uS*5.)*0.6; float f=exp(-d*0.005); gl_FragColor=vec4(uC*g*f, g*f*0.55*uOp); }`});
const grid=new THREE.Mesh(new THREE.PlaneGeometry(6000,6000),gridMat); grid.rotation.x=-Math.PI/2; scene.add(grid);

// ================= 粒子变形（开场数字、理论标题、收束） =================
const NM=14000;
const morph=cloud(NM,0.3,6,scene,0.35);
const SHAPES={};
function textShape(str,font,width,col,{y=0,jitter=0.04,col2=null,split=1}={}){
  const c=document.createElement('canvas'); c.width=2048; c.height=512; const g=c.getContext('2d');
  g.fillStyle='#000'; g.fillRect(0,0,2048,512); g.fillStyle='#fff'; g.font=font; g.textAlign='center'; g.textBaseline='middle';
  const mw=g.measureText(str).width; if(mw>1900){ const px=Math.floor(300*1900/mw); g.font=font.replace('300px',px+'px'); }
  g.fillText(str,1024,262);
  const d=g.getImageData(0,0,2048,512).data; const pts=[];
  let minx=1e9,maxx=-1e9; for(let yy=0;yy<512;yy+=3) for(let xx=0;xx<2048;xx+=3){ if(d[(yy*2048+xx)*4]>140){ pts.push([xx,yy]); if(xx<minx)minx=xx; if(xx>maxx)maxx=xx; } }
  const sc=width/(maxx-minx); const out=new Float32Array(NM*3); const cc=new Float32Array(NM*3);
  for(let i=pts.length-1;i>0;i--){ const j=Math.floor(rnd()*(i+1)); [pts[i],pts[j]]=[pts[j],pts[i]]; }
  for(let i=0;i<NM;i++){ const k=0.7+rnd()*0.4;
    if(i<pts.length*1.6){ const p=pts[i%pts.length]; out[i*3]=(p[0]-1024)*sc+(rnd()-0.5)*jitter; out[i*3+1]=-(p[1]-262)*sc+y+(rnd()-0.5)*jitter; out[i*3+2]=(rnd()-0.5)*jitter*4;
      const cl=(col2&&rnd()>split)?col2:col; cc[i*3]=cl.r*k; cc[i*3+1]=cl.g*k; cc[i*3+2]=cl.b*k; }
    else { // 多出来的粒子散成文字周围的微尘
      const a=rnd()*6.283, r=width*(0.55+rnd()*0.9); out[i*3]=Math.cos(a)*r; out[i*3+1]=Math.sin(a)*r*0.35+y; out[i*3+2]=(rnd()-0.5)*20; const kk=0.12*k; cc[i*3]=col.r*kk; cc[i*3+1]=col.g*kk; cc[i*3+2]=col.b*kk; } }
  return {p:out,c:cc};
}
function sphereShape(r,col,seamCol){
  const out=new Float32Array(NM*3), cc=new Float32Array(NM*3);
  for(let i=0;i<NM;i++){ const z=2*rnd()-1, th=rnd()*Math.PI*2, s=Math.sqrt(1-z*z); const x=s*Math.cos(th), y=s*Math.sin(th);
    out[i*3]=x*r; out[i*3+1]=y*r; out[i*3+2]=z*r; const phi=Math.atan2(z,x); const seam=Math.abs(y-0.62*Math.sin(2*phi))<0.06; const c=seam?seamCol:col; const k=0.8+rnd()*0.3;
    cc[i*3]=c.r*k; cc[i*3+1]=c.g*k; cc[i*3+2]=c.b*k; }
  return {p:out,c:cc};
}
function burstShape(r,col,col2=null,frac=0.5){ const out=new Float32Array(NM*3), cc=new Float32Array(NM*3);
  for(let i=0;i<NM;i++){ const z=2*rnd()-1, th=rnd()*Math.PI*2, s=Math.sqrt(1-z*z), rr=r*(0.25+Math.pow(rnd(),0.6)*0.9);
    out[i*3]=s*Math.cos(th)*rr; out[i*3+1]=s*Math.sin(th)*rr*0.7; out[i*3+2]=z*rr; const cl=(col2&&rnd()>frac)?col2:col; const k=0.5+rnd()*0.5; cc[i*3]=cl.r*k; cc[i*3+1]=cl.g*k; cc[i*3+2]=cl.b*k; }
  return {p:out,c:cc}; }
// 星系：前 1526 颗是「比赛」（1251 金 / 275 蓝，按官方生涯战绩），其余是暗尘
const GAL_N=1526, GAL_W=1251;
const galOrder=[...Array(GAL_N).keys()]; for(let i=GAL_N-1;i>0;i--){ const j=Math.floor(rnd()*(i+1)); [galOrder[i],galOrder[j]]=[galOrder[j],galOrder[i]]; }
const galWon=new Uint8Array(GAL_N); galOrder.slice(0,GAL_W).forEach(i=>galWon[i]=1);
function galaxyShape(R,sea=false){ const out=new Float32Array(NM*3), cc=new Float32Array(NM*3);
  for(let i=0;i<NM;i++){ const arm=i%3, u=Math.pow(rnd(),0.7), r=R*(0.06+u), a=arm*2.094+u*5.2+(rnd()-0.5)*0.5*(1-u*0.5);
    out[i*3]=Math.cos(a)*r+(rnd()-0.5)*R*0.05; out[i*3+1]=(rnd()-0.5)*R*0.04*(1.2-u); out[i*3+2]=Math.sin(a)*r+(rnd()-0.5)*R*0.05;
    let cl, k;
    if(sea){ cl=rnd()<0.541?GOLD:BLUE; k=0.35+rnd()*0.55; }
    else if(i<GAL_N){ cl=galWon[i]?GOLD:BLUE; k=1.5; } else { cl=DIMB; k=0.16+rnd()*0.22; if(u<0.15){ cl=GOLD; k=0.25; } }
    cc[i*3]=cl.r*k; cc[i*3+1]=cl.g*k; cc[i*3+2]=cl.b*k; }
  return {p:out,c:cc}; }
const NUMF='800 300px "Inter","Noto Sans CJK SC",sans-serif';
const SERIF='900 300px "Noto Serif CJK SC",serif';
SHAPES.void=burstShape(320,DIMB);
SHAPES.galaxy=galaxyShape(24);
SHAPES.n1526=textShape('1526',NUMF,34,WHITE);
SHAPES.n82=textShape('82%',NUMF,30,GOLD);
SHAPES.dust54=burstShape(26,GOLD,BLUE,0.54);
SHAPES.n54=textShape('54%',NUMF,30,CYAN);
SHAPES.ball=sphereShape(4.2,BALLC,WHITE);
SHAPES.burst=burstShape(70,BALLC);
const TITLE_TXT=LANG==='en'?'MARKOV CHAIN':'马尔可夫链';
SHAPES.title=textShape(TITLE_TXT,SERIF,LANG==='en'?54:46,BALLC);
SHAPES.titleGold=textShape(TITLE_TXT,SERIF,LANG==='en'?54:46,GOLD);
SHAPES.cp=textShape('40-15',NUMF,30,GOLD);
SHAPES.cpBurst=burstShape(26,RED,GOLD,0.6);
SHAPES.sea=galaxyShape(46,true);
SHAPES.one=textShape(LANG==='en'?"IT'S ONLY A POINT":'这只是一分',SERIF,LANG==='en'?50:40,GOLD);
const mDel=new Float32Array(NM), mPh=new Float32Array(NM); for(let i=0;i<NM;i++){ mDel[i]=rnd(); mPh[i]=rnd()*Math.PI*2; }
// 关键帧：[时刻, 形状, 过渡秒数, 旋涡强度]
function setMorph(keys,t,{op=1,spin=0,tilt=0,scale=1,offset=V(0,0,0)}={}){
  morph.visible=op>0.001; if(!morph.visible) return;
  let k=0; while(k+1<keys.length && t>=keys[k+1][0]) k++;
  const A=SHAPES[keys[k][1]], nx=keys[k+1];
  const P=morph.geometry.attributes.position.array, C=morph.geometry.attributes.color.array, AL=morph.geometry.attributes.alpha.array;
  const cs=Math.cos(spin), sn=Math.sin(spin), ct=Math.cos(tilt), st=Math.sin(tilt);
  for(let i=0;i<NM;i++){
    let x=A.p[i*3],y=A.p[i*3+1],z=A.p[i*3+2], r=A.c[i*3],g=A.c[i*3+1],b=A.c[i*3+2];
    if(nx && t>=nx[0]){
      const B=SHAPES[nx[1]]; const span=Math.max(nx[2],0.001); const dl=mDel[i]*span*0.45; const u=easeIO((t-nx[0]-dl)/(span*0.55));
      const sw=Math.sin(u*Math.PI)*(nx[3]||0);
      x+=(B.p[i*3]-x)*u; y+=(B.p[i*3+1]-y)*u; z+=(B.p[i*3+2]-z)*u;
      if(sw){ const a=mPh[i]+u*5; x+=Math.cos(a)*sw*7; y+=Math.sin(a*1.3)*sw*4; z+=Math.sin(a)*sw*9; }
      r+=(B.c[i*3]-r)*u; g+=(B.c[i*3+1]-g)*u; b+=(B.c[i*3+2]-b)*u;
    }
    const br=0.03*Math.sin(t*2.1+mPh[i]*3); x+=br; y+=br*0.7;
    let xr=x*cs+z*sn, zr=-x*sn+z*cs; let yr=y*ct-zr*st; zr=y*st+zr*ct;
    P[i*3]=xr*scale+offset.x; P[i*3+1]=yr*scale+offset.y; P[i*3+2]=zr*scale+offset.z; C[i*3]=r; C[i*3+1]=g; C[i*3+2]=b; AL[i]=op;
  }
  cloudDone(morph);
}
function morphPos(i){ const P=morph.geometry.attributes.position.array; return V(P[i*3],P[i*3+1],P[i*3+2]); }
// 实体网球
const ballMat=new THREE.ShaderMaterial({uniforms:{uOp:{value:1},uGlow:{value:1}},transparent:true,
  vertexShader:`varying vec3 vN; varying vec3 vP; void main(){ vN=normalize(normalMatrix*normal); vP=position; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader:`varying vec3 vN; varying vec3 vP; uniform float uOp,uGlow; void main(){ vec3 p=normalize(vP); float phi=atan(p.z,p.x); float seam=1.-smoothstep(0.03,0.06,abs(p.y-0.62*sin(2.*phi)));
   float l=0.45+0.55*max(dot(vN,normalize(vec3(0.4,0.6,1.))),0.); float rim=pow(1.-max(vN.z,0.),2.); vec3 c=mix(vec3(0.78,0.95,0.2)*l,vec3(1.),seam*0.9)+rim*vec3(0.8,1.,0.4)*uGlow; gl_FragColor=vec4(c,uOp);} `});
const ball=new THREE.Mesh(new THREE.SphereGeometry(1,64,48),ballMat); scene.add(ball);
const ballGlow=glowSprite(BALLC,14,0.6); const flare=glowSprite(WHITE,40,0);
const ballTrail=fatLine([V(0,0,0),V(0,0,-1)],BALLC,6,0.8);
const shock=ringSprite(GOLD,10,0); const shock2=ringSprite(CYAN,10,0);
const rays=new THREE.Group(); scene.add(rays); { for(let i=0;i<56;i++){ const a=i/56*Math.PI*2, r1=7+rnd()*4, r2=40+rnd()*70; fatLine([V(Math.cos(a)*r1,Math.sin(a)*r1*0.55,-2),V(Math.cos(a)*r2,Math.sin(a)*r2*0.55,-2)],GOLD,1.0+rnd()*1.6,0.35,rays); } }
function setRays(op,s=1,col=GOLD){ rays.visible=op>0.001; rays.scale.setScalar(s); rays.children.forEach((l,i)=>{ l.material.opacity=op*(0.2+0.25*((i*7)%5)/4); l.material.color.copy(col); }); }

// ================= 全息天平（一分） =================
const scale=new THREE.Group(); scene.add(scale);
const SC={}; {
  const edgeBox=(w,h,d,col,op)=>{ const g=new THREE.Group(); const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),addMat(col,op*0.18)); const e=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w,h,d)),new THREE.LineBasicMaterial({color:col,transparent:true,opacity:op,blending:THREE.AdditiveBlending,depthWrite:false})); g.add(m,e); return g; };
  SC.post=edgeBox(0.8,16,0.8,CYAN,0.9); SC.post.position.y=8; scale.add(SC.post);
  SC.base=new THREE.Mesh(new THREE.CylinderGeometry(5,6,0.6,48,1,true),addMat(CYAN,0.08)); SC.base.position.y=0.3; scale.add(SC.base);
  SC.beam=new THREE.Group(); SC.beam.position.y=16; scale.add(SC.beam);
  SC.beamBox=edgeBox(30,0.6,0.8,WHITE.clone().lerp(CYAN,0.4),0.9); SC.beam.add(SC.beamBox);
  SC.pivot=glowSprite(GOLD,4,0.9,SC.beam);
  SC.pans=[]; for(const sx of [-1,1]){ const pan=new THREE.Group(); scene.add(pan); scale.add(pan);
    const dish=new THREE.Mesh(new THREE.CylinderGeometry(5.5,3.2,1.6,48,1,true),addMat(sx<0?GOLD:BLUE,0.12)); pan.add(dish);
    const rim=new THREE.Mesh(new THREE.TorusGeometry(5.5,0.08,8,64),addMat(sx<0?GOLD:BLUE,0.9)); rim.rotation.x=Math.PI/2; rim.position.y=0.8; pan.add(rim);
    const strings=[0,1,2].map(k=>fatLine([V(0,0,0),V(0,1,0)],WHITE.clone().lerp(CYAN,0.5),1.2,0.6,scale));
    SC.pans.push({pan,strings,sx}); }
  // 100 颗球：54 金（左盘）46 蓝（右盘）
  SC.balls=new THREE.InstancedMesh(new THREE.SphereGeometry(0.62,16,12),new THREE.MeshBasicMaterial({transparent:true,blending:THREE.AdditiveBlending,depthWrite:false}),100); scale.add(SC.balls);
  SC.ballCol=[]; for(let i=0;i<100;i++){ SC.balls.setColorAt(i,(i<54?GOLD:BLUE).clone().multiplyScalar(0.7)); }
  SC.drop=[...Array(100).keys()]; for(let i=99;i>0;i--){ const j=Math.floor(rnd()*(i+1)); [SC.drop[i],SC.drop[j]]=[SC.drop[j],SC.drop[i]]; }
  SC.slot=[]; let kl=0,kr=0; for(let i=0;i<100;i++){ const left=i<54; const k=left?kl++:kr++; const layer=Math.floor(k/14), j=k%14; const a=j/14*6.283+layer*0.4, rr=j<6?1.6:3.6; SC.slot.push(V(Math.cos(a)*rr*(j<6?1:1),0.9+layer*1.05,Math.sin(a)*rr)); }
  // 硬币
  SC.coin=new THREE.Group(); scene.add(SC.coin);
  const cm=new THREE.Mesh(new THREE.CylinderGeometry(3,3,0.35,64),addMat(GOLD,0.16)); cm.rotation.x=Math.PI/2; SC.coin.add(cm);
  const cr=new THREE.Mesh(new THREE.TorusGeometry(3,0.09,8,64),addMat(WHITE,0.9)); SC.coin.add(cr);
}
// n：已落下的球数；tilt：横梁倾角（弧度）
function setScale(op,n,tilt,t,coinOp=0){
  scale.visible=op>0.001; SC.coin.visible=coinOp>0.001; if(!scale.visible) return;
  SC.beam.rotation.z=tilt;
  const m=new THREE.Matrix4(), q=new THREE.Quaternion(), sv=V(1,1,1);
  SC.pans.forEach((p,i)=>{ const end=V(p.sx*14,0,0).applyAxisAngle(V(0,0,1),tilt).add(V(0,16,0)); const pos=end.clone().add(V(0,-9,0)); p.pan.position.copy(pos);
    p.strings.forEach((l,k)=>{ const a=k/3*6.283; setLine(l,[end,pos.clone().add(V(Math.cos(a)*5.3,0.8,Math.sin(a)*5.3))]); l.material.opacity=0.55*op; }); });
  for(let i=0;i<100;i++){ const di=SC.drop.indexOf(i); const lt=n-di; const pan=SC.pans[i<54?0:1].pan;
    if(lt<=0){ m.compose(V(0,-999,0),q,sv.clone().setScalar(0.0001)); }
    else { const u=clamp01(lt); const tgt=pan.position.clone().add(SC.slot[i]); const from=tgt.clone().add(V(0,22,0)); const y=from.y+(tgt.y-from.y)*(u*u); const bounce=u>=1?Math.max(0,0.6*Math.sin(Math.min(1,(lt-1)*3)*Math.PI)*(1-clamp01((lt-1)*3))):0;
      m.compose(V(tgt.x,y+bounce,tgt.z),q,sv.clone().setScalar(1)); }
    SC.balls.setMatrixAt(i,m); }
  SC.balls.instanceMatrix.needsUpdate=true; SC.balls.material.opacity=op;
  SC.coin.rotation.set(0,t*7,0);
}

// ================= 比分河道（吸收型马尔可夫链） =================
function buildChain(def){
  const g=new THREE.Group(); scene.add(g);
  const nodes=new Map(); const edges=new Map();
  const key=s=>s.join(',');
  const addNode=s=>{ const k=key(s); if(!nodes.has(k)) nodes.set(k,{s,k,pos:def.layout(s),term:def.terminal(s)}); return nodes.get(k); };
  const q=[def.start]; addNode(def.start); const seen=new Set([key(def.start)]);
  while(q.length){ const s=q.shift(); if(def.terminal(s)!==null) continue; const r=def.step(s);
    for(const [n,w] of [[r.win,1],[r.lose,0]]){ addNode(n); edges.set(key(s)+'>'+key(n),{a:key(s),b:key(n),w,count:0}); if(!seen.has(key(n))){ seen.add(key(n)); q.push(n);} } }
  // 模拟对局：确定性抽样，凑齐 nWin / nLose
  const walks=[]; let nw=0,nl=0, guard=0;
  while((nw<def.nWin||nl<def.nLose)&&guard++<400000){ let s=def.start; const path=[s]; let res=null, steps=0;
    while(res===null&&steps++<80){ const r=def.step(s); s=rnd()<def.p?r.win:r.lose; path.push(s); res=def.terminal(s); }
    if(res===null) continue; if(res&&nw<def.nWin){ walks.push({path,res}); nw++; } else if(!res&&nl<def.nLose){ walks.push({path,res}); nl++; } }
  for(let i=walks.length-1;i>0;i--){ const j=Math.floor(rnd()*(i+1)); [walks[i],walks[j]]=[walks[j],walks[i]]; }
  walks.forEach(wk=>{ wk.win=[]; for(let k=0;k+1<wk.path.length;k++){ wk.win.push(key(def.step(wk.path[k]).win)===key(wk.path[k+1])?1:0); } });
  walks.forEach(wk=>{ for(let k=0;k+1<wk.path.length;k++){ const e=edges.get(key(wk.path[k])+'>'+key(wk.path[k+1])); if(e) e.count++; } });
  const N=walks.length;
  const pos=s=>{ const n=nodes.get(key(s)); return n.term===true?def.winPool:n.term===false?def.losePool:n.pos; };
  // 边：世界宽度 ∝ 流量（经过这条边的对局占比）；终局边连到水库口
  const edgeObjs=[...edges.values()].map(e=>{ const pa=nodes.get(e.a).pos, nb=nodes.get(e.b); const pb=nb.term===true?def.winPool.clone().add(V(0,def.poolH,0)):nb.term===false?def.losePool.clone().add(V(0,def.poolH,0)):nb.pos;
    const f=e.count/N; const col=e.w?GOLD:BLUE; const mid=pa.clone().lerp(pb,0.5); const pts=[pa,mid.clone().add(V(0,0,0)),pb];
    const glow=fatLine(pts,col,Math.max(0.05,f*def.maxW*1.8),0.12,g,{world:true}); const core=fatLine(pts,col,Math.max(0.03,f*def.maxW),0.5,g,{world:true});
    return {...e,f,glow,core,pa,pb}; });
  const nodeObjs=[...nodes.values()].filter(n=>n.term===null).map(n=>{ const sp=glowSprite(CYAN,def.nodeSize*2.4,0.4,g); sp.position.copy(n.pos); const rg=ringSprite(WHITE.clone().lerp(CYAN,0.6),def.nodeSize,0.8,g); rg.position.copy(n.pos); return {n,sp,rg}; });
  // 水库：玻璃圆柱＋液面粒子
  const pools=[[def.winPool,GOLD,true],[def.losePool,BLUE,false]].map(([p,c,isWin])=>{ const grp=new THREE.Group(); grp.position.copy(p); g.add(grp);
    const glass=new THREE.Mesh(new THREE.CylinderGeometry(def.poolR,def.poolR,def.poolH,48,1,true),addMat(c,0.08)); glass.position.y=def.poolH/2; grp.add(glass);
    const rimT=new THREE.Mesh(new THREE.TorusGeometry(def.poolR,0.06,8,64),addMat(c,0.9)); rimT.rotation.x=Math.PI/2; rimT.position.y=def.poolH; grp.add(rimT);
    const rimB=new THREE.Mesh(new THREE.TorusGeometry(def.poolR,0.1,8,64),addMat(c,1)); rimB.rotation.x=Math.PI/2; grp.add(rimB);
    const liquid=new THREE.Mesh(new THREE.CylinderGeometry(def.poolR*0.97,def.poolR*0.97,1,48),addMat(c,0.22)); grp.add(liquid);
    const surface=new THREE.Mesh(new THREE.CircleGeometry(def.poolR*0.97,48),addMat(c,0.55)); surface.rotation.x=-Math.PI/2; grp.add(surface);
    const glow=glowSprite(c,def.poolR*4,0.3,grp); return {grp,glass,rimT,rimB,liquid,surface,glow,isWin,c}; });
  const flow=cloud(N,def.dot*1.5,12,g); const trail=cloud(N*3,def.dot*0.9,8,g);
  return {g,def,nodes,edgeObjs,nodeObjs,pools,walks,flow,trail,pos,N};
}
// 返回 {w,l}：已注入水库的胜 / 负对局数
function setChain(C,op,t,{spawn=0.02,stepDur=0.3,graphOp=1,flowOp=1,levelScale=1}={}){
  C.g.visible=op>0.001; if(!C.g.visible) return {w:0,l:0};
  C.nodeObjs.forEach((o,i)=>{ o.rg.material.opacity=op*graphOp*0.85; o.sp.material.opacity=op*graphOp*(0.32+0.12*Math.sin(t*3+i)); });
  C.edgeObjs.forEach(e=>{ e.core.material.opacity=op*graphOp*0.3; e.glow.material.opacity=op*graphOp*0.05; });
  let w=0,l=0;
  C.walks.forEach((wk,i)=>{
    const lt=t-i*spawn; const steps=wk.path.length-1; const f=lt/stepDur;
    if(lt<0||f>=steps+1.2){ cloudHide(C.flow,i); for(let k=0;k<3;k++) cloudHide(C.trail,i*3+k); if(f>=steps+1.2){ if(wk.res) w++; else l++; } return; }
    const at=ff=>{ ff=Math.max(0,ff); if(ff>=steps){ const end=C.pos(wk.path[steps]); const top=end.clone().add(V(0,C.def.poolH,0)); const u=clamp01((ff-steps)/1.2); return top.clone().lerp(end.clone().add(V((Math.sin(i*12.9)*0.5)*C.def.poolR,C.def.poolH*0.3,(Math.cos(i*7.1)*0.5)*C.def.poolR)),u); }
      const k=Math.floor(ff), u=easeIO(ff-k); const a=C.pos(wk.path[k]); let b=C.pos(wk.path[k+1]); const tb=C.nodes.get(wk.path[k+1].join(',')).term; if(tb!==null) b=b.clone().add(V(0,C.def.poolH,0));
      const p=a.clone().lerp(b,u); const jit=0.18*C.def.dot*Math.sin(i*3.1+ff*9); p.x+=jit; p.z+=0.25*Math.cos(i*5.3); return p; };
    const p=at(f); const col=f>=steps?(wk.res?GOLD:BLUE):WHITE.clone().lerp(wk.win[Math.min(steps-1,Math.max(0,Math.floor(f)))]?GOLD:BLUE,0.6);
    cloudSet(C.flow,i,p.x,p.y,p.z,col.r,col.g,col.b,op*flowOp);
    for(let k=0;k<3;k++){ const q=at(f-(k+1)*0.07); cloudSet(C.trail,i*3+k,q.x,q.y,q.z,col.r,col.g,col.b,0.4*(1-k/3)*op*flowOp); }
  });
  cloudDone(C.flow); cloudDone(C.trail);
  // 水位：注入数 / 总对局数 × 池高
  C.pools.forEach(p=>{ const n=p.isWin?w:l; const h=Math.max(0.02,(n/C.N)*C.def.poolH*levelScale);
    p.liquid.scale.y=h; p.liquid.position.y=h/2; p.surface.position.y=h; p.liquid.material.opacity=0.22*op; p.surface.material.opacity=0.55*op*(n>0?1:0);
    p.glass.material.opacity=0.08*op; p.rimT.material.opacity=0.9*op; p.rimB.material.opacity=op; p.glow.material.opacity=0.3*op; p.glow.position.y=h; });
  return {w,l};
}
// 一局（钻石格：右下＝他赢这一分，左下＝输）。平分后在 40 平 / 占先之间打转
const sx=3.2, sy=2.5;
const GAME=buildChain({p:0.54,start:[0,0],nWin:720,nLose:480,dot:0.5,nodeSize:1.6,maxW:3.2,poolR:3.2,poolH:9,
  step:s=>{ const [a,b]=s; if(a>=3&&b>=3){ if(a===b) return {win:[4,3],lose:[3,4]}; return a>b?{win:[5,3],lose:[3,3]}:{win:[3,3],lose:[3,5]}; } return {win:[a+1,b],lose:[a,b+1]}; },
  terminal:s=>{ const [a,b]=s; if(a>=4&&a-b>=2) return true; if(b>=4&&b-a>=2) return false; return null; },
  layout:s=>{ const [a,b]=s; if(a>=3&&b>=3) return V((a-b)*sx*1.1,-6*sy-(a!==b?sy*1.1:0),0); return V((a-b)*sx,-(a+b)*sy,0); },
  winPool:V(6.2*sx,-11.5*sy,0), losePool:V(-6.2*sx,-11.5*sy,0)});
GAME.g.position.set(0,15,0);
// 一盘：先拿 6 局净胜 2 局；6-6 抢七（独立同分布下抢七胜率 62.4%，在 6-6 节点上一步决定）
const gx=2.1, gy=1.55;
const SET=buildChain({p:0.599,start:[0,0],nWin:610,nLose:190,dot:0.45,nodeSize:1.1,maxW:2.4,poolR:3.4,poolH:10,
  step:s=>{ const [a,b]=s; if(a===6&&b===6) return {win:[7,6],lose:[6,7]}; return {win:[a+1,b],lose:[a,b+1]}; },
  terminal:s=>{ const [a,b]=s; if(a===7) return true; if(b===7) return false; if(a>=6&&a-b>=2) return true; if(b>=6&&b-a>=2) return false; return null; },
  layout:s=>{ const [a,b]=s; return V((a-b)*gx,-(a+b)*gy,0); },
  winPool:V(9*gx,-16*gy,0), losePool:V(-9*gx,-16*gy,0)});
SET.g.position.set(0,15,0);
// 一场：五盘三胜（盘胜率 76.3%）
const MATCH=buildChain({p:0.763,start:[0,0],nWin:546,nLose:54,dot:0.55,nodeSize:2.2,maxW:3.6,poolR:3.6,poolH:10,
  step:s=>{ const [a,b]=s; return {win:[a+1,b],lose:[a,b+1]}; },
  terminal:s=>{ const [a,b]=s; if(a===3) return true; if(b===3) return false; return null; },
  layout:s=>{ const [a,b]=s; return V((a-b)*4.6,-(a+b)*3.6,0); },
  winPool:V(12.5,-19.5,0), losePool:V(-12.5,-19.5,0)});
MATCH.g.position.set(0,12,0);

// ================= S 曲线全息图 =================
function pGame(p){ const q=1-p; return Math.pow(p,4)*(1+4*q+10*q*q)+20*Math.pow(p,3)*Math.pow(q,3)*p*p/(1-2*p*q); }
function pTB(p){ const memo=new Map(); const f=(a,b)=>{ if(a>=7&&a-b>=2) return 1; if(b>=7&&b-a>=2) return 0; if(a>=6&&b>=6&&a===b) return p*p/(p*p+(1-p)*(1-p)); const k=a+','+b; if(memo.has(k)) return memo.get(k); const v=p*f(a+1,b)+(1-p)*f(a,b+1); memo.set(k,v); return v; }; return f(0,0); }
function pSet(p){ const g=pGame(p), tb=pTB(p); const memo=new Map(); const f=(a,b)=>{ if(a===7) return 1; if(b===7) return 0; if(a>=6&&a-b>=2) return 1; if(b>=6&&b-a>=2) return 0; if(a===6&&b===6) return tb; const k=a+','+b; if(memo.has(k)) return memo.get(k); const v=g*f(a+1,b)+(1-g)*f(a,b+1); memo.set(k,v); return v; }; return f(0,0); }
function pMatch(p,best){ const s=pSet(p), need=best===5?3:2; const f=(a,b)=>a===need?1:b===need?0:s*f(a+1,b)+(1-s)*f(a,b+1); return f(0,0); }
const CH={W:44,H:26,x0:0.40,x1:0.60};   // 横轴每分胜率 40%–60%，纵轴 0–100%
const chart=new THREE.Group(); scene.add(chart);
const chartX=p=>(p-CH.x0)/(CH.x1-CH.x0)*CH.W-CH.W/2, chartY=v=>v*CH.H;
{ const gc=WHITE.clone().lerp(CYAN,0.6);
  const panel=new THREE.Mesh(new THREE.PlaneGeometry(CH.W+4,CH.H+4),addMat(new THREE.Color(0.05,0.12,0.25),0.18)); panel.position.set(0,CH.H/2,-0.3); chart.add(panel);
  for(let k=0;k<=10;k++){ const y=chartY(k/10); fatLine([V(-CH.W/2,y,0),V(CH.W/2,y,0)],gc,k%5===0?1.4:0.8,k%5===0?0.35:0.14,chart); }
  for(let k=0;k<=20;k++){ const x=chartX(CH.x0+k*0.01); fatLine([V(x,0,0),V(x,CH.H,0)],gc,k%5===0?1.4:0.8,k%5===0?0.3:0.1,chart); } }
const CURVES=[ ['point',p=>p,WHITE.clone().lerp(CYAN,0.5)], ['game',pGame,CYAN], ['set',pSet,GOLD.clone().lerp(WHITE,0.25)], ['match',p=>pMatch(p,5),GOLD] ].map(([k,f,c])=>{
  const pts=[]; for(let i=0;i<=120;i++){ const p=CH.x0+(CH.x1-CH.x0)*i/120; pts.push(V(chartX(p),chartY(f(p)),0.05)); }
  const glow=fatLine(pts,c,9,0.18,chart), core=fatLine(pts,c,3,0.95,chart); const head=glowSprite(c,3,0.9,chart); return {k,f,c,pts,glow,core,head}; });
const scanLine=fatLine([V(0,0,0.1),V(0,CH.H,0.1)],GOLD,2.5,0.9,chart,{dashed:true,dash:0.6});
CURVES.forEach(c=>{ c.core.userData.curve=c.glow.userData.curve=true; }); scanLine.userData.curve=true;
chart.children.forEach(o=>{ if(o.material&&o.material.isLineMaterial&&!o.userData.curve) o.userData.op0=o.material.opacity; });
const scanDots=CURVES.map(c=>{ const s=glowSprite(c.c,4,1,chart); const r=ringSprite(c.c,2.2,1,chart); return {s,r}; });
// draw[k] 0..1：每条曲线画到哪儿；scanP：扫描线所在胜率（null 不显示）
function setChart(op,draw,scanP,scanOp=1){
  chart.visible=op>0.001; if(!chart.visible) return;
  chart.children.forEach(o=>{ if(o.userData.op0!==undefined) o.material.opacity=o.userData.op0*op; });
  CURVES.forEach((c,i)=>{ const u=clamp01(draw[i]); const n=Math.max(2,Math.round(u*120)+1);
    setLine(c.core,c.pts.slice(0,n)); setLine(c.glow,c.pts.slice(0,n)); c.core.material.opacity=0.95*op*(u>0?1:0); c.glow.material.opacity=0.18*op*(u>0?1:0);
    c.head.position.copy(c.pts[n-1]); c.head.material.opacity=(u>0&&u<1)?op:0; });
  if(scanP!==null&&scanP!==undefined){ const x=chartX(scanP); setLine(scanLine,[V(x,0,0.1),V(x,CH.H,0.1)]); scanLine.material.opacity=0.9*op*scanOp;
    CURVES.forEach((c,i)=>{ const y=chartY(c.f(scanP)); const on=draw[i]>=1?op*scanOp:0; scanDots[i].s.position.set(x,y,0.15); scanDots[i].r.position.set(x,y,0.15); scanDots[i].s.material.opacity=on; scanDots[i].r.material.opacity=on; }); }
  else { scanLine.material.opacity=0; scanDots.forEach(d=>{ d.s.material.opacity=0; d.r.material.opacity=0; }); }
}

// ================= 双影柱（模型 vs 真实） =================
const barsG=new THREE.Group(); scene.add(barsG);
function makeBar(){ const g=new THREE.Group(); barsG.add(g);
  const box=new THREE.Mesh(new THREE.BoxGeometry(1,1,1),addMat(GOLD,0.2)); g.add(box);
  const edges=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1,1,1)),new THREE.LineBasicMaterial({color:GOLD,transparent:true,opacity:0.9,blending:THREE.AdditiveBlending,depthWrite:false})); g.add(edges);
  const ghost=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1,1,1)),new THREE.LineDashedMaterial({color:CYAN,dashSize:0.4,gapSize:0.3,transparent:true,opacity:0.9,blending:THREE.AdditiveBlending,depthWrite:false})); g.add(ghost);
  const ghostFill=new THREE.Mesh(new THREE.BoxGeometry(1,1,1),addMat(CYAN,0.07)); g.add(ghostFill);
  const cap=glowSprite(GOLD,6,0.8,g); const gcap=new THREE.Mesh(new THREE.PlaneGeometry(1,1),addMat(CYAN,0.6)); gcap.rotation.x=-Math.PI/2; g.add(gcap);
  const base=ringSprite(GOLD,5,0.6,g);
  const pc=cloud(160,0.32,5,g); const ph=[...Array(160)].map(()=>[rnd(),rnd(),rnd()]);
  return {g,box,edges,ghost,ghostFill,cap,gcap,base,pc,ph}; }
const BARS=[0,1,2,3,4,5].map(()=>makeBar());
// h 实心柱高（null 不显示）；gh 虚线「模型」柱高（null 不显示）；drop 0..1 实心柱从上方落下
function setBar(b,x,h,gh,op,{w=4,col=GOLD,t=0,drop=1,gcol=CYAN}={}){
  b.g.visible=op>0.001; if(!b.g.visible) return; b.g.position.set(x,0,0);
  const showS=h!==null&&h>0.001, showG=gh!==null&&gh>0.001;
  b.box.visible=b.edges.visible=b.cap.visible=b.pc.visible=showS; b.ghost.visible=b.ghostFill.visible=b.gcap.visible=showG;
  if(showG){ b.ghost.scale.set(w*1.08,gh,w*1.08); b.ghost.position.y=gh/2; b.ghostFill.scale.set(w*1.08,gh,w*1.08); b.ghostFill.position.y=gh/2; b.ghost.material.opacity=0.9*op; b.ghostFill.material.opacity=0.07*op; b.ghost.material.color.copy(gcol);
    b.gcap.scale.set(w*1.08,w*1.08,1); b.gcap.position.y=gh; b.gcap.material.opacity=0.35*op; b.gcap.material.color.copy(gcol); b.ghost.computeLineDistances(); }
  if(showS){ const yoff=(1-easeOutBack(drop))*30; b.box.scale.set(w,h,w); b.box.position.y=h/2+yoff; b.edges.scale.set(w,h,w); b.edges.position.y=h/2+yoff;
    b.box.material.color.copy(col); b.edges.material.color.copy(col); b.cap.material.color.copy(col); b.box.material.opacity=0.1*op; b.edges.material.opacity=0.85*op; b.cap.position.set(0,h+yoff,0); b.cap.scale.setScalar(w*1.6); b.cap.material.opacity=0.45*op;
    b.ph.forEach((p,i)=>{ const yy=((p[0]+t*0.25)%1)*h; cloudSet(b.pc,i,(p[1]-0.5)*w*0.9,yy+yoff,(p[2]-0.5)*w*0.9,col.r,col.g,col.b,op*0.45*(1-yy/h*0.6)); }); cloudDone(b.pc); }
  b.base.material.color.copy(showS?col:gcol); b.base.scale.setScalar(w*1.9); b.base.material.opacity=0.5*op; b.base.position.y=0.02;
}
function hideBars(){ BARS.forEach(b=>b.g.visible=false); }

// ================= 2019 温网中央球场 =================
const court=new THREE.Group(); scene.add(court);
const CL=23.77/2, DW=10.97/2, SW=8.23/2, SL=6.40;
{ const lc=WHITE.clone().lerp(CYAN,0.5); const cl=(a,b)=>fatLine([a,b],lc,2.2,0.75,court);
  const surf=new THREE.Mesh(new THREE.PlaneGeometry(DW*2+8,CL*2+12),new THREE.MeshBasicMaterial({color:0x0b2a1a,transparent:true,opacity:0.6,depthWrite:false})); surf.rotation.x=-Math.PI/2; court.add(surf);
  const y=0.02; for(const z of [-CL,CL]) cl(V(-DW,y,z),V(DW,y,z)); for(const x of [-DW,DW,-SW,SW]) cl(V(x,y,-CL),V(x,y,CL));
  for(const z of [-SL,SL]) cl(V(-SW,y,z),V(SW,y,z)); cl(V(0,y,-SL),V(0,y,SL));
  const net=new THREE.Mesh(new THREE.PlaneGeometry(DW*2+1.8,0.95),addMat(WHITE,0.12)); net.position.y=0.48; court.add(net); fatLine([V(-DW-0.9,0.95,0),V(DW+0.9,0.95,0)],WHITE,2,0.8,court);
  // 看台：两层环形光点
  const st=cloud(6000,0.25,4,court,0.5); for(let i=0;i<6000;i++){ const a=rnd()*6.283, r=24+rnd()*12, h=1+(r-24)*0.8+rnd()*0.5; const k=0.25+rnd()*0.5; cloudSet(st,i,Math.cos(a)*r*0.75,h,Math.sin(a)*r,k*0.5,k*0.9,k*0.6,1); } cloudDone(st); }
// 两个容器：分别装两人的全场赢分（每颗粒子 = 1 分）
const VES=[GOLD,BLUE].map((c,i)=>{ const grp=new THREE.Group(); court.add(grp); grp.position.set(i===0?-10:10,0,-4);
  const glass=new THREE.Mesh(new THREE.CylinderGeometry(2.6,2.6,14,48,1,true),addMat(c,0.08)); glass.position.y=7; grp.add(glass);
  const rim=new THREE.Mesh(new THREE.TorusGeometry(2.6,0.06,8,64),addMat(c,0.9)); rim.rotation.x=Math.PI/2; rim.position.y=14; grp.add(rim);
  const pc=cloud(230,0.42,8,grp); const slots=[]; for(let k=0;k<230;k++){ const layer=Math.floor(k/16), j=k%16, a=j/16*6.283+layer*0.37, r=j<5?0.9:2.0; slots.push(V(Math.cos(a)*r,0.35+layer*0.42,Math.sin(a)*r)); }
  const beam=new THREE.Mesh(new THREE.CylinderGeometry(3.2,4.2,60,32,1,true),addMat(GOLD,0)); beam.position.y=30; grp.add(beam);
  return {grp,glass,rim,pc,slots,beam,c}; });
function setVessels(op,n0,n1,beam1=0){
  VES.forEach((v,i)=>{ const n=i===0?n0:n1; v.glass.material.opacity=0.09*op; v.rim.material.opacity=0.9*op;
    for(let k=0;k<230;k++){ if(k<n){ const s=v.slots[k]; cloudSet(v.pc,k,s.x,s.y,s.z,v.c.r,v.c.g,v.c.b,op); } else cloudHide(v.pc,k); } cloudDone(v.pc);
    v.beam.material.opacity=(i===1?beam1:0)*0.1*op; });
}

// ---------- post ----------
const composer=new EffectComposer(renderer,new THREE.WebGLRenderTarget(W,H,{samples:4,type:THREE.HalfFloatType}));
composer.addPass(new RenderPass(scene,camera));
const bloom=new UnrealBloomPass(new THREE.Vector2(W/2,H/2),0.65,0.5,0.3); composer.addPass(bloom);
const finalPass=new ShaderPass({uniforms:{tDiffuse:{value:null},uT:{value:0},uFlash:{value:0},uFade:{value:1},uCA:{value:0.0015},uGlitch:{value:0},uShake:{value:0},uZoom:{value:0}},
  vertexShader:`varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader:`uniform sampler2D tDiffuse; uniform float uT,uFlash,uFade,uCA,uGlitch,uShake,uZoom; varying vec2 vUv;
   float h(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453); }
   void main(){ vec2 uv=vUv; uv+=vec2(sin(uT*91.)*0.003,cos(uT*77.)*0.003)*uShake;
     if(uGlitch>0.){ float band=floor(uv.y*28.+floor(uT*24.)); float o=(h(vec2(band,floor(uT*30.)))-0.5)*0.06*uGlitch*step(0.6,h(vec2(band*1.7,floor(uT*30.)))); uv.x+=o; }
     vec2 c=uv-0.5; vec3 col=vec3(0.);
     if(uZoom>0.){ for(int k=0;k<8;k++){ float s=1.0-uZoom*0.06*float(k); col+=texture2D(tDiffuse,0.5+c*s).rgb; } col/=8.; }
     else { float ca=uCA+uGlitch*0.01; col=vec3(texture2D(tDiffuse,uv+c*ca).r,texture2D(tDiffuse,uv).g,texture2D(tDiffuse,uv-c*ca).b); }
     float vig=smoothstep(1.05,0.3,length(c*vec2(1.0,0.85))); col*=mix(0.55,1.0,vig);
     col+=(h(uv*vec2(1920.,1080.)+uT)-0.5)*0.03; col=mix(col,vec3(1.),uFlash); col*=uFade; gl_FragColor=vec4(col,1.); }`});
composer.addPass(finalPass); composer.addPass(new OutputPass());

// ---------- anchors for overlay ----------
const anchors={};
function proj(name,v,group){ const w=v.clone(); if(group) group.localToWorld(w); const p=w.project(camera); anchors[name]=[(p.x*0.5+0.5)*W,(1-(p.y*0.5+0.5))*H,(p.z<1&&p.z>-1)?1:0]; }
const val=(n,v)=>{anchors[n]=v;};
function cam(pos,tgt,fov,up){ camera.up.set(...(up||[0,1,0])); camera.position.copy(pos); camera.fov=fov; camera.lookAt(tgt); camera.updateProjectionMatrix(); camera.updateMatrixWorld(true); }

const S={THREE,V,cam,proj,val,ease,easeIO,easeOutBack,clamp01,setMorph,morphPos,ball,ballMat,ballGlow,flare,ballTrail,shock,shock2,setRays,setScale,SC,GAME,SET,MATCH,setChain,
  chart,setChart,CURVES,chartX,chartY,CH,BARS,setBar,hideBars,barsG,court,VES,setVessels,bloom,finalPass,gridMat,grid,skyMat,stars,dust,setLine,pGame,pSet,pMatch,GOLD,CYAN,WHITE,BLUE,BALLC,RED,DIMB,GAL_N};
window.__S=S;
function hideAll(){
  morph.visible=false; ball.visible=false; ballGlow.visible=false; flare.material.opacity=0; ballTrail.visible=false; shock.material.opacity=0; shock2.material.opacity=0; shock.material.color.copy(GOLD); setRays(0);
  scale.visible=false; SC.coin.visible=false; GAME.g.visible=false; SET.g.visible=false; MATCH.g.visible=false;
  [GAME,SET,MATCH].forEach(C=>{ C.g.scale.setScalar(1); }); GAME.g.position.set(0,15,0); SET.g.position.set(0,15,0); MATCH.g.position.set(0,12,0);
  chart.visible=false; hideBars(); barsG.position.set(0,0,0); court.visible=false;
  gridMat.uniforms.uOp.value=1; grid.visible=true; grid.position.y=-40; gridMat.uniforms.uS.value=4; skyMat.uniforms.uWarm.value=0; skyMat.uniforms.uOp.value=1; stars.material.uniforms.uOp.value=1; dust.material.uniforms.uOp.value=1;
}
window.renderAt=function(t,noRender){
  for(const k in anchors) delete anchors[k];
  hideAll();
  allClouds.forEach(c=>c.material.uniforms.uT.value=t);
  const fp=finalPass.uniforms; fp.uT.value=t; fp.uFlash.value=0; fp.uFade.value=1; fp.uGlitch.value=0; fp.uShake.value=0; fp.uZoom.value=0; bloom.strength=0.65;
  dust.rotation.y=t*0.01;
  for(const s of SHOTS){ if(t>=s.t0&&t<s.t1){ s.fn(S,t-s.t0,s.t1-s.t0,t); break; } }
  if(!noRender) composer.render();
  return JSON.stringify(anchors);
};
document.fonts.ready.then(()=>{ window.READY=true; });
