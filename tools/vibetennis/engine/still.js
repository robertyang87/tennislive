// 渲静帧：node still.js <端口> <输出目录> <t1> [t2 …]（秒）。语言走 VT_LANG（默认 zh）。
// 和 cap.js 同一条路（Playwright Chromium + swiftshader、window.renderAt(t)），只是一帧一张 jpg，
// 给渲前审片包用：整片渲之前先把每个镜头的样子摆出来看（EP05 的看台缺块、顶棚有孔、地球固定高度
// 都是整段渲完才被所有者看出来的，一张静帧几秒钟就能看出）。
const {chromium}=require('playwright'); const fs=require('fs');
const [,,port,out,...ts]=process.argv;
(async()=>{
 const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
 const p=await b.newPage({viewport:{width:1920,height:1080}});
 p.on('pageerror',e=>console.error('PAGEERR',e.message));
 await p.goto(`http://127.0.0.1:${port}/index.html?w=1920&h=1080&lang=${process.env.VT_LANG||'zh'}`,{timeout:180000});
 await p.waitForFunction('window.READY===true',{timeout:120000});
 fs.mkdirSync(out,{recursive:true});
 for(const t of ts.map(Number)){
   const url=await p.evaluate(t=>{ window.renderAt(t); return document.querySelector('canvas').toDataURL('image/jpeg',0.9); },t);
   fs.writeFileSync(`${out}/s_${t.toFixed(2).padStart(7,'0')}.jpg`,Buffer.from(url.split(',')[1],'base64'));
 }
 await b.close();
})().catch(e=>{ console.error(e); process.exit(1); });
