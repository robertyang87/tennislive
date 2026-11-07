// ---- 球场周边：中央球场看台（所有者 2026-11-07「要把球场周边看台渲染出来，比较有沉浸感」）----
// 1 单位 = 1 m。下层看台 20 排、LED 腰带、上层看台 24 排、顶沿灯环；场边一圈发光挡板；约两万名观众（坐姿低模）。
// 看台跟着 courtG 一起显隐、一起淡；离镜头 3~6 m 内的东西做抖动消隐（侧面机位在看台里，不让人头糊在镜头上）。
// 赛点那几秒观众席闪光灯变密（standsTick）。全部用自带的确定性随机，不动底座 frnd 的序列。
let ST_F, ST_TOP, ST_FL, ST_N=0; const ST_MATS=[];
const ST=(()=>{
  let sd=90210; const rr=()=>{ sd=(sd*48271)%2147483647; return sd/2147483647; };
  const G=new THREE.Group(); courtG.add(G);
  const near=(mat,a=3.5,b=5.0)=>{ mat.onBeforeCompile=(sh)=>{
      sh.vertexShader=sh.vertexShader.replace('#include <common>','#include <common>\nvarying float vD;').replace('#include <project_vertex>','#include <project_vertex>\nvD=-mvPosition.z;');
      sh.fragmentShader=sh.fragmentShader.replace('#include <common>','#include <common>\nvarying float vD;').replace('#include <clipping_planes_fragment>',
        `#include <clipping_planes_fragment>\n{ float k=smoothstep(${a.toFixed(1)},${b.toFixed(1)},vD); float h=fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453); if(h>k) discard; }`);
      sh.fragmentShader=sh.fragmentShader.replace('#include <fog_fragment>','#include <fog_fragment>\ngl_FragColor.rgb*=mix(1.0,0.45,smoothstep(25.0,75.0,vD));');   /* 远处的看台压暗：空气感 */
    }; return mat; };
  // 圆角矩形一圈，按弧长等分 n 个点（返回 [x,z,法线x,法线z]）
  function ring(a,b,rc,n){ const P=[]; const seg=(x0,z0,x1,z1)=>{ for(let i=0;i<24;i++){ const k=i/24; P.push([lerp(x0,x1,k),lerp(z0,z1,k)]); } };
    const arc=(cx,cz,t0)=>{ for(let i=0;i<24;i++){ const t=t0+i/24*Math.PI/2; P.push([cx+rc*Math.cos(t),cz+rc*Math.sin(t)]); } };
    seg(a,-(b-rc),a,b-rc); arc(a-rc,b-rc,0); seg(a-rc,b,-(a-rc),b); arc(-(a-rc),b-rc,Math.PI/2); seg(-a,b-rc,-a,-(b-rc)); arc(-(a-rc),-(b-rc),Math.PI); seg(-(a-rc),-b,a-rc,-b); arc(a-rc,-(b-rc),Math.PI*1.5);
    const cum=[0]; for(let i=1;i<=P.length;i++){ const p=P[i%P.length], q=P[i-1]; cum.push(cum[i-1]+Math.hypot(p[0]-q[0],p[1]-q[1])); }
    const tot=cum[cum.length-1], out=[]; let j=0;
    for(let i=0;i<n;i++){ const s=i/n*tot; while(cum[j+1]<s) j++; const p=P[j], q=P[(j+1)%P.length], k=(s-cum[j])/Math.max(1e-6,cum[j+1]-cum[j]);
      const x=lerp(p[0],q[0],k), z=lerp(p[1],q[1],k), tx_=q[0]-p[0], tz=q[1]-p[1], tl=Math.hypot(tx_,tz)||1; out.push([x,z,tz/tl,-tx_/tl]); }
    return {pts:out,len:tot}; }
  // 排：[内沿 a, b, 圆角, 台面高度, 台面深度]
  const ROWS=[]; { let a=11.6,b=21.2,rc=6.0,y=1.1; for(let r=0;r<20;r++){ ROWS.push([a,b,rc,y,0.85,'lo']); a+=0.85; b+=0.85; rc+=0.85; y+=0.42; }
    const fasciaA=a, fasciaB=b, fasciaRc=rc, fasciaY=y; ST_F=[fasciaA,fasciaB,fasciaRc,fasciaY];
    a+=1.4; b+=1.4; rc+=1.4; y+=1.9; for(let r=0;r<24;r++){ ROWS.push([a,b,rc,y,0.78,'hi']); a+=0.78; b+=0.78; rc+=0.78; y+=0.56; } ST_TOP=[a,b,rc,y]; }
  // 台阶：每排一条踏面＋一条立面（同一份几何），台沿一条细光线
  { const N=480, pos=[], idx=[], edge=[]; let base=0;
    for(let r=0;r<ROWS.length;r++){ const [a,b,rc,y,dp]=ROWS[r]; const A=ring(a,b,rc,N).pts, B=ring(a+dp,b+dp,rc+dp,N).pts; const yPrev=r? (ROWS[r][5]===ROWS[r-1][5]? ROWS[r-1][3] : y-1.9) : 0;
      for(let i=0;i<N;i++){ pos.push(A[i][0],yPrev,A[i][1], A[i][0],y,A[i][1], B[i][0],y,B[i][1]); }
      for(let i=0;i<N;i++){ const i2=(i+1)%N, o=base; const p0=o+i*3, p1=o+i2*3;
        idx.push(p0,p1,p0+1, p1,p1+1,p0+1,  p0+1,p1+1,p0+2, p1+1,p1+2,p0+2);
        if(r<20||r%2===0) edge.push(A[i][0],y+0.01,A[i][1],A[i2][0],y+0.01,A[i2][1]); }
      base+=N*3; }
    const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.setIndex(idx); g.computeVertexNormals();
    const m=new THREE.Mesh(g,near(new THREE.MeshLambertMaterial({color:0x0e1a30,side:THREE.DoubleSide,transparent:true}))); m.frustumCulled=false; G.add(m);
    const eg=new THREE.BufferGeometry(); eg.setAttribute('position',new THREE.Float32BufferAttribute(edge,3));
    const el=new THREE.LineSegments(eg,new THREE.LineBasicMaterial({color:0x5fc8ff,transparent:true,opacity:0.16,blending:THREE.AdditiveBlending,depthWrite:false})); el.frustumCulled=false; G.add(el);
    ST_MATS.push([m.material,1],[el.material,0.16]); }
  // 地面（场地外一圈深色硬地）＋场边挡板（发光广告带，不印任何品牌）
  { const fl=new THREE.Mesh(new THREE.PlaneGeometry(140,160),near(new THREE.MeshLambertMaterial({color:0x070d1a,transparent:true}))); fl.rotation.x=-Math.PI/2; fl.position.y=-0.02; fl.renderOrder=-2; G.add(fl); ST_MATS.push([fl.material,1]);
    const mkWall=(a,b,rc,y0,h,color,ei)=>{ const R=ring(a,b,rc,400).pts, pos=[], idx=[]; for(let i=0;i<R.length;i++){ pos.push(R[i][0],y0,R[i][1],R[i][0],y0+h,R[i][1]); }
      for(let i=0;i<R.length;i++){ const i2=(i+1)%R.length; idx.push(i*2,i2*2,i*2+1,i2*2,i2*2+1,i*2+1); }
      const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3)); g.setIndex(idx); g.computeVertexNormals();
      const m=new THREE.Mesh(g,near(new THREE.MeshStandardMaterial({color:0x0a1426,emissive:color,emissiveIntensity:ei,roughness:0.6,side:THREE.DoubleSide,transparent:true}))); m.frustumCulled=false; G.add(m); ST_MATS.push([m.material,1]); return m; };
    mkWall(11.3,20.9,5.7,0,1.1,0x1d5fb0,GLOW.emissive*0.9);                 // 场边挡板
    mkWall(ST_F[0],ST_F[1],ST_F[2],ST_F[3]-0.1,1.5,0x0a0f1c,0);           // 下层看台顶的墙
    mkWall(ST_F[0]+0.02,ST_F[1]+0.02,ST_F[2]+0.02,ST_F[3]+0.35,0.45,0x2a8cff,GLOW.emissive*1.3);   // LED 腰带
    mkWall(ST_TOP[0],ST_TOP[1],ST_TOP[2],ST_TOP[3]-0.2,2.4,0x0a0f1c,0);   // 顶沿
  }
  // 观众：坐姿低模（身子一个盒、头一个球），每排按弧长 0.6 m 一个，过道（每圈 28 条）空着、约一成空座
  { const people=[]; for(const [a,b,rc,y,dp,lvl] of ROWS){ const R0=ring(a,b,rc,8); const n=Math.floor(R0.len/0.6); const R=ring(a+dp*0.55,b+dp*0.55,rc+dp*0.55,n).pts;
      for(let i=0;i<n;i++){ const f=i/n*28; if(f-Math.floor(f)<0.06) continue; if(rr()<0.1){ rr(); continue; } people.push([R[i][0],y,R[i][1],R[i][2],R[i][3],rr()]); } }
    const n=people.length, body=new THREE.BoxGeometry(0.44,0.62,0.32), head=new THREE.IcosahedronGeometry(0.12,1);
    const mB=new THREE.InstancedMesh(body,near(new THREE.MeshLambertMaterial({transparent:true})),n), mH=new THREE.InstancedMesh(head,near(new THREE.MeshLambertMaterial({transparent:true})),n);
    const SH=[0x1b2a4a,0x2a3346,0x3b4458,0x6b7488,0x8a2b3a,0x1f5a8a,0x9a8a3a,0x2f6a4a,0x5a3a7a,0xb0b6c2,0x14203a,0x22304e], SK=[0x6a5040,0x8a6a55,0x4a3428,0x9a7a60];
    const o=new THREE.Object3D(), c=new THREE.Color(), heads=[];
    for(let i=0;i<n;i++){ const [x,y,z,nx,nz,s]=people[i]; const yaw=Math.atan2(-nx,-nz)+ (s-0.5)*0.5, jitter=(s*7919%1-0.5)*0.12;
      o.position.set(x+nx*jitter,y+0.33,z+nz*jitter); o.rotation.set(0,yaw,0); o.scale.setScalar(0.9+s*0.2); o.updateMatrix(); mB.setMatrixAt(i,o.matrix);
      c.setHex(SH[Math.floor(s*997)%SH.length]).lerp(new THREE.Color(0x1a2438),0.35).multiplyScalar(0.42); mB.setColorAt(i,c);
      o.position.y=y+0.33+0.44*(0.9+s*0.2); o.updateMatrix(); mH.setMatrixAt(i,o.matrix); heads.push(o.position.x-nx*0.32,o.position.y+0.05,o.position.z-nz*0.32);   /* 手机举在脸前，朝场内 */
      c.setHex(SK[Math.floor(s*331)%SK.length]).multiplyScalar(0.45); mH.setColorAt(i,c); }
    for(const m of [mB,mH]){ m.frustumCulled=false; m.instanceMatrix.needsUpdate=true; m.instanceColor.needsUpdate=true; G.add(m); ST_MATS.push([m.material,1]); }
    // 闪光灯：每个观众头顶一个点，uT 每 1/20 s 换一次谁在闪；uRate 是单人单步的闪光概率
    const seed=new Float32Array(n); for(let i=0;i<n;i++) seed[i]=rr()*1000;
    const fg=new THREE.BufferGeometry(); fg.setAttribute('position',new THREE.Float32BufferAttribute(heads,3)); fg.setAttribute('aS',new THREE.BufferAttribute(seed,1));
    ST_FL=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uT:{value:0},uRate:{value:0.0004},uOp:{value:1},uPx:{value:H/2}},
      vertexShader:`attribute float aS; uniform float uT,uRate,uPx; varying float vA; float h(float x){ return fract(sin(x)*43758.5453); }
        void main(){ vec4 mv=modelViewMatrix*vec4(position,1.); float r=h(aS*1.37+uT*17.13); vA= r<uRate ? 0.55+0.45*h(aS+uT) : 0.0; gl_PointSize= vA>0.0 ? 0.9*projectionMatrix[1][1]*uPx/max(1.0,-mv.z) : 0.0; gl_Position=projectionMatrix*mv; }`,
      fragmentShader:`uniform float uOp; varying float vA; void main(){ if(vA<=0.0) discard; vec2 p=gl_PointCoord-0.5; float d=length(p)*2.0; float a=pow(max(0.0,1.0-d),2.2); gl_FragColor=vec4(vec3(1.0,0.97,0.9)*a*vA*uOp*0.9,a*vA*uOp); }`});
    const fp=new THREE.Points(fg,ST_FL); fp.frustumCulled=false; G.add(fp); ST_N=n; }
  // 顶沿灯环：一圈灯点（小光晕），照向场内
  { const R=ring(ST_TOP[0]-0.3,ST_TOP[1]-0.3,ST_TOP[2]-0.3,64).pts; for(const [x,z] of R){ const s=glowSprite(0xdfeaff,1.6,0.32,G); s.position.set(x,ST_TOP[3]+1.4,z); ST_MATS.push([s.material,0.32]); } }
  return G; })();
// 每帧（shot 跑完之后）：看台跟 courtG 的显隐与淡出；赛点那几秒闪光灯变密
function standsTick(t,kind,u){ ST.visible=courtG.visible; if(!ST.visible) return; const o=courtG.userData.mat.opacity;
  for(const [m,b] of ST_MATS) m.opacity=b*o;
  let rate=0.0003; if(kind==='hook'){ const a=ev('court',7.7), b=ev('run',16.5); rate=lerp(0.0003,0.006,ss(a,a+1.0,u)*(1-ss(b+1.0,b+2.5,u))); }
  ST_FL.uniforms.uRate.value=rate; ST_FL.uniforms.uT.value=Math.floor(t*20); ST_FL.uniforms.uOp.value=o; }
