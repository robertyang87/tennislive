import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';
import { SHOTS, TOTAL } from './shots.js';

const W=+(new URLSearchParams(location.search).get('w')||1920), H=+(new URLSearchParams(location.search).get('h')||1080);
const renderer=new THREE.WebGLRenderer({antialias:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
renderer.setPixelRatio(1); renderer.setSize(W,H); renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.0;
document.body.appendChild(renderer.domElement);
const scene=new THREE.Scene(); scene.background=new THREE.Color(0x02040a);
scene.fog=new THREE.FogExp2(0x02040a,0.0018);
{ const sky=new THREE.Mesh(new THREE.SphereGeometry(3200,48,24),new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,fog:false,uniforms:{},vertexShader:`varying vec3 vD; void main(){ vD=normalize(position); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,fragmentShader:`varying vec3 vD; void main(){ float h=vD.y; float g=exp(-abs(h+0.02)*9.0); vec3 top=vec3(0.006,0.01,0.024); vec3 hz=vec3(0.018,0.032,0.075); vec3 vi=vec3(0.04,0.022,0.07); float side=0.5+0.5*vD.x; vec3 c=top+hz*g+vi*g*g*side*0.6; gl_FragColor=vec4(c,1.);} `})); scene.add(sky); }
const camera=new THREE.PerspectiveCamera(40,W/H,0.1,6000);

// ---------- palette ----------
const GOLD=new THREE.Color(1.0,0.66,0.22), CYAN=new THREE.Color(0.38,0.86,1.0), WHITE=new THREE.Color(1,1,1), VIOLET=new THREE.Color(0.55,0.45,1.0);
let seed=1234567; const rnd=()=>{seed=(seed*16807)%2147483647;return seed/2147483647;};

// ---------- helpers ----------
const lineMats=[];
function fatLine(pts,color,width,opacity=1,group=scene){
  const g=new LineGeometry(); g.setPositions(pts.flatMap(p=>[p.x,p.y,p.z]));
  const m=new LineMaterial({color,linewidth:width,transparent:true,opacity,depthWrite:false,blending:THREE.AdditiveBlending,worldUnits:false});
  m.resolution.set(W,H); lineMats.push(m);
  const l=new Line2(g,m); l.computeLineDistances(); group.add(l); return l;
}
const V=(x,y,z)=>new THREE.Vector3(x,y,z);
function addMat(color,opacity){return new THREE.MeshBasicMaterial({color,transparent:true,opacity,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide});}
function glowSprite(color,size){
  const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d');
  const gr=g.createRadialGradient(64,64,0,64,64,64); gr.addColorStop(0,'rgba(255,255,255,1)'); gr.addColorStop(0.15,'rgba(255,255,255,0.6)'); gr.addColorStop(0.45,'rgba(255,255,255,0.12)'); gr.addColorStop(1,'rgba(255,255,255,0)');
  g.fillStyle=gr; g.fillRect(0,0,128,128);
  const t=new THREE.CanvasTexture(c);
  const s=new THREE.Sprite(new THREE.SpriteMaterial({map:t,color,transparent:true,blending:THREE.AdditiveBlending,depthWrite:false}));
  s.scale.set(size,size,1); return s;
}
const dotTex=(()=>{const c=document.createElement('canvas');c.width=c.height=64;const g=c.getContext('2d');const gr=g.createRadialGradient(32,32,0,32,32,32);gr.addColorStop(0,'rgba(255,255,255,1)');gr.addColorStop(0.3,'rgba(255,255,255,0.5)');gr.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=gr;g.fillRect(0,0,64,64);return new THREE.CanvasTexture(c);})();
function points(arr,colors,size,opacity=1,group=scene,maxPx=7){
  const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(arr,3)); g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
  const m=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uSize:{value:size},uOp:{value:opacity},uMax:{value:maxPx},uTex:{value:dotTex},uH:{value:H}},
   vertexShader:`attribute vec3 color; varying vec3 vC; varying float vF; uniform float uSize,uMax,uH; void main(){ vC=color; vec4 mv=modelViewMatrix*vec4(position,1.); float px=uSize*uH*0.5*projectionMatrix[1][1]/-mv.z; vF=clamp(px/max(px,uMax),0.15,1.0); gl_PointSize=clamp(px,1.0,uMax); gl_Position=projectionMatrix*mv; }`,
   fragmentShader:`uniform sampler2D uTex; uniform float uOp; varying vec3 vC; varying float vF; void main(){ float d=length(gl_PointCoord-0.5); float ta=exp(-d*d*16.0)*(1.0-smoothstep(0.42,0.5,d)); gl_FragColor=vec4(vC*ta*uOp*vF, ta*uOp*vF);} `});
  m.opacity=opacity; const p=new THREE.Points(g,m); group.add(p); return p;
}
// ---------- starfield & dust ----------
{ const a=[],c=[]; for(let i=0;i<9000;i++){ const r=1500+rnd()*2500, th=rnd()*Math.PI*2, ph=Math.acos(2*rnd()-1); a.push(r*Math.sin(ph)*Math.cos(th), Math.abs(r*Math.cos(ph))*0.9-200, r*Math.sin(ph)*Math.sin(th)); const k=0.4+rnd()*0.6; const w=rnd(); c.push(k*(0.7+0.3*w),k*(0.75+0.2*w),k); }
  const s=points(a,c,7,0.9,scene,3); }
const dust=(()=>{ const a=[],c=[]; for(let i=0;i<5000;i++){ a.push((rnd()-0.5)*160,rnd()*50,(rnd()-0.5)*160); const k=0.25+rnd()*0.5; c.push(k*0.6,k*0.8,k);} return points(a,c,0.06,0.6,scene,4);})();

// ---------- grid floor (shader) ----------
const gridMat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,uniforms:{uOp:{value:1},uC:{value:new THREE.Color(0.25,0.55,1.0)}},
 vertexShader:`varying vec3 vW; void main(){ vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }`,
 fragmentShader:`varying vec3 vW; uniform float uOp; uniform vec3 uC;
  float grid(vec2 p,float s){ vec2 g=abs(fract(p/s-0.5)-0.5)/fwidth(p/s); return 1.-min(min(g.x,g.y),1.); }
  void main(){ float d=length(vW.xz); float g=grid(vW.xz,2.0)*0.35+grid(vW.xz,10.0)*0.6; float f=exp(-d*0.006);
   gl_FragColor=vec4(uC*g*f, g*f*0.55*uOp); }`});
const grid=new THREE.Mesh(new THREE.PlaneGeometry(4000,4000),gridMat); grid.rotation.x=-Math.PI/2; grid.position.y=-0.02; scene.add(grid);

// ---------- tennis court ----------
const tennis=new THREE.Group(); scene.add(tennis);
const L=23.77/2, DW=10.97/2, SW=8.23/2, SL=6.40;
// glass surface
const surf=new THREE.Mesh(new THREE.PlaneGeometry(DW*2+7,L*2+12),new THREE.MeshBasicMaterial({color:0x0a1a33,transparent:true,opacity:0.55,depthWrite:false}));
surf.rotation.x=-Math.PI/2; surf.position.y=0.005; tennis.add(surf);
const courtLines=[];
const cl=(a,b,w=2.2)=>courtLines.push(fatLine([a,b],WHITE.clone().lerp(CYAN,0.55),w,0.72,tennis));
const y0=0.02;
cl(V(-DW,y0,-L),V(DW,y0,-L)); cl(V(-DW,y0,L),V(DW,y0,L));
cl(V(-DW,y0,-L),V(-DW,y0,L)); cl(V(DW,y0,-L),V(DW,y0,L));
cl(V(-SW,y0,-L),V(-SW,y0,L)); cl(V(SW,y0,-L),V(SW,y0,L));
cl(V(-SW,y0,-SL),V(SW,y0,-SL)); cl(V(-SW,y0,SL),V(SW,y0,SL));
cl(V(0,y0,-SL),V(0,y0,SL));
// net: posts + mesh
const net=new THREE.Group(); tennis.add(net);
fatLine([V(-DW-0.9,1.07,0),V(0,0.914,0),V(DW+0.9,1.07,0)],WHITE,2.6,0.85,net);
for(let x=-DW-0.9;x<=DW+0.91;x+=0.45) fatLine([V(x,0,0),V(x,0.914+0.156*Math.abs(x)/(DW+0.9),0)],CYAN,1,0.35,net);
for(let y=0.15;y<0.9;y+=0.15) fatLine([V(-DW-0.9,y,0),V(DW+0.9,y,0)],CYAN,1,0.3,net);
fatLine([V(-DW-0.9,0,0),V(-DW-0.9,1.07,0)],WHITE,3,1,net); fatLine([V(DW+0.9,0,0),V(DW+0.9,1.07,0)],WHITE,3,1,net);
// stadium bowl (points + structural rings)
function bowl(group,ax,az,tiers,rows,cnt,warm){
  const a=[],c=[];
  for(let t=0;t<tiers;t++) for(let r=0;r<rows;r++){
    const k=t*rows+r, rx=ax+k*0.9, rz=az+k*0.9, y=1.2+k*0.62+t*1.5;
    const n=Math.floor(cnt*(1+k*0.04));
    for(let i=0;i<n;i++){ const th=(i/n)*Math.PI*2+rnd()*0.01; if(rnd()<0.12) continue;
      // superellipse for stadium shape
      const cx=Math.cos(th), sz=Math.sin(th); const p=0.6; const ex=Math.sign(cx)*Math.pow(Math.abs(cx),p), ez=Math.sign(sz)*Math.pow(Math.abs(sz),p);
      a.push(rx*ex,y,rz*ez); const w=rnd(); const b=(0.25+0.75*rnd()*rnd())*1.6;
      if(w<warm) c.push(b*1.0,b*0.75,b*0.45); else c.push(b*0.55,b*0.8,b*1.0); }
  }
  const p=points(a,c,0.2,1,group,6);
  // structural rings
  for(let t=0;t<=tiers;t++){ const k=t*rows, rx=ax+k*0.9, rz=az+k*0.9, y=1.0+k*0.62+t*1.5; const pts=[];
    for(let i=0;i<=160;i++){const th=i/160*Math.PI*2; const cx=Math.cos(th), sz=Math.sin(th); pts.push(V(rx*Math.sign(cx)*Math.pow(Math.abs(cx),0.6),y,rz*Math.sign(sz)*Math.pow(Math.abs(sz),0.6)));}
    fatLine(pts,CYAN,1.3,0.22,group); }
  return p;
}
const tBowl=bowl(tennis,13,22,3,9,260,0.55);
// fake glossy-floor reflections
const refl=new THREE.Group(); tennis.add(refl);
{ const n2=net.clone(true); n2.scale.y=-1; n2.traverse(o=>{ if(o.material){ o.material=o.material.clone(); o.material.opacity*=0.25; if(o.material.resolution) lineMats.push(o.material);} }); refl.add(n2);
  const b2=tBowl.clone(); b2.scale.y=-1; b2.material=tBowl.material.clone(); b2.material.uniforms.uOp.value=0.12; refl.add(b2); }
// light rigs: volumetric cones
const coneMat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,uniforms:{uOp:{value:0.22},uC:{value:new THREE.Color(0.6,0.75,1.0)}},
 vertexShader:`varying float vY; varying vec3 vN; varying vec3 vV; void main(){ vY=uv.y; vec4 mv=modelViewMatrix*vec4(position,1.); vN=normalize(normalMatrix*normal); vV=normalize(-mv.xyz); gl_Position=projectionMatrix*mv; }`,
 fragmentShader:`varying float vY; varying vec3 vN; varying vec3 vV; uniform float uOp; uniform vec3 uC; void main(){ float f=pow(1.-abs(dot(vN,vV)),1.2); float a=uOp*pow(vY,1.6)*(1.-f*0.7); gl_FragColor=vec4(uC*a,a);} `});
const cones=new THREE.Group(); tennis.add(cones);
for(const [x,z] of [[-16,-26],[16,-26],[-16,26],[16,26],[-22,0],[22,0]]){
  const h=34; const g=new THREE.ConeGeometry(14,h,40,1,true); const m=new THREE.Mesh(g,coneMat);
  m.position.set(x*0.5,h/2,z*0.5); const top=V(x,h,z); m.position.copy(top.clone().lerp(V(x*0.25,0,z*0.25),0.5));
  m.lookAt(V(x*0.25,0,z*0.25)); m.rotateX(-Math.PI/2); cones.add(m);
  const s=glowSprite(new THREE.Color(0.8,0.9,1.0),5); s.position.copy(top); cones.add(s);
}

// ---------- broadcast camera C1 (ATP: sightline grazes net top at 12.09 deg) ----------
const C1_BACK=18, C1_Z=L+C1_BACK, C1_Y=0.914+(C1_Z)*Math.tan(12.09*Math.PI/180);
const c1=new THREE.Group(); scene.add(c1); c1.position.set(0,C1_Y,C1_Z);
{ const body=new THREE.Mesh(new THREE.BoxGeometry(0.9,0.7,1.6),new THREE.MeshBasicMaterial({color:0x223355})); c1.add(body);
  const lens=new THREE.Mesh(new THREE.CylinderGeometry(0.28,0.36,0.8,24),new THREE.MeshBasicMaterial({color:0x99ddff})); lens.rotation.x=Math.PI/2; lens.position.z=-1.1; c1.add(lens);
  const g=glowSprite(CYAN,3); g.position.z=-1.5; c1.add(g);
  const e=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(0.9,0.7,1.6)),new THREE.LineBasicMaterial({color:CYAN})); c1.add(e); }
c1.lookAt(0,0,-1.5);
const c1cam=new THREE.PerspectiveCamera(16,16/9,0.5,2000); c1cam.position.copy(c1.position); c1cam.lookAt(0,0.3,-1.2);
// frustum lines from C1 to court corners
const frust=new THREE.Group(); scene.add(frust);
for(const [x,z] of [[-DW-1.5,-L-3],[DW+1.5,-L-3],[-DW-1.5,L+2],[DW+1.5,L+2]]) fatLine([c1.position.clone(),V(x,0,z)],CYAN,1.6,0.55,frust);
// sightline grazing net top
const sight=fatLine([c1.position.clone(), V(0,0.914,0), V(0,0,-(0.914/Math.tan(12.09*Math.PI/180)))],GOLD,2.5,1);
// vertical wedges at x=0
function fan(origin,pts,color,op){ const pos=[]; for(let i=0;i<pts.length-1;i++){ pos.push(origin.x,origin.y,origin.z, pts[i].x,pts[i].y,pts[i].z, pts[i+1].x,pts[i+1].y,pts[i+1].z);} const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); const m=new THREE.Mesh(g,addMat(color,op)); scene.add(m); return m; }
const zs=(a,b,n=40)=>Array.from({length:n+1},(_,i)=>V(0,0.03,a+(b-a)*i/n));
const wedgeAll=fan(c1.position,zs(-L,L),GOLD,0.12);
const wedgeFar=fan(c1.position,zs(-L,0),CYAN,0.2);
const wedgeNear=fan(c1.position,zs(0,L),GOLD,0.1);
const wedgeRims=new THREE.Group(); scene.add(wedgeRims);
for(const z of [-L,0,L]) fatLine([c1.position.clone(),V(0,0.03,z)],WHITE,1.8,0.8,wedgeRims);

// ---------- holographic TV screen showing C1 view ----------
const rt=new THREE.WebGLRenderTarget(640,360,{samples:4}); rt.texture.colorSpace=THREE.SRGBColorSpace;
const tvScreen=new THREE.Group(); scene.add(tvScreen);
{ const m=new THREE.Mesh(new THREE.PlaneGeometry(16,9),new THREE.MeshBasicMaterial({map:rt.texture,transparent:true,opacity:1,depthWrite:false,toneMapped:false})); tvScreen.add(m);
  fatLine([V(-8.2,-4.7,0.02),V(8.2,-4.7,0.02),V(8.2,4.7,0.02),V(-8.2,4.7,0.02),V(-8.2,-4.7,0.02)],CYAN,2.5,0.9,tvScreen);
  const g=glowSprite(CYAN,30); g.material.opacity=0.12; g.position.z=-0.1; tvScreen.add(g); }

// ---------- ball & trail ----------
const ball=new THREE.Group(); scene.add(ball);
const ballCore=new THREE.Mesh(new THREE.SphereGeometry(0.11,24,16),new THREE.MeshBasicMaterial({color:new THREE.Color(1.6,1.2,0.6)})); ball.add(ballCore);
const ballGlow=glowSprite(GOLD,1.6); ball.add(ballGlow);
const ballRefl=glowSprite(GOLD,1.0); ballRefl.material.opacity=0.25; scene.add(ballRefl);
const TRN=60; const trailGeo=new THREE.BufferGeometry(); trailGeo.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(TRN*2*3),3)); trailGeo.setAttribute('alpha',new THREE.Float32BufferAttribute(new Float32Array(TRN*2),1));
{ const idx=[]; for(let i=0;i<TRN-1;i++){ const a=i*2,b=a+1,c=a+2,d=a+3; idx.push(a,b,c,b,d,c);} trailGeo.setIndex(idx); }
const trailMat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,uniforms:{uC:{value:new THREE.Color(1.0,0.62,0.2)},uOp:{value:1}},
 vertexShader:`attribute float alpha; varying float vA; void main(){ vA=alpha; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);} `,
 fragmentShader:`varying float vA; uniform vec3 uC; uniform float uOp; void main(){ gl_FragColor=vec4(uC*1.6*vA*uOp, vA*uOp);} `});
const trail=new THREE.Mesh(trailGeo,trailMat); trail.frustumCulled=false; scene.add(trail);

// serve trajectory (from sim: 0.395 s to bounce 18.0 m, 0.714 s to 24.8 m)
function serve(tb){ // tb ball time since hit
  const z0=-L, tB=0.395, tE=0.714;
  if(tb<=0) return V(0.6,2.8,z0);
  if(tb<tB){ const u=tb/tB; const s=18.0*(u*(1.12-0.12*u)); return V(0.6-0.9*u,2.8*(1-u)+0.033*u - 0.4*Math.sin(Math.PI*u)*0, z0+s); }
  const u=Math.min(1,(tb-tB)/(tE-tB)); const z=z0+18+6.8*u*(1.1-0.1*u); return V(-0.3-0.5*u, 0.033+1.25*Math.sin(Math.PI*0.5*u)*(1.0) , z);
}
function setBall(tb,trailDur=0.12,width=0.09,op=1){
  const p=serve(tb); ball.position.copy(p); ballRefl.position.set(p.x,-p.y,p.z); ballRefl.visible=op>0.001; ballRefl.scale.setScalar(ballGlow.scale.x*0.8); ball.visible=op>0.001; ballGlow.material.opacity=op; ballCore.material.opacity=op;
  const pos=trailGeo.attributes.position.array, al=trailGeo.attributes.alpha.array;
  const camDir=new THREE.Vector3();
  for(let i=0;i<TRN;i++){ const tt=Math.max(0,tb-trailDur*i/(TRN-1)); const q=serve(tt);
    const q2=serve(Math.max(0,tt-0.004)); const dir=q.clone().sub(q2).normalize(); camDir.copy(camera.position).sub(q).normalize();
    const side=new THREE.Vector3().crossVectors(dir,camDir).normalize().multiplyScalar(width*(1-i/TRN));
    pos.set([q.x+side.x,q.y+side.y,q.z+side.z, q.x-side.x,q.y-side.y,q.z-side.z],i*6);
    const a=Math.pow(1-i/(TRN-1),1.6)*op*(tb>0?1:0); al[i*2]=a; al[i*2+1]=a; }
  trailGeo.attributes.position.needsUpdate=true; trailGeo.attributes.alpha.needsUpdate=true; trail.visible=op>0.001;
}

// ---------- courtside seat & sweep ----------
const SEAT=V(SW+6,3,0);
const seatMark=glowSprite(CYAN,1.4); seatMark.position.copy(SEAT); scene.add(seatMark);
const sweepGeo=new THREE.BufferGeometry(); sweepGeo.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(200*9),3));
const sweep=new THREE.Mesh(sweepGeo,addMat(GOLD,0.22)); sweep.frustumCulled=false; scene.add(sweep);
function setSweep(tb,op){ const arr=sweepGeo.attributes.position.array; arr.fill(0); const n=199;
  for(let i=0;i<n;i++){ const t1=tb*i/n, t2=tb*(i+1)/n; const a=serve(t1), b=serve(t2); arr.set([SEAT.x,SEAT.y,SEAT.z,a.x,a.y,a.z,b.x,b.y,b.z],i*9); }
  sweepGeo.attributes.position.needsUpdate=true; sweep.material.opacity=0.25*op; sweep.visible=op>0.001; }

// ---------- football stadium (far away) ----------
const FX=420; const football=new THREE.Group(); football.position.set(FX,0,0); scene.add(football);
{ const PL=105/2, PW=68/2, g=new THREE.Color(0.45,1.0,0.7);
  const fl=(a,b)=>fatLine([a,b],g,2.5,0.85,football);
  fl(V(-PW,0.02,-PL),V(PW,0.02,-PL)); fl(V(-PW,0.02,PL),V(PW,0.02,PL)); fl(V(-PW,0.02,-PL),V(-PW,0.02,PL)); fl(V(PW,0.02,-PL),V(PW,0.02,PL)); fl(V(-PW,0.02,0),V(PW,0.02,0));
  const circ=[]; for(let i=0;i<=80;i++){const t=i/80*Math.PI*2; circ.push(V(9.15*Math.cos(t),0.02,9.15*Math.sin(t)));} fatLine(circ,g,2.5,0.85,football);
  for(const s of [-1,1]){ fl(V(-20.16,0.02,s*PL),V(-20.16,0.02,s*(PL-16.5))); fl(V(20.16,0.02,s*PL),V(20.16,0.02,s*(PL-16.5))); fl(V(-20.16,0.02,s*(PL-16.5)),V(20.16,0.02,s*(PL-16.5))); }
  const fs=new THREE.Mesh(new THREE.PlaneGeometry(PW*2+10,PL*2+10),new THREE.MeshBasicMaterial({color:0x06241a,transparent:true,opacity:0.6,depthWrite:false})); fs.rotation.x=-Math.PI/2; football.add(fs);
  bowl(football,48,68,3,12,520,0.5);
}
// TV window frame on the pitch (40 m wide), rotates to face camera height
const fWin=new THREE.Group(); football.add(fWin);
fatLine([V(-20,0.3,-11),V(20,0.3,-11),V(20,0.3,11),V(-20,0.3,11),V(-20,0.3,-11)],GOLD,3.5,1,fWin);
const fBall=new THREE.Group(); football.add(fBall); fBall.add(new THREE.Mesh(new THREE.SphereGeometry(0.4,16,12),new THREE.MeshBasicMaterial({color:0xffffff}))); { const s=glowSprite(new THREE.Color(1,1,1),5); fBall.add(s);} 

// ---------- Brown windows (portals floating in space) ----------
const brown=new THREE.Group(); scene.add(brown); brown.position.set(0,400,0);
const pSmall=new THREE.Group(), pBig=new THREE.Group(); brown.add(pSmall,pBig);
const sq=(s,c,w)=>[V(-s,-s,0),V(s,-s,0),V(s,s,0),V(-s,s,0),V(-s,-s,0)];
fatLine(sq(3),CYAN,3,1,pSmall); fatLine(sq(6),CYAN,3,1,pBig); pSmall.position.set(-10,0,0); pBig.position.set(5,0,0);
const bDot1=glowSprite(GOLD,1.2), bDot2=glowSprite(GOLD,2.4); pSmall.add(bDot1); pBig.add(bDot2);

// ---------- field of arenas (reframe) ----------
const field=new THREE.Group(); scene.add(field); field.position.set(0,0,-900);
{ const a=[],c=[]; for(let gx=-30;gx<=30;gx++) for(let gz=-30;gz<=30;gz++){ if(rnd()<0.25) continue; const cx=gx*36+(rnd()-0.5)*8, cz=gz*36+(rnd()-0.5)*8;
    for(let i=0;i<40;i++){ const t=i/40*Math.PI*2; a.push(cx+8*Math.cos(t),0.2,cz+12*Math.sin(t)); const w=rnd()<0.5; c.push(w?0.9:0.4,w?0.65:0.75,w?0.35:1.0);}
    for(const [dx,dz] of [[-2,-4],[2,-4],[2,4],[-2,4],[0,0]]){ a.push(cx+dx,0.3,cz+dz); c.push(1.2,1.2,1.3);} if(rnd()<0.3){ a.push(cx+(rnd()-0.5)*3,1,cz+(rnd()-0.5)*6); c.push(2.0,1.3,0.5);} }
  points(a,c,2.6,1,field,5); }

// ---------- post: final shader ----------
const composer=new EffectComposer(renderer,new THREE.WebGLRenderTarget(W,H,{samples:4,type:THREE.HalfFloatType}));
composer.addPass(new RenderPass(scene,camera));
const bloom=new UnrealBloomPass(new THREE.Vector2(W/2,H/2),0.85,0.6,0.18); composer.addPass(bloom);
const finalPass=new ShaderPass({uniforms:{tDiffuse:{value:null},uT:{value:0},uFlash:{value:0},uFade:{value:1},uCA:{value:0.0015}},
 vertexShader:`varying vec2 vUv; void main(){ vUv=uv; gl_Position=vec4(position.xy,0.,1.);} `,
 fragmentShader:`uniform sampler2D tDiffuse; uniform float uT,uFlash,uFade,uCA; varying vec2 vUv;
  float h(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233))+uT*7.13)*43758.5453); }
  void main(){ vec2 d=vUv-0.5; float r=length(d);
   vec3 c; c.r=texture2D(tDiffuse,vUv+d*uCA*r*4.).r; c.g=texture2D(tDiffuse,vUv).g; c.b=texture2D(tDiffuse,vUv-d*uCA*r*4.).b;
   c*=1.0-smoothstep(0.35,0.95,r*1.15)*0.75;               // vignette
   c+= (h(vUv*vec2(1920.,1080.))-0.5)*0.045;                // grain
   c=mix(c,vec3(1.0,0.95,0.88),uFlash); c*=uFade;
   gl_FragColor=vec4(c,1.); }`});
composer.addPass(finalPass); composer.addPass(new OutputPass());

// ---------- runtime API ----------
const anchors={};
function proj(name,v){ const p=v.clone().project(camera); anchors[name]=[ (p.x*0.5+0.5)*W, (1-(p.y*0.5+0.5))*H, p.z<1?1:0 ]; }
const val=(n,v)=>{anchors[n]=v;};
const STATE={val,THREE,scene,camera,c1,c1cam,tennis,football,fWin,fBall,frust,sight,wedgeAll,wedgeFar,wedgeNear,wedgeRims,tvScreen,ball,trail,setBall,setSweep,sweep,seatMark,SEAT,serve,brown,pSmall,pBig,bDot1,bDot2,field,bloom,finalPass,gridMat,coneMat,cones,dust,tBowl,proj,V,L,C1_Y,C1_Z,FX};
function hideAll(){ for(const o of [frust,sight,wedgeAll,wedgeFar,wedgeNear,wedgeRims,tvScreen,sweep,seatMark,brown,fWin,fBall,field]) o.visible=false; setBall(0,0.1,0.09,0); }
window.renderAt=function(t){
  for(const k in anchors) delete anchors[k];
  hideAll(); scene.fog.density=0.0018; gridMat.uniforms.uOp.value=1; finalPass.uniforms.uT.value=t; finalPass.uniforms.uFlash.value=0; finalPass.uniforms.uFade.value=1; bloom.strength=0.85;
  let shot=SHOTS[SHOTS.length-1]; for(const s of SHOTS){ if(t>=s.t0 && t<s.t1){ shot=s; break; } }
  const lt=t-shot.t0, d=shot.t1-shot.t0;
  shot.fn(STATE,lt,d,t);
  camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  { const dd=camera.position.distanceTo(ball.position); ballGlow.scale.setScalar(Math.min(4,Math.max(0.3,dd*0.03))); }
  if(tvScreen.visible){ tvScreen.visible=false; const bv=ballGlow.scale.x; ballGlow.scale.setScalar(Math.max(0.3,c1cam.position.distanceTo(ball.position)*0.02)); renderer.setRenderTarget(rt); renderer.render(scene,c1cam); renderer.setRenderTarget(null); ballGlow.scale.setScalar(bv); tvScreen.visible=true; }
  composer.render();
  return JSON.stringify(anchors);
};
window.TOTAL=TOTAL; window.READY=true;
