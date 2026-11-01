// 镜头表（秒）。设计与每个数字的出处：papers/vibetennis-federer-54-percent-2026/sources.md 第五节。
const ease=x=>{x=Math.min(1,Math.max(0,x)); return x*x*(3-2*x);};
const easeIO=x=>{x=Math.min(1,Math.max(0,x)); return x<0.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;};
const ramp=(x,a,b)=>ease((x-a)/(b-a));
const lerp=(a,b,u)=>a+(b-a)*u;
function fadeIO(S,lt,d,a=0.5,b=0.5){ S.finalPass.uniforms.uFade.value=Math.max(0,Math.min(1,a>0?lt/a:1,b>0?(d-lt)/b:1)); }
function hit(S,t,at,dur=0.45,shake=0.6,ring=S.shock,col=null,size=60){ const u=(t-at)/dur; if(u>=0&&u<1){ ring.material.opacity=(1-u)*0.5; ring.scale.setScalar(16+u*size); if(col) ring.material.color.copy(col); S.finalPass.uniforms.uShake.value=Math.max(S.finalPass.uniforms.uShake.value,(1-u)*shake); } }

export const SHOTS=[]; const add=(t0,t1,fn)=>SHOTS.push({t0,t1,fn});
// ---- 2026-11-01 改版：在标题后插一段「马尔可夫链是什么、他怎么发现的」，片尾换成金句（所有者：「缺少一个最后的金句」
//      「同时你没有简单介绍马尔可夫链是什么。以及是他是怎么发现的」）。旧镜头一帧不改，靠时间映射：
//      新时间轴 = 旧 [0,15.5) ＋ 新段 A（32.32 s）＋ 旧 [15.5,176.2) ＋ 新段 B（19.96 s，替掉旧 [176.2,180) 的问句）＋ 旧 [180,188)
//      插入长度取整小节（74 BPM、拍长 0.808 s、一小节 3.232 s）：A 10 小节，B 净增 5 小节 → 之后的画面仍在原来的拍上
export const WARP={A0:15.5,LA:42.02,B_OLD:176.2,B_DROP:3.8,LB:19.96};   // LA 2026-11-01 二改：32.32 → 42.02（＋291 帧＝9.7 s，补「马尔可夫链就三样东西」；整帧平移，旧渲染可直接复用）
export const OLD_TOTAL=188;
export const TOTAL=OLD_TOTAL+WARP.LA+WARP.LB-WARP.B_DROP;   // 236.48
export const B0=WARP.B_OLD+WARP.LA;                          // 新段 B 在新时间轴上的起点 208.52
export function toOld(t){ const w=WARP;
  if(t<w.A0) return t; if(t<w.A0+w.LA) return null; if(t<B0) return t-w.LA; if(t<B0+w.LB) return null; return t-w.LA-w.LB+w.B_DROP; }
export function toNew(t){ const w=WARP;   // 旧时间 → 新时间；被替掉的旧 [176.2,180) 返回 null
  if(t<w.A0) return t; if(t<w.B_OLD) return t+w.LA; if(t<w.B_OLD+w.B_DROP) return null; return t+w.LA+w.LB-w.B_DROP; }
export const NEWSHOTS=[]; const addN=(t0,t1,fn)=>NEWSHOTS.push({t0,t1,fn});
// 段落表（overlay 右上角章节标、sfx 用）
export const SECT=[[0,7],[7,15.5],[15.5,33],[33,64],[64,95],[95,117],[117,140],[140,164],[164,180],[180,188]];   // 旧时间轴

// ===== 0–7 开场：1526 颗星的星系 → 82% → 一颗星炸成「分」的尘埃 → 54% → 问句 =====
const OPEN=[[0,'void',0],[0.05,'galaxy',1.3,0.6],[2.45,'n82',1.0,1],[4.05,'dust54',0.45,1.4],[4.55,'n54',0.85,0.8],[6.6,'burst',0.5,1]];
add(0,7.0,(S,lt,d,t)=>{
  const tilt=lerp(1.05,0,ramp(t,2.45,3.3)); const spin=t<2.45?t*0.35:0.86+Math.sin(t*0.4)*0.08;
  S.setMorph(OPEN,t,{spin,tilt});
  S.cam(S.V(Math.sin(t*0.2)*2,1.2,lerp(64,50,easeIO(t/7))),S.V(0,0,0),40);
  S.gridMat.uniforms.uOp.value=0.4;
  hit(S,t,1.25,0.5,0.3); hit(S,t,3.35,0.5,0.6); hit(S,t,5.3,0.5,0.7,S.shock2);
  if(t>4.0&&t<4.6){ S.finalPass.uniforms.uZoom.value=Math.sin((t-4.0)/0.6*Math.PI)*1.2; }
  if(t>6.35) S.finalPass.uniforms.uGlitch.value=ramp(t,6.35,6.85);
  S.proj('num',S.V(0,0,0)); S.proj('numTop',S.V(0,7,0)); S.proj('numBot',S.V(0,-7,0));
  fadeIO(S,lt,d,0.2,0.0001);
});

// ===== 7–15.5 理论大标题：网球飞入 → 撞碎 → 拼出「马尔可夫链」→ 光爆转金 =====
const TITLE=[[0,'burst',0],[8.15,'ball',0.01,0],[8.25,'burst',0.75,1],[9.0,'title',1.7,1],[11.15,'titleGold',0.55,0],[14.9,'void',0.9,1]];
add(7.0,15.5,(S,lt,d,t)=>{
  S.skyMat.uniforms.uWarm.value=ramp(t,11.1,11.8)*0.8;
  S.gridMat.uniforms.uOp.value=0.3;
  if(t<8.2){ const u=easeIO((t-7.0)/1.2); const at=uu=>S.V(lerp(-60,0,uu),lerp(18,0,uu)+Math.sin(uu*Math.PI)*6,lerp(-260,0,uu)); const p=at(u);
    S.ball.visible=true; S.ball.position.copy(p); S.ball.scale.setScalar(4.2); S.ball.rotation.set(t*9,t*6,0);
    S.ballGlow.visible=true; S.ballGlow.position.copy(p); S.ballGlow.scale.setScalar(14); S.ballGlow.material.opacity=0.3;
    S.ballTrail.visible=true; const tail=at(Math.max(0,u-0.18)); S.setLine(S.ballTrail,[tail,p]); S.ballTrail.material.opacity=0.8;
  } else S.setMorph(TITLE,t,{spin:t<11?Math.sin((t-8.2)*0.8)*0.25*(1-ease((t-9)/2)):0});
  const ui=(t-8.18)/0.5; if(ui>=0&&ui<1){ S.finalPass.uniforms.uFlash.value=(1-ui)*0.4; S.shock2.material.opacity=(1-ui); S.shock2.scale.setScalar(10+ui*90); S.shock2.position.set(0,0,0); S.finalPass.uniforms.uShake.value=(1-ui)*1.2; }
  const ug=(t-11.1)/1.6; if(ug>=0){ S.setRays(Math.max(0,(1-ug*0.6))*(ug<0.15?ug/0.15:1),1+ug*0.3); S.flare.material.opacity=Math.max(0,1-ug*1.6)*0.4; S.flare.position.set(0,0,-3); S.flare.scale.setScalar(60+ug*40); if(ug<0.35) S.finalPass.uniforms.uFlash.value=Math.max(S.finalPass.uniforms.uFlash.value,(0.35-ug)*0.45); }
  S.bloom.strength=t>11.1?0.55:0.45;
  const pull=easeIO((t-7)/8.5); S.cam(S.V(Math.sin(t*0.25)*2.5,lerp(4,1.2,pull),lerp(70,52,pull)),S.V(0,0.5,0),38);
  S.proj('title',S.V(0,0,0)); S.proj('titleBot',S.V(0,-7,0));
  fadeIO(S,lt,d,0.0001,0.6);
});

// ===== 15.5–33 一分：全息天平 =====
add(15.5,33,(S,lt,d,t)=>{
  const n=Math.pow(clamp((t-17.2)/7.5),1.35)*100;
  let wn=0, ln=0; for(let i=0;i<100;i++){ const di=S.SC.drop.indexOf(i); if(n-di>=1){ if(i<54) wn++; else ln++; } }
  const tilt=-((wn-ln)/Math.max(1,wn+ln))*0.5*ease((n-3)/10);   // 倾角 ∝ (赢-输)/总数：100 分时只有 2.3°
  S.setScale(1,n,tilt,t,ramp(t,25.8,26.6));
  S.SC.coin.position.set(26,16,0);
  const u=easeIO(lt/d); S.cam(S.V(lerp(-14,10,u),lerp(10,14,u),lerp(54,50,u)),S.V(2,11,0),40);
  S.grid.position.y=0; S.gridMat.uniforms.uOp.value=0.7;
  S.val('won',wn); S.val('lost',ln); S.val('tiltDeg',Math.abs(tilt)*180/Math.PI);
  S.proj('panL',S.SC.pans[0].pan.position.clone().add(S.V(0,1,0)),null); S.proj('panR',S.SC.pans[1].pan.position.clone().add(S.V(0,1,0)),null);
  S.proj('beam',S.V(0,16,0)); S.proj('coin',S.V(26,16,0)); S.proj('scaleTop',S.V(0,24,0));
  fadeIO(S,lt,d,0.6,0.5);
});
function clamp(x){ return Math.min(1,Math.max(0,x)); }

// ===== 33–64 一局：比分河道 =====
add(33,64,(S,lt,d,t)=>{
  const r=S.setChain(S.GAME,1,t-44,{spawn:0.012,stepDur:0.28,graphOp:ramp(t,33.3,36.5)});
  S.val('gw',r.w); S.val('gl',r.l); S.val('gn',S.GAME.N);
  const a=easeIO((t-33)/8), b=easeIO((t-44)/14);
  S.cam(S.V(lerp(8,0,a)+lerp(0,-6,b),lerp(14,4,a)+lerp(0,-3,b),lerp(18,62,a)+lerp(0,4,b)),S.V(0,lerp(14,0.5,a)+lerp(0,-0.5,b),0),42);
  S.gridMat.uniforms.uOp.value=0.25;
  const G=S.GAME, N=k=>G.nodes.get(k).pos;
  for(const k of ['0,0','1,0','0,1','2,0','1,1','0,2','3,0','2,1','1,2','0,3','3,1','2,2','1,3','3,2','2,3','3,3','4,3','3,4']) S.proj('g'+k.replace(',','_'),N(k),G.g);
  S.proj('gWin',G.def.winPool,G.g); S.proj('gLose',G.def.losePool,G.g);
  S.proj('gWinTop',G.def.winPool.clone().add(S.V(0,G.def.poolH+1,0)),G.g); S.proj('gLoseTop',G.def.losePool.clone().add(S.V(0,G.def.poolH+1,0)),G.g);
  fadeIO(S,lt,d,0.6,0.5);
});

// ===== 64–95 套娃：一局缩成一盘的一步，一盘缩成一场的一步 =====
add(64,95,(S,lt,d,t)=>{
  // 64–68：一局的河道缩进「一盘」的 0-0 节点
  if(t<82.5){
    const sh=easeIO((t-64)/3.2); const s0=S.SET.nodes.get('0,0').pos.clone().add(S.SET.g.position);
    if(sh<1){ S.setChain(S.GAME,1-ease((t-66.2)/1.2),999,{spawn:0.012,stepDur:0.28,flowOp:0.6}); S.GAME.g.scale.setScalar(lerp(1,0.05,sh)); S.GAME.g.position.copy(S.V(0,15,0).lerp(s0,sh)); }
    if(t>65.6&&t<66.4) S.finalPass.uniforms.uZoom.value=Math.sin((t-65.6)/0.8*Math.PI)*0.9;
    const r=S.setChain(S.SET,1,t-69,{spawn:0.012,stepDur:0.17,graphOp:ramp(t,65.5,68)});
    S.val('sw',r.w); S.val('sl',r.l); S.val('sn',S.SET.N);
    const u=easeIO((t-64)/5); S.cam(S.V(lerp(0,-4,easeIO((t-69)/13)),lerp(10,4,u),lerp(30,64,u)),S.V(0,lerp(12,-1,u),0),42);
    const G=S.SET; S.proj('s0_0',G.nodes.get('0,0').pos,G.g); S.proj('s6_6',G.nodes.get('6,6').pos,G.g); S.proj('s5_5',G.nodes.get('5,5').pos,G.g);
    S.proj('sWinTop',G.def.winPool.clone().add(S.V(0,G.def.poolH+1,0)),G.g); S.proj('sLoseTop',G.def.losePool.clone().add(S.V(0,G.def.poolH+1,0)),G.g);
  } else {
    // 82.5–95：一盘缩进「一场」的 0-0 节点
    const sh=easeIO((t-82.5)/3); const m0=S.MATCH.nodes.get('0,0').pos.clone().add(S.MATCH.g.position);
    if(sh<1){ S.setChain(S.SET,1-ease((t-84.5)/1.0),999,{spawn:0.012,stepDur:0.17,flowOp:0.6}); S.SET.g.scale.setScalar(lerp(1,0.07,sh)); S.SET.g.position.copy(S.V(0,15,0).lerp(m0,sh)); }
    if(t>84&&t<84.8) S.finalPass.uniforms.uZoom.value=Math.sin((t-84)/0.8*Math.PI)*0.9;
    const r=S.setChain(S.MATCH,1,t-86.3,{spawn:0.0095,stepDur:0.34,graphOp:ramp(t,83.8,86)});
    S.val('mw',r.w); S.val('ml',r.l); S.val('mn',S.MATCH.N);
    const u=easeIO((t-82.5)/4); S.cam(S.V(lerp(-4,3,easeIO((t-86)/9)),lerp(4,3,u),lerp(64,58,u)),S.V(0,-1,0),42);
    const G=S.MATCH; S.proj('m0_0',G.nodes.get('0,0').pos,G.g); S.proj('mWinTop',G.def.winPool.clone().add(S.V(0,G.def.poolH+1,0)),G.g); S.proj('mLoseTop',G.def.losePool.clone().add(S.V(0,G.def.poolH+1,0)),G.g);
  }
  S.gridMat.uniforms.uOp.value=0.25;
  fadeIO(S,lt,d,0.0001,0.5);
});

// ===== 95–117 放大曲线：全息 S 曲线 =====
add(95,117,(S,lt,d,t)=>{
  const u=easeIO(lt/d); S.cam(S.V(lerp(-8,6,u),lerp(16,14,u),lerp(52,48,u)),S.V(0,13,0),42);
  const draw=[ramp(t,96.8,98.4),ramp(t,99.0,100.6),ramp(t,101.2,102.8),ramp(t,103.4,105.0)];
  let p=null; if(t>=105.4) p=0.54; if(t>=108.6) p=lerp(0.54,0.50,easeIO((t-108.6)/1.2)); if(t>=110.6) p=lerp(0.50,0.51,easeIO((t-110.6)/1.4));
  S.setChart(ramp(t,95.2,96.4),draw,p,ramp(t,105.4,105.9));
  if(p!==null){ S.val('p',p); S.CURVES.forEach((c,i)=>{ S.val('cv'+i,c.f(p)); S.proj('cd'+i,S.V(S.chartX(p),S.chartY(c.f(p)),0.15),S.chart); }); S.proj('scanBot',S.V(S.chartX(p),0,0),S.chart); }
  S.CURVES.forEach((c,i)=>{ S.proj('cEnd'+i,c.pts[120],S.chart); });
  for(const v of [0.40,0.45,0.50,0.55,0.60]) S.proj('ax'+Math.round(v*100),S.V(S.chartX(v),-0.6,0),S.chart);
  for(const v of [0,0.5,1]) S.proj('ay'+Math.round(v*100),S.V(-S.CH.W/2-0.6,S.chartY(v),0),S.chart);
  S.grid.position.y=0; S.gridMat.uniforms.uOp.value=0.5;
  if(t>108.6&&t<109) S.finalPass.uniforms.uShake.value=0.3;
  fadeIO(S,lt,d,0.5,0.5);
});

// ===== 117–140 验证：模型 vs 真实（双影柱）。H：1 个百分点 = 0.26 =====
const HB=0.26;
const VAL=[ // [x, 模型, 真实]  模型＝资料包第三节；真实＝ATP / 罗兰·加洛斯 / UTS
  [-14,0.897,0.888], [0,0.256,0.266], [14,0.599,0.581] ];
add(117,140,(S,lt,d,t)=>{
  const u=easeIO(lt/d); S.cam(S.V(lerp(12,-8,u),lerp(18,16,u),lerp(62,58,u)),S.V(0,11,0),42);
  VAL.forEach(([x,m,r],i)=>{ const gg=ease((t-121.5-i*0.9)/1.0), dr=(t-126.5-i*1.5)/0.9;
    S.setBar(S.BARS[i],x,dr>0?r*100*HB:null,gg>0?m*100*HB*gg:null,gg>0?1:0,{w:5,t,drop:dr,col:S.GOLD});
    S.proj('vm'+i,S.V(x,m*100*HB*gg,0)); S.proj('vr'+i,S.V(x,r*100*HB,0)); S.proj('vb'+i,S.V(x,-1.4,0));
    const land=t-(126.5+i*1.5+0.9); if(land>0&&land<0.4){ S.finalPass.uniforms.uShake.value=Math.max(S.finalPass.uniforms.uShake.value,(0.4-land)*1.2); } });
  S.grid.position.y=-0.05; S.gridMat.uniforms.uOp.value=0.85;
  fadeIO(S,lt,d,0.6,0.5);
});

// ===== 140–164 局限：整场高估了 → 2019 温网决赛 =====
const CP=[[0,'void',0],[157.2,'cp',0.9,1],[160.8,'cpBurst',0.8,1.2]];
add(140,164,(S,lt,d,t)=>{
  if(t<148){
    S.cam(S.V(lerp(-6,4,easeIO((t-140)/8)),16,48),S.V(0,13,0),42); S.grid.position.y=-0.05; S.gridMat.uniforms.uOp.value=0.85;
    const gg=ease((t-140.4)/1.0), dr=(t-141.6)/0.9;
    S.setBar(S.BARS[3],0,dr>0?0.82*100*HB:null,gg>0?0.859*100*HB*gg:null,gg>0?1:0,{w:6,t,drop:dr,col:S.GOLD,gcol:t>143?S.RED:S.CYAN});
    S.proj('lm',S.V(0,0.859*100*HB*gg,0)); S.proj('lr',S.V(0,0.82*100*HB,0)); S.proj('lb',S.V(0,-1.4,0));
    fadeIO(S,lt,d,0.5,0.0001); if(t>147.5) S.finalPass.uniforms.uFade.value=Math.max(0,(148-t)/0.5);
  } else if(t<157){
    S.court.visible=true; S.skyMat.uniforms.uWarm.value=0.25;
    const u=easeIO((t-148)/9); S.cam(S.V(lerp(0,-6,u),lerp(30,20,u),lerp(44,40,u)),S.V(0,5,0),42); S.grid.position.y=-0.05; S.gridMat.uniforms.uOp.value=0.3;
    const n0=Math.round(218*easeIO((t-149.3)/3.6)), n1=Math.round(204*easeIO((t-149.3)/3.6));
    S.setVessels(1,n0,n1,ramp(t,153.6,154.4));
    S.val('p0',n0); S.val('p1',n1);
    S.proj('ves0',S.V(-10,15.5,-4)); S.proj('ves1',S.V(10,15.5,-4)); S.proj('ves0b',S.V(-10,-0.5,-4)); S.proj('ves1b',S.V(10,-0.5,-4));
    S.finalPass.uniforms.uFade.value=Math.min(1,(t-148)/0.6,(157-t)/0.3);
  } else {
    S.cam(S.V(0,1,lerp(54,44,easeIO((t-157)/7))),S.V(0,0,0),40); S.gridMat.uniforms.uOp.value=0.3;
    S.setMorph(CP,t,{op:1});
    hit(S,t,160.8,0.6,1.4,S.shock,S.RED,90); if(t>160.8&&t<161.4){ S.finalPass.uniforms.uFlash.value=(161.4-t)*0.25; S.finalPass.uniforms.uGlitch.value=(161.4-t)*1.0; }
    S.proj('cp',S.V(0,0,0)); S.proj('cpTop',S.V(0,7,0)); S.proj('cpBot',S.V(0,-7,0));
    S.finalPass.uniforms.uFade.value=Math.min(1,(t-157)/0.4,(164-t)/0.5);
  }
});

// ===== 164–180 收束：23.6 万分的星海 → 「这只是一分」 =====
const ONE=[[0,'void',0],[164.05,'sea',1.6,0.6],[168.2,'one',1.6,1],[178.2,'void',1.5,1]];
add(164,180,(S,lt,d,t)=>{
  const tilt=lerp(0.9,0,ramp(t,168.2,169.4)); const spin=t<168.2?(t-164)*0.18:0.76;
  S.setMorph(ONE,t,{spin:t<168.2?spin:0,tilt,offset:S.V(0,t<168.2?0:2.5,0)});
  S.skyMat.uniforms.uWarm.value=0.5*ramp(t,168.5,170)*(1-ramp(t,177.5,179));
  const ug=(t-170)/1.2; if(ug>=0&&ug<1.5){ S.setRays(Math.max(0,1-ug*0.7)*0.55,1+ug*0.2); S.flare.material.opacity=Math.max(0,1-ug*1.8)*0.5; S.flare.position.set(0,2.5,-3); S.flare.scale.setScalar(50); }
  S.cam(S.V(Math.sin(t*0.2)*2,t<168.2?lerp(40,8,easeIO((t-164)/4)):1.5,t<168.2?lerp(150,90,easeIO((t-164)/4)):lerp(58,62,easeIO((t-168)/12))),S.V(0,t<168.2?0:1.5,0),38);
  S.gridMat.uniforms.uOp.value=0.3;
  S.proj('one',S.V(0,2.5,0)); S.proj('oneBot',S.V(0,-4,0)); S.proj('seaC',S.V(0,0,0));
  fadeIO(S,lt,d,0.5,0.8);
});

// ===== 180–188 参考资料 =====
add(180,188,(S,lt,d,t)=>{
  S.cam(S.V(0,30,120),S.V(0,0,0),40); S.gridMat.uniforms.uOp.value=0.25; S.dust.material.uniforms.uOp.value=0.5;
  fadeIO(S,lt,d,0.6,0.6);
});

// ======================= 新段 A（新时间 15.5–57.52）：马尔可夫链是什么、他怎么发现的 =======================
// 出处：Seneta (2006)（1906 年论文为反驳涅克拉索夫「大数定律要求相互独立」而作）；
//      Markov (1913)，英译 Link (2006) Science in Context 19: 591–600（《奥涅金》前 20,000 字母：元音 8,638；元音后接元音 1104/8638=0.128；辅音后接元音 7534/11362=0.663）
const MA=[[0,'void',0],[0.15,'n1906',1.1,0.5],[3.4,'indep',1.4,0.6],[6.0,'links',1.8,0.5],[10.2,'onegin',1.8,0.6],[16.8,'twoNode',1.6,0.7],[35.6,'n00',1.2,0.5],[41.1,'void',0.9,1]];
addN(WARP.A0,WARP.A0+WARP.LA,(S,lt,d,t)=>{
  const u=lt;
  const spin=(u>=6&&u<10.2)?Math.sin((u-6)*0.55)*0.35:0;
  S.setMorph(MA,u,{spin,op:(u>=17.4&&u<35.6)?0.8:1});
  S.gridMat.uniforms.uOp.value=0.3; S.skyMat.uniforms.uWarm.value=0.25*ramp(u,10,11)*(1-ramp(u,16.5,17.5));
  // 镜头：1906 → 散点（稍拉远）→ 链条（环绕）→ 奥涅金（拉远放下整行）→ 两状态图 → 0-0
  let pos, tgt=S.V(0,0,0), fov=40;
  if(u<6) pos=S.V(Math.sin(u*0.3)*2,1.2,lerp(54,70,easeIO(u/6)));
  else if(u<10.2) pos=S.V(lerp(0,-10,easeIO((u-6)/4.2)),lerp(1.2,6,easeIO((u-6)/4.2)),lerp(70,62,easeIO((u-6)/4.2)));
  else if(u<16.8) pos=S.V(lerp(-10,0,easeIO((u-10.2)/1.6)),lerp(6,1,easeIO((u-10.2)/1.6)),lerp(68,78,easeIO((u-10.2)/1.4)));
  else if(u<35.6) pos=S.V(Math.sin((u-16.8)*0.15)*3,lerp(1,3,easeIO((u-16.8)/12)),lerp(78,68,easeIO((u-16.8)/3)));
  else pos=S.V(Math.sin(18.8*0.15)*3*(1-easeIO((u-35.6)/2)),lerp(3,4,easeIO((u-35.6)/3)),lerp(68,60,easeIO((u-35.6)/3)));
  S.cam(pos,tgt,fov);
  // 两状态图：粒子凝成两团（元音金 43.2% / 辅音蓝 56.8%）之后，边和令牌出现；令牌沿《奥涅金》开头真实的元音/辅音序列跳
  const mo=ramp(u,17.2,18.2)*(1-ramp(u,35.0,36.0));
  // 「马尔可夫链就三样东西」：25.3 状态（节点亮）→ 27.6 转移概率（边亮）→ 31.5 只看现在（令牌照跳，字母流里过去的变暗）
  const nodeHi=ramp(u,25.3,25.8)*(1-ramp(u,27.3,27.8)), edgeHi=ramp(u,27.6,28.1)*(1-ramp(u,31.2,31.7));
  const cur=S.setMK(mo,u-18.4,{hop:0.42,nodeHi,edgeHi});
  if(cur){ S.val('mkI',cur.i); S.val('mkU',cur.u); S.val('mkKey',cur.key); }
  S.val('mkOp',mo);
  hit(S,u,0.15,0.5,0.3); hit(S,u,6.0,0.5,0.3,S.shock2,null,40); hit(S,u,16.8,0.5,0.3); hit(S,u,35.6,0.45,0.4);
  S.proj('yr',S.V(0,0,0)); S.proj('yrBot',S.V(0,-6,0)); S.proj('links',S.V(0,0,0)); S.proj('lkBot',S.V(0,-5,0));
  S.proj('og',S.V(0,0,0)); S.proj('ogBot',S.V(0,-5.5,0));
  S.proj('mkV',S.MK_V); S.proj('mkC',S.MK_C); for(const k of ['VV','VC','CV','CC']) S.proj('mk'+k,S.MK_MID[k]);
  S.proj('n00',S.V(0,0,0)); S.proj('n00Bot',S.V(0,-6,0)); S.proj('n00L',S.V(-9,-3,0)); S.proj('n00R',S.V(9,-3,0));
  fadeIO(S,lt,d,0.5,0.6);
});

// ======================= 新段 B（新时间 208.52–228.48）：输掉的分 → 每局从 0-0 重来 → 金句 → 问句 =======================
// 108,336 = 236,038 − 127,702（UTS 生涯总分与赢分，资料包第一节）
const MB=[[0,'one',0],[0.5,'lost',2.2,0.8],[4.2,'void',1.6,0.6]];
addN(B0,B0+WARP.LB,(S,lt,d,t)=>{
  const u=lt, told=WARP.B_OLD+u;   // 开头几帧接着旧「这只是一分」的镜头
  const grow=1+0.6*easeIO((u-1.2)/3.6);
  S.setMorph(MB,u,{offset:S.V(0,lerp(2.5,0,easeIO((u-0.5)/2.2)),0),scale:u<4.2?grow:1,op:u<4.2?1:0.45*(1-ramp(u,10,11))+0.25,spin:u>0.5&&u<4.2?(u-0.5)*0.06:0});
  S.skyMat.uniforms.uWarm.value=0.5*(1-ramp(u,0.5,2.5))+0.45*ramp(u,10.2,11.2);
  S.gridMat.uniforms.uOp.value=0.3;
  // 0–4.2：镜头从旧问句那一帧接上，再慢慢退开，蓝色输分飘散
  if(u<4.2){ const z0=lerp(58,62,easeIO((told-168)/12)); S.cam(S.V(Math.sin(told*0.2)*2,lerp(1.5,3,easeIO(u/4.2)),lerp(z0,96,easeIO((u-0.4)/3.8))),S.V(0,lerp(1.5,0,easeIO(u/3)),0),38); }
  // 4.2–10.6：一局的比分河道，每一局都从 0-0 出发
  else if(u<10.6){ const a=easeIO((u-4.2)/6.4); S.cam(S.V(lerp(-4,-6,a),lerp(2,1,a),lerp(70,64,a)),S.V(0,lerp(2,0.5,a),0),42); }
  // 10.6–：金句，一颗球留在中间
  else { const a=easeIO((u-10.6)/9.4); S.cam(S.V(Math.sin(u*0.15)*1.5,lerp(2,1.4,a),lerp(46,38,a)),S.V(0,1,0),38); }
  const co=ramp(u,4.0,5.0)*(1-ramp(u,9.9,10.7));
  if(co>0.001){ S.setChain(S.GAME,co,u-4.4,{spawn:0.012,stepDur:0.28,graphOp:1});
    const p00=S.GAME.nodes.get('0,0').pos.clone().add(S.GAME.g.position);
    const k=((u-4.4)%1.4+1.4)%1.4/0.6; if(u>4.4&&k<1){ S.shock.material.opacity=(1-k)*0.6*co; S.shock.scale.setScalar(4+k*16); S.shock.position.copy(p00); S.shock.material.color.copy(S.WHITE); }
    S.proj('g00',S.GAME.nodes.get('0,0').pos,S.GAME.g); }
  const bo=ramp(u,10.3,11.3);
  if(bo>0.001){ S.ball.visible=true; S.ballMat.uniforms.uOp.value=bo*(1-0.45*ramp(u,15.6,17)); S.ball.position.set(0,1,0); S.ball.scale.setScalar(2.6*S.easeOutBack(ramp(u,10.3,11.4))+0.001); S.ball.rotation.set(u*0.35,u*0.5,0);
    S.ballGlow.visible=true; S.ballGlow.position.set(0,1,0); S.ballGlow.scale.setScalar(13); S.ballGlow.material.opacity=0.28*bo;
    const ug=(u-10.4)/1.4; if(ug>=0&&ug<1.6){ S.setRays(Math.max(0,1-ug*0.7)*0.35,1+ug*0.2); } }
  hit(S,u,10.4,0.5,0.25);
  S.proj('lostC',S.V(0,0,0)); S.proj('ballC',S.V(0,1,0)); S.proj('ballTop',S.V(0,5,0)); S.proj('ballBot',S.V(0,-3,0));
  fadeIO(S,lt,d,0.0001,0.8);
});

// ===== 封面底图（不进正片；node still.js 300 302，W/H 按封面尺寸给） =====
add(300,301,(S,lt,d,t)=>{   // A：S 曲线全息图
  const asp=window.innerWidth/window.innerHeight;
  if(asp<1) S.cam(S.V(0,22,104),S.V(0,21,0),42); else S.cam(S.V(-4,14,52),S.V(0,14,0),40);
  S.setChart(1,[1,1,1,1],0.54,1); S.grid.position.y=0; S.gridMat.uniforms.uOp.value=0.5;
  S.CURVES.forEach((c,i)=>S.proj('cEnd'+i,c.pts[120],S.chart));
});
add(302,303,(S,lt,d,t)=>{   // C：比分河道大场面（粒子在流、水库半满）
  const asp=window.innerWidth/window.innerHeight;
  if(asp<1) S.cam(S.V(0,-3,104),S.V(0,6,0),44); else S.cam(S.V(-8,2,58),S.V(0,1,0),40);
  S.setChain(S.GAME,1,9.5,{spawn:0.012,stepDur:0.28,graphOp:1});
  S.gridMat.uniforms.uOp.value=0.25;
});
