// 手势：在 generic-hand（WebXR，25 关节）上按真实指节弯曲摆出石头／剪刀／布。
// 弯曲轴按每根手指自己的方向和掌心法线算（世界坐标），再换到骨骼自己的坐标里转，所以不依赖模型的局部轴约定。
import * as THREE from 'three';
const FINGERS=['thumb','index-finger','middle-finger','ring-finger','pinky-finger'];
export const POSES={ // 每根手指三节的弯曲（弧度）：近节、中节、远节；拇指是 掌骨、近节、远节
  rock:    {'thumb':[0.95,0.75,0.7],'index-finger':[1.45,1.6,1.0],'middle-finger':[1.45,1.6,1.0],'ring-finger':[1.45,1.6,1.0],'pinky-finger':[1.45,1.6,1.0]},
  scissors:{'thumb':[0.95,0.75,0.7],'index-finger':[0,0.05,0.05],'middle-finger':[0,0.05,0.05],'ring-finger':[1.45,1.6,1.0],'pinky-finger':[1.45,1.6,1.0]},
  paper:   {'thumb':[0,0.05,0.05],'index-finger':[0,0.05,0.05],'middle-finger':[0,0.05,0.05],'ring-finger':[0,0.05,0.05],'pinky-finger':[0,0.05,0.05]},
};
// 注意：generic-hand 的 25 个关节是**平铺**的（都挂在 Armature 下、互为兄弟），不是一节连一节的链。
// 所以弯一节手指要自己做正向运动学：绕这一节的位置转，后面各节的位置和朝向一起跟着转（都在 Armature 坐标里算）。
export const SPREAD={rock:{},paper:{'index-finger':-0.06,'pinky-finger':0.08},scissors:{'index-finger':-0.22,'middle-finger':0.16}};
export function rigHand(root){
  const B={}; root.traverse(o=>{ B[o.name]=o; });
  const rest={}; for(const k in B) if(B[k].isBone||/^(wrist|thumb|index|middle|ring|pinky)/.test(k)) rest[k]={p:B[k].position.clone(),q:B[k].quaternion.clone()};
  const RP=n=>rest[n].p.clone();
  const span=RP('pinky-finger-metacarpal').sub(RP('index-finger-metacarpal'));
  const fdir=RP('middle-finger-tip').sub(RP('middle-finger-phalanx-proximal')).normalize();
  const normal=new THREE.Vector3().crossVectors(fdir,span).normalize();
  const chains={};
  for(const f of FINGERS){
    const names=f==='thumb'?['thumb-metacarpal','thumb-phalanx-proximal','thumb-phalanx-distal','thumb-tip']:[`${f}-phalanx-proximal`,`${f}-phalanx-intermediate`,`${f}-phalanx-distal`,`${f}-tip`];
    const d=RP(names[3]).sub(RP(names[0])).normalize();
    let axis=new THREE.Vector3().crossVectors(normal,d).normalize();
    if(f==='thumb'){ // 拇指往掌心、往食指方向收：轴取「拇指方向 × 掌心法线」和手指横轴的折中
      const toward=RP('index-finger-phalanx-proximal').sub(RP('thumb-metacarpal')).normalize();
      axis=new THREE.Vector3().crossVectors(d,toward).normalize(); }
    chains[f]={names,axis};
  }
  return {B,rest,chains,normal,root,
    set(pose,k=1,pose2=null,mix=0){
      for(const n in rest){ B[n].position.copy(rest[n].p); B[n].quaternion.copy(rest[n].q); }
      const rot=(names,i0,axis,ang)=>{ const R=new THREE.Quaternion().setFromAxisAngle(axis,ang); const piv=B[names[i0]].position.clone();
        for(let m=i0;m<4;m++){ const bn=B[names[m]]; if(m>i0) bn.position.sub(piv).applyQuaternion(R).add(piv); bn.quaternion.premultiply(R); } };
      for(const f of FINGERS){ const a=POSES[pose][f], b=pose2?POSES[pose2][f]:a; const {names,axis}=chains[f];
        const sp=THREE.MathUtils.lerp(SPREAD[pose][f]||0,pose2?(SPREAD[pose2][f]||0):(SPREAD[pose][f]||0),mix)*k; if(sp) rot(names,0,normal,sp); // 张开（剪刀的 V）
        const sign=f==='thumb'?1:-1; // 实测：四指朝掌心握要取 −1，拇指往里收取 +1（2026-11-04 并排渲图核过）
        for(let i=0;i<3;i++){ const ang=sign*k*THREE.MathUtils.lerp(a[i],b[i],mix); if(Math.abs(ang)<1e-4) continue;
          const R=new THREE.Quaternion().setFromAxisAngle(axis,ang); const piv=B[names[i]].position.clone();
          for(let m=i;m<4;m++){ const bn=B[names[m]]; if(m>i) bn.position.sub(piv).applyQuaternion(R).add(piv); bn.quaternion.premultiply(R); } } }
      root.updateMatrixWorld(true);
    } };
}
