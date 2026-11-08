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
  FLOW.hide(); BL.hide(); TOWER.set(0); TOWER.g.scale.setScalar(1); TOWER.g.position.set(0,0,0); WIRE.material.opacity=0; BL.smooth.material.color.set(0xb0c430); HUM.forEach(H=>{ H.root.scale.setScalar(1); if(H.racket) H.racket.g.visible=true; }); ST_RATE=0.0003; courtG.userData.mat.color.set(0xffffff); }
// 全息榜单行
function row(k,i,str,val,max,col,o,hl=0){ const y=1.4-i*0.75; const w=4.6*clamp(val/max); const l=ln(col,hl?14:10); setLine(l,[V(-1.2,y,0),V(-1.2+w,y,0)]); l.material.opacity=o*(0.75+0.25*hl);
  const t=tx(k,str,{color:hl?'#ffffff':'#c8d8ea',size:0.42,glow:hl?CYAN:'rgba(120,160,200,0.6)'}); t.position.set(-3.4,y,0.1); op(t,o); }

// ---------- 1 钩子：开场即砸出冲突——「7」从天而降炸开 → 炸成「接发之王」→ 甩进 2011 美网赛点接发 → 王在哪？ ----------
// 所有者 2026-11-07：「前几秒一定要抓住人……直接抛出来，然后用炸裂或者是非常爆裂的动作，或者特效把这个东西做到极致」
function burst(c,k,col,spread=6,o=1){ const cc=new THREE.Color(col); for(let i=0;i<1600;i++){ const p=PTS[i]; const dir=V(p[0],p[1]*1.2,p[2]).normalize(); const sp=spread*(0.4+0.6*p[3]); const e=1-Math.pow(1-clamp(k),2.2);
  cset(pt,i,c.x+dir.x*sp*e,c.y+dir.y*sp*e-1.5*e*e,c.z+dir.z*sp*e,cc.r,cc.g,cc.b,o*(1-ss(0.55,1,k))*(0.5+0.5*p[4])); } cdone(pt); }
function shockRing(c,k,col,maxR,o=1,vertical=false){ const r=rg(); r.position.copy(c); vertical?r.rotation.set(0,0,0):r.rotation.set(-Math.PI/2,0,0); const e=1-Math.pow(1-clamp(k),3); r.scale.setScalar(0.2+maxR*e); r.material.color.set(col).multiplyScalar(GLOW.k); r.material.opacity=o*(1-ss(0.35,1,k)); }



// ==================== EP11 本集镜头工具 ====================
const PJ=0x9dff5a, BLU=0x5aa8ff, OR=0xffb347;
function lab(k,str,x,y,o,opt={}){ const t=tx(k,str,Object.assign({color:'#e8f4ff',size:0.34,glow:CYAN},opt)); if(x!==null) hud(t,x,y,opt.d||9); op(t,o); return t; }   // x=null：世界坐标（调用方设 position）
function bar(col,x0,x1,y,o,w=10,d=9){ const l=ln(col,w); setLine(l,[hp(x0,y,d),hp(Math.abs(x1-x0)<0.001?x0+0.001:x1,y,d)]); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=20; return l; }
// Cd–Re 图表（镜头空间）：k＝画到哪（0–1）
const CH={x0:-4.3,x1:-0.3,y0:-2.6,y1:0.9};
function chart(o,parts,d=9){ const {x0,x1,y0,y1}=CH;
  const ax=ln(0x9fb8d0,2); setLine(ax,[hp(x0,y1+0.2,d),hp(x0,y0,d),hp(x1+0.2,y0,d)]); ax.material.opacity=o*0.7; ax.material.depthTest=false;
  lab('chY',T('阻力系数','drag coefficient'),x0+0.1,y1+0.45,o,{size:0.24,color:'#aab8c8'}); lab('chX',T('雷诺数（≈ 速度 × 球的大小）→','Reynolds number (≈ speed × size) →'),(x0+x1)/2,y0-0.4,o,{size:0.24,color:'#aab8c8'});
  for(const [arr,col,k] of parts){ if(k<=0) continue; const l=ln(new THREE.Color(col).multiplyScalar(0.55),5); setLine(l,curvePts(arr,x0,x1,y0,y1,k,d)); l.material.opacity=o*0.85; l.material.depthTest=false; l.renderOrder=20; } }   // 光晕标准：曲线是叠加发光，压暗
const chartP=(lx,cd,d=9)=>hp(lerp(CH.x0,CH.x1,(lx-4)/2.2),lerp(CH.y0,CH.y1,cd/0.7),d);
function dotAt(lx,cd,col,o,s=0.5){ const g=gs(col,s*0.8,o*0.55); g.position.copy(chartP(lx,cd)); g.renderOrder=21; g.material.depthTest=false; return g; }
const L10=(v_kmh)=>Math.log10(v_kmh/3.6*0.067/1.5e-5);   // 6.7 cm 球的 log10(Re)
// 在镜头空间画一颗球（大小以屏幕单位计）
function hball(m,x,y,R,d=9,o=1,spin=0){ showBall(m,hp(x,y,d),R,o,spin); }

// ---------- 1 钩子：网球为什么要长毛？→ 剃光 → 同一记 200 km/h 的发球：光球忽快忽慢、网球稳稳 118 → 刹车，更是稳定器 → 铁塔 ----------
function shotHook(u,D){
  const SH=ev('shave',3.6), SV=ev('serve',5.2), FK=ev('fork',7.6), WB=ev('wobble',13.1), SD=ev('steady',16.7), BR=ev('brake',22.4), STb=ev('stab',23.5), TW=ev('tower',25.8);
  if(u<SV-0.2){ // 微距：毛茸茸的网球自转 → 毛被一阵风剃飞
    look(Math.sin(u*0.3)*0.4,0.1,lerp(4.8,4.2,ss(0,SV,u)),0,0,0); rims(PJ,CY,4);
    const c=V(0,0,0); showBall(BL.tennis,c,1.0,1,u*0.6); const fz=1-ss(SH,SH+0.6,u); BL.fuzz(c,1.0,Math.max(0.02,fz)*1.6,1);
    if(u>SH){ const k=(u-SH)/1.4; burst(c.clone().add(V(0.3,0,0)),k,0xeaff80,4,0.9); showBall(BL.smooth,c,1.002,ss(SH+0.1,SH+0.5,u),u*0.6); BL.tennis.visible=ss(SH+0.1,SH+0.5,u)<0.999; /* 有毛的球保持不透明垫在下面，光球淡入盖住再撤：两颗都半透明会一起变暗、中间一帧几乎全空（motion_check 3.87s 跳变） */ }
    const q=bt('hkQ',T('网球为什么要长毛？','Why does a tennis ball wear fuzz?'),{size:0.95,glow:'rgba(214,238,58,0.55)',fx:'particles'}); hud(q,0,1.75,9); q.update(u,0.2,SH+0.4,0.85);
    return; }
  // 侧上方看球场：两条球道，同一记 200 km/h 的发球（按 v=v0/(1+k v0 t) 的阻力规律慢放）；光球两个幽灵＝悬崖前（Cd 0.5）/悬崖后（Cd 0.1）
  courtG.visible=true; ST_RATE=0.0005; const v=u-SV; const per=3.4; const L2_=11.885;
  look(19,9.5,1.5,0,1.4,0.5); rims(CY,GO,5);
  const k=(Math.max(0,v)%per)/per;
  const zAt=(cd)=>{ const kk=0.5*1.21*cd*Math.PI*0.0335*0.0335/0.0577; return Math.min(L2_+2,-L2_+Math.log(1+kk*55.6*k*0.55)/kk); };
  const o=ss(SV-0.2,SV+0.3,u)*(1-ss(TW-0.6,TW,u)); const ol=o*(1-ss(BR-0.7,BR-0.1,u));   // 大字出来前，标签先退场
  const flick=(Math.sin(u*11)+Math.sin(u*17.3))>0;
  const xS=0, xT=0, yb=1.0, yS=3.0;
  const zS=zAt(u<FK?0.5:(flick?0.1:0.5)), zT=zAt(0.6);
  showBall(BL.smooth,V(xS,yS,zS),0.42,o,u*3); showBall(BL.tennis,V(xT,yb,zT),0.42,o,u*3); BL.fuzz(V(xT,yb,zT),0.42,1.2,o); const gS=gs(0xffffff,1.6,0.3*o); gS.position.set(xS,yS,zS); const gT=gs(PJ,1.6,0.35*o); gT.position.set(xT,yb,zT);
  const tr1=ln(0xffffff,3); setLine(tr1,[V(xS,yS,-L2_),V(xS,yS,zS)]); tr1.material.opacity=0.5*o; const tr2=ln(PJ,3); setLine(tr2,[V(xT,yb,-L2_),V(xT,yb,zT)]); tr2.material.opacity=0.6*o;
  if(u>FK){ const g=0.4+0.6*Math.abs(Math.sin(u*9)); const gA=gs(0xffffff,1.4,0.35*o*g); gA.position.set(xS,yS,zAt(0.5)); const gB=gs(0xffffff,1.4,0.35*o*(1-g)); gB.position.set(xS,yS,zAt(0.1)); }
  const vS=u<FK?'—':(flick?'≈ 183':'≈ 129');
  lab('hkL1',T('光溜溜的球','bald ball'),null,0,ol,{size:1.2,color:'#ffffff'}).position.set(0,yS+1.3,-L2_+1.5);
  lab('hkL2',T('网球（有毛）','tennis ball (fuzz)'),null,0,ol,{size:1.2,color:'#d8ffc8',glow:'rgba(157,255,90,0.7)'}).position.set(0,yb-1.2,-L2_+1.5);
  lab('hkV0',T('同一记发球：出手 200 km/h','same serve: launched at 200 km/h'),0,3.0,o*ss(SV,SV+0.4,u),{size:0.34,color:'#ffe2a0',glow:GOLD,plate:true});
  const t1=tx('hkVS'+vS,T('到对面 '+vS+' km/h','at the far end '+vS+' km/h'),{color:'#ffffff',size:1.2,glow:CYAN}); t1.position.set(0,yS+1.3,L2_-3.0); op(t1,ol*ss(FK,FK+0.3,u));
  lab('hkVT',T('到对面 ≈ 118 km/h，每次都一样','at the far end ≈ 118 km/h, every time'),null,0,ol*ss(SD-0.4,SD+0.2,u),{size:1.1,color:'#d8ffc8',glow:'rgba(157,255,90,0.7)'}).position.set(0,yb-1.2,L2_-3.5);
  lab('hkWB',T('忽快忽慢','fast, then slow'),0,2.35,o*ss(WB,WB+0.4,u)*(1-ss(BR-0.5,BR,u)),{size:0.5,color:'#ffb0a8',glow:RED});
  const b1=bt('hkB',T('刹车','A BRAKE'),{size:1.0,glow:'rgba(214,238,58,0.5)',fx:'particles'}); hud(b1,-2.2,1.2,9); b1.update(u,BR,TW-0.4,0.82);
  const b2=bt('hkS',T('稳定器','A STABILISER'),{size:1.0,glow:'rgba(79,227,255,0.5)',fx:'particles'}); hud(b2,2.4,1.2,9); b2.update(u,STb,TW-0.4,0.82);
  if(u>TW-0.6){ TOWER.set(ss(TW-0.6,TW+0.8,u)); TOWER.g.position.set(0,0,0); TOWER.g.scale.setScalar(1.6); look(lerp(17,10,ss(TW-0.6,D,u)),lerp(15,3,ss(TW-0.6,D,u)),lerp(2,6,ss(TW-0.6,D,u)),0,lerp(0,2.4,ss(TW-0.6,D,u)),0); }
}

// ---------- 2 埃菲尔：铁塔拔地而起 → 风洞里的球 → 阻力突然掉 → 悬崖 0.5 → 0.1 → 阻力危机 → 普朗特的细线 ----------
const WIRE=new THREE.Mesh(new THREE.TorusGeometry(1.0,0.012,8,96),new THREE.MeshBasicMaterial({color:0xffe2a0,transparent:true,opacity:0})); WIRE.rotation.y=Math.PI/2; scene.add(WIRE);
function shotEiffel(u,D){
  const TN=ev('tunnel',2.8), DR=ev('drop',10.3), CL=ev('cliff',12.5), NM=ev('name',17.4), WR=ev('wire',21.9);
  rims(GO,CY,4); const a=0.15*Math.sin(u*0.2);
  TOWER.set(ss(0,1.4,u)); TOWER.g.position.set(-4.2,-2.6,-3); TOWER.g.scale.set(1.7,1.7*ss(0,1.6,u),1.7);
  look(Math.sin(a)*10,0.6,Math.cos(a)*10,0.2,0.4,0);
  // 风洞里的球：右上；风速随时间加快 → 过了悬崖分离角从 80° 跳到 120°
  const c=V(1.4,1.1,0), R=0.75; const speed=ss(TN,DR+1.5,u); const crisis=ss(DR-0.2,DR+0.6,u); const wired=ss(WR,WR+0.6,u);
  const sep=lerp(80,120,Math.max(crisis*(1-ss(WR-1.2,WR-0.4,u)),wired));
  if(u>TN-0.4){ FLOW.draw(c,R,sep,0.3,ss(TN-0.4,TN+0.4,u),u,0x9fd8ff,0.3+0.6*speed); showBall(BL.smooth,c,R,1,0); }
  WIRE.material.opacity=wired; WIRE.position.copy(c); WIRE.scale.setScalar(R*1.01);
  lab('eiY',T('1912 · 埃菲尔的风洞','1912 · Eiffel’s wind tunnel'),0.8,3.0,ss(0.6,1.2,u),{size:0.32,color:'#ffe2a0',glow:GOLD,plate:true});
  // 右下的 Cd–Re 图（只画光滑球那条），点随风速滑；到悬崖掉下去
  const o=ss(DR-1.0,DR-0.3,u); CH.x0=0.4; CH.x1=4.4; CH.y0=-2.7; CH.y1=-0.3;
  chart(o,[[CURVE.smooth,0xffffff,ss(DR-1.0,CL+1.0,u)]]);
  const lx=lerp(4.6,5.75,ss(DR-0.8,CL+1.0,u)); dotAt(lx,CURVE.at(CURVE.smooth,lx),0xffffff,o*0.8,0.6);
  lab('eiA',T('约 0.5','≈ 0.5'),CH.x0+0.9,lerp(CH.y0,CH.y1,0.5/0.7)+0.3,o*ss(CL,CL+0.4,u),{size:0.3});
  lab('eiB',T('约 0.1','≈ 0.1'),CH.x0+3.0,lerp(CH.y0,CH.y1,0.1/0.7)+0.25,o*ss(CL+0.6,CL+1.0,u),{size:0.3,color:'#ffd27a'});
  CH.x0=-4.3; CH.x1=-0.3; CH.y0=-2.6; CH.y1=0.9;
  const t=bt('eiT',T('阻力危机','DRAG CRISIS'),{size:1.05,glow:'rgba(255,90,74,0.5)',fx:'particles'}); hud(t,-0.2,1.9,9); t.update(u,NM,WR-0.3,0.82);
  lab('eiW',T('1914 · 普朗特：绑一圈细线，阻力也掉了','1914 · Prandtl: a thin wire ring, and drag drops too'),0.8,2.4,ss(WR,WR+0.5,u),{size:0.3,color:'#ffe2a0',glow:GOLD});
}

// ---------- 3 边界层：钻到球面 → 层流早分离、尾流宽 → 湍流贴得更久、尾流窄 → 雷诺数 ----------
function shotLayer(u,D){
  const BLt=ev('bl',3.4), LM=ev('lam',6.7), SP=ev('sep',8.4), TB=ev('turb',16.0), NR=ev('narrow',21.0), RE=ev('re',25.8);
  rims(CY,OR,4); const k=ss(0,2.0,u); look(lerp(0.2,0.0,k),lerp(0.6,0.3,k),lerp(4.0,9.5,k),1.2,0.0,0);
  const c=V(0,0,0), R=1.4; const tt=ss(TB-0.3,TB+1.6,u); const sep=lerp(80,120,tt);
  FLOW.draw(c,R,sep,0.2+0.8*(1-tt),1,u,0x9fd8ff,0.45,0.32); showBall(BL.smooth,c,R,1,0);
  // 边界层：贴着球面的一圈细亮线
  const bl=ln(CY,4); const pts=[]; for(let i=0;i<=40;i++){ const a=Math.PI-i/40*(sep*Math.PI/180); pts.push(V(Math.cos(a)*R*1.05,Math.sin(a)*R*1.05,0)); } setLine(bl,pts); bl.material.opacity=ss(BLt,BLt+0.5,u);
  const bl2=ln(CY,4); setLine(bl2,pts.map(p=>V(p.x,-p.y,0))); bl2.material.opacity=ss(BLt,BLt+0.5,u);
  lab('lyB',T('边界层','boundary layer'),null,0,ss(BLt,BLt+0.5,u),{size:0.34}).position.set(-1.6,1.55,0.2);
  // 分离点
  const sa=Math.PI-sep*Math.PI/180; const spP=V(Math.cos(sa)*R*1.05,Math.sin(sa)*R*1.05,0);
  if(u>SP-0.3){ const g=gs(OR,0.6,0.6*ss(SP-0.3,SP+0.3,u)); g.position.copy(spP); const g2=gs(OR,0.6,0.6*ss(SP-0.3,SP+0.3,u)); g2.position.copy(V(spP.x,-spP.y,0));
    const l=lab('lyS',T('分离点','separation'),null,0,ss(SP,SP+0.4,u),{size:0.3,color:'#ffd27a',glow:GOLD}); l.position.copy(spP).add(V(0.2,0.45,0.2)); }
  lab('lyL',T('层流：早早脱开，尾流宽','laminar: separates early, wide wake'),3.0,2.4,ss(LM,LM+0.5,u)*(1-ss(TB-0.3,TB,u)),{size:0.32});
  lab('lyT',T('湍流：贴得更久，尾流变窄','turbulent: hugs longer, narrow wake'),3.0,2.4,ss(TB,TB+0.5,u),{size:0.32,color:'#ffd27a',glow:GOLD});
  // 尾流宽度标尺 + 阻力条
  const w=Math.sin(sep*Math.PI/180)*R; const ox=c.x+R*2.6; const l1=ln(OR,3); setLine(l1,[V(ox,w,0),V(ox,-w,0)]); l1.material.opacity=ss(NR-0.4,NR+0.3,u);
  const dragK=lerp(1,0.25,tt); bar(RED,-4.2,-4.2+3.2*dragK,-2.5,ss(LM,LM+0.6,u),16); lab('lyD',T('阻力','drag'),-4.7,-2.5,ss(LM,LM+0.6,u),{size:0.3,color:'#ffb0a8'});
  const r=lab('lyR',T('雷诺数 ≈ 速度 × 球的大小 ÷ 空气的黏性','Reynolds number ≈ speed × size ÷ air viscosity'),0,-1.9,ss(RE,RE+0.5,u),{size:0.32,plate:true});
  lab('lyR2',T('约 30 万：悬崖在这里','≈ 300,000: the cliff is here'),0,-2.55,ss(RE+1.5,RE+2.0,u),{size:0.34,color:'#ffd27a',glow:GOLD});
}

// ---------- 4 高尔夫：凹坑里的小涡 → 曲线左移 → 出手就在悬崖下 ----------
function shotGolf(u,D){
  const DM=ev('dimple',3.9), SF=ev('shift',7.0), DV=ev('drive',9.8);
  rims(CY,GO,4); look(Math.sin(u*0.1)*0.5,0.3,9.5,0.6,0.2,0);
  const c=V(1.6,1.0,0), R=0.9; FLOW.draw(c,R,120,0.3,1,u,0x9fd8ff,0.55,0.3); showBall(BL.golf,c,R,1,u*0.3);
  if(u>DM){ const cc=new THREE.Color(0xffd27a); for(let i=0;i<300;i++){ const p=PTS[i]; const a=Math.PI*(0.25+0.75*p[3])*(p[4]>0.5?1:-1); const s=0.03+0.02*Math.sin(u*9+i); const q=V(c.x+Math.cos(a)*R*(1.03+s),c.y+Math.sin(a)*R*(1.03+s),c.z+(p[2]/8)*0.2); cset(pt,i,q.x,q.y,q.z,cc.r,cc.g,cc.b,ss(DM,DM+0.6,u)*0.8); } cdone(pt); }
  lab('gfD',T('凹坑：把边界层提前搅乱','dimples trip the boundary layer early'),null,0,ss(DM,DM+0.5,u),{size:0.3,color:'#ffd27a',glow:GOLD}).position.copy(c).add(V(0,R+0.55,0));
  CH.x0=-4.6; CH.x1=-0.6; CH.y0=-2.7; CH.y1=0.5; const o=ss(SF-0.6,SF,u);
  chart(o,[[CURVE.smooth,0xffffff,1],[CURVE.golf,0xffd27a,ss(SF,SF+1.2,u)]]);
  lab('gfS',T('光滑球','smooth'),CH.x1-0.4,lerp(CH.y0,CH.y1,0.16/0.7)+0.3,o,{size:0.26}); lab('gfG',T('高尔夫','golf'),CH.x0+1.6,lerp(CH.y0,CH.y1,0.3/0.7)+0.2,o*ss(SF+0.6,SF+1.2,u),{size:0.26,color:'#ffd27a'});
  if(u>DV){ const lx=Math.log10(75*0.0411/1.5e-5); dotAt(lx,CURVE.at(CURVE.golf,lx),0xffd27a,ss(DV,DV+0.4,u),0.7); lab('gfV',T('一记开球：已经在悬崖下面','a drive: already past the cliff'),CH.x0+2.0,CH.y1+0.6,ss(DV,DV+0.4,u),{size:0.3,color:'#ffd27a'}); }
  CH.x0=-4.3; CH.x1=-0.3; CH.y0=-2.6; CH.y1=0.9;
}

// ---------- 5 足球：卡在悬崖边 → 不转时尾流忽左忽右 → 电梯球 ----------
function shotFootball(u,D){
  const ED=ev('edge',4.6), KN=ev('knuckle',8.2);
  rims(CY,RED,4); look(0,0.4,9.5,0,0.2,0);
  const sk=ss(KN-0.5,KN+0.5,u)*Math.sin(u*3.1)*0.9; const c=V(-0.6+sk*0.12,0.6+sk*0.25,0), R=0.95;
  FLOW.draw(c,R,lerp(80,110,ss(ED,ED+1,u)),0.8,1,u,0x9fd8ff,0.5,0.3,sk); showBall(BL.foot,c,R,1,0);
  if(u>KN){ const tr=ln(0xffffff,3); const pts=[]; for(let i=0;i<=40;i++){ const x=-5+i*0.25; pts.push(hp(x,-2.0+0.35*Math.sin(i*0.6+u*2)*ss(KN,KN+1,u),9)); } setLine(tr,pts); tr.material.opacity=0.6*ss(KN,KN+0.6,u); tr.material.depthTest=false; }
  lab('fbE',T('足球的速度：正好卡在悬崖边','a football’s speed sits right at the cliff edge'),0,2.6,ss(ED,ED+0.5,u),{size:0.32});
  lab('fbK',T('不转时，尾流忽左忽右 → 电梯球','no spin: the wake flips side to side → knuckleball'),0,-2.6,ss(KN,KN+0.5,u),{size:0.32,color:'#ffb0a8',glow:RED});
}

// ---------- 6 网球：职业球速段正好压在光滑球的悬崖上 → 没毛就时上时下 → 毛把悬崖抹平（约 0.6）→ 三组测量 → 一来一回 ----------
function shotTennis(u,D){
  const BD=ev('band',6.0), FP=ev('flip',12.8), FL=ev('flat',17.1), FZ=ev('fuzz',17.9), CD=ev('cd',21.7), LB=ev('labs',24.7), RL=ev('rally',31.8);
  const q=bt('tnQ',T('那网球呢？','And the tennis ball?'),{size:0.9,glow:'rgba(214,238,58,0.5)',fx:'particles'}); hud(q,0,0.4,9); q.update(u,0.3,2.6,0.85);
  if(u<RL-0.4){
    rims(PJ,CY,4); look(Math.sin(u*0.06)*0.4,0.3,9.5,0,0.3,0);
    const o=ss(2.4,3.2,u)*(1-ss(RL-0.9,RL-0.4,u));
    CH.x0=-3.6; CH.x1=3.6; CH.y0=-2.5; CH.y1=1.3;
    chart(o,[[CURVE.smooth,0xffffff,1],[CURVE.tennis,PJ,ss(FL,FL+1.5,u)]]);
    // 职业球速段 100–250 km/h
    if(u>BD){ const a=L10(100), b=L10(250); const ob=o*ss(BD,BD+0.6,u); const xa=lerp(CH.x0,CH.x1,(a-4)/2.2), xb=lerp(CH.x0,CH.x1,(b-4)/2.2);
      for(let i=0;i<14;i++){ const x=lerp(xa,xb,i/13); const l=ln(GO,2); setLine(l,[hp(x,CH.y0,9),hp(x,CH.y1,9)]); l.material.opacity=ob*0.25; l.material.depthTest=false; }
      lab('tnBd',T('职业比赛的球速 100–250 km/h','pro ball speeds 100–250 km/h'),(xa+xb)/2,CH.y1+0.45,ob,{size:0.3,color:'#ffd27a',glow:GOLD}); }
    if(u>FP && u<FL+0.5){ const f=(Math.sin(u*6)+Math.sin(u*9.7))>0; const lx=L10(230); dotAt(lx,f?0.1:0.48,0xffffff,0.9*ss(FP,FP+0.4,u)*(1-ss(FL,FL+0.5,u)),0.7);
      lab('tnFp',T('没毛的网球：一会儿在悬崖上，一会儿掉下去','without fuzz: on the cliff, then off it'),0,-3.05,ss(FP,FP+0.4,u)*(1-ss(FL,FL+0.5,u)),{size:0.3,color:'#ffffff'}); }
    if(u>FL){ for(const v of [100,160,230]){ const lx=L10(v); dotAt(lx,CURVE.at(CURVE.tennis,lx),PJ,ss(FL+1,FL+1.5,u),0.55); } }
    lab('tnCd',T('网球：约 0.6，没有悬崖','tennis ball: ≈ 0.6, no cliff'),lerp(CH.x0,CH.x1,0.75),lerp(CH.y0,CH.y1,0.6/0.7)+0.45,ss(CD,CD+0.5,u)*o,{size:0.36,color:'#d8ffc8',glow:'rgba(157,255,90,0.7)'});
    lab('tnLb',T('三组风洞与理论测量，结论一致','three independent measurements agree'),0,-3.05,ss(LB,LB+0.5,u)*o,{size:0.3});
    // 绒毛显微：右上角一颗大网球，毛尖拖出小涡
    const fo=ss(FZ-0.3,FZ+0.6,u)*(1-ss(LB-0.4,LB,u)); if(fo>0){ const c=hp(2.75,1.75,7); showBall(BL.tennis,c,0.55,fo,u*0.3); BL.fuzz(c,0.55,2.2,fo);
      const cc=new THREE.Color(0xeaff80).multiplyScalar(0.5); for(let i=0;i<500;i++){ const p=PTS[i]; const a=(p[3]-0.5)*Math.PI*1.2+Math.PI*0.5*(p[4]>0.5?1:-1); const r=0.55*(1.12+0.05*Math.sin(u*8+i)); const sw=0.05*Math.sin(u*6+i*1.3);
        const q=c.clone().add(V(Math.cos(a)*r+sw+((u*0.6+p[0])%1)*0.4,Math.sin(a)*r,0)); cset(pt,i,q.x,q.y,q.z,cc.r,cc.g,cc.b,fo*0.6); } cdone(pt);
      lab('tnFz',T('每根毛自己都在挡风','every fibre adds its own drag'),3.1,0.6,fo,{size:0.3,color:'#eaff80',glow:'rgba(214,238,58,0.6)'}); }
    CH.x0=-4.3; CH.x1=-0.3; CH.y0=-2.6; CH.y1=0.9; return; }
  // 一来一回：带看台的球场，网球在两端之间稳稳往返
  courtG.visible=true; ST_RATE=0.0008; const k=ss(RL-0.4,D,u); look(lerp(9,7,k),lerp(4.5,3.8,k),lerp(13,11,k),0,0.6,0); rims(PJ,CY,5);
  const per=1.6, f=((u-RL)%per)/per, dir=Math.floor((u-RL)/per)%2; const z=lerp(-10,10,dir?1-f:f); const y=0.5+1.4*Math.sin(Math.PI*f);
  const p=V(0.6*Math.sin(u),y,z); showBall(BL.tennis,p,0.12,1,u*4); BL.fuzz(p,0.12,1,1); const g=gs(PJ,0.6,0.35); g.position.copy(p);
  const t=bt('tnR',T('慢一点、稳一点，才有一来一回','Slower, steadier — that’s what makes a rally'),{size:0.7,glow:'rgba(214,238,58,0.45)',fx:'particles'}); hud(t,0,2.3,9); t.update(u,RL+0.2,D-0.1,0.82);
}

// ---------- 7 毛的状态：紧的毛 vs 蓬的毛 → 尾流与阻力 → 球员挑球 → 帕特·卡什 ----------
function shotFluff(u,D){
  const FLc=ev('fl',2.6), PK=ev('pick',8.2), CS=ev('cash',11.2);
  rims(PJ,GO,4); look(0,0.4,9.5,0,0.3,0);
  if(u<PK-0.3){ const o=ss(0,0.6,u); const a=hp(-2.4,0.6,9.5), b=hp(2.4,0.6,9.5);
    showBall(BL.tennis,a,0.8,o,u*0.4); showBall(BL.tennis2,b,0.8,o,u*0.4); BL.fuzz(b,0.8,3.2,o);
    // 右边那颗用另一份毛壳：蓬
    FLOW.draw(b,0.8,85,0.6,o*ss(FLc,FLc+0.6,u),u,0x9fd8ff,0.4,0.2);
    const cc=new THREE.Color(0xeaff80).multiplyScalar(0.5); for(let i=0;i<900;i++){ const p=PTS[i%1600]; const uu=p[3]*2-1, ang=p[4]*6.283, s=Math.sqrt(1-uu*uu); const r=0.8*(1+0.22*(0.2+0.8*((i*7)%10)/10)+0.02*Math.sin(u*5+i)); cset(pt,700+i%900,b.x+s*Math.cos(ang)*r,b.y+uu*r,b.z+s*Math.sin(ang)*r,cc.r,cc.g,cc.b,o); }
    cdone(pt); const tb=BL.tennis.clone();
    lab('flA',T('毛紧','tight felt'),-2.4,-0.7,o,{size:0.34,color:'#d8ffc8'}); lab('flB',T('毛蓬','fluffed-up felt'),2.4,-0.7,o,{size:0.34,color:'#ffd27a'});
    lab('flD',T('毛越蓬，阻力越大','the fluffier, the more drag'),0,2.4,ss(FLc,FLc+0.5,u),{size:0.38,color:'#ffffff'});
    return; }
  // 挑球：全息球员在底线前，三颗球悬在手前，挑出毛紧的那颗
  courtG.visible=true; ST_RATE=0.0004; const H=RET; humanOp(H,1); place(H,0.3,11.0,Math.PI); applyPose(H,POSE.stand);
  look(2.6,1.6,14.4,0.3,1.1,11.0); rims(PJ,CY,5);
  const hand=V(0.3,1.15,10.4); const pp=[]; for(let i=0;i<3;i++){ const p=hand.clone().add(V((i-1)*0.22,0.05*Math.sin(u*2+i)+(i===1?ss(PK+0.8,PK+1.6,u)*0.25:0),0)); pp.push(p); }
  showBall(BL.tennis,pp[1],0.06,1,u); BL.fuzz(pp[1],0.06,0.8,1); showBall(BL.smooth,pp[0],0.062,0.9,u); showBall(BL.golf,pp[2],0.001,0,0);
  const cc=new THREE.Color(0xeaff80); for(const [q,amt] of [[pp[0],1.6],[pp[2],1.6]]){ for(let i=0;i<120;i++){ const p=PTS[i]; const uu=p[3]*2-1, ang=p[4]*6.283, s2=Math.sqrt(1-uu*uu); const r=0.062*(1+0.25*amt*0.5); cset(pt,(q===pp[0]?0:200)+i,q.x+s2*Math.cos(ang)*r,q.y+uu*r,q.z+s2*Math.sin(ang)*r,cc.r,cc.g,cc.b,0.8); } } cdone(pt);
  const sel=pp[1]; const g=gs(PJ,0.4,0.5*ss(PK+0.8,PK+1.4,u)); g.position.copy(sel);
  lab('flP',T('发球前，挑一颗毛不蓬的','before serving: pick the one with tight felt'),0,2.5,ss(PK,PK+0.5,u),{size:0.34});
  lab('flC',T('「发球，你要一颗没起毛的球。」——帕特·卡什，1987 温网冠军','“If you’re serving, you want a ball that isn’t fluffed up.” — Pat Cash, 1987 Wimbledon champion'),0,-2.4,ss(CS,CS+0.6,u),{size:0.3,color:'#ffe2a0',glow:GOLD,plate:true});
}

// ---------- 8 国际网联 3 号球：大约 6%，重量不变 → 迎风面积大、阻力大 ----------
function shotItf(u,D){
  const BG=ev('big',4.0), AR=ev('area',9.7);
  rims(CY,GO,4); look(0,0.4,9.5,0,0.3,0); const o=ss(0,0.6,u);
  const a=hp(-2.0,0.4,9.5), b=hp(2.0,0.4,9.5); const s=lerp(1.0,1.066,ss(BG,BG+1.0,u));
  showBall(BL.tennis,a,0.9,o,u*0.3); BL.fuzz(a,0.9,1,o);
  showBall(BL.tennis2,b,0.9*s,o,u*0.3);
  const r1=rg(); r1.position.copy(a); r1.rotation.set(0,0,0); r1.scale.setScalar(0.9*1.02); r1.material.opacity=0.6*ss(AR,AR+0.5,u);
  const r2=rg(); r2.position.copy(b); r2.rotation.set(0,0,0); r2.scale.setScalar(0.9*s*1.02); r2.material.opacity=0.8*ss(AR,AR+0.5,u);
  lab('itA',T('标准球（2 号）','standard ball (type 2)'),-2.0,-1.0,o,{size:0.32}); lab('itB',T('3 号球：大约 6%，重量不变','type 3: about 6% bigger, same weight'),2.0,-1.0,ss(BG,BG+0.5,u),{size:0.32,color:'#ffd27a',glow:GOLD});
  lab('itC',T('给快场地、海拔 1219 米以上用','for fast courts and altitude above 1,219 m'),2.0,-1.55,ss(BG+1.0,BG+1.5,u),{size:0.28,color:'#aab8c8'});
  lab('itD',T('迎风面积大了 → 阻力大了 → 球慢了','bigger frontal area → more drag → slower ball'),0,2.4,ss(AR,AR+0.5,u),{size:0.36});
}

// ---------- 9 结论 ＋ 问句 ----------
function shotEnd(u,D){
  const SL=ev('slow',5.9), QQ=ev('q',10.7);
  rims(PJ,CY,5); const a=0.3+u*0.03; look(Math.sin(a)*6,0.4,Math.cos(a)*6,0,0,0);
  const c=V(0,0,0); FLOW.draw(c,1.1,118,0.2,1-ss(QQ-0.5,QQ,u),u,0x9fd8ff,0.45,0.25); showBall(BL.tennis,c,1.1,1,u*0.4); BL.fuzz(c,1.1,1.4,1);
  const t=bt('ndT',T('网球的毛：刹车，也是稳定器','The fuzz: a brake, and a stabiliser'),{size:0.85,glow:'rgba(214,238,58,0.45)',fx:'particles'}); hud(t,0,2.3,9); t.update(u,0.5,QQ-0.4,0.8);
  const q=bt('ndQ',T('你发球前，会挑毛不蓬的那一颗吗？','Before you serve, do you pick the tight one?'),{size:0.75,glow:'rgba(79,227,255,0.45)',fx:'particles'}); hud(q,0,-2.0,9); q.update(u,QQ,D+5,0.82);
}

const SHOTS={hook:shotHook,eiffel:shotEiffel,layer:shotLayer,golf:shotGolf,football:shotFootball,tennis:shotTennis,fluff:shotFluff,itf:shotItf,end:shotEnd};
function shotTest(u,D){ look(0,0,8,0,0,0); }
