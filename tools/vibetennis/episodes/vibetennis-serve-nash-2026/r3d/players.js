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
// 体型：X Bot 腰身太细，不像 ATP 球员（所有者 2026-11-04「人的模型腰身太细，不像 atp 球员」）。
// 不缩放骨骼（非均匀缩放会让手臂、头被剪切拉歪），而是在绑定姿势下把躯干网格的顶点沿水平方向往外推：
// 每个顶点按它绑在躯干各骨上的权重插值出加厚系数，以那几根骨在绑定姿势里的位置为轴心。几何体被所有克隆共享，只改一次。
// 目标是倒三角：肩宽、胸背厚而不前凸、腰直不收、胯不宽、四肢粗。躯干骨 [横向, 前后]，四肢骨一个数＝绕骨轴的径向加粗。
export const BUILD={Hips:[0.88,0.84],Spine:[1.42,1.0],Spine1:[1.36,0.95],Spine2:[1.28,0.84],
  LeftShoulder:1.12,RightShoulder:1.12,LeftArm:1.2,RightArm:1.2,LeftForeArm:1.12,RightForeArm:1.12,LeftUpLeg:1.08,RightUpLeg:1.08,LeftLeg:1.1,RightLeg:1.1,Neck:1.15};
export const SHOULDER_OUT=1.14; // 上臂骨根部沿锁骨方向外移的倍数：肩更宽
function thicken(m){
  const geo=m.geometry; if(geo.userData.built) return; geo.userData.built=true;
  const bones=m.skeleton.bones, nm=bones.map(b=>b.name.replace(/^mixamorig:?/,''));
  const bp=m.skeleton.boneInverses.map(inv=>new THREE.Vector3().setFromMatrixPosition(inv.clone().invert())); // 绑定姿势下骨的位置（骨架空间）
  const ax=bones.map((b,i)=>{ const ch=b.children.find(c=>c.isBone); if(!ch) return null; const j=bones.indexOf(ch); return bp[j].clone().sub(bp[i]).normalize(); });
  const pos=geo.attributes.position, si=geo.attributes.skinIndex, sw=geo.attributes.skinWeight, v=new THREE.Vector3(), o=new THREE.Vector3(), d=new THREE.Vector3();
  for(let i=0;i<pos.count;i++){
    v.fromBufferAttribute(pos,i).applyMatrix4(m.bindMatrix); o.set(0,0,0); let W=0;
    for(let j=0;j<4;j++){ const w=sw.getComponent(i,j); if(!w) continue; const b=si.getComponent(i,j), f=BUILD[nm[b]]; if(f===undefined) continue; W+=w;
      if(Array.isArray(f)){ d.set((v.x-bp[b].x)*(f[0]-1),0,(v.z-bp[b].z)*(f[1]-1)); }   // 躯干：竖直轴，横向／前后分开
      else { const a=ax[b]||new THREE.Vector3(0,1,0); d.copy(v).sub(bp[b]); d.addScaledVector(a,-d.dot(a)).multiplyScalar(f-1); } // 四肢：只推垂直于骨轴的那部分
      o.addScaledVector(d,w); }
    if(!W) continue; v.add(o).applyMatrix4(m.bindMatrixInverse); pos.setXYZ(i,v.x,v.y,v.z); }
  pos.needsUpdate=true; geo.computeVertexNormals(); geo.computeBoundingSphere(); }
export function makePlayer(gltf,color,scene){
  const root=SkeletonUtils.clone(gltf.scene); const g=new THREE.Group(); g.add(root); scene.add(g);
  const col=new THREE.Color(color);
  const body=new THREE.MeshPhysicalMaterial({color:0x0b1020,metalness:0.75,roughness:0.28,clearcoat:1,clearcoatRoughness:0.15,emissive:col.clone().multiplyScalar(0.25)});
  const joints=new THREE.MeshStandardMaterial({color:col,emissive:col,emissiveIntensity:1.6,metalness:0.2,roughness:0.4});
  const wire=new THREE.MeshBasicMaterial({color:col,wireframe:true,transparent:true,opacity:0.07,blending:THREE.AdditiveBlending,depthWrite:false});
  const skinned=[]; root.traverse(o=>{ if(o.isSkinnedMesh){ thicken(o); skinned.push(o); o.frustumCulled=false; o.material=/Joints/.test(o.name)?joints:body; } });
  for(const m of skinned){ const w=new THREE.SkinnedMesh(m.geometry,wire); w.bind(m.skeleton,m.bindMatrix); w.frustumCulled=false; m.parent.add(w); }
  const B={}; root.traverse(o=>{ if(o.isBone) B[o.name.replace(/^mixamorig:?/,'')]=o; });
  // 球拍：挂在右手骨上
  const rk=new THREE.Group(); const fr=new THREE.Mesh(new THREE.TorusGeometry(13,1.1,10,48),new THREE.MeshStandardMaterial({color:0xf2f6ff,metalness:0.6,roughness:0.25,emissive:col,emissiveIntensity:0.5}));
  fr.scale.set(1,1.35,1); fr.position.y=46; rk.add(fr);
  const strings=new THREE.Mesh(new THREE.CircleGeometry(12.5,32),new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:0.4,side:THREE.DoubleSide,blending:THREE.AdditiveBlending,depthWrite:false})); strings.scale.set(1,1.35,1); strings.position.y=46; rk.add(strings);
  const hd=new THREE.Mesh(new THREE.CylinderGeometry(1.4,1.6,28,10),new THREE.MeshStandardMaterial({color:0x1a1f2e,metalness:0.3,roughness:0.6})); hd.position.y=14; rk.add(hd);
  rk.scale.setScalar(0.01); scene.add(rk); // 球拍单独挂在场景里，每帧按前臂方向对齐（Mixamo 手骨的局部轴不可靠）
  const mixer=new THREE.AnimationMixer(root); const idle=mixer.clipAction(gltf.animations.find(a=>a.name==='idle')); idle.play();
  const rest={}; for(const k in B) rest[k]=B[k].quaternion.clone(); const armPos={L:B.LeftArm.position.clone().multiplyScalar(SHOULDER_OUT),R:B.RightArm.position.clone().multiplyScalar(SHOULDER_OUT)};
  return {g,root,B,mixer,racket:rk,
    pose(t,keys){ // keys: {骨:球员自身坐标方向}；先放待机动画，再把指定的骨瞄准
      mixer.setTime(t); B.LeftArm.position.copy(armPos.L); B.RightArm.position.copy(armPos.R); root.updateMatrixWorld(true);
      if(!keys){ this.syncRacket(); return; } const wq=g.getWorldQuaternion(new THREE.Quaternion());
      for(const k of ['RightUpLeg','LeftUpLeg','RightLeg','LeftLeg','RightArm','RightForeArm','LeftArm','LeftForeArm']){ if(!keys[k]) continue; aim(B[k],B[CHILD[k]],keys[k].clone().applyQuaternion(wq)); }
      this.syncRacket(); },
    syncRacket(){ const h=B.RightHand.getWorldPosition(new THREE.Vector3()), e=B.RightForeArm.getWorldPosition(new THREE.Vector3());
      const d=h.clone().sub(e).normalize(); rk.position.copy(h).addScaledVector(d,0.02); rk.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d); },
    serveKeys(k){ // 关键姿势之间插值
      let i=0; while(i<SERVE_KEYS.length-2&&k>SERVE_KEYS[i+1][0]) i++; const [k0,a]=SERVE_KEYS[i],[k1,b]=SERVE_KEYS[i+1]; const m=THREE.MathUtils.clamp((k-k0)/(k1-k0),0,1); const s=m*m*(3-2*m);
      const out={}; for(const n in a) out[n]=a[n].clone().lerp(b[n],s).normalize(); return out; } };
}
