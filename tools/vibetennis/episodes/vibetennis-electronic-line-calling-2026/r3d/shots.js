// 镜头表。时间轴按秒（BGM 未定，不卡节拍）。每段对应提纲 specs/vibetennis/drafts/…outline.md 的一行。
const ease=x=>{x=Math.min(1,Math.max(0,x)); return x*x*(3-2*x);};
const easeIO=x=>{x=Math.min(1,Math.max(0,x)); return x<0.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;};
const ramp=(x,a,b)=>ease((x-a)/(b-a));
const lerp=(a,b,u)=>a+(b-a)*u;
function path(S,keys,u){ const pts=keys.map(k=>new S.THREE.Vector3(...k)); return new S.THREE.CatmullRomCurve3(pts,false,'centripetal').getPoint(Math.min(1,Math.max(0,u))); }
function fadeIO(S,lt,d,a=0.5,b=0.5){ S.finalPass.uniforms.uFade.value=Math.max(0,Math.min(1,lt/a,(d-lt)/b)); }
const LAB=y=>y+1000;

export const SHOTS=[]; const add=(t0,t1,fn)=>SHOTS.push({t0,t1,fn});
export const SECT=[[0,15],[15,35],[35,60],[60,85],[85,110],[110,130],[130,155],[155,180],[180,200],[200,222],[222,236],[236,244]];
export const TOTAL=244;

// ===== S1 回放：电视转播的回放画面 → 冻结 → 扫描线 → 全息线框 =====
add(0,6,(S,lt,d)=>{
  const tb=0.30+lt*0.14; S.setBall(Math.min(tb,1.6),1,0.18,0.06);
  S.surfMat.color.setHex(0x1b5aa0); S.surfMat.opacity=0.95; S.baseStripMat.opacity=1; S.finalPass.uniforms.uTV.value=0.55; S.bloom.strength=0.35; S.coneMat.uniforms.uOp.value=0.08;
  const u=easeIO(lt/d); S.cam(path(S,[[9,7,S.L-9],[6,4.5,S.L-5],[3.2,2.2,S.L-1.8]],u),path(S,[[-1,0.4,S.L-6],[-1.2,0.2,S.L-2],[S.LAND.x,0.05,S.LAND.z]],u),42);
  if(tb>=S.TB){ const a=ramp(tb,S.TB,S.TB+0.05); S.replayFoot.material.opacity=0.95*a; S.replayFootRim.material.opacity=a; S.hitFlare.position.copy(S.LAND); S.hitFlare.material.opacity=Math.max(0,1-(tb-S.TB)*6)*1.5; S.hitFlare.scale.setScalar(0.5); }
  S.proj('ball',S.ball.position); S.proj('land',S.LAND); fadeIO(S,lt,d,0.6,0.01);
});
add(6,15,(S,lt,d)=>{
  const frozen=lt<4.6;
  S.replayFoot.material.opacity=frozen?0.95:0.25; S.replayFootRim.material.opacity=1; S.baseStripMat.opacity=frozen?1:0.55;
  if(frozen){ S.surfMat.color.setHex(0x1b5aa0); S.surfMat.opacity=0.95; S.finalPass.uniforms.uTV.value=0.55; S.bloom.strength=0.35; S.coneMat.uniforms.uOp.value=0.08; }
  if(lt>3.8&&lt<4.6) S.finalPass.uniforms.uGlitch.value=ramp(lt,3.8,4.3)*(1-ramp(lt,4.45,4.6));
  if(lt>=4.6&&lt<6.4) S.finalPass.uniforms.uScan.value=1-(lt-4.6)/1.8;
  if(lt>=4.6){ S.setCams(ramp(lt,6.0,8.0),0); }
  const u=easeIO(Math.max(0,(lt-4.8)/(d-4.8)));
  const pos=lt<4.6?S.V(S.LAND.x+0.55,0.32,S.LAND.z+0.75):path(S,[[S.LAND.x+0.55,0.32,S.LAND.z+0.75],[4,6,S.L+8],[14,16,S.L+22]],u);
  const tgt=lt<4.6?S.V(S.LAND.x,0.0,S.LAND.z-0.05):path(S,[[S.LAND.x,0,S.LAND.z-0.05],[0,0,S.L*0.4],[0,0,0]],u);
  S.cam(pos,tgt,lt<4.6?32+lt*0.6:40);
  S.proj('land',S.LAND); S.proj('lineEdge',S.V(S.LAND.x-0.15,0.01,S.L-0.05)); S.val('frozen',frozen?1:0);
});

// ===== S2 相机：12 台相机亮起 → 视锥 → 越过一台相机看球 =====
add(15,28,(S,lt,d)=>{
  S.setCams(i=>ramp(lt,0.6+i*0.35,1.0+i*0.35), ramp(lt,6.5,8.5));
  const a=lt/d*Math.PI*0.55-0.6; const r=lerp(52,44,lt/d);
  S.cam(S.V(r*Math.sin(a),lerp(30,24,lt/d),r*Math.cos(a)),S.V(0,2,0),46);
  S.CAMPOS.forEach((p,i)=>S.proj('cam'+i,p)); fadeIO(S,lt,d,0.4,0.3);
});
add(28,35,(S,lt,d)=>{
  S.setCams(1,0.35); const tb=0.15+((lt*0.32)%0.85); S.setBall(tb,1,0.1,0.06);
  const c=S.CAMPOS[3]; const eye=c.clone().add(S.V(3.2,2.4,3.6)); S.camRigs[3].lens.material.opacity=0.25;
  S.cam(eye,S.ball.position.clone().lerp(S.V(0,0,0),0.35),38);
  S.proj('ball',S.ball.position); S.proj('cam3',c); fadeIO(S,lt,d,0.3,0.3);
});

// ===== S3 三角定位：先是一双眼睛 → 12 条视线交会 → 一帧一个点 → 轨迹 =====
add(35,43,(S,lt,d)=>{
  S.eyes.visible=true; S.tennis.visible=false; S.rigGroup.visible=false; S['cones'].visible=false;
  const u=easeIO(lt/d); S.cam(S.V(lerp(0.46,0.36,u),300+lerp(0.16,0.12,u),lerp(0.34,0.24,u)),S.V(-0.02,299.97,-0.2),40);
  S.eyeRays.forEach((r,i)=>r.material.opacity=0.35*ramp(lt,1.0+i*0.5,1.8+i*0.5)); S.eyeFlows.forEach((r,i)=>r.material.opacity=0.95*ramp(lt,1.0+i*0.5,1.8+i*0.5)); S.eyeHit.material.opacity=ramp(lt,2.6,3.2);
  S.proj('eyeL',S.V(-0.032,300,0)); S.proj('cup',S.cupP.clone().add(S.V(0,300.05,0))); fadeIO(S,lt,d,0.5,0.4);
});
add(43,60,(S,lt,d)=>{
  S.setCams(1,0.15);
  const TBf=0.55, frames=24;
  const freeze=lt<7.5; const tb=freeze?TBf:Math.min(S.TB+0.3,TBf+(lt-7.5)*0.09);
  S.setBall(tb,1,freeze?0:0.08,0.06);
  // rays: 2 → 3 → all 12
  const nR=lt<2?2:(lt<3.5?3:12);
  S.camRigs.forEach((c,i)=>{ const show=i<nR?ramp(lt,i<2?0.3:(i<3?2.0:3.5),(i<2?0.9:(i<3?2.5:4.4))):0; S.setRay(c,S.ball.position.clone(),show*(freeze?1:Math.max(0.15,1-(lt-7.5)*0.4))); });
  S.hitFlare.position.copy(S.ball.position); S.hitFlare.material.opacity=freeze?ramp(lt,0.9,1.4)*1.2:0.6; S.hitFlare.scale.setScalar(1.6);
  if(!freeze){ const n=Math.min(frames,Math.floor((tb-0.0)/((S.TB)/frames))+1); const pts=[]; for(let i=0;i<n;i++) pts.push(S.traj(i*S.TB/frames)); S.ghostGroup&&0; S.setGhosts(pts,0.07,0.9); }
  else S.setGhosts([],0,0);
  if(lt>13){ const pts=[]; for(let i=0;i<=80;i++) pts.push(S.traj(i/80*S.TB)); S.trajLine.visible=true; S.setLine(S.trajLine,pts); S.trajLine.material.opacity=ramp(lt,13,14.5); }
  const a=0.9+lt*0.03; S.cam(S.V(22*Math.sin(a),lerp(13,10,lt/d),22*Math.cos(a)-2),S.V(-1.5,1.6,0),44);
  S.proj('ball',S.ball.position); S.val('nrays',nR); S.val('ghosts',freeze?0:1); fadeIO(S,lt,d,0.4,0.4);
});

// ===== S4 拍得到吗：340 帧/秒的残影，帧间 16.3 cm；触地 4.7 ms 只有一两帧 =====
add(60,85,(S,lt,d)=>{
  S.lab.visible=true; S.tennis.visible=false; S.rigGroup.visible=false; S.strobe.visible=true; S.labBall.visible=false; S.fuzz.visible=false;
  S.groundU.uGridOp.value=1; const n=Math.min(13,Math.floor(lt*1.6)+1); const step=16.3;
  S.strobeBalls.forEach((m,i)=>{ const x=-180+i*step; const y=S.R+Math.max(0,(-x)*0.06)*0+ (i<11?Math.max(0,(10-i))*1.2:0); m.position.set(x,y,0); m.visible=i<n; m.material.opacity=i===n-1?0.95:0.35; });
  S.strobeGap.forEach((l,i)=>{ if(i<n-1){ const a=S.strobeBalls[i].position, b=S.strobeBalls[i+1].position; S.setLine(l,[a.clone().add(S.V(0,S.R+2,0)),b.clone().add(S.V(0,S.R+2,0))]); l.material.opacity=0.8; } });
  const u=easeIO(Math.max(0,(lt-10)/8));
  S.cam(path(S,[[-90,LAB(40),190],[-60,LAB(30),150],[-14,LAB(9),48]],u),path(S,[[-90,LAB(8),0],[-70,LAB(6),0],[-20,LAB(3),0]],u),46);
  if(n>=2){ S.proj('g0',S.strobeBalls[n-2].position.clone().add(S.V(0,S.R+2,0)),S.lab); S.proj('g1',S.strobeBalls[n-1].position.clone().add(S.V(0,S.R+2,0)),S.lab); }
  S.proj('contact',S.V(-180+12*step,0,0),S.lab); S.val('n',n); fadeIO(S,lt,d,0.4,0.4);
});

// ===== S5 脚印：竖直落下压出约 4.2 cm 的接触面 → 斜着落地滑出约 10 cm → 系统画的是推算的 =====
add(85,96,(S,lt,d)=>{
  S.lab.visible=true; S.tennis.visible=false; S.rigGroup.visible=false; S.groundU.uGridOp.value=1;
  const cmax=0.74; let c=0, y=S.R;
  if(lt<3) y=S.R+lerp(14,0,easeIO(lt/3)); else if(lt<8){ const k=(lt-3)/5; c=cmax*Math.sin(Math.PI*Math.min(1,k*1.25)); y=S.R-c; } else { y=S.R+lerp(0,10,easeIO((lt-8)/3)); }
  S.labBall.position.set(0,y,0); S.fuzz.position.set(0,y,0); S.labBallU.uFloor.value=-y; S.labBallU.uBulge.value=c*0.12;
  const a=Math.sqrt(Math.max(0,2*S.R*c-c*c)); if(a>0.05){ S.contactRing.scale.set(a,1,a); S.contactRing.material.opacity=1; }
  if(lt>=5&&lt<8){ S.contactRing.scale.set(2.1,1,2.1); S.contactRing.material.opacity=1; }
  S.cam(S.V(lerp(10,7,lt/d),LAB(lerp(4,6,lt/d)),lerp(20,16,lt/d)),S.V(0,LAB(2),0),36);
  S.proj('ringL',S.V(-2.1,0,0),S.lab); S.proj('ringR',S.V(2.1,0,0),S.lab); S.val('cr',a); S.val('phase',lt>=5&&lt<8?1:0); fadeIO(S,lt,d,0.4,0.3);
});
add(96,110,(S,lt,d)=>{
  S.lab.visible=true; S.tennis.visible=false; S.rigGroup.visible=false;
  const slow=6.0; const tms=Math.min(4.72,Math.max(0,(lt-1.5)/slow*4.72)); const before=lt<1.5;
  const X0=-5, v=2.1, cmax=0.82; let x,y,c=0;
  if(before){ const k=lt/1.5; x=X0-lerp(30,0,k); y=S.R+lerp(30*Math.tan(17.7*Math.PI/180),0,k); }
  else if(tms<4.72){ x=X0+v*tms; c=cmax*Math.sin(Math.PI*tms/4.72); y=S.R-c; }
  else { const k=(lt-1.5-slow); x=X0+v*4.72+k*12; y=S.R+k*4; }
  S.labBall.visible=lt<10; S.fuzz.visible=lt<10; S.labBall.position.set(x,y,0); S.fuzz.position.set(x,y,0); S.labBallU.uFloor.value=-y; S.labBallU.uBulge.value=c*0.12;
  S.groundU.uFoot.value=1; S.groundU.uT.value=before?-1:tms; S.groundU.uFootX0.value=X0; S.groundU.uFootV.value=v; S.groundU.uFootC.value=cmax;
  if(lt>10.5){ S.sysEllipse.position.set(X0+5.0,0,0); S.sysEllipse.material.opacity=ramp(lt,10.5,11.5); S.groundU.uFoot.value=1-0.45*ramp(lt,10.5,11.5); }
  const u=easeIO(lt/d); S.cam(path(S,[[-14,LAB(6),22],[-4,LAB(10),20],[2,LAB(26),14]],u),path(S,[[-6,LAB(1.5),0],[-1,LAB(1),0],[0,LAB(0),0]],u),38);
  S.proj('fpStart',S.V(X0-2,0,0),S.lab); S.proj('fpEnd',S.V(X0+v*4.72+2,0,0),S.lab); S.proj('sys',S.V(X0+5,0,2.6),S.lab); S.val('tms',tms); fadeIO(S,lt,d,0.3,0.4);
});

// ===== S6 球印：红土偏大、硬地偏小 → 法网还在看球印 =====
add(110,130,(S,lt,d)=>{
  S.lab.visible=true; S.tennis.visible=false; S.rigGroup.visible=false; S.labBall.visible=false; S.fuzz.visible=false;
  S.bloom.strength=0.3; S.groundU.uSplit.value=ramp(lt,0,1.5); S.groundU.uMarks.value=ramp(lt,2.0,3.5); S.markTrue.forEach(m=>m.material.opacity=ramp(lt,4,5));
  if(lt>14){ S.inspect.material.opacity=ramp(lt,14,15)*(0.75+0.25*Math.sin(lt*6)); }
  const u=easeIO(Math.max(0,(lt-13)/6));
  S.cam(path(S,[[0,LAB(44),20],[0,LAB(30),26],[0,LAB(16),24]],u),path(S,[[0,LAB(0),0],[0,LAB(0),3],[0,LAB(0),9]],u),40);
  S.proj('clay',S.V(0,0,9),S.lab); S.proj('hard',S.V(0,0,-9),S.lab); S.proj('clayEdge',S.V(6.3,0,9),S.lab); S.proj('hardEdge',S.V(3.6,0,-9),S.lab); fadeIO(S,lt,d,0.4,0.4);
});

// ===== S7 精度：刻度尺；2.6 mm；离线 5 mm 以外 100%；0.15 s =====
function rulerView(S,lt,d,zones,human,hs){
  S.lab.visible=true; S.tennis.visible=false; S.rigGroup.visible=false; S.labBall.visible=false; S.fuzz.visible=false; S.ruler.visible=true;
  S.groundU.uLine.value=1; S.groundU.uLineX.value=0; S.groundU.uZones.value=zones; S.groundU.uHuman.value=human; S.groundU.uHumanS.value=hs;
  S.groundU.uFoot.value=1; S.groundU.uT.value=4.72; S.groundU.uFootX0.value=-3.0; S.groundU.uFootV.value=1.6; S.groundU.uFootC.value=0.82;
  S.bloom.strength=0.35; S.proj('edge',S.V(0,0,6),S.lab); S.proj('edgeTop',S.V(0,0,-4),S.lab); S.proj('z5',S.V(0.5,0,-4),S.lab); S.proj('z100',S.V(10,0,-4),S.lab); S.proj('zm100',S.V(-10,0,-4),S.lab); S.proj('r26',S.V(0.26,0,6),S.lab);
}
add(130,155,(S,lt,d)=>{
  rulerView(S,lt,d,ramp(lt,9,11),0,1.4);
  const u=easeIO(lt/d); S.cam(path(S,[[4,LAB(44),30],[2,LAB(40),26],[0,LAB(40),24]],u),S.V(0.5,LAB(0),1.0),40); fadeIO(S,lt,d,0.4,0.3);
});
// ===== S8 人眼：司线不确定度 1.4 → 3.2 cm =====
add(155,180,(S,lt,d)=>{
  const hs=lt<9?1.4:lerp(1.4,3.2,ramp(lt,9,11)); rulerView(S,lt,d,0.55,ramp(lt,1,2.5),hs);
  S.cam(S.V(0,LAB(44),26),S.V(0,LAB(0),0.5),40); S.val('hs',hs); fadeIO(S,lt,d,0.3,0.4);
});

// ===== S9 局限：5 mm 容差 → 1 mm 不平（放大示意）→ 绒毛先碰地 =====
add(180,187,(S,lt,d)=>{ rulerView(S,lt,d,1,0,1.4); S.groundU.uFoot.value=0; S.cam(S.V(0,LAB(40),24),S.V(0,LAB(0),0),36); fadeIO(S,lt,d,0.3,0.3); });
add(187,194,(S,lt,d)=>{
  S.lab.visible=true; S.tennis.visible=false; S.rigGroup.visible=false; S.bump.visible=true; S.labBall.visible=false; S.fuzz.visible=false;
  const ang=15*Math.PI/180, h=0.6, shift=h/Math.tan(ang);
  const pa=[S.V(-40,S.R+40*Math.tan(ang),0),S.V(0,S.R,0)], pb=[S.V(-40,S.R+40*Math.tan(ang),0),S.V(-shift,S.R+h,0)];
  S.bump.position.set(-shift-7+0.0,h/2,0); S.bump.scale.set(1,1,1); S.bump.position.x=-7-shift+7-7; // patch spans x∈[-14-shift..−shift]
  S.bump.position.x=-shift-7;
  S.setLine(S.pathA,pa); S.setLine(S.pathB,pb); S.pathA.material.opacity=ramp(lt,0.5,1.5); S.pathB.material.opacity=ramp(lt,2,3);
  S.dotA.position.set(0,0.05,0); S.dotA.material.opacity=ramp(lt,0.8,1.5); S.dotB.position.set(-shift,h+0.05,0); S.dotB.material.opacity=ramp(lt,2.4,3);
  S.cam(S.V(-12,LAB(12),56),S.V(-12,LAB(3),0),34);
  S.proj('dotA',S.V(0,0,0),S.lab); S.proj('dotB',S.V(-shift,h,0),S.lab); fadeIO(S,lt,d,0.3,0.3);
});
add(194,200,(S,lt,d)=>{
  S.lab.visible=true; S.tennis.visible=false; S.rigGroup.visible=false;
  const y=S.R+lerp(0.9,0.22,easeIO(lt/3.5)); S.labBall.position.set(0,y,0); S.fuzz.position.set(0,y,0); S.labBallU.uFloor.value=-y;
  S.fuzzTouch.position.set(0,0.05,0); S.fuzzTouch.material.opacity=lt>3?ramp(lt,3,3.5)*(0.7+0.3*Math.sin(lt*10)):0;
  S.cam(S.V(9,LAB(2.4),14),S.V(0,LAB(1.6),0),30);
  S.proj('fibre',S.V(0,0,0),S.lab); S.proj('ballEdge',S.V(0,0.25,0),S.lab); fadeIO(S,lt,d,0.3,0.4);
});

// ===== S10 人还剩什么：空着的司线椅 → 脚误相机与按钮 → 半边相机误关 → 主裁 =====
add(200,206,(S,lt,d)=>{
  S.chairs.visible=true; S.setCams(1,0);
  const u=easeIO(lt/d); S.cam(path(S,[[-S.DW-6,2.2,S.L+8],[-S.DW-4,1.6,S.L+5.5]],u),S.V(-S.DW-1.8,0.5,S.L+3.2),40);
  S.proj('ljChair',S.V(-S.DW-1.8,1.0,S.L+3.2)); fadeIO(S,lt,d,0.4,0.3);
});
add(206,214,(S,lt,d)=>{
  S.chairs.visible=true; S.setCams(0.35,0); S.ffGroup.visible=true; S.btn.material.opacity=0.5+0.5*Math.abs(Math.sin(lt*3));
  S.ffRays.forEach((r,i)=>r.material.opacity=0.7*ramp(lt,0.3+i*0.15,0.8+i*0.15));
  const u=easeIO(lt/d); S.cam(path(S,[[-S.DW-14,7,S.L+20],[-6,5,S.L+16]],u),S.V(-3,0.5,S.L+1),44);
  S.proj('ff',S.V(0,0.6,S.L+5.5)); S.proj('booth',S.V(-S.DW-12,4,S.L+10)); fadeIO(S,lt,d,0.3,0.3);
});
add(214,222,(S,lt,d)=>{
  S.chairs.visible=true; const off=S.CAMPOS.map(p=>p.x<0);
  S.setCams(i=>off[i]?1-ramp(lt,0.4+i*0.18,0.7+i*0.18):1, 0.1);
  const outLand=S.V(-2.0,S.BR,S.L+0.55); const f=tb=>{ const P0=S.V(-2.4,1.0,-S.L-1.0); const T=1.05; if(tb<T){ const u=tb/T, s=u*(1.18-0.18*u); return S.V(P0.x+(outLand.x-P0.x)*s,P0.y*(1-s)+S.BR*s+4*1.55*s*(1-s),P0.z+(outLand.z-P0.z)*s);} const u=Math.min(1,(tb-T)/0.55); return S.V(outLand.x-0.5*u,S.BR+1.8*Math.sin(Math.PI*0.62*u),outLand.z+5*u); };
  if(lt>2.5&&lt<5.4){ S.setBall((lt-2.5)*0.55,1,0.12,0.06,f); }
  S.umpGlow.material.opacity=lt>5.4?ramp(lt,5.4,6)*(0.7+0.3*Math.sin(lt*5)):0;
  S.cam(S.V(22,15,S.L+16),S.V(0,0.5,S.L*0.3),44);
  S.proj('ump',S.V(S.DW+1.4,2.4,0)); S.proj('out',outLand); fadeIO(S,lt,d,0.3,0.4);
});

// ===== S11 收束 + 参考页 =====
add(222,236,(S,lt,d)=>{
  S.setCams(i=>ramp(lt,0.2+i*0.12,0.6+i*0.12),ramp(lt,2,4)*0.4);
  const u=easeIO(lt/d); S.cam(path(S,[[30,18,40],[10,60,60],[0,120,40]],u),S.V(0,0,0),44);
  S.finalPass.uniforms.uFade.value=Math.min(ramp(lt,0,0.4),1-0.55*ramp(lt,3,6));
});
add(236,244.5,(S,lt,d)=>{
  S.setCams(1,0.4); const a=lt*0.03; S.cam(S.V(120*Math.sin(a),130,120*Math.cos(a)),S.V(0,0,0),44);
  S.finalPass.uniforms.uFade.value=0.25*Math.min(1,(d-lt)/1.0);
});

// ===== 封面专用（t=300，在成片时间轴之外）：低机位贴着底线，12 条视线汇聚到将要落地的球，地上一个压线的脚印 =====
add(300,301,(S,lt,d)=>{
  S.setCams(1,0); S.baseStripMat.opacity=0.9;
  const tb=S.TB-0.035; S.setBall(tb,1,0.10,0.05);
  S.camRigs.forEach(c=>S.setRay(c,S.ball.position.clone(),0.85));
  S.hitFlare.position.copy(S.ball.position); S.hitFlare.material.opacity=0.35; S.hitFlare.scale.setScalar(0.45);
  S.cam(S.V(S.LAND.x+0.25,0.42,S.LAND.z+2.2),S.V(S.LAND.x+0.05,0.95,S.LAND.z-3.0),52);
  S.proj('ball',S.ball.position); S.proj('land',S.LAND);
});
// ===== 封面 C（许先森风，t=302）：高空斜俯整座球场，12 道视线在将落地的球上汇聚 =====
add(302,303,(S,lt,d)=>{
  S.setCams(1,0.25); S.coneMat.uniforms.uOp.value=0.32; S.bloom.strength=1.05;
  const tb=S.TB-0.06; S.setBall(tb,1,0.12,0.06);
  S.camRigs.forEach(c=>S.setRay(c,S.ball.position.clone(),0.9));
  S.hitFlare.position.copy(S.ball.position); S.hitFlare.material.opacity=0.7; S.hitFlare.scale.setScalar(2.2);
  S.cam(S.V(-26,30,S.L+30),S.V(-1.0,0,S.L-6),40);
});
