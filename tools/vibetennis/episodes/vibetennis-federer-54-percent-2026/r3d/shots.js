// 镜头表（秒）。设计与每个数字的出处：papers/vibetennis-federer-54-percent-2026/sources.md 第五节。
const ease=x=>{x=Math.min(1,Math.max(0,x)); return x*x*(3-2*x);};
const easeIO=x=>{x=Math.min(1,Math.max(0,x)); return x<0.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;};
const ramp=(x,a,b)=>ease((x-a)/(b-a));
const lerp=(a,b,u)=>a+(b-a)*u;
function fadeIO(S,lt,d,a=0.5,b=0.5){ S.finalPass.uniforms.uFade.value=Math.max(0,Math.min(1,a>0?lt/a:1,b>0?(d-lt)/b:1)); }
function hit(S,t,at,dur=0.45,shake=0.6,ring=S.shock,col=null,size=60){ const u=(t-at)/dur; if(u>=0&&u<1){ ring.material.opacity=(1-u)*0.85; ring.scale.setScalar(16+u*size); if(col) ring.material.color.copy(col); S.finalPass.uniforms.uShake.value=Math.max(S.finalPass.uniforms.uShake.value,(1-u)*shake); } }

export const SHOTS=[]; const add=(t0,t1,fn)=>SHOTS.push({t0,t1,fn});
export const TOTAL=188;
// 段落表（overlay 右上角章节标、sfx 用）
export const SECT=[[0,7],[7,15.5],[15.5,33],[33,64],[64,95],[95,117],[117,140],[140,164],[164,180],[180,188]];

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
    S.ballGlow.visible=true; S.ballGlow.position.copy(p); S.ballGlow.scale.setScalar(18); S.ballGlow.material.opacity=0.55;
    S.ballTrail.visible=true; const tail=at(Math.max(0,u-0.18)); S.setLine(S.ballTrail,[tail,p]); S.ballTrail.material.opacity=0.8;
  } else S.setMorph(TITLE,t,{spin:t<11?Math.sin((t-8.2)*0.8)*0.25*(1-ease((t-9)/2)):0});
  const ui=(t-8.18)/0.5; if(ui>=0&&ui<1){ S.finalPass.uniforms.uFlash.value=(1-ui)*0.7; S.shock2.material.opacity=(1-ui); S.shock2.scale.setScalar(10+ui*90); S.shock2.position.set(0,0,0); S.finalPass.uniforms.uShake.value=(1-ui)*1.2; }
  const ug=(t-11.1)/1.6; if(ug>=0){ S.setRays(Math.max(0,(1-ug*0.6))*(ug<0.15?ug/0.15:1),1+ug*0.3); S.flare.material.opacity=Math.max(0,1-ug*1.6)*0.9; S.flare.position.set(0,0,-3); S.flare.scale.setScalar(60+ug*40); if(ug<0.35) S.finalPass.uniforms.uFlash.value=Math.max(S.finalPass.uniforms.uFlash.value,(0.35-ug)*0.9); }
  S.bloom.strength=t>11.1?1.0:0.8;
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
  S.gridMat.uniforms.uOp.value=0.25; S.bloom.strength=0.8;
});
