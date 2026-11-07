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
  beamMat.uniforms.uOp.value=0; rimL.intensity=0; rimR.intensity=0; DOF.on=false; MOTE_SPEED=1; SLOW=null; }
// 全息榜单行
function row(k,i,str,val,max,col,o,hl=0){ const y=1.4-i*0.75; const w=4.6*clamp(val/max); const l=ln(col,hl?14:10); setLine(l,[V(-1.2,y,0),V(-1.2+w,y,0)]); l.material.opacity=o*(0.75+0.25*hl);
  const t=tx(k,str,{color:hl?'#ffffff':'#c8d8ea',size:0.42,glow:hl?CYAN:'rgba(120,160,200,0.6)'}); t.position.set(-3.4,y,0.1); op(t,o); }

// ---------- 1 钩子：2011 美网，赛点接发 → 官方榜单第 7 ----------
function shotHook(u,D){
  const SV=ev('serve',3.15), RT=ev('ret',6.2), RUN=ev('run',10.9), CR=ev('crown',14.5), BD=ev('board',18.1), R7=ev('r7',20.6), QQ=ev('q',22.5);
  if(u<RUN-0.3){ courtG.visible=true; const C=SV+0.9, sf=0.65/Math.max(0.6,RT-C);   /* 慢放：发球到接发人击球的 0.65 s 拉到旁白「正手」那一刻 */
    humanOp(SRV,1); humanOp(RET,1); place(SRV,-0.8,-L2-0.3,0); place(RET,2.2,L2+0.9,Math.PI);
    applyPose(SRV,poseAt([[0,'stand'],[SV-0.6,'stand'],[SV,'sToss'],[SV+0.6,'sTrophy'],[C,'sHit'],[C+0.6,'sFollow']],u));
    const tb=(u-C)*sf; const A=V(-0.95,2.8,-L2+0.1), B=V(3.6,0,SLN-0.6), Cp=V(3.0,0.9,L2+0.7);
    applyPose(RET,poseAt([[0,'ready'],[C-0.15,'ready'],[C,'split'],[C+0.15/sf,'land'],[RT-0.35,'lungeF'],[RT+0.2,'lungeF'],[RT+1.4,'ready']],u));
    RET.root.position.x=lerp(2.2,2.7,ss(C+0.2/sf,RT-0.3,u));
    if(u>C&&tb<0.65){ const p=serveAt(tb,A,B,Cp); const b=bl(); showB(b,p,1,BS); const pts=[]; for(let i=0;i<=20;i++) pts.push(serveAt(tb*i/20,A,B,Cp)); trail(pts,GO,4,0.8); }
    if(u>=RT){ const k=clamp((u-RT)*1.2); const E=V(-3.6,0,-L2+3.2); const p=V(lerp(Cp.x,E.x,k),0.9+Math.sin(Math.PI*k)*1.1,lerp(Cp.z,E.z,k)); const b=bl(); showB(b,p,1-ss(0.95,1,k),BS); const pts=[]; for(let i=0;i<=24;i++){ const kk=k*i/24; pts.push(V(lerp(Cp.x,E.x,kk),0.9+Math.sin(Math.PI*kk)*1.1,lerp(Cp.z,E.z,kk))); } trail(pts,CY,6,0.9);
      if(k>=1){ const r=rg(); r.rotation.set(-Math.PI/2,0,0); r.position.set(E.x,0.02,E.z); r.scale.setScalar(lerp(0.3,2.5,ss(0,0.8,(u-RT)-0.84))); r.material.color.set(CY).multiplyScalar(GLOW.k); r.material.opacity=0.8*(1-ss(0,1.2,(u-RT)-0.84)); } }
    SLOW=[RT-0.1,RT+0.5];
    const sc=tx('hkSc',T('2011 美网半决赛 · 第五盘 3:5 · 费德勒发球 · 两个赛点','2011 US Open SF · fifth set 3-5 · Federer serving · 2 match points'),{color:'#ffe2a0',size:0.34,glow:GOLD,plate:true}); hud(sc,0,2.55); op(sc,ss(0.3,1,u)*(1-ss(RUN-0.8,RUN-0.3,u)));
    const n1=tx('hkN1',T('费德勒','Federer'),{color:'#ffe2a0',size:0.34}); n1.position.set(-0.8,2.4,-L2-0.3); op(n1,ss(0.5,1.1,u)*(1-ss(SV+1.5,SV+2,u)));
    const n2=tx('hkN2',T('德约科维奇','Djokovic'),{color:'#c8f4ff',size:0.34}); n2.position.set(2.4,2.4,L2+0.9); op(n2,ss(0.8,1.4,u)*(1-ss(SV+1.5,SV+2,u)));
    const w=tx('hkW',T('正手接发 · 直接得分','Forehand return winner'),{color:'#ffffff',size:0.5,glow:CYAN}); hud(w,0,-2.2); op(w,ss(RT+0.3,RT+0.9,u));
    const sch=tx('hkS',T('动作为示意','Motion is schematic'),{color:'#9fb8d0',size:0.24}); hud(sch,3.6,-2.95); op(sch,1);
    const tc=ss(0,SV,u), rc=ss(RT-0.5,RT+1.5,u);
    look(lerp(7.5,5.2,tc)-rc*2.2, lerp(4.2,2.8,tc), lerp(L2+10,L2+7.2,tc)-rc*1.5, lerp(0,0.8,tc)-rc*1.4, 0.6, lerp(-2,-4,tc)+rc*-1);   /* 接发人身后偏高：两个人都在画里 */
    beamMat.uniforms.uOp.value=0.12; rims(GO,CY,5); DOF.on=u>C-0.3&&u<RT+1.2; DOF.focus=camera.position.distanceTo(V(3,0.9,L2)); DOF.ap=0.00005; return; }
  if(u<BD-0.3){ // 连赢四局：3:5 → 7:5；接发之王
    const v=u-RUN; const a=t3d('s35','3 : 5','#c8d8ea',0.9), b=t3d('s75','7 : 5','#ffd27a',1.1);
    a.g.position.set(0,0.6,0); b.g.position.set(0,0.6,0); const k=ss(0.6,1.6,v); t3op(a,ss(0,0.4,v)*(1-k)); t3op(b,k*(1-ss(CR-RUN+0.2,CR-RUN+0.6,v))); a.g.rotation.y=k*Math.PI*0.5; b.g.rotation.y=(1-k)*-Math.PI*0.5;
    const l=tx('hkRun',T('连赢四局 · 6-7 4-6 6-3 6-2 7-5','Four games in a row · 6-7 4-6 6-3 6-2 7-5'),{color:'#ffffff',size:0.4}); hud(l,0,-2.0); op(l,ss(0.4,1,v)*(1-ss(CR-RUN-0.3,CR-RUN,v)));
    const t=bt('kingT',T('接发之王','King of the Return'),{size:1.25,glow:GOLD,fx:'shock'}); hud(t,0,0.4); t.update(v,CR-RUN);   /* 冲击 */
    const k2=ss(CR-RUN,CR-RUN+1.4,v); particles(k2,0,1.9,0,3.6,0.5,0xffc24a,k2>0?0.8*(1-ss(BD-RUN-1,BD-RUN-0.4,v)):0);
    look(Math.sin(v*0.3)*0.6,0.4,9,0,0.3,0); rims(GO,CY,5); beamMat.uniforms.uOp.value=0.08; return; }
  // 官方榜单：第 1 科里亚、第 3 纳达尔、第 7 德约（只画核过的三行，中间用省略）
  const v=u-BD; const o=ss(0,0.8,v);
  row('lb1',0,T('1  科里亚','1  Coria'),171.5-150,22,0x9fb8d0,o); row('lb3',1,T('3  纳达尔','3  Nadal'),167.8-150,22,0x9fb8d0,o*ss(0.2,0.9,v));
  const dots=tx('lbDot','· · ·',{color:'#7f93aa',size:0.5}); dots.position.set(-3.4,-0.15,0.1); op(dots,o);
  const hl=ss(R7-BD,R7-BD+0.4,u-BD); row('lb7',2.5,T('7  德约科维奇','7  Djokovic'),163.5-150,22,hl>0.5?RD:CY,o*ss(0.4,1.1,v),hl);
  const vals=[['lbv1','171.5',0],['lbv3','167.8',1],['lbv7','163.5',2.5]]; vals.forEach(([k,s,i])=>{ const t=tx(k,s,{color:'#e8f0ff',size:0.36}); t.position.set(3.75,1.4-i*0.75,0.1); op(t,o); });
  const hd=tx('lbH',T('ATP 官方 · 历史接发评分（1991 年起）','ATP official · career Return Rating (since 1991)'),{color:'#c8f4ff',size:0.36,glow:CYAN}); hud(hd,0,2.6); op(hd,o);
  const big=t3d('r7','7','#ff7a6a',1.6); big.g.position.set(3.2,-1.2,0.4); t3op(big,hl*(1-ss(QQ-BD-0.4,QQ-BD,v)));
  const q=bt('hookQ',T('那这个「王」，到底王在哪？','So where does the "king" come from?'),{size:0.78,glow:GOLD,accent:T('王在哪','the "king"'),fx:'shock'}); hud(q,0,-2.2); q.update(v,QQ-BD,Infinity,0.9);
  look(0.4,0.5,lerp(9.5,8.6,ss(0,D-BD,v)),0.4,0.4,0); rims(CY,RD,4); }

// ---------- 2 时间赛跑：0.65 s 的来球，0.2 s 的反应，0.19 s 就动拍 ----------
const TMAX=0.7;
function shotRace(u,D){
  const TL0=ev('tl',0.5), FL=ev('fly',5.4), RE=ev('react',7.1), JP=ev('jump',15.8), LD=ev('land',16.7), RK=ev('racket',18.2), FK=ev('fork',26.1), GU=ev('guess',31.9);
  courtG.visible=true; humanOp(SRV,1); humanOp(RET,1); place(SRV,-0.8,-L2-0.3,0); place(RET,0.6,L2+0.9,Math.PI);
  // 慢放：整段里把 0–0.7 s 循环演示（每轮 7 s，即 1/10 速），时间轴上的光标同步走
  const per=7.0, cyc=u<FL?0:((u-FL)%per)/per*TMAX+(u<FL?0:0), tb=u<FL?0:cyc;
  applyPose(SRV,tb<0.001&&u<FL?POSE.sTrophy:mixPose(POSE.sHit,POSE.sFollow,ss(0,0.25,tb)));
  const rp=tb<0.009?POSE.ready:tb<0.152?mixPose(POSE.split,POSE.land,ss(0.009,0.152,tb)):tb<0.187?POSE.land:mixPose(POSE.land,POSE.lungeF,ss(0.187,0.5,tb));
  applyPose(RET,u<JP?(u<FL?POSE.ready:mixPose(POSE.ready,POSE.ready,0)):rp);
  if(u>=FL){ const A=V(-0.95,2.8,-L2+0.1), B=V(2.4,0,SLN-0.6), Cp=V(1.6,0.9,L2+0.6); const b=bl(); if(tb<0.65){ showB(b,serveAt(tb,A,B,Cp),1,BS*1.4); } const pts=[]; for(let i=0;i<=24;i++) pts.push(serveAt(Math.min(tb,0.65)*i/24,A,B,Cp)); trail(pts,GO,4,0.7); }
  look(-23,6.5,0.4,0,0.0,0.4);   /* 侧面看整条来球路线：两个人都在画里 */
  // 时间轴（镜头坐标里画）：0 → 0.7 s
  const x0=-4.2, x1=4.2, ty=2.15, X=t=>lerp(x0,x1,t/TMAX); const kk=ss(TL0,TL0+0.8,u);
  const ax=ln(0x9fd8ff,3); setLine(ax,[hp(x0,ty),hp(lerp(x0,x1,kk),ty)]); ax.material.opacity=0.9;
  for(let i=0;i<=7;i++){ const t=ln(0x9fd8ff,2); setLine(t,[hp(X(i*0.1),ty-0.08),hp(X(i*0.1),ty+0.08)]); t.material.opacity=0.8*kk; const s=tx('tk'+i,(i/10).toFixed(1)+'s',{color:'#9fb8d0',size:0.2}); hud(s,X(i*0.1),ty+0.28); op(s,kk); }
  const bf=ln(GO,9); setLine(bf,[hp(x0,ty-0.42),hp(X(0.65)*ss(FL,FL+1,u)+x0*(1-ss(FL,FL+1,u)),ty-0.42)]); bf.material.opacity=ss(FL,FL+0.5,u);
  const lb=tx('rBall',T('来球：发球到接发人约 0.6–0.7 秒','Ball: ~0.6–0.7 s from serve to returner'),{color:'#ffe2a0',size:0.28,glow:GOLD}); hud(lb,X(0.5),ty-0.68); op(lb,ss(FL,FL+0.6,u)*(1-ss(JP-0.6,JP,u)));
  const rr=ln(RD,9); setLine(rr,[hp(x0,ty-1.05),hp(lerp(x0,X(0.2),ss(RE,RE+0.8,u)),ty-1.05)]); rr.material.opacity=ss(RE,RE+0.4,u);
  const ll=tx('rReact',T('人的简单反应 ≈ 0.2 秒','Simple reaction ≈ 0.2 s'),{color:'#ffd2c8',size:0.28,glow:RED}); hud(ll,X(0.2)+1.9,ty-1.05); op(ll,ss(RE,RE+0.6,u)*(1-ss(JP-0.6,JP,u)));
  // 职业接发人的三个时刻
  const marks=[[0.009,JP,T('起跳','Take-off'),0],[0.152,LD,T('落地 0.15 s','Land 0.15 s'),1],[0.187,RK,T('动拍 0.19 s','Racket moves 0.19 s'),2]];
  marks.forEach(([t,e,s,i])=>{ const k=ss(e,e+0.5,u); const m=ln(CY,5); setLine(m,[hp(X(t),ty-0.3),hp(X(t),ty-1.7-i*0.0)]); m.material.opacity=k; const lb2=tx('rm'+i,s,{color:'#c8f4ff',size:0.28,glow:CYAN}); hud(lb2,X(t)+0.5+i*0.95,ty-1.95-i*0.3); op(lb2,k); });
  const cur=ln(WH,3); setLine(cur,[hp(X(tb),ty+0.15),hp(X(tb),ty-2.6)]); cur.material.opacity=u>FL?0.55:0;
  const src=tx('rSrc',T('职业球员实测（Mecheri 2019；Navia 2022）','Measured in pros (Mecheri 2019; Navia 2022)'),{color:'#9fb8d0',size:0.24}); hud(src,2.6,-2.95); op(src,ss(JP,JP+0.6,u));
  if(u>FK-0.2){ const k=ss(FK,FK+0.8,u); const c=wpos(RET.root).add(V(0,1.0,-1.0)); [-1,1].forEach((s,i)=>{ const a=ln(i?CY:GO,6,true); setLine(a,[c,c.clone().add(V(s*1.6*k,0,-1.6*k))]); a.material.opacity=k; }); const q=tx('rQ',T('往哪边？','Which way?'),{color:'#ffffff',size:0.5}); q.position.copy(c.clone().add(V(0,0.8,-1))); op(q,k*(1-ss(GU-0.4,GU,u))); }
  const g=bt('raceT',T('看清球之前，就已经猜好了','They guess before they see the ball clearly'),{size:0.62,glow:GOLD,accent:T('猜好了','guess'),fx:'streak'}); hud(g,0,-2.2); g.update(u,GU);
  rims(GO,CY,5); beamMat.uniforms.uOp.value=0.08; }

// ---------- 3 读懂发球人：抛球、持拍手臂＋球拍、上半身；眼睛先跳到落点 ----------
function shotRead(u,D){
  const BO=ev('body',0.5), TS=ev('toss',6.5), AR=ev('arm',7.2), GZ=ev('gaze',10.3), SC=ev('sacc',18.7), TI=ev('title',22.7);
  if(u<SC-0.3){ courtG.visible=true; humanOp(SRV,1); place(SRV,0,0,0); SRV.root.position.set(0,0,-L2-0.2);
    const ph=0.5+0.5*Math.sin((u-BO)*0.9); applyPose(SRV,mixPose(POSE.sToss,POSE.sTrophy,ss(0.1,0.9,ph)));
    // 抛球
    const tossH=2.4+1.0*ss(0.1,0.9,ph); const handL=wpos(SRV.armL.hand); const ball=bl(); const bp=V(handL.x,tossH,handL.z+0.15); showB(ball,bp,1,BS*1.3);
    const cues=[[TS,bp,GO,T('抛球','Ball toss'),0.7],[AR,wpos(SRV.armR.el),CY,T('持拍手臂＋球拍','Arm + racket'),0.9],[GZ,wpos(SRV.spine).add(V(0,0.4,0)),MT,T('上半身','Upper body'),1.2]];
    cues.forEach(([e,p,c,s,sz],i)=>{ const k=ss(e,e+0.6,u); const g=gs(c,sz,0.55*k); g.position.copy(p); const r=rg(); r.position.copy(p); r.rotation.set(0,0,0); r.scale.setScalar(sz*0.7*(1+0.08*Math.sin(u*4+i))); r.material.color.set(c).multiplyScalar(GLOW.k); r.material.opacity=0.8*k;
      const t=tx('cue'+i,s,{color:'#ffffff',size:0.3,glow:i===0?GOLD:i===1?CYAN:MINT}); t.position.copy(p.clone().add(V(i===0?0.7:-0.9,0.25,0.2))); op(t,k); });
    // 视线：从镜头这边（接发人的眼睛）射向线索
    if(u>GZ){ const eye=V(0.6,1.7,L2+0.6); const k=ss(GZ,GZ+0.8,u); [wpos(SRV.spine).add(V(0,0.4,0)),bp].forEach((p,i)=>{ const l=ln(MT,3,true); setLine(l,[eye,eye.clone().lerp(p,k)]); l.material.opacity=0.8*k; });
      const t=tx('gzT',T('眼动追踪：高手更多看上半身和球','Eye tracking: experts fixate the upper body and ball'),{color:'#c8ffe6',size:0.32,glow:MINT}); hud(t,0,-2.3); op(t,k); }
    const tt=tx('rdT',T('研究：高手靠抛球和持拍手臂＋球拍预判发球方向','Research: experts read the toss and arm + racket'),{color:'#ffe2a0',size:0.32,glow:GOLD}); hud(tt,0,-2.3); op(tt,ss(TS,TS+0.6,u)*(1-ss(GZ-0.3,GZ,u)));
    look(lerp(1.2,0.4,ss(0,SC,u)),1.7,-L2+lerp(6.5,5.2,ss(0,SC,u)),0,1.8,-L2-0.2); rims(GO,MT,5); DOF.on=true; DOF.focus=6; DOF.ap=0.00004; return; }
  // 板球研究：视线提前跳到落点等球
  const v=u-SC; courtG.visible=true; const per=3.2, k=(v%per)/per; const A=V(-0.6,2.6,-8), B=V(0.3,0,3.2), E=V(0.5,1.0,9.0);
  const p=k<0.6?A.clone().lerp(B,k/0.6).add(V(0,Math.sin(Math.PI*k/0.6)*0.6,0)):B.clone().lerp(E,(k-0.6)/0.4).add(V(0,Math.sin(Math.PI*(k-0.6)/0.4)*0.5,0));
  const b=bl(); showB(b,p,1,BS*1.4); const eye=V(0.5,1.7,9.6);
  const gT=k<0.35?p:B; const gl=ln(MT,4,true); setLine(gl,[eye,gT]); gl.material.opacity=0.85;
  const r=rg(); r.rotation.set(-Math.PI/2,0,0); r.position.set(B.x,0.02,B.z); r.scale.setScalar(0.8+0.2*Math.sin(v*6)); r.material.color.set(MT).multiplyScalar(GLOW.k); r.material.opacity=0.9*ss(0.3,0.36,k);
  const t=tx('scT',T('板球研究：顶级击球手的视线提前跳到落点等球','Cricket studies: elite batters\' eyes jump ahead to the bounce'),{color:'#c8ffe6',size:0.32,glow:MINT}); hud(t,0,2.5); op(t,ss(0,0.6,v)*(1-ss(TI-SC-0.4,TI-SC,v)));
  const ti=bt('readT',T('接发，在球过网之前就开始了','The return starts before the ball crosses the net'),{size:0.64,glow:GOLD,accent:T('之前','before'),fx:'write'}); hud(ti,0,-2.2); ti.update(v,TI-SC);
  look(3.2,2.4,12,0,0.8,1); rims(MT,CY,4); }

// ---------- 4 分腿垫步：快一成多；牵张-缩短循环 ----------
function spring(a,b,col,o,comp){ const l=ln(col,4); const pts=[]; const ax=b.clone().sub(a), len=ax.length(); ax.normalize(); const side=new THREE.Vector3(1,0,0).cross(ax).normalize(); const side2=ax.clone().cross(side).normalize(); const n=10, r=0.07*(1+comp*0.6);
  for(let i=0;i<=n*16;i++){ const t=i/(n*16); const ang=t*n*Math.PI*2; pts.push(a.clone().addScaledVector(ax,len*t).addScaledVector(side,Math.cos(ang)*r).addScaledVector(side2,Math.sin(ang)*r)); } setLine(l,pts); l.material.opacity=o; }
function shotSplit(u,D){
  const GOg=ev('go',0.5), HP=ev('hop',4.7), RC=ev('race',7.7), SP=ev('spring',15.5), TI=ev('title',20.1);
  courtG.visible=true;
  if(u<RC-0.3){ humanOp(RET,1); place(RET,0,L2+0.6,Math.PI); const v=u-HP; const per=2.4; const k=v<0?0:(v%per)/per;
    const P=k<0.15?mixPose(POSE.ready,POSE.split,ss(0,0.15,k)):k<0.4?mixPose(POSE.split,POSE.land,ss(0.15,0.4,k)):k<0.75?mixPose(POSE.land,POSE.lungeF,ss(0.45,0.75,k)):mixPose(POSE.lungeF,POSE.ready,ss(0.75,1,k));
    applyPose(RET,P); RET.root.position.y=k>0.15&&k<0.4?Math.sin(Math.PI*(k-0.15)/0.25)*0.12:0; RET.root.position.x=k>0.45&&k<0.75?ss(0.45,0.75,k)*1.0:k>=0.75?lerp(1,0,ss(0.75,1,k)):0;
    SLOW=[HP,RC];
    const t=tx('spT',T('分腿垫步：对手击球那一刻起跳','Split step: take off as the server strikes'),{color:'#c8f4ff',size:0.36,glow:CYAN}); hud(t,0,-2.3); op(t,ss(HP,HP+0.6,u));
    look(3.6,1.4,L2+4.2,0,0.9,L2+0.6); rims(CY,GO,5); return; }
  if(u<SP-0.3){ // 两个人比启动：垫步的先到
    const v=u-RC; humanOp(G1,1); humanOp(G2,1); const per=3.0, k=(v%per)/per;
    const go=t=>clamp((t-0.12)/0.75), go2=t=>clamp((t-0.12)/(0.75/1.125));   /* 垫步约快 12%：同样距离，用时 ÷ 1.12 */
    [[G1,-1.4,go(k),false],[G2,1.4,go2(k),true]].forEach(([H,x,g,sp])=>{ place(H,x,0,Math.PI*0.5); H.root.position.z=-g*4.5+2; applyPose(H,g>0&&g<1?mixPose(POSE.lungeF,POSE.ready,0.5*Math.sin(g*20)+0.5):POSE.ready); });
    const f1=ln(0x9fb8d0,4), f2=ln(CY,4); setLine(f1,[V(-1.4,0.02,-2.5),V(1.4,0.02,-2.5)]); f1.material.opacity=0.7; f2.material.opacity=0;
    const a=tx('spA',T('不垫步','No split step'),{color:'#c8d8ea',size:0.36}); a.position.set(-1.4,2.3,2); op(a,1);
    const b=tx('spB',T('垫步','Split step'),{color:'#c8f4ff',size:0.36,glow:CYAN}); b.position.set(1.4,2.3,2); op(b,1);
    const r=tx('spR',T('实验：快 12–13%','Lab tests: 12–13% faster'),{color:'#ffffff',size:0.46,glow:CYAN}); hud(r,0,-2.2); op(r,ss(0.3,0.9,v));
    const s=tx('spS',T('Uzu 等 2009；Nieminen 等 2014（光信号实验）','Uzu et al. 2009; Nieminen et al. 2014 (light-signal tasks)'),{color:'#9fb8d0',size:0.24}); hud(s,2.6,-2.95); op(s,1);
    look(0,4.2,7.2,0,0.6,0); rims(CY,0x9fb8d0,5); return; }
  // X 光腿：肌肉和肌腱像弹簧
  const v=u-SP; look(1.6,1.0,L2+3.0,0,0.6,L2+0.6); humanOp(RET,0.35); place(RET,0,L2+0.6,Math.PI); const per=2.2, k=(v%per)/per; const comp=k<0.4?ss(0,0.4,k):1-ss(0.4,0.55,k);
  applyPose(RET,mixPose(POSE.split,POSE.land,comp));
  [[RET.legR,0],[RET.legL,1]].forEach(([Lg,i])=>{ const hip=wpos(Lg.hp), knee=wpos(Lg.kn), an=wpos(Lg.an); spring(hip,knee,GO,0.9,comp); spring(knee,an,GO,0.9,comp); const g=gs(GO,0.5+0.5*comp,0.35*comp); g.position.copy(knee); });
  const e=ln(GO,10); setLine(e,[hp(-3.8,-1.4),hp(-3.8,-1.4+2.2*comp)]); e.material.opacity=0.9; const el=tx('spE',T('储能','Stored energy'),{color:'#ffe2a0',size:0.3}); hud(el,-3.8,-1.75); op(el,1);
  const ti=bt('ssc',T('牵张-缩短循环','Stretch-shortening cycle'),{size:0.78,glow:GOLD,fx:'sag'}); hud(ti,0,2.3); ti.update(v,TI-SP);   /* 下沉：像落地 */
  const l=tx('spL',T('落地拉长 → 像弹簧一样存能 → 立刻弹出','Landing stretches → stores energy like a spring → snaps back'),{color:'#ffffff',size:0.32}); hud(l,0,-2.3); op(l,ss(0,0.6,v));
  rims(GO,CY,6); }

// ---------- 5 硬地滑步：静摩擦 → 滑动摩擦 ----------
function shotSlide(u,D){
  const SL=ev('slide',2.3), GR=ev('grip',7.7), KN=ev('kin',11.9), CP=ev('comp',17.1);
  courtG.visible=true;
  if(u<CP-0.3){ humanOp(RET,1); place(RET,0,L2,Math.PI); const per=4.0, v=Math.max(0,u-SL), k=(v%per)/per;
    const x=k<0.55?ss(0,0.55,k)*3.2:3.2-ss(0.7,1,k)*3.2; RET.root.position.x=x; applyPose(RET,k<0.15?POSE.ready:k<0.7?mixPose(POSE.ready,POSE.lungeF,ss(0.15,0.45,k)):mixPose(POSE.lungeF,POSE.ready,ss(0.7,1,k)));
    const foot=wpos(RET.legR.ft); const sliding=k>0.3&&k<0.55; const mu=u<KN?1:(sliding?0.55:1);
    const fl=ln(u<KN?GO:CY,14); setLine(fl,[foot.clone().setY(0.06),foot.clone().setY(0.06).add(V(-1.6*mu,0,0))]); const fh=ln(u<KN?GO:CY,14); const tip=foot.clone().setY(0.06).add(V(-1.6*mu,0,0)); setLine(fh,[tip.clone().add(V(0.25,0,0.15)),tip,tip.clone().add(V(0.25,0,-0.15))]); fh.material.opacity=u>GR?0.95:0; fl.material.opacity=u>GR?0.95:0;
    const tr=ln(CY,5); setLine(tr,[V(Math.max(0,x-1.6),0.02,L2+0.15),V(x,0.02,L2+0.15)]); tr.material.opacity=sliding&&u>SL?0.6:0;
    const a=tx('slA',T('静摩擦：抓住地面','Static friction: grip'),{color:'#ffe2a0',size:0.36,glow:GOLD}); hud(a,0,-2.25); op(a,ss(GR,GR+0.6,u)*(1-ss(KN-0.3,KN,u)));
    const b=tx('slB',T('滑起来：滑动摩擦更小，一边刹车一边到位','Sliding: smaller kinetic friction, braking while reaching'),{color:'#c8f4ff',size:0.34,glow:CYAN}); hud(b,0,-2.25); op(b,ss(KN,KN+0.6,u));
    const c=tx('slC',T('摩擦力示意','Friction schematic'),{color:'#9fb8d0',size:0.24}); hud(c,3.6,-2.95); op(c,ss(GR,GR+0.6,u));
    SLOW=[SL,CP]; look(lerp(5.5,3.2,ss(0,GR,u)),lerp(1.8,0.8,ss(GR-1,GR+1,u)),L2+lerp(5.5,3.4,ss(0,GR,u)),1.6,0.4,L2); DOF.on=u>GR; DOF.focus=3.6; DOF.ap=0.00005; rims(GO,CY,5); return; }
  // 两个人比回位：滑步刹车先回到中间
  const v=u-CP; humanOp(G1,1); humanOp(G2,1); const per=3.4, k=(v%per)/per;
  [[G1,-0.9,1.0,false],[G2,0.9,1/1.08,true]].forEach(([H,dz,sc,sl])=>{ const kk=clamp(k/sc); const x=kk<0.5?ss(0,0.5,kk)*3:3-ss(0.5,1,kk)*3; place(H,x-1.5,L2+dz,Math.PI); applyPose(H,kk<0.5?mixPose(POSE.ready,POSE.lungeF,ss(0.1,0.5,kk)):mixPose(POSE.lungeF,POSE.ready,ss(0.5,1,kk))); });
  const a=tx('slD',T('普通刹车','Normal braking'),{color:'#c8d8ea',size:0.34}); a.position.set(-3.6,2.2,L2-0.9); op(a,1);
  const b=tx('slE',T('滑步刹车','Slide braking'),{color:'#c8f4ff',size:0.34,glow:CYAN}); b.position.set(-3.6,2.2,L2+0.9); op(b,1);
  const r=tx('slR',T('大学精英球员实验：滑步回位更快（Ji 等 2025）','Elite college players: sliding recovers faster (Ji et al. 2025)'),{color:'#ffffff',size:0.32}); hud(r,0,-2.25); op(r,ss(0.3,0.9,v));
  look(0,5.5,L2+6.5,0,0.5,L2); rims(CY,0x9fb8d0,4); }

// ---------- 6 数据：榜单拆开看 ----------
function shotData(u,D){
  const BD=ev('board',0.5), SM=ev('sum',5.0), AL=ev('all',9.5), HD=ev('hard',11.9), AC=ev('act',13.3), Y1=ev('y11',17.1), DP=ev('deep',23.1), HH=ev('h2h',30.5), LS=ev('last',36.3);
  if(u<Y1-0.3){ // 四项相加 → 三个名次
    look(Math.sin(u*0.2)*0.4,0.3,9,0,0.2,0); const o=ss(BD,BD+0.6,u); const comps=[[T('一发接发得分率','1st-serve return pts'),33.4,GO],[T('二发接发得分率','2nd-serve return pts'),55.0,CY],[T('接发局胜率','Return games won'),31.2,MT],[T('破发成功率','Break points converted'),43.9,0xa78bfa]];
    let acc=0; const ks=ss(SM,SM+2.0,u);
    comps.forEach(([s,val,c],i)=>{ const w=val/170*8.4; const x0=lerp(-4.2,-4.2+acc,ks), y=lerp(1.3-i*0.6,-0.3,ks); const l=ln(c,12); setLine(l,[hp(x0,y),hp(x0+w,y)]); l.material.opacity=o*ss(SM-0.2+i*0.25,SM+0.4+i*0.25,u+0.6)*(1-ss(AL-0.6,AL,u));
      const t=tx('dc'+i,s+' '+val.toFixed(1),{color:'#ffffff',size:0.26}); hud(t,x0+w/2,y+0.32); op(t,o*(1-ks)); acc+=w; });
    const sum=tx('dSum',T('= 163.5','= 163.5'),{color:'#ffe2a0',size:0.5,glow:GOLD}); hud(sum,3.9,-0.3); op(sum,ks*(1-ss(AL-0.3,AL,u)));
    const hd=tx('dH',T('ATP 接发评分 = 四项百分比相加','ATP Return Rating = four percentages added'),{color:'#c8f4ff',size:0.34,glow:CYAN}); hud(hd,0,2.5); op(hd,ss(SM,SM+0.5,u)*(1-ss(AL-0.3,AL,u)));
    const ranks=[[AL,'7',T('历史','All-time'),'#ff9a8a'],[HD,'2',T('硬地','Hard court'),'#ffd27a'],[AC,'1',T('现役','Active players'),'#7fffd0']];
    ranks.forEach(([e,n,s,c],i)=>{ const k=ss(e,e+0.5,u); const o3=t3d('rk'+n,n,c,1.3); o3.g.position.copy(hp(-3+i*3,0.2,9)); o3.g.quaternion.copy(camera.quaternion); t3op(o3,k); const t=tx('rkl'+i,s,{color:'#ffffff',size:0.4}); hud(t,-3+i*3,-1.1); op(t,k); });
    const ft=tx('dF',T('ATP 官方榜单，截至 2026 年 11 月','ATP official leaderboards, as of Nov 2026'),{color:'#9fb8d0',size:0.24}); hud(ft,2.6,-2.95); op(ft,ss(AL,AL+0.5,u));
    rims(GO,CY,4); return; }
  if(u<DP-0.3){ // 2011：38.8% 的接发局
    const v=u-Y1; const k=ss(0.2,1.8,v); const r=ln(GO,12); arc(r,V(0,0.3,0),1.6,Math.PI/2,Math.PI/2-Math.PI*2*0.388*k,'z'); r.material.opacity=0.95; const r2=ln(0x5a6a80,4); arc(r2,V(0,0.3,0),1.6,0,Math.PI*2,'z'); r2.material.opacity=0.6;
    const n=t3d('p388','38.8%','#ffd27a',0.6); n.g.position.set(0,0.3,0); t3op(n,ss(0.6,1.2,v)); const y=t3d('y2011','2011','#c8f4ff',0.45); y.g.position.set(0,2.4,0); t3op(y,ss(0,0.5,v));
    const t=tx('d11',T('接发局胜率 · 当年接发评分第一','Return games won · No. 1 that year'),{color:'#ffffff',size:0.36}); hud(t,0,-2.3); op(t,ss(0.4,1,v));
    look(0,0.5,7.2,0,0.4,0); rims(GO,CY,4); return; }
  if(u<HH-0.3){ // 回球深度：3D 球场上 100 个落点，八成落在发球线以后
    const v=u-DP; courtG.visible=true; const kd=ss(0.3,2.5,v);
    const cnt=Math.floor(100*kd); DOTS.forEach((m,i)=>{ const deep=(i%5)!==4; const h=((i*7919)%997)/997, h2=((i*104729)%991)/991; m.visible=i<cnt;   /* 100 个落点，按真实的八成落在发球线以后 */
      m.position.set(-3.6+h2*7.2,0.06,deep?-(SLN+0.4+h*(L2-SLN-0.8)):-(1.2+h*(SLN-1.6))); m.material.color.set(deep?CY:RD).multiplyScalar(0.9); });
    const sl=ln(WH,4); setLine(sl,[V(-4.1,0.03,-SLN),V(4.1,0.03,-SLN)]); sl.material.opacity=0.9*ss(0,0.5,v);
    const a=tx('dpA',T('发球线','Service line'),{color:'#ffffff',size:0.3}); a.position.set(4.6,0.4,-SLN); op(a,ss(0,0.5,v));
    const names=[[T('德约','Djokovic'),80,CY],[T('穆雷','Murray'),76,0x9fb8d0],[T('辛纳','Sinner'),76,0x9fb8d0],[T('费德勒','Federer'),75,0x9fb8d0],[T('阿加西','Agassi'),74,0x9fb8d0],[T('阿尔卡拉斯','Alcaraz'),74,0x9fb8d0],[T('纳达尔','Nadal'),69,0x9fb8d0]];
    look(-4.2,9.5,2.5,-4.2,0,-7.5);   /* 球场偏到画面右边，左边放名单 */
    names.forEach(([s,val,c],i)=>{ const k=ss(1.4+i*0.25,2.0+i*0.25,v); const y=1.9-i*0.48; const l=ln(c,i?8:12); setLine(l,[hp(-2.9,y),hp(-2.9+(val-60)/25*2.4*k,y)]); l.material.opacity=k; const t=tx('dpn'+i,s+'  '+val+'%',{color:i?'#c8d8ea':'#ffffff',size:0.28,glow:i?'rgba(120,160,200,0.6)':CYAN}); hud(t,-4.0,y); op(t,k); });
    const h=tx('dpH',T('回到发球线以后的比例（志愿者逐分统计）','Returns landing beyond the service line (volunteer charting)'),{color:'#c8f4ff',size:0.32,glow:CYAN}); hud(h,0,2.6); op(h,ss(0.3,0.9,v));
    rims(CY,GO,4); return; }
  // 对大炮发球手
  const v=u-HH; const pairs=[[T('拉奥尼奇','Raonic'),'12 – 0'],[T('伊斯内尔','Isner'),'10 – 2']];
  pairs.forEach(([s,sc],i)=>{ const k=ss(i*0.6,i*0.6+0.6,v); const o3=t3d('hh'+i,sc,i?'#ffd27a':'#7fffd0',0.75); o3.g.position.set(-2.2+i*4.4,0.4,0); t3op(o3,k*(1-ss(LS-HH-0.3,LS-HH,v))); const t=tx('hhn'+i,T('对 ','vs ')+s,{color:'#ffffff',size:0.42}); t.position.set(-2.2+i*4.4,-0.7,0); op(t,k*(1-ss(LS-HH-0.3,LS-HH,v))); });
  const h=tx('hhH',T('面对大炮发球手（ATP 交手记录）','Against big servers (ATP head-to-head)'),{color:'#c8f4ff',size:0.34,glow:CYAN}); hud(h,0,2.5); op(h,ss(0,0.5,v)*(1-ss(LS-HH-0.3,LS-HH,v)));
  const ti=bt('dataT',T('未必破发最多，却回得最深','Not the most breaks — but the deepest returns'),{size:0.66,glow:GOLD,accent:T('回得最深','deepest'),fx:'spin'}); hud(ti,0,0.3); ti.update(v,LS-HH);
  look(Math.sin(v*0.3)*0.6,0.3,8.5,0,0.2,0); rims(GO,CY,4); }

// ---------- 7 结论 ----------
function shotEnd(u,D){
  const N0=ev('n0',0.5), P1=ev('p1',5.0), P2=ev('p2',5.9), P3=ev('p3',6.5), QQ=ev('q',9.3);
  look(lerp(3,1.5,ss(0,D,u)),1.6,L2+5,0,1.0,L2); courtG.visible=true; humanOp(RET,1); place(RET,0,L2+0.6,Math.PI); applyPose(RET,poseAt([[0,'ready'],[P2,'ready'],[P2+0.3,'split'],[P2+0.6,'land'],[P3+0.4,'lungeF'],[P3+1.6,'ready']],u));
  const t0=bt('endA',T('接发比的不是反应','It\'s not about reaction speed'),{size:0.7,glow:CYAN,fx:'particles'}); hud(t0,0,2.4); t0.update(u,N0,P1-0.6);
  const pil=[[P1,T('更早看懂','Read earlier'),MT],[P2,T('及时起跳','Split in time'),CY],[P3,T('回得够深','Return deep'),GO]];
  pil.forEach(([e,s,c],i)=>{ const k=ss(e,e+0.5,u); const x=-3.2+i*3.2; const l=ln(c,10); setLine(l,[hp(x,-1.7),hp(x,-1.7+1.5*k)]); l.material.opacity=k*(1-ss(QQ-0.4,QQ,u)); const t=tx('pil'+i,s,{color:'#ffffff',size:0.42,glow:i===0?MINT:i===1?CYAN:GOLD}); hud(t,x,-2.2); op(t,k*(1-ss(QQ-0.4,QQ,u))); });
  const q=bt('endQ',T('你心中的接发之王是谁？','Who is your king of the return?'),{size:0.82,glow:GOLD,fx:'shock'}); hud(q,0,2.4); q.update(u,QQ);
  const nm=tx('endN',T('德约 · 纳达尔 · 阿加西 ……','Djokovic · Nadal · Agassi …'),{color:'#ffe2a0',size:0.5,glow:GOLD}); hud(nm,0,1.4); op(nm,ss(QQ+0.6,QQ+1.2,u));
  rims(GO,CY,5); beamMat.uniforms.uOp.value=0.1; }

const SHOTS={hook:shotHook,race:shotRace,read:shotRead,split:shotSplit,slide:shotSlide,data:shotData,end:shotEnd};
function shotTest(u,D){}
Object.assign(PAL,{
  hook: {top:0x05030f,hz:0x1a1048,vi:0x3a0a3a,a:0xffc24a},
  race: {top:0x030812,hz:0x0b2a50,vi:0x0a2030,a:0x4fe3ff},
  read: {top:0x020c0a,hz:0x063828,vi:0x062a2a,a:0x34f5a8},
  split:{top:0x03050c,hz:0x0c1a3a,vi:0x08202a,a:0x4fe3ff},
  slide:{top:0x0c0806,hz:0x3a2a08,vi:0x0a2030,a:0xffc24a},
  data: {top:0x06041a,hz:0x1d1250,vi:0x2b0d55,a:0xa78bfa},
  end:  {top:0x050505,hz:0x2a2008,vi:0x08202a,a:0xffc24a}});
