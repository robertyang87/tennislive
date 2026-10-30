// 分段渲染：node cap.js <起始帧> <结束帧> <输出.mp4> [宽] [高] [端口]
// 用本机预装的 Playwright Chromium（swiftshader 软件 GL），逐帧调用 window.renderAt(t)，
// JPEG 管道喂给 ffmpeg；每帧的 2D 锚点写到 <输出>.anchors.json 给 overlay.py 用。
const {chromium}=require('playwright'); const {spawn}=require('child_process'); const fs=require('fs');
const [,,f0,f1,out,w,h,port]=process.argv; const FPS=30, W=+(w||1920), H=+(h||1080), P=port||8765;
(async()=>{
 const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
 const p=await b.newPage({viewport:{width:W,height:H}});
 p.on('console',m=>{ if(m.type()==='error') console.error('PAGE',m.text()); }); p.on('pageerror',e=>console.error('PAGEERR',e.message));
 await p.goto(`http://127.0.0.1:${P}/index.html?w=${W}&h=${H}`); await p.waitForFunction('window.READY===true',{timeout:120000});
 const ff=spawn('ffmpeg',['-y','-loglevel','error','-f','image2pipe','-framerate',String(FPS),'-c:v','mjpeg','-i','-','-c:v','libx264','-preset','ultrafast','-crf','12','-pix_fmt','yuv420p',out]);
 const anchors=[]; const t0=Date.now();
 for(let f=+f0;f<+f1;f++){
   const r=await p.evaluate(t=>{ const a=window.renderAt(t); return [a, document.querySelector('canvas').toDataURL('image/jpeg',0.93)]; }, f/FPS);
   anchors.push([f,JSON.parse(r[0])]);
   const buf=Buffer.from(r[1].split(',')[1],'base64'); if(!ff.stdin.write(buf)) await new Promise(res=>ff.stdin.once('drain',res));
   if((f-f0)%90===0) console.log(out,'frame',f,((Date.now()-t0)/(f-f0+1)).toFixed(0),'ms/f');
 }
 ff.stdin.end(); await new Promise(r=>ff.on('close',r)); fs.writeFileSync(out+'.anchors.json',JSON.stringify(anchors)); await b.close();
})();
