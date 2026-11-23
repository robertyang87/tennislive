// ==================== EP14 不是补钾：本集物件与镜头 ====================
// 香蕉、玻璃卡、柱状图、示意糖原仓。糖原仓必须标「示意」，不得画成网球活检。
// 颜色沿用底座：CY 青、GO 金、RD 红、MT 薄荷绿、GOLD/CYAN/RED 光晕字串
const YL2=0xffe2a0, PU=0xa78bfa;
function hline(col,w,pts,o,d=9,dashed=false){ const l=ln(col,w,dashed); setLine(l,pts.map(p=>hp(p[0],p[1],d))); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=20; return l; }
function wline(col,w,pts,o,dashed=false,dt=false){ const l=ln(col,w,dashed); setLine(l,pts); l.material.opacity=o; l.material.depthTest=dt; l.renderOrder=19; return l; }

function bnCurve(){
  const pts=[];
  for(let i=0;i<=32;i++){
    const t=i/32, a=(t-0.5)*2.15, R=1.35;
    pts.push(new THREE.Vector3(0.05*Math.sin(Math.PI*t), R*(1-Math.cos(a))-R*(1-Math.cos(1.075)), R*Math.sin(a)));
  }
  return new THREE.CatmullRomCurve3(pts);
}
function radAt(t){ return 0.075+0.145*Math.pow(Math.sin(Math.PI*t),0.85); }
function taperedTube(curve,seg=40,radSegs=20){
  const frames=curve.computeFrenetFrames(seg,false);
  const pos=[], nrm=[], idx=[], rs=radSegs;
  for(let i=0;i<=seg;i++){
    const t=i/seg, p=curve.getPoint(t), r=radAt(t), N=frames.normals[i], B=frames.binormals[i];
    for(let j=0;j<=rs;j++){
      const a=j/rs*Math.PI*2, ca=Math.cos(a), sa=Math.sin(a);
      const q=p.clone().addScaledVector(N,r*ca).addScaledVector(B,r*sa);
      pos.push(q.x,q.y,q.z);
      const n=N.clone().multiplyScalar(ca).addScaledVector(B,sa).normalize();
      nrm.push(n.x,n.y,n.z);
    }
  }
  for(let i=0;i<seg;i++) for(let j=0;j<rs;j++){
    const a=i*(rs+1)+j, b=a+rs+1; idx.push(a,b,a+1, a+1,b,b+1);
  }
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
  g.setAttribute('normal',new THREE.Float32BufferAttribute(nrm,3));
  g.setIndex(idx); g.computeVertexNormals(); return g;
}
function ribbonGeo(curve,rScale,a0,a1,seg=28){
  const frames=curve.computeFrenetFrames(seg,false);
  const pos=[], nrm=[], uv=[], idx=[];
  for(let i=0;i<=seg;i++){
    const t=i/seg, p=curve.getPoint(t), r=radAt(t)*rScale;
    const N=frames.normals[i], B=frames.binormals[i];
    for(const a of [a0,a1]){
      const ca=Math.cos(a), sa=Math.sin(a);
      const q=p.clone().addScaledVector(N,r*ca).addScaledVector(B,r*sa);
      pos.push(q.x,q.y,q.z);
      const n=N.clone().multiplyScalar(ca).addScaledVector(B,sa).normalize();
      nrm.push(n.x,n.y,n.z); uv.push(t,a===a0?0:1);
    }
  }
  for(let i=0;i<seg;i++){ const a=i*2,b=a+1,c=a+2,d=a+3; idx.push(a,c,b, b,c,d); }
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
  g.setAttribute('normal',new THREE.Float32BufferAttribute(nrm,3));
  g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));
  g.setIndex(idx); g.computeVertexNormals(); return g;
}
const matFlesh=new THREE.MeshStandardMaterial({color:0xf6e08a,roughness:0.52,metalness:0.03,emissive:0x3a2800,emissiveIntensity:0.08,side:THREE.DoubleSide});
const matPeel=new THREE.MeshStandardMaterial({color:0xe8b41e,roughness:0.58,metalness:0.02,emissive:0x2a1c00,emissiveIntensity:0.07,side:THREE.DoubleSide});
const matPeelIn=new THREE.MeshStandardMaterial({color:0xf8eeb0,roughness:0.72,metalness:0.0,emissive:0x2a2208,emissiveIntensity:0.04,side:THREE.DoubleSide});
const matStem=new THREE.MeshStandardMaterial({color:0x5a3a18,roughness:0.85,emissive:0x1a1000,emissiveIntensity:0.05});
const matCut=new THREE.MeshStandardMaterial({color:0xfff3c0,roughness:0.42,emissive:0x332800,emissiveIntensity:0.10,side:THREE.DoubleSide});
function mkBanana(){
  const root=new THREE.Group(); const curve=bnCurve();
  const flesh=new THREE.Mesh(taperedTube(curve,56,24),matFlesh); flesh.castShadow=true; root.add(flesh);
  const stemP=curve.getPoint(0.02), stemT=curve.getTangent(0.02);
  const peels=[];
  // 三瓣：绕圆周均分，每瓣约 2.0 rad，在果柄处铰接
  const spans=[[-0.15,1.25],[1.95,3.35],[4.05,5.45]];
  for(let i=0;i<3;i++){
    const g=new THREE.Group();
    const outer=new THREE.Mesh(ribbonGeo(curve,1.08,spans[i][0],spans[i][1],32),matPeel);
    const inner=new THREE.Mesh(ribbonGeo(curve,1.01,spans[i][0],spans[i][1],32),matPeelIn);
    // 把几何挪到以果柄为原点，方便向外翻开
    outer.position.sub(stemP); inner.position.sub(stemP);
    g.position.copy(stemP); g.add(outer,inner); root.add(g); peels.push(g);
  }
  const stem=new THREE.Mesh(new THREE.CylinderGeometry(0.045,0.07,0.28,8),matStem);
  stem.position.copy(stemP); stem.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),stemT.clone().negate()); root.add(stem);
  function endCap(t,mat){
    const m=new THREE.Mesh(new THREE.CircleGeometry(radAt(t)+0.002,24),mat);
    const p=curve.getPoint(t), T=curve.getTangent(t);
    m.position.copy(p); m.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1), t<0.5?T.clone().negate():T);
    root.add(m); return m;
  }
  const capStem=endCap(0.02,matFlesh), capTip=endCap(0.985,matFlesh);
  const cut=new THREE.Mesh(new THREE.CircleGeometry(0.20,24),matCut); cut.visible=false; root.add(cut);
  root.visible=false; scene.add(root);
  return {root,flesh,peels,stem,cut,capStem,capTip,curve,stemP,stemT};
}
const BAN=mkBanana();
function setPeel(k){
  k=clamp(k,0,1);
  const midA=[0.55, 2.65, 4.75];
  const frames0=BAN.curve.computeFrenetFrames(8,false);
  const N=frames0.normals[0], B=frames0.binormals[0], T=BAN.stemT.clone().normalize();
  for(let i=0;i<3;i++){
    const rad=N.clone().multiplyScalar(Math.cos(midA[i])).addScaledVector(B,Math.sin(midA[i])).normalize();
    const axis=new THREE.Vector3().crossVectors(T, rad).normalize();
    BAN.peels[i].quaternion.setFromAxisAngle(axis, k*1.05);
  }
}
function setBite(k){
  k=clamp(k,0,1);
  BAN.cut.visible=k>0.08; BAN.capTip.visible=k<=0.08;
  if(k>0.08){
    const tt=1-0.16*k, p=BAN.curve.getPoint(tt), T=BAN.curve.getTangent(tt);
    BAN.cut.position.copy(p); BAN.cut.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),T);
    BAN.cut.scale.setScalar(radAt(tt)/0.20);
  }
  BAN.flesh.scale.set(1,1,1);
}
function bnOp(o){ BAN.root.visible=o>0.01; BAN.root.traverse(m=>{ if(m.material){ m.material.transparent=o<0.99; m.material.opacity=o; }}); }
function bnPose(x,y,z,s=1,rx=0,ry=0,rz=0){ BAN.root.position.set(x,y,z); BAN.root.scale.setScalar(s); BAN.root.rotation.set(rx,ry,rz); }

// 玻璃卡平面池
const CARDS=[];
function card(w,h,col=0x0a1428,op=0.55){
  let m=CARDS.find(c=>!c.userData.used);
  if(!m){
    const geo=new THREE.PlaneGeometry(1,1);
    const mat=new THREE.MeshPhysicalMaterial({color:col,roughness:0.25,metalness:0.15,transmission:0.15,transparent:true,opacity:0.55,emissive:0x061018,emissiveIntensity:0.12,side:THREE.DoubleSide,depthWrite:false});
    m=new THREE.Mesh(geo,mat); m.renderOrder=8; scene.add(m); CARDS.push(m);
  }
  m.userData.used=1; m.visible=op>0.01; m.scale.set(w,h,1); m.material.color.setHex(col); m.material.opacity=op; m.material.transparent=true;
  return m;
}
function hideCards(){ CARDS.forEach(c=>{ c.visible=false; c.userData.used=0; }); }

// 示意糖原仓
const TANK=(()=>{
  const g=new THREE.Group();
  const wall=new THREE.Mesh(new THREE.CylinderGeometry(0.7,0.7,2.2,32,1,true), new THREE.MeshPhysicalMaterial({color:0x0c2a24,transparent:true,opacity:0.35,roughness:0.2,metalness:0.15,side:THREE.DoubleSide,emissive:0x042018,emissiveIntensity:0.1,depthWrite:false}));
  const fill=new THREE.Mesh(new THREE.CylinderGeometry(0.64,0.64,1,32), new THREE.MeshStandardMaterial({color:0x34f5a8,roughness:0.35,emissive:0x0a3a22,emissiveIntensity:0.22,transparent:true,opacity:0.85}));
  fill.position.y=-0.6; fill.userData.baseH=2.0;
  const rim=new THREE.Mesh(new THREE.TorusGeometry(0.7,0.03,8,40), new THREE.MeshStandardMaterial({color:0x4fe3ff,emissive:0x0a3038,emissiveIntensity:0.2}));
  rim.rotation.x=Math.PI/2; rim.position.y=1.1;
  g.add(wall,fill,rim); g.visible=false; scene.add(g);
  return {g,fill,wall,rim};
})();
function tankFill(frac,op){
  TANK.g.visible=op>0.02; TANK.g.traverse(m=>{ if(m.material){ m.material.transparent=true; m.material.opacity=(m===TANK.fill?0.85:0.35)*op; }});
  const h=0.25+1.7*clamp(frac,0,1); TANK.fill.scale.y=h; TANK.fill.position.y=-1.1+h/2;
}

function hideBN(){
  bnOp(0); setPeel(0); setBite(0); BAN.root.position.set(0,0,0); BAN.root.rotation.set(0,0,0); BAN.root.scale.setScalar(1);
  hideCards(); TANK.g.visible=false;
}
function hideAll(){
  courtG.visible=false; courtG.userData.mat.opacity=1; courtG.rotation.set(0,0,0); courtG.position.set(0,0,0); courtG.children[1].visible=false;
  HUM.forEach(H=>{ humanOp(H,0); H.root.position.set(0,0,0); H.root.rotation.set(0,0,0); H.root.scale.setScalar(1); });
  BALLS.forEach(b=>{ b.m.visible=false; b.gl.visible=false; }); bI=0;
  LN.forEach(l=>{ l.material.opacity=0; l.material.dashed=false; l.material.depthTest=false; l.renderOrder=0; }); lnI=0; RG.forEach(r=>r.material.opacity=0); rgI=0; GS.forEach(s=>{ s.material.opacity=0; s.visible=false; }); gsI=0;
  for(const k in TT) op(TT[k],0); for(const k in TB) TB[k].g.visible=false; for(const k in text3D) t3op(text3D[k],0); chide(pt);
  beamMat.uniforms.uOp.value=0; rimL.intensity=0; rimR.intensity=0; DOF.on=false; MOTE_SPEED=1; SLOW=null; ST_RATE=0.0003;
  hideBN();
}
function num(key,str,col,size,x,y,o,d=9){ const n=t3d(key,str,col,size); hud(n,x,y,d); t3op(n,o); if(!n.g.userData.ndt){ n.g.traverse(m=>{ if(m.material){ m.material.depthTest=false; m.renderOrder=24; } }); n.g.userData.ndt=1; } return n; }
function courtOn(o=1){ courtG.visible=o>0.003; courtG.userData.mat.opacity=o; courtG.children[1].visible=false; }
const beatT=(k)=>TL.beat.hit+k*TL.beat.p;
const pulse=(u,t,w=0.35)=>u>t?Math.exp(-(u-t)/w):0;
function clockRing(x,y,r,frac,o,col=CY){
  const n=48, pts=[], f=clamp(frac,0,1);
  for(let i=0;i<=Math.round(n*f);i++){ const a=-Math.PI/2+i/n*Math.PI*2; pts.push([x+r*Math.cos(a),y+r*Math.sin(a)]); }
  if(pts.length>1) hline(col,5,pts,o);
}

// ---------- 1 钩子：夜场换边，九十秒，抽出香蕉，剥开咬一口，补钾？ ----------
function shotHook(u,D){
  const PE=ev('peel',3.5), BI=ev('bite',5.1), MY=ev('myth',7.7), Q=ev('q',10.4);
  rims(GO,CY,3.2); beamMat.uniforms.uOp.value=0.10; courtOn(1); ST_RATE=0.0016;
  const k=ss(0,D,u);
  look(lerp(5.8,3.4,k),lerp(1.65,1.20,k),lerp(11.0,7.2,k), lerp(1.8,1.0,ss(0,PE+0.8,u)), lerp(0.7,0.9,k), lerp(10.2,8.4,k));
  DOF.on=true; DOF.focus=2.8; DOF.ap=0.00018;
  // 换边时钟
  const left=Math.max(0,90-u*(90/Math.max(8,D-1.2))), fr=left/90, clk=Math.ceil(left);
  if(shotHook._clk!=null && shotHook._clk!==clk && text3D['hkClk'+shotHook._clk]) t3op(text3D['hkClk'+shotHook._clk],0);
  shotHook._clk=clk;
  clockRing(-3.15,1.55,0.72,fr,0.9, fr<0.25?RD:CY);
  num('hkClk'+clk,clk+' s',fr<0.25?RD:CY,0.42,-3.15,1.55,0.95);
  lab('hkCh',T('换边','changeover'),-3.15,0.95,0.85,{size:0.26,color:'#bff3ff'});
  // 香蕉从毛巾下抽出
  const appear=ss(PE-2.2,PE-0.2,u);
  bnOp(appear); bnPose(1.55,0.90,8.55, 0.92, -0.15, 0.35, 1.25);
  setPeel(ss(PE-0.2,PE+1.8,u)*0.58); setBite(0);
  const g=gs(GO,0.55,0.30*appear*(0.7+0.3*Math.sin(u*5))); g.position.set(1.35,0.88,8.55);
  lab('hkTow',T('毛巾底下','under the towel'),2.4,0.15,appear*(1-ss(PE,PE+0.8,u)),{size:0.28,color:'#e8f4ff'});
  const mo=ss(MY,MY+0.35,u)*(1-ss(Q-0.15,Q+0.6,u)*0.0);
  lab('hkMyth',T('补钾，别抽筋','potassium, no cramp'),0.15,1.85,ss(MY,MY+0.3,u),{size:0.48,color:'#ffe2a0',glow:GOLD});
  if(u>Q-0.05){ lab('hkQ',T('真的是为了这个吗？','is that really why?'),0.15,1.25,ss(Q,Q+0.35,u),{size:0.40,color:'#ffb0a8',glow:RED});
    if(u>Q&&u<Q+1.2) shockRing(hp(0.15,1.85), (u-Q)/1.2, RD, 2.0, 0.65, true); }
}

// ---------- 2 片名：不是补钾 / 肌糖原（示意） ----------
function shotTitle(u,D){
  const PU=ev('punch',0.53), GL=ev('gly',5.32), NO=ev('no',9.04);
  rims(GO,YL2,4.5); beamMat.uniforms.uOp.value=0.08; courtOn(0); ST_RATE=0.0004;
  look(lerp(0.2,-0.4,ss(0,D,u)),1.05,7.2, 0,0.15,0);
  const tt=bt('tt0',T('不是补钾','Not potassium'),{size:1.12,glow:'rgba(255,194,74,0.45)',fx:'weave',accent:T('补钾','potassium')});
  hud(tt,0,0.35,9); tt.update(u, PU-0.4, D-0.2, 0.95);
  if(u>PU&&u<PU+1.1) shockRing(hp(0,0.35),(u-PU)/1.1,GO,2.4,0.7,true);
  const go=ss(GL,GL+0.45,u);
  lab('ttGly',T('肌糖原','MUSCLE GLYCOGEN'),0,-0.85,go,{size:0.48,color:'#b8ffe0',glow:'rgba(52,245,168,0.7)'});
  lab('ttNote',T('耐力运动的经典燃料库 · 示意','classic fuel store in endurance sport · schematic'),0,-1.35,go,{size:0.26,color:'#9fb8b0'});
  lab('ttNo',T('吃香蕉是为了防抽筋 —— 还没有被证明','eating bananas to prevent cramp — not shown'),0,-1.85,ss(NO,NO+0.4,u),{size:0.30,color:'#e8f4ff'});
}

// ---------- 3 剖开：118 g / 27 / 14 / 3 / 105 / 422 / GI 51 ----------
function shotPeel(u,D){
  const SZ=ev('size',3.2), CH=ev('cho',5.85), SU=ev('sug',6.92), FI=ev('fib',8.51), KC=ev('kcal',9.58), KK=ev('k',13.3), GI=ev('gi',19.15), RP=ev('ripe',21.28), FS=ev('first',24.47);
  rims(GO,CY,3.4); beamMat.uniforms.uOp.value=0.07; courtOn(0); ST_RATE=0.00035;
  const k=ss(0,D,u);
  look(lerp(2.6,2.0,k),lerp(1.35,0.95,k),lerp(3.6,2.8,k), 0,0.2,0);
  DOF.on=true; DOF.focus=2.3; DOF.ap=0.00016;
  bnOp(1); bnPose(0.15,0.05,0, 1.15, 0.35, 1.15+u*0.03, -0.15);
  setPeel(0.05+0.62*ss(0.2,2.4,u)); setBite(0);
  const g=gs(GO,0.8,0.22+0.06*Math.sin(u*3)); g.position.set(0,0.2,0);
  lab('pSz',T('可食部约 118 克','edible portion ≈ 118 g'),0,1.95,ss(SZ,SZ+0.3,u),{size:0.32,color:'#e8f4ff'});
  const items=[
    ['pCHO','27 g',T('碳水','CHO'),GO,CH,-3.3,1.15],
    ['pSUG','14 g',T('糖','sugar'),YL2,SU,-3.3,0.45],
    ['pFIB','3 g',T('纤维','fibre'),0xb8d4a0,FI,-3.3,-0.25],
    ['pKCAL','105',T('千卡','kcal'),0xffe2a0,KC,-3.3,-0.95],
    ['pK','422 mg',T('钾','K'),CY,KK,3.25,0.55]
  ];
  for(const [id,val,lb,col,t0,x,y] of items){
    const o=ss(t0,t0+0.28,u);
    const c=card(1.55,0.85,0x0c1420,0.5*o); c.position.copy(hp(x,y));
    num(id,val,col,0.42,x,y+0.12,o); lab(id+'l',lb,x,y-0.32,o,{size:0.24,color:'#c8d4e0'});
  }
  // GI 表盘
  const go=ss(GI-0.2,GI+0.35,u);
  const gx=2.9, gy=-1.15;
  clockRing(gx,gy,0.85,0.51*ss(GI,GI+0.8,u),go,GO);
  clockRing(gx,gy,0.85,1,go*0.25,0x445060);
  num('pGI','GI 51',GO,0.40,gx,gy+0.05,go);
  lab('pGIl',T('国际表平均值 · 低 GI','international table mean · low GI'),gx,gy-0.55,go,{size:0.22,color:'#c8d4e0'});
  lab('pRipe',T('过熟会再高一些','higher when overripe'),gx,gy-0.95,ss(RP,RP+0.3,u),{size:0.24,color:'#ffd0a0'});
  lab('pFirst',T('它首先是一块带着钾的糖','first of all, sugar that carries potassium'),0,-2.05,ss(FS,FS+0.35,u),{size:0.36,color:'#ffe2a0',glow:GOLD});
}

// ---------- 4 钠钾与抽筋 ----------
function shotSalt(u,D){
  const NA=ev('na',2.13), SW=ev('sweat',5.32), NM=ev('naMg',8.51), KM=ev('kMg',11.17), CV=ev('cover',14.36), MS=ev('miss',16.49), RC=ev('race',22.34), NV=ev('nerve',26.60), VD=ev('verdict',31.92);
  rims(CY,RD,3.2); beamMat.uniforms.uOp.value=0.06; courtOn(0); ST_RATE=0.0003;
  look(0,1.4,8.0, 0,0.2,0);
  lab('sHead',T('汗里丢掉最多的，是钠','the biggest sweat loss is sodium'),0,2.05,ss(NA,NA+0.3,u)*(1-ss(SW+2,SW+3.2,u)),{size:0.40,color:'#9fe9ff'});
  lab('sCond',T('实验室 · 90 分钟骑车 · 11 人 · 中等强度 · 不是网球','lab · 90-min cycling · n=11 · moderate · not tennis'),0,2.05,ss(SW,SW+0.3,u),{size:0.26,color:'#9aa8b8'});
  // 柱：钠 1565 vs 钾 194，高度按毫克，钾柱很矮。422 mg 香蕉钾盖过钾柱。
  const maxMg=1600, Hmax=2.6;
  const hNa=Hmax*(1565/maxMg)*ss(NM,NM+0.7,u), hK=Hmax*(194/maxMg)*ss(KM,KM+0.7,u), hB=Hmax*(422/maxMg)*ss(CV,CV+0.6,u);
  const xNa=-1.7, xK=0.55, y0=-1.55;
  function colBar(x,h,col,o){
    if(o<0.02||h<0.02) return;
    const l=wline(col,14,[V(x,y0,0),V(x,y0+h,0)],o); l.material.depthTest=false;
    const s=gs(col,0.45,0.45*o); s.position.set(x,y0+h,0);
  }
  // 对照卡出现后把柱状图和判语淡出，避免「抽筋」压到 1,565 mg
  const leaveBars=1-ss(RC,RC+0.45,u);
  colBar(xNa,hNa,CY,ss(NM,NM+0.2,u)*leaveBars); colBar(xK,hK,GO,ss(KM,KM+0.2,u)*leaveBars);
  // 香蕉钾虚线柱
  if(hB>0.02){ const l=wline(MT,4,[V(xK+0.22,y0,0),V(xK+0.22,y0+hB,0)],0.85*ss(CV,CV+0.2,u)*leaveBars,true); }
  num('sNa','1,565 mg',CY,0.40,xNa,y0+hNa+0.35,ss(NM,NM+0.25,u)*leaveBars); lab('sNal',T('钠','Na'),xNa-0.55,y0+0.22,ss(NM,NM+0.2,u)*leaveBars,{size:0.28,color:'#bff3ff'});
  num('sK','194 mg',GO,0.34,xK,y0+hK+0.35,ss(KM,KM+0.25,u)*leaveBars); lab('sKl',T('钾','K'),xK-0.50,y0+0.22,ss(KM,KM+0.2,u)*leaveBars,{size:0.28,color:'#ffe2a0'});
  lab('sBan',T('一根香蕉 422 mg 钾','one banana: 422 mg K'),xK+1.85,y0+hB+0.22,ss(CV,CV+0.3,u)*leaveBars,{size:0.26,color:'#b8ffe0'});
  // sMiss 不能放在 y<-1.95：layoutText 会把它抬回字幕带上沿，压到柱脚「钾」上。改到右下安全区、拆成两行。
  const mo=ss(MS,MS+0.3,u)*(1-ss(VD-0.8,VD,u))*leaveBars;
  lab('sMiss1',T('盖得住这次钾损失','covers this K loss'),2.25,-1.12,mo,{size:0.28,color:'#ffb0a8',glow:RED});
  lab('sMiss2',T('盖不住那些钠','not the sodium'),2.25,-1.50,mo,{size:0.28,color:'#ffb0a8',glow:RED});
  // 队列对照
  const ro=ss(RC,RC+0.4,u);
  if(ro>0.02){
    const c1=card(2.4,1.5,0x12101c,0.5*ro); c1.position.copy(hp(-2.2,0.55));
    const c2=card(2.4,1.5,0x12101c,0.5*ro); c2.position.copy(hp(2.2,0.55));
    lab('crA',T('抽筋','cramp'),-2.2,1.05,ro,{size:0.30,color:'#ffb0a8'});
    lab('crB',T('对照','control'),2.2,1.05,ro,{size:0.30,color:'#bff3ff'});
    lab('crK',T('血清钾：没有可靠差别','serum K: no reliable difference'),0,0.15,ro,{size:0.32,color:'#e8f4ff'});
    lab('crN',T('更说得通：疲劳后，神经对肌肉的控制乱了','more plausible: neural control after fatigue'),0,-0.55,ss(NV,NV+0.35,u),{size:0.28,color:'#c9d6ff'});
  }
  lab('sVd',T('钾是真的。防抽筋，还没有被证明。','K is real. Preventing cramp has not been shown.'),0,-2.05,ss(VD,VD+0.35,u),{size:0.36,color:'#ffe2a0',glow:GOLD});
}

// ---------- 5 补糖窗口（糖原仓＝示意） ----------
function shotFuel(u,D){
  const ND=ev('need',3.72), NB=ev('notbx',6.38), GL=ev('glu',10.11), GD=ev('guide',14.36), ST=ev('stmt',15.96), LO=ev('lo',24.47), HI=ev('hi',28.19), WN=ev('win',31.38), SE=ev('set',32.45), BR=ev('bar',40.43), NA=ev('notall',43.09);
  rims(MT,GO,3.2); beamMat.uniforms.uOp.value=0.07; courtOn(0); ST_RATE=0.0003;
  look(lerp(-0.4,0.6,ss(0,D,u)),1.15,7.6, -0.4,0.2,0);
  tankFill(0.72-0.25*ss(ND,ND+4,u), ss(0.3,1.2,u)*(1-ss(ST+6,ST+8,u)*0.35)+0.4*ss(ST+6,ST+8,u));
  TANK.g.position.set(-2.3,0.15,0);
  lab('fTk',T('肌糖原 · 示意','muscle glycogen · schematic'),-2.3,2.05,ss(0.4,1.0,u),{size:0.28,color:'#b8ffe0'});
  lab('fNot',T('不是网球场上的活检','not a biopsy from a tennis court'),-2.3,1.65,ss(NB,NB+0.3,u),{size:0.24,color:'#9aa8b8'});
  lab('fGlu',T('网球研究更多测的是血糖','tennis studies more often measure blood glucose'),-2.3,-1.85,ss(GL,GL+0.3,u),{size:0.24,color:'#c8d4e0'});
  lab('fGd',T('指南仍把比赛中的碳水，写成补贴糖原的燃料','guidelines still describe in-match CHO as topping up glycogen'),0,2.15,ss(GD,GD+0.3,u),{size:0.26,color:'#eafff6'});
  // 指南刻度
  const so=ss(ST,ST+0.5,u);
  const x0=0.6, yb=-1.3, W=4.6, h=0.22;
  wline(0x2a4a44,3,[V(x0,yb,0),V(x0+W,yb,0)],0.7*so);
  // 30-60 段、60-90 段
  const p30=W*(30/90), p60=W*(60/90), p90=W;
  const aLo=ss(LO,LO+0.6,u), aHi=ss(HI,HI+0.6,u);
  wline(MT,16,[V(x0,yb+0.18,0),V(x0+p60*aLo,yb+0.18,0)],0.85*so);
  wline(GO,16,[V(x0+p60,yb+0.18,0),V(x0+p60+(p90-p60)*aHi,yb+0.18,0)],0.85*aHi);
  num('f30','30',MT,0.28,x0,yb-0.45,so); num('f60','60',MT,0.28,x0+p60,yb-0.45,aLo); num('f90','90 g/h',GO,0.28,x0+p90,yb-0.45,aHi);
  lab('fLo',T('90 分钟–3 小时：30–60 g/h','90 min–3 h: 30–60 g/h'),x0+p60*0.5,yb+0.7,ss(LO,LO+0.3,u),{size:0.26,color:'#b8ffe0'});
  lab('fHi',T('五盘 · 约 5 小时：60–90 g/h','five sets · ~5 h: 60–90 g/h'),x0+p60+0.9,yb+0.7,ss(HI,HI+0.3,u),{size:0.26,color:'#ffe2a0'});
  lab('fSrc',T('2025 ITF / WTA / ATP 专家声明','2025 ITF / WTA / ATP expert statement'),x0+W*0.5,yb+1.15,so,{size:0.24,color:'#9aa8b8'});
  // 窗口
  const wo=ss(WN,WN+0.3,u);
  clockRing(3.4,1.45,0.55,90/120,wo,CY);
  num('f90s','90 s',CY,0.32,3.4,1.55,wo); lab('f90l',T('换边','changeover'),3.4,1.05,wo,{size:0.22,color:'#bff3ff'});
  num('f120s','120 s',GO,0.32,3.4,0.45,ss(SE,SE+0.3,u)); lab('f120l',T('盘间','between sets'),3.4,0.05,ss(SE,SE+0.3,u),{size:0.22,color:'#ffe2a0'});
  // 27 g 标记：线用 HUD 坐标，与 27 g 数字对齐；注记放在 27 g 左侧，躲开右上 120 s
  const bo=ss(BR,BR+0.3,u);
  const x27=x0+W*(27/90);
  hline(YL2,3,[[x27,yb-0.05],[x27,yb+1.25]],bo);
  num('f27','27 g',GO,0.36,x27,yb+1.60,bo);
  lab('fBar',T('大概刚够下限','roughly the lower end'),x27-1.40,yb+1.60,bo,{size:0.26,color:'#ffe2a0'});
  lab('fAll',T('一小时一根，不是五盘的全部','one an hour is not a whole five-set match'),0.2,-0.92,ss(NA,NA+0.3,u),{size:0.28,color:'#eafff6'});
}

// ---------- 6 试验证据（含混杂与缺口） ----------
function shotProof(u,D){
  const MX=ev('mix',4.26), V=ev('v',5.85), VR=ev('vres',17.55), M=ev('m',18.09), MT=ev('mtot',23.94), M1=ev('m1st',27.13), MN=ev('mnote',31.38), MI=ev('mit',35.64), N=ev('n',40.43), NR=ev('nres',46.28), NT=ev('ntime',47.34), BL=ev('blo',51.07), DL=ev('dole',53.73), NN=ev('none',59.58);
  rims(PU,CY,3.0); beamMat.uniforms.uOp.value=0.05; courtOn(0); ST_RATE=0.00025;
  look(0,0.9,8.4, 0,0.1,0);
  lab('prMix',T('结果并不完全一样','the results are not all the same'),0,2.1,ss(MX,MX+0.3,u)*(1-ss(V+2,V+3,u)),{size:0.42,color:'#c9d6ff'});
  function trial(id,x,y,w,h,t0,title,body,src,accent,opMul=1){
    const o=ss(t0,t0+0.35,u)*opMul;
    if(o<0.01) return 0;
    const c=card(w,h,0x101428,0.55*o); c.position.copy(hp(x,y));
    lab(id+'t',title,x,y+h*0.32,o,{size:0.28,color:accent||'#e8f4ff'});
    lab(id+'b',body,x,y-0.02,o,{size:0.24,color:'#c8d4e0'});
    lab(id+'s',src,x,y-h*0.32,o,{size:0.20,color:'#8a96a8'});
    return o;
  }
  // 依次：Vergauwen 左、McRae 中、Mitchell 右，然后 Nieman 大卡，最后空卡
  const phase2=ss(N-0.6,N,u);
  const yA=0.2, fade=1-phase2;
  const two=ss(M-0.15,M+0.4,u), three=ss(MI-0.15,MI+0.4,u);
  const xV=lerp(0, lerp(-1.55,-2.55,three), two);
  // 滑出画面会被 layoutText 拉回左右安全区，改成与 McRae 一样按 fade 淡出
  trial('v',xV, yA, 2.7, 2.3, V,
    T('1998 · 13 名男选手','1998 · 13 trained men'),
    T('补糖后，击球质量掉得更少','with CHO, stroke quality fell less'),
    T('Vergauwen 等，双盲交叉，2 小时高强度','Vergauwen et al., double-blind crossover, 2 h'),
    '#b8ffe0', fade);
  lab('vr',T('掉得更少','declined less'),-2.9, -1.25, ss(VR,VR+0.3,u)*fade,{size:0.26,color:'#34f5a8'});
  trial('m',0, yA, 2.7, 2.3, M,
    T('2012 · 22 名国家级选手','2012 · 22 national-level'),
    T('总发球 68% 对 66%  ·  一发 65% 对 61%','total serve 68% vs 66%  ·  1st 65% vs 61%'),
    T('McRae & Galloway，室内 2 小时','McRae & Galloway, 2 h indoors'),
    '#c9d6ff', fade);
  lab('mn',T('差距不大 · 这场也可能还不够累','small gaps · the match may not have been tiring enough'),0,-1.35,ss(MN,MN+0.3,u)*fade,{size:0.24,color:'#9aa8b8'});
  trial('mi',2.55, yA, 2.7, 2.3, MI,
    T('1992 · 12 名选手 · 3 小时','1992 · 12 players · 3 h'),
    T('血糖高了，表现没有更好','glucose up, no better performance'),
    T('Mitchell 等，碳水饮料对水','Mitchell et al., CHO drink vs water'),
    '#ffb0a8', fade);
  // Nieman
  const no=ss(N,N+0.4,u)*(1-ss(NN-0.4,NN,u));
  trial('n',0, 0.25, 5.6, 2.4, N,
    T('2012 · 14 名男自行车手 · 75 km','2012 · 14 male cyclists · 75 km'),
    T('香蕉 2 小时 41 分  ·  等量碳水饮料 2 小时 36 分  ·  没有明显差别','banana 2 h 41 min  ·  matched drink 2 h 36 min  ·  no clear difference'),
    T('Nieman 等 · Dole 资助 · 不是网球','Nieman et al. · Dole-funded · not tennis'),
    '#ffe2a0', no);
  lab('nBlo',T('吃香蕉的人更饱、更胀','banana riders felt fuller and more bloated'),0,-1.45,ss(BL,BL+0.3,u)*no,{size:0.28,color:'#ffd0a0'});
  // 空卡
  const eo=ss(NN,NN+0.4,u);
  const c=card(5.2,1.8,0x180a10,0.6*eo); c.position.copy(hp(0,0.1));
  lab('none',T('网球场上，还没找到香蕉对照试验','no head-to-head banana trial on a tennis court has been found'),0,0.25,eo,{size:0.36,color:'#ffb0a8',glow:RED});
  lab('none2',T('这是本集必须留下的缺口','this is a gap this episode has to leave open'),0,-0.4,eo,{size:0.26,color:'#c8d4e0'});
}

// ---------- 7 对照与 2010 温网 ----------
function shotAlt(u,D){
  const OK=ev('ok',3.19), DR=ev('drink',4.26), DT=ev('date',12.77), CW=ev('chew',21.28), BB=ev('bbc',22.87), AK=ev('ask',30.32);
  rims(GO,CY,3.2); beamMat.uniforms.uOp.value=0.06; courtOn(ss(BB,BB+0.8,u)*0.55); ST_RATE=0.0008;
  const k=ss(0,D,u);
  look(lerp(0,-0.3,k),1.1,7.8, 0,0.15, lerp(0,2.5,ss(BB,BB+1.5,u)));
  // 三件对照
  const show=1-ss(BB-0.4,BB+0.6,u);
  bnOp(show*ss(0.2,1.0,u)); bnPose(-2.6,0.15,0, 0.85, 0.4, 1.1, 0); setPeel(0.7); setBite(0);
  lab('aBn',T('香蕉  27 g','banana  27 g'),-2.6,-1.15,show*ss(OK,OK+0.3,u),{size:0.30,color:'#ffe2a0'});
  // 瓶子
  const bo=show*ss(DR,DR+0.3,u);
  if(bo>0.02){
    const bottle=card(0.7,2.0,0x0a3040,0.7*bo); bottle.position.set(0,0.3,0);
    const liq=card(0.55,1.4,0x0a80a0,0.55*bo); liq.position.set(0,0.05,0.02);
    num('aDr','27 g',CY,0.36,0,1.55,bo); lab('aDrl',T('450 mL · 6%  · 按浓度算','450 mL · 6%  · by concentration'),0,-1.15,bo,{size:0.24,color:'#bff3ff'});
    lab('aNa',T('还能补水和钠','also replaces water and sodium'),0,-1.55,bo,{size:0.24,color:'#9fe9ff'});
  }
  // 美枣（椭球）
  const do_=show*ss(DT,DT+0.3,u);
  if(do_>0.02){
    const d=gs(0xc45c20,0.85,0.5*do_); d.position.set(2.6,0.25,0);
    num('aDt','18 g',0xffb347,0.36,2.6,1.55,do_); lab('aDtl',T('一颗美枣','one Medjool date'),2.6,-1.15,do_,{size:0.28,color:'#ffd0a0'});
  }
  lab('aChew',T('有纤维，要咀嚼，九十秒不一定吃得完一整根','fibre, chewing: 90 s may not finish a whole one'),0,-2.05,ss(CW,CW+0.3,u)*show,{size:0.28,color:'#e8f4ff'});
  // 2010 BBC
  const ho=ss(BB,BB+0.45,u);
  if(ho>0.02){
    bnOp(Math.max(show,ho)); bnPose(0.95,0.7,8.2, 0.75, -0.45, 0.9, 0.1); setPeel(0.8);
    const poster=card(4.8,2.2,0x1a1206,0.62*ho); poster.position.copy(hp(-0.2,0.7));
    lab('bbcY',T('2010  ·  温网半决赛','2010  ·  Wimbledon semi-final'),-0.2,1.35,ho,{size:0.34,color:'#ffe2a0',glow:GOLD});
    lab('bbcS',T('穆雷 4–6，第二盘 2–2 的一次换边','Murray 4–6, 2–2 in the second, one changeover'),-0.2,0.75,ho,{size:0.26,color:'#e8f4ff'});
    lab('bbcA',T('纳达尔向裁判要的，是香蕉','what Nadal asked the umpire for was bananas'),-0.2,0.15,ss(AK,AK+0.3,u),{size:0.34,color:'#fff3d0'});
    lab('bbcSrc',T('BBC Sport 文字直播，Tom Fordyce','BBC Sport live text, Tom Fordyce'),-0.2,-0.45,ho,{size:0.22,color:'#9aa8b8'});
  }
}

// ---------- 8 关闭 ----------
function shotEnd(u,D){
  const AG=ev('again',0.53), KK=ev('k',3.72), CH=ev('cho',10.11), Q=ev('q',19.68);
  rims(GO,CY,3.6); beamMat.uniforms.uOp.value=0.10; courtOn(0.35); ST_RATE=0.0008;
  look(2.2,1.05,5.2, 0.2,0.7,8.0);
  DOF.on=true; DOF.focus=2.6; DOF.ap=0.0002;
  bnOp(1); bnPose(0.7,0.72,8.05, 0.85, -0.45, 0.95, 0.10);
  setPeel(0.82); setBite(0.55+0.04*Math.sin(u*2));
  const g=gs(GO,0.9,0.32+0.1*Math.sin(u*4)); g.position.set(0.6,0.75,8.0);
  const ko=ss(KK,KK+0.35,u)*(1-ss(CH-0.4,CH+0.8,u));
  num('eK','422 mg',CY,0.50,-2.6,1.3,ko); lab('eKl',T('钾是真的','the potassium is real'),-2.6,0.7,ko,{size:0.30,color:'#bff3ff'});
  lab('eK2',T('还没有被证明是抽筋药','not shown to be a cramp medicine'),-2.6,0.25,ko,{size:0.26,color:'#9aa8b8'});
  const co=ss(CH,CH+0.4,u);
  num('eC','27 g',GO,0.62,-2.4,1.15,co); lab('eCl',T('碳水，才是更站得住的理由','carbohydrate is the more defensible reason'),-2.4,0.45,co,{size:0.32,color:'#ffe2a0',glow:GOLD});
  const qo=ss(Q,Q+0.4,u);
  lab('eQ',T('下次换边，还会先想到钾吗？','next changeover, will K still come first?'),0,-1.85,qo,{size:0.38,color:'#e8f4ff'});
}

const SHOTS={hook:shotHook,title:shotTitle,peel:shotPeel,salt:shotSalt,fuel:shotFuel,proof:shotProof,alt:shotAlt,end:shotEnd};
function shotTest(u,D){ look(0,0,8,0,0,0); }
