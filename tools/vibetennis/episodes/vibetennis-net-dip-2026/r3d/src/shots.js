// ==================== EP13 网中间矮：本集物件 ====================
// 1 单位 = 1 m。球网沿 x 轴、在 z=0；双打网柱中心在 x=±(DW+0.914)=±6.399，单打支杆在 x=±(SW+0.914)=±5.029（ITF 规则第 1 条）。
// 网形：自由下垂（绷紧但中央带松开）用悬链线 cosh；中央带拉下之后是「两段直线＋中间折角」的浅 V（静力学：单点集中力）。两者按 k 混合。
// 所有上屏数字的出处见 papers/vibetennis-net-dip-2026/sources.md；弹道余量、角度窗口由同目录 net_geometry.py 复现（真空、不计阻力和旋转）。
renderer.localClippingEnabled=true;
const POSTX=DW+0.914, STICKX=SW+0.914, HPOST=1.07, HCEN=0.914, H99=0.991, FT=0.3048;
const MG=0xff4fd8, SIL=0xaec4d6;
const NETST=()=>({xs:POSTX, hp:HPOST, hc0:H99, hc:HCEN, k:1, exg:1, op:1, heat:0, strap:1, loose:0, postH:null, sticks:0, ghost:0, glowV:0, cen:null});
function cordY(x,s){ const ax=Math.abs(x), xs=s.xs; if(ax>=xs) return s.hp;
  const a=xs*1.6, f=(Math.cosh(xs/a)-Math.cosh(x/a))/(Math.cosh(xs/a)-1); const free=s.hp-(s.hp-s.hc0)*f;
  const vv=s.hc+(s.hp-s.hc)*ax/xs; const y=lerp(free,vv,s.k); return s.hp-(s.hp-y)*s.exg; }
const NET=(()=>{
  const G=new THREE.Group(); scene.add(G);
  const NV=161, NH=10, X0=-POSTX, DX=2*POSTX/(NV-1);
  const nseg=NV+NH*(NV-1); const pos=new Float32Array(nseg*6), col=new Float32Array(nseg*6);
  const mg=new THREE.BufferGeometry(); mg.setAttribute('position',new THREE.BufferAttribute(pos,3)); mg.setAttribute('color',new THREE.BufferAttribute(col,3));
  const mm=new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:0.55,blending:THREE.AdditiveBlending,depthWrite:false});
  const mesh=new THREE.LineSegments(mg,mm); mesh.frustumCulled=false; G.add(mesh);
  // 网沿白带（深 5–6.35 cm，取 6 cm）
  const bp=new Float32Array(NV*2*3), bi=[]; for(let i=0;i<NV-1;i++){ const a=i*2; bi.push(a,a+1,a+2, a+1,a+3,a+2); }
  const bg=new THREE.BufferGeometry(); bg.setAttribute('position',new THREE.BufferAttribute(bp,3)); bg.setIndex(bi);
  const bm=new THREE.MeshPhysicalMaterial({color:0xe8eef4,emissive:0xffffff,emissiveIntensity:GLOW.emissiveWhite,roughness:0.55,sheen:0.6,sheenRoughness:0.5,sheenColor:new THREE.Color(0xffffff),side:THREE.DoubleSide,transparent:true});   // 网带：帆布质感（sheen）
  const band=new THREE.Mesh(bg,bm); band.frustumCulled=false; G.add(band);
  // 中央带（宽 5 cm，全白）：从网沿到地面锚点；松开时向前鼓出
  const SN=16, sp=new Float32Array((SN+1)*2*3), si=[]; for(let i=0;i<SN;i++){ const a=i*2; si.push(a,a+1,a+2, a+1,a+3,a+2); }
  const sg=new THREE.BufferGeometry(); sg.setAttribute('position',new THREE.BufferAttribute(sp,3)); sg.setIndex(si);
  const sm=new THREE.MeshPhysicalMaterial({color:0xf4f7fa,emissive:0xffffff,emissiveIntensity:GLOW.emissiveWhite,roughness:0.5,sheen:0.6,sheenRoughness:0.5,sheenColor:new THREE.Color(0xffffff),side:THREE.DoubleSide,transparent:true});
  const strap=new THREE.Mesh(sg,sm); strap.frustumCulled=false; G.add(strap);
  const anchor=new THREE.Mesh(new THREE.TorusGeometry(0.035,0.01,8,20),new THREE.MeshStandardMaterial({color:0xc8d4e0,metalness:0.8,roughness:0.3,transparent:true})); anchor.position.set(0,0.02,0.0); G.add(anchor);
  const pmat=new THREE.MeshPhysicalMaterial({color:0xdde8f0,metalness:0.9,roughness:0.22,clearcoat:1,clearcoatRoughness:0.08,envMapIntensity:5,transparent:true});   // 网柱：拉丝金属＋清漆，吃环境反射
  const posts=[-1,1].map(s=>{ const m=new THREE.Mesh(new THREE.CylinderGeometry(0.045,0.05,1,16),pmat); m.position.x=s*POSTX; G.add(m); return m; });
  const kmat=new THREE.MeshPhysicalMaterial({color:0xffe2a0,emissive:0xffc24a,emissiveIntensity:0.3,metalness:0.6,roughness:0.25,clearcoat:1,clearcoatRoughness:0.1,envMapIntensity:4,transparent:true});
  const sticks=[-1,1].map(s=>{ const m=new THREE.Mesh(new THREE.CylinderGeometry(0.03,0.03,1,12),kmat); m.position.x=s*STICKX; G.add(m); return m; });
  const ghost=fatLine(0x9fd8ff,2,true); G.add(ghost);
  const cA=new THREE.Color(0x9fc4e0), cLow=new THREE.Color(CY), cHigh=new THREE.Color(OR), tmp=new THREE.Color();
  let S=NETST();
  function upd(s){ S=s; G.visible=s.op>0.003; if(!G.visible) return; const bot=0.04; let n=0;
    for(let i=0;i<NV;i++){ const x=X0+i*DX, y=cordY(x,s)-0.055;
      const h=clamp((cordY(x,s)-s.hc)/Math.max(0.01,s.hp-s.hc)); tmp.copy(cA).lerp(h<0.5?cLow.clone().lerp(cA,h*2):cA.clone().lerp(cHigh,(h-0.5)*2),s.heat).multiplyScalar(0.55);
      pos.set([x,bot,0,x,y,0],n*6); col.set([tmp.r,tmp.g,tmp.b,tmp.r,tmp.g,tmp.b],n*6); n++; }
    for(let j=1;j<=NH;j++) for(let i=0;i<NV-1;i++){ const xa=X0+i*DX, xb=xa+DX; const ya=bot+(cordY(xa,s)-0.055-bot)*j/(NH+1), yb=bot+(cordY(xb,s)-0.055-bot)*j/(NH+1);
      const h=clamp((cordY(xa,s)-s.hc)/Math.max(0.01,s.hp-s.hc)); tmp.copy(cA).lerp(h<0.5?cLow.clone().lerp(cA,h*2):cA.clone().lerp(cHigh,(h-0.5)*2),s.heat).multiplyScalar(0.45);
      pos.set([xa,ya,0,xb,yb,0],n*6); col.set([tmp.r,tmp.g,tmp.b,tmp.r,tmp.g,tmp.b],n*6); n++; }
    mg.attributes.position.needsUpdate=true; mg.attributes.color.needsUpdate=true; mm.opacity=0.55*s.op;
    for(let i=0;i<NV;i++){ const x=X0+i*DX, y=cordY(x,s); bp.set([x,y,0.004, x,y-0.06,0.004],i*6); } bg.attributes.position.needsUpdate=true; bg.computeVertexNormals(); bm.opacity=s.op;
    const top=cordY(0,s)-0.03, L0=top-0.02;
    for(let i=0;i<=SN;i++){ const t=i/SN, y=lerp(top,0.02,t), z=0.012+s.loose*0.16*Math.sin(Math.PI*t)+s.loose*0.05*t; sp.set([-0.025,y,z, 0.025,y,z],i*6); }
    sg.attributes.position.needsUpdate=true; sg.computeVertexNormals(); sm.opacity=s.op*s.strap; strap.visible=s.strap>0.003; anchor.material.opacity=s.op*s.strap; anchor.visible=strap.visible;
    const ph=s.postH??s.hp; posts.forEach(m=>{ m.scale.y=ph+0.025; m.position.y=(ph+0.025)/2; }); pmat.opacity=s.op;
    sticks.forEach(m=>{ const h=Math.max(0.001,(s.hp+0.02)*s.sticks); m.scale.y=h; m.position.y=h/2; m.visible=s.sticks>0.003; }); kmat.opacity=s.op;
    if(s.ghost>0.003){ const g2=Object.assign({},s,{xs:POSTX}); const pts=[]; for(let i=0;i<=80;i++){ const x=-POSTX+i*2*POSTX/80; pts.push(V(x,cordY(x,g2),0.01)); } setLine(ghost,pts); ghost.material.opacity=0.8*s.ghost*s.op; } else ghost.material.opacity=0; }
  return {G,upd,get S(){ return S; },band,strap,posts,sticks}; })();
// 演示绳（片头、反转、受力对比）：两点之间一根发光的绳。shape：sag＝下垂深度，k＝被中间一点拉成 V 的程度，cy＝V 的最低点
function ropePts(x0,x1,yTop,sag,k,cyV,n=96,a=null){ const half=(x1-x0)/2, xc=(x0+x1)/2; a=a||half*0.55; const out=[];
  const c0=Math.cosh(half/a);
  for(let i=0;i<=n;i++){ const x=x0+i*(x1-x0)/n, u=x-xc; const f=(c0-Math.cosh(u/a))/(c0-1); const free=yTop-sag*f; const vv=cyV+(yTop-cyV)*Math.abs(u)/half; out.push([x,lerp(free,vv,k)]); } return out; }
// 镜头空间里画一条折线（pts 是 [x,y]，d 距离）
function hline(col,w,pts,o,d=9,dashed=false){ const l=ln(col,w,dashed); setLine(l,pts.map(p=>hp(p[0],p[1],d))); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=20; return l; }
function harrow(col,w,x0,y0,x1,y1,o,head=0.16,d=9){ hline(col,w,[[x0,y0],[x1,y1]],o,d); const a=Math.atan2(y1-y0,x1-x0); for(const s of [-1,1]) hline(col,w,[[x1,y1],[x1-head*Math.cos(a+s*0.45),y1-head*Math.sin(a+s*0.45)]],o,d); }
// 世界点 → 镜头空间（d=9 平面上的 x、y）：字贴着物体放，但字号不随远近变
function toHud(wp){ camera.updateMatrixWorld(); const p=wp.clone().applyMatrix4(camera.matrixWorldInverse); const k=9/Math.max(0.05,-p.z); return [p.x*k,p.y*k]; }
function alab(k,str,wp,dx,dy,o,opt={}){ const [x,y]=toHud(wp); const t=lab(k,str,x+dx,y+dy,o,opt); if(opt.lead&&o>0.01) hline(opt.leadCol||CY,1.5,[[x,y],[x+dx*0.85,y+dy-(dy>0?0.14:-0.14)]],o*0.7); return t; }
function anum(key,str,col,size,wp,dx,dy,o){ const [x,y]=toHud(wp); return num(key,str,col,size,x+dx,y+dy,o); }
// 世界坐标里的竖直量尺：底到顶一根线、两头横档
function wruler(col,x,y0,y1,z,o,w=3,tick=0.06){ const l=ln(col,w); setLine(l,[V(x,y0,z),V(x,y1,z)]); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=19;
  for(const y of [y0,y1]){ const t=ln(col,w); setLine(t,[V(x-tick,y,z),V(x+tick,y,z)]); t.material.opacity=o; t.material.depthTest=false; t.renderOrder=19; } }
function wline(col,w,pts,o,dashed=false,dt=false){ const l=ln(col,w,dashed); setLine(l,pts); l.material.opacity=o; l.material.depthTest=dt; l.renderOrder=19; return l; }
// 真空弹道（同 net_geometry.py）：v m/s、出射角 th、击球高 y0；s 为水平距离
const G9=9.81, KMH=100/3.6;
const yAt=(s,v,th,y0)=>y0+s*Math.tan(th)-G9*s*s/(2*v*v*Math.cos(th)**2);
function landAngle(v,R,y0){ const a=G9*R*R/(2*v*v), disc=R*R-4*a*(a-y0); return Math.atan((R-Math.sqrt(disc))/(2*a)); }
function clipAngle(v,s,y0,h){ const a=G9*s*s/(2*v*v), disc=s*s-4*a*(a-(y0-h)); return Math.atan((s-Math.sqrt(disc))/(2*a)); }
const hLin=(x)=>HCEN+(HPOST-HCEN)*Math.min(Math.abs(x),STICKX)/STICKX;
// 两条典型来回（边线内 1 m 击球，落到对面底线内 1 m）：沿线、斜线
const MOD=(()=>{ const x0=SW-1, z0=L, out={};
  for(const [k,x1] of [['dtl',x0],['cc',-x0]]){ const z1=-(L-1); const t=(0-z0)/(z1-z0); const xn=x0+t*(x1-x0); const sN=Math.hypot(xn-x0,z0), R=Math.hypot(x1-x0,z1-z0);
    const h=hLin(xn), th=landAngle(KMH,R,1.0), clr=yAt(sN,KMH,th,1.0)-h, cl=clipAngle(KMH,sN,1.0,h);
    out[k]={x0,z0,x1,z1,xn,sN,R,h,th,clr,win:th-cl}; } return out; })();
// 3D 球轨迹：从 (x0,z0) 到 (x1,z1)，按弹道画；k 0–1 是飞行进度。返回当前球心
function flight(key,col,m,k,o,{exgY=1,trail=true,ballS=0.45}={}){ const pts=[]; const N=60, kk=clamp(k);
  for(let i=0;i<=N*kk;i++){ const f=i/N, s=f*m.R; pts.push(V(lerp(m.x0,m.x1,f),1+(yAt(s,KMH,m.th,1.0)-1)*exgY,lerp(m.z0,m.z1,f))); }
  const f=kk, s=f*m.R, P=V(lerp(m.x0,m.x1,f),1+(yAt(s,KMH,m.th,1.0)-1)*exgY,lerp(m.z0,m.z1,f));
  if(trail&&pts.length>1){ const l=ln(col,4); setLine(l,pts); l.material.opacity=o*0.85; }
  if(k>0&&k<1.0) showB(bl(),P,o,ballS); return P; }
// 年代网（④）：英尺制
const YEARS=[ {y:1874, post:7*FT, cen:null, gap:null},
              {y:1877, post:5*FT, cen:3.25*FT, gap:21},
              {y:1878, post:4.75*FT, cen:3*FT, gap:21},
              {y:1880, post:4*FT, cen:3*FT, gap:12},
              {y:1882, post:3.5*FT, cen:3*FT, gap:6} ];
// 粒子流（⑥ 扇形）：沿三条射线流动，粒子数按百分比分
function fanFlow(origin,ends,shares,cols,u,o){ let i0=0; const n=1600; for(let b=0;b<ends.length;b++){ const m=Math.round(n*shares[b]); const cc=new THREE.Color(cols[b]);
    for(let i=i0;i<Math.min(n,i0+m);i++){ const p=PTS[i]; const f=(p[3]+u*0.35)%1; const e=ends[b]; const spread=0.6+1.6*f;
      const x=lerp(origin.x,e.x,f)+(p[0]/16)*spread*0.5, z=lerp(origin.z,e.z,f)+(p[2]/8)*spread*0.3, y=0.25+Math.sin(Math.PI*f)*1.4+(p[1]/9)*0.15;
      cset(pt,i,x,y,z,cc.r,cc.g,cc.b,o*(0.35+0.65*p[4])*Math.sin(Math.PI*f)); } i0+=m; }
  for(let i=i0;i<n;i++) cset(pt,i,0,-50,0,0,0,0,0); cdone(pt); }
// 拆字：同一行 3D 字做两份，各用一张裁切平面只留一半（反转镜头里白带子把「CATENARY · 1691」扯断）
const CLIP={L:new THREE.Plane(), R:new THREE.Plane()};
function splitText(key,str,col,size,x,y,o,split,cutX=0){ const A=t3d(key+'L',str,col,size), B=t3d(key+'R',str,col,size);
  if(!A.m.material.clippingPlanes){ A.m.material.clippingPlanes=[CLIP.L]; A.e.material.clippingPlanes=[CLIP.L]; B.m.material.clippingPlanes=[CLIP.R]; B.e.material.clippingPlanes=[CLIP.R]; }
  const e=clamp(split), fall=e*e;
  for(const [O,sg,P] of [[A,-1,CLIP.L],[B,1,CLIP.R]]){ O.g.position.copy(hp(x+sg*(0.25*e+1.6*fall),y-2.4*fall,9)); O.g.quaternion.copy(camera.quaternion); O.g.rotateOnAxis(V(0,0,1),-sg*0.55*fall); O.g.updateMatrixWorld(true);
    // 裁切平面跟着那一半走：法线随它旋转、过它的切口（字的局部坐标里 x=cutX-x 那条竖线）
    const nn=V(sg,0,0).applyQuaternion(O.g.quaternion); P.setFromNormalAndCoplanarPoint(nn,O.g.localToWorld(V(cutX-x,0,0)));
    t3op(O,o*(1-ss(0.75,1,e))); }
  return [A,B]; }

function hideAll(){
  courtG.visible=false; courtG.userData.mat.opacity=1; courtG.rotation.set(0,0,0); courtG.position.set(0,0,0); courtG.children[1].visible=false;
  HUM.forEach(H=>{ humanOp(H,0); H.root.position.set(0,0,0); H.root.rotation.set(0,0,0); H.root.scale.setScalar(1); });
  BALLS.forEach(b=>{ b.m.visible=false; b.gl.visible=false; }); bI=0;
  LN.forEach(l=>{ l.material.opacity=0; l.material.dashed=false; l.material.depthTest=false; l.renderOrder=0; }); lnI=0; RG.forEach(r=>r.material.opacity=0); rgI=0; GS.forEach(s=>{ s.material.opacity=0; s.visible=false; }); gsI=0;
  for(const k in TT) op(TT[k],0); for(const k in TB) TB[k].g.visible=false; for(const k in text3D) t3op(text3D[k],0); chide(pt);
  beamMat.uniforms.uOp.value=0; rimL.intensity=0; rimR.intensity=0; DOF.on=false; MOTE_SPEED=1; SLOW=null; ST_RATE=0.0003;
  NET.upd(Object.assign(NETST(),{op:0})); }
function num(key,str,col,size,x,y,o,d=9){ const n=t3d(key,str,col,size); hud(n,x,y,d); t3op(n,o); if(!n.g.userData.ndt){ n.g.traverse(m=>{ if(m.material){ m.material.depthTest=false; m.renderOrder=24; } }); n.g.userData.ndt=1; } return n; }
function courtOn(o=1){ courtG.visible=o>0.003; courtG.userData.mat.opacity=o; courtG.children[1].visible=false; }
const beatT=(k)=>TL.beat.hit+k*TL.beat.p;   // 第 k 拍（HIT＝0）的片内秒
const pulse=(u,t,w=0.35)=>u>t?Math.exp(-(u-t)/w):0;

// ---------- 1 钩子：贴着网沿从网柱滑到中央 → 两端 1.07 / 中间 0.914 / 矮 15.6 → 编织问句 → 网松了？→ 只剩一根绳，垂成曲线 → 起势 ----------
function shotHook(u,D){
  const DIP=ev('dip',3.4), PO=ev('post',5.0), MI=ev('mid',6.1), DF=ev('diff',8.2), Q=ev('q',9.8), LO=ev('loose',11.4), RO=ev('rope',12.5), CU=ev('curve',14.6), NA=ev('name',16.2);
  rims(GO,CY,4); beamMat.uniforms.uOp.value=0.12;
  if(u<LO){ courtOn(1); ST_RATE=u<PO?0.004:0.0012;
    const s=NETST(); NET.upd(s);
    if(u<PO-0.2){ const k=ss(0,PO,u); look(lerp(6.1,1.4,k),lerp(1.22,1.08,k),lerp(1.9,2.3,k),lerp(3.4,-0.4,k),lerp(1.0,0.92,k),0); DOF.on=true; DOF.focus=2.2; DOF.ap=0.0002;
      const g=gs(GO,0.55,0.55*ss(DIP,DIP+0.3,u)*(0.75+0.25*Math.sin(u*6))); g.position.set(0,HCEN,0.02);
      if(u>DIP){ const pts=[]; const kk=ss(DIP,DIP+0.9,u); for(let i=0;i<=40;i++){ const x=-1.6+3.2*i/40*kk; pts.push(V(x,cordY(x,s)+0.004,0.02)); } wline(GO,3,pts,0.9*(1-ss(PO-0.6,PO-0.2,u)),false,true); }
      alab('hkDip',T('塌下去了？','sagging?'),V(0,HCEN,0),0.9,0.9,ss(DIP,DIP+0.3,u)*(1-ss(PO-0.6,PO-0.2,u)),{size:0.36,color:'#ffe2a0',glow:GOLD,lead:true,leadCol:GO});
      return; }
    // 正面：网柱到中央，量尺立起
    const k2=ss(PO-0.2,MI+0.6,u); look(lerp(4.6,1.6,k2),lerp(1.15,1.02,k2),lerp(6.4,3.4,k2),lerp(3.6,0.5,k2),lerp(0.75,0.86,k2),0);
    const ruP=ss(PO,PO+0.4,u), ruM=ss(MI,MI+0.4,u), qo=1-ss(Q-0.9,Q-0.4,u);
    wruler(CY,POSTX-0.12,0,HPOST*ruP,0.05,ruP*qo); alab('hkP',T('1.07 米','1.07 m'),V(POSTX-0.12,HPOST,0),-0.2,0.55,ruP*qo,{size:0.4,color:'#bff3ff'});
    wruler(GO,0.12,0,HCEN*ruM,0.05,ruM*qo); alab('hkM',T('0.914 米','0.914 m'),V(0.12,HCEN,0),0.5,-0.95,ruM*qo,{size:0.4,color:'#ffe2a0',glow:GOLD});
    const df=ss(DF,DF+0.35,u); wline(0x9fd8ff,2,[V(-0.6,HPOST,0.03),V(POSTX,HPOST,0.03)],0.7*ruM*qo,true);
    wruler(GO,0.0,HCEN,HPOST,0.06,df*qo,4,0.12);
    anum('hkD','-15.6 cm',GO,0.42,V(0,(HPOST+HCEN)/2,0),-1.55,0.15,df*qo); if(u>DF&&u<DF+1.3) shockRing(hp(...toHud(V(0,(HPOST+HCEN)/2,0)),9),(u-DF)/1.3,GO,2.2,0.7,true);
    const qq=bt('hkQ',T('球网中间，为什么矮？','Why is the net lower in the middle?'),{size:0.9,glow:'rgba(255,194,74,0.5)',fx:'weave',accent:T('矮','lower')}); hud(qq,0,1.25,9); qq.update(u,Q-0.8,RO-0.3,0.92);
    return; }
  // 网松了 → 球场淡出 → 只剩一根绳
  const kL=ss(LO,LO+0.8,u), kR=ss(RO,RO+1.2,u);
  courtOn(1-kR); ST_RATE=0.0005;
  const wob=Math.exp(-(u-LO)*1.6)*Math.sin((u-LO)*9)*0.05;
  const s=Object.assign(NETST(),{k:1-kL,hc0:lerp(H99,0.72,kL)+wob,op:1-kR}); NET.upd(s);
  look(lerp(0,0,kR),lerp(1.25,1.05,kR),lerp(9.5,10.5,kR)-ss(NA,NA+1.6,u)*2.2,0,lerp(0.75,0.6,kR),0);
  // 绳：从网绳的位置长出来，越垂越深（演示：两柱 ±4，下垂 1.4）
  if(u>RO-0.2){ const sag=lerp(HPOST-0.72,1.45,ss(RO,RO+1.6,u)), xh=lerp(POSTX,4.0,ss(RO,RO+1.6,u)); const P=ropePts(-xh,xh,HPOST+0.6*ss(RO,RO+1.6,u),sag,0,0);
    const l=ln(0xffe6b0,4); setLine(l,P.map(p=>V(p[0],p[1],0))); l.material.opacity=ss(RO-0.2,RO+0.4,u);
    for(const sg of [-1,1]){ const pl=ln(SIL,6); setLine(pl,[V(sg*xh,0,0),V(sg*xh,HPOST+0.6*ss(RO,RO+1.6,u),0)]); pl.material.opacity=0.8*ss(RO,RO+0.6,u); }
    // 光点沿曲线跑一遍
    if(u>CU){ const f=clamp((u-CU)/1.4), i=Math.min(P.length-1,Math.floor(f*(P.length-1))); const g=gs(0xffe6b0,0.5,0.8*(1-ss(0.9,1,f))); g.position.set(P[i][0],P[i][1],0.02);
      const tr=ln(GO,6); setLine(tr,P.slice(0,i+1).map(p=>V(p[0],p[1],0.01))); tr.material.opacity=0.9; }
    // 起势：粒子向绳的最低点聚拢
    if(u>NA){ const k=ss(NA,D,u); const c=V(0,P[48][1],0); const cc=new THREE.Color(GO);
      for(let i=0;i<1600;i++){ const p=PTS[i]; const r=(1-k)*(3+p[3]*4); const th=p[4]*6.283+u*(0.6+p[3]); cset(pt,i,c.x+Math.cos(th)*r,c.y+Math.sin(th)*r*0.6,c.z+(p[2]/8)*r,cc.r,cc.g,cc.b,0.6*k*(0.4+0.6*p[4])); } cdone(pt); } }
}

// ---------- 2 HIT：「悬链线 CATENARY · 1691」→ 方程 → 白带子落下把字扯断、把绳拉成 V →「可它，不是悬链线」→ 镜头钻到中央带 ----------
const slowIn=(u,ws)=>{ for(const w of ws) if(u>=w[0]&&u<=w[1]){ SLOW=w; return; } };   // 快动作窗口：引擎累积 6 子帧做真运动模糊
// ---------- GSAP 动字：CATENARY · 1691 逐字砸下（第 2 拍落地）→ 每拍轻脉冲 → 白带子从正中扯断，两半逐字飞散下坠 ----------
// GSAP（gsap.com，Standard no-charge license）只当缓动/编排引擎用：时间线暂停，每帧 tl.time(u) 定格，逐帧可复现；全部用 fromTo，乱序跳帧也一致
let KT=null;
function kinTitle(u,B,TE){
  const str=T('CATENARY·1691','HANGING CHAIN·1691'), size=0.34, y0=0.95;
  if(!KT||KT.str!==str||KT.TE!==TE){ if(KT) KT.tl.kill();
    const ch=[...str], L=[]; let x=0; const gap=size*0.1;
    ch.forEach((c,i)=>{ if(c===' '){ x+=size*0.45; return; } const o=t3d('kt'+i+c,c,GO,size); o.m.geometry.computeBoundingBox(); const bb=o.m.geometry.boundingBox; const w=Math.max(size*0.25,bb.max.x-bb.min.x);
      if(c==='·'){ x+=size*0.18; } L.push({o,cx:x+w/2,y:0,z:0,rx:0,rz:0,s:1,op:0,dx:0}); x+=w+gap+(c==='·'?size*0.18:0); });
    const tw=x-gap; L.forEach(l=>{ l.cx-=tw/2; });
    let seed=7; const rnd=()=>{ seed=(seed*16807)%2147483647; return seed/2147483647; };
    const tl=gsap.timeline({paused:true}); const n=L.length, each=0.035, dur=0.42, mid=(n-1)/2;
    L.forEach((l,i)=>{ const d=Math.abs(i-mid)*each, st=2*B-dur-mid*each+d, sg=l.cx<0?-1:1;
      tl.fromTo(l,{y:2.4,z:3.2,rx:-1.3,rz:(rnd()-0.5)*1.6,s:1.9,op:0},{y:0,z:0,rx:0,rz:0,s:1,op:1,duration:dur,ease:'back.out(2.2)',immediateRender:false},st);
      for(let k=3;k*B<TE-0.25;k++) tl.fromTo(l,{s:1.07},{s:1,duration:B*0.9,ease:'power2.out',immediateRender:false},k*B+d*0.25);
      const dd=Math.abs(l.cx)*0.06;
      tl.fromTo(l,{dx:0},{dx:sg*(0.32+Math.abs(l.cx)*0.10),duration:0.28,ease:'expo.out',immediateRender:false},TE+dd);
      tl.fromTo(l,{y:0,rz:0,rx:0,op:1},{y:-3.4,rz:sg*(0.7+rnd()*0.9),rx:0.6+rnd()*0.8,op:0,duration:0.95,ease:'power3.in',immediateRender:false},TE+0.2+dd); });
    KT={str,TE,L,tl}; }
  KT.tl.time(Math.max(0,u));
  for(const l of KT.L){ hud(l.o,l.cx+l.dx,y0+l.y,9); l.o.m.position.set(0,0,l.z); l.o.m.rotation.set(l.rx,0,l.rz); l.o.m.scale.setScalar(l.s); t3op(l.o,l.op); }
}
function shotTitle(u,D){
  const YR=ev('yr',1.6), EQ=ev('eq',2.7), TW=ev('twist',5.85), TE=ev('tear',6.9), AN=ev('ans',10.6), SA=ev('strap',12.2);
  const B=TL.beat.p; rims(GO,CY,5); slowIn(u,[[TE-0.05,TE+1.3]]);
  if(u<AN-0.05){
    look(0,1.3,10.4-ss(0,AN,u)*0.8,0,1.25,0);
    // 绳：HIT 前一刻的深悬链线；白带子落下后被拉成 V
    const pull=ss(TE+0.3,TE+1.0,u); const P=ropePts(-4,4,HPOST+0.6,1.45,pull,-0.25);
    const l=ln(0xffe6b0,4); setLine(l,P.map(p=>V(p[0],p[1],0))); l.material.opacity=1;
    for(const sg of [-1,1]){ const pl=ln(SIL,6); setLine(pl,[V(sg*4,0,0),V(sg*4,HPOST+0.6,0)]); pl.material.opacity=0.8; }
    if(u<0.9){ shockRing(V(0,P[48][1],0.05),u/0.9,GO,6,0.9,true); burst(V(0,P[48][1],0),u/0.9,GO,7,0.9); }
    // 大字：悬链线（粒子汇聚，HIT 当拍）→ CATENARY · 1691（第 2 拍砸下）
    const t1=bt('ttCat',T('悬链线','CATENARY'),{size:1.55,glow:'rgba(255,194,74,0.55)',fx:'particles',accent:T('悬链线',null)}); hud(t1,0,2.05,9); t1.update(u,0.0,TE,1);
    kinTitle(u,B,TE);
    if(u>2*B&&u<2*B+1.2) shockRing(hp(0,0.95),(u-2*B)/1.2,GO,4.5,0.7,true);
    if(u>YR&&u<YR+1.0) shockRing(hp(2.0,0.95),(u-YR)/1.0,CY,2.0,0.6,true);
    const eqT=bt('ttEq',T('y = a · cosh(x / a)','hanging chain: a cosh curve'),{size:0.42,glow:'rgba(79,227,255,0.5)',fx:'write',thread:'#7fe4ff'}); hud(eqT,0,-0.05,9); eqT.update(u,EQ,TE-0.1,0.9);
    lab('ttEqN',T('1691 年：数学家们第一次解出了它','1691: first solved by mathematicians'),0,-1.6,ss(EQ+0.4,EQ+0.8,u)*(1-ss(TE-0.3,TE,u)),{size:0.26,color:'#bcd0e4'});
    // 白带子：从画面上方落下，穿过字（TE 当拍扯断），钩住绳的最低点往下拉到地锚
    const yR=toHud(V(0,P[48][1],0))[1], yG=toHud(V(0,-0.45,0))[1];
    if(u>TW){ const tip=u<TE?lerp(4.4,0.95,ss(TW,TE,u)):lerp(0.95,yR,ss(TE,TE+0.3,u)); const upO=u<TE+0.3?1:1-ss(TE+0.3,TE+0.7,u);
      if(upO>0.01){ const st=hline(0xffffff,9,[[0,4.6],[0,tip]],0.95*upO); st.renderOrder=23; }
      if(u>TE+0.3){ hline(0xffffff,9,[[0,yR],[0,yG]],ss(TE+0.3,TE+0.5,u)); const g=gs(0xffffff,0.35,0.6*ss(TE+0.3,TE+0.6,u)); g.position.copy(hp(0,yG)); }
      if(u>TE&&u<TE+1.0) shockRing(hp(0,0.95),(u-TE)/1.0,0xffffff,3.2,0.8,true); }
    if(u>TE+0.9){ const ang=gs(GO,0.7,0.6*ss(TE+0.9,TE+1.3,u)); ang.position.copy(hp(0,yR)); }
    const nt=bt('ttNot',T('可它，不是悬链线','But it is NOT a catenary'),{size:0.9,glow:'rgba(255,255,255,0.4)',fx:'shock',accent:T('不是','NOT'),accentColor:'#ff6a5a'}); hud(nt,0,1.55,9); nt.update(u,TE+0.9,AN-0.6,0.92);
    lab('ttV',T('中间被一点拉住：两段直线＋折角','pulled at one point: two straight runs + a kink'),0,-1.95,ss(TE+1.4,TE+1.9,u)*(1-ss(AN-0.6,AN-0.1,u)),{size:0.3,color:'#e8f4ff'});
    return; }
  // 钻到真实球网的中央带
  courtOn(1); ST_RATE=0.0008; const s=NETST(); NET.upd(s);
  const k=ss(AN,AN+1.6,u); look(lerp(1.4,0.42,k),lerp(1.2,0.7,k),lerp(3.2,1.25,k),0,lerp(0.8,0.5,k),0); DOF.on=true; DOF.focus=lerp(3.2,1.3,k); DOF.ap=0.00025;
  const so=ss(SA,SA+0.4,u); for(const sx of [-0.03,0.03]) wline(GO,2.5,[V(sx,0.02,0.03),V(sx,cordY(0,s)-0.03,0.03)],so*(0.7+0.3*Math.sin(u*5)),false,true);
  alab('ttS',T('中央带','CENTER STRAP'),V(0.03,0.55,0),-1.6,1.0,so,{size:0.42,color:'#ffe2a0',glow:GOLD,lead:true,leadCol:GO});
  alab('ttS2',T('宽 ≤ 5 厘米 · 必须全白 · ITF 规则第 1 条','≤ 5 cm wide · all white · ITF Rule 1'),V(0.03,0.55,0),-2.3,0.45,so,{size:0.26,color:'#bcd0e4'});
}

// ---------- 3 拉带子：网绳绷紧（1.8–2.0 kN）→ 带子松开、中间约 99 cm（低约 8 cm）→ 带子一拉 91.4（再 7.7）→ 一半一半 → 受力：自重=光滑、单点=V → 浅 V＋金句 ----------
function shotStrap(u,D){
  const TN=ev('tense',2.7), KN=ev('kn',3.7), LB=ev('lb',6.4), LO=ev('loose',10.1), C99=ev('c99',12.8), D8=ev('d8',14.4), PU=ev('pull',18.6), C91=ev('c914',19.2), D77=ev('d77',21.3),
        HA=ev('half',25.5), OT=ev('other',27.7), CH=ev('chain',30.9), PT=ev('point',34.6), KK=ev('kink',37.8), VV=ev('v',42.0), QU=ev('quote',43.1); slowIn(u,[[PU-0.05,PU+0.8]]);
  rims(GO,CY,4);
  if(u<CH-0.05){ courtOn(1); ST_RATE=0.0005;
    const kt=ss(TN,TN+1.4,u), kp=ss(PU,PU+0.9,u); const wob=u>TN+1.4?Math.exp(-(u-TN-1.4)*3)*Math.sin((u-TN-1.4)*14)*0.01:0;
    const cam=ss(0,HA,u), cz=ss(LO-0.4,LO+1.4,u)*(1-ss(HA-0.7,HA+0.3,u)); const ex=1+2*cz, E=y=>HPOST-(HPOST-y)*ex;
    const s=Object.assign(NETST(),{k:kp,hc0:lerp(0.80,H99,kt)+wob,loose:1-ss(PU-0.3,PU+0.3,u),exg:ex}); NET.upd(s);
    look(lerp(lerp(2.6,2.1,cam),0.9,cz),lerp(lerp(1.12,1.02,cam),1.0,cz),lerp(lerp(4.6,3.9,cam),4.3,cz),lerp(lerp(-1.2,-1.0,cam),0.9,cz),lerp(lerp(0.82,0.86,cam),0.92,cz),0);
    lab('stEx3',T('竖向放大 3 倍示意','vertical ×3 for clarity'),3.4,-1.6,cz,{size:0.24,color:'#aab8c8'});
    // 张力计（HUD 圆表）：0–2.5 kN，绿区 1.8–2.0
    const go=ss(TN-0.3,TN+0.2,u)*(1-ss(LO-0.5,LO+0.1,u)); if(go>0.01){ const cx=-3.7, cy=1.15, r=0.62; const val=lerp(0.4,1.9,kt);
      const arcP=(a0,a1)=>{ const P=[]; for(let i=0;i<=40;i++){ const a=lerp(a0,a1,i/40); P.push([cx+r*Math.cos(a),cy+r*Math.sin(a)]); } return P; };
      const A=v=>Math.PI*(1.15-1.3*v/2.5); hline(0x5a6a80,4,arcP(A(0),A(2.5)),go); hline(MT,7,arcP(A(1.8),A(2.0)),go); hline(GO,5,arcP(A(0),A(val)),go);
      hline(0xffffff,3,[[cx,cy],[cx+r*0.92*Math.cos(A(val)),cy+r*0.92*Math.sin(A(val))]],go);
      num('stKN','1.8–2.0 kN',GO,0.3,cx,cy-0.55,go*ss(KN,KN+0.3,u)); lab('stKNl',T('网绳张力 · ITF 建议','net cord tension · ITF advice'),cx,cy+0.85,go,{size:0.26,color:'#bcd0e4'});
      lab('stLB',T('≈ 400–450 磅','≈ 400–450 lb'),cx,cy-1.05,go*ss(LB,LB+0.3,u),{size:0.3,color:'#ffe2a0',glow:GOLD});
      // 绳上的张力箭头：朝网柱
      const ao=go*ss(TN,TN+0.6,u); for(const x of [1.2,2.4]){ const y=cordY(x,s)+0.05; const a=toHud(V(x,y,0)), b=toHud(V(x+0.55,cordY(x+0.55,s)+0.05,0)); harrow(CY,3,a[0],a[1],b[0],b[1],ao*0.8,0.12); } }
    // 带子松开（标出来）→ 中间约 99 cm（低约 8 cm）
    const lo=ss(LO,LO+0.4,u)*(1-ss(PU-0.3,PU,u)); alab('stLo',T('中央带：先松开','strap: loosened first'),V(0.0,0.45,0.1),-1.3,0.2,lo,{size:0.3,color:'#e8f4ff',lead:true});
    const r99=ss(C99,C99+0.4,u); const yC=cordY(0,s);
    
    const t99=r99*(1-ss(PU,PU+0.3,u)), t91=ss(C91,C91+0.3,u);
    alab('st99',T('≈ 99 厘米','≈ 99 cm'),V(-0.1,yC,0),-1.05,0.25,t99*(1-ss(HA-0.4,HA,u)),{size:0.42,color:'#bff3ff'});
    alab('st91',T('91.4 厘米','91.4 cm'),V(-0.1,yC,0),-1.05,-0.35,t91*(1-ss(HA-0.4,HA,u)),{size:0.46,color:'#ffe2a0',glow:GOLD});
    const d8=ss(D8,D8+0.4,u)*(1-ss(HA-0.4,HA,u)); wline(0x9fd8ff,3,[V(-2.2,E(HPOST),0.04),V(3.2,E(HPOST),0.04)],0.85*d8,true); wruler(CY,0.32,E(H99),E(HPOST),0.07,d8,3,0.05);
    alab('st8',T('低约 8 厘米','≈ 8 cm lower'),V(0.32,E((H99+HPOST)/2),0),1.15,0.1,d8,{size:0.32,color:'#bff3ff'});
    const d7=ss(D77,D77+0.4,u)*(1-ss(HA-0.4,HA,u)); wline(GO,3,[V(-2.2,E(H99),0.04),V(3.2,E(H99),0.04)],0.75*ss(PU,PU+0.3,u)*(1-ss(HA-0.4,HA,u)),true); wruler(GO,0.32,E(HCEN),E(H99),0.07,d7,3,0.05);
    anum('st77','7.7 cm',GO,0.32,V(0.32,E((H99+HCEN)/2),0),1.25,-0.6,d7); if(u>PU&&u<PU+1.2) shockRing(V(0,0.02,0),(u-PU)/1.2,GO,1.0,0.8,false);
    if(u>PU&&u<PU+0.9){ const g=gs(0xffffff,0.35,0.7*(1-ss(PU,PU+0.9,u))); g.position.set(0,cordY(0,s),0.03); }
    // 一半一半：HUD 竖条（15.6 cm 放大），上段青 7.9、下段金 7.7
    const ho=ss(HA,HA+0.4,u); if(ho>0.01){ const x=3.7, y0=0.0, y1=2.1, ym=lerp(y1,y0,7.9/15.6), og=ss(OT,OT+0.3,u);
      hline(CY,22,[[x,y1],[x,lerp(y1,ym,ss(HA,HA+0.6,u))]],ho*0.9); hline(GO,22,[[x,ym],[x,lerp(ym,y0,og)]],og*0.95);
      lab('stH1',T('绷紧后自然下垂 ≈ 8','cord sag ≈ 8'),x-1.6,(y1+ym)/2,ho,{size:0.3,color:'#bff3ff',plate:true}); lab('stH2',T('带子拉下 7.7','strap pull 7.7'),x-1.6,(ym+y0)/2,og,{size:0.3,color:'#ffe2a0',glow:GOLD,plate:true});
      num('stH3','15.6 cm',0xffffff,0.3,x,y1+0.38,ho); lab('stH4',T('一半 ＋ 一半','half + half'),x-1.75,y1+0.38,og,{size:0.32,color:'#ffffff'}); }
    return; }
  // 受力：左＝只受自重（均布小箭头）→ 光滑悬链线；右＝中间一点下拉 → 两段直线＋折角
  if(u<VV-0.05){ courtOn(0); look(0,0.6,11,0,0.6,0);
    const oL=ss(CH,CH+0.5,u), oR=ss(PT,PT+0.5,u);
    const P1=ropePts(-5.2,-0.8,1.3,1.1,0,0,60); hline(0xffe6b0,4,P1,oL); for(const sg of [-5.2,-0.8]) hline(SIL,6,[[sg,-1.0],[sg,1.3]],oL*0.8);
    for(let i=4;i<60;i+=6){ const p=P1[i]; harrow(CY,2.5,p[0],p[1]-0.04,p[0],p[1]-0.36,oL*ss(CH+0.2,CH+0.8,u)*0.85,0.08); }
    lab('chL',T('只受自重 → 光滑曲线（悬链线）','own weight only → smooth curve (catenary)'),-3.0,-1.55,oL,{size:0.28,color:'#bff3ff'});
    const pk=ss(PT+0.3,PT+1.2,u); const P2=ropePts(0.8,5.2,1.3,0.35,pk,-0.15,60); hline(0xffe6b0,4,P2,oR); for(const sg of [0.8,5.2]) hline(SIL,6,[[sg,-1.0],[sg,1.3]],oR*0.8);
    const cy2=P2[30][1]; harrow(0xffffff,6,3.0,cy2,3.0,cy2-0.9*ss(PT+0.1,PT+0.6,u),oR,0.16); lab('chF',T('中央带的拉力','strap force'),3.0,cy2-1.25,oR*ss(PT+0.4,PT+0.8,u),{size:0.26,color:'#ffffff'});
    lab('chR',T('中间一点下拉 → 两段直线＋折角','pulled at one point → two straight runs + a kink'),3.0,-1.55+0.0,oR,{size:0.28,color:'#ffe2a0',glow:GOLD});
    const ko=ss(KK,KK+0.4,u); if(ko>0.01){ const g=gs(GO,0.9,0.7*ko*(0.8+0.2*Math.sin(u*6))); g.position.copy(hp(3.0,cy2)); const a=P2[18], b=P2[42];
      harrow(GO,3.5,3.0,cy2,lerp(3.0,a[0],0.75),lerp(cy2,a[1],0.75),ko,0.13); harrow(GO,3.5,3.0,cy2,lerp(3.0,b[0],0.75),lerp(cy2,b[1],0.75),ko,0.13);
      lab('chK',T('折角','kink'),3.0,cy2+0.42,ko,{size:0.32,color:'#ffe2a0',glow:GOLD}); lab('chT',T('两边的张力 ＋ 带子的拉力，正好平衡','both tensions + strap force balance'),3.0,1.75,ko,{size:0.26,color:'#bcd0e4'}); }
    return; }
  // 真实球网：竖向放大看清浅 V，金句
  courtOn(1); ST_RATE=0.0006; const ex=lerp(1,6,ss(VV,VV+1.2,u)); const s=Object.assign(NETST(),{exg:ex,heat:ss(VV,VV+1.2,u)*0.7}); NET.upd(s);
  look(0,1.6,15.5,0,0.55,0);
  const vo=ss(VV+0.4,VV+1.2,u); const vp=[]; for(const x of [-POSTX,0,POSTX]) vp.push(V(x,cordY(x,s)+0.01,0.03)); wline(GO,4,vp,vo*0.9,false,false);
  lab('stEx',T('竖向放大 6 倍示意','vertical ×6 for clarity'),3.4,-1.5,vo,{size:0.26,color:'#aab8c8'});
  const qt=bt('stQ',T('它不是塌的，是被拉成这样的','Not sagging. Pulled into shape.'),{size:0.78,glow:'rgba(255,194,74,0.5)',fx:'shock',accent:T('拉','Pulled')}); hud(qt,0,1.65,9); qt.update(u,QU,D+5,0.92);
}

// ---------- 4 降网史：1874 七英尺 → 1877 五英尺／3 英尺 3 英寸 → 沿线穿越撞网、截击占优 → 1878 中间 3 英尺 → 1880 四英尺 → 1882 三英尺六／三英尺，用到今天 → 穿越球过了 ----------
function shotHist(u,D){
  const Y4=ev('y1874',3.7), Y7=ev('y1877',8.5), SZ=ev('size',10.1), P5=ev('p5',11.7), C33=ev('c33',13.3), PA=ev('pass',17.0), VO=ev('volley',19.2), DN=ev('down',23.9),
        Y8=ev('y1878',25.0), Y0=ev('y1880',27.7), Y2=ev('y1882',30.9), TD=ev('today',35.1), P2=ev('pass2',38.8), QQ=ev('q',44.2); slowIn(u,[[PA,PA+1.4],[P2,P2+1.4]]);
  rims(GO,CY,4); courtOn(1); ST_RATE=0.0005;
  // 当前年份（台阶式切换：每次 0.6 s 落下）
  const marks=[[0,0],[Y4,0],[Y7,1],[Y8,2],[Y0,3],[Y2,4]]; let i=0; for(let j=0;j<marks.length;j++) if(u>=marks[j][0]) i=marks[j][1];
  const prev=Math.max(0,i-1), tStep=marks.find(m=>m[1]===i)[0]; const e=i===0?1:ss(tStep,tStep+0.6,u); const bounce=e<1?0:Math.exp(-(u-tStep-0.6)*6)*Math.sin((u-tStep-0.6)*20)*0.015;
  const A=YEARS[prev], Bq=YEARS[i]; const post=lerp(A.post,Bq.post,e)+bounce;
  const cenA=A.cen??1.42, cenB=Bq.cen??1.42; const cen=lerp(cenA,cenB,e);
  const s=Object.assign(NETST(),{hp:post,hc:cen,postH:post,op:1}); NET.upd(s);
  const qz=ss(QQ,QQ+2.5,u);
  look(lerp(-5.2,0,qz),lerp(2.3,16,qz),lerp(11.5,9,qz),0,lerp(0.9,0,qz),lerp(0,0.5,qz));
  const o=1-ss(QQ,QQ+0.8,u);
  // 年代轴（HUD 底部）
  const yrs=YEARS.map(y=>y.y), x0=-4.4, x1=4.4, xa=y=>lerp(x0,x1,(y-1874)/8), ty=-1.62;
  hline(0x5a6a80,3,[[x0,ty],[x1,ty]],o*ss(Y4-0.5,Y4,u)); hline(GO,5,[[x0,ty],[xa(lerp(A.y,Bq.y,e)),ty]],o*ss(Y4-0.5,Y4,u));
  yrs.forEach((y,j)=>{ const on=j<=i; lab('hy'+y,String(y),xa(y),ty-0.32,o*ss(Y4-0.5,Y4,u)*(on?1:0.45),{size:0.26,color:on?'#ffe2a0':'#8090a4',glow:on?GOLD:CYAN}); const g=gs(on?GO:0x5a6a80,0.28,o*ss(Y4-0.5,Y4,u)*(on?0.8:0.4)); g.position.copy(hp(xa(y),ty)); });
  // 年份大数字＋网柱／中间读数
  const yo=o*ss(Y4,Y4+0.3,u); num('hyBig'+Bq.y,String(Bq.y),GO,0.5,3.7,1.95,yo*e); if(e<1) num('hyBig'+A.y,String(A.y),GO,0.5,3.7,1.95+0.6*e,yo*(1-e));
  const ftTxt=(m)=>{ const inch=Math.round(m/FT*12); const f=Math.floor(inch/12), r=inch%12; return T(r?`${f} 英尺 ${r} 英寸`:`${f} 英尺`, r?`${f} ft ${r} in`:`${f} ft`); };
  if(u>Y4-0.2){ alab('hpost'+Bq.y,T('网柱 ','posts ')+ftTxt(Bq.post),V(POSTX,post,0),-0.2,0.5,yo*e,{size:0.32,color:'#bff3ff'});
    if(Bq.cen) alab('hcen'+Bq.y,T('中间 ','centre ')+ftTxt(Bq.cen),V(0,cen,0),0,-1.0,yo*e*(Bq.y===1877?ss(C33,C33+0.3,u):1),{size:0.32,color:'#ffe2a0',glow:GOLD});
    else { alab('hcenU',T('中间：明显更矮（各家记载不一）','centre: much lower (sources differ)'),V(0,1.42,0),0,-1.15,yo*e,{size:0.28,color:'#e8f4ff'}); const g=gs(0x9fd8ff,0.9,0.35*yo*e); g.position.set(0,1.42,0.05); }
    if(Bq.gap) lab('hgap'+Bq.y,T(`两端比中间高 ${Bq.gap} 英寸`,`posts ${Bq.gap} in above centre`),-3.2,1.95,yo*e,{size:0.3,color:Bq.gap===6?'#ffe2a0':'#e8f4ff',glow:Bq.gap===6?GOLD:CYAN}); }
  wruler(CY,POSTX+0.25,0,post,0.05,yo,3,0.08);
  if(i===1){ const so=ss(SZ,SZ+0.4,u)*(1-ss(PA-0.5,PA,u)); lab('hsize',T('场地尺寸：从这一届起和今天一样','court size: same as today from here on'),-1.6,-1.0,so,{size:0.28,color:'#bcd0e4'}); }
  if(i>=2){ const lk=ss(Y8,Y8+0.5,u)*o; shockRing(V(0,0.02,0),clamp((u-Y8)/1.2),CY,1.2,lk*0.7,false); if(u>Y8+0.3) alab('hlock',T('中间：1878 年起就是 3 英尺','centre: 3 ft since 1878'),V(0,HCEN,0),-2.6,0.55,lk*(1-ss(P2-0.4,P2,u)),{size:0.28,color:'#bff3ff',lead:true}); }
  if(u>TD){ const to=ss(TD,TD+0.4,u)*o*(1-ss(P2-0.4,P2,u)); lab('htoday',T('1882 → 今天：1.07 米 / 0.914 米（ITF 2026）','1882 → today: 1.07 m / 0.914 m (ITF 2026)'),0,-1.0,to,{size:0.3,color:'#ffe2a0',glow:GOLD}); }
  // 沿线穿越：1877 撞网（红），1882 过网（绿）；网前一名截击手
  const passBall=(t0,ok,key)=>{ const k=clamp((u-t0)/1.1); if(k<=0) return; const x=SW-0.25, z0=L, z1=-L+2, fN=L/(z0-z1); const hNet=cordY(x,s);
    const yF=f=>lerp(0.9,0.2,f)+Math.sin(Math.PI*f)*0.7; const fEnd=ok?1:fN; const P=[]; const N=40;
    for(let j=0;j<=N;j++){ const f=fEnd*Math.min(k,1)*j/N; P.push(V(x,yF(f),lerp(z0,z1,f))); }
    const l=ln(ok?MT:RD,4); setLine(l,P); l.material.opacity=o*(1-ss(2.6,3.4,u-t0)); const last=P[P.length-1]; if(k<1) showB(bl(),last,o,0.5);
    if(!ok&&k>=0.98) shockRing(V(x,yF(fN),0.02),clamp((u-t0-1.08)/0.8),RD,0.9,o*0.9,true);
    alab(key,ok?T('穿越球过网','passing shot clears'):T('沿线穿越：撞网','down-the-line pass: into the net'),V(x,yF(fN),0),ok?-1.6:-1.7,0.6,o*ss(t0+0.3,t0+0.6,u)*(1-ss(t0+3.2,t0+3.7,u)),{size:0.3,color:ok?'#b8ffd8':'#ffb0a8',glow:ok?MINT:RED}); };
  if(u>PA&&u<DN) passBall(PA,false,'hPass1');
  if(u>P2&&u<QQ+0.5) passBall(P2,true,'hPass2');
  const vo=ss(VO,VO+0.5,u)*(1-ss(DN-0.4,DN,u))+ss(P2,P2+0.4,u)*(1-ss(QQ-0.3,QQ+0.2,u)); if(vo>0.01){ humanOp(RET,o*vo); place(RET,SW-1.2,-2.2,0); applyPose(RET,POSE[u>P2?'lungeF':'split']);
    alab('hVol',T('网前截击','net volleyer'),V(SW-1.2,1.9,-2.2),1.0,0.4,o*vo*(u<DN?1:0),{size:0.3,color:'#bff3ff'}); }
  if(u>P2) lab('hWhy2',T('当时的史料：降低网柱，让底线的穿越球能对付网前截击','period accounts: posts lowered so baseline passes can beat the volley'),0,-1.0,ss(P2+0.3,P2+0.7,u)*o,{size:0.28,color:'#e8f4ff'});
  // 结尾：升到俯视，15.6 cm 浮在网中央
  if(qz>0.01){ anum('hq156','15.6 cm',GO,0.5,V(0,1.0,0),0,1.0,ss(QQ+0.8,QQ+1.4,u)); }
}

// ---------- 5 勾股：单打场 23.77 × 8.23 → 斜线 25.15（+1.38）→ 沿边线过网约 104 cm / 斜线过中央 91.4 cm（浅 V 模型）→ 两球竞速 ----------
function shotDiag(u,D){
  const CO=ev('court',0.5), CR=ev('corner',5.3), PY=ev('pyth',7.4), HY=ev('hyp',8.0), PL=ev('plus',10.6), CX=ev('cross',13.3), DT=ev('dtl',14.9), CC=ev('cc',18.1), BO=ev('both',22.3), SA=ev('safe',25.0); slowIn(u,[[DT,DT+1.3],[CC,CC+1.3],[BO,BO+1.3]]);
  rims(GO,CY,4); courtOn(1); ST_RATE=0.0005;
  const A=V(SW,0.03,L), Bd=V(SW,0.03,-L), Cc=V(-SW,0.03,-L);
  if(u<CX-0.05){ const s=NETST(); NET.upd(s);
    const k=ss(0,CX,u); look(lerp(14,11,k),lerp(24,21,k),lerp(15,13,k),0,0,0.5);
    const co=ss(CO,CO+0.5,u);
    // 单打场边框发光
    wline(CY,3,[V(-SW,0.03,L),V(SW,0.03,L),V(SW,0.03,-L),V(-SW,0.03,-L),V(-SW,0.03,L)],co*0.7,false,true);
    alab('dgL','23.77 m',V(SW,0,0),1.0,0.0,co,{size:0.42,color:'#bff3ff'}); alab('dgW','8.23 m',V(0,0,-L),0,0.45,co,{size:0.42,color:'#ffd0f4',glow:'rgba(255,79,216,0.8)'});
    const cr=ss(CR,CR+0.4,u); for(const p of [A,Cc]){ const g=gs(GO,1.4,0.8*cr*(0.8+0.2*Math.sin(u*6))); g.position.copy(p).add(V(0,0.1,0)); }
    const py=ss(PY,PY+0.9,u); if(py>0){ wline(CY,6,[A,Bd],py,false,true); wline(MG,6,[Bd,V(lerp(SW,-SW,ss(PY+0.3,PY+0.9,u)),0.03,-L)],py,false,true); }
    const hy=ss(HY,HY+0.9,u); if(hy>0) wline(GO,7,[A,A.clone().lerp(Cc,hy)],1,false,true);
    const eq=bt('dgEq',T('a² + b² = c²','a² + b² = c²'),{size:0.62,glow:'rgba(255,194,74,0.5)',fx:'write'}); hud(eq,0,2.0,9); eq.update(u,PY,CX-0.5,0.9);
    anum('dgC','25.15 m',GO,0.42,A.clone().lerp(Cc,0.5),-1.6,0.35,ss(HY+0.5,HY+0.9,u));
    const pl=ss(PL,PL+0.4,u); num('dgP','+1.38 m',GO,0.42,3.6,-0.9,pl); lab('dgP2',T('斜线比直线多出','diagonal is longer by'),3.6,-0.3,pl,{size:0.28,color:'#e8f4ff'});
    return; }
  // 低机位在击球人身后：网按高度着色（中间冷、两边暖）
  const s=Object.assign(NETST(),{heat:1,xs:STICKX,sticks:1}); NET.upd(s);
  const kc=ss(CX,CX+1.5,u); look(lerp(SW+1.6,SW+0.8,kc),lerp(3.0,2.2,kc),lerp(L+5,L+4.2,kc),lerp(SW-2,0.5,kc),lerp(0.8,0.9,kc),0);
  const m1={x0:SW,z0:L,x1:SW,z1:-L+1,R:2*L-1,th:0,sN:L}, m2={x0:SW,z0:L,x1:-SW,z1:-L+1}; m2.R=Math.hypot(m2.x1-m2.x0,m2.z1-m2.z0);
  m1.th=landAngle(KMH,m1.R,1.0); m2.th=landAngle(KMH,m2.R,1.0);
  const fly=(m,t0,col)=>{ const k=clamp((u-t0)/1.25); if(u<t0) return; flight('f',col,m,k,1,{ballS:0.5}); };
  const tD=u<BO?DT:BO, tC=u<BO?CC:BO+0.0;
  { const ho=ss(CX,CX+0.8,u); humanOp(SRV,ho*0.85); place(SRV,SW+0.55,L+0.25,0); applyPose(SRV,(u>DT&&u<DT+0.5)||(u>CC&&u<CC+0.5)||(u>BO&&u<BO+0.5)?POSE.lungeF:POSE.ready); }
  if(u>DT) fly(m1,tD,0xd6ee3a); if(u>CC) fly(m2,tC,GO);
  const xd=SW, xc=SW+(-SW-SW)*(L/(L+(L-1)));   // 过网点
  const dO=ss(DT+0.6,DT+1.0,u), cO=ss(CC+0.6,CC+1.0,u);
  if(dO>0){ const g=gs(OR,0.5,0.8*dO); g.position.set(xd,cordY(xd,s),0.03); alab('dgD',T('沿边线：网约 104 厘米','down the line: net ≈ 104 cm'),V(xd,cordY(xd,s),0),0.6,0.9,dO,{size:0.34,color:'#ffd9a0',glow:'rgba(255,179,71,0.9)',lead:true,leadCol:OR}); }
  if(cO>0){ const g=gs(CY,0.5,0.8*cO); g.position.set(xc,cordY(xc,s),0.03); alab('dgCc',T('斜线过中间：91.4 厘米','crosscourt over the middle: 91.4 cm'),V(xc,cordY(xc,s),0),-1.1,0.75,cO,{size:0.34,color:'#bff3ff',lead:true}); }
  lab('dgM',T('浅 V 网形模型 · 按单打支杆处 1.07 米','shallow-V net model · 1.07 m at the singles sticks'),0,-1.55,Math.max(dO,cO)*(1-ss(SA-0.3,SA,u)),{size:0.24,color:'#aab8c8'});
  const sf=bt('dgSafe',T('斜线：路更远，网更低','Crosscourt: longer path, lower net'),{size:0.72,glow:'rgba(255,194,74,0.5)',fx:'streak',accent:T('更低','lower net')}); hud(sf,0,1.75,9); sf.update(u,SA,D+5,0.92);
}

// ---------- 6 余量：按模型算（100 km/h、击球高 1 m、落底线内 1 m）→ 斜线过网余量约 45 cm、沿线约 30 cm → 角度窗口 2.1° vs 1.4° → 上旋一句 → 职业数据扇形 52.9 / 17.4 → 沿线失误 19% vs 11% ----------
function shotMargin(u,D){
  const MO=ev('model',1.6), VV=ev('v',3.7), LA=ev('land',5.3), CC=ev('cc',8.0), DT=ev('dtl',11.2), WI=ev('win',14.4), SP=ev('spin',21.3), MC=ev('mcp',26.1), PC=ev('pcc',31.9), PD=ev('pdtl',33.5), UE=ev('ue',36.7), U19=ev('ue19',39.4), U11=ev('ue11',42.0);
  rims(GO,CY,4);
  if(u<MC-0.05){ courtOn(0); look(0,0,9,0,0,0);
    // 侧视图：横轴 0–24 m（画面 -5.0…5.0），纵轴 0–2.4 m 放大（画面 -1.3…+1.6）
    const X=s=>-5.0+10.0*s/24, Y=y=>-1.3+y*1.2;
    const go=ss(0,0.6,u);
    hline(0x5a6a80,3,[[X(0),Y(0)],[X(24),Y(0)]],go); for(let s=0;s<=24;s+=4){ hline(0x5a6a80,2,[[X(s),Y(0)],[X(s),Y(0)-0.08]],go); }
    lab('mgAx',T('水平距离（米）· 高度放大示意','distance (m) · height exaggerated'),3.4,Y(0)-0.38,go,{size:0.22,color:'#8090a4'});
    lab('mgM',T('按模型算 · 真空弹道，不计空气阻力和旋转','model · vacuum trajectory, no drag or spin'),0,2.05,ss(MO,MO+0.4,u),{size:0.3,color:'#ffe2a0',glow:GOLD});
    const hit=gs(0xffffff,0.5,0.8*go); hit.position.copy(hp(X(0),Y(1))); lab('mgV','100 km/h',X(0)+0.6,Y(1)+0.6,ss(VV,VV+0.3,u),{size:0.34,color:'#ffffff'}); lab('mgH',T('击球高 1 米','contact 1 m'),X(0)+0.55,Y(1)-0.38,ss(VV,VV+0.3,u),{size:0.24,color:'#bcd0e4'});
    const la=ss(LA,LA+0.4,u); lab('mgL',T('落在底线内 1 米','lands 1 m inside the baseline'),X(23.2),Y(0)+0.45,la,{size:0.26,color:'#bcd0e4'});
    const draw=(m,col,t0,key,dy)=>{ const k=ss(t0,t0+1.2,u); if(k<=0) return; const P=[]; for(let i=0;i<=60*k;i++){ const s=i/60*m.R; P.push([X(s),Y(yAt(s,KMH,m.th,1.0))]); } hline(col,4,P,1);
      const net=[[X(m.sN),Y(0)],[X(m.sN),Y(m.h)]]; hline(col===GO?CY:OR,9,net,0.9); const yb=yAt(m.sN,KMH,m.th,1.0); const co=ss(t0+1.0,t0+1.4,u);
      hline(col,16,[[X(m.sN)+dy,Y(m.h)],[X(m.sN)+dy,lerp(Y(m.h),Y(yb),co)]],0.75*co);
      return {x:X(m.sN)+dy,y0:Y(m.h),y1:Y(yb),co}; };
    const c=draw(MOD.cc,GO,CC,'cc',0.22), d=draw(MOD.dtl,CY,DT,'dtl',-0.22);
    if(c) { num('mgC','≈45 cm',GO,0.34,c.x+1.15,(c.y0+c.y1)/2+0.15,c.co); lab('mgCl',T('斜线（网约 92 厘米）','crosscourt (net ≈ 92 cm)'),c.x+1.2,(c.y0+c.y1)/2-0.42,c.co,{size:0.24,color:'#ffe2a0',glow:GOLD}); }
    if(d) { num('mgD','≈30 cm',CY,0.34,d.x-1.15,(d.y0+d.y1)/2+0.15,d.co); lab('mgDl',T('沿线（网约 101 厘米）','down the line (net ≈ 101 cm)'),d.x-1.2,(d.y0+d.y1)/2-0.42,d.co,{size:0.24,color:'#bff3ff'}); }
    // 角度窗口：从击球点放出两个扇面（角度放大 8 倍画）
    const wo=ss(WI,WI+0.6,u)*(1-ss(SP-0.3,SP,u)); if(wo>0.01){ const o0=[X(0),Y(1)]; for(const [m,col,yo2] of [[MOD.cc,GO,0.55],[MOD.dtl,CY,-0.55]]){ const a0=Math.atan(Math.tan(m.th)*1.2*24/10)*1, w=m.win*8; const r=3.0;
        const P=[o0]; for(let i=0;i<=16;i++){ const a=a0-w+w*i/16; P.push([o0[0]+r*Math.cos(a),o0[1]+r*Math.sin(a)]); } P.push(o0); hline(col,3,P,wo); }
      lab('mgW1',T('斜线 2.1°','crosscourt 2.1°'),X(5.6),Y(1)+1.25,wo,{size:0.3,color:'#ffe2a0',glow:GOLD}); lab('mgW2',T('沿线 1.4°','down the line 1.4°'),X(5.6),Y(1)-0.15,wo,{size:0.3,color:'#bff3ff'});
      lab('mgW3',T('能打进的出手角度：宽了将近一半（角度放大示意）','angle window: nearly 50% wider (angles exaggerated)'),0,-1.75,wo,{size:0.26,color:'#e8f4ff'}); }
    // 上旋：一条更早下坠的品红弧线
    const so=ss(SP,SP+0.5,u)*(1-ss(MC-0.5,MC-0.1,u)); if(so>0.01){ const m=MOD.cc; const P=[]; for(let i=0;i<=60;i++){ const s=i/60*m.R; const y=yAt(s,KMH,m.th+0.03,1.0)-0.9*Math.pow(s/m.R,2.2)*0.75; P.push([X(s),Y(y)]); } hline(MG,3,P,so*0.9,9,true);
      lab('mgS',T('示意：加上上旋，过网更高也能落进来（马格努斯效应，见 EP03）','sketch: with topspin, higher over the net and still in (Magnus effect, EP03)'),0,-1.75,so,{size:0.26,color:'#ffd0f4',glow:'rgba(255,79,216,0.8)'}); }
    return; }
  // 职业数据：反手角扇形（俯视球场）
  courtOn(1); ST_RATE=0.0005; NET.upd(Object.assign(NETST(),{xs:STICKX,sticks:1}));
  look(-0.4,20,L+5.5,-0.4,0,6.8);
  const O=V(-SW+0.6,0.1,L+0.4), E={cc:V(SW-1.0,0.1,-L+1.5), mid:V(0,0.1,-L+1.5), dtl:V(-SW+1.0,0.1,-L+1.5)};
  const mo=ss(MC,MC+0.6,u); const ueK=ss(UE,UE+0.6,u);
  // 扇形（示意）：从反手位放出三瓣，半径∝占比；方向按真实落点，夹角放大画
  const [ox,oy]=toHud(O); const g=gs(0xffffff,1.0,0.8*mo); g.position.copy(hp(ox,oy)); lab('mpO',T('反手位','backhand corner'),ox,oy-0.32,mo,{size:0.3,color:'#e8f4ff'});
  const dCol=new THREE.Color(CY).lerp(new THREE.Color(RD),ueK).getHex();
  const pet=[['dtl',dCol,0.174,96,112,PD],['mid',0xc8d4e4,1-0.529-0.174,70,92,PC],['cc',GO,0.529,30,66,PC]];
  const tips={};
  for(const [k,col,w,a0,a1,t0] of pet){ const grow=ss(MC+0.2,MC+1.2,u)*mo, hi=k==='mid'?0.55:(0.6+0.4*ss(t0,t0+0.3,u)); const R=(0.6+4.6*w)*grow;
    const arc=[]; for(let i=0;i<=20;i++){ const a=(a0+(a1-a0)*i/20)*Math.PI/180; arc.push([ox+R*Math.cos(a),oy+R*Math.sin(a)]); }
    hline(col,4,[[ox,oy],...arc,[ox,oy]],mo*hi);
    for(let i=1;i<8;i++){ const a=(a0+(a1-a0)*i/8)*Math.PI/180; hline(col,10,[[ox+0.25*Math.cos(a),oy+0.25*Math.sin(a)],[ox+R*Math.cos(a),oy+R*Math.sin(a)]],mo*hi*0.32); }
    const am=(a0+a1)/2*Math.PI/180; tips[k]=[ox+(R+0.45)*Math.cos(am),oy+(R+0.35)*Math.sin(am)]; }
  const fo=Math.max(0,1-ueK);
  num('mpCC','52.9%',GO,0.5,tips.cc[0]+0.3,tips.cc[1],ss(PC,PC+0.3,u)); lab('mpCCl',T('斜线','crosscourt'),tips.cc[0]+0.3,tips.cc[1]-0.5,ss(PC,PC+0.3,u),{size:0.3,color:'#ffe2a0',glow:GOLD});
  lab('mpMid',T('中路','middle'),tips.mid[0]+0.1,tips.mid[1],mo*ss(PC,PC+0.3,u)*0.8,{size:0.24,color:'#c8d4e4'});
  num('mpDT','17.4%',CY,0.5,tips.dtl[0]-0.25,tips.dtl[1]+0.15,ss(PD,PD+0.3,u)*fo); lab('mpDTl',T('沿线','down the line'),tips.dtl[0]-0.25,tips.dtl[1]-0.35,ss(PD,PD+0.3,u)*fo,{size:0.3,color:'#bff3ff'});
  lab('mpFan',T('扇形示意：半径＝占比','fan sketch: radius = share'),3.6,1.9,mo,{size:0.22,color:'#8090a4'});
  lab('mpSrc',T('Tennis Abstract 记拍项目 · 2010 年代男子 · 反手位的反手抽击（不含切削）','Tennis Abstract Match Charting · men, 2010s · backhand-corner backhands (no slices)'),0,2.3,mo*(1-ueK),{size:0.24,color:'#aab8c8'});
  if(ueK>0.01){ num('mpUE','19%',RD,0.62,tips.dtl[0]-0.25,tips.dtl[1]+0.15,ss(U19,U19+0.3,u)); lab('mpUEl',T('沿线：非受迫性失误','down the line: unforced errors'),tips.dtl[0]-0.25,tips.dtl[1]-0.4,ueK,{size:0.3,color:'#ffb0a8',glow:RED});
    num('mpAll','11%',0xffffff,0.5,3.4,0.6,ss(U11,U11+0.3,u)); lab('mpAlll',T('这个位置所有出球：平均','all shots from this corner'),3.4,0.0,ss(U11,U11+0.3,u),{size:0.28,color:'#e8f4ff'});
    lab('mpSrc2',T('Tennis Abstract（Sackmann 2020）· 反手位出球，正反手合计','Tennis Abstract (Sackmann 2020) · from the backhand corner, both wings'),0,2.3,ueK,{size:0.24,color:'#aab8c8'}); }
}

// ---------- 7 单打支杆：网柱在双打宽度 → 单打边线外 0.914 m 插支杆 → 网撑回 1.07 m（无支杆：边线处约低 2.8 cm，按模型算） ----------
function shotSticks(u,D){
  const DB=ev('dbl',0.5), PO=ev('posts',2.7), SK=ev('sticks',9.0), DM=ev('d914',8.0), LI=ev('lift',11.2), RU=ev('rule',14.4);
  rims(GO,CY,4); courtOn(1); ST_RATE=0.0005;
  const ks=ss(SK,SK+1.0,u); const ex=lerp(1,4,ss(LI,LI+0.8,u));
  const s=Object.assign(NETST(),{xs:lerp(POSTX,STICKX,ks),sticks:ks,exg:ex,ghost:ss(LI,LI+0.5,u)}); NET.upd(s);
  look(lerp(-3,3,ss(0,D,u)),2.4,10.5,lerp(-0.5,2.5,ss(0,DM,u)),0.6,0);
  const po=ss(PO,PO+0.4,u)*(1-ss(SK-0.3,SK,u)); for(const sg of [-1,1]){ const g=gs(CY,0.6,0.7*po); g.position.set(sg*POSTX,HPOST+0.05,0); }
  alab('skP',T('网柱：双打边线外 0.914 米','posts: 0.914 m outside the doubles line'),V(POSTX,HPOST,0),-0.6,0.8,po,{size:0.3,color:'#bff3ff',lead:true});
  const dm=ss(DM,DM+0.4,u); if(dm>0){ for(const sg of [1]){ wline(GO,4,[V(sg*SW,0.05,0.25),V(sg*STICKX,0.05,0.25)],dm,false,false); alab('skD','0.914 m',V(sg*(SW+0.457),0.05,0.25),0,-0.6,dm,{size:0.36,color:'#ffe2a0',glow:GOLD}); }
    alab('skSL',T('单打边线','singles sideline'),V(SW,0.02,0.6),-0.9,-0.9,dm*(1-ss(RU-0.3,RU,u)),{size:0.26,color:'#e8f4ff',lead:true}); }
  if(ks>0.01) alab('skS',T('单打支杆','singles sticks'),V(STICKX,HPOST*ks,0),0.5,0.9,ks*(1-ss(LI-0.2,LI,u)),{size:0.34,color:'#ffe2a0',glow:GOLD,lead:true,leadCol:GO});
  const lo=ss(LI,LI+0.5,u); if(lo>0){ alab('skL',T('撑回 1.07 米','back up to 1.07 m'),V(STICKX,HPOST,0),0.4,0.9,lo*(1-ss(RU-0.3,RU,u)),{size:0.34,color:'#ffe2a0',glow:GOLD});
    alab('skG',T('没有支杆：边线处约低 2.8 厘米（按模型算）','no sticks: ≈ 2.8 cm lower at the sideline (model)'),V(SW,cordY(SW,Object.assign({},s,{xs:POSTX})),0),-0.4,-1.0,lo*(1-ss(RU-0.3,RU,u)),{size:0.26,color:'#bff3ff',lead:true});
    lab('skEx',T('竖向放大 4 倍示意','vertical ×4 for clarity'),-3.6,-1.55,lo,{size:0.24,color:'#aab8c8'}); }
  const ro=ss(RU,RU+0.8,u); if(ro>0){ const P=[]; const n=Math.round(80*ro); for(let i=0;i<=n;i++){ const x=-STICKX+i*2*STICKX/80; P.push(V(x,cordY(x,s)+0.01,0.03)); } if(P.length>1) wline(GO,5,P,1,false,false);
    lab('skR',T('两边高、中间低：规则要的就是这个','high at the sides, low in the middle: by design of the rules'),0,1.75,ss(RU+0.3,RU+0.7,u),{size:0.34,color:'#ffe2a0',glow:GOLD}); }
}

// ---------- 8 回扣：开头那张网再滑一遍 → 白带子收紧、折角被光描出来 → 金句 → 编织问句 ----------
function shotEnd(u,D){
  const AG=ev('again',0.5), QU=ev('quote',3.2), QQ=ev('q',8.0);
  rims(GO,CY,4); courtOn(1); ST_RATE=u>QQ?0.003:0.001; beamMat.uniforms.uOp.value=0.12;
  const kk=ss(AG,AG+1.4,u); const s=Object.assign(NETST(),{k:lerp(0.55,1,kk),hc0:H99}); NET.upd(s);
  const k=ss(0,QU+1,u); look(lerp(6.0,0.7,k),lerp(1.2,0.95,k),lerp(1.9,2.0,k),lerp(3.4,0,k),lerp(1.0,0.75,k),0); DOF.on=true; DOF.focus=lerp(2.2,2.0,k); DOF.ap=0.0002;
  if(u>QU-0.5){ const pts=[]; for(let i=0;i<=40;i++){ const x=-1.4+2.8*i/40; pts.push(V(x,cordY(x,s)+0.004,0.02)); } wline(GO,4,pts,ss(QU-0.5,QU,u)*0.9,false,true); const g=gs(GO,0.5,0.7*ss(QU-0.5,QU,u)); g.position.set(0,cordY(0,s),0.03); }
  wruler(GO,0.0,HCEN,HPOST,0.06,ss(AG+0.6,AG+1.2,u)*(1-ss(QQ-0.4,QQ,u)),4,0.1); anum('enD','15.6 cm',GO,0.36,V(0,(HPOST+HCEN)/2,0),-1.2,-0.5,ss(AG+0.8,AG+1.2,u)*(1-ss(QQ-0.4,QQ,u)));
  const qt=bt('enQ',T('它不是塌的。是被拉成这样的。','It isn\'t sagging. It\'s pulled into shape.'),{size:0.74,glow:'rgba(255,194,74,0.5)',fx:'shock',accent:T('拉成这样',null)}); hud(qt,0,1.75,9); qt.update(u,QU,QQ-0.4,0.92);
  const q=bt('enQ2',T('下次看球，你会先瞄中间那条白带子吗？','Next match: will you look at the white strap first?'),{size:0.66,glow:'rgba(255,194,74,0.5)',fx:'weave',accent:T('白带子','white strap')}); hud(q,0,1.6,9); q.update(u,QQ,D+5,0.92);
  const fo=ss(D-1.6,D-0.1,u); if(fo>0){ courtOn(1-fo); NET.upd(Object.assign({},s,{op:1-fo})); }
}
const SHOTS={hook:shotHook,title:shotTitle,strap:shotStrap,hist:shotHist,diag:shotDiag,margin:shotMargin,sticks:shotSticks,end:shotEnd};
function shotTest(u,D){ look(0,0,8,0,0,0); }
// 英文版局部重渲用：只跑 setState 不出图，列出这一帧可见的字（键＋内容）。中英两边比对，有差别的帧才需要按英文重渲 3D，其余直接复用中文块
window.textProbe=(t)=>{ setState(t); const v=[];
  for(const k in TT){ const s=TT[k]; if(s.visible&&s.material.opacity>0.01) v.push('T:'+k+':'+(s.userData.str||'?')); }
  for(const k in text3D){ const o=text3D[k]; if(o.g.visible&&o.m.material.opacity>0.01) v.push('3:'+k+':'+(o.m.userData.str||'?')); }
  for(const k in TB){ if(TB[k].g.visible) v.push('B:'+k+':'+TB[k].__str); }
  return v.sort(); };
