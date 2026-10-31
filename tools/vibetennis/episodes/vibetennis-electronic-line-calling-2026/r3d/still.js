// 抽静帧：node still.js <秒> <秒> ...  → stills/s_XXXX.XX.jpg（+ .json 锚点）
const {chromium}=require('playwright'); const fs=require('fs');
const times=process.argv.slice(2).map(Number); const W=+(process.env.W||1920), H=+(process.env.H||1080), P=process.env.PORT||8765, D=process.env.OUT||'stills';
(async()=>{
 const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
 const p=await b.newPage({viewport:{width:W,height:H}});
 p.on('console',m=>{ if(m.type()==='error'||m.type()==='warning') console.error('PAGE',m.text().slice(0,300)); }); p.on('pageerror',e=>console.error('PAGEERR',e.message));
 await p.goto(`http://127.0.0.1:${P}/index.html?w=${W}&h=${H}`); await p.waitForFunction('window.READY===true',{timeout:120000});
 fs.mkdirSync(D,{recursive:true});
 for(const t of times){ const t0=Date.now(); const r=await p.evaluate(t=>{ const a=window.renderAt(t); return [a,document.querySelector('canvas').toDataURL('image/jpeg',0.9)]; },t);
   const n=`${D}/s_${t.toFixed(2).padStart(7,'0')}`; fs.writeFileSync(n+'.jpg',Buffer.from(r[1].split(',')[1],'base64')); fs.writeFileSync(n+'.json',r[0]); console.log(t,Date.now()-t0,'ms'); }
 await b.close();
})();
