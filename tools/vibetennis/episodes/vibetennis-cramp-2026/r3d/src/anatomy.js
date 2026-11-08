// ==================== EP11 抽筋：解剖资产 ====================
// 小腿特写 LEG（1 单位 ≈ 10 cm，示意，不是解剖比例尺）：膝在 y≈3.2，踝在 y≈-3，小腿肚朝 -z。
// 三条神经都通到左上方的「脊髓」段：Ia（肌梭→脊髓，油门）、Ib（高尔基腱器→脊髓，刹车）、α 运动神经（脊髓→肌纤维）。
// 神经冲动是沿通路跑的粒子：rate 决定有多少颗在跑、speed 决定跑多快；都只由 t 决定（确定性，分块渲染可续）。
const LEG=(()=>{
  const G=new THREE.Group(); scene.add(G); G.visible=false;
  const mk=(col)=>holoMat(col);
  const M={muscle:mk(0x4fe3ff), bone:mk(0xbcc8d8), tendon:mk(0xe8f4ff), foot:mk(0x9fb8d0), spine:mk(0xa78bfa)};
  const mesh=(geo,mat,x,y,z,sx=1,sy=1,sz=1)=>{ const m=new THREE.Mesh(geo,mat); m.position.set(x,y,z); m.scale.set(sx,sy,sz); G.add(m); return m; };
  const SPH=new THREE.SphereGeometry(1,40,28);
  // 骨：胫骨、腓骨（淡）
  mesh(new THREE.CylinderGeometry(0.17,0.2,6.4,16),M.bone,0,0.1,0.35); mesh(new THREE.CylinderGeometry(0.08,0.09,6.0,12),M.bone,0.42,0.0,0.05);
  mesh(SPH,M.bone,0,3.35,0.25,0.62,0.35,0.6);   // 膝（胫骨平台）
  // 肌肉：腓肠肌内外两个头、比目鱼肌
  const gL=mesh(SPH,M.muscle,-0.33,1.45,-0.55,0.55,1.75,0.55), gR=mesh(SPH,M.muscle,0.33,1.5,-0.5,0.52,1.7,0.52);
  const sol=mesh(SPH,M.muscle,0,-0.1,-0.35,0.72,1.55,0.42);
  // 跟腱、跟骨、脚
  const ach=mesh(new THREE.CylinderGeometry(0.27,0.16,1.9,16),M.tendon,0,-2.05,-0.55);
  mesh(SPH,M.bone,0,-3.25,-0.35,0.42,0.38,0.5);
  const foot=new THREE.Group(); foot.position.set(0,-3.15,0.1); G.add(foot);
  const fm=new THREE.Mesh(new THREE.CapsuleGeometry(0.42,2.0,8,16),M.foot); fm.rotation.x=Math.PI/2; fm.position.set(0,-0.15,1.0); fm.scale.set(1,1,0.55); foot.add(fm);
  // 肌纤维：70 根曲线，收缩时变短、鼓起
  const NF=70, NS=14, FIB=[]; let sd=4242; const rr=()=>{ sd=(sd*48271)%2147483647; return sd/2147483647; };
  for(let i=0;i<NF;i++){ const side=i%2?1:-1; FIB.push({x:side*(0.12+rr()*0.38), z:-0.5-rr()*0.32, top:2.9+rr()*0.35, ph:rr()*6.283}); }
  const fg=new THREE.BufferGeometry(); fg.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(NF*(NS-1)*2*3),3));
  const fibMat=new THREE.LineBasicMaterial({color:0x7fefff,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false});
  const fibers=new THREE.LineSegments(fg,fibMat); fibers.frustumCulled=false; G.add(fibers);
  // 肌梭（螺旋，油门）、高尔基腱器（腱上的网，刹车）
  const helix=[]; for(let i=0;i<=120;i++){ const a=i/120*Math.PI*14; helix.push(new THREE.Vector3(0.09*Math.cos(a),0.9+i/120*1.0,0.09*Math.sin(a))); }
  const spG=new THREE.BufferGeometry().setFromPoints(helix); const spMat=new THREE.LineBasicMaterial({color:0xffc24a,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false});
  const spindle=new THREE.Line(spG,spMat); spindle.position.set(-0.3,0,-0.62); G.add(spindle);
  const gtoMat=new THREE.MeshBasicMaterial({color:0x5aa8ff,wireframe:true,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false});
  const gto=new THREE.Mesh(new THREE.TorusKnotGeometry(0.2,0.05,80,8,2,5),gtoMat); gto.position.set(0,-1.2,-0.58); G.add(gto);
  // 脊髓段：左上方一截发光的柱子＋椎骨环
  const cordX=-3.0, cordZ=-1.6; mesh(new THREE.CylinderGeometry(0.22,0.22,3.0,20),M.spine,cordX,5.0,cordZ);
  for(let i=0;i<4;i++) mesh(new THREE.TorusGeometry(0.42,0.06,10,40),M.spine,cordX,3.9+i*0.75,cordZ).rotation.x=Math.PI/2;
  // 神经通路
  const C=(pts)=>new THREE.CatmullRomCurve3(pts.map(p=>new THREE.Vector3(...p)));
  const PATH={
    Ia:C([[-0.3,1.4,-0.62],[-0.7,2.3,-1.2],[-1.5,3.4,-1.5],[-2.4,4.6,-1.6],[cordX+0.15,5.1,cordZ]]),
    Ib:C([[0,-1.2,-0.58],[-0.6,0.0,-1.3],[-1.2,1.8,-1.7],[-2.1,3.9,-1.8],[cordX+0.15,5.6,cordZ]]),
    a :C([[cordX+0.15,4.6,cordZ],[-2.2,3.9,-1.3],[-1.2,3.0,-1.0],[-0.4,2.1,-0.85],[0.1,1.3,-0.8]])};
  const NL={}; for(const k in PATH){ const l=fatLine(k==='Ib'?0x5aa8ff:k==='Ia'?0xffc24a:0xff6a55,3); setLine(l,PATH[k].getPoints(60)); l.material.opacity=0; NL[k]=l; }
  // 冲动粒子
  const NP=600, imp=cloud(NP,0.5,22,scene,0); const ISEED=[...Array(NP)].map(()=>[rr(),rr(),rr()]);
  const st={op:0,c:0,ia:0,ib:0,mot:0,ankle:0};
  function update(t){
    G.visible=st.op>0.003; const o=st.op;
    const col=new THREE.Color(0x4fe3ff).lerp(new THREE.Color(0xff4a3a),st.c);
    for(const m of [gL,gR,sol]){ m.material.uniforms.uC.value.copy(col); }
    for(const k in M) M[k].uniforms.uOp.value=o*(k==='bone'?0.45:k==='muscle'?0.9:0.8);
    // 收缩：肌腹变短变鼓、抖动
    const sh=st.c*0.05*Math.sin(t*41)+st.c*0.03*Math.sin(t*67);
    gL.scale.set(0.55*(1+0.22*st.c)+sh,1.75*(1-0.12*st.c),0.55*(1+0.25*st.c)); gR.scale.set(0.52*(1+0.22*st.c)-sh,1.7*(1-0.12*st.c),0.52*(1+0.25*st.c));
    sol.scale.set(0.72*(1+0.1*st.c),1.55*(1-0.06*st.c),0.42*(1+0.15*st.c));
    foot.rotation.x=-st.ankle;                     // 正＝勾脚（拉伸），负＝绷脚（抽筋时脚尖被拉下）
    ach.scale.y=1+0.12*Math.max(0,st.ankle);
    const P=fg.attributes.position.array; let q=0;
    for(const f of FIB){ const top=f.top-0.35*st.c, bot=-1.25, bulge=0.12+0.22*st.c;
      let px,py,pz; for(let s=0;s<NS;s++){ const k=s/(NS-1); const y=lerp(top,bot,k); const b=Math.sin(Math.PI*k)*bulge; const x=f.x*(1-0.7*k*k), z=f.z-b+0.02*st.c*Math.sin(t*50+f.ph);
        if(s>0){ P[q++]=px;P[q++]=py;P[q++]=pz;P[q++]=x;P[q++]=y;P[q++]=z; } px=x;py=y;pz=z; } }
    fg.attributes.position.needsUpdate=true; fibMat.opacity=o*0.55; fibMat.color.copy(col).lerp(new THREE.Color(0xffffff),0.35);
    spMat.opacity=o*(0.35+0.65*st.ia); gtoMat.opacity=o*(0.25+0.75*st.ib); gto.rotation.y=t*0.6;
    NL.Ia.material.opacity=o*(0.25+0.6*st.ia); NL.Ib.material.opacity=o*(0.25+0.6*st.ib); NL.a.material.opacity=o*(0.25+0.6*st.mot);
    // 冲动：前 1/3 跑 Ia、中 1/3 跑 Ib、后 1/3 跑 α；rate 控制亮起的颗数
    const cs={Ia:[1,0.76,0.29],Ib:[0.35,0.66,1],a:[1,0.35,0.28]};
    for(let i=0;i<NP;i++){ const [s0,s1,s2]=ISEED[i]; const k=i<200?'Ia':i<400?'Ib':'a'; const rate=k==='Ia'?st.ia:k==='Ib'?st.ib:st.mot;
      const on=s1<rate; const sp=0.35+1.4*rate; const u=(s0+t*sp*0.5)%1; const p=PATH[k].getPointAt(u);
      const c=cs[k]; cset(imp,i,p.x,p.y,p.z,c[0],c[1],c[2],on?o*(0.6+0.4*s2):0); }
    cdone(imp); }
  return {G,st,update,PATH,imp,gL,gR,sol,gto,spindle,foot,cord:new THREE.Vector3(cordX,5.0,cordZ),hide(){ st.op=0; G.visible=false; for(const k in NL) NL[k].material.opacity=0; chide(imp); fibMat.opacity=0; spMat.opacity=0; gtoMat.opacity=0; }};
})();

// 消化道（挂在全息人身上，单位 m）：嘴→食道→胃→小肠；用来跟「嘴里的神经信号」比速度
const GUT=(()=>{
  const G=new THREE.Group(); scene.add(G); G.visible=false; const mat=holoMat(0x34f5a8);
  const C=(pts)=>new THREE.CatmullRomCurve3(pts.map(p=>new THREE.Vector3(...p)));
  const eso=C([[0,1.62,0.08],[0,1.5,0.02],[0,1.38,0.0],[0.02,1.28,0.02]]);
  const stomach=new THREE.Mesh(new THREE.SphereGeometry(1,28,20),mat); stomach.scale.set(0.11,0.07,0.06); stomach.position.set(0.05,1.22,0.04); G.add(stomach);
  const coil=[]; for(let i=0;i<=60;i++){ const a=i/60*Math.PI*6; coil.push([0.05+0.08*Math.cos(a)*(1-i/120),1.12-i/60*0.18,0.05+0.05*Math.sin(a)]); }
  const gut=C(coil);
  const tube=new THREE.Mesh(new THREE.TubeGeometry(gut,120,0.012,8,false),mat); G.add(tube);
  const et=new THREE.Mesh(new THREE.TubeGeometry(eso,30,0.01,8,false),mat); G.add(et);
  return {G,mat,eso,gut,stomach,set(o){ mat.uniforms.uOp.value=o; G.visible=o>0.003; }};
})();
