// 只补锚点：node anchors.js <起始帧> <结束帧> <输出.anchors.json>（渲染中断、mp4 完整但锚点没写出来时用）
const {chromium}=require('playwright'); const fs=require('fs');
const [,,f0,f1,out]=process.argv; const FPS=30;
(async()=>{
 const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
 const p=await b.newPage({viewport:{width:1920,height:1080}});
 await p.goto('http://127.0.0.1:8765/index.html?w=1920&h=1080'); await p.waitForFunction('window.READY===true',{timeout:120000});
 const anchors=await p.evaluate(([a,z,fps])=>{ const r=[]; for(let f=a;f<z;f++) r.push([f,JSON.parse(window.renderAt(f/fps,true))]); return r; },[+f0,+f1,FPS]);
 fs.writeFileSync(out,JSON.stringify(anchors)); console.log('anchors',anchors.length); await b.close();
})();
