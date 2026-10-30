const BAR=2.1364, B0=0.46; const bar=k=>B0+BAR*k;
const ease=x=>{x=Math.min(1,Math.max(0,x)); return x*x*(3-2*x);};
const easeIO=x=>{x=Math.min(1,Math.max(0,x)); return x<0.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;};
function lerpV(S,a,b,u){ return new S.THREE.Vector3().lerpVectors(a,b,u); }
function path(S,keys,u){ // keys: [[x,y,z],...] catmull-rom
  const pts=keys.map(k=>new S.THREE.Vector3(...k)); const c=new S.THREE.CatmullRomCurve3(pts,false,'centripetal'); return c.getPoint(Math.min(1,Math.max(0,u)));
}
function cam(S,pos,tgt,fov,up){ S.camera.up.set(...(up||[0,1,0])); S.camera.position.copy(pos); S.camera.fov=fov; S.camera.lookAt(tgt); S.camera.updateProjectionMatrix(); S.camera.updateMatrixWorld(true); }
function fadeIO(S,lt,d,a=0.5,b=0.5){ S.finalPass.uniforms.uFade.value=Math.min(1,lt/a,(d-lt)/b); }
const loop=(x,p)=>((x%p)+p)%p;

export const SHOTS=[];
const add=(t0,t1,fn)=>SHOTS.push({t0,t1,fn});

// A1 crane down from space onto the arena, slow-motion serve
add(0,bar(3),(S,lt,d)=>{
  const u=easeIO(lt/d);
  cam(S,path(S,[[0,520,420],[30,160,190],[18,40,70],[10,16,40]],u),path(S,[[0,0,-60],[0,0,-10],[0,1,0],[0,1,0]],u),38);
  S.setBall(loop(lt*0.22,0.95)-0.1,0.25,0.12,1);
  S.proj('ball',S.ball.position); fadeIO(S,lt,d,1.2,0.05);
});
// A2 courtside: real-time serves whip past
add(bar(3),bar(6),(S,lt,d)=>{
  const sway=Math.sin(lt*0.4)*0.6;
  cam(S,S.V(S.SEAT.x-0.5,S.SEAT.y-0.6,S.SEAT.z+2.5+sway),S.V(0,1.0,-3+sway),62);
  const tb=loop(lt,2.3)-0.4; S.setBall(tb,0.09,0.14,1);
  const fl=Math.max(0,1-Math.abs(tb-0.2)/0.06); S.finalPass.uniforms.uFlash.value=0.18*fl;
  S.bloom.strength=1.15; fadeIO(S,lt,d,0.15,0.3);
});
// B1 football stadium aerial wide: ball slow
add(bar(6),bar(9),(S,lt,d)=>{
  const u=lt/d; const X=S.FX;
  cam(S,S.V(X-140+40*u,120-15*u,150-20*u),S.V(X,0,0),36);
  S.fBall.visible=true; const p=loop(lt*0.19,1); S.fBall.position.set(-20+40*Math.sin(p*6.28)*0.3, 0.4, -52+105*p);
  fadeIO(S,lt,d,0.6,0.3);
});
// B2 football TV-style tight long lens, window frame, fast across
add(bar(9),bar(12),(S,lt,d)=>{
  const X=S.FX; const p=loop(lt*0.5,1); const bz=-20+40*p;
  S.fBall.visible=true; S.fBall.position.set(4, 0.4, bz);
  S.fWin.visible=true; S.fWin.position.set(0,0,bz*0.25);
  cam(S,S.V(X+110,38,bz*0.25),S.V(X,0,bz*0.25),20);
  fadeIO(S,lt,d,0.3,0.6);
});
// C1 low dolly along court in slow motion with measurements
add(bar(12),bar(15)+1.0,(S,lt,d)=>{
  const tb=Math.min(0.75,lt*0.12); S.setBall(tb,0.2,0.1,1);
  const b=S.ball.position; cam(S,S.V(7.5,1.4,b.z+5),S.V(0,1.0,b.z-6),46);
  S.proj('base_far',S.V(0,0.05,-S.L)); S.proj('base_near',S.V(0,0.05,S.L)); S.proj('ball',b); S.proj('bounce',S.serve(0.395)); S.val('tb',tb);
  fadeIO(S,lt,d,0.4,0.2);
});
// C2 real-time from high side, repeated, timer
add(bar(15)+1.0,bar(18),(S,lt,d)=>{
  const tb=loop(lt,2.0)-0.3; S.setBall(tb,0.1,0.12,1);
  cam(S,S.V(26-lt*0.6,14,6),S.V(0,0,0),40);
  S.proj('base_far',S.V(0,0.05,-S.L)); S.proj('base_near',S.V(0,0.05,S.L)); S.proj('ball',S.ball.position); S.val('tb',tb);
  fadeIO(S,lt,d,0.2,0.4);
});
// D1 orbit the broadcast camera, frustum & sightline
add(bar(18),bar(22),(S,lt,d)=>{
  const u=easeIO(lt/d); const c=S.c1.position; const a=0.9-1.4*u;
  cam(S,S.V(c.x+9*Math.sin(a),c.y+2.5-1*u,c.z+9*Math.cos(a)),S.V(c.x*0.5,c.y*0.6,c.z-6-8*u),44);
  S.frust.visible=true; S.sight.visible=lt>d*0.45; S.setBall(loop(lt*0.5,1.3)-0.2,0.15,0.1,1);
  S.proj('c1',S.V(c.x,c.y+0.9,c.z)); S.proj('nettop',S.V(0,0.914,0));
  fadeIO(S,lt,d,0.5,0.3);
});
// D2 side elevation: wedges
add(bar(22),bar(26),(S,lt,d)=>{
  const u=lt/d; const mid=S.V(0,3.6,8.5);
  cam(S,S.V(80-5*u,4.5,8.5),mid,24);
  S.wedgeRims.visible=true; S.sight.visible=true;
  if(u<0.5){ S.wedgeAll.visible=true; } else { S.wedgeFar.visible=true; S.wedgeNear.visible=true; }
  S.setBall(loop(lt*0.6,1.4)-0.2,0.15,0.1,1);
  S.proj('c1',S.V(0,S.C1_Y+1.2,S.C1_Z)); S.proj('far',S.V(0,0,-S.L)); S.proj('net',S.V(0,0,0)); S.proj('near',S.V(0,0,S.L));
  S.proj('wedgeMidFar',S.V(0,S.C1_Y*0.35,S.C1_Z*0.35-8)); S.proj('wedgeMidNear',S.V(0,S.C1_Y*0.2,S.C1_Z*0.6));
  fadeIO(S,lt,d,0.3,0.3);
});
// D3 holographic TV showing camera-1 view, ball barely moves
add(bar(26),bar(29),(S,lt,d)=>{
  const u=lt/d; S.tvScreen.visible=true; S.tvScreen.position.set(0,S.C1_Y+9,S.C1_Z+4); S.tvScreen.rotation.set(-0.08,0,0);
  const sp=S.tvScreen.position; cam(S,S.V(sp.x-5+4*u,sp.y+3,sp.z+36-5*u),S.V(sp.x,sp.y-1,sp.z),42);
  S.setBall(loop(lt,2.0)-0.4,0.1,0.1,1); S.c1cam.fov=16; S.c1cam.updateProjectionMatrix();
  fadeIO(S,lt,d,0.3,0.2);
});
// D4 push into the screen: become camera 1 view (vertical crop)
add(bar(29),bar(32),(S,lt,d)=>{
  const u=easeIO(Math.min(1,lt/2.5)); const c=S.c1.position;
  cam(S,lerpV(S,S.V(c.x+3,c.y+6,c.z+14),S.V(c.x,c.y+0.3,c.z-1.6),u),S.V(0,0.3,-1.2),lerpV(S,S.V(50,0,0),S.V(36,0,0),u).x);
  S.setBall(loop(lt,1.6)-0.3,0.1,0.1,1);
  if(lt<0.25) S.finalPass.uniforms.uFlash.value=0.5*(1-lt/0.25);
  S.proj('far',S.V(0,0,-S.L)); S.proj('near',S.V(0,0,S.L));
  fadeIO(S,lt,d,0.01,0.3);
});
// E1 overhead-side: sweep wedge from the seat
add(bar(32),bar(37),(S,lt,d)=>{
  const u=lt/d; const tb=Math.min(0.714,loop(lt*0.35,0.95));
  S.setBall(tb,0.15,0.1,1); S.setSweep(tb,1); S.seatMark.visible=true;
  cam(S,S.V(30+6*u,34,14-10*u),S.V(3,0,0),40);
  S.proj('seat',S.SEAT); S.proj('ball',S.ball.position); S.proj('sweepLabel',S.V(S.SEAT.x-3,S.SEAT.y,S.SEAT.z));
  S.val('tb',tb); fadeIO(S,lt,d,0.4,0.3);
});
// E2 the seat POV with HUD bars
add(bar(37),bar(42),(S,lt,d)=>{
  cam(S,S.V(S.SEAT.x+1.5,S.SEAT.y+0.4,S.SEAT.z+2.8),S.V(0,1,-3),58);
  S.setBall(loop(lt,2.14)-0.5,0.1,0.14,1); S.seatMark.visible=false;
  fadeIO(S,lt,d,0.3,0.4);
});
// F1 eye pursuit: courtside, ball streak, reticle in overlay
add(bar(42),bar(47),(S,lt,d)=>{
  cam(S,S.V(S.SEAT.x,S.SEAT.y,S.SEAT.z+2.5),S.V(0,1,-2.5),50);
  const tb=loop(lt,2.14)-0.4; S.setBall(tb,0.16,0.16,1); S.proj('ball',S.ball.position); S.val('tb',tb);
  S.bloom.strength=0.9; fadeIO(S,lt,d,0.5,0.3);
});
// F2 depth motion: ball comes straight at you from behind baseline (low)
add(bar(47),bar(51),(S,lt,d)=>{
  cam(S,S.V(0.0,1.6,S.L+4),S.V(0,1.0,-S.L),34);
  S.setBall(loop(lt*0.5,1.07)-0.15,0.2,0.12,1); S.proj('ball',S.ball.position);
  fadeIO(S,lt,d,0.3,0.5);
});
// G1 crane up and fly to football stadium (scale reveal)
add(bar(51),bar(55),(S,lt,d)=>{
  const u=easeIO(lt/d); const X=S.FX;
  S.scene.fog.density=0.0006; cam(S,path(S,[[20,12,40],[60,90,160],[X*0.5,220,260],[X-60,150,190]],u),path(S,[[0,0,0],[30,0,0],[X*0.7,0,0],[X,0,0]],u),40);
  S.proj('tennis',S.V(0,2,0)); S.proj('football',S.V(X,2,0));
  fadeIO(S,lt,d,0.3,0.3);
});
// G2 Brown portals
add(bar(55),bar(60),(S,lt,d)=>{
  S.brown.visible=true; const b=S.brown.position; const u=lt/d;
  cam(S,S.V(b.x+2*Math.sin(u*1.2),b.y+0.5,b.z+30-3*u),S.V(b.x,b.y-0.5,b.z),40);
  const p1=loop(lt*0.35,1), p2=loop(lt*0.35,1);
  S.bDot1.position.set(-3+6*p1,0.6*Math.sin(p1*6.28),0.1); S.bDot2.position.set(-6+12*p2,1.2*Math.sin(p2*6.28),0.1);
  S.proj('pSmall',S.V(b.x-10,b.y-3.6,b.z)); S.proj('pBig',S.V(b.x+5,b.y-6.6,b.z)); S.proj('pSmallTop',S.V(b.x-10,b.y+3.4,b.z)); S.proj('pBigTop',S.V(b.x+5,b.y+6.4,b.z));
  fadeIO(S,lt,d,0.4,0.3);
});
// G3 football: window vs whole pitch, from high
add(bar(60),bar(64),(S,lt,d)=>{
  const X=S.FX; const p=loop(lt*0.19,1); const bz=-50+100*p;
  S.fBall.visible=true; S.fBall.position.set(6,0.4,bz); S.fWin.visible=true; S.fWin.position.set(0,0,Math.max(-40,Math.min(40,bz)));
  cam(S,S.V(X+150,130,40),S.V(X,0,0),34);
  S.proj('win',S.V(X,0,S.fWin.position.z-11)); S.proj('pitch',S.V(X,0,-58));
  fadeIO(S,lt,d,0.3,0.4);
});
// H both arenas from very high
add(bar(64),bar(69),(S,lt,d)=>{
  const u=lt/d; const X=S.FX;
  S.scene.fog.density=0.0002; cam(S,S.V(X*0.5-20*u,260+30*u,400-30*u),S.V(X*0.5,0,0),40);
  S.setBall(loop(lt*0.5,1.2)-0.2,0.3,0.6,1);
  S.fBall.visible=true; S.fBall.position.set(6,0.4,-50+100*loop(lt*0.19,1));
  S.proj('tennis',S.V(0,0,30)); S.proj('football',S.V(X,0,72));
  fadeIO(S,lt,d,0.4,0.3);
});
// I1 pull back to a field of arenas (other people's lives)
add(bar(69),bar(74),(S,lt,d)=>{
  const u=easeIO(lt/d); const f=S.field.position;
  S.field.visible=true; S.scene.fog.density=0.0004; cam(S,S.V(f.x+40,60+500*u,f.z+260+400*u),S.V(f.x,0,f.z-200*u),45);
  fadeIO(S,lt,d,0.6,0.2);
});
// I2 dive into courtside: ball streak (your own life)
add(bar(74),bar(77),(S,lt,d)=>{
  const u=easeIO(Math.min(1,lt/1.6));
  cam(S,lerpV(S,S.V(40,220,240),S.V(S.SEAT.x-0.3,S.SEAT.y-0.5,0.3),u),lerpV(S,S.V(0,0,0),S.V(0,1,-2),u),lerpV(S,S.V(40,0,0),S.V(64,0,0),u).x);
  const tb=loop(lt-1.4,1.6)-0.2; if(lt>1.4) S.setBall(tb,0.09,0.15,1);
  S.bloom.strength=1.2; fadeIO(S,lt,d,0.05,0.8);
});
// J closing: drifting in dark with dust
add(bar(77),bar(82),(S,lt,d)=>{
  cam(S,S.V(0,30+lt*0.6,90-lt*1.2),S.V(0,12,0),40); S.gridMat.uniforms.uOp.value=0.4;
  S.finalPass.uniforms.uFade.value=0.35*Math.min(1,lt/1.0, (d-lt)/1.0);
});
// K sources: black
add(bar(82),999,(S,lt,d)=>{ cam(S,S.V(0,30,90),S.V(0,12,0),40); S.finalPass.uniforms.uFade.value=0.12; });
export const TOTAL=bar(82)+6.5;
