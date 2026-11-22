// EP13 网中间矮：EffectCraft 生成的光效素材（黑底，ffmpeg 用 screen 叠到强拍上）
var p=app.project;
function solid(comp,name){ return comp.layers.addSolid([0,0,0],name,1920,1080,1,comp.duration); }
// 1) 镜头光晕扫过：HIT / 扯断 / 拉带子 强拍
var c1=p.items.addComp("flare",1920,1080,1,1.2,30);
var l1=solid(c1,"bg"); var f=l1.Effects.addProperty("Lens Flare");
f.property("Lens Type").setValue(3);
var b=f.property("Flare Brightness"); b.setValueAtTime(0,0); b.setValueAtTime(0.07,130); b.setValueAtTime(0.4,55); b.setValueAtTime(1.2,0);
var ce=f.property("Flare Center"); ce.setValueAtTime(0,[760,430]); ce.setValueAtTime(1.2,[1160,430]);
// 2) 金色光扫：章节转场
var c2=p.items.addComp("sweep",1920,1080,1,0.9,30);
var l2=solid(c2,"bg"); var s=l2.Effects.addProperty("Light Sweep");
s.property("Direction").setValue(-24); s.property("Shape").setValue(1); s.property("Width").setValue(260);
s.property("Sweep Intensity").setValue(70); s.property("Edge Intensity").setValue(120); s.property("Edge Thickness").setValue(2.5);
s.property("Light Color").setValue([1,0.80,0.45,1]);
var gb=l2.Effects.addProperty("Gaussian Blur"); gb.property(1).setValue(40);
var sc=s.property("Center"); sc.setValueAtTime(0,[-400,540]); sc.setValueAtTime(0.9,[2400,540]);
p.save(new File("/workspace/tools_ext/vfx/ep13_vfx.ecproj"));
writeLn("ok "+p.numItems);
