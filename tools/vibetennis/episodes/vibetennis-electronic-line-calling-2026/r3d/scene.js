// vibetennis 第 2 集《电子司线，真的准吗？》3D 场景。
// 画风沿用第 1 集（深蓝底、发光网格、全息球场、星点看台、bloom＋暗角＋颗粒）。
// 两个尺度：球场（单位：米，原点在场地中心）和「实验台」lab（单位：厘米，挂在 y=1000 的高空）。
// 所有数字的出处见 papers/vibetennis-electronic-line-calling-2026/sources.md。
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

const Q=new URLSearchParams(location.search);
const W=+(Q.get('w')||1920), H=+(Q.get('h')||1080);
const renderer=new THREE.WebGLRenderer({antialias:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
renderer.setPixelRatio(1); renderer.setSize(W,H); renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.0;
document.body.appendChild(renderer.domElement);
const scene=new THREE.Scene(); scene.background=new THREE.Color(0x02040a);
scene.fog=new THREE.FogExp2(0x02040a,0.0018);
{ const sky=new THREE.Mesh(new THREE.SphereGeometry(3200,48,24),new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,fog:false,
  vertexShader:`varying vec3 vD; void main(){ vD=normalize(position); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,
  fragmentShader:`varying vec3 vD; void main(){ float h=vD.y; float g=exp(-abs(h+0.02)*9.0); vec3 top=vec3(0.006,0.01,0.024); vec3 hz=vec3(0.018,0.032,0.075); vec3 vi=vec3(0.04,0.022,0.07); float side=0.5+0.5*vD.x; gl_FragColor=vec4(top+hz*g+vi*g*g*side*0.6,1.);} `}));
  scene.add(sky); }
const camera=new THREE.PerspectiveCamera(40,W/H,0.01,6000);

// ---------- palette ----------
const GOLD=new THREE.Color(1.0,0.66,0.22), CYAN=new THREE.Color(0.38,0.86,1.0), WHITE=new THREE.Color(1,1,1),
      GREEN=new THREE.Color(0.35,1.0,0.6), AMBER=new THREE.Color(1.0,0.55,0.12), RED=new THREE.Color(1.0,0.3,0.3), BALLC=new THREE.Color(0.85,1.0,0.25);
let seed=7654321; const rnd=()=>{seed=(seed*16807)%2147483647;return seed/2147483647;};
const V=(x,y,z)=>new THREE.Vector3(x,y,z);

// ---------- helpers ----------
const lineMats=[]; const flowMats=[]; const eyeFlowMats=[];
function lineMat(color,width,opacity,dashed=false,dash=1){
  const m=new LineMaterial({color,linewidth:width,transparent:true,opacity,depthWrite:false,blending:THREE.AdditiveBlending,worldUnits:false,dashed,dashSize:dash,gapSize:dash*0.7});
  m.resolution.set(W,H); lineMats.push(m); return m;
}
function fatLine(pts,color,width,opacity=1,group=scene,dashed=false,dash=1){
  const g=new LineGeometry(); g.setPositions(pts.flatMap(p=>[p.x,p.y,p.z]));
  const l=new Line2(g,lineMat(color,width,opacity,dashed,dash)); l.computeLineDistances(); group.add(l); return l;
}
function setLine(l,pts){ l.geometry.setPositions(pts.flatMap(p=>[p.x,p.y,p.z])); l.computeLineDistances(); }
function addMat(color,opacity){return new THREE.MeshBasicMaterial({color,transparent:true,opacity,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide});}
const glowTex=(()=>{ const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d');
  const gr=g.createRadialGradient(64,64,0,64,64,64); gr.addColorStop(0,'rgba(255,255,255,1)'); gr.addColorStop(0.15,'rgba(255,255,255,0.6)'); gr.addColorStop(0.45,'rgba(255,255,255,0.12)'); gr.addColorStop(1,'rgba(255,255,255,0)');
  g.fillStyle=gr; g.fillRect(0,0,128,128); return new THREE.CanvasTexture(c); })();
function glowSprite(color,size,op=1){ const s=new THREE.Sprite(new THREE.SpriteMaterial({map:glowTex,color,transparent:true,opacity:op,blending:THREE.AdditiveBlending,depthWrite:false})); s.scale.set(size,size,1); return s; }
const dotTex=(()=>{const c=document.createElement('canvas');c.width=c.height=64;const g=c.getContext('2d');const gr=g.createRadialGradient(32,32,0,32,32,32);gr.addColorStop(0,'rgba(255,255,255,1)');gr.addColorStop(0.3,'rgba(255,255,255,0.5)');gr.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=gr;g.fillRect(0,0,64,64);return new THREE.CanvasTexture(c);})();
function points(arr,colors,size,opacity=1,group=scene,maxPx=7){
  const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(arr,3)); g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
  const m=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uSize:{value:size},uOp:{value:opacity},uMax:{value:maxPx},uTex:{value:dotTex},uH:{value:H}},
   vertexShader:`attribute vec3 color; varying vec3 vC; varying float vF; uniform float uSize,uMax,uH; void main(){ vC=color; vec4 mv=modelViewMatrix*vec4(position,1.); float px=uSize*uH*0.5*projectionMatrix[1][1]/-mv.z; vF=clamp(px/max(px,uMax),0.15,1.0); gl_PointSize=clamp(px,1.0,uMax); gl_Position=projectionMatrix*mv; }`,
   fragmentShader:`uniform float uOp; varying vec3 vC; varying float vF; void main(){ float d=length(gl_PointCoord-0.5); float ta=exp(-d*d*16.0)*(1.0-smoothstep(0.42,0.5,d)); gl_FragColor=vec4(vC*ta*uOp*vF, ta*uOp*vF);} `});
  const p=new THREE.Points(g,m); group.add(p); return p;
}

// ---------- starfield & dust ----------
{ const a=[],c=[]; for(let i=0;i<9000;i++){ const r=1500+rnd()*2500, th=rnd()*Math.PI*2, ph=Math.acos(2*rnd()-1); a.push(r*Math.sin(ph)*Math.cos(th), Math.abs(r*Math.cos(ph))*0.9-200, r*Math.sin(ph)*Math.sin(th)); const k=0.4+rnd()*0.6; const w=rnd(); c.push(k*(0.7+0.3*w),k*(0.75+0.2*w),k); }
  points(a,c,7,0.9,scene,3); }
{ const a=[],c=[]; for(let i=0;i<4000;i++){ a.push((rnd()-0.5)*160,rnd()*50,(rnd()-0.5)*160); const k=0.25+rnd()*0.5; c.push(k*0.6,k*0.8,k);} points(a,c,0.06,0.6,scene,4); }

// ---------- grid floor ----------
const gridMat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,uniforms:{uOp:{value:1},uC:{value:new THREE.Color(0.25,0.55,1.0)}},
 vertexShader:`varying vec3 vW; void main(){ vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }`,
 fragmentShader:`varying vec3 vW; uniform float uOp; uniform vec3 uC;
  float grid(vec2 p,float s){ vec2 g=abs(fract(p/s-0.5)-0.5)/fwidth(p/s); return 1.-min(min(g.x,g.y),1.); }
  void main(){ float d=length(vW.xz); float g=grid(vW.xz,2.0)*0.35+grid(vW.xz,10.0)*0.6; float f=exp(-d*0.006); gl_FragColor=vec4(uC*g*f, g*f*0.55*uOp); }`});
const grid=new THREE.Mesh(new THREE.PlaneGeometry(4000,4000),gridMat); grid.rotation.x=-Math.PI/2; grid.position.y=-0.02; scene.add(grid);

// ================= TENNIS COURT (metres) =================
const tennis=new THREE.Group(); scene.add(tennis);
const L=23.77/2, DW=10.97/2, SW=8.23/2, SL=6.40, BR=0.0335;
const surfMat=new THREE.MeshBasicMaterial({color:0x0a1a33,transparent:true,opacity:0.55,depthWrite:false});
const surf=new THREE.Mesh(new THREE.PlaneGeometry(DW*2+7,L*2+12),surfMat); surf.rotation.x=-Math.PI/2; surf.position.y=0.005; tennis.add(surf);
const courtLines=new THREE.Group(); tennis.add(courtLines);
const cl=(a,b,w=2.2)=>fatLine([a,b],WHITE.clone().lerp(CYAN,0.55),w,0.72,courtLines);
const y0=0.02;
cl(V(-DW,y0,-L),V(DW,y0,-L)); cl(V(-DW,y0,L),V(DW,y0,L)); cl(V(-DW,y0,-L),V(-DW,y0,L)); cl(V(DW,y0,-L),V(DW,y0,L));
cl(V(-SW,y0,-L),V(-SW,y0,L)); cl(V(SW,y0,-L),V(SW,y0,L)); cl(V(-SW,y0,-SL),V(SW,y0,-SL)); cl(V(-SW,y0,SL),V(SW,y0,SL)); cl(V(0,y0,-SL),V(0,y0,SL));
cl(V(0,y0,-L),V(0,y0,-L+0.10)); cl(V(0,y0,L),V(0,y0,L-0.10));
// near baseline as a real 10 cm white strip (world units) for close-ups — lines are part of the court
const baseStripMat=new THREE.MeshBasicMaterial({color:new THREE.Color(0.42,0.50,0.60),transparent:true,opacity:0.0,depthWrite:false});
const baseStrip=new THREE.Mesh(new THREE.PlaneGeometry(DW*2,0.10),baseStripMat); baseStrip.rotation.x=-Math.PI/2; baseStrip.position.set(0,0.008,L-0.05); tennis.add(baseStrip);
// net
const net=new THREE.Group(); tennis.add(net);
fatLine([V(-DW-0.9,1.07,0),V(0,0.914,0),V(DW+0.9,1.07,0)],WHITE,2.6,0.85,net);
for(let x=-DW-0.9;x<=DW+0.91;x+=0.45) fatLine([V(x,0,0),V(x,0.914+0.156*Math.abs(x)/(DW+0.9),0)],CYAN,1,0.35,net);
for(let y=0.15;y<0.9;y+=0.15) fatLine([V(-DW-0.9,y,0),V(DW+0.9,y,0)],CYAN,1,0.3,net);
fatLine([V(-DW-0.9,0,0),V(-DW-0.9,1.07,0)],WHITE,3,1,net); fatLine([V(DW+0.9,0,0),V(DW+0.9,1.07,0)],WHITE,3,1,net);
// stadium bowl
function bowl(group,ax,az,tiers,rows,cnt,warm){
  const a=[],c=[];
  for(let t=0;t<tiers;t++) for(let r=0;r<rows;r++){
    const k=t*rows+r, rx=ax+k*0.9, rz=az+k*0.9, y=1.2+k*0.62+t*1.5; const n=Math.floor(cnt*(1+k*0.04));
    for(let i=0;i<n;i++){ const th=(i/n)*Math.PI*2+rnd()*0.01; if(rnd()<0.12) continue;
      const cx=Math.cos(th), sz=Math.sin(th); const ex=Math.sign(cx)*Math.pow(Math.abs(cx),0.6), ez=Math.sign(sz)*Math.pow(Math.abs(sz),0.6);
      a.push(rx*ex,y,rz*ez); const b=(0.25+0.75*rnd()*rnd())*1.6; if(rnd()<warm) c.push(b,b*0.75,b*0.45); else c.push(b*0.55,b*0.8,b); }
  }
  const p=points(a,c,0.2,1,group,6);
  for(let t=0;t<=tiers;t++){ const k=t*rows, rx=ax+k*0.9, rz=az+k*0.9, y=1.0+k*0.62+t*1.5; const pts=[];
    for(let i=0;i<=160;i++){const th=i/160*Math.PI*2; const cx=Math.cos(th), sz=Math.sin(th); pts.push(V(rx*Math.sign(cx)*Math.pow(Math.abs(cx),0.6),y,rz*Math.sign(sz)*Math.pow(Math.abs(sz),0.6)));}
    fatLine(pts,CYAN,1.3,0.22,group); }
  return p;
}
const tBowl=bowl(tennis,15,24,3,9,260,0.55);
// chairs: chair umpire (net side) and an empty line-judge chair (behind near baseline)
const chairs=new THREE.Group(); tennis.add(chairs);
function chair(x,z,h,color){ const g=new THREE.Group(); g.position.set(x,0,z); chairs.add(g);
  const e=(w,hh,d,y)=>{ const m=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w,hh,d)),new THREE.LineBasicMaterial({color,transparent:true,opacity:0.9})); m.position.y=y; g.add(m); return m; };
  e(0.6,0.08,0.6,h); e(0.6,0.6,0.08,h+0.3).position.z=-0.26; for(const [dx,dz] of [[-0.27,-0.27],[0.27,-0.27],[-0.27,0.27],[0.27,0.27]]){ const l=fatLine([V(dx,0,dz),V(dx,h,dz)],color,1.6,0.8,g); }
  return g; }
const umpChair=chair(DW+1.4,0,1.8,CYAN); umpChair.rotation.y=-Math.PI/2;
const umpGlow=glowSprite(GOLD,3,0); umpGlow.position.set(DW+1.4,2.4,0); chairs.add(umpGlow);
const ljChair=chair(-DW-1.8,L+3.2,0.5,WHITE.clone().lerp(CYAN,0.3)); ljChair.rotation.y=Math.PI*0.5;

// ---------- 12 tracking cameras on the stadium rim ----------
const camRigs=[]; const rigGroup=new THREE.Group(); scene.add(rigGroup);
const CAMPOS=[]; for(const s of [-1,1]) for(const z of [-L*0.75,0,L*0.75]) CAMPOS.push(V(s*(DW+11),11+Math.abs(z)*0.12,z));
for(const s of [-1,1]) for(const x of [-6.5,0,6.5]) CAMPOS.push(V(x,13,s*(L+14)));
for(const p of CAMPOS){ const g=new THREE.Group(); g.position.copy(p); rigGroup.add(g);
  const box=new THREE.Mesh(new THREE.BoxGeometry(0.7,0.55,1.2),new THREE.MeshBasicMaterial({color:0x1a2b4a})); g.add(box);
  const edge=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(0.7,0.55,1.2)),new THREE.LineBasicMaterial({color:CYAN,transparent:true,opacity:1})); g.add(edge);
  // 相机是被动拍摄、不发光的：只在机身顶部留一个小状态灯，不画镜头光晕（所有者 2026-10-30 指出光晕不符合事实）
  const lens=glowSprite(CYAN,0.32); lens.position.set(0,0.34,0.45); g.add(lens);
  const tgt=V(p.x*0.15,0,p.z*0.15); g.lookAt(tgt); g.rotateY(Math.PI); // box -z faces target after flip
  // frustum (towards its half of the court)
  const fr=new THREE.Group(); scene.add(fr); const cn=[]; const dir=tgt.clone().sub(p).normalize(); const side=new THREE.Vector3().crossVectors(dir,V(0,1,0)).normalize();
  for(const [a,b] of [[-1,-1],[1,-1],[1,1],[-1,1]]){ const q=tgt.clone().add(side.clone().multiplyScalar(a*9)).add(dir.clone().multiplyScalar(b*7)); q.y=0; cn.push(q); fatLine([p,q],CYAN,1.0,0.28,fr); }
  fatLine([...cn,cn[0]],CYAN,1.0,0.22,fr);
  // 视线：一条淡的实线＋一串从球流向镜头的光点（光是从球进到相机里，不是相机往外射）
  const ray=fatLine([p,p.clone().add(V(0,-1,0))],GOLD,1.2,0.0); const flow=fatLine([p,p.clone().add(V(0,-1,0))],GOLD,2.6,0.0,scene,true,0.5); flowMats.push(flow.material);
  camRigs.push({g,p,edge,lens,box,fr,ray,flow,on:1});
}
function setCams(on,frustum=0,rays=0){ camRigs.forEach((c,i)=>{ const o=typeof on==='function'?on(i):on; c.g.visible=o>0.001; c.lens.material.opacity=o; c.edge.material.opacity=o; c.fr.visible=frustum>0.001&&o>0.001; c.fr.children.forEach(l=>l.material.opacity=0.28*frustum*o); c.ray.visible=false; c.flow.visible=false; c.on=o; }); }
function setRay(c,ballPos,op){ c.ray.visible=c.flow.visible=op>0.01; if(op<=0.01) return; setLine(c.ray,[ballPos,c.p]); setLine(c.flow,[ballPos,c.p]); c.ray.material.opacity=0.35*op; c.flow.material.opacity=0.95*op; }
// 6 foot-fault cameras: low, looking along the baselines & centre marks
const ffGroup=new THREE.Group(); scene.add(ffGroup); const ffRays=[];
for(const s of [-1,1]) for(const x of [-DW-2.2,0,DW+2.2]){
  const p=V(x,0.6,s*(L+(x===0?5.5:1.2))); const g=new THREE.Group(); g.position.copy(p); ffGroup.add(g);
  g.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(0.45,0.35,0.7)),new THREE.LineBasicMaterial({color:GOLD})));
  const s2=glowSprite(GOLD,0.3); s2.position.y=0.25; g.add(s2);
  const tgt=x===0?V(0,0,s*L):V(-Math.sign(x)*SW*0.6,0,s*L); ffRays.push(fatLine([p,tgt],GOLD,1.4,0.6,ffGroup));
}
const booth=new THREE.Group(); ffGroup.add(booth); booth.position.set(-DW-12,4,L+10);
booth.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(3.2,2,0.2)),new THREE.LineBasicMaterial({color:GOLD})));
const btn=glowSprite(RED,1.6); btn.position.set(0,-1.5,0.3); booth.add(btn);
for(const r of [[-DW-2.2,0.6,L+1.2],[0,0.6,L+5.5]]) fatLine([V(...r),booth.position.clone()],GOLD,1.0,0.35,ffGroup,true,0.6);

// ---------- ball, trail, ghosts ----------
const ball=new THREE.Group(); scene.add(ball);
const ballCore=new THREE.Mesh(new THREE.SphereGeometry(0.11,24,16),new THREE.MeshBasicMaterial({color:new THREE.Color(1.5,1.6,0.5),transparent:true})); ball.add(ballCore);
const ballGlow=glowSprite(BALLC,1.6); ball.add(ballGlow);
const TRN=60; const trailGeo=new THREE.BufferGeometry(); trailGeo.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(TRN*2*3),3)); trailGeo.setAttribute('alpha',new THREE.Float32BufferAttribute(new Float32Array(TRN*2),1));
{ const idx=[]; for(let i=0;i<TRN-1;i++){ const a=i*2,b=a+1,c=a+2,d=a+3; idx.push(a,b,c,b,d,c);} trailGeo.setIndex(idx); }
const trailMat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,uniforms:{uC:{value:new THREE.Color(0.8,1.0,0.3)},uOp:{value:1}},
 vertexShader:`attribute float alpha; varying float vA; void main(){ vA=alpha; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,
 fragmentShader:`varying float vA; uniform vec3 uC; uniform float uOp; void main(){ gl_FragColor=vec4(uC*1.6*vA*uOp, vA*uOp);} `});
const trail=new THREE.Mesh(trailGeo,trailMat); trail.frustumCulled=false; scene.add(trail);
// a groundstroke from the far baseline that lands on the near baseline (footprint touches the line → IN)
const LAND=V(-1.4,BR,L+0.035), TB=1.05, TE=1.6;
function traj(tb){
  const P0=V(-2.4,1.0,-L-1.0);
  if(tb<=0) return P0.clone();
  if(tb<TB){ const u=tb/TB; const s=u*(1.18-0.18*u); return V(P0.x+(LAND.x-P0.x)*s, P0.y*(1-s)+BR*s+4*1.55*s*(1-s), P0.z+(LAND.z-P0.z)*s); }
  const u=Math.min(1,(tb-TB)/(TE-TB)); return V(LAND.x-0.6*u, BR+1.9*Math.sin(Math.PI*0.62*u), LAND.z+5.2*u*(1.08-0.08*u));
}
function setBall(tb,op=1,trailDur=0.12,width=0.07,f=traj,core=1){
  const p=f(tb); ball.position.copy(p); ball.visible=op>0.001; ballGlow.material.opacity=op; ballCore.material.opacity=op*core; ballCore.visible=core>0;
  const pos=trailGeo.attributes.position.array, al=trailGeo.attributes.alpha.array; const camDir=new THREE.Vector3();
  for(let i=0;i<TRN;i++){ const tt=Math.max(0,tb-trailDur*i/(TRN-1)); const q=f(tt); const q2=f(Math.max(0,tt-0.004)); const dir=q.clone().sub(q2); if(dir.lengthSq()<1e-12) dir.set(0,0,1); dir.normalize();
    camDir.copy(camera.position).sub(q).normalize(); const side=new THREE.Vector3().crossVectors(dir,camDir).normalize().multiplyScalar(width*(1-i/TRN));
    pos.set([q.x+side.x,q.y+side.y,q.z+side.z, q.x-side.x,q.y-side.y,q.z-side.z],i*6);
    const a=Math.pow(1-i/(TRN-1),1.6)*op*(tb>0?1:0); al[i*2]=a; al[i*2+1]=a; }
  trailGeo.attributes.position.needsUpdate=true; trailGeo.attributes.alpha.needsUpdate=true; trail.visible=op>0.001&&trailDur>0;
}
const GH=40; const ghosts=[]; const ghostGroup=new THREE.Group(); scene.add(ghostGroup);
for(let i=0;i<GH;i++){ const m=new THREE.Mesh(new THREE.SphereGeometry(1,16,12),new THREE.MeshBasicMaterial({color:BALLC,transparent:true,opacity:0.6,blending:THREE.AdditiveBlending,depthWrite:false})); ghostGroup.add(m); ghosts.push(m); }
function setGhosts(ptsArr,r,op){ ghosts.forEach((m,i)=>{ if(i<ptsArr.length){ m.visible=true; m.position.copy(ptsArr[i]); m.scale.setScalar(r); m.material.opacity=op*(ptsArr.length>1?0.35+0.65*i/(ptsArr.length-1):1);} else m.visible=false; }); }
const trajLine=fatLine([V(0,0,0),V(0,0,1)],BALLC,2.2,0.0);
const hitFlare=glowSprite(WHITE,3,0); scene.add(hitFlare);
// on-court replay footprint (metres): ~10 cm × 4.4 cm ellipse at the landing point
const replayFoot=new THREE.Mesh(new THREE.CircleGeometry(1,48),new THREE.MeshBasicMaterial({color:new THREE.Color(1.0,0.85,0.2),transparent:true,opacity:0,depthWrite:false})); replayFoot.renderOrder=5;
replayFoot.rotation.x=-Math.PI/2; replayFoot.scale.set(0.022,0.05,1); replayFoot.position.set(LAND.x,0.012,LAND.z); tennis.add(replayFoot);
const replayFootRim=fatLine(Array.from({length:49},(_,i)=>{const a=i/48*Math.PI*2; return V(LAND.x+0.022*Math.cos(a),0.014,LAND.z+0.05*Math.sin(a));}),GOLD,2.4,0); replayFootRim.renderOrder=6;

// ================= EYES (analogy, metres, at y=300) =================
const eyes=new THREE.Group(); scene.add(eyes); eyes.position.set(0,300,0);
const eyeBalls=[]; for(const x of [-0.032,0.032]){ const e=new THREE.Group(); e.position.set(x,0,0); eyes.add(e);
  e.add(new THREE.Mesh(new THREE.SphereGeometry(0.012,24,16),new THREE.MeshBasicMaterial({color:0x223355}))); const ir=glowSprite(CYAN,0.02); ir.position.z=-0.012; e.add(ir); eyeBalls.push(e); }
const cupP=V(0.0,-0.06,-0.45); const cup=new THREE.Group(); cup.position.copy(cupP); eyes.add(cup);
{ const pts=[]; for(let i=0;i<=32;i++){const a=i/32*Math.PI*2; pts.push(V(0.035*Math.cos(a),0.05,0.035*Math.sin(a)));} fatLine(pts,WHITE,2,0.8,cup); const pb=[]; for(let i=0;i<=32;i++){const a=i/32*Math.PI*2; pb.push(V(0.028*Math.cos(a),-0.05,0.028*Math.sin(a)));} fatLine(pb,WHITE,2,0.8,cup);
  for(const a of [0,Math.PI/2,Math.PI,Math.PI*1.5]) fatLine([V(0.035*Math.cos(a),0.05,0.035*Math.sin(a)),V(0.028*Math.cos(a),-0.05,0.028*Math.sin(a))],WHITE,1.5,0.6,cup); }
const eyeRays=eyeBalls.map(e=>fatLine([cupP.clone().add(V(0,0.05,0)),e.position.clone()],GOLD,1.4,0.9,eyes));
const eyeFlows=eyeBalls.map(e=>{ const l=fatLine([cupP.clone().add(V(0,0.05,0)),e.position.clone()],GOLD,2.6,0,eyes,true,0.025); eyeFlowMats.push(l.material); return l; });
const eyeHit=glowSprite(GOLD,0.06); eyeHit.position.copy(cupP).add(V(0,0.05,0)); eyes.add(eyeHit);

// ================= LAB (centimetres, at y=1000) =================
const lab=new THREE.Group(); scene.add(lab); lab.position.set(0,1000,0);
const R=3.35; // ball radius, cm
// ground with shader: optional clay/hard split, a white line band, the footprint (union of contact discs),
// zone bands (machine ±0.5 cm amber / green 0.5..10) and human uncertainty glow.
const groundU={uT:{value:0},uFoot:{value:0},uFootX0:{value:-5},uFootV:{value:2.1},uFootT:{value:4.72},uFootC:{value:0.82},
  uLine:{value:0},uLineX:{value:0},uZones:{value:0},uHuman:{value:0},uHumanS:{value:1.4},uSplit:{value:0},uMarks:{value:0},uBump:{value:0},uGridOp:{value:1}};
const groundMat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,uniforms:groundU,
 vertexShader:`varying vec2 vP; void main(){ vP=position.xy; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,
 fragmentShader:`varying vec2 vP; uniform float uT,uFoot,uFootX0,uFootV,uFootT,uFootC,uLine,uLineX,uZones,uHuman,uHumanS,uSplit,uMarks,uBump,uGridOp;
  float grid(vec2 p,float s){ vec2 g=abs(fract(p/s-0.5)-0.5)/fwidth(p/s); return 1.-min(min(g.x,g.y),1.); }
  float hash(vec2 p){ return fract(sin(dot(p,vec2(41.3,289.1)))*43758.5); }
  void main(){
   vec2 p=vec2(vP.x,-vP.y); // x along travel, y across
   float d=length(p); float fade=exp(-d*0.009);
   vec3 base=vec3(0.02,0.05,0.11);
   if(uSplit>0.){ vec3 clay=vec3(0.30,0.11,0.05); vec3 hard=vec3(0.03,0.10,0.24); base=mix(base,(p.y>0.?clay:hard),uSplit); }
   vec3 c=base*0.9; float a=0.92*fade+0.05;
   float g=grid(p,1.0)*0.25+grid(p,10.0)*0.5; c+=vec3(0.25,0.55,1.0)*g*0.45*uGridOp*fade;
   // white line band (5 cm wide) whose outer edge sits at x=uLineX; inside the court is x<uLineX
   if(uLine>0.){ float inL=step(uLineX-5.0,p.x)*step(p.x,uLineX); c=mix(c,vec3(0.20,0.25,0.31),inL*0.9*uLine); float edge=1.-smoothstep(0.,0.05,abs(p.x-uLineX)); c+=vec3(0.4,0.8,1.0)*edge*uLine*0.5; }
   // zones relative to the line's outer edge
   if(uZones>0.){ float dx=abs(p.x-uLineX); float inR=step(dx,10.0);
     float amb=step(dx,0.5); float grn=inR*(1.-amb);
     c=mix(c,vec3(0.05,0.26,0.15),grn*0.6*uZones); c=mix(c,vec3(0.60,0.30,0.04),amb*0.9*uZones); }
   if(uHuman>0.){ float dx=p.x-uLineX; float gs=exp(-dx*dx/(2.*uHumanS*uHumanS)); c=mix(c,vec3(0.25,0.55,0.95),gs*0.75*uHuman); }
   // footprint: union of contact discs of a ball sliding at uFootV cm/ms for uFootT ms
   if(uFoot>0.){ float hit=0.; for(int i=0;i<40;i++){ float tm=uFootT*float(i)/39.; if(tm>uT) break; float cc=uFootC*sin(3.14159*tm/uFootT); float a2=sqrt(max(0.,2.*${(3.35).toFixed(2)}*cc-cc*cc)); vec2 ctr=vec2(uFootX0+uFootV*tm,0.); if(length(p-ctr)<a2) hit=1.; }
     c=mix(c,vec3(0.50,0.62,0.20),hit*0.85*uFoot); }
   // ball marks: clay mark scatters wider than the contact patch, hard-court mark smaller
   if(uMarks>0.){ vec2 q=p; float side=sign(q.y); vec2 ctrL=vec2(0.,9.); vec2 ctrR=vec2(0.,-9.);
     vec2 e1=(q-ctrL)/vec2(5.0,2.2); vec2 e2=(q-ctrR)/vec2(5.0,2.2);
     float n=hash(floor(q*6.)); float clayM=step(length((q-ctrL)/vec2(6.3,2.9)),1.0)*step(0.35,n)*step(0.,q.y);
     float hardM=step(length((q-ctrR)/vec2(3.6,1.5)),1.0)*step(q.y,0.);
     c=mix(c,vec3(0.48,0.28,0.18),clayM*0.8*uMarks); c=mix(c,vec3(0.22,0.30,0.42),hardM*0.85*uMarks); }
   gl_FragColor=vec4(c,a);
  }`});
const ground=new THREE.Mesh(new THREE.PlaneGeometry(420,420),groundMat); ground.rotation.x=-Math.PI/2; lab.add(ground);
// the ball (cm) — vertices below the floor plane are flattened onto it → a real contact patch
const labBallU={uFloor:{value:-R-1},uBulge:{value:0},uOp:{value:1}};
const labBall=new THREE.Mesh(new THREE.SphereGeometry(R,96,64),new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:labBallU,
 vertexShader:`uniform float uFloor,uBulge; varying vec3 vN; varying vec3 vV; varying float vFlat; void main(){ vec3 p=position; vFlat=0.;
  if(p.y<uFloor){ p.y=uFloor; vFlat=1.; } float k=1.+uBulge*(1.-abs(p.y)/${(3.35).toFixed(2)}); p.xz*=k;
  vec4 mv=modelViewMatrix*vec4(p,1.); vN=normalize(normalMatrix*normal); vV=normalize(-mv.xyz); gl_Position=projectionMatrix*mv; }`,
 fragmentShader:`uniform float uOp; varying vec3 vN; varying vec3 vV; varying float vFlat; void main(){ float f=pow(1.-abs(dot(vN,vV)),2.0); vec3 c=vec3(0.75,1.0,0.25)*(0.18+1.4*f)+vec3(1.0,0.9,0.5)*vFlat*0.8; gl_FragColor=vec4(c*uOp,(0.35+0.65*f)*uOp);} `}));
lab.add(labBall);
// fuzz (felt fibres) as a point shell around the ball
const fuzz=(()=>{ const a=[],c=[]; for(let i=0;i<5000;i++){ const u=rnd()*2-1, th=rnd()*Math.PI*2, r=R*(1.0+rnd()*0.10); const s=Math.sqrt(1-u*u); a.push(r*s*Math.cos(th),r*u,r*s*Math.sin(th)); const k=0.5+rnd()*0.5; c.push(0.8*k,1.0*k,0.35*k);} return points(a,c,0.07,0.9,lab,3); })();
const fuzzTouch=glowSprite(RED,1.6,0); lab.add(fuzzTouch);
const contactRing=fatLine(Array.from({length:65},(_,i)=>{const a=i/64*Math.PI*2; return V(Math.cos(a),0.02,Math.sin(a));}),GOLD,2.5,0,lab);
const sysEllipse=fatLine(Array.from({length:97},(_,i)=>{const a=i/96*Math.PI*2; return V(5.0*Math.cos(a),0.06,2.2*Math.sin(a));}),CYAN,3.2,0,lab,true,0.6);
const markTrue=[9,-9].map(z=>fatLine(Array.from({length:97},(_,i)=>{const a=i/96*Math.PI*2; return V(5.0*Math.cos(a),0.06,z+2.2*Math.sin(a));}),CYAN,3.2,0,lab,true,0.6));
const inspect=fatLine(Array.from({length:97},(_,i)=>{const a=i/96*Math.PI*2; return V(8*Math.cos(a),0.05,9+8*Math.sin(a));}),GOLD,2.5,0,lab);
// ruler ticks along x (mm) at the line's outer edge
const ruler=new THREE.Group(); lab.add(ruler);
for(let mm=-100;mm<=100;mm++){ const x=mm/10; const big=mm%10===0, mid=mm%5===0; const len=big?1.6:(mid?1.0:0.5);
  fatLine([V(x,0.05,6),V(x,0.05,6+len)],WHITE.clone().lerp(CYAN,0.4),big?1.8:1.0,big?0.9:0.55,ruler); }
fatLine([V(-10,0.05,6),V(10,0.05,6)],WHITE,1.6,0.8,ruler);
// bump (raised patch, exaggerated) for the 1 mm unevenness demo
const bump=new THREE.Mesh(new THREE.BoxGeometry(14,0.6,10),new THREE.MeshBasicMaterial({color:new THREE.Color(0.2,0.45,0.9),transparent:true,opacity:0.35,depthWrite:false}));
bump.position.set(-2,0.3,0); lab.add(bump); const bumpEdge=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(14,0.6,10)),new THREE.LineBasicMaterial({color:CYAN,transparent:true,opacity:0.8})); bump.add(bumpEdge);
const pathA=fatLine([V(0,0,0),V(0,0,1)],BALLC,2.2,0,lab), pathB=fatLine([V(0,0,0),V(0,0,1)],GOLD,2.2,0,lab,true,0.6);
const dotA=glowSprite(BALLC,1.4,0), dotB=glowSprite(GOLD,1.4,0); lab.add(dotA,dotB);
// frame strobe (cm scale, lab): ghosts every 16.3 cm for a 200 km/h ball skimming the ground
const strobe=new THREE.Group(); lab.add(strobe); const strobeBalls=[];
for(let i=0;i<14;i++){ const m=new THREE.Mesh(new THREE.SphereGeometry(R,24,16),new THREE.MeshBasicMaterial({color:BALLC,transparent:true,opacity:0.5,blending:THREE.AdditiveBlending,depthWrite:false})); strobe.add(m); strobeBalls.push(m); }
const strobeGap=[]; for(let i=0;i<13;i++) strobeGap.push(fatLine([V(0,0,0),V(1,0,0)],GOLD,1.6,0,strobe,true,0.8));

// ---------- light cones (atmosphere over the court) ----------
const coneMat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,uniforms:{uOp:{value:0.2},uC:{value:new THREE.Color(0.6,0.75,1.0)}},
 vertexShader:`varying float vY; varying vec3 vN; varying vec3 vV; void main(){ vY=uv.y; vec4 mv=modelViewMatrix*vec4(position,1.); vN=normalize(normalMatrix*normal); vV=normalize(-mv.xyz); gl_Position=projectionMatrix*mv; }`,
 fragmentShader:`varying float vY; varying vec3 vN; varying vec3 vV; uniform float uOp; uniform vec3 uC; void main(){ float f=pow(1.-abs(dot(vN,vV)),1.2); float a=uOp*pow(vY,1.6)*(1.-f*0.7); gl_FragColor=vec4(uC*a,a);} `});
const cones=new THREE.Group(); tennis.add(cones);
for(const [x,z] of [[-18,-28],[18,-28],[-18,28],[18,28]]){ const h=36; const m=new THREE.Mesh(new THREE.ConeGeometry(14,h,40,1,true),coneMat);
  const top=V(x,h,z); m.position.copy(top.clone().lerp(V(x*0.25,0,z*0.25),0.5)); m.lookAt(V(x*0.25,0,z*0.25)); m.rotateX(-Math.PI/2); cones.add(m); const s=glowSprite(new THREE.Color(0.8,0.9,1.0),5); s.position.copy(top); cones.add(s); }

// ---------- post ----------
const composer=new EffectComposer(renderer,new THREE.WebGLRenderTarget(W,H,{samples:4,type:THREE.HalfFloatType}));
composer.addPass(new RenderPass(scene,camera));
const bloom=new UnrealBloomPass(new THREE.Vector2(W/2,H/2),0.85,0.6,0.18); composer.addPass(bloom);
const finalPass=new ShaderPass({uniforms:{tDiffuse:{value:null},uT:{value:0},uFlash:{value:0},uFade:{value:1},uCA:{value:0.0015},uGlitch:{value:0},uScan:{value:-1},uTV:{value:0}},
 vertexShader:`varying vec2 vUv; void main(){ vUv=uv; gl_Position=vec4(position.xy,0.,1.);} `,
 fragmentShader:`uniform sampler2D tDiffuse; uniform float uT,uFlash,uFade,uCA,uGlitch,uScan,uTV; varying vec2 vUv;
  float h(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233))+uT*7.13)*43758.5453); }
  void main(){ vec2 uv=vUv;
   if(uGlitch>0.){ float row=floor(uv.y*60.); float r=h(vec2(row,floor(uT*24.))); if(r<uGlitch*0.5) uv.x+= (r-0.25)*0.08*uGlitch; }
   vec2 d=uv-0.5; float rr=length(d); float ca=uCA+uGlitch*0.006;
   vec3 c; c.r=texture2D(tDiffuse,uv+d*ca*rr*4.).r; c.g=texture2D(tDiffuse,uv).g; c.b=texture2D(tDiffuse,uv-d*ca*rr*4.).b;
   if(uTV>0.){ float sl=0.5+0.5*sin(uv.y*1080.*3.14159); c=mix(c,c*(0.82+0.18*sl)*vec3(1.05,1.05,0.95),uTV); }
   if(uScan>=0.){ float s=1.-smoothstep(0.,0.012,abs(uv.y-uScan)); c+=vec3(0.5,0.9,1.0)*s*1.4; }
   c*=1.0-smoothstep(0.35,0.95,rr*1.15)*0.75;
   c+=(h(uv*vec2(1920.,1080.))-0.5)*0.045;
   c=mix(c,vec3(1.0,0.97,0.92),uFlash); c*=uFade;
   gl_FragColor=vec4(c,1.); }`});
composer.addPass(finalPass); composer.addPass(new OutputPass());

// ---------- runtime API ----------
const anchors={};
function proj(name,v,group){ const w=v.clone(); if(group) group.localToWorld(w); const p=w.project(camera); anchors[name]=[(p.x*0.5+0.5)*W,(1-(p.y*0.5+0.5))*H,(p.z<1&&p.z>-1)?1:0]; }
const val=(n,v)=>{anchors[n]=v;};
function cam(pos,tgt,fov,up){ camera.up.set(...(up||[0,1,0])); camera.position.copy(pos); camera.fov=fov; camera.lookAt(tgt); camera.updateProjectionMatrix(); camera.updateMatrixWorld(true); }
const STATE={THREE,scene,camera,cam,V,L,DW,SW,BR,LAND,TB,TE,R,traj,setBall,setGhosts,ghosts,trajLine,setLine,hitFlare,replayFoot,replayFootRim,surfMat,baseStripMat,courtLines,tennis,
  camRigs,CAMPOS,setCams,setRay,eyeFlows,rigGroup,ffGroup,ffRays,booth,btn,umpGlow,ljChair,chairs,eyes,eyeRays,eyeHit,cupP,lab,groundU,labBall,labBallU,fuzz,fuzzTouch,contactRing,sysEllipse,markTrue,inspect,ruler,bump,pathA,pathB,dotA,dotB,
  strobe,strobeBalls,strobeGap,bloom,finalPass,gridMat,coneMat,cones,tBowl,proj,val,ball,ballGlow,ballCore,glowSprite,GOLD,CYAN,WHITE,BALLC};
function hideAll(){
  for(const o of [ffGroup,eyes,lab,chairs,ghostGroup,strobe,ruler,bump]) o.visible=false;
  for(const o of [tennis,rigGroup,grid,cones]) o.visible=true;
  setCams(0,0,0); setBall(0,0); trajLine.material.opacity=0; trajLine.visible=false; hitFlare.material.opacity=0;
  replayFoot.material.opacity=0; replayFootRim.material.opacity=0; baseStripMat.opacity=0; surfMat.color.setHex(0x0a1a33); surfMat.opacity=0.55;
  umpGlow.material.opacity=0; ljChair.visible=true;
  for(const k in groundU) if(k!=='uFootX0'&&k!=='uFootV'&&k!=='uFootT'&&k!=='uFootC'&&k!=='uHumanS'&&k!=='uLineX') groundU[k].value=0; groundU.uGridOp.value=1; groundU.uLineX.value=0;
  labBallU.uFloor.value=-R-1; labBallU.uBulge.value=0; labBallU.uOp.value=1; labBall.visible=true; labBall.position.set(0,R,0); fuzz.visible=true; fuzz.position.set(0,R,0); fuzz.material.uniforms.uOp.value=0.9; fuzzTouch.material.opacity=0;
  contactRing.material.opacity=0; sysEllipse.material.opacity=0; markTrue.forEach(m=>m.material.opacity=0); inspect.material.opacity=0;
  pathA.material.opacity=0; pathB.material.opacity=0; dotA.material.opacity=0; dotB.material.opacity=0; strobeGap.forEach(l=>l.material.opacity=0);
  eyeRays.forEach(r=>r.material.opacity=0); eyeFlows.forEach(r=>r.material.opacity=0); eyeHit.material.opacity=0; btn.material.opacity=1; ffRays.forEach(r=>r.material.opacity=0.6);
}
window.renderAt=function(t){
  for(const k in anchors) delete anchors[k];
  hideAll(); scene.fog.density=0.0018; gridMat.uniforms.uOp.value=1; coneMat.uniforms.uOp.value=0.2;
  const fp=finalPass.uniforms; fp.uT.value=t; fp.uFlash.value=0; fp.uFade.value=1; fp.uGlitch.value=0; fp.uScan.value=-1; fp.uTV.value=0; bloom.strength=0.85;
  for(const m of flowMats) m.dashOffset=-t*7.0; for(const m of eyeFlowMats) m.dashOffset=-t*0.35;
  let shot=SHOTS[SHOTS.length-1]; for(const s of SHOTS){ if(t>=s.t0 && t<s.t1){ shot=s; break; } }
  const lt=t-shot.t0, d=shot.t1-shot.t0;
  shot.fn(STATE,lt,d,t);
  camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  // 机位离某台相机太近时，把它的灯头压暗，免得一团光糊住画面
  for(const c of camRigs){ const dc=camera.position.distanceTo(c.p); if(dc<14){ const k=Math.max(0.05,(dc-3)/11); c.lens.material.opacity*=k; } }
  { const dd=camera.position.distanceTo(ball.position); ballGlow.scale.setScalar(Math.min(4,Math.max(0.12,dd*0.03))); }
  composer.render();
  return JSON.stringify(anchors);
};
window.READY=true;
