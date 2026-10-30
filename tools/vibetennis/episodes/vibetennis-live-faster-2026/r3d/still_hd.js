const puppeteer=require('puppeteer-core'); const fs=require('fs');
const times=process.argv.slice(2).map(Number);
(async()=>{
 const b=await puppeteer.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:'new',args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--window-size=1620,2160']});
 const p=await b.newPage(); await p.setViewport({width:1620,height:2160});
 p.on('console',m=>{ if(m.type()==='error'||m.type()==='warn') console.error('PAGE',m.text().slice(0,300)); }); p.on('pageerror',e=>console.error('PAGEERR',e.message));
 await p.goto('http://127.0.0.1:8765/index.html?w=1620&h=2160'); await p.waitForFunction('window.READY===true',{timeout:60000});
 const info=await p.evaluate(()=>{const gl=document.querySelector('canvas').getContext('webgl2'); const e=gl.getExtension('WEBGL_debug_renderer_info'); return e?gl.getParameter(e.UNMASKED_RENDERER_WEBGL):'?';}); console.log(info);
 fs.mkdirSync("stills_hd",{recursive:true});
 for(const t of times){ const t0=Date.now(); const r=await p.evaluate(t=>{ const a=window.renderAt(t); return [a,document.querySelector('canvas').toDataURL('image/jpeg',0.9)]; },t);
   fs.writeFileSync(`stills_hd/p_${t.toFixed(2).padStart(7,'0')}.jpg`,Buffer.from(r[1].split(',')[1],'base64')); fs.writeFileSync(`stills_hd/p_${t.toFixed(2).padStart(7,'0')}.json`,r[0]); console.log(t,Date.now()-t0,'ms'); }
 await b.close();
})();
