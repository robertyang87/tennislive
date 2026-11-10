// ==================== 本集镜头 ====================
// 球场：1 单位 = 1 m（底座 courtG 就是 ITF 尺寸，球网在 z=0）。甲（金，SRV）站近端 z=+L 一侧面朝 -z；乙（青，RET）站远端 z=-L 一侧面朝 +z。
const SRV=makeHuman(0xffc24a), RET=makeHuman(0x4fe3ff);
const HUM=[SRV,RET];
const rkS=makeRk('carbon',{a:13.5/2*IN*0.95,b:10.5/2*IN*0.95}), rkR=makeRk('carbon',{a:13.5/2*IN*0.95,b:10.5/2*IN*0.95});
attachRacket(SRV,rkS); attachRacket(RET,rkR);
const CY=0x4fe3ff, GO=0xffc24a, RD=0xff5a4a, MT=0x34f5a8, WH=0xffffff, PJ=0x9dff5a, OR=0xffb347;
const GA=GO, GB=CY;   // 甲＝金，乙＝青（全片固定）
// 镜头坐标里的点（look() 之后调）：x、y 是画面上的偏移，d 是离相机的距离。d=9 时画面半宽约 5.5、半高约 3.1；字幕带以上 y>-1.95，品牌带以下 y<2.4
function hp(x,y,d=9){ camera.updateMatrixWorld(); return V(x,y,-d).applyQuaternion(camera.quaternion).add(camera.position); }
const rims=(a,b,i=5)=>{ rimL.intensity=i; rimR.intensity=i; rimL.color.set(a); rimR.color.set(b); rimL.position.set(-6,4,6); rimR.position.set(6,4,6); };
function place(H,x,z,yaw){ H.root.position.set(x,0,z); H.root.rotation.set(0,yaw,0); }
function lab(k,str,x,y,o,opt={}){ const t=tx(k,str,Object.assign({color:'#e8f4ff',size:0.34,glow:CYAN},opt)); if(x!==null) hud(t,x,y,opt.d||9); op(t,o); return t; }   // x=null：世界坐标（调用方设 position）
function bar(col,x0,x1,y,o,w=10,d=9){ const l=ln(col,w); setLine(l,[hp(x0,y,d),hp(Math.abs(x1-x0)<0.001?x0+0.001:x1,y,d)]); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=20; return l; }
function burst(c,k,col,spread=6,o=1){ const cc=new THREE.Color(col); for(let i=0;i<1600;i++){ const p=PTS[i]; const dir=V(p[0],p[1]*1.2,p[2]).normalize(); const sp=spread*(0.4+0.6*p[3]); const e=1-Math.pow(1-clamp(k),2.2);
  cset(pt,i,c.x+dir.x*sp*e,c.y+dir.y*sp*e-1.5*e*e,c.z+dir.z*sp*e,cc.r,cc.g,cc.b,o*(1-ss(0.55,1,k))*(0.5+0.5*p[4])); } cdone(pt); }
function shockRing(c,k,col,maxR,o=1,vertical=false){ const r=rg(); r.position.copy(c); if(vertical){ r.quaternion.copy(camera.quaternion); } else r.rotation.set(-Math.PI/2,0,0); const e=1-Math.pow(1-clamp(k),3); r.scale.setScalar(0.2+maxR*e); r.material.color.set(col).multiplyScalar(GLOW.k); r.material.opacity=o*(1-ss(0.35,1,k)); }

// ==================== EP12 抢七轮发：本集物件 ====================
// 序列：'A'＝甲、'B'＝乙。全部可在 papers/vibetennis-tiebreak-2026/tiebreak_math.py 里复现。
const SEQ={ ABAB:k=>'AB'[k%2], ABBA:k=>(((k+1)>>1)%2)?'B':'A', TM:k=>{ let c=0,x=k; while(x){ c+=x&1; x>>=1; } return 'AB'[c%2]; } };
const seqStr=(o,n)=>[...Array(n)].map((_,k)=>SEQ[o](k)).join('');
const NA=T('甲','A'), NB=T('乙','B');
// ---- 格子：金属底板＋彩色自发光（彩色件 ≤ 0.35，光晕标准）----
const TILE_G=new THREE.BoxGeometry(1,1,0.06);
const TILES=[...Array(260)].map(()=>{ const m=new THREE.Mesh(TILE_G,new THREE.MeshStandardMaterial({color:0x0a0f18,emissive:0xffffff,emissiveIntensity:GLOW.emissive,metalness:0.55,roughness:0.35,transparent:true,opacity:0,depthWrite:false,depthTest:false})); m.visible=false; m.renderOrder=18; scene.add(m); return m; });
let tI=0;
function tile(p,w,h,col,o,dim=1){ const m=TILES[tI++]; if(!m) return null; m.visible=o>0.003; m.position.copy(p); m.quaternion.copy(camera.quaternion); m.scale.set(w,h,1); m.material.emissive.set(col).multiplyScalar(dim); m.material.color.set(col).multiplyScalar(0.12); m.material.opacity=o; return m; }
// ---- 格子上的字（甲／乙、A／B、数字）：每个字一张贴图，精灵池共用 ----
const LTX={}; const BLANK=new THREE.Texture();
function letTex(ch){ if(LTX[ch]) return LTX[ch]; const c=document.createElement('canvas'); c.width=c.height=160; const g=c.getContext('2d'); const cjk=/[㐀-鿿]/.test(ch);
  g.font=(cjk?'900 104px "VT Title","Noto Sans CJK SC",sans-serif':'900 104px "Inter Display","Inter",sans-serif'); g.textAlign='center'; g.textBaseline='middle';
  g.lineJoin='round'; g.lineWidth=10; g.strokeStyle='rgba(0,0,0,0.6)'; g.strokeText(ch,80,86); g.fillStyle='#ffffff'; g.fillText(ch,80,86);
  const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; t.anisotropy=8; return LTX[ch]=t; }
const LETS=[...Array(160)].map(()=>{ const s=new THREE.Sprite(new THREE.SpriteMaterial({map:BLANK,transparent:true,depthTest:false,depthWrite:false,opacity:0,color:0xe6e6e6})); s.renderOrder=24; s.visible=false; scene.add(s); return s; });
let lI=0;
function letter(ch,p,size,o){ const s=LETS[lI++]; if(!s) return; if(NOTEXT) o=0; s.visible=o>0.003; s.material.map=letTex(ch); s.material.opacity=o; s.position.copy(p); s.scale.set(size,size,1); }
// 一排序列格（镜头空间）：k＝点亮到第几格（可小数，逐格弹出）；letters：格上写甲乙
function seqRow(seq,x0,y,cw,o,{k=999,d=9,letters=true,gapR=0.14,hl=-1,dimFrom=999,pop=0.35}={}){
  const w=cw*(1-gapR); for(let i=0;i<seq.length;i++){ const on=ss(i,i+pop,k); if(on<=0.002) continue; const a=seq[i]==='A';
    const sc=0.55+0.45*on+0.18*(i===hl?1:0); const p=hp(x0+cw*(i+0.5),y+0.12*(1-on),d);
    const dim=i>=dimFrom?0.35:1; tile(p,w*sc,w*1.06*sc,a?GA:GB,o*on,dim);
    if(letters&&w>0.16) letter(a?NA:NB,p.clone().add(new THREE.Vector3(0,0,0.05).applyQuaternion(camera.quaternion)),w*0.82*sc,o*on*dim); } }
// 发球次数累计差（甲 − 乙）折线：每格一个点（镜头空间）
function diffLine(seq,x0,y0,cw,amp,o,k,col){ const pts=[hp(x0,y0)]; let d=0; for(let i=0;i<seq.length&&i<k;i++){ d+=seq[i]==='A'?1:-1; const f=clamp(k-i); pts.push(hp(x0+cw*(i+f),y0+amp*lerp(d-(seq[i]==='A'?1:-1),d,f))); }
  if(pts.length<2) pts.push(hp(x0+0.001,y0)); const l=ln(col,6); setLine(l,pts); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=21; return d; }
// ---- 发球：一分的动作＋球的飞行（k：这一分的进度 0–1）----
const BALL=makeBall(0.11);
const STAND={A:[0.6,12.4,Math.PI],B:[-0.6,-12.4,0]};   // [x,z,朝向]
function servePoint(who,k,o=1,{ballOn=true}={}){ const S=who==='A'?SRV:RET, R=who==='A'?RET:SRV, sgn=who==='A'?1:-1;
  applyPose(S,poseAt([[0,'sToss'],[0.22,'sTrophy'],[0.36,'sHit'],[0.62,'sFollow'],[1,'ready']],k)); applyPose(R,poseAt([[0,'ready'],[0.45,'split'],[0.7,'land'],[1,'ready']],k));
  const A0=V(STAND[who][0]+0.25*sgn,2.75,STAND[who][1]-0.35*sgn), B0=V(-STAND[who][0]*1.6,0.03,-sgn*5.2), C0=V(STAND[who==='A'?'B':'A'][0],1.0,STAND[who==='A'?'B':'A'][1]*0.92);
  let p; if(k<0.36) p=V(A0.x,lerp(1.4,3.1,Math.sin(k/0.36*Math.PI*0.5)),A0.z); else if(k<0.62){ const q=(k-0.36)/0.26; p=V(lerp(A0.x,B0.x,q),lerp(A0.y,0.05,q)+Math.sin(Math.PI*q)*0.25,lerp(A0.z,B0.z,q)); } else { const q=(k-0.62)/0.38; p=V(lerp(B0.x,C0.x,q),Math.sin(Math.PI*q*0.6)*1.2,lerp(B0.z,C0.z,q)); }
  showB(BALL,p,o*(ballOn?1:0),1); const g=gs(who==='A'?GA:GB,1.2,0.45*o*(ballOn?1:0)); g.position.copy(p); return p; }
// ---- 天平（世界坐标，挂在镜头前）：θ＞0 右边沉 ----
const SCALE=(()=>{ const G=new THREE.Group(); scene.add(G); const mt=new THREE.MeshStandardMaterial({color:0x1a2230,metalness:0.85,roughness:0.25,emissive:0x0a1a2a,emissiveIntensity:0.6,transparent:true,opacity:1});
  const post=new THREE.Mesh(new THREE.CylinderGeometry(0.06,0.09,2.6,20),mt); post.position.y=1.3; G.add(post);
  const base=new THREE.Mesh(new THREE.CylinderGeometry(0.7,0.8,0.12,40),mt); G.add(base);
  const piv=new THREE.Group(); piv.position.y=2.6; G.add(piv);
  const beam=new THREE.Mesh(new THREE.BoxGeometry(4.2,0.08,0.12),mt); piv.add(beam);
  const pans=[-1,1].map(s=>{ const h=new THREE.Group(); h.position.x=s*2.0; piv.add(h); const pan=new THREE.Mesh(new THREE.CylinderGeometry(0.7,0.55,0.08,40),mt); pan.position.y=-1.3; h.add(pan);
    const lg=new THREE.BufferGeometry().setFromPoints([V(0,0,0),V(-0.6,-1.27,0),V(0,0,0),V(0.6,-1.27,0),V(0,0,0),V(0,-1.27,0.6)]); const ls=new THREE.LineSegments(lg,new THREE.LineBasicMaterial({color:0x9fd8ff,transparent:true,opacity:0.6})); h.add(ls); return {h,pan,ls}; });
  const glow=new THREE.Mesh(new THREE.TorusGeometry(0.16,0.03,10,40),new THREE.MeshBasicMaterial({color:new THREE.Color(0xffc24a).multiplyScalar(GLOW.k),transparent:true})); glow.position.y=2.6; G.add(glow);
  return {G,piv,pans,mt,glow,set(theta,o){ G.visible=o>0.003; mt.opacity=o; glow.material.opacity=o; pans.forEach(p=>{ p.ls.material.opacity=0.6*o; }); piv.rotation.z=-theta; pans.forEach(p=>p.h.rotation.z=theta); }}; })();
const panPos=(s)=>SCALE.pans[s<0?0:1].pan.getWorldPosition(new THREE.Vector3());
// ---- 足球场：球门（白色门柱＋网格）、点球点 ----
const GOAL=(()=>{ const G=new THREE.Group(); scene.add(G); const W7=7.32, H2=2.44;
  const pm=new THREE.MeshStandardMaterial({color:0xe8eef4,emissive:0xffffff,emissiveIntensity:GLOW.emissiveWhite,metalness:0.3,roughness:0.4,transparent:true});
  const cyl=(a,b)=>{ const d=b.clone().sub(a); const m=new THREE.Mesh(new THREE.CylinderGeometry(0.06,0.06,d.length(),14),pm); m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(V(0,1,0),d.normalize()); G.add(m); };
  cyl(V(-W7/2,0,0),V(-W7/2,H2,0)); cyl(V(W7/2,0,0),V(W7/2,H2,0)); cyl(V(-W7/2,H2,0),V(W7/2,H2,0));
  const nl=[]; for(let x=-W7/2;x<=W7/2+1e-3;x+=0.3){ nl.push(x,H2,0, x,H2*0.75,-1.8, x,H2*0.75,-1.8, x,0,-2.0); } for(let y=0;y<=H2;y+=0.3){ const z=-2.0*(1-y/H2)-1.8*(y/H2)*0.4; nl.push(-W7/2,y,z,W7/2,y,z); }
  const ng=new THREE.BufferGeometry(); ng.setAttribute('position',new THREE.Float32BufferAttribute(nl,3));
  const net=new THREE.LineSegments(ng,new THREE.LineBasicMaterial({color:0xcfe6ff,transparent:true,opacity:0.25,blending:THREE.AdditiveBlending})); G.add(net);
  const pc=document.createElement('canvas'); pc.width=pc.height=512; const g=pc.getContext('2d'); for(let i=0;i<16;i++){ g.fillStyle=i%2?'#0d2a16':'#103320'; g.fillRect(0,i*32,512,32); } g.strokeStyle='rgba(235,245,255,0.75)'; g.lineWidth=4; g.strokeRect(96,0,320,170); g.strokeRect(186,0,140,58); g.fillStyle='rgba(235,245,255,0.85)'; g.beginPath(); g.arc(256,113,2.5,0,7); g.fill();
  const pt2=new THREE.CanvasTexture(pc); pt2.colorSpace=THREE.SRGBColorSpace;
  const pitch=new THREE.Mesh(new THREE.PlaneGeometry(40,40),new THREE.MeshStandardMaterial({map:pt2,roughness:0.9,transparent:true})); pitch.rotation.x=-Math.PI/2; pitch.position.set(0,-0.01,20-0.0); G.add(pitch);
  const bc=document.createElement('canvas'); bc.width=256; bc.height=128; const b=bc.getContext('2d'); b.fillStyle='#f2f4f6'; b.fillRect(0,0,256,128); b.fillStyle='#1a1f28'; for(const [x,y] of [[40,40],[120,30],[200,50],[80,95],[170,100],[240,95],[10,100]]){ b.beginPath(); for(let i=0;i<5;i++){ const a=i/5*6.283; b.lineTo(x+Math.cos(a)*14,y+Math.sin(a)*14); } b.fill(); }
  const bt2=new THREE.CanvasTexture(bc); bt2.colorSpace=THREE.SRGBColorSpace;
  const ball=new THREE.Mesh(new THREE.SphereGeometry(0.11,32,20),new THREE.MeshStandardMaterial({map:bt2,roughness:0.5,transparent:true})); G.add(ball);
  return {G,pm,net,pitch,ball,set(o){ G.visible=o>0.003; pm.opacity=o; net.material.opacity=0.25*o; pitch.material.opacity=o; ball.material.opacity=o; }}; })();
// ---- 2621 个抢七：点云排成两根柱 ----
function cloudBars(k,cols,o){ for(let i=0;i<1600;i++){ const p=PTS[i]; const b=i%cols.length; const [cx,cy,w,h,col]=cols[b]; const cc=new THREE.Color(col);
    const t=hp(cx+(p[3]-0.5)*w,cy+p[4]*h,9); const s=hp(p[0]*0.7,p[1]*0.5,9+p[2]*0.4); const e=ss(0,1,k*1.3-p[3]*0.3);
    cset(pt,i,lerp(s.x,t.x,e),lerp(s.y,t.y,e),lerp(s.z,t.z,e),cc.r,cc.g,cc.b,o*(0.5+0.5*e)); } cdone(pt); }

function hideAll(){
  courtG.visible=false; courtG.userData.mat.opacity=1; courtG.rotation.set(0,0,0);
  HUM.forEach(H=>{ humanOp(H,0); H.root.position.set(0,0,0); H.root.rotation.set(0,0,0); H.root.scale.setScalar(1); });
  BALLS.forEach(b=>{ b.m.visible=false; b.gl.visible=false; }); bI=0; BALL.m.visible=false; BALL.gl.visible=false;
  LN.forEach(l=>{ l.material.opacity=0; l.material.dashed=false; }); lnI=0; RG.forEach(r=>r.material.opacity=0); rgI=0; GS.forEach(s=>{ s.material.opacity=0; s.visible=false; }); gsI=0;
  TILES.forEach(m=>{ m.visible=false; }); tI=0; LETS.forEach(s=>{ s.visible=false; }); lI=0;
  for(const k in TT) op(TT[k],0); for(const k in TB) TB[k].g.visible=false; for(const k in text3D) t3op(text3D[k],0); chide(pt);
  beamMat.uniforms.uOp.value=0; rimL.intensity=0; rimR.intensity=0; DOF.on=false; MOTE_SPEED=1; SLOW=null;
  SCALE.set(0,0); SCALE.G.position.set(0,0,0); SCALE.G.rotation.set(0,0,0); SCALE.G.scale.setScalar(1); GOAL.set(0); ST_RATE=0.0003; }
// 3D 数字（Inter Display Black 挤出）：挂在镜头空间
function num(key,str,col,size,x,y,o,d=9){ const n=t3d(key,str,col,size); hud(n,x,y,d); t3op(n,o); return n; }
// 两名球员站位（场地镜头用）
function players(o){ humanOp(SRV,o); humanOp(RET,o); place(SRV,STAND.A[0],STAND.A[1],STAND.A[2]); place(RET,STAND.B[0],STAND.B[1],STAND.B[2]); applyPose(SRV,POSE.ready); applyPose(RET,POSE.ready); }
// 按序列一分一分地发：t 是从第一分开始的秒，per 每分秒数；返回当前第几分（整数）
function rally(seq,t,per,o){ if(t<0){ return -1; } const i=Math.min(seq.length-1,Math.floor(t/per)); const k=t>=seq.length*per?1:(t-i*per)/per; servePoint(seq[i],k,o,{ballOn:t<seq.length*per}); return i; }

// ---------- 1 钩子：218 比 204 砸下 → 三个抢七 7-5 7-4 7-3 → 场上发球光点按 1-2-2-2 跳 → 和一串数列前四位相同 → 更公平吗？ ----------
function shotHook(u,D){
  const PT=ev('pts',1.0), LO=ev('lose',3.2), TB1=ev('tb',5.2), TB3=ev('tb3',7.6), OR1=ev('order',10.0), ONE=ev('one',12.4), TWO=ev('two',14.6), WHY=ev('why',16.6), SQ=ev('seq',18.8), SAME=ev('same',20.2), Q=ev('q2',22.6);
  courtG.visible=true; ST_RATE=u<OR1?0.004:0.0006; rims(GO,CY,5); beamMat.uniforms.uOp.value=0.1;
  if(u<OR1-0.3){ // 夜里的中央球场，俯冲下来；218 与 204 两块金属大数字砸在网前
    const k=ss(0,OR1,u); look(lerp(-3,3,k),lerp(7.5,4.6,k),lerp(23,18.5,k),0,1.4,2); players(1);
    const a=ss(PT-0.1,PT+0.35,u), b=ss(PT+0.35,PT+0.8,u);
    const nF=num('h218','218',GO,1.25,-2.4,0.75+(1-a)*1.6,a*(1-ss(TB1-0.4,TB1,u))); const nD=num('h204','204',CY,1.25,2.4,0.75+(1-b)*1.6,b*(1-ss(TB1-0.4,TB1,u)));
    if(u>PT+0.3&&u<PT+1.6) shockRing(hp(-2.4,0.4),(u-PT-0.3)/1.3,GO,3.5,0.8,true); if(u>PT+0.75&&u<PT+2.1) shockRing(hp(2.4,0.4),(u-PT-0.75)/1.3,CY,3.5,0.8,true);
    const lo=ss(PT+0.4,PT+0.9,u)*(1-ss(TB1-0.4,TB1,u));
    lab('hkF',T('费德勒 · 总得分','Federer · total points'),-2.4,1.95,lo,{size:0.34,color:'#ffe2a0',glow:GOLD}); lab('hkD',T('德约科维奇 · 总得分','Djokovic · total points'),2.4,1.95,lo,{size:0.34});
    lab('hkY',T('2019 温网男单决赛','2019 Wimbledon men\'s final'),0,-1.1,lo,{size:0.32,plate:true});
    const L1=ss(LO,LO+0.4,u)*(1-ss(TB1-0.4,TB1,u)); lab('hkW',T('冠军','CHAMPION'),2.4,-0.35,L1,{size:0.46,color:'#ffffff',glow:CYAN});
    lab('hkM',T('多赢 14 分，却输了','14 more points — and lost'),-2.4,-0.35,L1,{size:0.4,color:'#ffd27a',glow:GOLD});
    // 三个抢七：逐个砸下（第三个最大），德约的颜色
    const TBS=[['7-5',-3.0],['7-4',0],['7-3',3.0]];
    TBS.forEach(([s,x],i)=>{ const t0=TB1+i*0.75+(i===2?Math.max(0,TB3-TB1-1.5):0); const e=ss(t0,t0+0.35,u); const sz=i===2?0.95:0.75;
      num('htb'+i,s,CY,sz,x,0.9+(1-e)*1.8,e*(1-ss(OR1-0.6,OR1-0.3,u))); if(u>t0+0.3&&u<t0+1.5) shockRing(hp(x,0.5),(u-t0-0.3)/1.2,CY,2.4,0.7,true);
      lab('htbL'+i,[T('第一盘','set 1'),T('第三盘','set 3'),T('第五盘 · 12 平之后','set 5 · after 12-12')][i],x,-0.05,e*(1-ss(OR1-0.6,OR1-0.3,u)),{size:0.3,color:i===2?'#ffffff':'#bcd0e4'}); });
    lab('htbT',T('三个抢七，全归德约','three tiebreaks, all Djokovic'),0,2.2,ss(TB1+0.2,TB1+0.6,u)*(1-ss(OR1-0.6,OR1-0.3,u)),{size:0.36});
    return; }
  // 拉到底线后方：甲在近端、乙在远端，发球光点按 1-2-2-2 跳；上方一排格子同步亮起
  const k2=ss(OR1-0.3,WHY,u); look(lerp(5,-3.5,k2),lerp(5.2,6.0,k2),lerp(19.5,19,k2),0,0.2,3.5); players(1);
  const seq=seqStr('ABBA',8); const per=0.82; const t0=ONE-0.9;
  if(u<WHY+0.4) rally(seq,u-t0,per,1-ss(WHY,WHY+0.4,u));
  const lit=(u-t0)/per; const o=ss(OR1-0.3,OR1+0.3,u)*(1-ss(Q-0.5,Q-0.1,u));
  const rowY=lerp(1.8,1.55,ss(SQ-0.4,SQ+0.4,u)); seqRow(seq,-3.2,rowY,0.8,o,{k:Math.max(0,lit+0.6)});
  lab('hkO1',T('先发的只发 1 分','first server: 1 point'),-2.8,2.5,o*ss(ONE,ONE+0.4,u)*(1-ss(TWO-0.2,TWO,u)),{size:0.32,color:'#ffe2a0',glow:GOLD});
  lab('hkO2',T('之后每人连发 2 分','then 2 each'),0.6,2.5,o*ss(TWO,TWO+0.4,u)*(1-ss(SQ-0.4,SQ,u)),{size:0.32});
  // 「一串数列」：下面再排一行 Thue–Morse，前四位连线变绿，第五位起分开
  const s2=ss(SQ-0.2,SQ+0.5,u); if(s2>0){ const tm=seqStr('TM',8); seqRow(tm,-3.2,rowY-1.15,0.8,o*s2,{k:(u-SQ+0.2)*7});
    const m=ss(SAME,SAME+0.6,u); for(let i=0;i<8;i++){ const same=tm[i]===seq[i]; if(i>=4&&!same){ const g=gs(RD,0.7,0.35*o*ss(SAME+0.5,SAME+1.0,u)); g.position.copy(hp(-3.2+0.8*(i+0.5),rowY-0.58)); } }
    const lk=ln(MT,8); setLine(lk,[hp(-3.2+0.05,rowY-0.58),hp(-3.2+0.05+3.2*m,rowY-0.58)]); lk.material.opacity=o*m; lk.material.depthTest=false; lk.renderOrder=21;
    lab('hkS1',T('前四位：完全相同','first four: identical'),-1.6,rowY-1.95,o*ss(SAME+0.2,SAME+0.6,u),{size:0.3,color:'#b8ffd8',glow:MINT});
    lab('hkS2',T('一串研究了一百多年的数列','a sequence studied for 100+ years'),2.6,rowY-1.95,o*s2,{size:0.28,color:'#c8d8ea'}); }
  const q=bt('hkQ',T('它真的让抢七更公平吗？','Does it make the tiebreak fairer?'),{size:0.85,glow:'rgba(255,194,74,0.5)',fx:'shock'}); hud(q,0,0.4,9); q.update(u,Q,D+5,0.85);
}

// ---------- 2 规则：平时一局一人发到底 → 抢七一分一换（甲｜乙乙｜甲甲…）→ 每 6 分换边 ----------
function shotRule(u,D){
  const G=ev('game',0.3), TB=ev('tb',4.6), CH=ev('ch',11.5);
  courtG.visible=true; rims(GO,CY,4); players(1); ST_RATE=0.0005;
  look(lerp(4,-3,ss(0,D,u)),5.0,19.5,0,0.3,3.5);
  if(u<TB-0.3){ // 一局：全是甲发，6 个球连着；上方一排金格
    const seq='AAAAAA'; rally(seq,u-G-0.2,0.66,1);
    seqRow(seq,-2.4,1.45,0.8,1-ss(TB-0.6,TB-0.3,u),{k:(u-G)/0.66+0.6});
    lab('ruG',T('平时：一局从头到尾一个人发','a normal game: one server throughout'),0,2.3,ss(G,G+0.4,u)*(1-ss(TB-0.6,TB-0.3,u)),{size:0.32,plate:true});
    return; }
  const seq=seqStr('ABBA',12); const per=Math.min(0.62,(CH+1.6-TB)/7); const t=u-TB+0.2; rally(seq,t,per,1);
  const o=1-ss(D-0.6,D-0.1,u); seqRow(seq,-4.8,1.45,0.8,o,{k:t/per+0.6});
  // 分隔竖线：1 | 2 3 | 4 5 | 6 7 …
  for(const b of [1,3,5,7,9,11]){ const e=ss(TB+b*per-0.4,TB+b*per,u); const l=ln(0xffffff,3); setLine(l,[hp(-4.8+0.8*b,1.02),hp(-4.8+0.8*b,1.88)]); l.material.opacity=0.6*o*e; l.material.depthTest=false; l.renderOrder=22; }
  lab('ruT',T('抢七：一分一换','tiebreak: switch point by point'),0,2.3,ss(TB,TB+0.4,u)*o,{size:0.32,plate:true});
  // 每 6 分换边：第 6、12 格下方亮一个「换边」
  for(const [i,key] of [[5,'ruC1'],[11,'ruC2']]){ const e=ss(TB+(i+1)*per-0.2,TB+(i+1)*per+0.2,u); lab(key,T('换边','change ends'),-4.8+0.8*(i+0.5),0.72,e*o,{size:0.26,color:'#b8ffd8',glow:MINT}); }
  lab('ruR',T('国际网联《网球规则》第 5 条、第 10 条','ITF Rules of Tennis, rules 5 and 10'),0,-1.55,ss(CH,CH+0.5,u)*o,{size:0.26,color:'#aab8c8'});
}

// ---------- 3 发球占优：64% / 68.5% → 一人一分时甲每到单数分领先、乙一直在追 → 1-2-2-2 多发的人来回换 ----------
function shotEdge(u,D){
  const PC=ev('pct',0.3), DJ=ev('dj',3.2), FD=ev('fd',5.0), AB=ev('abab',8.5), CH=ev('chase',12.5), BA=ev('abba',15.5);
  rims(GO,CY,4); const a=0.12*Math.sin(u*0.15); look(Math.sin(a)*9,0.4,Math.cos(a)*9,0,0.2,0);
  if(u<AB-0.3){ // 两根发球得分率柱，带一条 50% 线
    courtG.visible=false; const o=1-ss(AB-0.7,AB-0.3,u);
    const H=3.4, y0=-1.6; const l50=ln(0xffffff,2,true); setLine(l50,[hp(-3.6,y0+H*0.5),hp(3.6,y0+H*0.5)]); l50.computeLineDistances(); l50.material.dashSize=0.15; l50.material.gapSize=0.1; l50.material.opacity=0.55*o*ss(PC,PC+0.5,u); l50.material.depthTest=false;
    lab('egH',T('50%','50%'),-4.2,y0+H*0.5,0.8*o*ss(PC,PC+0.5,u),{size:0.28,color:'#c8d8ea'});
    const e1=ss(DJ-0.2,DJ+0.8,u), e2=ss(FD-0.2,FD+0.8,u);
    const b1=ln(CY,60); setLine(b1,[hp(-1.4,y0),hp(-1.4,y0+H*0.639*e1+0.001)]); b1.material.opacity=0.8*o*ss(0,0.05,e1); b1.material.depthTest=false;
    const b2=ln(GO,60); setLine(b2,[hp(1.4,y0),hp(1.4,y0+H*0.685*e2+0.001)]); b2.material.opacity=0.8*o*ss(0,0.05,e2); b2.material.depthTest=false;
    num('eg64','64%',CY,0.5,-1.4,y0+H*0.639*e1+0.55,o*e1); num('eg68','68.5%',GO,0.5,1.4,y0+H*0.685*e2+0.55,o*e2);
    lab('egD',T('德约 · 发球得分','Djokovic · serve points won'),-1.4,y0-0.35,o*e1,{size:0.28}); lab('egF',T('费德勒 · 发球得分','Federer · serve points won'),1.4,y0-0.35,o*e2,{size:0.28,color:'#ffe2a0',glow:GOLD});
    lab('egT',T('发球的人占优','the server has the edge'),0,2.25,o*ss(PC,PC+0.4,u),{size:0.42,color:'#ffffff'});
    lab('egS',T('2019 温网决赛 · 官方技术统计','2019 Wimbledon final · official stats'),0,1.75,o*ss(FD,FD+0.5,u),{size:0.24,color:'#aab8c8'});
    return; }
  // 账本：上面一排顺序格，下面一条「甲多发几个」的折线；先一人一分，再 1-2-2-2
  const m=ss(BA-0.4,BA+0.4,u); const o=ss(AB-0.3,AB+0.3,u);
  const seq=m<0.5?seqStr('ABAB',12):seqStr('ABBA',12); const per=m<0.5?(BA-0.5-AB)/12:(D-1.0-BA)/12; const t=m<0.5?(u-AB):(u-BA); const k=t/per;
  const x0=-4.8, cw=0.8, oo=o*(1-ss(BA-0.5,BA-0.3,u)*(1-ss(BA-0.3,BA+0.1,u)));
  seqRow(seq,x0,1.45,cw,oo,{k:k+0.6,letters:true});
  const zl=ln(0x9fb8d0,2); setLine(zl,[hp(x0,-0.4),hp(x0+cw*12,-0.4)]); zl.material.opacity=0.6*oo; zl.material.depthTest=false;
  lab('egZ',T('一样多','even'),x0-0.55,-0.4,0.8*oo,{size:0.24,color:'#aab8c8'}); lab('egP',T('甲多 1','A +1'),x0-0.55,0.55,0.8*oo,{size:0.24,color:'#ffe2a0',glow:GOLD}); lab('egN',T('乙多 1','B +1'),x0-0.55,-1.35,0.8*oo*m,{size:0.24});
  const dd=diffLine(seq,x0,-0.4,cw,0.95,oo,k,m<0.5?GO:MT);
  lab('egA',T('一人一分','one each'),0,2.3,oo*(1-ss(0.3,0.5,m)),{size:0.36,plate:true}); lab('egB',T('一、二、二、二','1-2-2-2'),0,2.3,oo*ss(0.5,0.7,m),{size:0.36,plate:true});
  const chase=ss(CH,CH+0.4,u)*(1-m); lab('egC',T('后发的人：一直在追','second server: always chasing'),2.0,-1.35,oo*chase,{size:0.32,color:'#ffb0a8',glow:RED});
  if(m<0.5&&u>CH){ for(let i=0;i<12;i+=2){ if(i<k){ const g=gs(RD,0.8,0.35*oo*chase*(0.6+0.4*Math.sin(u*6))); g.position.copy(hp(x0+cw*(i+1),-0.4+0.95)); } } }
  lab('egE',T('多发一个的人，来回换','the extra serve keeps switching'),2.0,-1.35,oo*ss(BA+1.5,BA+2.0,u),{size:0.32,color:'#b8ffd8',glow:MINT});
}

// ---------- 4 反转：两种顺序都是 50% → 净胜两分 → 补打不改结果 → 前 12 分各发 6 个 → 6 平后每组各一个 → 去掉它：53.6% ----------
function shotMath(u,D){
  const M0=ev('m0',0.3), CA=ev('calc',2.6), R1=ev('r1',4.6), R2=ev('r2',8.4), MD=ev('model',11.0), KEY=ev('key',13.6), EX=ev('ex',17.0), FI=ev('fill',19.5),
        TW=ev('twelve',23.0), AF=ev('after',27.0), RC=ev('race',32.0), MO=ev('more',34.5), PC=ev('pct',38.0);
  rims(GO,CY,4);
  if(u<EX-0.3){ // 天平：两种顺序各放一边，平；50% = 50%
    const a=0.1*Math.sin(u*0.2); look(Math.sin(a)*10,2.2,Math.cos(a)*10,0,1.6,0);
    const o=ss(M0,M0+0.6,u)*(1-ss(EX-0.7,EX-0.3,u)); SCALE.set(0.18*(1-ss(R2,R2+1.2,u))*Math.cos(u*2.2)*(1-ss(R1,R2,u))+0.0,o); SCALE.G.position.set(0,-0.6,0);
    const pl=panPos(-1), pr=panPos(1);
    lab('mtA',T('一人一分','one each'),null,0,o*ss(CA,CA+0.4,u),{size:0.42}).position.copy(pl).add(V(0,1.15,0));
    lab('mtB',T('一、二、二、二','1-2-2-2'),null,0,o*ss(CA,CA+0.4,u),{size:0.42,color:'#ffe2a0',glow:GOLD}).position.copy(pr).add(V(0,1.15,0));
    const n1=t3d('mt50a','50%',CY,0.62); n1.g.position.copy(pl).add(V(0,0.55,0)); n1.g.quaternion.copy(camera.quaternion); t3op(n1,o*ss(R1,R1+0.4,u));
    const n2=t3d('mt50b','50%',GO,0.62); n2.g.position.copy(pr).add(V(0,0.55,0)); n2.g.quaternion.copy(camera.quaternion); t3op(n2,o*ss(R2,R2+0.4,u));
    lab('mtAs',T('假设：两人一样强，发球都赢 65%','assume: equal players, each wins 65% on serve'),0,2.6,o*ss(CA,CA+0.4,u),{size:0.3,plate:true});
    lab('mtEq',T('顺序，没有改变输赢','the order changes nothing'),0,-1.55,o*ss(MD,MD+0.4,u)*(1-ss(KEY-0.4,KEY,u)),{size:0.4,color:'#ffffff'});
    lab('mtMd',T('「每分独立」模型 · 按假设推算','"independent points" model · computed'),0,-2.1+0.25,o*ss(MD,MD+0.4,u),{size:0.24,color:'#aab8c8'});
    const t=bt('mtKey',T('净胜两分','WIN BY TWO'),{size:1.05,glow:'rgba(255,194,74,0.55)',fx:'shock'}); hud(t,0,-1.2,9); t.update(u,KEY,EX-0.6,0.85);
    if(u>KEY+0.3&&u<KEY+1.6) shockRing(hp(0,-1.2),(u-KEY-0.3)/1.3,GO,4,0.6,true);
    return; }
  look(0,0.3,9.5,0,0.3,0);
  if(u<RC-0.3){ // 补打不改结果：12 格，一个 7 比 4 的抢七；第 12 分补成幽灵格；下面一排写发球人
    const o=ss(EX-0.3,EX+0.3,u)*(1-ss(RC-0.7,RC-0.3,u)); const x0=-4.9, cw=0.72;
    const WIN='AABABAABABA';   // 谁赢了这一分（甲 7、乙 4：第 11 分甲 7 比 4 赢下）——画成「得分小球」，和下面的「发球格」区分开
    const kk=(u-EX)/0.22; let sa=0, sb=0;
    for(let i=0;i<12;i++){ const ghost=i===11; const on=ghost?ss(FI,FI+0.5,u):ss(i,i+0.4,kk); if(on<=0) continue; const w=ghost?'?':WIN[i];
      const p=hp(x0+cw*(i+0.5),1.55); if(!ghost){ if(w==='A') sa++; else sb++; }
      const g=gs(ghost?0x9fb8d0:(w==='A'?GA:GB),ghost?0.75:0.95,(ghost?0.25:0.55)*o*on); g.position.copy(p);
      showB(BALLS[Math.min(5,bI++)]||BALL,p,0,1);
      letter(ghost?'?':(w==='A'?NA:NB),p,cw*0.5,o*on*(ghost?0.8:0.95)); }
    lab('mxT',T('每一分是谁赢的','who won each point'),x0+1.3,2.2,o*ss(EX,EX+0.4,u)*(1-ss(TW-0.4,TW,u)),{size:0.28,color:'#c8d8ea'});
    num('mx74','7 : 4',GO,0.55,4.4,1.55,o*ss(EX+2.4,EX+2.8,u)*(1-ss(FI,FI+0.4,u)));
    num('mx75','≥ 7',GO,0.55,4.4,1.55,o*ss(FI+0.5,FI+0.9,u)*(1-ss(TW-0.4,TW,u)));
    lab('mxF',T('补完 12 分：甲照样拿到 7 分以上，结果不变','play all 12: A still has 7+, same result'),0,0.75,o*ss(FI+0.3,FI+0.7,u)*(1-ss(TW-0.4,TW,u)),{size:0.34,color:'#ffe2a0',glow:GOLD});
    // 12 分里谁发球：两种顺序各一行，右边标名字
    const s=ss(TW-0.3,TW+0.4,u); if(s>0){ const r1=seqStr('ABAB',12), r2=seqStr('ABBA',12);
      seqRow(r1,x0,0.45,cw,o*s,{k:(u-TW)*14}); seqRow(r2,x0,-0.45,cw,o*s,{k:(u-TW-0.3)*14});
      lab('mxR1',T('一人一分','one each'),x0+cw*12+0.75,0.45,o*s,{size:0.24,color:'#c8d8ea'}); lab('mxR2',T('一二二二','1-2-2-2'),x0+cw*12+0.75,-0.45,o*s,{size:0.24,color:'#c8d8ea'});
      lab('mxS',T('谁发球','who serves'),x0+1.0,1.0,o*s*(1-ss(AF-0.4,AF,u)),{size:0.26,color:'#c8d8ea'});
      lab('mxC',T('两人各发 6 个','6 serves each'),0,2.2,o*ss(TW+1.2,TW+1.6,u)*(1-ss(AF-0.4,AF,u)),{size:0.38,color:'#b8ffd8',glow:MINT}); }
    const af=ss(AF-0.2,AF+0.4,u); if(af>0){ // 6 平之后：每两分一组
      for(let j=0;j<3;j++){ const xx=-2.6+j*1.8; seqRow('AB',xx,-1.4,0.62,o*af,{k:(u-AF)*6-j*2});
        const br=ln(MT,3); setLine(br,[hp(xx,-0.98),hp(xx,-0.93),hp(xx+1.24,-0.93),hp(xx+1.24,-0.98)]); br.material.opacity=o*af*ss(j*0.33,j*0.33+0.3,(u-AF)/1.2); br.material.depthTest=false; }
      lab('mxA',T('6 平之后：每两分一组，各发一个','after 6-6: pairs, one serve each'),0,2.2,o*af,{size:0.36,color:'#b8ffd8',glow:MINT}); }
    return; }
  // 去掉净胜两分：先到 7 分，最多 13 分；第 13 格是甲的，天平往甲那边沉
  const o=ss(RC-0.3,RC+0.3,u); const x0=-4.81, cw=0.74; const r=seqStr('ABAB',13), r2=seqStr('ABBA',13);
  seqRow(r,x0,1.35,cw,o,{k:(u-RC)*16,hl:12}); seqRow(r2,x0,0.5,cw,o,{k:(u-RC-0.25)*16,hl:12});
  const hl=ss(MO,MO+0.4,u); const g=gs(GO,1.3,0.45*o*hl); g.position.copy(hp(x0+cw*12.5,0.92));
  lab('mrT',T('改成先到 7 分就赢：最多 13 分（上：一人一分 · 下：一二二二）','first to 7, no margin: at most 13 points (top: one each · bottom: 1-2-2-2)'),0,2.2,o,{size:0.3,plate:true});
  lab('mrC',T('甲发 7 个 · 乙发 6 个','A serves 7 · B serves 6'),0,-0.25,o*hl,{size:0.36,color:'#ffe2a0',glow:GOLD});
  const p=ss(PC-0.2,PC+0.6,u); num('mr536','53.6%',GO,0.8,-1.6,-1.05,o*p); num('mr464','46.4%',CY,0.55,2.0,-1.05,o*p*0.85);
  lab('mrA',T('先发的人','first server'),-3.6,-1.05,o*p,{size:0.28,color:'#ffe2a0',glow:GOLD}); lab('mrB',T('后发的人','second server'),3.7,-1.05,o*p,{size:0.28});
  lab('mrS',T('两种顺序都一样 · 按发球赢 65% 推算','same for both orders · assuming 65% on serve'),0,-1.75,o*p,{size:0.24,color:'#aab8c8'});
}

// ---------- 5 那图什么：换手 11 次 vs 6 次 → 一直在追 → Thue–Morse 一层层长出来 → 每层轮流当先手 → 网球只抄第一层 ----------
function shotWhy(u,D){
  const SW=ev('sw',0.3), CN=ev('cnt',3.0), CHS=ev('ch',7.5), BU=ev('build',11.0), AB=ev('ab',13.2), AB2=ev('abba2',15.5), TM=ev('tm',19.0), HI=ev('hist',21.0),
        LY=ev('layer',26.0), EC=ev('econ',28.0), TN=ev('tennis',33.0), SP=ev('split',35.0);
  rims(GO,CY,4); const a=0.1*Math.sin(u*0.17); look(Math.sin(a)*9.5,0.3,Math.cos(a)*9.5,0,0.3,0);
  if(u<BU-0.3){ // 换手：两条轨道，球在两人之间跳；一人一分的折线来回 11 次，一二二二只有 6 次
    const o=ss(SW,SW+0.4,u)*(1-ss(BU-0.7,BU-0.3,u)); const x0=-4.6, cw=0.8;
    for(const [row,seq,yy,key,cnt] of [[0,seqStr('ABAB',12),1.3,'wyA',11],[1,seqStr('ABBA',12),-0.9,'wyB',6]]){
      const k=(u-SW-row*0.4)*7; const pts=[]; for(let i=0;i<12&&i<k;i++){ const yv=yy+(seq[i]==='A'?0.38:-0.38); pts.push(hp(x0+cw*(i+0.15),yv),hp(x0+cw*(i+0.85),yv)); }
      if(pts.length>=2){ const l=ln(row?MT:RD,7); setLine(l,pts); l.material.opacity=o; l.material.depthTest=false; l.renderOrder=21; }
      for(const s of [-1,1]){ const r=ln(0x9fb8d0,2); setLine(r,[hp(x0,yy+s*0.38),hp(x0+cw*12,yy+s*0.38)]); r.material.opacity=0.3*o; r.material.depthTest=false; }
      lab(key+'L',row?T('一、二、二、二','1-2-2-2'):T('一人一分','one each'),x0+1.2,yy+0.95,o,{size:0.3,color:row?'#b8ffd8':'#ffb0a8',glow:row?MINT:RED});
      num(key+'N',String(cnt),row?MT:RD,0.62,4.6,yy,o*ss(CN+row*0.6,CN+row*0.6+0.4,u)); }
    lab('wyT',T('12 分里，换几次发球','server switches in 12 points'),0,2.6,o,{size:0.34,plate:true});
    lab('wyP',T('一直在追的人，可能更紧张——这个，算不出来','chasing all the time may add pressure — math can\'t see that'),0,-1.75,o*ss(CHS,CHS+0.5,u),{size:0.3,color:'#ffd27a',glow:GOLD});
    return; }
  if(u<TN-0.3){ // Thue–Morse：每一行＝上一行接上它的反面（金青对调），一层层往下长成条码塔
    const o=ss(BU-0.3,BU+0.3,u)*(1-ss(TN-0.7,TN-0.3,u)); const Wd=8.4, xL=-Wd/2;
    const lvT=[BU, AB, AB2, TM, TM+1.0, TM+1.8, TM+2.5]; const yTop=2.05, dy=0.5;
    for(let n=0;n<7;n++){ const len=1<<n; const g=ss(lvT[n]-0.2,lvT[n]+0.5,u); if(g<=0) continue; const seq=seqStr('TM',len); const cw=Wd/64*(64/len)*0.5*(n===0?1:1);
      const rowW=Math.min(Wd, 0.8*len); const c2=rowW/len; const x0=-rowW/2;
      for(let i=0;i<len;i++){ const half=i>=len/2&&n>0; const e=half?ss(0,1,(g-0.15)*1.6):1; if(e<=0) continue; const xx=x0+c2*(i+0.5)+(half?(1-e)*2.4:0);
        const p=hp(xx,yTop-n*dy-(n>3?(n-3)*0.0:0)); tile(p,c2*0.86,Math.min(0.5,c2*0.95),seq[i]==='A'?GA:GB,o*(half?e:1));
        if(c2>=0.5) letter(seq[i]==='A'?NA:NB,p.clone().add(new THREE.Vector3(0,0,0.05).applyQuaternion(camera.quaternion)),c2*0.6,o*(half?e:1)); }
      if(n>0&&n<4){ const l=ln(0xffffff,2,true); setLine(l,[hp(0,yTop-n*dy+0.32),hp(0,yTop-n*dy-0.32)]); l.computeLineDistances(); l.material.dashSize=0.06; l.material.gapSize=0.05; l.material.opacity=0.5*o*g; l.material.depthTest=false; } }
    lab('tmR',T('接上它的反面','append its mirror'),3.4,2.05-0.5,o*ss(AB,AB+0.4,u)*(1-ss(TM-0.4,TM,u)),{size:0.3,color:'#ffe2a0',glow:GOLD});
    const t=bt('tmT',T('Thue–Morse 序列','THUE–MORSE'),{size:0.78,glow:'rgba(79,227,255,0.5)',fx:'weave',thread:'#7fe4ff'}); hud(t,0,-1.55,9); t.update(u,TM,LY-0.4,0.82);
    lab('tmH',T('1851 普鲁埃 · 1906 图厄 · 1921 莫尔斯','1851 Prouhet · 1906 Thue · 1921 Morse'),3.2,2.1,o*ss(HI,HI+0.5,u)*(1-ss(LY-0.4,LY,u)),{size:0.28,color:'#c8d8ea'});
    // 每一层都轮流当先手：两两一组框起来、四四一组框起来，组首的颜色交替
    const ly=ss(LY,LY+0.5,u); if(ly>0){ const len=16, rowW=8.0, c2=rowW/len, x0=-rowW/2, y=yTop-4*dy; for(const [gsz,yo,col] of [[2,-0.32,MT],[4,-0.46,OR]]){ const e=ss(LY+(gsz===4?1.2:0),LY+(gsz===4?1.7:0.5),u);
        for(let j=0;j<len/gsz;j++){ const b=ln(col,3); const xa=x0+c2*j*gsz+0.04, xb=x0+c2*(j+1)*gsz-0.04; setLine(b,[hp(xa,y+yo+0.08),hp(xa,y+yo),hp(xb,y+yo),hp(xb,y+yo+0.08)]); b.material.opacity=o*e; b.material.depthTest=false; b.renderOrder=22; } } }
    lab('tmL',T('两个一组、四个一组：先手都在轮换','in pairs, in fours: the first mover alternates'),0,-1.55,o*ly*(1-ss(EC-0.3,EC,u)),{size:0.32,color:'#b8ffd8',glow:MINT});
    lab('tmE',T('经济学家：两人轮流比赛，顺序怎么排才公平','economists: the fair order for taking turns'),0,-1.55,o*ss(EC,EC+0.4,u),{size:0.3});
    lab('tmE2',T('Palacios-Huerta 2012','Palacios-Huerta 2012'),3.6,2.1,o*ss(EC,EC+0.4,u),{size:0.24,color:'#aab8c8'});
    return; }
  // 网球只抄了第一层：两行对齐，前四位连线，第五位起红
  const o=ss(TN-0.3,TN+0.3,u); const tm=seqStr('TM',8), te=seqStr('ABBA',8); const x0=-3.6, cw=0.9;
  seqRow(tm,x0,1.2,cw,o,{k:(u-TN)*12}); seqRow(te,x0,-0.15,cw,o,{k:(u-TN-0.3)*12});
  lab('tnA',T('Thue–Morse','Thue–Morse'),x0-0.9,1.2,o,{size:0.3,color:'#c8d8ea'}); lab('tnB',T('网球抢七','tiebreak'),x0-0.9,-0.15,o,{size:0.3,color:'#ffe2a0',glow:GOLD});
  for(let i=0;i<8;i++){ const same=tm[i]===te[i]; const e=ss(SP-1.2+i*0.12,SP-0.9+i*0.12,u); const l=ln(i<4?MT:(same?0x9fb8d0:RD),i<4?6:4); setLine(l,[hp(x0+cw*(i+0.5),0.78),hp(x0+cw*(i+0.5),0.27)]); l.material.opacity=o*e*(i<4||!same?1:0.4); l.material.depthTest=false; }
  lab('tnS',T('前四位一样 · 第五位起分开','same for four · apart from the fifth'),0,-1.35,o*ss(SP,SP+0.4,u),{size:0.36,color:'#ffffff'});
}

// ---------- 6 足球：点球大战一人一脚 → 129 次先踢六成 → IFAB 2017 试行甲乙乙甲、2018 停掉 → 540 次测不出 ----------
function shotSoccer(u,D){
  const Q=ev('q',0.3), PK=ev('pk',2.6), S6=ev('s60',6.0), IF=ev('ifab',10.0), ST=ev('stop',13.0), BG=ev('big',16.0);
  rims(0x9fffc0,CY,4); GOAL.set(1); GOAL.G.position.set(0,0,0);
  const kk=ss(0,D,u); look(lerp(-2.2,2.2,kk),lerp(1.7,2.2,kk),lerp(15.5,14.0,kk),0,1.0,0);
  // 一人一脚：甲乙甲乙……球从点球点射向球门
  const per=1.1; const t=u-PK+0.4; const i=Math.max(0,Math.floor(t/per)); const k=t<0?0:(t-i*per)/per; const side=[0.6,-0.7,0.9,-1.0,0.2,-0.4,0.8,-0.9,0.5,-0.6][i%10];
  const spot=V(0,0.11,8.83); const tgt=V(side*3.0,0.5+0.8*Math.abs(side),-0.6); const kb=ss(0.1,0.55,k);
  GOAL.ball.position.copy(t<0?spot:spot.clone().lerp(tgt,kb)).add(V(0,Math.sin(kb*Math.PI)*0.4,0)); GOAL.ball.rotation.set(kb*8,kb*3,0);
  const who=i%2?'B':'A'; if(t>=0){ const g=gs(who==='A'?GA:GB,0.9,0.4*(1-kb*0.6)); g.position.copy(GOAL.ball.position); }
  const o=1-ss(D-0.5,D-0.1,u);
  const row=u<IF+0.6?seqStr('ABAB',10):seqStr('ABBA',10); seqRow(row,-4.0,1.55,0.8,o,{k:u<IF+0.6?(t/per+1):(u-IF-0.6)*8,hl:u<IF+0.6?i:-1});
  lab('scT',T('点球大战：一人一脚','penalty shootout: one kick each'),0,2.25,o*ss(Q,Q+0.4,u)*(1-ss(IF+0.2,IF+0.6,u)),{size:0.32,plate:true}); lab('scT2',T('2017 试行：甲乙乙甲','2017 trial: ABBA'),0,2.25,o*ss(IF+0.4,IF+0.8,u),{size:0.32,plate:true,color:'#ffe2a0',glow:GOLD});
  const p6=ss(S6-0.2,S6+0.5,u)*(1-ss(IF-0.4,IF,u)); num('sc60','60%',GO,0.9,-3.2,0.6,o*p6); lab('sc60L',T('先踢的一方赢了 · 129 次点球大战（2010）','first kickers won · 129 shootouts (2010)'),-1.6,-0.35,o*p6,{size:0.3,color:'#ffe2a0',glow:GOLD});
  const sf=0; const st=bt('scStop',T('2018 · 停掉','2018 · DROPPED'),{size:0.7,glow:'rgba(255,90,74,0.5)',fx:'sag'}); hud(st,2.4,0.35,9); st.update(u,ST,BG+1.6,0.82);
  lab('scIF',T('国际足球协会理事会（IFAB）','IFAB, football\'s lawmakers'),2.4,-0.45,o*ss(IF,IF+0.4,u)*(1-ss(BG+1.2,BG+1.6,u)),{size:0.28,color:'#c8d8ea'});
  const bg=ss(BG+1.4,BG+2.0,u); if(bg>0){ cloudBars(ss(BG+1.4,BG+3.0,u),[[-1.2,-1.6,1.4,1.5*1.0,GO],[1.2,-1.6,1.4,1.5*0.95,CY]],o*bg*0.8);
    lab('scBG',T('样本扩大到 540 次：先踢的优势，测不出来了（2012）','540 shootouts: no significant first-kicker edge (2012)'),0,0.25,o*ss(BG+1.6,BG+2.0,u),{size:0.32,color:'#ffffff'}); }
}

// ---------- 7 网球的真实数据：2621 个抢七，先发后发无显著区别 → 博客统计 50.8% / 49.7% ----------
function shotData(u,D){
  const DD=ev('d',0.3), RS=ev('res',3.2), BL=ev('blog',6.6);
  courtG.visible=true; courtG.userData.mat.opacity=0.4; rims(GO,CY,4); const kk=ss(0,D,u); look(lerp(-3,3,kk),9.5,15.5,0,0.5,0);
  const o=1-ss(D-0.5,D-0.1,u);
  if(u<BL-0.3){ const e=ss(DD,DD+2.2,u); cloudBars(e,[[-1.5,-1.55,1.6,3.1,GO],[1.5,-1.55,1.6,3.1,CY]],o*(1-ss(BL-0.7,BL-0.3,u)));
    num('dt2621','2621',WH,0.75,0,2.15,o*ss(DD,DD+0.5,u)*(1-ss(BL-0.7,BL-0.3,u))); lab('dtL',T('个抢七 · 2012–2015 · 巡回赛和大满贯','tiebreaks · 2012–2015 · tour and Slams'),0,1.45,o*ss(DD+0.2,DD+0.6,u)*(1-ss(BL-0.7,BL-0.3,u)),{size:0.28,color:'#c8d8ea'});
    lab('dtA',T('先发','served first'),-1.5,-1.8,o*e*(1-ss(BL-0.7,BL-0.3,u)),{size:0.3,color:'#ffe2a0',glow:GOLD}); lab('dtB',T('后发','served second'),1.5,-1.8,o*e*(1-ss(BL-0.7,BL-0.3,u)),{size:0.3});
    lab('dtR',T('赢面：没有显著区别 · 男女都一样','win chance: no significant difference · men and women'),0,0.75,o*ss(RS,RS+0.5,u)*(1-ss(BL-0.7,BL-0.3,u)),{size:0.34,color:'#b8ffd8',glow:MINT}); return; }
  const b=ss(BL-0.3,BL+0.6,u); const H=3.2, y0=-1.6; const l50=ln(0xffffff,2,true); setLine(l50,[hp(-3.4,y0+H*0.5),hp(3.4,y0+H*0.5)]); l50.computeLineDistances(); l50.material.dashSize=0.15; l50.material.gapSize=0.1; l50.material.opacity=0.55*o*b; l50.material.depthTest=false;
  const b1=ln(CY,56); setLine(b1,[hp(-1.3,y0),hp(-1.3,y0+H*0.508*b+0.001)]); b1.material.opacity=0.8*o; b1.material.depthTest=false;
  const b2=ln(GO,56); setLine(b2,[hp(1.3,y0),hp(1.3,y0+H*0.497*b+0.001)]); b2.material.opacity=0.8*o; b2.material.depthTest=false;
  num('dt508','50.8%',CY,0.5,-1.3,y0+H*0.508*b+0.5,o*b); num('dt497','49.7%',GO,0.5,1.3,y0+H*0.497*b+0.5,o*b);
  lab('dtM',T('男子巡回赛 · 先发的人赢','ATP · first server won'),-1.3,y0-0.3,o*b,{size:0.26}); lab('dtW',T('女子巡回赛 · 先发的人赢','WTA · first server won'),1.3,y0-0.3,o*b,{size:0.26,color:'#ffe2a0',glow:GOLD});
  lab('dtH',T('50%','50%'),-3.9,y0+H*0.5,0.8*o*b,{size:0.26,color:'#c8d8ea'});
  lab('dtS',T('博客统计（Tennis Abstract，2015），非同行评审','blog analysis (Tennis Abstract, 2015), not peer-reviewed'),0,2.55,o*b,{size:0.26,color:'#aab8c8'});
}

// ---------- 8 结论＋问句：场上再发一遍 1-2-2-2，每到双数分两人的计数一样 ----------
function shotEnd(u,D){
  const N0=ev('n0',0.3), TP=ev('tip',7.5), QQ=ev('q',11.5);
  courtG.visible=true; rims(GO,CY,5); beamMat.uniforms.uOp.value=0.1; players(1); ST_RATE=0.0008;
  const a=0.25+u*0.02; look(Math.sin(a)*20,7,Math.cos(a)*20,0,1.0,0);
  const t=bt('ndT',T('公平，靠的是净胜两分','Fairness comes from winning by two'),{size:0.85,glow:'rgba(255,194,74,0.5)',fx:'write'}); hud(t,0,2.1,9); t.update(u,N0+0.2,TP-0.4,0.82);
  const seq=seqStr('ABBA',8); const per=0.75; const tt=u-TP+0.2; if(u>TP-0.3&&u<QQ+1.5){ rally(seq,tt,per,1-ss(QQ+0.5,QQ+1.5,u)); const kk=tt/per; seqRow(seq,-3.2,2.05,0.8,1-ss(QQ-0.6,QQ-0.2,u),{k:kk+0.6});
    let a2=0,b2=0; for(let i=0;i<8&&i<kk;i++){ if(seq[i]==='A') a2++; else b2++; }
    const even=a2===b2&&kk>1; num('ndA'+a2,String(a2),GO,0.55,-1.0,0.95,(1-ss(QQ-0.6,QQ-0.2,u))); num('ndB'+b2,String(b2),CY,0.55,1.0,0.95,(1-ss(QQ-0.6,QQ-0.2,u)));
    lab('ndE',T('= 一样多','= even'),0,0.95,even?(1-ss(QQ-0.6,QQ-0.2,u)):0,{size:0.32,color:'#b8ffd8',glow:MINT}); }
  const q=bt('ndQ',T('你打抢七，喜欢先发还是后发？','In a tiebreak: serve first, or second?'),{size:0.72,glow:'rgba(79,227,255,0.45)',fx:'particles'}); hud(q,0,-1.3,9); q.update(u,QQ,D+5,0.82);
}

const SHOTS={hook:shotHook,rule:shotRule,edge:shotEdge,math:shotMath,why:shotWhy,soccer:shotSoccer,data:shotData,end:shotEnd};
function shotTest(u,D){ look(0,0,8,0,0,0); }
