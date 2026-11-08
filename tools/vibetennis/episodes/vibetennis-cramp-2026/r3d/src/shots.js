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
  const lk=bt('bkLk',T('锁死','LOCKED'),{size:0.9,glow:'rgba(255,90,74,0.5)',fx:'particles'}); hud(lk,2.4,1.6,9); lk.update(u,LK,D-0.1,0.78);
}

// ---------- 5 拉伸：勾脚尖 → 跟腱被拉紧 → 刹车（蓝）压过油门（红）→ 肌肉松开 ----------
function shotStretch(u,D){
  const FX=ev('flex',4.5), RL=ev('relief',7.3);
  const f=ss(FX-0.3,FX+1.0,u), r=ss(FX+0.3,RL+1.2,u);
  LEG.st.op=1; LEG.st.ankle=lerp(-0.35,0.55,f); LEG.st.ib=lerp(0.08,1,f); LEG.st.ia=lerp(1,0.3,r); LEG.st.mot=lerp(1,0.06,r); LEG.st.c=lerp(1,0,r); LEG.update(u);
  legCam(u,2.05,2.45,D,0.8,12); rims(BLU,GO,4);
  if(u>FX){ const c=V(0,-1.2,-0.58); const g=gs(BLU,0.8,0.3*f); g.position.copy(c); shockRing(c,(u-FX)/1.2,BLU,2.2,0.6,true); }
  const a=lab('stA',T('勾脚尖 → 跟腱拉紧','toes pulled up → tendon stretched'),-2.6,-1.6,ss(FX,FX+0.5,u),{size:0.32,color:'#cfe4ff',glow:CYAN});
  const t=bt('stT',T('刹车又起作用了','The brake kicks back in'),{size:0.8,glow:'rgba(79,227,255,0.45)',fx:'particles'}); hud(t,0,2.0,9); t.update(u,RL,D-0.1,0.78);
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
  const t=bt('ndT',T('油门踩死 · 刹车失灵','Accelerator stuck · brake failing'),{size:0.85,glow:'rgba(255,90,74,0.45)',fx:'particles'}); hud(t,0,2.2,9); t.update(u,0.5,QQ-0.4,0.78);
  lab('ndA',T('① 先拉伸','① stretch first'),-2.6,-1.9,ss(P1,P1+0.5,u)*(1-ss(QQ-0.4,QQ,u)),{size:0.36,color:'#9fd0ff',glow:CYAN});
  lab('ndB',T('② 汗多又咸的人，再补盐','② heavy, salty sweaters: add salt'),1.6,-1.9,ss(P2,P2+0.5,u)*(1-ss(QQ-0.4,QQ,u)),{size:0.36,color:'#ffd27a',glow:GOLD});
  const q=bt('ndQ',T('你抽筋的时候，是怎么缓过来的？','When you cramp, how do you get out of it?'),{size:0.85,glow:CYAN,fx:'particles'}); hud(q,0,0.2,9); q.update(u,QQ,D+5);
}

const SHOTS={hook:shotHook,camps:shotCamps,pickle:shotPickle,brake:shotBrake,stretch:shotStretch,data:shotData,salt:shotSalt,back:shotBack,end:shotEnd};
function shotTest(u,D){ look(0,0,8,0,0,0); }
