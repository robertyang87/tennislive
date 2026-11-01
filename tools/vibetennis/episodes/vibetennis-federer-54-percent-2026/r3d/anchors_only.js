// 只算锚点不出图：node anchors_only.js <起始帧> <结束帧> <输出.json>（renderAt(t,true) 不跑合成渲染，几分钟一段）
const {chromium}=require('playwright'); const fs=require('fs');
const [,,f0,f1,out]=process.argv; const P=process.env.PORT||8766;
(async()=>{ const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
 const p=await b.newPage({viewport:{width:1920,height:1080}});
 await p.goto(`http://127.0.0.1:${P}/index.html?w=1920&h=1080&lang=zh`); await p.waitForFunction('window.READY===true',{timeout:120000});
 const res=await p.evaluate(([a,z])=>{ const o=[]; for(let f=a;f<z;f++) o.push([f,JSON.parse(window.renderAt(f/30,true))]); return o; },[+f0,+f1]);
 fs.writeFileSync(out,JSON.stringify(res)); console.log(res.length); await b.close(); })();
