// 球员：Mixamo X Bot（骨骼＋待机动画），全息材质；发球动作是在待机动画上用「骨骼瞄准」叠出来的关键姿势。
import * as THREE from 'three';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
const V=(x,y,z)=>new THREE.Vector3(-x,y,z).normalize(); // 写的时候按「右手在 +x」想，这里统一镜像：球员面向 +z 时右手其实在 −x（2026-11-04 渲图核过）
// 关键姿势：各段骨骼在**球员自身坐标**里的朝向（球员面向 +z，右手持拍）
export const SERVE_KEYS=[ // [k, {骨:方向}]
  [0.00,{RightArm:V(0.35,-1,0.15),RightForeArm:V(0.3,-0.6,0.8),LeftArm:V(-0.3,-1,0.2),LeftForeArm:V(-0.1,-0.4,0.9)}],          // 准备：拍在身前
  [0.30,{RightArm:V(0.9,-0.6,-0.3),RightForeArm:V(0.7,-0.2,-0.6),LeftArm:V(-0.15,0.6,0.5),LeftForeArm:V(-0.05,0.9,0.4)}],        // 抛球：左手送球上去
  [0.50,{RightArm:V(0.95,0.25,-0.35),RightForeArm:V(0.15,0.95,-0.4),LeftArm:V(-0.05,1,0.2),LeftForeArm:V(0,1,0.15)}],           // 奖杯姿势
  [0.62,{RightArm:V(0.2,1,0.25),RightForeArm:V(0.12,1,0.35),LeftArm:V(-0.4,-0.5,0.6),LeftForeArm:V(-0.2,-0.6,0.8)}],            // 击球：右臂伸直向上
  [0.85,{RightArm:V(-0.5,-0.6,0.6),RightForeArm:V(-0.8,-0.5,0.2),LeftArm:V(-0.5,-0.7,0.4),LeftForeArm:V(-0.3,-0.9,0.2)}],       // 随挥：拍收到左侧
  [1.00,{RightArm:V(-0.4,-0.8,0.45),RightForeArm:V(-0.6,-0.7,0.3),LeftArm:V(-0.3,-1,0.2),LeftForeArm:V(-0.1,-0.8,0.5)}]];
export const READY_KEY={RightArm:V(0.25,-0.85,0.45),RightForeArm:V(-0.35,0.1,1),LeftArm:V(-0.25,-0.85,0.45),LeftForeArm:V(0.4,0.05,1),
  RightUpLeg:V(0.38,-1,0.3),RightLeg:V(0.12,-1,-0.3),LeftUpLeg:V(-0.38,-1,0.3),LeftLeg:V(-0.12,-1,-0.3)}; // 接发准备：两腿分开屈膝、双手握拍在身前
const CHILD={RightArm:'RightForeArm',RightForeArm:'RightHand',LeftArm:'LeftForeArm',LeftForeArm:'LeftHand',RightUpLeg:'RightLeg',RightLeg:'RightFoot',LeftUpLeg:'LeftLeg',LeftLeg:'LeftFoot'};
function aim(bone,child,dirWorld){
  bone.updateMatrixWorld(true);
  const a=bone.getWorldPosition(new THREE.Vector3()), b=child.getWorldPosition(new THREE.Vector3()); const cur=b.sub(a).normalize();
  const q=new THREE.Quaternion().setFromUnitVectors(cur,dirWorld);
  const pq=bone.parent.getWorldQuaternion(new THREE.Quaternion());
  bone.quaternion.premultiply(pq.clone().invert().multiply(q).multiply(pq)); bone.updateMatrixWorld(true); }
// 体型（所有者 2026-11-04：「人的模型腰身太细，不像 atp 球员」「要按着 atp 球员的比例做」）。
// 比例来源：ANSUR II（2012 美军人体测量，男性 4,082 人公开数据）里身高 1.83–1.98 m、BMI 20–24、35 岁以下的 98 人
// （平均 1.87 m／78 kg，ATP 前列球员的典型身形），各部位除以身高取均值——量法和数在 papers/vibetennis-serve-nash-2026/data/body/。
// X Bot 原本是卡通人台：头大 2 成、上臂短 2 成、腰只有人的一半宽、胯宽 27%、躯干短 16%。
// 做法：①骨长（LEN）把各节拉到人的比例；②躯干在绑定姿势下按高度逐层把横宽、前后厚度对到人的轮廓（不是按骨乘倍数——
//   这个模型的腰是一颗外露的关节球、胯是一块宽骨盆板，按骨缩放对不准）；③四肢按围度径向加粗。不缩放骨骼，动作不受影响。
// 人体轮廓（相对身高）：[高度, 横宽, 前后厚]——转子高 0.523 处胯宽 0.180／臀厚 0.118，脐高 0.612 处腰宽 0.160／腰厚 0.109，胸高 0.741 处胸宽 0.152／胸厚 0.123
export let HS=1; // 新身高／原身高：人体轮廓的目标宽度要按它换算到绑定姿势的长度单位里
const HUMAN=[[0.47,0.170,0.112],[0.523,0.180,0.118],[0.612,0.160,0.109],[0.68,0.150,0.115],[0.741,0.152,0.123],[0.80,0.152,0.120]];
// 模型绑定姿势里的两个锚：髋关节高 0.539 ↔ 人的转子高 0.523，肩关节高 0.796 ↔ 人的肩峰高 0.821（躯干段线性对应）
const ANCH=[0.539,0.523,0.796,0.821];
export const BUILD={LeftArm:0.95,RightArm:0.95,LeftForeArm:1.03,RightForeArm:1.03,LeftUpLeg:1.23,RightUpLeg:1.23,LeftLeg:0.94,RightLeg:0.94}; // 四肢径向：按 ANSUR 的大腿／小腿／上臂／前臂围度（围度÷π 对比网格到骨轴的平均距离×2）
const NOT_TORSO=/Arm|Hand|Head|Neck|Thumb|Index|Middle|Ring|Pinky/;
const lerpTab=(tab,x,c)=>{ if(x<=tab[0][0]) return tab[0][c]; for(let i=1;i<tab.length;i++) if(x<=tab[i][0]){ const [a,b]=[tab[i-1],tab[i]]; return a[c]+(b[c]-a[c])*(x-a[0])/(b[0]-a[0]); } return tab[tab.length-1][c]; };
const sstep=(a,b,x)=>{ const t=Math.min(1,Math.max(0,(x-a)/(b-a))); return t*t*(3-2*t); };
export let PROFILE=null; // 两张网格（身体、关节）各量各的：腰那颗关节球在关节网格里，要单独放大去填满胸甲和骨盆之间的空当
function profile(ms){
  const pts=new Map(); let y0=1e9,y1=-1e9; const v=new THREE.Vector3();
  for(const m of ms){ const P=[]; const pos=m.geometry.attributes.position, si=m.geometry.attributes.skinIndex, sw=m.geometry.attributes.skinWeight, nm=m.skeleton.bones.map(b=>b.name.replace(/^mixamorig:?/,''));
    for(let i=0;i<pos.count;i++){ v.fromBufferAttribute(pos,i).applyMatrix4(m.bindMatrix); let bw=0,bn=''; for(let j=0;j<4;j++){ const w=sw.getComponent(i,j); if(w>bw){bw=w;bn=nm[si.getComponent(i,j)];} } P.push([v.x,v.y,v.z,bn]); y0=Math.min(y0,v.y); y1=Math.max(y1,v.y); }
    pts.set(m,P); }
  const H=y1-y0, out=new Map();
  for(const [m,P] of pts){
    const raw=[]; for(let r=0.40;r<=0.86;r+=0.005){ const sel=P.filter(p=>Math.abs((p[1]-y0)/H-r)<0.003&&!NOT_TORSO.test(p[3]));
      if(sel.length<4){ raw.push(null); continue; } const xs=sel.map(p=>p[0]), zs=sel.map(p=>p[2]); raw.push([r,(Math.max(...xs)-Math.min(...xs))/H,(Math.max(...zs)-Math.min(...zs))/H,(Math.max(...zs)+Math.min(...zs))/2]); }
    const env=raw.map((x,i)=>{ if(!x) return null; const n=raw.slice(Math.max(0,i-2),i+3).filter(Boolean); return [x[0],Math.max(...n.map(q=>q[1])),Math.max(...n.map(q=>q[2])),x[3]]; }); // 外包络：±1% 身高取最大，挡板边缘不各自鼓出来
    const f=env.map(x=>{ if(!x) return null; const h=ANCH[1]+(x[0]-ANCH[0])*(ANCH[3]-ANCH[1])/(ANCH[2]-ANCH[0]);
      return [x[0],Math.min(2.6,Math.max(0.6,HS*lerpTab(HUMAN,h,1)/x[1])),Math.min(2.2,Math.max(0.6,HS*lerpTab(HUMAN,h,2)/x[2])),x[3]]; });
    const sm=f.map((x,i)=>{ if(!x) return null; const n=f.slice(Math.max(0,i-3),i+4).filter(Boolean); return [x[0],n.reduce((s,q)=>s+q[1],0)/n.length,n.reduce((s,q)=>s+q[2],0)/n.length,n.reduce((s,q)=>s+q[3],0)/n.length]; }).filter(Boolean); // ±1.5% 平滑
    out.set(m,sm); }
  return {y0,H,out}; }
function thicken(m,all){
  const geo=m.geometry; if(geo.userData.built) return; geo.userData.built=true;
  if(!PROFILE) PROFILE=profile(all); const {y0,H}=PROFILE, sm=PROFILE.out.get(m);
  const bones=m.skeleton.bones, nm=bones.map(b=>b.name.replace(/^mixamorig:?/,''));
  const bp=m.skeleton.boneInverses.map(inv=>new THREE.Vector3().setFromMatrixPosition(inv.clone().invert()));
  const ax=bones.map((b,i)=>{ const ch=b.children.find(c=>c.isBone); if(!ch) return null; const j=bones.indexOf(ch); return bp[j].clone().sub(bp[i]).normalize(); });
  const pos=geo.attributes.position, si=geo.attributes.skinIndex, sw=geo.attributes.skinWeight, v=new THREE.Vector3(), o=new THREE.Vector3(), d=new THREE.Vector3();
  const at=(r,c)=>lerpTab(sm,r,c); // 层间线性插值
  const bmi=m.bindMatrix.clone().invert(); // ⚠️ 不用 m.bindMatrixInverse：attached 模式下 updateMatrixWorld 会把它改写成当前位置的逆，写回顶点就进了错的坐标系（整个人放大 100 倍）
  for(let i=0;i<pos.count;i++){
    v.fromBufferAttribute(pos,i).applyMatrix4(m.bindMatrix); const r=(v.y-y0)/H;
    let wt=1; o.set(0,0,0);
    for(let j=0;j<4;j++){ const w=sw.getComponent(i,j); if(!w) continue; const b=si.getComponent(i,j), n=nm[b]; if(NOT_TORSO.test(n)) wt-=w; const f=BUILD[n]; if(f===undefined) continue;
      const a=ax[b]||new THREE.Vector3(0,1,0); d.copy(v).sub(bp[b]); d.addScaledVector(a,-d.dot(a)).multiplyScalar(f-1); o.addScaledVector(d,w*(/UpLeg/.test(n)?1-sstep(0.44,0.50,r):1)); } // 大腿根进了胯部，交给躯干轮廓管，不再额外加粗（不然胯被撑宽）
    const blend=Math.max(0,wt)*sstep(0.44,0.48,r)*(1-sstep(0.79,0.83,r));
    if(blend>0){ const fx=at(r,1), fz=at(r,2), zc=at(r,3); v.x*=1+(fx-1)*blend; v.z=zc+(v.z-zc)*(1+(fz-1)*blend); }
    v.add(o).applyMatrix4(bmi); pos.setXYZ(i,v.x,v.y,v.z); }
  pos.needsUpdate=true; geo.computeVertexNormals(); geo.computeBoundingSphere(); }
// 骨长：子骨的局部位置乘倍数＝这一节拉长／缩短（网格跟着骨走）。键是子骨名，Left 开头的左右对称套用；Head 是头的整体缩放。
// ⚠️ 只缩不拉：人台的部件是刚性的，拉长一节会在接缝处拉出缝（脊柱拉长 20% 时腰上开了一道缝），缩短只会重叠、看不出来。
// 所以「躯干相对太短」靠缩短腿、头、前臂来对，最后整体放大回原来的身高（STATURE）。
export const LEN={LeftLeg:0.84,LeftFoot:0.84,Head:0.68,LeftArm:0.98,LeftForeArm:1.07,LeftHand:0.84};
const SIDE=k=>k.startsWith('Left')?[k,'Right'+k.slice(4)]:[k];
export function makePlayer(gltf,color,scene){
  const root=SkeletonUtils.clone(gltf.scene); const g=new THREE.Group(); g.add(root); scene.add(g);
  const col=new THREE.Color(color);
  // 不发光（所有者 2026-11-04：「不要腰部发光，全身都不要」）：关节和身体都是实体材质，没有自发光、没有叠加发光的线框；
  // 两个人靠底色区分（发球人橙、接发人青）
  const body=new THREE.MeshPhysicalMaterial({color:col.clone().multiplyScalar(0.8),metalness:0.3,roughness:0.42,clearcoat:0.6,clearcoatRoughness:0.3});
  const joints=body; // 关节和身体同一种材质：分色会让腰那一圈读成一道缝，像分段的人台
  const B={}; root.traverse(o=>{ if(o.isBone) B[o.name.replace(/^mixamorig:?/,'')]=o; });
  const sk=[]; root.traverse(o=>{ if(o.isSkinnedMesh) sk.push(o); });
  const lenPos=[]; for(const k in LEN){ if(k==='Head') continue; for(const n of SIDE(k)) lenPos.push([B[n],B[n].position.clone().multiplyScalar(LEN[k])]); }
  // 骨长改完量一次：身高变了多少（HS）、脚抬起了多少（髋要往下放同样多，不然脚悬空）
  const wy=n=>B[n].getWorldPosition(new THREE.Vector3()).y;
  // ⚠️ 不用 skeleton.pose()：它把髋骨（父节点不是骨）的局部变换直接设成世界矩阵，模型外壳上的 0.01 缩放会被叠两次、整个人缩成 1/100。
  // 加载时骨骼就在绑定姿势上，记下各骨的局部变换，要回到绑定姿势时照抄回去。
  const R0=[]; root.traverse(o=>{ if(o.isBone) R0.push([o,o.position.clone(),o.quaternion.clone(),o.scale.clone()]); });
  const restore=()=>{ for(const [o,p,q,sc] of R0){ o.position.copy(p); o.quaternion.copy(q); o.scale.copy(sc); } };
  g.updateMatrixWorld(true); const top0=wy('HeadTop_End'), toe0=wy('LeftToe_End'), hipW=B.Hips.getWorldPosition(new THREE.Vector3()), hipL=B.Hips.position.clone();
  for(const [b,p] of lenPos) b.position.copy(p); B.Head.scale.setScalar(LEN.Head); root.updateMatrixWorld(true);
  const top1=wy('HeadTop_End'), toe1=wy('LeftToe_End'); HS=(top1-toe1)/(top0-toe0);
  const hipOff=B.Hips.parent.worldToLocal(hipW.clone().add(new THREE.Vector3(0,-(toe1-toe0),0))).sub(hipL);
  root.scale.multiplyScalar(1/HS); // 整体放大回原来的身高，球场里的大小不变
  const applyLen=()=>{ for(const [b,p] of lenPos) b.position.copy(p); B.Head.scale.setScalar(LEN.Head); B.Hips.position.add(hipOff); };
  const skinned=[]; if(!PROFILE) PROFILE=profile(sk); sk.forEach(m=>thicken(m,sk));
  root.traverse(o=>{ if(o.isSkinnedMesh){ skinned.push(o); o.frustumCulled=false; o.material=/Joints/.test(o.name)?joints:body; } });
  // 球拍：挂在右手骨上
  const rk=new THREE.Group(); const fr=new THREE.Mesh(new THREE.TorusGeometry(13,1.1,10,48),new THREE.MeshStandardMaterial({color:0xf2f6ff,metalness:0.6,roughness:0.25}));
  fr.scale.set(1,1.35,1); fr.position.y=46; rk.add(fr);
  const strings=new THREE.Mesh(new THREE.CircleGeometry(12.5,32),new THREE.MeshStandardMaterial({color:0xdde3ee,transparent:true,opacity:0.35,side:THREE.DoubleSide,depthWrite:false,roughness:0.8})); strings.scale.set(1,1.35,1); strings.position.y=46; rk.add(strings);
  const hd=new THREE.Mesh(new THREE.CylinderGeometry(1.4,1.6,28,10),new THREE.MeshStandardMaterial({color:0x1a1f2e,metalness:0.3,roughness:0.6})); hd.position.y=14; rk.add(hd);
  rk.scale.setScalar(0.01); scene.add(rk); // 球拍单独挂在场景里，每帧按前臂方向对齐（Mixamo 手骨的局部轴不可靠）
  const mixer=new THREE.AnimationMixer(root); const idle=mixer.clipAction(gltf.animations.find(a=>a.name==='idle')); idle.play();
  const rest={}; for(const k in B) rest[k]=B[k].quaternion.clone();
  return {g,root,B,mixer,racket:rk,skinned,
    bindPose(){ restore(); applyLen(); root.updateMatrixWorld(true); }, // 量比例用：绑定姿势＋骨长调整
    pose(t,keys){ // keys: {骨:球员自身坐标方向}；先放待机动画，再把指定的骨瞄准
      mixer.setTime(t); applyLen(); root.updateMatrixWorld(true);
      if(!keys){ this.syncRacket(); return; } const wq=g.getWorldQuaternion(new THREE.Quaternion());
      for(const k of ['RightUpLeg','LeftUpLeg','RightLeg','LeftLeg','RightArm','RightForeArm','LeftArm','LeftForeArm']){ if(!keys[k]) continue; aim(B[k],B[CHILD[k]],keys[k].clone().applyQuaternion(wq)); }
      this.syncRacket(); },
    syncRacket(){ const h=B.RightHand.getWorldPosition(new THREE.Vector3()), e=B.RightForeArm.getWorldPosition(new THREE.Vector3());
      const d=h.clone().sub(e).normalize(); rk.position.copy(h).addScaledVector(d,0.02); rk.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d); },
    serveKeys(k){ // 关键姿势之间插值
      let i=0; while(i<SERVE_KEYS.length-2&&k>SERVE_KEYS[i+1][0]) i++; const [k0,a]=SERVE_KEYS[i],[k1,b]=SERVE_KEYS[i+1]; const m=THREE.MathUtils.clamp((k-k0)/(k1-k0),0,1); const s=m*m*(3-2*m);
      const out={}; for(const n in a) out[n]=a[n].clone().lerp(b[n],s).normalize(); return out; } };
}
