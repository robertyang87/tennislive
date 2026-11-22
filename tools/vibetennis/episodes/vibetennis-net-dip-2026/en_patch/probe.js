// 逐帧（不出图）比对中英两版 3D 里可见的字：node probe.js <端口> <输出.json>
const {chromium}=require('playwright'); const fs=require('fs');
const P=process.argv[2]||8771, OUT=process.argv[3]||'probe.json';
(async()=>{ const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
 const res={};
 for(const L of ['zh','en']){ const p=await b.newPage({viewport:{width:480,height:270}}); p.on('pageerror',e=>console.error('PAGEERR',e.message));
   await p.goto(`http://127.0.0.1:${P}/index.html?w=480&h=270&lang=${L}`,{timeout:180000}); await p.waitForFunction('window.READY===true',{timeout:180000});
   res[L]=await p.evaluate(()=>{ const N=Math.round(window.__TOTAL||0); const out=[]; const tot=window.CUTS? null:null; return null; });
   const N=JSON.parse(fs.readFileSync('r3d/timeline.json')).total*30|0;
   res[L]=await p.evaluate((N)=>{ const o=[]; for(let f=0;f<=N;f++) o.push(window.textProbe(f/30).join('|')); return o; },N);
   console.log(L,res[L].length); await p.close(); }
 const d=res.zh.map((s,i)=>s!==res.en[i]?1:0); fs.writeFileSync(OUT,JSON.stringify(d)); console.log('diff frames',d.reduce((a,b)=>a+b,0),'/',d.length); await b.close(); })();
