// 球员：CC0 写实男性基础人体（BoQsc/Godot-Male-Base-Mesh），全息材质；发球动作是在静止姿势上用「骨骼瞄准」叠出来的关键姿势。
// 所有者 2026-11-04 先嫌 X Bot「腰身太细，不像 atp 球员」、又「不要腰部发光」，最后「不要这个模型的人」——X Bot 是分段人台，换成一整块连续的人体。
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
// 这个模型是 Blender Rigify 的骨骼命名，对到发球代码用的 Mixamo 名字上
const MAP={Hips:'spine',Spine:'spine001',Spine1:'spine002',Spine2:'spine003',Neck:'spine004',Head:'spine005',
  LeftShoulder:'shoulderL',LeftArm:'upper_armL',LeftForeArm:'forearmL',LeftHand:'handL',RightShoulder:'shoulderR',RightArm:'upper_armR',RightForeArm:'forearmR',RightHand:'handR',
  LeftUpLeg:'thighL',LeftLeg:'shinL',LeftFoot:'footL',LeftToeBase:'toeL',RightUpLeg:'thighR',RightLeg:'shinR',RightFoot:'footR',RightToeBase:'toeR'};
export const STATURE=1.87; // ATP 前列球员的典型身高（papers/vibetennis-serve-nash-2026/data/body/atp_like.json：ANSUR II 里 1.83–1.98 m、BMI 20–24 那 98 人平均 1.87 m）
function aim(bone,child,dirWorld){
  bone.updateMatrixWorld(true);
  const a=bone.getWorldPosition(new THREE.Vector3()), b=child.getWorldPosition(new THREE.Vector3()); const cur=b.sub(a).normalize();
  const q=new THREE.Quaternion().setFromUnitVectors(cur,dirWorld);
  const pq=bone.parent.getWorldQuaternion(new THREE.Quaternion());
  bone.quaternion.premultiply(pq.clone().invert().multiply(q).multiply(pq)); bone.updateMatrixWorld(true); }
export function makePlayer(gltf,color,scene){
  const root=SkeletonUtils.clone(gltf.scene); const fix=new THREE.Group(); fix.add(root); const g=new THREE.Group(); g.add(fix); scene.add(g);
  const raw={}; root.traverse(o=>{ if(o.isBone) raw[o.name]=o; }); const B={}; for(const k in MAP) B[k]=raw[MAP[k]];
  // 摆正：模型原本面朝 ±x。按左脚「脚跟→脚尖」转到面朝 +z，再按包围盒缩放到 STATURE、脚踩地
  g.updateMatrixWorld(true); const wp=o=>o.getWorldPosition(new THREE.Vector3());
  const d=wp(B.LeftToeBase).sub(wp(B.LeftFoot)); fix.rotation.y=-Math.atan2(d.x,d.z); g.updateMatrixWorld(true);
  if(wp(B.LeftArm).x<0) console.warn('makePlayer: 左臂不在 +x，左右镜像了');
  const bx=new THREE.Box3().setFromObject(root,true); const sc=STATURE/(bx.max.y-bx.min.y); fix.scale.setScalar(sc); fix.position.y=-bx.min.y*sc;
  const col=new THREE.Color(color);
  // 透明全息（所有者 2026-11-04「还是换回原来透明的人吧」）：深色玻璃体＋同色微光＋叠加线框；没有单独高亮的关节
  const body=new THREE.MeshPhysicalMaterial({color:0x0b1020,metalness:0.75,roughness:0.28,clearcoat:1,clearcoatRoughness:0.15,emissive:col.clone().multiplyScalar(0.25)});
  const wire=new THREE.MeshBasicMaterial({color:col,wireframe:true,transparent:true,opacity:0.1,blending:THREE.AdditiveBlending,depthWrite:false});
  const skinned=[]; root.traverse(o=>{ if(o.isSkinnedMesh){ skinned.push(o); o.frustumCulled=false; o.material=body; } });
  for(const m of skinned){ const w=new THREE.SkinnedMesh(m.geometry,wire); w.bind(m.skeleton,m.bindMatrix); w.frustumCulled=false; m.parent.add(w); }
  // 球拍：单独挂在场景里，每帧按前臂方向对齐。单位 cm（整体 ×0.01），按网球拍的实际尺寸：全长 68.5、拍框 33×26（椭圆）、
  // 拍喉两根梁 V 形接到拍框、八角拍柄 2 cm 粗＋柄尾、16×19 拍线（所有者 2026-11-04「网球拍的样子不对，不要像羽毛球拍」——
  // 原来是细长柄配小圆环，头小柄长、没有拍喉，比例像羽毛球拍）
  const rk=new THREE.Group(); const HC=51, HA=13, HB=16.5;   // 拍框中心高度、半宽、半高
  const frameMat=new THREE.MeshStandardMaterial({color:0xf2f6ff,metalness:0.6,roughness:0.25,emissive:col,emissiveIntensity:0.5});
  const ell=new THREE.EllipseCurve(0,HC,HA,HB,0,Math.PI*2);   const fpts=ell.getPoints(96).map(p=>new THREE.Vector3(p.x,p.y,0));
  rk.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(fpts,true),120,1.05,10,true),frameMat));
  for(const sx of [-1,1]){ const th=new THREE.CatmullRomCurve3([new THREE.Vector3(sx*1.4,20,0),new THREE.Vector3(sx*4.5,28,0),new THREE.Vector3(sx*HA*0.62,HC-HB*0.8,0)]);
    rk.add(new THREE.Mesh(new THREE.TubeGeometry(th,24,0.95,8,false),frameMat)); }
  const hd=new THREE.Mesh(new THREE.CylinderGeometry(1.75,1.75,20,8),new THREE.MeshStandardMaterial({color:0x1a1f2e,metalness:0.3,roughness:0.6})); hd.position.y=10.5; rk.add(hd);
  const cap=new THREE.Mesh(new THREE.CylinderGeometry(1.95,1.95,1.2,8),frameMat); cap.position.y=0.6; rk.add(cap);
  const sp=[]; const inside=(x)=>HB*Math.sqrt(Math.max(0,1-(x/HA)**2))*0.97;
  for(let i=0;i<16;i++){ const x=-HA*0.92+i*(HA*1.84/15); const h=inside(x); sp.push(x,HC-h,0,x,HC+h,0); }                 // 竖线 16
  for(let j=0;j<19;j++){ const y=-HB*0.92+j*(HB*1.84/18); const w=HA*Math.sqrt(Math.max(0,1-(y/HB)**2))*0.97; sp.push(-w,HC+y,0,w,HC+y,0); } // 横线 19
  const sg=new THREE.BufferGeometry(); sg.setAttribute('position',new THREE.Float32BufferAttribute(sp,3));
  rk.add(new THREE.LineSegments(sg,new THREE.LineBasicMaterial({color:col,transparent:true,opacity:0.55,blending:THREE.AdditiveBlending,depthWrite:false})));
  const bed=new THREE.Mesh(new THREE.CircleGeometry(1,48),new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:0.12,side:THREE.DoubleSide,blending:THREE.AdditiveBlending,depthWrite:false})); bed.scale.set(HA,HB,1); bed.position.y=HC; rk.add(bed);
  rk.scale.setScalar(0.01); scene.add(rk);
  const R0=[]; root.traverse(o=>{ if(o.isBone) R0.push([o,o.position.clone(),o.quaternion.clone()]); });
  return {g,root,B,racket:rk,skinned,
    pose(t,keys){ // 静止姿势＋一点呼吸起伏，再把指定的骨瞄准（keys：球员自身坐标里的方向）
      for(const [o,p,q] of R0){ o.position.copy(p); o.quaternion.copy(q); }
      B.Spine1.rotateX(0.025*Math.sin(t*1.7)); B.Spine2.rotateX(0.015*Math.sin(t*1.7+0.6)); B.Neck.rotateX(-0.02*Math.sin(t*1.7));
      root.updateMatrixWorld(true);
      if(!keys){ this.syncRacket(); return; } const wq=g.getWorldQuaternion(new THREE.Quaternion());
      for(const k of ['RightUpLeg','LeftUpLeg','RightLeg','LeftLeg','RightArm','RightForeArm','LeftArm','LeftForeArm']){ if(!keys[k]) continue; aim(B[k],B[CHILD[k]],keys[k].clone().applyQuaternion(wq)); }
      this.syncRacket(); },
    syncRacket(){ const h=B.RightHand.getWorldPosition(new THREE.Vector3()), e=B.RightForeArm.getWorldPosition(new THREE.Vector3());
      const d=h.clone().sub(e).normalize(); rk.position.copy(h).addScaledVector(d,-0.08); rk.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d); }, // 手握在柄中段：柄尾露出手外约 8 cm
    serveKeys(k){ // 关键姿势之间插值
      let i=0; while(i<SERVE_KEYS.length-2&&k>SERVE_KEYS[i+1][0]) i++; const [k0,a]=SERVE_KEYS[i],[k1,b]=SERVE_KEYS[i+1]; const m=THREE.MathUtils.clamp((k-k0)/(k1-k0),0,1); const s=m*m*(3-2*m);
      const out={}; for(const n in a) out[n]=a[n].clone().lerp(b[n],s).normalize(); return out; } };
}
