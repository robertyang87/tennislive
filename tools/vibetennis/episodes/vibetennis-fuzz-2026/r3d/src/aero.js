// ==================== EP11 阻力危机：空气动力资产 ====================
// FLOW：绕球的烟线（二维势流绕圆柱近似 + 分离点之后的尾流），sep＝分离角（从迎风驻点量，度）。
//   层流（光滑球、低速）约 80°：尾流宽；湍流（过了阻力危机）约 120°：尾流窄——示意，画面标「示意」。
// CURVE：阻力系数 Cd 对雷诺数 Re 的经典曲线（光滑球带「悬崖」、高尔夫提前跳崖、网球一路平），点在线上滑。
// BL：光滑球、高尔夫球（凹坑）、足球（拼块）、网球（绒毛壳）。TOWER：埃菲尔铁塔线框。
const FLOW=(()=>{
  const NS=34, PTS_PER=46, LEN=7.0; const lines=[];
  // 预先积分流线：圆柱半径 1，来流沿 +x，速度 1；分离后沿分离处切线方向直行、再慢慢回正
  function streamline(y0,sepDeg){ const pts=[]; let x=-LEN, y=y0; const dt=0.04; const sep=sepDeg*Math.PI/180; let sepd=false, vy0=0;
    for(let i=0;i<900 && x<LEN;i++){ const r2=x*x+y*y; const r4=r2*r2;
      let u=1-(x*x-y*y)/r4, v=-2*x*y/r4;
      const ang=Math.atan2(Math.abs(y),-x);   // 从迎风驻点（-x 方向）量起的角度
      if(!sepd && r2<1.9 && ang>sep && x>-0.2){ sepd=true; vy0=v; }
      if(sepd){ u=1; v=vy0*Math.exp(-(x)*0.6); }
      x+=u*dt; y+=v*dt; if(r2<1.0005){ const s=Math.sqrt(1.0005/r2); x*=s; y*=s; }
      if(i%3===0) pts.push([x,y]); }
    return pts; }
  function build(sepDeg){ const out=[]; for(let i=0;i<NS;i++){ const y0=(i/(NS-1)-0.5)*4.4; if(Math.abs(y0)<0.04) continue; out.push(streamline(y0,sepDeg)); } return out; }
  const cache={}; const get=(s)=>cache[s]||(cache[s]=build(s));
  // 流线本身画成细线（同一分离角共用一份几何），粒子在线上流动
  const LG=new THREE.Group(); scene.add(LG); const LMAT=new THREE.LineBasicMaterial({color:0x6fc8ff,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false});
  const lcache={}; function lineObj(sep){ if(lcache[sep]) return lcache[sep]; const L=get(sep), seg=[]; for(const ln of L){ for(let i=0;i<ln.length-1;i++) seg.push(ln[i][0],ln[i][1],0,ln[i+1][0],ln[i+1][1],0); }
    const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(seg,3)); const o=new THREE.LineSegments(g,LMAT); o.frustumCulled=false; o.visible=false; LG.add(o); lcache[sep]=o; return o; }
  const P=cloud(2600,0.09,9,scene,0); let sd=777; const rr=()=>{ sd=(sd*48271)%2147483647; return sd/2147483647; };
  const SEED=[...Array(2600)].map(()=>[rr(),rr(),rr(),rr()]);
  // c：球心；R：球半径（世界单位）；sep：分离角；turb：尾流的乱度；o：透明度；t：时间；col：颜色；z0：烟线所在的面（离球心的深度偏移）
  function draw(c,R,sep,turb,o,t,col=0x9fd8ff,speed=0.45,lineO=0.3,skew=0){ const L=get(Math.round(sep)); for(const k in lcache) lcache[k].visible=false; const lo=lineObj(Math.round(sep)); lo.visible=o>0.003; lo.position.copy(c); lo.scale.setScalar(R); LMAT.opacity=o*lineO; const cc=new THREE.Color(col), wc=new THREE.Color(0xffd27a);
    const wake=Math.sin(sep*Math.PI/180);   // 尾流半宽（以 R 计）
    for(let i=0;i<2600;i++){ const s=SEED[i]; if(i<2000){ const line=L[i%L.length]; const f=(s[0]+t*speed*(0.9+0.2*s[1]))%1; const k=f*(line.length-1), a=Math.floor(k), w=k-a; const p0=line[a], p1=line[Math.min(line.length-1,a+1)];
        const x=lerp(p0[0],p1[0],w), y=lerp(p0[1],p1[1],w); const fade=Math.min(1,f*6,(1-f)*6);
        cset(P,i,c.x+x*R,c.y+y*R,c.z,cc.r,cc.g,cc.b,o*fade*0.95); }
      else { // 尾流里的涡：在分离之后、宽度 wake 的区域里打转
        const f=(s[0]+t*0.35)%1; const x=0.4+f*5.0; const amp=wake*(0.75+0.25*Math.sin(x*1.3)); const ph=s[1]*6.283+t*(2+3*turb)+x*1.7;
        const y=Math.sin(ph)*amp*(0.25+0.75*s[2])*(1+0.15*turb*Math.sin(t*7+s[3]*20)); const z=Math.cos(ph)*amp*0.5*s[2];
        cset(P,i,c.x+x*R,c.y+(y+skew*x*0.35)*R,c.z+z*R,wc.r,wc.g,wc.b,o*0.7*(1-f)*Math.min(1,f*8)); } }
    cdone(P); }
  return {draw,hide(){ chide(P); for(const k in lcache) lcache[k].visible=false; }};
})();

// Cd–Re 曲线（屏幕上的全息图表；数据点按文献量级手描，画面标「示意」，具体数字只在 sources.md 核过的才上屏）
const CURVE=(()=>{
  const smooth=[[4.0,0.5],[4.6,0.5],[5.0,0.5],[5.3,0.49],[5.4,0.44],[5.47,0.25],[5.53,0.12],[5.6,0.1],[5.9,0.12],[6.2,0.16]];
  const golf=[[4.0,0.47],[4.4,0.46],[4.6,0.40],[4.75,0.27],[4.9,0.24],[5.1,0.25],[5.4,0.27],[5.7,0.28],[6.2,0.29]];
  const tennis=[[4.0,0.66],[4.6,0.65],[5.0,0.63],[5.2,0.6],[5.4,0.59],[5.6,0.58],[5.9,0.58],[6.2,0.58]];
  const at=(arr,lx)=>{ for(let i=0;i<arr.length-1;i++){ const [a,b]=[arr[i],arr[i+1]]; if(lx<=b[0]) return lerp(a[1],b[1],clamp((lx-a[0])/(b[0]-a[0]))); } return arr[arr.length-1][1]; };
  return {smooth,golf,tennis,at};
})();
// 把曲线画到镜头空间：x 轴 log10(Re) 4.0–6.2 映到 [x0,x1]，y 轴 Cd 0–0.7 映到 [y0,y1]
function curvePts(arr,x0,x1,y0,y1,k=1,d=9){ const pts=[]; const lx1=lerp(4.0,6.2,k); for(let lx=4.0;lx<=lx1+1e-6;lx+=0.02){ pts.push(hp(lerp(x0,x1,(lx-4)/2.2),lerp(y0,y1,CURVE.at(arr,lx)/0.7),d)); } if(pts.length<2) pts.push(pts[0].clone().add(V(0.001,0,0))); return pts; }

const BL=(()=>{
  const g=new THREE.Group(); scene.add(g);
  const mk=(mat,r=1)=>{ const m=new THREE.Mesh(new THREE.SphereGeometry(r,64,48),mat); m.visible=false; g.add(m); return m; };
  // 高尔夫：画布上画凹坑做法线感（用暗点 + 高光近似）
  const golfTex=(()=>{ const c=document.createElement('canvas'); c.width=1024; c.height=512; const x=c.getContext('2d'); x.fillStyle='#e9eef2'; x.fillRect(0,0,1024,512);
    for(let j=0;j<18;j++) for(let i=0;i<40;i++){ const cx=(i+(j%2)*0.5)*25.6, cy=j*28.4+14; const gr=x.createRadialGradient(cx-3,cy-3,1,cx,cy,11); gr.addColorStop(0,'#b8c0c8'); gr.addColorStop(1,'#eef2f5'); x.fillStyle=gr; x.beginPath(); x.arc(cx,cy,10,0,6.283); x.fill(); }
    const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; return t; })();
  const footTex=(()=>{ const c=document.createElement('canvas'); c.width=1024; c.height=512; const x=c.getContext('2d'); x.fillStyle='#f4f4f4'; x.fillRect(0,0,1024,512); x.strokeStyle='#2a3240'; x.lineWidth=5;
    for(let i=0;i<8;i++){ x.beginPath(); for(let k=0;k<=64;k++){ const yy=k/64*512; const xx=i*128+40*Math.sin(yy/512*Math.PI*2+i); k?x.lineTo(xx,yy):x.moveTo(xx,yy); } x.stroke(); }
    x.beginPath(); x.moveTo(0,256); for(let k=0;k<=128;k++) x.lineTo(k*8,256+40*Math.sin(k/16)); x.stroke(); const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; return t; })();
  const smooth=mk(new THREE.MeshPhysicalMaterial({color:0xb0c430,roughness:0.25,clearcoat:1,emissive:0x2a3200,emissiveIntensity:0.2}));
  const golf=mk(new THREE.MeshStandardMaterial({map:golfTex,color:0xb8b8b8,roughness:0.5,emissive:0x101418,emissiveIntensity:0.2}));
  const foot=mk(new THREE.MeshStandardMaterial({map:footTex,roughness:0.45,emissive:0x101418,emissiveIntensity:0.2}));
  const tennis=mk(new THREE.MeshPhysicalMaterial({map:ballTex,color:0xc8c8c8,roughness:0.85,sheen:1,sheenColor:new THREE.Color(0xf6ff9a),emissive:0x2a3200,emissiveIntensity:0.25}));
  // 绒毛：网球外面一层短毛（粒子壳），fuzz 0–1 控制毛的长短（磨秃＝0）
  const FZ=cloud(1800,0.035,5,g,0); let sd=31337; const rr=()=>{ sd=(sd*48271)%2147483647; return sd/2147483647; };
  const FD=[...Array(1800)].map(()=>{ const u=rr()*2-1, a=rr()*6.283, s=Math.sqrt(1-u*u); return [s*Math.cos(a),u,s*Math.sin(a),rr()]; });
  function fuzz(c,R,amt,o,col=0xeaff80){ const cc=new THREE.Color(col).multiplyScalar(0.5);   /* 光晕标准：毛是叠加发光，压一半 */ for(let i=0;i<1800;i++){ const d=FD[i]; const rr_=R*(1+amt*0.06*(0.3+0.7*d[3])); cset(FZ,i,c.x+d[0]*rr_,c.y+d[1]*rr_,c.z+d[2]*rr_,cc.r,cc.g,cc.b,o*amt*(0.4+0.6*d[3])); } cdone(FZ); }
  const tennis2=mk(new THREE.MeshPhysicalMaterial({map:ballTex,color:0xc8c8c8,roughness:0.9,sheen:1,sheenColor:new THREE.Color(0xf6ff9a),emissive:0x2a3200,emissiveIntensity:0.25}));
  const all=[smooth,golf,foot,tennis,tennis2];
  return {g,smooth,golf,foot,tennis,tennis2,all,fuzz,hide(){ all.forEach(m=>{ m.visible=false; m.scale.setScalar(1); m.rotation.set(0,0,0); m.material.opacity=1; m.material.transparent=false; }); chide(FZ); }};
})();
function showBall(m,c,R,o=1,spin=0){ m.visible=o>0.003; m.position.copy(c); m.scale.setScalar(R); m.rotation.set(0.3,spin,0.2); m.material.transparent=o<1; m.material.opacity=o; }

// 埃菲尔铁塔（线框，约 3 单位高；1 单位≈100 m）：四条弧形腿＋三层平台＋交叉斜撑
const TOWER=(()=>{
  const g=new THREE.Group(); scene.add(g); g.visible=false; const segs=[];
  const halfW=(y)=>{ const h=y/3.0; return 0.62*Math.pow(1-h,2.2)+0.025; };
  const corner=(y,sx,sz)=>[sx*halfW(y),y,sz*halfW(y)];
  const C=[[1,1],[1,-1],[-1,-1],[-1,1]];
  for(const [sx,sz] of C){ for(let i=0;i<60;i++){ const y0=i/60*3.0, y1=(i+1)/60*3.0; segs.push(...corner(y0,sx,sz),...corner(y1,sx,sz)); } }
  for(let i=0;i<=24;i++){ const y=i/24*2.7; for(let k=0;k<4;k++){ const a=corner(y,...C[k]), b=corner(y,...C[(k+1)%4]); segs.push(...a,...b);
      const y2=Math.min(2.7,y+2.7/24); const a2=corner(y2,...C[(k+1)%4]); segs.push(...a,...a2); } }
  for(const yy of [0.57,1.15,2.76]){ for(let k=0;k<4;k++){ const w=halfW(yy)+0.06; const a=[C[k][0]*w,yy,C[k][1]*w], b=[C[(k+1)%4][0]*w,yy,C[(k+1)%4][1]*w]; segs.push(...a,...b); } }
  // 底部拱
  for(let k=0;k<4;k++){ const [sx,sz]=C[k], [tx2,tz2]=C[(k+1)%4]; for(let i=0;i<20;i++){ const f0=i/20, f1=(i+1)/20; const P=(f)=>{ const x=lerp(sx*halfW(0.1),tx2*halfW(0.1),f), z=lerp(sz*halfW(0.1),tz2*halfW(0.1),f); return [x,0.1+0.32*Math.sin(Math.PI*f),z]; }; segs.push(...P(f0),...P(f1)); } }
  const geo=new THREE.BufferGeometry(); geo.setAttribute('position',new THREE.Float32BufferAttribute(segs,3));
  const mat=new THREE.LineBasicMaterial({color:0xffc24a,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false});
  const L=new THREE.LineSegments(geo,mat); L.frustumCulled=false; g.add(L);
  return {g,mat,set(o){ mat.opacity=o*0.7; g.visible=o>0.003; }};
})();
